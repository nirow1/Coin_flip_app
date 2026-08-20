import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.Game.models import Game, GamePlayer
from Backend.Leader_board.service import LeaderBoardService
from Backend.Wallet.enums import TransactionType
from Backend.Wallet.services import WalletService


class GameService:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ─── Public API ───────────────────────────────────────────────
    async def join_game(self, user_id: int, side: str, wallet: WalletService, redis_client: Redis) -> (GamePlayer, Game):
        self._validate_side(side)

        game = await self._get_or_raise_open_game()

        if await self._check_player_in_game(game.id, user_id):
            raise ValueError("Player is already in this game")

        self._check_lockout(game)

        await wallet.debit(user_id, Decimal("1.00"))
        player = await self._add_player_to_game(game, user_id, side, paid_by_user_id=user_id)
        await self._record_choice(game.id, 1, side, redis_client)
        return (player, game)

    async def invite_friend(self, user_id: int, friend_id: int, wallet: WalletService) -> bool:
        game = await self._get_or_raise_open_game()

        if await self._check_player_in_game(game.id, friend_id):
            raise ValueError("Friend is already in this game")

        self._check_lockout(game)

        await wallet.debit(user_id, Decimal("1.00"))
        await self._add_player_to_game(game, friend_id, None, paid_by_user_id=user_id)
        return True

    async def choose_side(self, user_id: int, game_id: int, side: str, redis_client: Redis) -> dict:
        self._validate_side(side)

        game = await self._get_game_by_id(game_id, lock=False)

        if game.status in ("showdown_pending", "finished"):
            raise ValueError("Cannot choose side in this game state")

        player = await self._get_game_player(game_id, user_id)

        if player.is_eliminated:
            raise ValueError("Eliminated players cannot choose a side")

        if player.side is not None:
            raise ValueError("Player has already chosen side")

        previous_side = player.side
        player.side = side
        await self.session.flush()

        await self._record_choice(game_id, player.round_number, side, redis_client)
        return await self.get_percentages(game_id, player.round_number, redis_client)

    async def get_players_active_games(self, user_id: int) -> list[Game]:
        result = await self.session.execute(select(Game)
                                             .join(GamePlayer, Game.id == GamePlayer.game_id)
                                             .where(GamePlayer.user_id == user_id,
                                                    Game.status.in_(["open", "active", "showdown_pending", "showdown_active"]),
                                                    GamePlayer.is_eliminated.is_(False)))
        return list(result.scalars().all())

    async def execute_flip(self, game_id: int,wallet: WalletService, leaderboard: LeaderBoardService) -> Game:
        game = await self._get_game_by_id(game_id)
        players = await self._get_players_for_game(game_id)

        if game.status not in ("open", "active"):
            raise ValueError("Cannot flip in this game state")

        # Increment round count for all players and assign random side to those who haven't chosen yet
        for player in players:
            player.round_number += 1
            if player.side is None:
                player.side = self._flip_coin()

        # All players chose the same side → trigger showdown
        if len({p.side for p in players}) == 1:
            game.status = "showdown_pending"
            self._set_initial_player_count(game, len(players))
            # Reset sides so players get a fresh choice when showdown_active begins
            for player in players:
                player.side = None
            await self.session.flush()
            return game

        # Set initial player count on first flip
        self._set_initial_player_count(game, len(players))

        # Flip coin, eliminate losers, determine next state
        winning_side = self._flip_coin()
        survivors, eliminated = self._apply_eliminations(players, winning_side)

        for player in eliminated:
            await leaderboard.update_streak(player.user_id, player.round_number)

        self._determine_next_state(game, survivors)

        if len(survivors) == 1:
            winner = survivors[0]
            await self._cashout(winner, game, game.prize_pool, wallet, leaderboard)

        await self.session.flush()
        return game

    async def set_showdown_decision(self, user_id: int, game_id: int, decision: str):
        if decision not in ("cashout", "continue"):
            raise ValueError("Decision must be 'cashout' or 'continue'")

        game = await self._get_game_by_id(game_id)

        if game.status != "showdown_pending":
            raise ValueError("Showdown is not active yet")

        player = await self._get_game_player(game_id, user_id)

        if player.is_eliminated:
            raise ValueError("Eliminated players cannot make a showdown decision")

        player.cashout_decision = decision
        await self.session.flush()

    async def try_start_showdown(self, game_id: int,
                                 wallet: WalletService,
                                 leaderboard: LeaderBoardService,
                                 redis_client: Redis) -> Game | None:
        game = await self._get_game_by_id(game_id)

        if game.status != "showdown_pending":
            raise ValueError("Showdown is not pending")

        # Survivors only
        players = await self._get_players_for_game(game_id)

        # 1. Split into takers and continuers. Players who haven't decided are treated as continuers.
        takers = [p for p in players if p.cashout_decision == "cashout"]
        continuers = [p for p in players if p.cashout_decision != "cashout"]  # includes undecided

        # 2. Process cashouts
        payout = (game.prize_pool / len(players)).quantize(Decimal("0.01"))
        total_payout = payout * len(takers)
        game.prize_pool -= total_payout

        for player in takers:
            await self._cashout(player, game, payout, wallet, leaderboard)

        # 3. Determine next state
        if len(continuers) == 0:
            game.status = "finished"
        elif len(continuers) == 1:
            winner = continuers[0]
            game.status = "finished"
            await self._cashout(winner, game, game.prize_pool, wallet, leaderboard)
        else:
            game.status = "showdown_active"
            await redis_client.set(f"showdown_flip:{game_id}:{continuers[0].round_number}", "1", ex=60)

        await self.session.flush()
        return game

    async def execute_showdown_flip(self, game_id: int,
                                    wallet: WalletService,
                                    leaderboard: LeaderBoardService,
                                    redis_client: Redis):
        game = await self._get_game_by_id(game_id)

        if game.status != "showdown_active":
            raise ValueError("Showdown is not active")

        players = await self._get_players_for_game(game_id)

        for player in players:
            player.round_number += 1
            if player.side is None:
                player.side = self._flip_coin()

        winning_side = self._flip_coin()

        # Invalid flip: nobody chose the winning side → reset sides and retry next round
        if all(p.side != winning_side for p in players):
            for player in players:
                player.side = None
            await redis_client.set(f"showdown_flip:{game_id}:{players[0].round_number}", "1", ex=60)
            return await self._set_game_state(game, "showdown_active")

        survivors, eliminated = self._apply_eliminations(players, winning_side)

        for player in eliminated:
            await leaderboard.update_streak(player.user_id, player.round_number)

        if len(survivors) == 1:
            winner = survivors[0]
            game = await self._set_game_state(game, "finished")
            await self._cashout(winner, game, game.prize_pool, wallet, leaderboard)
            return game

        game.current_player_count = len(survivors)
        await redis_client.set(f"showdown_flip:{game_id}:{players[0].round_number}", "1", ex=60)
        return await self._set_game_state(game, "showdown_active")

    # ─── Open-game lifecycle (engine recovery) ────────────────────
    async def create_game(self, flip_time: datetime) -> Game:
        new_game = Game(status="open",
                        start_date=datetime.now(timezone.utc),
                        flip_time=flip_time,
                        prize_pool=Decimal(0),
                        initial_player_count=None,
                        current_player_count=0,
                        showdown_active=False)

        self.session.add(new_game)
        await self.session.flush()
        return new_game

    def next_daily_flip_time(self, now: datetime | None = None) -> datetime:
        now = now or datetime.now(timezone.utc)
        candidate = now.replace(hour=19, minute=0, second=0, microsecond=0)
        if now >= candidate:
            candidate += timedelta(days=1)
        return candidate

    async def ensure_open_game(self, wallet: WalletService) -> Game | None:
        await self.cancel_stale_open_games(wallet)

        game = await self.get_open_game()

        if game is None:
            return await self.create_game(self.next_daily_flip_time())

        return game

    async def cancel_stale_open_games(self, wallet: WalletService):
        # 1m grace after flip_time so the 19:00 flip path can finish before refunds.
        games = await self.get_open_games()
        for game in games:
            if game.flip_time < datetime.now(timezone.utc) - timedelta(minutes=1):
                await self.cancel_game(game.id, wallet)

    async def cancel_game(self, game_id: int, wallet: WalletService):
        """Cancel an open/active game and refund each seat's join fee.

        TODO(void-game): showdown_pending / showdown_active / finished need a separate
        void path — claw back amount_won, reverse leaderboard earnings, honour
        withdrawal locks, and never stack a 1.00 seat refund on top of cashouts.
        """
        game = await self._get_game_by_id(game_id)
        if game.status not in ("open", "active"):
            raise ValueError("Only open or active games can be canceled")

        # All seats (including eliminated) paid 1.00; refund each for open/active void.
        # House absorbs the 2% edge if the game had already flipped (prize_pool *= 0.98).
        players = await self.get_all_players(game_id)
        for player in players:
            await self._refund(player, game, wallet)

        game.prize_pool = Decimal(0)
        game.status = "canceled"
        await self.session.flush()
        return game

    # ─── Queries ──────────────────────────────────────────────────
    async def get_all_games(self) -> list[Game]:
        result = await self.session.execute(select(Game).order_by(Game.id.desc()))
        return list(result.scalars().all())

    async def get_all_players(self, game_id: int) -> list[GamePlayer]:
        result = await self.session.execute(select(GamePlayer).where(GamePlayer.game_id == game_id))
        return list(result.scalars().all())

    async def get_open_game(self, lock: bool = False) -> Game | None:
        query = select(Game).where(Game.status == "open").order_by(Game.flip_time.asc())
        if lock:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_open_games(self) -> list[Game]:
        result = await self.session.execute(
            select(Game).where(Game.status == "open").order_by(Game.flip_time.asc())
        )
        return list(result.scalars().all())

    async def get_active_games(self) -> list[Game]:
        result = await self.session.execute(select(Game).where(Game.status.in_(["open", "active", "showdown_pending"])).order_by(Game.id.desc()))
        return list(result.scalars().all())

    async def get_showdown_pending_games(self) -> list[Game]:
        """Returns games waiting for players to make cashout/continue decisions."""
        result = await self.session.execute(select(Game).where(Game.status == "showdown_pending").order_by(Game.id.desc()))
        return list(result.scalars().all())

    async def get_showdown_active_games(self) -> list[Game]:
        """Returns games in active showdown phase (ready for execute_showdown_flip)."""
        result = await self.session.execute(select(Game).where(Game.status == "showdown_active").order_by(Game.id.desc()))
        return list(result.scalars().all())

    async def get_game_status(self, game_id: int) -> str:
        game = await self._get_game_by_id(game_id, lock=False)
        return game.status

    async def get_game_player(self, game_id: int, user_id: int) -> GamePlayer:
        return await self._get_game_player(game_id, user_id)

    # ─── Internal Helpers ─────────────────────────────────────────
    async def _get_or_raise_open_game(self) -> Game:
        """Fetches the next open game or raises if none available."""
        game = await self.get_open_game(lock=True)
        if game is None:
            raise ValueError("No open game available")
        return game

    async def _refund(self, player: GamePlayer, game: Game, wallet: WalletService):
        # Prefer paid_by_user_id (inviter); fall back to seat holder for legacy rows.
        recipient_id = player.paid_by_user_id if player.paid_by_user_id is not None else player.user_id
        await wallet.credit(recipient_id, Decimal("1.00"), TransactionType.REFUND)
        await self.session.flush()
        return True

    async def _cashout(self, player: GamePlayer,
                       game: Game, payout: Decimal,
                       wallet: WalletService,
                       leaderboard: LeaderBoardService) -> Decimal:
        if player.is_eliminated:
            raise ValueError("Eliminated players cannot cash out")

        if game.status not in ("showdown_pending", "finished"):
            raise ValueError("Cannot cash out in this game state")

        player.is_eliminated = True
        player.eliminated_at = datetime.now(timezone.utc)

        # TODO(void-game): persist amount_won (and funds_locked_until) on GamePlayer
        # before/with this credit so a later void can claw back exactly.
        await wallet.credit(player.user_id, payout)
        await leaderboard.increment_earnings(player.user_id, payout)
        await leaderboard.update_streak(player.user_id, player.round_number)
        await self.session.flush()
        return payout

    async def _add_player_to_game(
        self,
        game: Game,
        user_id: int,
        side: str | None,
        paid_by_user_id: int | None = None,
    ) -> GamePlayer:
        """Creates a GamePlayer record and updates game stats. Does not handle payment."""
        player = GamePlayer(
            game_id=game.id,
            user_id=user_id,
            side=side,
            round_number=1,
            is_eliminated=False,
            eliminated_at=None,
            paid_by_user_id=paid_by_user_id if paid_by_user_id is not None else user_id,
        )
        self.session.add(player)
        game.prize_pool += Decimal("1.00")
        game.current_player_count += 1
        await self.session.flush()
        return player

    async def _get_game_by_id(self, game_id: int, lock: bool = True) -> Game:
        query = select(Game).where(Game.id == game_id)
        if lock:
            query = query.with_for_update()

        game = (await self.session.execute(query)).scalar_one_or_none()
        if game is None:
            raise ValueError("Game not found")

        return game

    async def _get_game_player(self, game_id: int, user_id: int) -> GamePlayer:
        result = await self.session.execute(select(GamePlayer)
                                             .where(GamePlayer.game_id == game_id,
                                                    GamePlayer.user_id == user_id))
        player = result.scalar_one_or_none()

        if player is None:
            raise ValueError("Player not found in this game")

        return player

    async def _get_players_for_game(self, game_id: int) -> list[GamePlayer]:
        result = await self.session.execute(select(GamePlayer)
                                             .where(GamePlayer.game_id == game_id,
                                                    GamePlayer.is_eliminated.is_(False)))
        return list(result.scalars().all())

    async def _set_game_state(self, game: Game, state: str) -> Game:
        """Utility to set game state with validation."""
        # "canceled" is set directly in cancel_game today; include here if that path switches.
        if state not in ("open", "active", "showdown_pending", "showdown_active", "finished", "canceled"):
            raise ValueError("Invalid game state")
        game.status = state
        await self.session.flush()
        return game

    async def _check_player_in_game(self, game_id: int, user_id: int) -> bool:
        existing = await self.session.execute(
            select(GamePlayer).where(GamePlayer.game_id == game_id,
                                     GamePlayer.user_id == user_id)
        )

        return existing.scalar_one_or_none() is not None

    # ─── Static Utilities ─────────────────────────────────────────
    @staticmethod
    def _apply_eliminations(players: list[GamePlayer], winning_side: str) -> tuple[list[GamePlayer], list[GamePlayer]]:
        """Marks losing players as eliminated. Returns (survivors, eliminated)."""
        survivors = []
        eliminated = []
        for player in players:
            if player.side != winning_side:
                player.is_eliminated = True
                player.eliminated_at = datetime.now(timezone.utc)
                eliminated.append(player)
            else:
                player.side = None
                survivors.append(player)
        return survivors, eliminated

    @staticmethod
    def _check_lockout(game: Game) -> None:
        """Raises if joining is disabled within 5 minutes of the flip."""
        if game.flip_time is not None:
            now = datetime.now(timezone.utc)
            lockout_start = game.flip_time - timedelta(minutes=5)
            if now >= lockout_start:
                raise ValueError("Joining is disabled 5 minutes before the flip")

    @staticmethod
    def _determine_next_state(game: Game, survivors: list[GamePlayer]) -> None:
        """Updates game status and player count based on remaining survivors."""
        game.current_player_count = len(survivors)

        if len(survivors) == 1:
            game.status = "finished"
        elif game.current_player_count / game.initial_player_count <= 0.05:
            game.status = "showdown_pending"
        else:
            game.status = "active"

    @staticmethod
    def _flip_coin() -> str:
        return "heads" if secrets.randbelow(2) == 0 else "tails"

    @staticmethod
    def _validate_side(choice: str):
        if choice not in ("heads", "tails") or choice is None:
            raise ValueError("Side must be 'heads' or 'tails'")

    @staticmethod
    def _set_initial_player_count(game: Game, count: int):
        if game.initial_player_count is None:
            game.initial_player_count = count
            game.prize_pool *= Decimal("0.98")
            game.prize_pool = game.prize_pool.quantize(Decimal("0.01"))

    @staticmethod
    async def get_percentages(game_id: int, round_id: int, redis_client: Redis) -> dict:
        heads_key = f"game:{game_id}:round:{round_id}:heads"
        tails_key = f"game:{game_id}:round:{round_id}:tails"

        heads, tails = await redis_client.mget(heads_key, tails_key)
        heads = int(heads or 0)
        tails = int(tails or 0)

        total_choices = heads + tails
        if total_choices == 0:
            return {"heads": 0, "tails": 0}

        return {
            "heads": round((heads / total_choices) * 100, 2),
            "tails": round((tails / total_choices) * 100, 2),
        }

    @staticmethod
    async def _record_choice(game_id: int, round_id: int, choice: str, redis_client: Redis):
        key = f"game:{game_id}:round:{round_id}:{choice}"
        await redis_client.incr(key)
        await redis_client.expire(key, 86400)  # TTL: 24 hours

    @staticmethod
    async def _decrement_choice(game_id: int, round_id: int, choice: str, redis_client: Redis):
        key = f"game:{game_id}:round:{round_id}:{choice}"
        current = await redis_client.get(key)
        if current is not None and int(current) > 0:
            await redis_client.decr(key)
