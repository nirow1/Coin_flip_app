from sqlalchemy.ext.asyncio import AsyncSession
from Auth.dependencies import get_current_user
from Auth.models import User
from Game.services import GameService
from fastapi import APIRouter, Depends
from Wallet.services import WalletService
from db import get_session

router = APIRouter()

@router.post("/join")
async def join_game(side: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    game_service = GameService(session, wallet_service)
    await game_service.join_game(user.id, side)
    return {"message": "Joined game successfully"}

@router.post("/choose")
async def choose_side(side: str, game_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    game_service = GameService(session, wallet_service)
    response = await game_service.choose_side(user.id, game_id, side)
    return {"message": "Side chosen successfully", "heads": response["heads"], "tails": response["tails"]}


@router.post("/showdown/decision")
async def cashout_decision(decision: str, game_id: int,  user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    game_service = GameService(session, wallet_service)
    await game_service.set_showdown_decision(user.id, game_id, decision)
    return {"message": "Cashout decision recorded successfully"}


@router.get("/current")
async def get_current_game():


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