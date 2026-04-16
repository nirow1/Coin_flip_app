from decimal import Decimal

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from Auth.models import User
from Leader_board.model import Leaderboard
from Social.service import FriendService


class LeaderBoardService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.friend_service = FriendService(session)

    async def get_streak_leaderboard(
        self,
        user_id: int,
        friends_only: bool,
        limit: int = 50,
    ) -> list:
        stmt = (
            select(
                User.id.label("user_id"),
                User.username,
                Leaderboard.longest_streak,
            )
            .join(User, User.id == Leaderboard.user_id)
            .order_by(desc(Leaderboard.longest_streak))
            .limit(limit)
        )

        if friends_only:
            friends = await self.friend_service.get_friends(user_id)
            friend_ids = {
                f.user_id if f.user_id != user_id else f.friend_id
                for f in friends
            }
            if not friend_ids:
                return []
            stmt = stmt.where(Leaderboard.user_id.in_(friend_ids))

        result = await self.session.execute(stmt)
        return list(result.mappings().all())

    async def get_total_earnings_leaderboard(self,
                                             user_id: int,
                                             friends_only: bool,
                                             limit: int = 50,
                                             ) -> list:



        # 2. Build aggregation query
        stmt = (
            select(
                User.id.label("user_id"),
                User.username,
                Leaderboard.total_earnings,
            )
            .join(User, User.id == Leaderboard.user_id)
            .order_by(desc(Leaderboard.total_earnings))
            .limit(limit)
        )

        # 3. Apply friends filter
        if friends_only:
            friends = await self.friend_service.get_friends(user_id)
            friend_ids = {
                f.user_id if f.user_id != user_id else f.friend_id
                for f in friends
            }
            if not friend_ids:
                return []
            stmt = stmt.where(Leaderboard.user_id.in_(friend_ids))

        # 4. Execute
        result = await self.session.execute(stmt)
        return list(result.mappings().all())

    async def increment_earnings(self, user_id: int, amount: Decimal) -> None:
        leaderboard_entry = await self._get_leaderboard(user_id)

        if leaderboard_entry is None:
            leaderboard_entry = await self._create_leaderboard(user_id)

        leaderboard_entry.total_earnings += amount
        await self.session.flush()

    async def update_streak(self, user_id: int, new_streak: int) -> None:
        leaderboard_entry = await self._get_leaderboard(user_id)

        if leaderboard_entry is None:
            leaderboard_entry = await self._create_leaderboard(user_id)

        if leaderboard_entry.longest_streak < new_streak:
            leaderboard_entry.longest_streak = new_streak
        await self.session.flush()

    async def _get_leaderboard(self, user_id: int) -> Leaderboard | None:
        leaderboard_entry = await self.session.execute(
            select(Leaderboard).where(Leaderboard.user_id == user_id)
        )
        return leaderboard_entry.scalar_one_or_none()

    async def _create_leaderboard(self, user_id: int) -> Leaderboard:
        new_entry = Leaderboard(
            user_id=user_id,
            total_earnings=0,
            longest_streak=0,
        )
        self.session.add(new_entry)
        await self.session.flush()
        return new_entry
