from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from Backend.Wallet.enums import Chain, WithdrawAsset

MAX_BUY_CREDITS = 10000
MIN_WITHDRAW_CREDITS = Decimal("10.0")


class SolanaWebhookPayload(BaseModel):
    """Webhook body is signature-only. Amount/destination/memo come from RPC."""

    signature: str


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


class CreateOrderRequest(BaseModel):
    """Order creation accepts quote_id only — never client-supplied amounts."""

    quote_id: str


class WithdrawQuoteRequest(BaseModel):
    credits: Annotated[
        Decimal,
        Field(ge=MIN_WITHDRAW_CREDITS, max_digits=12, decimal_places=2),
    ]
    asset: WithdrawAsset
    destination: str
    chain: Chain

    @field_validator("credits")
    @classmethod
    def two_decimal_places(cls, value: Decimal) -> Decimal:
        if value.as_tuple().exponent < -2:
            raise ValueError("credits must have at most two decimal places")
        return value


class WithdrawRequest(BaseModel):
    """Withdraw accepts quote_id + idempotency_key only — never client amounts."""

    quote_id: str
    idempotency_key: str
