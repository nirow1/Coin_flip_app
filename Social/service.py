from sqlalchemy import select, or_, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from Auth.models import User
from Game.models import GamePlayer
from Game.service import GameService
from Notification.service import NotificationService
from Social.models import Friend
from Social.enums import FriendStatus
from Wallet.services import WalletService


class FriendService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def send_friend_request(self, user_id: int, friend_id: int) -> bool:
        if user_id == friend_id:
            return False  # Cannot send request to self

        # Check if a relationship already exists in either direction
        exists = await self.session.execute(
            select(Friend).where(
                or_(
                    (Friend.user_id == user_id) & (Friend.friend_id == friend_id),
                    (Friend.user_id == friend_id) & (Friend.friend_id == user_id),
                )
            )
        )
        if exists.scalar_one_or_none() is not None:
            return False

        friend_request = Friend(
            user_id=user_id,
            friend_id=friend_id,
            status=FriendStatus.PENDING,
        )
        self.session.add(friend_request)
        await self.session.commit()
        return True

    async def accept_friend_request(self, user_id: int, friend_id: int) -> bool:
        try:
            result = await self.session.execute(
                update(Friend)
                .where(Friend.user_id == friend_id)
                .where(Friend.friend_id == user_id)
                .where(Friend.status == FriendStatus.PENDING)
                .values(status=FriendStatus.ACCEPTED)
                .returning(Friend.id)
            )
            await self.session.commit()
            return result.fetchone() is not None
        except Exception:
            await self.session.rollback()
            return False

    async def decline_friend_request(self, user_id: int, friend_id: int) -> bool:
        # Delete the pending request sent by friend_id to user_id
        try:
            result = await self.session.execute(
                delete(Friend)
                .where(Friend.user_id == friend_id)
                .where(Friend.friend_id == user_id)
                .where(Friend.status == FriendStatus.PENDING)
                .returning(Friend.id)
            )
            await self.session.commit()
            return result.fetchone() is not None
        except Exception:
            await self.session.rollback()
            return False

    async def remove_friend(self, user_id: int, friend_id: int) -> bool:
        # Delete the accepted friendship record in either direction
        try:
            result = await self.session.execute(
                delete(Friend)
                .where(
                    or_(
                        (Friend.user_id == user_id) & (Friend.friend_id == friend_id),
                        (Friend.user_id == friend_id) & (Friend.friend_id == user_id),
                    )
                )
                .where(Friend.status == FriendStatus.ACCEPTED)
                .returning(Friend.id)
            )
            await self.session.commit()
            return result.fetchone() is not None
        except Exception:
            await self.session.rollback()
            return False

    async def get_friends(self, user_id: int) -> list[Friend]:
        result = await self.session.execute(
            select(Friend).where(
                or_(Friend.user_id == user_id, Friend.friend_id == user_id),
                Friend.status == FriendStatus.ACCEPTED,
            )
        )
        return list(result.scalars().all())

    async def get_pending_request(self, user_id: int) -> list[Friend]:
        # Returns requests sent TO this user (they are the recipient)
        result = await self.session.execute(
            select(Friend).where(
                Friend.friend_id == user_id,
                Friend.status == FriendStatus.PENDING,
            )
        )
        return list(result.scalars().all())

    async def search_users(self, query: str, user_id: int) -> list[User]:
        pattern = f"%{query}%"

        # All user IDs who already have ANY relationship with the requester (either direction)
        related_ids = (
            select(Friend.friend_id).where(Friend.user_id == user_id)
            .union(
                select(Friend.user_id).where(Friend.friend_id == user_id)
            )
        )

        stmt = (
            select(User)
            .where(
                or_(
                    User.username.ilike(pattern),
                    User.email.ilike(pattern),
                ),
                User.id != user_id,
                User.id.not_in(related_ids),
            )
            .limit(20)
        )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_friend_game_status(self, user_id: int, game_id: int) -> str:
        result = await self.session.execute(
            select(GamePlayer.is_eliminated)
            .where(GamePlayer.game_id == game_id)
            .where(GamePlayer.user_id == user_id)
        )
        is_eliminated = result.scalar_one_or_none()

        if is_eliminated is None:
            return "not_in_game"
        return "eliminated" if is_eliminated else "active"

    async def invite_friend_to_game(self,
                                    user_id: int,
                                    friend_id: int,
                                    game_service: GameService,
                                    wallet: WalletService,
                                    notif: NotificationService) -> bool:
        # Check if friend is accepted
        friend_status = await self.session.execute(
            select(Friend).where(
                or_(
                    (Friend.user_id == user_id) & (Friend.friend_id == friend_id),
                    (Friend.user_id == friend_id) & (Friend.friend_id == user_id),
                ),
                Friend.status == FriendStatus.ACCEPTED,
            )
        )

        if friend_status.scalar_one_or_none() is None:
            raise ValueError("Can only invite accepted friends to game")

        result =  await game_service.invite_friend(user_id, friend_id, wallet)

        await notif.notify_friend_successfully_added_to_game(user_id, friend_id)

        return result