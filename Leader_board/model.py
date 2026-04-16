from sqlalchemy import Column, Integer, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from db import Base


class Leaderboard(Base):
    __tablename__ = "leaderboard"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    longest_streak = Column(Integer, nullable=False, default=0)
    total_earnings = Column(Numeric(10, 2), nullable=False, default=0)

    user = relationship("User", back_populates="leaderboard")
