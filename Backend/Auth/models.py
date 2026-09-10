from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from Backend.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    discriminator = Column(String(4), nullable=True)
    password_hash = Column(String, nullable=False)
    country = Column(String, nullable=False)

    dob = Column(Date, nullable=False)
    estimated_age = Column(Float, nullable=True)
    age_review_required = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    age_review_reasons = Column(JSON, nullable=False, default=list, server_default=text("'[]'"))
    kyc_status = Column(String(16), nullable=False, default="none", server_default="none")
    age_check_consent_at = Column(DateTime(timezone=True), nullable=True)

    is_email_verified = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    email_verification_token_hash = Column(String, nullable=True, index=True)
    email_verification_expires_at = Column(DateTime(timezone=True), nullable=True)
    email_verification_sent_at = Column(DateTime(timezone=True), nullable=True)

    is_admin = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    fcm_token = Column(String(500), nullable=True)

    # The corresponding Wallet model is expected to define
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    solana_wallet = relationship("UserSolanaWallet", back_populates="user", uselist=False)
    notifications = relationship("Notification", back_populates="user", uselist=True)
    friends = relationship("Friend", back_populates="user", uselist=True, foreign_keys="Friend.user_id")
    leaderboard = relationship("Leaderboard", back_populates="user", uselist=False)
