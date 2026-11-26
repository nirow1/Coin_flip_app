import asyncio
from datetime import datetime, time, timezone

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from Backend.Game.service import GameService
from Backend.Leader_board.service import LeaderBoardService
from Backend.Wallet.services import WalletService

_LAST_FLIP_DATE_KEY = "scheduler:last_flip_date"
_SHOWDOWN_TIMER_TTL_S = 60


class GameEngine:
    def __init__(self, async_session, redis: Redis, pubsub: PubSub):
        self.async_session = async_session
        self.redis_client = redis
        self.pubsub = pubsub

    async def daily_scheduler(self):
        """Flip at/after 19:00 UTC once per day, and ensure an open game ~once per minute.

        Ordering: flip/showdown runs before ensure so a due open game is not
        cancelled-by-staleness instead of flipped. If flip fails and the game
        stays open past flip_time, the next ensure tick cancels + refunds
        (intentional fallback; service applies a short grace window).

        Flips commit separately from ensure_open_game so a ensure failure cannot
        roll back the day's payouts. Tick-level errors are logged and the loop
        continues so the scheduler stays alive.

        Flip idempotency uses Redis key scheduler:last_flip_date (UTC date) so
        sleep drift and leader restarts cannot miss or double-run the daily flip.
        Missing showdown Redis timers are re-armed each tick.
        """
        while True:
            now = datetime.now(timezone.utc)

            try:
                should_flip = await self._should_run_daily_flip(now)
                timer_keys: list[str] = []

                if should_flip:
                    async with self.async_session() as session:
                        service = GameService(session)
                        wallet = WalletService(session)
                        leaderboard = LeaderBoardService(session)

                        games = await service.get_active_games()

                        for game in games:
                            if game.status not in ("open", "active", "showdown_pending"):
                                continue
                            try:
                                async with session.begin_nested():
                                    if game.status in ("open", "active"):
                                        await service.execute_flip(
                                            game.id, wallet, leaderboard
                                        )
                                    else:
                                        _, timer_key = await service.try_start_showdown(
                                            game.id,
                                            wallet,
                                            leaderboard,
                                        )
                                        if timer_key:
                                            timer_keys.append(timer_key)
                            except Exception as e:
                                print(f"Error processing game {game.id}: {e}")

                        await session.commit()

                    await self._mark_daily_flip_done(now)
                    await self._set_timer_keys(timer_keys)

                await self._recover_missing_showdown_timers()

                try:
                    async with self.async_session() as session:
                        service = GameService(session)
                        wallet = WalletService(session)
                        await service.ensure_open_game(wallet)
                        await session.commit()
                except Exception as e:
                    print(f"Error ensuring open game: {e}")

            except Exception as e:
                print(f"Error in daily_scheduler tick: {e}")

            # Throttle ensure + avoid spinning the loop.
            await asyncio.sleep(60)

    async def showdown_scheduler(self):
        await self.pubsub.psubscribe("__keyevent@0__:expired")

        async for message in self.pubsub.listen():
            if message["type"] != "pmessage":
                continue

            expired_key = message["data"]
            if isinstance(expired_key, bytes):
                expired_key = expired_key.decode()

            if not expired_key.startswith("showdown_flip:"):
                continue

            # Key shape: showdown_flip:{game_id}:{round_number}
            # round_number uniqueness is for Redis TTL timers; flip logic reads DB state.
            parts = expired_key.split(":")
            if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
                print(f"Skipping malformed showdown key: {expired_key}")
                continue

            game_id = int(parts[1])

            async with self.async_session() as session:
                service = GameService(session)
                wallet = WalletService(session)
                leaderboard = LeaderBoardService(session)

                try:
                    _, timer_key = await service.execute_showdown_flip(
                        game_id,
                        wallet,
                        leaderboard,
                    )
                    await session.commit()
                    if timer_key:
                        await self._set_timer_keys([timer_key])
                except Exception as e:
                    print(f"Error processing showdown flip for game {game_id}: {e}")

    async def _should_run_daily_flip(self, now: datetime) -> bool:
        """True when local UTC time is at/after today's 19:00 and we have not flipped today."""
        flip_at = datetime.combine(now.date(), time(19, 0), tzinfo=timezone.utc)
        if now < flip_at:
            return False

        today = now.date().isoformat()
        try:
            last = await self.redis_client.get(_LAST_FLIP_DATE_KEY)
        except Exception as e:
            print(f"Error reading last flip date: {e}")
            return False

        if isinstance(last, bytes):
            last = last.decode()
        return last != today

    async def _mark_daily_flip_done(self, now: datetime) -> None:
        today = now.date().isoformat()
        try:
            await self.redis_client.set(_LAST_FLIP_DATE_KEY, today)
        except Exception as e:
            print(f"Error writing last flip date: {e}")

    async def _set_timer_keys(self, timer_keys: list[str]) -> None:
        for timer_key in timer_keys:
            try:
                await self.redis_client.set(timer_key, "1", ex=_SHOWDOWN_TIMER_TTL_S)
            except Exception as e:
                print(f"Error setting showdown timer {timer_key}: {e}")

    async def _recover_missing_showdown_timers(self) -> None:
        """Re-arm Redis TTL timers for showdown_active games that have none."""
        try:
            async with self.async_session() as session:
                service = GameService(session)
                games = await service.get_showdown_active_games()
                missing: list[str] = []

                for game in games:
                    try:
                        pattern = f"showdown_flip:{game.id}:*"
                        existing = await self.redis_client.keys(pattern)
                        if existing:
                            continue
                        timer_key = await service.showdown_timer_key(game.id)
                        if timer_key:
                            missing.append(timer_key)
                    except Exception as e:
                        print(f"Error checking showdown timer for game {game.id}: {e}")
        except Exception as e:
            print(f"Error recovering showdown timers: {e}")
            return

        if missing:
            await self._set_timer_keys(missing)
