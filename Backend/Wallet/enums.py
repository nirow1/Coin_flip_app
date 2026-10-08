import enum


class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    WIN = "win"
    PURCHASE = "purchase"
    REFUND = "refund"
    DEPOSIT_SOLANA = "deposit_solana"
    WITHDRAW_SOLANA = "withdraw_solana"


class Chain(str, enum.Enum):
    SOLANA = "solana"
    POLYGON = "polygon"


class CreditOrderStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"
    NEEDS_REVIEW = "needs_review"


class UnmatchedDepositStatus(str, enum.Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    REFUNDED = "refunded"


class WithdrawAsset(str, enum.Enum):
    SOL = "sol"
    USDC = "usdc"
