from decimal import Decimal

import fakeredis.aioredis as fakeredis
import pytest

from Backend.Game.models import GamePlayer
from Backend.Game.service import GameService

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_percentages(redis, game_id: int, round_number: int, heads: int, tails: int) -> None:
    await redis.set(f"game:{game_id}:round:{round_number}:heads", str(heads))
    await redis.set(f"game:{game_id}:round:{round_number}:tails", str(tails))


async def test_get_players_games_live_includes_percentages(session, make_game, create_test_user):
    service = GameService(session)
    redis = fakeredis.FakeRedis(decode_responses=True)
    user = await create_test_user("get_players_games_live@test.com")
    game = await make_game("active")

    session.add(GamePlayer(
        game_id=game.id,
        user_id=user.id,
        side="heads",
        round_number=1,
        is_eliminated=False,
    ))
    await session.flush()
    await _seed_percentages(redis, game.id, 1, heads=3, tails=1)

    items = await service.get_players_games(user.id, redis)

    assert len(items) == 1
    item = items[0]
    assert item.id == game.id
    assert item.outcome == "live"
    assert item.heads == 75.0
    assert item.tails == 25.0
    assert item.is_eliminated is False
    assert item.round_number == 1


async def test_get_players_games_eliminated_omits_percentages(session, make_game, create_test_user):
    service = GameService(session)
    redis = fakeredis.FakeRedis(decode_responses=True)
    user = await create_test_user("get_players_games_elim@test.com")
    game = await make_game("active")

    session.add(GamePlayer(
        game_id=game.id,
        user_id=user.id,
        side="tails",
        round_number=3,
        is_eliminated=True,
        cashout_decision=None,
    ))
    await session.flush()
    await _seed_percentages(redis, game.id, 3, heads=4, tails=1)

    items = await service.get_players_games(user.id, redis)

    assert len(items) == 1
    item = items[0]
    assert item.outcome == "eliminated"
    assert item.round_number == 3
    assert item.is_eliminated is True
    assert item.heads is None
    assert item.tails is None


async def test_get_players_games_won_via_cashout(session, make_game, create_test_user, mock_wallet, mock_leaderboard):
    service = GameService(session)
    redis = fakeredis.FakeRedis(decode_responses=True)
    user = await create_test_user("get_players_games_won@test.com")
    game = await make_game("finished")
    game.prize_pool = Decimal("10.00")

    player = GamePlayer(
        game_id=game.id,
        user_id=user.id,
        side=None,
        round_number=2,
        is_eliminated=False,
        cashout_decision=None,
    )
    session.add(player)
    await session.flush()

    await service._cashout(player, game, Decimal("10.00"), mock_wallet, mock_leaderboard)

    items = await service.get_players_games(user.id, redis)

    assert player.cashout_decision == "cashout"
    assert len(items) == 1
    item = items[0]
    assert item.outcome == "won"
    assert item.cashout_decision == "cashout"
    assert item.is_eliminated is True
    assert item.heads is None
    assert item.tails is None
    mock_wallet.credit.assert_awaited_once()


async def test_get_players_games_canceled_is_ended(session, make_game, create_test_user):
    service = GameService(session)
    redis = fakeredis.FakeRedis(decode_responses=True)
    user = await create_test_user("get_players_games_ended@test.com")
    game = await make_game("canceled")

    session.add(GamePlayer(
        game_id=game.id,
        user_id=user.id,
        side="heads",
        round_number=1,
        is_eliminated=False,
        cashout_decision=None,
    ))
    await session.flush()

    items = await service.get_players_games(user.id, redis)

    assert len(items) == 1
    item = items[0]
    assert item.outcome == "ended"
    assert item.status == "canceled"
    assert item.heads is None
    assert item.tails is None


async def test_get_players_games_empty_when_user_has_no_seats(session, create_test_user):
    service = GameService(session)
    redis = fakeredis.FakeRedis(decode_responses=True)
    user = await create_test_user("get_players_games_empty@test.com")

    items = await service.get_players_games(user.id, redis)

    assert items == []
