from sqlalchemy import Column, Integer, String, DateTime, Numeric, Boolean, func, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from db import Base


class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True)
    status = Column(String, nullable=False, default="open")
    start_date = Column(DateTime(timezone=True), nullable=False)
    flip_time = Column(DateTime(timezone=True), nullable=False)

    initial_player_count = Column(Integer, nullable=True)
    current_player_count = Column(Integer, nullable=True, default=0)

    prize_pool = Column(Numeric(10, 2), nullable=False, default=0)
    showdown_active = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    players = relationship("GamePlayer", back_populates="game", cascade="all, delete-orphan")
    flips = relationship("Flip", back_populates="game", cascade="all, delete-orphan")


class GamePlayer(Base):
    __tablename__ = "game_players"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))

    choice = Column(String, nullable=True)  # "heads" or "tails"
    round_number = Column(Integer, nullable=False, default=1)

    is_eliminated = Column(Boolean, default=False)
    eliminated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("game_id", "user_id", name="uq_game_player"),
    )

    # Relationships
    game = relationship("Game", back_populates="players")
    user = relationship("User")

class Flip(Base):
    __tablename__ = "flips"

    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="CASCADE"))

    round_number = Column(Integer, nullable=False)
    result = Column(String, nullable=False)  # "heads" or "tails"

    executed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    game = relationship("Game", back_populates="flips")

