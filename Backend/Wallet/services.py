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
from solana.exceptions import SolanaRpcException
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Finalized
from solana.rpc.core import RPCException
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.solders import get_associated_token_address
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.Core.security import verify_password
from Backend.config import settings
from Backend.Core.core_solana import (
    assert_solana_withdraw_destination,
    full_account_keys,
    iter_memos,
    verify_fetched_solana_transaction,
)
from Backend.Core.exceptions import InsufficientFundsError
from Backend.Wallet.enums import (
    Chain,
    CreditOrderStatus,
    QuoteKind,
    TransactionType,
    UnmatchedDepositStatus,
    WithdrawalStatus,
    WithdrawAsset,
)
from Backend.Wallet.models import (
    CreditOrder,
    PaymentQuote,
    Transaction,
    UnmatchedDeposit,
    Wallet,
    Withdrawal,
)
from Backend.Wallet.pricing import quote_buy_lamports, quote_withdraw_atomic
from Backend.Wallet.schemas import MAX_PENDING_CREDIT_ORDERS, AdminResolveAction

logger = logging.getLogger(__name__)

LAMPORTS_PER_SOL = Decimal(1000000000)
_RPC_TIMEOUT_SEC = 10
# Accept at most ~2% above the quoted lamports. Anything higher needs review.
OVERPAY_MAX_RATIO = Decimal("1.02")


class DepositTransactionNotFetched(Exception):
    """getTransaction returned nothing. Retryable; the poller must not advance."""

    def __init__(self, signature: str) -> None:
        self.signature = signature
        super().__init__(f"transaction not fetched: {signature}")


