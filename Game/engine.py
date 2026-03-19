import asyncio
from datetime import datetime
from Game.services import GameService
from Wallet.services import WalletService


class GameEngine:
    def __init__(self, session_factory, wallet_service: WalletService):
        self.session_factory = session_factory
        self.wallet_service = wallet_service

    async def daily_scheduler(self):
        while True:
            now = datetime.now()

            if now.hour == 20 and now.minute == 0:
                async with self.session_factory() as session:
                    service: GameService = GameService(session, self.wallet_service)
                    game = await service.get_daily_game()
                    await service.execute_flip(game.id)
                    await service.create_next_game()
                    await session.commit()

                await asyncio.sleep(60)  # avoid double-trigger

            await asyncio.sleep(1)

    async def showdown_scheduler(self):
        while True:
            async with self.session_factory() as session:
                service = GameService(session)
                games = await service.get_showdown_games()

                for game in games:
                    await service.execute_showdown_flip(game.id)

                await session.commit()

            await asyncio.sleep(1)

