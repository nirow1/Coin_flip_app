from sqlalchemy.ext.asyncio import AsyncSession
from Auth.dependencies import get_current_user, get_current_admin
from Wallet.services import WalletService
from fastapi import APIRouter, Depends, HTTPException, status
from Game.services import GameService
from Game.schemas import GameResponse, GamePlayerResponse
from Auth.models import User
from db import get_session
from typing import List

router = APIRouter()


@router.post("/join")
async def join_game(side: str, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    wallet_service = WalletService(session)
    game_service = GameService(session)
    try:
        await game_service.join_game(user.id, side, wallet_service)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Joined game successfully"}


@router.post("/choose")
async def choose_side(side: str, game_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    game_service = GameService(session)
    try:
        response = await game_service.choose_side(user.id, game_id, side)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Side chosen successfully", "heads": response["heads"], "tails": response["tails"]}


@router.post("/showdown/decision")
async def cashout_decision(decision: str, game_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    game_service = GameService(session)
    try:
        await game_service.set_showdown_decision(user.id, game_id, decision)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"message": "Cashout decision recorded successfully"}


@router.get("/current", response_model=List[GameResponse])
async def get_current_games(user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    game_service = GameService(session)
    games = await game_service.get_players_active_games(user.id)
    return [GameResponse.model_validate(g) for g in games]


@router.get("/{game_id}/state")
async def get_game_state(game_id: int, session: AsyncSession = Depends(get_session)):
    game_service = GameService(session)
    try:
        state = await game_service.get_game_status(game_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return {"state": state}


@router.get("/{game_id}/player")
async def get_game_player(game_id: int, user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)):
    game_service = GameService(session)
    try:
        player = await game_service.get_game_player(game_id, user.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return GamePlayerResponse.model_validate(player)


@router.get("/admin/games")
async def get_all_games(user: User = Depends(get_current_admin), session: AsyncSession = Depends(get_session)):
    game_service = GameService(session)
    games = await game_service.get_all_games()
    return [GameResponse.model_validate(g) for g in games]