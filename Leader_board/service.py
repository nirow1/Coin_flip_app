from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from Auth.models import User
from Leader_board.model import Leaderboard
from Social.service import FriendService


class LeaderBoardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.friend_service = FriendService(session)

    async def get_streak_leaderboard(self, user_id: int, friends_only: bool, limit: int = 50) -> list:
        return await self._leaderboard_query(Leaderboard.longest_streak, user_id, friends_only, limit)

    async def get_friends_streak_leaderboard(self, user_id: int, limit: int = 50) -> list:
        return await self._leaderboard_query(Leaderboard.longest_streak, user_id, friends_only=True, limit=limit)

    async def _leaderboard_query(
        self,
        metric_column,
        user_id: int,
        friends_only: bool,
        limit: int = 50,
    ) -> list:
        friend_ids = None
        if friends_only:
            friends = await self.friend_service.get_friends(user_id)
            friend_ids = {
                f.user_id if f.user_id != user_id else f.friend_id
                for f in friends
            }
            if not friend_ids:
                return []

        stmt = (
            select(
                User.id.label("user_id"),
                User.username,
                metric_column,
            )
            .join(User, User.id == Leaderboard.user_id)
            .order_by(desc(metric_column))
            .limit(limit)
        )

        if friends_only:
            stmt = stmt.where(Leaderboard.user_id.in_(friend_ids))

        result = await self.session.execute(stmt)
        return list(result.mappings().all())
