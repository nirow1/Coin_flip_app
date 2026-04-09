from fastapi import APIRouter

router = APIRouter()

@router.get("/notification")
async def get_all_notifications():
    ...

@router.put("/notification/{notification_id}/read")
async def update_notification_read(notification_id: int):
    ...

@router.put("/notification/read_all")
async def update_notification_read_all():
    ...

@router.get("/notification/unread_count")
async def update_notification_unread_count():
    ...

