from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.Auth.dependencies import get_current_admin, get_current_user
from Backend.Auth.models import User
from Backend.config import settings
from Backend.Core.core_redis import get_redis
from Backend.db import get_session
from Backend.Wallet.enums import Chain
from Backend.Wallet.schemas import (
    QUOTE_RATE_LIMIT,
    QUOTE_RATE_WINDOW_SEC,
    BalanceResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    CreditsQuoteRequest,
    CreditsQuoteResponse,
    NeedsReviewResponse,
    OrderStatusResponse,
    ResolveNeedsReviewRequest,
    ResolveUnmatchedRequest,
    SolanaWebhookPayload,
    TransactionResponse,
    UnmatchedDepositResponse,
    WithdrawQuoteRequest,
    WithdrawQuoteResponse,
    WithdrawRequest,
    WithdrawResponse,
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


async def require_withdrawals_enabled() -> None:
    """503 while WITHDRAWALS_ENABLED is False (built but dark)."""
    if not settings.WITHDRAWALS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Withdrawals temporarily unavailable",
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
        redis=redis,
    )
    p = quote.payload
    amount_sol = str(Decimal(p["lamports"]) / Decimal("1000000000"))
    return CreditsQuoteResponse(
        quote_id=quote.id,
        expires_at=quote.expires_at,
        credits=int(p["credits"]),
        amount_sol=amount_sol,
        lamports=int(p["lamports"]),
        fee=str(p["fee"]),
        price=str(p["price"]),
        price_source=str(p["price_source"]),
        cluster=settings.SOLANA_CLUSTER,
    )


@router.post("/credits/orders", response_model=CreateOrderResponse)
async def create_credit_order(
    body: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_solana_payments),
):
    wallet_service = WalletService(session)
    order = await wallet_service.create_credit_order(
        user_id=current_user.id,
        quote_id=str(body.quote_id),
    )
    fields = wallet_service._order_payment_fields(order)
    return CreateOrderResponse(
        order_id=order.id,
        receive_address=order.receive_address,
        amount_sol=fields["amount_sol"],
        reference=order.reference_pubkey,
        memo=order.order_ref,
        expires_at=order.expires_at,
        solana_pay_url=fields["solana_pay_url"],
    )


@router.get("/credits/orders/{order_id}", response_model=OrderStatusResponse)
async def get_credit_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_solana_payments),
) -> OrderStatusResponse:
    wallet_service = WalletService(session)
    order = await wallet_service.get_credit_order_for_owner(
        order_id=order_id,
        user_id=current_user.id,
    )
    return OrderStatusResponse(
        order_id=order.id,
        status=order.status.value,
        credits=order.credits,
        expires_at=order.expires_at,
        paid_tx_hash=order.paid_tx_hash,
    )


@router.post("/credits/withdraw/quote", response_model=WithdrawQuoteResponse)
async def create_withdraw_quote(
    body: WithdrawQuoteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    _: None = Depends(require_solana_payments),
    __: None = Depends(require_withdrawals_enabled),
):
    await _enforce_quote_rate_limit(redis, current_user.id)
    wallet_service = WalletService(session)
    quote = await wallet_service.create_withdraw_quote(
        user_id=current_user.id,
        credits=body.credits,
        asset=body.asset,
        destination=body.destination,
        chain=body.chain,
        redis=redis,
    )
    p = quote.payload
    return WithdrawQuoteResponse(
        quote_id=quote.id,
        expires_at=quote.expires_at,
        asset=p["asset"],
        destination=p["destination"],
        credits=p["credits"],
        fee_credits=p["fee_credits"],
        net_credits=p["net_credits"],
        net_atomic=int(p["net_atomic"]),
        ata_rent_lamports=int(p.get("ata_rent_lamports") or 0),
    )


@router.post("/credits/withdraw", response_model=WithdrawResponse)
async def create_withdrawal(
    body: WithdrawRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_solana_payments),
    __: None = Depends(require_withdrawals_enabled),
):
    wallet_service = WalletService(session)
    withdrawal = await wallet_service.create_withdrawal(
        user_id=current_user.id,
        quote_id=str(body.quote_id),
        idempotency_key=body.idempotency_key,
        password=body.password,
        password_hash=current_user.password_hash,
    )
    return WithdrawResponse(
        withdrawal_id=withdrawal.id,
        status=withdrawal.status.value,
        credits_debited=withdrawal.credits_debited,
        net_atomic=withdrawal.net_atomic_amount,
        asset=withdrawal.asset.value,
        destination=withdrawal.destination,
    )


@router.get(
    "/admin/needs-review",
    response_model=list[NeedsReviewResponse],
)
async def list_needs_review_orders(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    wallet_service = WalletService(session)
    orders = await wallet_service.list_needs_review_orders()
    return orders

@router.get(
    "/admin/unmatched-deposits",
    response_model=list[UnmatchedDepositResponse],
)
async def list_unmatched_deposits(
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    wallet_service = WalletService(session)
    deposits = await wallet_service.list_open_unmatched_deposits()
    return deposits
    
@router.post(
    "/admin/needs-review/orders/{order_id}/resolve",
    response_model=NeedsReviewResponse,
)
async def resolve_needs_review_order(
    order_id: int,
    body: ResolveNeedsReviewRequest,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    wallet_service = WalletService(session)
    order = await wallet_service.resolve_needs_review_order(
        order_id=order_id,
        admin=current_admin.id,
        action=body.action,
        credits=body.credits)
    return order

@router.post(
    "/admin/unmatched-deposits/{deposit_id}/resolve",
    response_model=UnmatchedDepositResponse,
)
async def resolve_unmatched_deposit(
    deposit_id: int,
    body: ResolveUnmatchedRequest,
    current_admin: User = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    wallet_service = WalletService(session)
    deposit = await wallet_service.resolve_unmatched_deposit(
        deposit_id=deposit_id,
        admin=current_admin.id,
        action=body.action,
        user_id=body.user_id,
        credits=body.credits,
        resolved_order_id=body.resolved_order_id,
        )
    return deposit