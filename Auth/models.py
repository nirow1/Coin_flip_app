from sqlalchemy import Column, Integer, String, Date, DateTime
from sqlalchemy.sql import func
from db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    country = Column(String, nullable=False)
    dob = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
