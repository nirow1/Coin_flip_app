from decimal import Decimal
from pydantic import BaseModel


class EarningsResponse(BaseModel):
    user_id: int
    username: str | None
    total_earnings: Decimal

    model_config = {"from_attributes": True}


class StreakResponse(BaseModel):
    user_id: int
    username: str | None
    longest_streak: int

    model_config = {"from_attributes": True}
