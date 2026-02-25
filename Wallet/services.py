from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from decimal import Decimal
from typing import cast
from Wallet.models import Wallet, Transaction
from Auth.models import User
from fastapi import HTTPException, status


class WalletService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Wallet creation
    async def create_wallet(self, user_id: int) -> Wallet:
        new_wallet = Wallet(user_id=user_id, balance=Decimal("0.00"))
        self.session.add(new_wallet)
        await self.session.commit()
        await self.session.refresh(new_wallet)
        return new_wallet

    # Get wallet balance
    async def get_wallet(self, wallet_id: int) -> Wallet:
        results = await self.session.execute(select(Wallet).where(Wallet.id == wallet_id))
        wallet = results.scalar_one_or_none()

        if wallet is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

        return wallet

    #get transaction
    async def get_transactions(self, wallet_id: int) -> list[Transaction]:  # type: ignore[override]
        results = await self.session.execute(
            select(Transaction)
            .where(Transaction.wallet_id == wallet_id)
            .order_by(Transaction.timestamp.desc())
        )
        transactions = cast(list[Transaction], results.scalars().all())
        return transactions