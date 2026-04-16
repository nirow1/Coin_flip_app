from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from db import get_session
from Leader_board.service import LeaderBoardService


async def get_leaderboard_service(session: AsyncSession = Depends(get_session)) -> LeaderBoardService:
    return LeaderBoardService(session)

