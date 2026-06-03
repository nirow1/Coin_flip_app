import enum


class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    WIN = "win"
    PURCHASE = "purchase"
    REFUND = "refund"
    DEPOSIT_SOLANA = "deposit_solana"
    WITHDRAW_SOLANA = "withdraw_solana"

