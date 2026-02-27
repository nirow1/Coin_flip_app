from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from Wallet.services import WalletService
from Wallet.schemas import WalletResponse, TransactionResponse
from Auth.dependencies import get_current_user

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.get("/balance", response_model=WalletResponse)
async def get_balance(current_user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    wallet = await wallet_service.get_wallet(current_user["id"])
    return wallet

@router.get("/transactions", response_model=list[TransactionResponse])
async def get_transactions(current_user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    wallet = await wallet_service.get_wallet(current_user["id"])
    transactions = await wallet_service.get_transactions(wallet.id)
    return transactions