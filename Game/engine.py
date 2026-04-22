import asyncio
from datetime import datetime, timezone, timedelta
from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from Game.service import GameService
from Leader_board.service import LeaderBoardService
from Wallet.services import WalletService


class GameEngine:
    def __init__(self, async_session, wallet_service: WalletService, leaderboard: LeaderBoardService, redis: Redis, pubsub: PubSub):
        self.async_session = async_session
        self.wallet_service = wallet_service
        self.leaderboard_service = leaderboard
        self.redis_client = redis
        self.pubsub = pubsub

    async def daily_scheduler(self):
        while True:
            now = datetime.now(timezone.utc)

            # 20:00 CET == 19:00 UTC
            if now.hour == 19 and now.minute == 0:
                async with self.async_session() as session:
                    service = GameService(session)

                    games = await service.get_active_games()

                    for game in games:
                        try:
                            if game.status in ("open", "active"):
                                await service.execute_flip(game.id, self.wallet_service, self.leaderboard_service)

                            elif game.status == "showdown_pending":
                                await service.try_start_showdown(game.id, self.wallet_service, self.leaderboard_service, self.redis_client)
                        except Exception as e:
                            print(f"Error processing game {game.id}: {e}")

                    # Always create a new open game at 20:00
                    await service.create_game(now + timedelta(days=1))

                    await session.commit()

                await asyncio.sleep(60)  # prevent double-trigger

            await asyncio.sleep(1)

    async def showdown_scheduler(self):
        await self.pubsub.psubscribe("__keyevent@0__:expired")

        async for message in self.pubsub.listen():
            if message["type"] != "pmessage":
                continue
            expired_key = message["data"]

            if expired_key.startswith("showdown_flip:"):
                parts = expired_key.split(":")
                if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
                    print(f"Skipping malformed showdown key: {expired_key}")
                    continue

                _, game_id, round_id = parts

                async with self.async_session() as session:
                    service = GameService(session)

                    try:
                        await service.execute_showdown_flip(int(game_id),
                                                            self.wallet_service,
                                                            self.leaderboard_service,
                                                            self.redis_client)
                        await session.commit()
                    except Exception as e:
                        print(f"Error processing showdown flip for game {game_id}: {e}")