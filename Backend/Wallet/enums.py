import enum


class TransactionType(str, enum.Enum):
    CREDIT = "credit"
    DEBIT = "debit"
    WIN = "win"
    PURCHASE = "purchase"
    REFUND = "refund"
    WITHDRAWAL = "withdrawal"


class QuoteKind(str, enum.Enum):
    BUY = "buy"
    WITHDRAW = "withdraw"



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
