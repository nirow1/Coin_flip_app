import asyncio
from datetime import datetime, timezone, timedelta
from Game.services import GameService
from Wallet.services import WalletService


class GameEngine:
    def __init__(self, async_session, wallet_service: WalletService):
        self.async_session = async_session
        self.wallet_service = wallet_service

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
                                await service.execute_flip(game.id)

                            elif game.status == "showdown_pending":
                                await service.try_start_showdown(game.id, self.wallet_service)
                        except Exception as e:
                            print(f"Error processing game {game.id}: {e}")

                    # Always create a new open game at 20:00
                    await service.create_game(now + timedelta(days=1))

                    await session.commit()

                await asyncio.sleep(60)  # prevent double-trigger

            await asyncio.sleep(1)

    async def showdown_scheduler(self):
        while True:
            async with self.async_session() as session:
                service = GameService(session)

                # Fetch games that are in showdown_active state (ready for a flip)
                games = await service.get_showdown_active_games()

                for game in games:
                    try:
                        await service.execute_showdown_flip(game.id, self.wallet_service)
                    except Exception as e:
                        print(f"Error processing showdown flip for game {game.id}: {e}")

                await session.commit()

            await asyncio.sleep(1)


