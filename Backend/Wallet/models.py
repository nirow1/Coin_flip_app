import uuid

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from Backend.db import Base
from Backend.Wallet.enums import (
    Chain,
    CreditOrderStatus,
    QuoteKind,
    TransactionType,
    UnmatchedDepositStatus,
    WithdrawalStatus,
    WithdrawAsset,
)


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Numeric(12, 2), default=0, nullable=False)
    # TODO(void-game): locked_balance or rely on GamePlayer.funds_locked_until when
    # voiding showdown/finished games after cashouts.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    type = Column(Enum(TransactionType), nullable=False)
    tx_hash = Column(String, nullable=True, unique=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    wallet = relationship("Wallet", back_populates="transactions")


class PaymentQuote(Base):
    """Server-stored quote; clients must pass quote_id only on order/withdraw."""

    __tablename__ = "payment_quotes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    chain = Column(Enum(Chain), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    kind = Column(Enum(QuoteKind), nullable=False)


class CreditOrder(Base):
    __tablename__ = "credit_orders"
    __table_args__ = (
        Index("ix_credit_orders_user_id_status", "user_id", "status"),
        Index("ix_credit_orders_status_expires_at", "status", "expires_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    credits = Column(Numeric(12, 2), nullable=False)
    chain = Column(Enum(Chain), nullable=False)
    status = Column(
        Enum(CreditOrderStatus),
        nullable=False,
        default=CreditOrderStatus.PENDING,
    )
    # Solana Pay memo / order_ref — unique attribution string
    order_ref = Column(String, nullable=False, unique=True)
    reference_pubkey = Column(String, nullable=False, unique=True)
    quoted_atomic_amount = Column(BigInteger, nullable=False)
    receive_address = Column(String, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    paid_tx_hash = Column(String, nullable=True, unique=True)
    received_atomic_amount = Column(BigInteger, nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    review_reason = Column(String, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    quote_id = Column(
        String(36),
        ForeignKey("payment_quotes.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UnmatchedDeposit(Base):
    __tablename__ = "unmatched_deposits"

    id = Column(Integer, primary_key=True, index=True)
    tx_hash = Column(String, nullable=False, unique=True)
    lamports = Column(BigInteger, nullable=False)
    raw_memo = Column(String, nullable=True)
    sender = Column(String, nullable=True)
    chain = Column(Enum(Chain), nullable=False, default=Chain.SOLANA)
    reference_pubkey = Column(String, nullable=True)
    block_time = Column(DateTime(timezone=True), nullable=True)
    resolved_order_id = Column(
        Integer, ForeignKey("credit_orders.id"), nullable=True
    )
    status = Column(
        Enum(UnmatchedDepositStatus),
        nullable=False,
        default=UnmatchedDepositStatus.OPEN,
    )
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Withdrawal(Base):
    __tablename__ = "withdrawals"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "idempotency_key",
            name="uq_withdrawals_user_idempotency",
        ),
        Index("ix_withdrawals_status_created_at", "status", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    chain = Column(Enum(Chain), nullable=False)
    asset = Column(Enum(WithdrawAsset), nullable=False)
    credits_debited = Column(Numeric(12, 2), nullable=False)
    net_atomic_amount = Column(BigInteger, nullable=False)
    destination = Column(String, nullable=False)
    quote_id = Column(
        String(36),
        ForeignKey("payment_quotes.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    idempotency_key = Column(String(64), nullable=False)
    status = Column(
        Enum(WithdrawalStatus),
        nullable=False,
        default=WithdrawalStatus.QUEUED,
    )
    # Polygon reuse; unused on Solana
    nonce = Column(Integer, nullable=True)
    signature = Column(String, nullable=True, unique=True)
    attempt_hashes = Column(JSON, nullable=True)
    raw_tx = Column(LargeBinary, nullable=True)
    last_valid_block_height = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    confirmed_at = Column(DateTime(timezone=True), nullable=True)

class ChainCursor(Base):
    __tablename__ = "chain_cursors"

    chain = Column(Enum(Chain), primary_key=True)
    last_signature = Column(String, nullable=True)
    last_block = Column(BigInteger, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
