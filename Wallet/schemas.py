from pydantic import BaseModel, Field
from typing import Annotated
from datetime import datetime
from decimal import Decimal

# ...existing code...

class SolanaWebhookPayload(BaseModel):
    tx_hash: str              # Solana transaction signature — used for deduplication
    destination_address: str  # recipient's Solana public key
    amount_sol: Decimal       # amount in SOL

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

class AmountRequest(BaseModel):
    amount: Annotated[Decimal, Field(gt=0)]
