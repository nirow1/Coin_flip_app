from Game.models import GamePlayer
from Game.service import GameService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_choose_side_success(game_context, test_user, make_game):
    service, wallet, redis = game_context
    game = await make_game("open")

    session = service.session
    session.add(GamePlayer(game_id=game.id, user_id=test_user.id, side=None, round_number=1, is_eliminated=False))
    await session.flush()

    await service.choose_side(test_user.id, game.id, "tails", redis)

    fetch = await service.get_game_player(game.id, test_user.id)
    assert fetch.side == "tails"


async def test_choose_side_invalid_side(game_context, test_user, make_game):
    service, wallet, redis = game_context
    game = await make_game("open")

    service.session.add(GamePlayer(game_id=game.id, user_id=test_user.id, side=None, round_number=1, is_eliminated=False))
    await service.session.flush()

    with pytest.raises(ValueError, match="Side must be 'heads' or 'tails"):
        await service.choose_side(test_user.id, game.id, "side", redis)


async def test_choose_side_invalid_game_status(game_context, test_user, make_game):
    service, wallet, redis = game_context
    game = await make_game("finished")

    service.session.add(GamePlayer(game_id=game.id, user_id=test_user.id, side=None, round_number=1, is_eliminated=False))
    await service.session.flush()

    with pytest.raises(ValueError, match="Cannot choose side in this game state"):
        await service.choose_side(test_user.id, game.id, "tails", redis)


async def test_choose_side_player_eliminated(game_context, test_user, make_game):
    service, wallet, redis = game_context
    game = await make_game("open")

    service.session.add(GamePlayer(game_id=game.id, user_id=test_user.id, side=None, round_number=1, is_eliminated=True))
    await service.session.flush()

    with pytest.raises(ValueError, match="Eliminated players cannot choose a side"):
        await service.choose_side(test_user.id, game.id, "tails", redis)


async def test_choose_side_player_have_already_chosen(game_context, test_user, make_game):
    service, wallet, redis = game_context
    game = await make_game("open")

    # is_eliminated=False so the already-chosen check is reached first
    service.session.add(GamePlayer(game_id=game.id, user_id=test_user.id, side="tails", round_number=1, is_eliminated=False))
    await service.session.flush()

    with pytest.raises(ValueError, match="Player has already chosen side"):
        await service.choose_side(test_user.id, game.id, "heads", redis)


async def test_choose_side_redis_percentage(game_context, make_game, create_test_user):
    service, wallet, redis = game_context
    game = await make_game("open")

    players = []
    for i in range(5):
        user = await create_test_user(f"percentage_user{i}@test.com")
        player = GamePlayer(game_id=game.id, user_id=user.id, side=None, round_number=1, is_eliminated=False)
        service.session.add(player)
        players.append(player)
    await service.session.flush()

    result = None
    for i, player in enumerate(players):
        result = await service.choose_side(player.user_id, game.id, "heads" if i % 2 == 0 else "tails", redis)

    # i=0,2,4 → heads (3), i=1,3 → tails (2) → heads: 60%, tails: 40%
    assert result == {"heads": 60.0, "tails": 40.0}
