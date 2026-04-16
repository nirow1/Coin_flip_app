from sqlalchemy import Column, Integer, ForeignKey
from db import Base


class Leaderboard(Base):
    __tablename__ = "leaderboard"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    total_earnings = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
