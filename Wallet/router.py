from Wallet.schemas import WalletResponse, TransactionResponse, AmountRequest
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from Auth.dependencies import get_current_user
from Wallet.services import WalletService
from decimal import Decimal
from db import get_session

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.get("/balance", response_model=WalletResponse)
async def get_balance(current_user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    wallet = await wallet_service.get_wallet(current_user["id"])
    return wallet

@router.post("/credit", response_model=TransactionResponse)
async def credit_wallet(data: AmountRequest, current_user: dict=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    transaction = await wallet_service.credit(current_user["id"], data.amount)
    return transaction

@router.post("/debit", response_model=TransactionResponse)
async def debit_wallet(data: AmountRequest, current_user: dict=Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    transaction = await wallet_service.debit(current_user["id"], data.amount)
    return transaction

@router.get("/transactions", response_model=list[TransactionResponse])
async def get_transactions(current_user: dict = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    transactions = await wallet_service.get_transactions(current_user["id"])
    return transactions