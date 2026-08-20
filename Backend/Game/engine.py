import asyncio
from datetime import datetime, timezone

from redis.asyncio import Redis
from redis.asyncio.client import PubSub

from Backend.Game.service import GameService
from Backend.Leader_board.service import LeaderBoardService
from Backend.Wallet.services import WalletService


class GameEngine:
    def __init__(self, async_session, redis: Redis, pubsub: PubSub):
        self.async_session = async_session
        self.redis_client = redis
        self.pubsub = pubsub

    async def daily_scheduler(self):
        """Flip at 19:00 UTC, and ensure an open game exists ~once per minute.

        Ordering: at 19:00, flip/showdown runs before ensure so a due open game
        is not cancelled-by-staleness instead of flipped. If flip fails and the
        game stays open past flip_time, the next ensure tick cancels + refunds
        (intentional fallback; service applies a short grace window).
        """
        while True:
            now = datetime.now(timezone.utc)
            is_flip_minute = now.hour == 19 and now.minute == 0

            async with self.async_session() as session:
                service = GameService(session)
                wallet = WalletService(session)
                leaderboard = LeaderBoardService(session)

                if is_flip_minute:
                    games = await service.get_active_games()

                    for game in games:
                        try:
                            if game.status in ("open", "active"):
                                await service.execute_flip(game.id, wallet, leaderboard)

                            elif game.status == "showdown_pending":
                                await service.try_start_showdown(
                                    game.id,
                                    wallet,
                                    leaderboard,
                                    self.redis_client,
                                )
                        except Exception as e:
                            print(f"Error processing game {game.id}: {e}")

                await service.ensure_open_game(wallet)
                await session.commit()

            # Throttle ensure + avoid double-triggering the 19:00 flip minute.
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
                    await service.execute_showdown_flip(
                        game_id,
                        wallet,
                        leaderboard,
                        self.redis_client,
                    )
                    await session.commit()
                except Exception as e:
                    print(f"Error processing showdown flip for game {game_id}: {e}")
