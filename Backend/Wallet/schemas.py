from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator
from solders.pubkey import Pubkey
from solders.signature import Signature

from Backend.config import settings
from Backend.Wallet.enums import Chain, WithdrawAsset

MAX_BUY_CREDITS = 10000
MIN_WITHDRAW_CREDITS = Decimal("10.0")
MAX_WITHDRAW_CREDITS = Decimal("10000.00")
MAX_PENDING_CREDIT_ORDERS = 3
WEBHOOK_MAX_SKEW_SECONDS = 300
QUOTE_RATE_LIMIT = 10
QUOTE_RATE_WINDOW_SEC = 60


class SolanaWebhookPayload(BaseModel):
    """Webhook body is signature-only. Amount/destination/memo come from RPC.

    Custom HMAC notifier contract — not Helius's transaction-array payload.
    """

    signature: str

    @field_validator("signature")
    @classmethod
    def validate_solana_signature(cls, value: str) -> str:
        try:
            return str(Signature.from_string(value))
        except Exception as exc:
            raise ValueError("signature must be a valid Solana transaction signature") from exc


class BalanceResponse(BaseModel):
    balance: Decimal


class WalletResponse(BaseModel):
    id: int
    balance: Decimal
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    id: int
    amount: Decimal
    type: str
    timestamp: datetime

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int


class CreditsQuoteRequest(BaseModel):
    credits: int = Field(ge=1, le=MAX_BUY_CREDITS)
    chain: Chain


class CreditsQuoteResponse(BaseModel):
    quote_id: str
    expires_at: datetime


class CreateOrderRequest(BaseModel):
    """Order creation accepts quote_id only — never client-supplied amounts."""

    quote_id: UUID


class WithdrawQuoteRequest(BaseModel):
    credits: Annotated[
        Decimal,
        Field(
            ge=MIN_WITHDRAW_CREDITS,
            le=MAX_WITHDRAW_CREDITS,
            max_digits=12,
            decimal_places=2,
        ),
    ]
    asset: WithdrawAsset
    destination: str
    chain: Chain

    @field_validator("destination")
    @classmethod
    def validate_destination(cls, value: str) -> str:
        try:
            dest = str(Pubkey.from_string(value))
        except Exception as exc:
            raise ValueError("destination must be a valid Solana public key") from exc

        house = {
            settings.SOLANA_HOT_WALLET_ADDRESS,
            settings.SOLANA_COLD_RECEIVE_ADDRESS,
        }
        if dest in house:
            raise ValueError("destination must not be a house address")
        return dest


class WithdrawRequest(BaseModel):
    """Withdraw accepts quote_id + idempotency_key only — never client amounts."""

    quote_id: UUID
    idempotency_key: str = Field(min_length=16, max_length=64)


class CreateOrderResponse(BaseModel):
    order_id: int
    receive_address: str
    amount_sol: str
    reference: str
    memo: str
    expires_at: datetime
    solana_pay_url: str


class OrderStatusResponse(BaseModel):
    order_id: int
    status: str
    credits: Decimal
    expires_at: datetime
    paid_tx_hash: str | None = None


class NeedsReviewResponse(BaseModel):
    id: int
    user_id: int
    credits: Decimal
    status: str
    review_reason: str | None = None
    quoted_atomic_amount: int
    received_atomic_amount: int | None = None
    paid_tx_hash: str | None = None
    expires_at: datetime
    paid_at: datetime | None = None
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class UnmatchedDepositResponse(BaseModel):
    id: int
    tx_hash: str
    lamports: int
    raw_memo: str | None = None
    sender: str | None = None
    chain: Chain
    reference_pubkey: str | None = None
    block_time: datetime | None = None
    status: str
    resolved_order_id: int | None = None
    resolved_by: int | None = None
    resolved_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminResolveAction(str, Enum):
    CREDIT = "credit"
    MARK_REFUNDED = "mark_refunded"
    

class ResolveNeedsReviewRequest(BaseModel):
    """Credit uses order.user_id + order.credits (optional credits override for underpay)."""

    action: AdminResolveAction
    credits: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)


class ResolveUnmatchedRequest(BaseModel):
    """Credit requires user_id + credits; mark_refunded needs neither."""
    action: AdminResolveAction
    user_id: int
    credits: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    resolved_order_id: int | None = None

    @model_validator(mode="after")
    def credit_requires__user_and_amount(self) -> "ResolveUnmatchedRequest":
        if self.action == AdminResolveAction.CREDIT:
            if self.user_id is None:
                raise ValueError("user_id is required for credit action")
            if self.credits is None:
                raise ValueError("credits is required for credit action")
        return self

