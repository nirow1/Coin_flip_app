import hashlib
import hmac
import logging
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from urllib.parse import urlencode

from fastapi import HTTPException, status
from redis.asyncio import Redis
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Finalized
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.config import settings
from Backend.Core.core_solana import (
    full_account_keys,
    iter_memos,
    verify_fetched_solana_transaction,
)
from Backend.Core.exceptions import InsufficientFundsError
from Backend.Wallet.enums import Chain, CreditOrderStatus, QuoteKind, TransactionType
from Backend.Wallet.models import (
    CreditOrder,
    PaymentQuote,
    Transaction,
    UnmatchedDeposit,
    Wallet,
)
from Backend.Wallet.pricing import quote_buy_lamports
from Backend.Wallet.schemas import MAX_PENDING_CREDIT_ORDERS

logger = logging.getLogger(__name__)

LAMPORTS_PER_SOL = Decimal(1000000000)
_RPC_TIMEOUT_SEC = 10
OVERPAY_MAX_RATIO = Decimal("1.05")


class WalletService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Wallet creation
    async def create_wallet(self, user_id: int) -> Wallet:
        new_wallet = Wallet(user_id=user_id, balance=Decimal("0.00"))
        self.session.add(new_wallet)
        return new_wallet

    # Get wallet (read-only)
    async def get_wallet(self, user_id: int) -> Wallet:
        result = await self.session.execute(select(Wallet).where(Wallet.user_id == user_id))
        wallet = result.scalar_one_or_none()

        if wallet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

        return wallet

    # Get wallet with lock (for write operations only)
    async def get_wallet_for_update(self, user_id: int) -> Wallet:
        results = await self.session.execute(select(Wallet)
                                             .where(Wallet.user_id == user_id)
                                             .with_for_update()
                                             )
        wallet = results.scalar_one_or_none()

        if wallet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

        return wallet

    # Get transactions by user_id — fetches wallet internally
    async def get_transactions(self, user_id: int) -> list[Transaction]:  # type: ignore[override]
        results = await self.session.execute(
            select(Transaction)
            .join(Wallet, Transaction.wallet_id == Wallet.id)
            .where(Wallet.user_id == user_id)
            .order_by(Transaction.id.desc())
        )
        transactions = cast(list[Transaction], results.scalars().all())
        return transactions

    async def _apply_transaction(self, wallet: Wallet, amount: Decimal, transaction_type: TransactionType, tx_hash: str | None = None) -> Transaction:
        new_balance = wallet.balance + amount

        if new_balance < Decimal("0.00"):
            raise InsufficientFundsError()

        wallet.balance = new_balance
        transaction = Transaction(wallet_id=wallet.id, amount=amount, type=transaction_type, tx_hash=tx_hash)

        self.session.add(transaction)
        await self.session.flush()
        await self.session.refresh(transaction)
        await self.session.refresh(wallet)
        return transaction

    async def verify_solana_webhook_hmac(
        self,
        *,
        raw_body: bytes,
        signature_header: str,
        timestamp_header: str,
    ) -> None:
        """Verify timestamp skew + HMAC over ``{timestamp}.{body}`` before parsing JSON."""
        from Backend.Wallet.schemas import WEBHOOK_MAX_SKEW_SECONDS

        if not signature_header.isascii() or not timestamp_header.isascii():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
        if not signature_header or not timestamp_header:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

        try:
            ts = int(timestamp_header)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            ) from exc

        now = int(datetime.now(UTC).timestamp())
        if abs(now - ts) > WEBHOOK_MAX_SKEW_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Webhook timestamp expired",
            )

        secret = settings.SOLANA_WEBHOOK_SECRET
        secret_bytes = (
            secret.get_secret_value()
            if hasattr(secret, "get_secret_value")
            else str(secret)
        ).encode()
        signed = f"{timestamp_header}.".encode("ascii") + raw_body
        expected = hmac.new(
            secret_bytes,
            signed,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature_header):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    async def process_solana_webhook(self, tx_signature: str) -> None:
        """Signature-only webhook: always ack; matching/credit happen here."""
        await self.process_deposit_signature(tx_signature)

    async def create_buy_quote(self, user_id: int, credits: int, chain: Chain, redis: Redis) -> PaymentQuote:
        priced = await quote_buy_lamports(credits, redis)
        now = datetime.now(UTC)
        quote = PaymentQuote(
            user_id=user_id,
            kind=QuoteKind.BUY,
            chain=chain,
            payload={
                "credits": credits,
                "chain": chain.value,
                "lamports": priced["lamports"],
                "price": priced["price"],
                "fee": priced["fee"],
                "price_source": priced["price_source"],
            },
            expires_at=now + timedelta(minutes=5),
        )
        self.session.add(quote)
        await self.session.flush()
        return quote

    async def consume_quote(
        self,
        *,
        quote_id: str,
        user_id: int,
        kind: QuoteKind,
    ) -> dict:
        now = datetime.now(UTC)
        stmt = (
            update(PaymentQuote)
            .where(
                PaymentQuote.id == quote_id,
                PaymentQuote.user_id == user_id,
                PaymentQuote.kind == kind,
                PaymentQuote.consumed_at.is_(None),
                PaymentQuote.expires_at > now,
            )
            .values(consumed_at=now)
            .returning(PaymentQuote.payload, PaymentQuote.expires_at)
        )
        result = await self.session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quote invalid, expired, or already used",
            )
        payload, expires_at = row
        return {"payload": payload, "expires_at": expires_at}

    async def create_credit_order(self, *, user_id: int, quote_id: str) -> CreditOrder:
        consumed = await self.consume_quote(
            quote_id=quote_id,
            user_id=user_id,
            kind=QuoteKind.BUY,
        )
        payload = consumed["payload"]
        expires_at = consumed["expires_at"]

        pending = await self.session.scalar(
            select(func.count())
            .select_from(CreditOrder)
            .where(
                CreditOrder.user_id == user_id,
                CreditOrder.status == CreditOrderStatus.PENDING,
            )
        )
        if (pending or 0) >= MAX_PENDING_CREDIT_ORDERS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum number of pending credit orders reached",
            )

        reference_pubkey = str(Keypair().pubkey())
        order_ref = secrets.token_urlsafe(16)

        order = CreditOrder(
            user_id=user_id,
            credits=Decimal(str(payload["credits"])),
            chain=Chain(payload["chain"]),
            status=CreditOrderStatus.PENDING,
            order_ref=order_ref,
            reference_pubkey=reference_pubkey,
            quoted_atomic_amount=int(payload["lamports"]),
            receive_address=settings.SOLANA_COLD_RECEIVE_ADDRESS,
            expires_at=expires_at,
            quote_id=quote_id,
        )

        self.session.add(order)
        await self.session.flush()
        await self.session.refresh(order)
        return order

    def _order_payment_fields(self, order: CreditOrder) -> dict:
        amount_sol = str(Decimal(order.quoted_atomic_amount) / LAMPORTS_PER_SOL)
        query = urlencode(
            {
                "amount": amount_sol,
                "reference": order.reference_pubkey,
                "memo": order.order_ref,
            }
        )
        solana_pay_url = f"solana:{order.receive_address}?{query}"
        return {"amount_sol": amount_sol, "solana_pay_url": solana_pay_url}

    async def get_credit_order_for_owner(self, *, user_id: int, order_id: int) -> CreditOrder:
        result = await self.session.execute(
            select(CreditOrder).where(
                CreditOrder.id == order_id,
                CreditOrder.user_id == user_id,
            )
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credit order not found",
            )
        return order

    async def process_deposit_signature(self, tx_signature: str) -> None:
        tx = await self._fetch_finalized_tx(tx_signature)
        if tx is None:
            return

        account_keys, memos = self._tx_account_keys_and_memos(tx)
        lamports = self._cold_lamports_delta(tx, account_keys)
        order = await self._find_order_for_tx(account_keys, memos)

        if order is None:
            block_time_raw = getattr(tx, "block_time", None) or getattr(tx, "blockTime", None)
            block_time = (
                datetime.fromtimestamp(int(block_time_raw), UTC)
                if block_time_raw is not None
                else None
            )
            self.session.add(
                UnmatchedDeposit(
                    tx_hash=tx_signature,
                    lamports=lamports,
                    raw_memo=memos[0] if memos else None,
                    sender=account_keys[0] if account_keys else None,
                    chain=Chain.SOLANA,
                    reference_pubkey=None,
                    block_time=block_time,
                )
            )
            try:
                await self.session.flush()
            except IntegrityError:
                await self.session.rollback()
            return

        locked = await self.session.execute(
            select(CreditOrder)
            .where(CreditOrder.id == order.id)
            .with_for_update()
        )
        order = locked.scalar_one()

        if order.paid_tx_hash == tx_signature or order.status == CreditOrderStatus.PAID:
            return

        verified = verify_fetched_solana_transaction(
            tx,
            tx_hash=tx_signature,
            expected_destination=order.receive_address,
            expected_lamports=0,
            expected_memo=order.order_ref,
            expected_reference=order.reference_pubkey,
        )

        order.received_atomic_amount = verified.received_lamports

        quoted = int(order.quoted_atomic_amount)
        received = int(verified.received_lamports)
        max_ok = int(Decimal(quoted) * OVERPAY_MAX_RATIO)

        paid_at_block = (
            datetime.fromtimestamp(verified.block_time, UTC)
            if verified.block_time is not None
            else None
        )
        expires_at = order.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        late = paid_at_block is not None and paid_at_block > expires_at
        under = received < quoted
        over = received > max_ok

        if under or over or late or order.status != CreditOrderStatus.PENDING:
            order.status = CreditOrderStatus.NEEDS_REVIEW
            order.paid_tx_hash = tx_signature
            order.paid_at = paid_at_block or datetime.now(UTC)
            if under:
                order.review_reason = "underpaid"
            elif over:
                order.review_reason = "overpaid"
            elif late:
                order.review_reason = "late"
            else:
                order.review_reason = f"unexpected_status:{order.status.value}"
            return

        order.status = CreditOrderStatus.PAID
        order.paid_tx_hash = tx_signature
        order.paid_at = datetime.now(UTC)
        try:
            await self.credit(
                order.user_id,
                Decimal(order.credits),
                TransactionType.PURCHASE,
                tx_hash=tx_signature,
            )
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()

    async def _fetch_finalized_tx(self, tx_signature: str):
        async with AsyncClient(settings.SOLANA_RPC_URL, timeout=_RPC_TIMEOUT_SEC) as client:
            resp = await client.get_transaction(
                Signature.from_string(tx_signature),
                encoding="jsonParsed",
                commitment=Finalized,
                max_supported_transaction_version=0,
            )
        return resp.value

    async def _find_order_for_tx(
        self, account_keys: list[str], memos: list[str]
    ) -> CreditOrder | None:
        result = await self.session.execute(
            select(CreditOrder)
            .where(CreditOrder.reference_pubkey.in_(account_keys))
            .order_by(CreditOrder.id.asc())
            .limit(1)
        )
        order = result.scalar_one_or_none()
        if order is not None:
            return order
        if not memos:
            return None
        result = await self.session.execute(
            select(CreditOrder)
            .where(CreditOrder.order_ref.in_(memos))
            .order_by(CreditOrder.id.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _tx_account_keys_and_memos(self, tx) -> tuple[list[str], list[str]]:
        meta = tx.transaction.meta
        message = tx.transaction.transaction.message
        keys = full_account_keys(message, meta, encoding="jsonParsed")
        memos = iter_memos(message, keys)
        return keys, memos

    def _cold_lamports_delta(self, tx, account_keys: list[str]) -> int:
        cold = str(Pubkey.from_string(settings.SOLANA_COLD_RECEIVE_ADDRESS))
        meta = tx.transaction.meta
        for i, key in enumerate(account_keys):
            if key == cold:
                return int(meta.post_balances[i]) - int(meta.pre_balances[i])
        return 0

    async def credit(self, user_id: int, amount: Decimal, transaction_type: TransactionType = TransactionType.CREDIT, tx_hash: str | None = None) -> Transaction:
        if amount <= 0:
            raise ValueError("credit amount must be positive")
        wallet = await self.get_wallet_for_update(user_id)
        return await self._apply_transaction(wallet, amount, transaction_type, tx_hash=tx_hash)

    async def debit(self, user_id: int, amount: Decimal, transaction_type: TransactionType = TransactionType.DEBIT) -> Transaction:
        if amount <= 0:
            raise ValueError("debit amount must be positive")
        wallet = await self.get_wallet_for_update(user_id)
        return await self._apply_transaction(wallet, -amount, transaction_type)
