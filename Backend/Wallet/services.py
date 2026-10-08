import hashlib
import hmac
import logging
from decimal import Decimal
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.config import settings
from Backend.Wallet.enums import TransactionType
from Backend.Wallet.models import Transaction, Wallet

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
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient funds")

        wallet.balance = new_balance
        transaction = Transaction(wallet_id=wallet.id, amount=amount, type=transaction_type, tx_hash=tx_hash)

        self.session.add(transaction)
        await self.session.flush()
        await self.session.refresh(transaction)
        await self.session.refresh(wallet)
        return transaction

    async def process_solana_webhook(self, raw_body: bytes, signature: str, tx_signature: str) -> None:
        """Ack Solana deposit webhooks. Payload is signature-only; never 404.

        CreditOrder matching + RPC verify land in later phases. Until then,
        unknown/unmatched signatures are logged and acknowledged with 200 so
        providers do not retry-storm.
        """
        expected = hmac.new(
            settings.SOLANA_WEBHOOK_SECRET.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

        # Phase 0: no CreditOrder table yet — treat every notified signature as unmatched.
        logger.info(
            "solana webhook unmatched signature=%s (CreditOrder matching not wired yet)",
            tx_signature,
        )

    async def credit(self, user_id: int, amount: Decimal, transaction_type: TransactionType = TransactionType.CREDIT, tx_hash: str | None = None) -> Transaction:
        wallet = await self.get_wallet_for_update(user_id)
        return await self._apply_transaction(wallet, amount, transaction_type, tx_hash=tx_hash)

    async def debit(self, user_id: int, amount: Decimal, transaction_type: TransactionType = TransactionType.DEBIT) -> Transaction:
        wallet = await self.get_wallet_for_update(user_id)
        return await self._apply_transaction(wallet, -amount, transaction_type)
