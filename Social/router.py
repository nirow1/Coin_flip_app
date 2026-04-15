from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from Auth.dependencies import get_current_user
from Auth.models import User
from Game.service import GameService
from Notification.service import NotificationService
from Social.schemas import FriendResponse, UserSearchResponse
from Social.service import FriendService
from Wallet.services import WalletService
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


@router.patch("/accept/{friend_id}")
async def accept_friend_request(friend_id: int,
                                user: User = Depends(get_current_user),
                                session: AsyncSession = Depends(get_session)):
    friend_service = FriendService(session)
    success = await friend_service.accept_friend_request(user.id, friend_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Friend request could not be accepted")
    return {"request_accepted": success}


@router.patch("/decline/{friend_id}")
async def decline_friend_request(friend_id: int,
                                 user: User = Depends(get_current_user),
                                 session: AsyncSession = Depends(get_session)):
    friend_service = FriendService(session)
    success = await friend_service.decline_friend_request(user.id, friend_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Friend request could not be declined")
    return {"request_declined": success}


@router.delete("/remove/{friend_id}")
async def remove_friend(friend_id: int,
                        user: User = Depends(get_current_user),
                        session: AsyncSession = Depends(get_session)):
    friend_service = FriendService(session)
    request = await friend_service.remove_friend(user.id, friend_id)
    if not request:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Friend could not be removed")
    return {"friend_removed": request}


@router.get("")
async def get_friends(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> list[FriendResponse]:
    friend_service = FriendService(session)
    friends = await friend_service.get_friends(user.id)
    return [FriendResponse.model_validate(f) for f in friends ]



@router.get("/pending")
async def get_pending_requests(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)) -> list[FriendResponse]:
    friend_service = FriendService(session)
    pending_requests = await friend_service.get_pending_request(user.id)
    return [FriendResponse.model_validate(r) for r in pending_requests]


@router.get("/search", response_model=list[UserSearchResponse])
async def search_users(query: str,
                       user: User = Depends(get_current_user),
                       session: AsyncSession = Depends(get_session)):
    friend_service = FriendService(session)
    users = await friend_service.search_users(query, user.id)
    return [UserSearchResponse.model_validate(u) for u in users]


@router.get("/game/{game_id}/friend/{friend_id}/status")
async def get_friends_game_status(game_id: int,
                                  friend_id: int,
                                  user: User = Depends(get_current_user),
                                  session: AsyncSession = Depends(get_session)):
    friend_service = FriendService(session)

    friends = await friend_service.get_friends(user.id)
    friend_ids = [f.friend_id if f.user_id == user.id else f.user_id for f in friends]
    if friend_id not in friend_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not your friend")

    game_status = await friend_service.get_friend_game_status(friend_id, game_id)
    return {"game_status": game_status}


@router.post("/invite/{friend_id}", status_code=status.HTTP_201_CREATED)
async def invite_friend_to_game(friend_id: int,
                                user: User = Depends(get_current_user),
                                session: AsyncSession = Depends(get_session)):
    friend_service = FriendService(session)
    wallet = WalletService(session)
    game_service = GameService(session)
    notifications = NotificationService(session)
    try:
        success = await friend_service.invite_friend_to_game(user.id, friend_id, game_service, wallet, notifications)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Friend could not be invited")
    return {"friend_invited": success}
