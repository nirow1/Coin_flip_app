from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.Auth.dependencies import get_current_user
from Backend.Auth.models import User
from Backend.Core.core_redis import get_redis
from Backend.db import get_session
from Backend.Wallet.enums import Chain
from Backend.Wallet.schemas import (
    BalanceResponse,
    CreditsQuoteRequest,
    CreditsQuoteResponse,
    QUOTE_RATE_LIMIT,
    QUOTE_RATE_WINDOW_SEC,
    SolanaWebhookPayload,
    TransactionResponse,
)
from Backend.Wallet.services import WalletService

router = APIRouter(prefix="/wallet", tags=["wallet"])


async def require_solana_payments(request: Request) -> None:
    """503 when Solana RPC is unreachable (startup or until recovery succeeds)."""
    if not getattr(request.app.state, "solana_payments_enabled", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Solana payments temporarily unavailable",
        )


async def _enforce_quote_rate_limit(redis: Redis, user_id: int) -> None:
    key = f"rate:wallet:quote:{user_id}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, QUOTE_RATE_WINDOW_SEC)
    if count > QUOTE_RATE_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many quote requests; try again later",
        )


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wallet_service = WalletService(session)
    wallet = await wallet_service.get_wallet(current_user.id)
    return BalanceResponse(balance=wallet.balance)


@router.get("/transactions", response_model=list[TransactionResponse])
async def get_transactions(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    wallet_service = WalletService(session)
    transactions = await wallet_service.get_transactions(current_user.id)
    return transactions


@router.post("/webhook/solana", status_code=status.HTTP_200_OK)
async def solana_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_solana_payments),
):
    """HMAC-first webhook. Custom {signature} body — not Helius format."""
    raw_body = await request.body()
    signature_header = request.headers.get("x-webhook-signature", "")
    timestamp_header = request.headers.get("x-webhook-timestamp", "")

    wallet_service = WalletService(session)
    await wallet_service.verify_solana_webhook_hmac(
        raw_body=raw_body,
        signature_header=signature_header,
        timestamp_header=timestamp_header,
    )

    try:
        payload = SolanaWebhookPayload.model_validate_json(raw_body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=exc.errors(),
        ) from exc

    await wallet_service.process_solana_webhook(tx_signature=payload.signature)
    return {"message": "ok"}


@router.post("/credits/quote", response_model=CreditsQuoteResponse)
async def create_buy_quote(
    body: CreditsQuoteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    _: None = Depends(require_solana_payments),
):
    if body.chain == Chain.POLYGON:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Polygon rail is not implemented",
        )

    await _enforce_quote_rate_limit(redis, current_user.id)

    wallet_service = WalletService(session)
    quote = await wallet_service.create_buy_quote(
        user_id=current_user.id,
        credits=body.credits,
        chain=body.chain,
    )
    return CreditsQuoteResponse(quote_id=quote.id, expires_at=quote.expires_at)
