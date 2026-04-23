from Game.models import GamePlayer
from Game.service import GameService
import fakeredis.aioredis as fakeredis
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_choose_side_success(session, test_user, make_game):
    service = GameService(session)
    redis = fakeredis.FakeRedis(decode_responses=True)

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
    await service.choose_side(test_user.id, game.id, "tails", redis)

    # Assert: player's side is updated
    fetch = await service.get_game_player(game.id, test_user.id)
    assert fetch.side == "tails"


async def test_choose_side_invalid_side(session, test_user, make_game):
    ...


async def test_choose_side_redis_percentage(session, test_user, make_game):
    ...

