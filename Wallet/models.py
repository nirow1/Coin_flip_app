from sqlalchemy import Column, Integer, ForeignKey, Numeric, DateTime, func, String
from sqlalchemy.orm import relationship
from db import Base

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    balance = Column(Numeric(12, 2), default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    wallet_id = Column(Integer, ForeignKey("wallets.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    #todo: The 'type' column lacks constraints to enforce valid transaction types. Consider using an Enum or adding a check constraint to ensure only valid values ('credit', 'debit', 'win', 'purchase', 'refund') can be stored in the database.
    type = Column(String, nullable=False)  # "credit", "debit", "win", "purchase", "refund"
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    wallet = relationship("Wallet", back_populates="transactions")
