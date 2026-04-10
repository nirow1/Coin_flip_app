from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from db import get_session
from Notification.service import NotificationService
from Notification.schemas import NotificationOut, UnreadCountOut
from Auth.models import User
from Auth.dependencies import get_current_user

router = APIRouter(prefix="/notification", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
async def get_all_notifications(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    service = NotificationService(session)
    return await service.get_all_unread_notifications(user.id)


@router.patch("/{notification_id}/read")
async def update_notification_read(
    notification_id: int,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    service = NotificationService(session)
    found = await service.mark_as_read(notification_id, user.id)
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return {"success": True}


@router.put("/read_all")
async def update_notification_read_all(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    service = NotificationService(session)
    success = await service.mark_all_read(user.id)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to mark notifications as read")
    return {"success": True}


@router.get("/unread_count", response_model=UnreadCountOut)
async def get_notification_unread_count(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    service = NotificationService(session)
    notifications = await service.get_all_unread_notifications(user.id)
    return {"unread_count": len(notifications)}
