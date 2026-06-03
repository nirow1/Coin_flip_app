from fastapi import APIRouter, Depends, Query
from Backend.Auth.dependencies import get_current_user
from Backend.Auth.models import User
from Backend.Leader_board.dependencies import get_leaderboard_service
from Backend.Leader_board.schema import EarningsResponse, StreakResponse
from Backend.Leader_board.service import LeaderBoardService

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/streak", response_model=list[StreakResponse])
async def streak_leaderboard(
    friends_only: bool = False,
    limit: int = Query(default=50, le=100),
    user: User = Depends(get_current_user),
    service: LeaderBoardService = Depends(get_leaderboard_service),
):
    return await service.get_streak_leaderboard(
        user_id=user.id,
        friends_only=friends_only,
        limit=limit,
    )


@router.get("/earnings", response_model=list[EarningsResponse])
async def earnings_leaderboard(
    friends_only: bool = False,
    limit: int = Query(default=50, le=100),
    user: User = Depends(get_current_user),
    service: LeaderBoardService = Depends(get_leaderboard_service),
):
    return await service.get_total_earnings_leaderboard(
        user_id=user.id,
        friends_only=friends_only,
        limit=limit,
    )