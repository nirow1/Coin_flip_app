from datetime import datetime
from pydantic import BaseModel
from Notification.enums import NotificationType


class NotificationOut(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    type: NotificationType
    is_read: bool
    created_at: datetime
    read_at: datetime | None = None

    model_config = {"from_attributes": True}


class UnreadCountOut(BaseModel):
    unread_count: int

