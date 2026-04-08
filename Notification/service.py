from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def send_in_app_notification(self, user_id: int, title: str, message: str, type):
        ...

    async def send_push_notification(self, user_id: int, title: str, message: str, data):
        ...

    async def send_email_notification(self, user_id: int, subject: str, body: str):
        ...

    async def notify_flip_result(self, user_id: int, survived: bool, round_number: int):
        ...

    async def notify_elimination(self, user_id: int, round_number: int):
        ...

    async def notify_showdown_activated(self, user_id: int, game_id: int):
        ...

    async def notify_game_ended(self, user_id: int, prize_amount: Decimal):
        ...

    async def notify_prize_paid(self, user_id: int, amount: Decimal):
        ...

    async def notify_friend_invite(self, user_id: int, from_username: str, game_id: int):
        ...

    async def notify_new_game_available(self, user_id: int, game_id: int):
        ...

    async def notify_credit_purchase_confirmed(self, user_id: int, amount: Decimal, method: str):
        ...
