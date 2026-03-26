import pytest
from decimal import Decimal
from unittest.mock import patch
from Game.models import GamePlayer
from Game.services import GameService
from Wallet.services import WalletService

pytestmark = pytest.mark.asyncio(loop_scope="session")

async def test_execute_showdown_flip_success(session, make_game, create_test_user):
    service = GameService(session)
    wallet = WalletService(session)
    game = await make_game("showdown_active")

    for i in range(100):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "heads" if i % 2 == 0 else "tails"
        session.add(GamePlayer(user_id=user.id, game_id=game.id, side=side,
                               cashout_decision="continue", is_eliminated=False))

    await session.flush()

    game_after_flip = await service.execute_showdown_flip(game.id, wallet)

    assert game_after_flip.status == "showdown_active"

    players = await service.get_all_players(game.id)
    eliminated = [p for p in players if p.is_eliminated]
    assert len(eliminated) == 50

async def test_execute_showdown_flip_winner(session, test_user, test_wallet, make_game, create_test_user):
    service = GameService(session)
    wallet = WalletService(session)
    game = await make_game("showdown_active")

    game.prize_pool = Decimal("101.00")
    await session.flush()

    session.add(GamePlayer(user_id=test_user.id, game_id=game.id, side="tails",  cashout_decision="continue", is_eliminated=False))

    for i in range(100):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "heads"
        session.add(GamePlayer(user_id=user.id, game_id=game.id, side=side,  cashout_decision="continue", is_eliminated=False))

    await session.flush()

    # Check test_user balance before cashout
    balance_before = (await wallet.get_wallet(test_user.id)).balance

    with patch.object(GameService, "_flip_coin", return_value="tails"):
        game_after_flip = await service.execute_showdown_flip(game.id, wallet)

    assert game_after_flip.status == "finished"

    balance_after = (await wallet.get_wallet(test_user.id)).balance
    assert balance_after == balance_before + Decimal("101.00")

