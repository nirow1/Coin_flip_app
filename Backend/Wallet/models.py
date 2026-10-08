import uuid

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    LargeBinary,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import relationship

from Backend.db import Base
from Backend.Wallet.enums import (
    Chain,
    CreditOrderStatus,
    TransactionType,
    UnmatchedDepositStatus,
)


class Wallet(Base):
    __tablename__ = "wallets"

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


class UserSolanaWallet(Base):
    __tablename__ = "user_solana_wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    public_key = Column(String, nullable=False)
    private_key_encrypted = Column(LargeBinary, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="solana_wallet")


class PaymentQuote(Base):
    """Server-stored quote; clients must pass quote_id only on order/withdraw."""

    __tablename__ = "payment_quotes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CreditOrder(Base):
    __tablename__ = "credit_orders"

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
    quote_id = Column(
        String(36),
        ForeignKey("payment_quotes.id"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UnmatchedDeposit(Base):
    __tablename__ = "unmatched_deposits"

    id = Column(Integer, primary_key=True, index=True)
    tx_hash = Column(String, nullable=False, unique=True)
    lamports = Column(BigInteger, nullable=False)
    raw_memo = Column(String, nullable=True)
    status = Column(
        Enum(UnmatchedDepositStatus),
        nullable=False,
        default=UnmatchedDepositStatus.OPEN,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
