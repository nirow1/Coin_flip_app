from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from decimal import Decimal
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from Wallet.models import Wallet, Transaction
from Wallet.enums import TransactionType
from Core.core_solana import solana_send_transaction, verify_solana_transaction
from config import settings
from fastapi import HTTPException, status


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
        await self.session.commit()
        await self.session.refresh(transaction)
        await self.session.refresh(wallet)
        return transaction

    async def deposit_sol(self, user_id: int, amount_sol: Decimal, tx_hash: str):
        # 1. Verify on-chain transaction BEFORE crediting balance
        try:
            await verify_solana_transaction(
                tx_hash=tx_hash,
                expected_destination=settings.SOLANA_HOT_WALLET_ADDRESS,
                expected_amount_sol=amount_sol,
                rpc_url=settings.SOLANA_RPC_URL
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"On-chain deposit verification failed: {e}"
            )

        # 2. Only credit if verification passed
        try:
            return await self.credit(
                user_id=user_id,
                amount=amount_sol,
                transaction_type=TransactionType.DEPOSIT_SOLANA,
                tx_hash=tx_hash
            )
        except IntegrityError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Transaction {tx_hash} has already been processed"
            )

    async def withdraw_sol(self, user_id: int, amount_sol: Decimal, destination_address: str):
        # 1. Debit internal balance first
        transaction = await self.debit(
            user_id=user_id,
            amount=amount_sol,
            transaction_type=TransactionType.WITHDRAW_SOLANA
        )

        # 2. Send SOL on-chain; if it fails, refund the internal balance
        try:
            tx_sig = await solana_send_transaction(
                destination_address,
                amount_sol,
                settings.SOLANA_RPC_URL
            )
        except Exception as e:
            await self.credit(
                user_id=user_id,
                amount=amount_sol,
                transaction_type=TransactionType.CREDIT
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"On-chain transaction failed, withdrawal reversed: {e}"
            )

        return {"transaction": transaction, "tx_signature": tx_sig}

    async def credit(self, user_id: int, amount: Decimal, transaction_type: TransactionType = TransactionType.CREDIT, tx_hash: str | None = None) -> Transaction:
        wallet = await self.get_wallet_for_update(user_id)
        return await self._apply_transaction(wallet, amount, transaction_type, tx_hash=tx_hash)

    async def debit(self, user_id: int, amount: Decimal, transaction_type: TransactionType = TransactionType.DEBIT) -> Transaction:
        wallet = await self.get_wallet_for_update(user_id)
        return await self._apply_transaction(wallet, -amount, transaction_type)