from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Notification.models import Notification
from Notification.enums import NotificationType


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def send_in_app_notification(
        self,
        user_id: int,
        title: str,
        message: str,
        notification_type: NotificationType,
    ) -> dict:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notification_type,
        )

        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)

        return {
            "id": notification.id,
            "user_id": notification.user_id,
            "title": notification.title,
            "message": notification.message,
            "type": notification.type,
            "is_read": notification.is_read,
            "created_at": notification.created_at,
        }

    async def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """Marks a single notification as read and sets read_at timestamp. Returns True if found."""
        from sqlalchemy.sql import func

        result = await self.session.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            return False

        notification.is_read = True
        notification.read_at = func.now()
        await self.session.commit()
        return True

    async def send_push_notification(self, user_id: int, title: str, message: str, data: dict) -> None:
        ...

    async def send_email_notification(self, user_id: int, subject: str, body: str) -> None:
        ...

    async def notify_flip_result(self, user_id: int, survived: bool, round_number: int) -> None:
        ...

    async def notify_elimination(self, user_id: int, round_number: int) -> None:
        ...

    async def notify_side_assigned(self, user_id: int, assigned_side: str, game_id: int) -> None:
        ...

    async def notify_showdown_activated(self, user_id: int, game_id: int) -> None:
        ...

    async def notify_game_started(self, user_id: int, game_id: int) -> None:
        ...

    async def notify_game_ended(self, user_id: int, prize_amount: Decimal) -> None:
        ...

    async def notify_prize_paid(self, user_id: int, amount: Decimal) -> None:
        ...

    async def notify_friend_invite(self, user_id: int, from_username: str, game_id: int) -> None:
        ...

    async def notify_new_game_available(self, user_id: int, game_id: int) -> None:
        ...

    async def notify_credit_purchase_confirmed(self, user_id: int, amount: Decimal, method: str) -> None:
        ...

    async def notify_wallet_deposit(self, user_id: int, amount: Decimal) -> None:
        ...

    async def notify_wallet_withdrawal(self, user_id: int, amount: Decimal) -> None:
        ...

