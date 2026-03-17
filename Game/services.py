import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from Wallet.services import WalletService
from Game.models import Game, GamePlayer
from typing import Optional, List
from sqlalchemy import select
from decimal import Decimal


class GameService:
    def __init__(self, session: AsyncSession, wallet_service: WalletService):
        self.session = session
        self.wallet_service = wallet_service

        # Public API

    async def join_game(self, user_id: int, choice: str) -> GamePlayer:
        self._validate_choice(choice)

        game = await self.get_open_game(lock=True)

        if game is None:
            raise ValueError("No open game available")

        # Check if the player is already in the game
        existing = await self.session.execute(
            select(GamePlayer).where(GamePlayer.game_id == game.id,
                                     GamePlayer.user_id == user_id)
        )
        if existing.scalar_one_or_none() is not None:
            raise ValueError("Player is already in this game")

        if game.flip_time is not None:
            now = datetime.now(timezone.utc)
            lockout_start = game.flip_time - timedelta(minutes=5)
            if now >= lockout_start:
                raise ValueError("Joining is disabled 5 minutes before the flip")

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
        self._validate_choice(choice)

        game = await self._get_game_by_id(game_id)

        if game is None:
            raise ValueError("game does not exist")

        if game.status != "open":
            raise ValueError("Cannot choose a side in a game that is not open")

        result = await self.session.execute(select(GamePlayer)
                                             .where(GamePlayer.user_id == user_id,
                                                    GamePlayer.game_id == game_id))
        player = result.scalar_one_or_none()

        if player is None:
            raise ValueError("No player available to choose")

        if player.is_eliminated:
            raise ValueError("Eliminated players cannot choose a side")

        player.choice = choice
        await self.session.flush()

        return await self.get_percentages(game_id)

    async def get_percentages(self, game_id: int) -> dict:
        result = await self.session.execute(
            select(GamePlayer.choice)
            .where(GamePlayer.game_id == game_id,
                   GamePlayer.is_eliminated.is_(False))
        )
        choices = [row[0] for row in result.fetchall() if row[0] is not None]

        total_choices = len(choices)

        if total_choices == 0:
            return {"heads": 0, "tails": 0}

        return {
            "heads": round(choices.count("heads") / total_choices * 100, 2),
            "tails": round(choices.count("tails") / total_choices * 100, 2)
        }


    async def get_player_active_games(self, user_id: int) -> List[Game]:
        result = await self.session.execute(select(Game)
                                             .join(GamePlayer, Game.id == GamePlayer.game_id)
                                             .where(GamePlayer.user_id == user_id,
                                                    Game.status.in_(["open", "active"]),
                                                    GamePlayer.is_eliminated.is_(False)))
        return list(result.scalars().all())

    async def execute_flip(self, game_id: int) -> Game:
        game = await self._get_game_by_id(game_id)
        players = await self._get_players_for_game(game_id)

        if game.status not in ("open", "active"):
            raise ValueError("Cannot flip in this game state")

        # Increment round count for everyone
        for player in players:
            player.round_number += 1

        if len({p.choice for p in players}) == 1:
            game.status = "showdown_pending"
            await self.session.flush()
            return game

        # Normal flip
        winning_side = self._flip_coin()

        # Apply elimination logic
        for player in players:
            if player.choice != winning_side:
                player.is_eliminated = True
                player.eliminated_at = datetime.now(timezone.utc)

        # Set initial player count
        if game.initial_player_count is None:
            game.initial_player_count = len(players)

        survivors = [p for p in players if not p.is_eliminated]
        game.current_player_count = len(survivors)

        # One survivor → finished
        if len(survivors) == 1:
            game.status = "finished"
        # ≤ 5% survivors → showdown
        elif game.current_player_count / game.initial_player_count <= 0.05:
            game.status = "showdown_pending"
        # Otherwise → game continues normally
        else:
            game.status = "active"

        await self.session.flush()
        return game

    async def set_showdown_decision(self, user_id: int, game_id: int, decision: str):
        player = await self._get_game_player(game_id, user_id)
        game = await self._get_game_by_id(game_id)

        if player.is_eliminated:
            raise ValueError("Eliminated players cannot make a showdown decision")
        if game.status != "showdown_pending":
            raise ValueError("Showdown is not active yet")
        if decision not in ("cashout", "continue"):
            raise ValueError("Decision must be 'cashout' or 'continue'")

        player.cashout_decision = decision
        await self.session.flush()

    async def try_start_showdown(self, game_id: int) -> Optional[Game]:
        game = await self._get_game_by_id(game_id)

        if game.status != "showdown_pending":
            raise ValueError("Showdown is not pending")

        # Survivors only
        players = await self._get_players_for_game(game_id)

        # 1. Split into takers and continuers
        takers = [p for p in players if p.cashout_decision == "cashout"]
        continuers = [p for p in players if p.cashout_decision != "cashout"]  # includes undecided

        # 2. Process cashouts
        for p in takers:
            p.is_eliminated = True
            p.eliminated_at = datetime.now(timezone.utc)
            await self.cashout(p.user_id, game_id)

        # 3. Determine next state
        if len(continuers) == 0:
            game.status = "finished"
        elif len(continuers) == 1:
            winner = continuers[0]
            winner.is_eliminated = True
            winner.eliminated_at = datetime.now(timezone.utc)
            await self.cashout(winner.user_id, game_id)
            game.status = "finished"
        else:
            game.status = "showdown_active"

        await self.session.flush()
        return game

    async def execute_showdown_flip(self, game_id: int):
        ...

    async def cashout(self, user_id: int, game_id: int) -> Decimal:
        ...

    # Internal helpers
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

    async def _get_game_by_id(self, game_id: int, lock: bool = True) -> Game:
        query = select(Game).where(Game.id == game_id)
        if lock:
            query = query.with_for_update()

        game = (await self.session.execute(query)).scalar_one_or_none()
        if game is None:
            raise ValueError("Game not found")

        return game

    async def get_open_game(self, lock: bool = False) -> Optional[Game]:
        query = select(Game).where(Game.status == "open")
        if lock:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_game_player(self, game_id: int, user_id: int) -> GamePlayer:
        result = await self.session.execute(select(GamePlayer)
                                             .where(GamePlayer.game_id == game_id,
                                                    GamePlayer.user_id == user_id))
        player = result.scalar_one_or_none()

        if player is None:
            raise ValueError("Player not found in this game")

        return player

    async def _get_players_for_game(self, game_id: int) -> List[GamePlayer]:
        result = await self.session.execute(select(GamePlayer)
                                             .where(GamePlayer.game_id == game_id,
                                                    GamePlayer.is_eliminated.is_(False)))
        return list(result.scalars().all())

    @staticmethod
    def _flip_coin() -> str:
        return "heads" if secrets.randbelow(2) == 0 else "tails"

    @staticmethod
    def _validate_choice(choice: str):
        if choice not in ("heads", "tails"):
            raise ValueError("Choice must be 'heads' or 'tails'")