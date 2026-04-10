from decimal import Decimal
import asyncio
import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest
from sqlalchemy import select, update
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings
from Auth.models import User
from Notification.models import Notification
from Notification.enums import NotificationType

_FCM_ENDPOINT = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
_FCM_SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]


async def _get_fcm_access_token() -> str:
    """
    Fetches a short-lived OAuth2 access token for the FCM v1 API.
    Token refresh uses google-auth (sync) – run in executor to avoid blocking.
    """
    creds = service_account.Credentials.from_service_account_file(
        settings.FIREBASE_SERVICE_ACCOUNT_PATH,
        scopes=_FCM_SCOPES,
    )
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, creds.refresh, GoogleAuthRequest())
    return creds.token


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # Send functions
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
    
    async def mark_all_read(self, user_id: int) -> bool:
        try:
            await self.session.execute(
                update(Notification)
                .where(Notification.user_id == user_id, Notification.is_read == False)
                .values(is_read=True, read_at=func.now())
            )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            return False
        return True

    async def send_push_notification(self, user_id: int, title: str, message: str, data: dict) -> str | None:
        result = await self.session.execute(
            select(User.fcm_token).where(User.id == user_id)
        )
        fcm_token = result.scalar_one_or_none()

        if not fcm_token:
            return None

        access_token = await _get_fcm_access_token()

        url = _FCM_ENDPOINT.format(project_id=settings.FIREBASE_PROJECT_ID)
        payload = {
            "message": {
                "token": fcm_token,
                "notification": {
                    "title": title,
                    "body": message,
                },
                # FCM v1 data values must all be strings
                "data": {k: str(v) for k, v in (data or {}).items()},
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                # FCM v1 returns the message name as "projects/{id}/messages/{msg_id}"
                return response.json()["name"]
            except httpx.HTTPStatusError:
                return None

    async def notify(self, user_id: int, title: str, message: str, n_type: NotificationType, push=True):
        await self.send_in_app_notification(user_id, title, message, n_type)

        if push:
            await self.send_push_notification(user_id, title, message, data={"type": n_type})

    # Later to be implemented
    async def send_email_notification(self, user_id: int, subject: str, body: str) -> None:
        ...

    async def get_all_unread_notifications(self, user_id: int) -> list[Notification]:
        result = await self.session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .where(Notification.is_read == False)
            .order_by(Notification.created_at.desc())
        )
        notifications = result.scalars().all()
        return list(notifications)

    # Trigger functions
    async def notify_flip_result(self, user_id: int, survived: bool, round_number: int) -> None:
        if survived:
            title = "Round survived"
            message = f"You survived round {round_number}"
        else:
            title = "Eliminated"
            message = f"You were eliminated in round {round_number}"

        await self.notify(user_id, title, message, NotificationType.flip_result)

    async def notify_side_assigned(self, user_id: int, assigned_side: str, game_id: int) -> None:
        title = "Side assigned"
        message = f"You were assigned to the {assigned_side} side in game {game_id}"
        await self.notify(user_id, title, message, NotificationType.side_assigned)

    async def notify_showdown_activated(self, user_id: int, game_id: int) -> None:
        title = "Showdown activated"
        message = f"The showdown has been activated in game {game_id}"
        await self.notify(user_id, title, message, NotificationType.showdown_activated)

    async def notify_game_started(self, user_id: int, game_id: int) -> None:
        title = "Game started"
        message = f"Your game {game_id} has started!"
        await self.notify(user_id, title, message, NotificationType.game_started)

    async def notify_game_ended(self, user_id: int, prize_amount: Decimal) -> None:
        title = "Game won!"
        message = f"Your game has ended. You won {prize_amount} credits!"
        await self.notify(user_id, title, message, NotificationType.game_won)

    async def notify_prize_paid(self, user_id: int, amount: Decimal) -> None:
        title = "Prize paid"
        message = f"Your prize of {amount} credits has been paid out!"
        await self.notify(user_id, title, message, NotificationType.prize_paid)

    async def notify_friend_invite(self, user_id: int, from_username: str, game_id: int) -> None:
        title = "Friend invite"
        message = f"You were invited by {from_username} to become friends!"
        await self.notify(user_id, title, message, NotificationType.friend_invite)

    async def notify_new_game_available(self, user_id: int, game_id: int) -> None:
        title = "New game available"
        message = f"A new game with ID {game_id} is now available to join! Join now and win a prize!"
        await self.notify(user_id, title, message, NotificationType.new_game_available)

    async def notify_credit_purchase_confirmed(self, user_id: int, amount: Decimal, method: str) -> None:
        title = "Credit purchase confirmed"
        message = f"Your purchase of {amount} credits using {method} has been confirmed!"
        await self.notify(user_id, title, message, NotificationType.credit_purchase_confirmed)

    async def notify_wallet_deposit(self, user_id: int, amount: Decimal) -> None:
        title = "Wallet deposit"
        message = f"Your wallet has been credited with {amount} credits!"
        await self.notify(user_id, title, message, NotificationType.wallet_deposit)

    async def notify_wallet_withdrawal(self, user_id: int, amount: Decimal) -> None:
        title = "Wallet withdrawal"
        message = f"Your wallet has been debited by {amount} credits!"
        await self.notify(user_id, title, message, NotificationType.wallet_withdrawal)

