from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Optional


class GameResponse(BaseModel):
    id: int
    status: str
    start_date: datetime
    flip_time: datetime
    prize_pool: Decimal
    current_player_count: int
    initial_player_count: Optional[int]

    model_config = {"from_attributes": True}


class GamePlayerResponse(BaseModel):
    id: int
    game_id: int
    user_id: int
    side: Optional[str]
    cashout_decision: Optional[str]
    round_number: int
    is_eliminated: bool

    model_config = {"from_attributes": True}

