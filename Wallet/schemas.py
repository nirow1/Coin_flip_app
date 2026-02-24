from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal

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