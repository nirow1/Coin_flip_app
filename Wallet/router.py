from Wallet.schemas import WalletResponse, TransactionResponse, AmountRequest, SolanaWebhookPayload
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from Auth.dependencies import get_current_user
from Wallet.models import UserSolanaWallet
from Wallet.services import WalletService
from Auth.models import User
from db import get_session
from config import settings
import hmac
import hashlib

router = APIRouter(prefix="/wallet", tags=["wallet"])

@router.get("/balance", response_model=WalletResponse)
async def get_balance(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    wallet = await wallet_service.get_wallet(current_user.id)
    return wallet

@router.post("/credit", response_model=TransactionResponse)
async def credit_wallet(data: AmountRequest, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    transaction = await wallet_service.credit(current_user.id, data.amount)
    return transaction

@router.post("/debit", response_model=TransactionResponse)
async def debit_wallet(data: AmountRequest, current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    transaction = await wallet_service.debit(current_user.id, data.amount)
    return transaction

@router.get("/transactions", response_model=list[TransactionResponse])
async def get_transactions(current_user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    transactions = await wallet_service.get_transactions(current_user.id)
    return transactions

#todo: read this and find out what it did
@router.post("/webhook/solana", status_code=status.HTTP_200_OK)
async def solana_webhook(
    payload: SolanaWebhookPayload,
    request: Request,
    session: AsyncSession = Depends(get_session)
):
    # 1. Verify HMAC signature from webhook provider (e.g. Helius, QuickNode)
    signature = request.headers.get("x-webhook-signature", "")
    raw_body = await request.body()
    expected = hmac.new(
        settings.SOLANA_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    # 2. Look up user by destination Solana address
    result = await session.execute(
        select(UserSolanaWallet).where(UserSolanaWallet.public_key == payload.destination_address)
    )
    solana_wallet = result.scalar_one_or_none()
    if solana_wallet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solana address not linked to any user")

    # 3. Credit user — deposit_sol handles tx_hash deduplication internally
    wallet_service = WalletService(session)
    await wallet_service.deposit_sol(
        user_id=solana_wallet.user_id,
        amount_sol=payload.amount_sol,
        tx_hash=payload.tx_hash
    )

    return {"message": "Deposit processed"}
