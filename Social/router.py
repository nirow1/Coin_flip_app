from fastapi import APIRouter
from Social.service import FriendService

router = APIRouter(prefix="/friends", tags=["friends"])

@router.post("/request/{friend_id}")
async def send_friend_request(friend_id: int):
    ...