import pytest

from Backend.Core.security import create_access_token
from Backend.Game.models import GamePlayer

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_get_my_games_live_includes_percentages(client, create_test_user, make_game, session, fake_redis):
    user = await create_test_user("get_my_games_live@test.com")
    game = await make_game("active")

    session.add(GamePlayer(
        user_id=user.id,
        game_id=game.id,
        side="heads",
        round_number=1,
        is_eliminated=False,
    ))
    await session.flush()
    await fake_redis.set(f"game:{game.id}:round:1:heads", "3")
    await fake_redis.set(f"game:{game.id}:round:1:tails", "1")

    token = create_access_token({"sub": str(user.id)})
    response = await client.get("/game/mine", cookies={"access_token": token})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["id"] == game.id
    assert item["outcome"] == "live"
    assert item["heads"] == 75.0
    assert item["tails"] == 25.0
    assert item["is_eliminated"] is False
    assert item["round_number"] == 1


async def test_get_my_games_eliminated_omits_percentages(client, create_test_user, make_game, session, fake_redis):
    user = await create_test_user("get_my_games_elim@test.com")
    game = await make_game("active")

    session.add(GamePlayer(
        user_id=user.id,
        game_id=game.id,
        side="tails",
        round_number=3,
        is_eliminated=True,
        cashout_decision=None,
    ))
    await session.flush()
    await fake_redis.set(f"game:{game.id}:round:3:heads", "4")
    await fake_redis.set(f"game:{game.id}:round:3:tails", "1")

    token = create_access_token({"sub": str(user.id)})
    response = await client.get("/game/mine", cookies={"access_token": token})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["outcome"] == "eliminated"
    assert item["round_number"] == 3
    assert item["is_eliminated"] is True
    assert item["heads"] is None
    assert item["tails"] is None


async def test_get_my_games_won_after_cashout(client, create_test_user, make_game, session, fake_redis):
    user = await create_test_user("get_my_games_won@test.com")
    game = await make_game("finished")

    session.add(GamePlayer(
        user_id=user.id,
        game_id=game.id,
        side=None,
        round_number=2,
        is_eliminated=True,
        cashout_decision="cashout",
    ))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})
    response = await client.get("/game/mine", cookies={"access_token": token})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["outcome"] == "won"
    assert item["cashout_decision"] == "cashout"
    assert item["is_eliminated"] is True
    assert item["heads"] is None
    assert item["tails"] is None


async def test_get_my_games_canceled_is_ended(client, create_test_user, make_game, session, fake_redis):
    user = await create_test_user("get_my_games_ended@test.com")
    game = await make_game("canceled")

    session.add(GamePlayer(
        user_id=user.id,
        game_id=game.id,
        side="heads",
        round_number=1,
        is_eliminated=False,
        cashout_decision=None,
    ))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})
    response = await client.get("/game/mine", cookies={"access_token": token})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["outcome"] == "ended"
    assert item["status"] == "canceled"
    assert item["heads"] is None
    assert item["tails"] is None


async def test_get_my_games_missing_auth(client):
    response = await client.get("/game/mine")
    assert response.status_code == 401


async def test_get_my_games_empty_when_user_has_no_seats(client, create_test_user, fake_redis):
    user = await create_test_user("get_my_games_empty@test.com")
    token = create_access_token({"sub": str(user.id)})

    response = await client.get("/game/mine", cookies={"access_token": token})

    assert response.status_code == 200
    assert response.json() == []
