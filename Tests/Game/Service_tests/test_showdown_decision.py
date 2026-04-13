from datetime import timedelta
from Game.models import GamePlayer
from Game.service import GameService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_set_showdown_decision_continue(session, make_game, create_test_user):
    service = GameService(session)
    game = await make_game("showdown_pending", timedelta(seconds=1))

    user = await create_test_user("choosing_user@test.com")
    session.add(GamePlayer(game_id=game.id, user_id=user.id,
                           side=None, round_number=1, is_eliminated=False))
    await session.flush()

    await service.set_showdown_decision(user.id, game.id, "continue")

    player = await service.get_game_player(game.id, user.id)
    assert player.cashout_decision == "continue"


async def test_set_showdown_decision_cashout(session, make_game, create_test_user):
    service = GameService(session)
    game = await make_game("showdown_pending", timedelta(seconds=1))

    user = await create_test_user("cashout_user@test.com")
    session.add(GamePlayer(game_id=game.id, user_id=user.id,
                           side=None, round_number=1, is_eliminated=False))
    await session.flush()

    await service.set_showdown_decision(user.id, game.id, "cashout")

    player = await service.get_game_player(game.id, user.id)
    assert player.cashout_decision == "cashout"


async def test_set_showdown_decision_invalid_decision(session, make_game, create_test_user):
    service = GameService(session)
    game = await make_game("showdown_pending", timedelta(seconds=1))

    user = await create_test_user("invalid_user@test.com")
    session.add(GamePlayer(game_id=game.id, user_id=user.id,
                           side=None, round_number=1, is_eliminated=False))
    await session.flush()

    with pytest.raises(ValueError, match="Decision must be 'cashout' or 'continue'"):
        await service.set_showdown_decision(user.id, game.id, "invalid")


async def test_set_showdown_decision_wrong_game_status(session, make_game, create_test_user):
    service = GameService(session)
    # Game is "active" — not in showdown_pending
    game = await make_game("active", timedelta(seconds=1))

    user = await create_test_user("wrong_status_user@test.com")
    session.add(GamePlayer(game_id=game.id, user_id=user.id,
                           side="tails", round_number=1, is_eliminated=False))
    await session.flush()

    with pytest.raises(ValueError, match="Showdown is not active yet"):
        await service.set_showdown_decision(user.id, game.id, "continue")


async def test_set_showdown_decision_eliminated_player(session, make_game, create_test_user):
    service = GameService(session)
    game = await make_game("showdown_pending", timedelta(seconds=1))

    user = await create_test_user("eliminated_user@test.com")
    session.add(GamePlayer(game_id=game.id, user_id=user.id,
                           side=None, round_number=1, is_eliminated=True))
    await session.flush()

    with pytest.raises(ValueError, match="Eliminated players cannot make a showdown decision"):
        await service.set_showdown_decision(user.id, game.id, "continue")


async def test_set_showdown_decision_player_not_in_game(session, make_game, create_test_user):
    service = GameService(session)
    game = await make_game("showdown_pending", timedelta(seconds=1))

    # User exists but has no GamePlayer record for this game
    user = await create_test_user("not_in_game@test.com")

    with pytest.raises(ValueError, match="Player not found in this game"):
        await service.set_showdown_decision(user.id, game.id, "continue")

