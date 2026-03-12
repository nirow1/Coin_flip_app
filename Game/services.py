from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Wallet.services import WalletService
from Game.models import Game, GamePlayer
from datetime import datetime, timezone
from typing import Optional


class GameService:
    def __init__(self, session: AsyncSession, wallet_service: WalletService):
        self.session = session
        self.wallet_service = wallet_service

        # Public API
    async def create_game(self, flip_time: datetime) -> Game:
        new_game = Game(status="open",
                        start_date=datetime.now(timezone.utc),
                        flip_time=flip_time,
                        prize_pool=Decimal("0"),
                        initial_player_count=None,
                        current_player_count=0,
                        showdown_active=False)

        self.session.add(new_game)
        await self.session.flush()
        return new_game

    async def get_open_game(self) -> Optional[Game]:
        result = await self.session.execute(
            select(Game).where(Game.status == "open")
        )
        return result.scalar_one()

    async def join_game(self, user_id: int, choice: str) -> GamePlayer:
        self._validate_choice(choice)

        game = await  self.get_open_game()
        if game is None:
            raise ValueError("No open game available to join")

        await self.wallet_service.debit(user_id, Decimal("1.00"))

        joined_player = GamePlayer(game_id=game.id,
                                   user_id=user_id,
                                   choice=choice,
                                   round_number=1,
                                   is_eliminated=False,
                                   eliminated_at=None)
        self.session.add(joined_player)

        game.prize_pool += Decimal("1.00")
        game.current_player_count += 1

        await self.session.flush()
        return joined_player

    async def choose_side(self, user_id: int, game_id: int, choice: str):
        ...

    async def get_percentages(self, game_id: int) -> dict:
        ...

    async def get_player_active_game(self, user_id: int) -> Optional[Game]:
        ...

    # Internal helpers
    async def _get_game_by_id(self, game_id: int) -> Game:
        ...

    async def _get_game_player(self, game_id: int, user_id: int) -> GamePlayer:
        ...

    async def _ensure_user_not_in_active_game(self, user_id: int):
        ...

    async def _calculate_percentages(self, game_id: int) -> dict:
        ...

    def _validate_choice(self, choice: str):
        ...