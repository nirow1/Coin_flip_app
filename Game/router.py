from sqlalchemy.ext.asyncio import AsyncSession
from Auth.dependencies import get_current_user
from Auth.models import User
from Game.services import GameService
from fastapi import APIRouter, Depends
from Wallet.services import WalletService
from db import get_session

router = APIRouter()

@router.post("/join")
async def join_game(choice: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    game_service = GameService(session, wallet_service)
    await game_service.join_game(user.id, choice)
    return {"message": "Joined game successfully"}

@router.post("/choose")
async def choose_side():
    ...

@router.post("/showdown/decision")
async def cashout_decision():
    ...

@router.get("/current")
async def get_current_game():
    ...

@router.get("/{game_id}/state")
async def get_game_state(game_id: int):
    ...

@router.get("/{game_id}/player")
async def get_game_player(game_id: int):
    ...

@router.get("/me/active")
async def get_players_active_games():
    ...

@router.get("/admin/games")
async def get_all_games():
    ...