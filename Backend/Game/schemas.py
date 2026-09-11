from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class GameResponse(BaseModel):
    id: int
    status: str
    start_date: datetime
    flip_time: datetime
    prize_pool: Decimal
    current_player_count: int
    initial_player_count: int | None

    model_config = {"from_attributes": True}

class MyGameItemResponse(BaseModel):
    id: int
    status: str
    start_date: datetime
    flip_time: datetime
    prize_pool: Decimal
    current_player_count: int
    initial_player_count: int | None
    side: str | None
    cashout_decision: str | None
    round_number: int
    is_eliminated: bool
    outcome: str  # live | won | eliminated | ended
    heads: float | None = None  # only when outcome == live
    tails: float | None = None

    model_config = {"from_attributes": True}


class GamePlayerResponse(BaseModel):
    id: int
    game_id: int
    user_id: int
    side: str | None
    cashout_decision: str | None
    round_number: int
    is_eliminated: bool

    model_config = {"from_attributes": True}

