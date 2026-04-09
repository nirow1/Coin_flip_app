from sqlalchemy import Column, Integer, String, Date, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    country = Column(String, nullable=False)
    dob = Column(Date, nullable=False)
    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    fcm_token = Column(String(500), nullable=True)

    # The corresponding Wallet model is expected to define
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    solana_wallet = relationship("UserSolanaWallet", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user", uselist=True)
