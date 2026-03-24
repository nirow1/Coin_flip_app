from decimal import Decimal

from Game.models import GamePlayer
from Wallet.services import WalletService
from Game.services import GameService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

async def test_join_game_success(session, test_user, open_game, test_wallet):
    service = GameService(session)
    wallet = WalletService(session)

    await wallet.credit(test_user.id, Decimal("50.00"))

    player = await service.join_game(test_user.id, "heads", wallet)

    fetch = await service.get_game_player(player.game_id, player.user_id)
    # assert: player exists in game_players
    assert fetch is not None

    # assert: game player state
    assert fetch.user_id == test_user.id
    assert fetch.side == "heads"
    assert fetch.is_eliminated == False

    # assert: wallet balance decreased
    players_wallet = await wallet.get_wallet(test_user.id)
    assert players_wallet.balance == Decimal("49.00")
    
async def test_join_game_fail(session, test_user, open_game, test_wallet):
    service = GameService(session)
    wallet = WalletService(session)

    # Fail 1: insufficient funds — wallet has 0.00 balance, debit of 1.00 is rejected
    with pytest.raises(Exception) as exc_info:
        await service.join_game(test_user.id, "heads", wallet)
    assert exc_info.value.status_code == 400

    # Fail 2: player already joined — credit wallet, join once, then try again
    await wallet.credit(test_user.id, Decimal("50.00"))
    await service.join_game(test_user.id, "heads", wallet)

    with pytest.raises(ValueError, match="Player is already in this game"):
        await service.join_game(test_user.id, "heads", wallet)

async def test_choose_side_success(session, test_user, make_game):
    service = GameService(session)

    game = await make_game("open")

    # Add player directly — bypassing join_game to avoid wallet side effects
    player = GamePlayer(
        game_id=game.id,
        user_id=test_user.id,
        side="heads",
        round_number=1,
        is_eliminated=False,
    )
    session.add(player)
    await session.flush()

    # Action: change side to "tails"
    await service.choose_side(test_user.id, game.id, "tails")

    # Assert: player's side is updated
    fetch = await service.get_game_player(game.id, test_user.id)
    assert fetch.side == "tails"

