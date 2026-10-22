import hashlib
import hmac
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.config import settings
from Backend.Core.exceptions import InsufficientFundsError
from Backend.Wallet.enums import Chain, QuoteKind, TransactionType
from Backend.Wallet.models import PaymentQuote, Transaction, Wallet
from Backend.Wallet.pricing import quote_buy_lamports

logger = logging.getLogger(__name__)


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
        """Ack Solana deposit webhooks. Payload is signature-only; never 404.

        CreditOrder matching + RPC verify land in later phases. Until then,
        unknown/unmatched signatures are logged and acknowledged with 200 so
        providers do not retry-storm.
        """
        logger.info(
            "solana webhook unmatched signature=%s (CreditOrder matching not wired yet)",
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
            .returning(PaymentQuote.payload)
        )
        result = await self.session.execute(stmt)
        payload = result.scalar_one_or_none()
        if payload is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Quote invalid, expired, or already used",
            )
        return payload

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
