from Game.services import GameService
from Wallet.services import WalletService


async def test_join_game_success(session):
    service = GameService(session)
    wallet = WalletService(session)

    # setup: create user, add credits, create open game

    await service.join_game(user.id, "heads", wallet)

    # assert: player exists in game_players
    # assert: wallet balance decreased
    # assert: choice saved