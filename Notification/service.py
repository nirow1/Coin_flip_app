from decimal import Decimal
import asyncio
import httpx
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleAuthRequest
from sqlalchemy import select
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
            except Exception:
                pass

        # FCM v1 returns the message name as "projects/{id}/messages/{msg_id}"
        return response.json()["name"]

    async def notify(self, user_id: int, title: str, message: str, n_type: NotificationType, push=True):
        await self.send_in_app_notification(user_id, title, message, n_type)

        if push:
            await self.send_push_notification(user_id, title, message, data={"type": n_type})

    async def send_email_notification(self, user_id: int, subject: str, body: str) -> None:
        ...

    # Trigger functions
    async def notify_flip_result(self, user_id: int, survived: bool, round_number: int) -> None:
        if survived:
            title = "Round survived"
            message = f"You survived round {round_number}"
        else:
            title = "Eliminated"
            message = f"You were eliminated in round {round_number}"

        await self.notify(user_id, title, message, NotificationType.flip_result)

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