def _unmatched_is_junk(tx, lamports: int) -> bool:
    """Failed transactions and cold outflows are not deposits."""
    meta = getattr(getattr(tx, "transaction", None), "meta", None)
    err = getattr(meta, "err", None) if meta is not None else None
    return err is not None or lamports <= 0


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
        """Signature-only webhook: always ack; matching/credit happen here.

        A signature RPC has not indexed yet is left for the cold-address poller.
        That path raises so the cursor stays put and the next tick retries.
        """
        try:
            await self.process_deposit_signature(tx_signature)
        except DepositTransactionNotFetched:
            logger.info(
                "webhook signature %s not fetched yet; acknowledging for poller retry",
                tx_signature,
            )

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

    async def create_withdrawal(
        self,
        *,
        user_id: int,
        quote_id: str,
        idempotency_key: str,
        password: str,
        password_hash: str,
    ) -> Withdrawal:
        if not verify_password(password, password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid password",
            )

        existing = await self._withdrawal_by_idempotency(user_id, idempotency_key)
        if existing is not None:
            return existing

        try:
            consumed = await self.consume_quote(
                quote_id=quote_id,
                user_id=user_id,
                kind=QuoteKind.WITHDRAW,
            )
        except HTTPException as exc:
            # The other request consumed the quote and inserted the row first.
            if exc.status_code == status.HTTP_400_BAD_REQUEST:
                raced = await self._withdrawal_by_idempotency(user_id, idempotency_key)
                if raced is not None:
                    return raced
            raise
        payload = consumed["payload"]
        credits = Decimal(str(payload["credits"]))
        net_atomic = int(payload["net_atomic"])
        asset = WithdrawAsset(payload["asset"])
        chain = Chain(payload["chain"])
        destination = str(payload["destination"])

        # Hold this user's wallet row so two requests cannot both pass the caps.
        # debit() locks the same row again below; that second lock stays as-is.
        await self.get_wallet_for_update(user_id)

        since = datetime.now(UTC) - timedelta(hours=24)
        user_total = await self._withdrawn_credits_since(since=since, user_id=user_id)
        if user_total + credits > settings.WITHDRAW_DAILY_USER_CAP_CREDITS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Daily withdraw cap exceeded",
            )

        global_total = await self._withdrawn_credits_since(since=since)
        if global_total + credits > settings.WITHDRAW_DAILY_GLOBAL_CAP_CREDITS:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Global withdraw cap exceeded",
            )
        
        try:
            await self.debit(
                user_id,
                credits,
                transaction_type=TransactionType.WITHDRAWAL,
            )
        except InsufficientFundsError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=exc.message,
            ) from exc

        withdrawal = Withdrawal(
            user_id=user_id,
            chain=chain,
            asset=asset,
            credits_debited=credits,
            net_atomic_amount=net_atomic,
            destination=destination,
            quote_id=quote_id,
            idempotency_key=idempotency_key,
            status=WithdrawalStatus.QUEUED,
        )
        self.session.add(withdrawal)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raced = await self._withdrawal_by_idempotency(user_id, idempotency_key)
            if raced is not None:
                return raced
            raise
        
        await self.session.refresh(withdrawal)
        return withdrawal

    async def _withdrawal_by_idempotency(
        self, user_id: int, idempotency_key: str
    ) -> Withdrawal | None:
        return await self.session.scalar(
            select(Withdrawal).where(
                Withdrawal.user_id == user_id,
                Withdrawal.idempotency_key == idempotency_key,
            )
        )

    async def _withdrawn_credits_since(
        self,
        *,
        since: datetime,
        user_id: int | None = None,
    ) -> Decimal:
        """Sum credits_debited for withdrawals still holding funds (not failed_refunded)."""
        stmt = select(
            func.coalesce(func.sum(Withdrawal.credits_debited), 0)
        ).where(
            Withdrawal.created_at >= since,
            Withdrawal.status != WithdrawalStatus.FAILED_REFUNDED,
        )
        if user_id is not None:
            stmt = stmt.where(Withdrawal.user_id == user_id)
        total = await self.session.scalar(stmt)
        return Decimal(str(total or 0))


    async def create_withdraw_quote(
        self,
        *,
        user_id: int,
        credits: Decimal,
        asset: WithdrawAsset,
        destination: str,
        chain: Chain,
        redis: Redis,
    ) -> PaymentQuote:
        if chain != Chain.SOLANA:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Only Solana withdrawals are implemented",
            )
        try:
            dest_info = await assert_solana_withdraw_destination(
            destination=destination,
            asset=asset,
            )
        except ValueError as exc:
            raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
            ) from exc
        
        priced = await quote_withdraw_atomic(
            credits=credits, asset=asset, redis=redis
        )

        net_atomic = int(priced["net_atomic"])
        ata = dest_info.get("ata")
        ata_rent_lamports = 0
        async with AsyncClient(
            settings.SOLANA_RPC_URL, timeout=_RPC_TIMEOUT_SEC
        ) as client:
            if asset == WithdrawAsset.USDC and ata:
                ata_info = await client.get_account_info(Pubkey.from_string(ata))
                if ata_info.value is None:
                    rent_resp = await client.get_minimum_balance_for_rent_exemption(165)
                    ata_rent_lamports = int(rent_resp.value)

            hot = Pubkey.from_string(settings.SOLANA_HOT_WALLET_ADDRESS)
            if asset == WithdrawAsset.SOL:
                bal = await client.get_balance(hot)
                available = int(bal.value)
            else:
                mint = Pubkey.from_string(settings.SOLANA_USDC_MINT)
                hot_ata = get_associated_token_address(hot, mint)
                # Missing hot ATA → RPC errors; treat as zero inventory (same as sketch).
                try:
                    tok = await client.get_token_account_balance(hot_ata)
                    available = (
                        int(tok.value.amount) if tok.value is not None else 0
                    )
                except (RPCException, SolanaRpcException):
                    available = 0
        
        reserved = await self.session.scalar(
            select(func.coalesce(func.sum(Withdrawal.net_atomic_amount), 0)).where(
                Withdrawal.chain == Chain.SOLANA,
                Withdrawal.asset == asset,
                Withdrawal.status.in_(
                    [
                        WithdrawalStatus.QUEUED,
                        WithdrawalStatus.SIGNED,
                        WithdrawalStatus.BROADCAST,
                    ]
                ),
            )
        )
        free = available - int(reserved or 0)
        if free < net_atomic:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Insufficient hot wallet inventory",
            )
        
        if asset == WithdrawAsset.USDC and ata_rent_lamports:
            sol_bal = await self._hot_sol_lamports_for_rent()
            if sol_bal < ata_rent_lamports:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Hot wallet SOL too low to create destination ATA",
                )
        
        now = datetime.now(UTC)
        payload = {
            "credits": str(credits),
            "chain": chain.value,
            "asset": asset.value,
            "destination": dest_info["destination"],
            "net_atomic": net_atomic,
            "fee_credits": priced["fee_credits"],
            "net_credits": priced["net_credits"],
            "price": priced["price"],
            "price_source": priced["price_source"],
            "ata": ata,
            "ata_rent_lamports": ata_rent_lamports,
        }
        quote = PaymentQuote(
            user_id=user_id,
            kind=QuoteKind.WITHDRAW,
            chain=chain,
            payload=payload,
            expires_at=now + timedelta(minutes=5),
        )
        self.session.add(quote)
        await self.session.flush()
        return quote
    
    async def _hot_sol_lamports_for_rent(self) -> int:
        async with AsyncClient(
            settings.SOLANA_RPC_URL, timeout=_RPC_TIMEOUT_SEC
        ) as client:
            bal = await client.get_balance(
                Pubkey.from_string(settings.SOLANA_HOT_WALLET_ADDRESS)
            )
            return int(bal.value)

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

        # Same lock as withdrawals: concurrent creates for one user run one at a time.
        await self.get_wallet_for_update(user_id)

        now = datetime.now(UTC)
        pending = await self.session.scalar(
            select(func.count())
            .select_from(CreditOrder)
            .where(
                CreditOrder.user_id == user_id,
                CreditOrder.status == CreditOrderStatus.PENDING,
                CreditOrder.expires_at > now,
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

    async def resolve_needs_review_order(self, 
                                         *,
                                         order_id: int,
                                         admin: int,
                                         action: AdminResolveAction,
                                         credits: Decimal | None = None,
                                         ) -> CreditOrder:
        result = await self.session.execute(
            select(CreditOrder)
            .where(CreditOrder.id == order_id)
            .with_for_update()
        )
        order = result.scalar_one_or_none()
        if order is None or order.status != CreditOrderStatus.NEEDS_REVIEW:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Credit order not found or not in needs_review")
        now = datetime.now(UTC)

        if action == AdminResolveAction.MARK_REFUNDED:
            order.status = CreditOrderStatus.REFUNDED
            order.resolved_by = admin
            order.resolved_at = now
            return order
        
        if not order.paid_tx_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Credit order has no paid transaction hash")

        amount = credits if credits is not None else Decimal(order.credits)
        order.status = CreditOrderStatus.PAID
        order.resolved_by  = admin
        order.resolved_at = now

        try:
            await self.credit(order.user_id, amount, TransactionType.PURCHASE, tx_hash=order.paid_tx_hash)
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction already applied",
            ) from exc
        return order
    
    async def resolve_unmatched_deposit(self, 
                                        *,
                                        deposit_id: int,
                                        admin: int,
                                        action: AdminResolveAction,
                                        user_id: int | None = None,
                                        credits: Decimal | None = None,
                                        resolved_order_id: int | None = None,
                                        ) -> UnmatchedDeposit:
        result = await self.session.execute(
            select(UnmatchedDeposit)
            .where(UnmatchedDeposit.id == deposit_id)
            .with_for_update()
        )

        deposit = result.scalar_one_or_none()
        if deposit is None or deposit.status != UnmatchedDepositStatus.OPEN:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Unmatched deposit not found or not open")
        now = datetime.now(UTC)

        if action == AdminResolveAction.MARK_REFUNDED:
            deposit.status = UnmatchedDepositStatus.REFUNDED
            deposit.resolved_by = admin
            deposit.resolved_at = now
            return deposit

        if user_id is None or credits is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User ID and credits are required")
        deposit.status = UnmatchedDepositStatus.RESOLVED
        deposit.resolved_by = admin
        deposit.resolved_at = now
        deposit.resolved_order_id = resolved_order_id
        try:
            await self.credit(user_id, credits, TransactionType.PURCHASE, tx_hash=deposit.tx_hash)
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction already applied",
            ) from exc
        return deposit

    async def list_needs_review_orders(self) -> list[CreditOrder]:
        result = await self.session.execute(
            select(CreditOrder)
            .where(CreditOrder.status == CreditOrderStatus.NEEDS_REVIEW)
            .order_by(CreditOrder.id.asc())
        )
        return list(result.scalars().all() )

    async def list_open_unmatched_deposits(self) -> list[UnmatchedDeposit]:
        result = await self.session.execute(
            select(UnmatchedDeposit)
            .where(UnmatchedDeposit.status == UnmatchedDepositStatus.OPEN)
            .order_by(UnmatchedDeposit.id.asc())
        )
        return list(result.scalars().all() )

    async def process_deposit_signature(self, tx_signature: str) -> None:
        tx = await self._fetch_finalized_tx(tx_signature)
        if tx is None:
            # Poller leaves the cursor on this signature and retries next tick.
            raise DepositTransactionNotFetched(tx_signature)

        account_keys, memos = self._tx_account_keys_and_memos(tx)
        lamports = self._cold_lamports_delta(tx, account_keys)
        order = await self._find_order_for_tx(account_keys)

        if order is None:
            if _unmatched_is_junk(tx, lamports):
                # Clean return: poller still advances. Webhook acks with no row.
                logger.info(
                    "ignoring non-credit signature %s (err or non-positive cold delta)",
                    tx_signature,
                )
                return
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

        # Same signature already stored on the order: unique no-op.
        if order.paid_tx_hash == tx_signature:
            return

        # A different payment after the order left PENDING must not overwrite
        # paid_tx_hash / amounts. Keep an audit row instead.
        if order.status != CreditOrderStatus.PENDING:
            if _unmatched_is_junk(tx, lamports):
                return
            await self._record_extra_payment(
                order,
                tx_signature,
                lamports,
                account_keys,
                memos,
                tx,
            )
            return

        try:
            verified = verify_fetched_solana_transaction(
                tx,
                tx_hash=tx_signature,
                expected_destination=order.receive_address,
                expected_lamports=0,
                expected_memo=order.order_ref,
                expected_reference=order.reference_pubkey,
            )
        except ValueError as exc:
            # Do not raise: the cold-address poller would keep this signature
            # as the cursor and never reach later deposits.
            await self._mark_verify_failed(order, tx_signature, exc)
            return

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

        if under or over or late:
            order.status = CreditOrderStatus.NEEDS_REVIEW
            order.paid_tx_hash = tx_signature
            order.paid_at = paid_at_block or datetime.now(UTC)
            if under:
                order.review_reason = "underpaid"
            elif over:
                order.review_reason = "overpaid"
            else:
                order.review_reason = "late"
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

    async def _record_extra_payment(
        self,
        order: CreditOrder,
        tx_signature: str,
        lamports: int,
        account_keys: list[str],
        memos: list[str],
        tx,
    ) -> None:
        """Insert an OPEN unmatched row for a second signature. Duplicate tx_hash is a no-op."""
        block_time_raw = getattr(tx, "block_time", None) or getattr(tx, "blockTime", None)
        block_time = (
            datetime.fromtimestamp(int(block_time_raw), UTC)
            if block_time_raw is not None
            else None
        )
        # Savepoint: a unique violation rolls back only this insert, not the order.
        try:
            async with self.session.begin_nested():
                self.session.add(
                    UnmatchedDeposit(
                        tx_hash=tx_signature,
                        lamports=lamports,
                        raw_memo=memos[0] if memos else None,
                        sender=account_keys[0] if account_keys else None,
                        chain=Chain.SOLANA,
                        reference_pubkey=order.reference_pubkey,
                        block_time=block_time,
                        resolved_order_id=order.id,
                        status=UnmatchedDepositStatus.OPEN,
                    )
                )
                await self.session.flush()
        except IntegrityError:
            return

    async def _fetch_finalized_tx(self, tx_signature: str):
        async with AsyncClient(settings.SOLANA_RPC_URL, timeout=_RPC_TIMEOUT_SEC) as client:
            resp = await client.get_transaction(
                Signature.from_string(tx_signature),
                encoding="jsonParsed",
                commitment=Finalized,
                max_supported_transaction_version=0,
            )
        return resp.value

    async def _mark_verify_failed(
        self, order: CreditOrder, tx_signature: str, exc: ValueError
    ) -> None:
        """Park a matched deposit in NEEDS_REVIEW. Never raise."""
        logger.warning(
            "deposit %s matched order %s but failed verification: %s",
            tx_signature,
            order.id,
            exc,
        )
        order.status = CreditOrderStatus.NEEDS_REVIEW
        detail = " ".join(str(exc).split())
        order.review_reason = f"verify_failed:{detail}"[:500]
        if order.paid_at is None:
            order.paid_at = datetime.now(UTC)
        if order.paid_tx_hash is not None:
            return
        taken = await self.session.scalar(
            select(CreditOrder.id)
            .where(CreditOrder.paid_tx_hash == tx_signature)
            .limit(1)
        )
        if taken is None:
            order.paid_tx_hash = tx_signature

    async def _find_order_for_tx(self, account_keys: list[str]) -> CreditOrder | None:
        """Match Solana Pay reference only. Memo is checked later in verify."""
        if not account_keys:
            return None
        result = await self.session.execute(
            select(CreditOrder)
            .where(CreditOrder.reference_pubkey.in_(account_keys))
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
