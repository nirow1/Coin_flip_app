from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from Auth.dependencies import get_current_user
from Auth.models import User
from Social.service import FriendService
from db import get_session

router = APIRouter(prefix="/friends", tags=["friends"])


@router.post("/request/{friend_id}", status_code=status.HTTP_201_CREATED)
async def send_friend_request(friend_id: int,
                              user: User = Depends(get_current_user),
                              session: AsyncSession = Depends(get_session)):
    friend_service = FriendService(session)
    success = await friend_service.send_friend_request(user.id, friend_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Friend request could not be sent")
    return {"invitations_sent": success}


@router.put("/accept/{friend_id}")
async def accept_friend_request(friend_id: int,
                                user: User = Depends(get_current_user),
                                session: AsyncSession = Depends(get_session)):
    ...


@router.put("/decline/{friend_id}")
async def decline_friend_request(friend_if: int,
                                          user: User = Depends(get_current_user),
                                          session: AsyncSession = Depends(get_session)):
    ...


@router.delete("/remove/{friend_id}")
async def remove_friend(friend_id: int,
                        user: User = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)):
    ...


@router.get("/friends")
async def get_friends(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    ...


@router.get("/pending")
async def get_pending_requests(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    ...


@router.get("/search?query=")
async def search_users(query: str,
                       user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    ...


@router.get("/game/{game_id}/status")
async def get_friends_game_status(game_id: int,
                                  user: User = Depends(get_current_user),
                                  session: AsyncSession = Depends(get_session)):
    ...


@router.post("/friends/invite/{friend_id}/")
async def invite_friend_to_game(friend_id: int,
                                user: User = Depends(get_current_user),
                                session: AsyncSession = Depends(get_session)):
    ...
