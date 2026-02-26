from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db import get_session
from Wallet.services import WalletService
from Wallet.schemas import WalletResponse, TransactionResponse
from Auth.dependencies import get_current_user

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.post("/balance", response_model=WalletResponse)
async def get_balance(current_user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    wallet = await wallet_service.get_wallet_for_update(current_user["id"])
    return wallet