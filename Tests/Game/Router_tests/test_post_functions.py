import pytest
from Core.security import create_access_token
from Game.models import GamePlayer

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_get_current_games_success(client, create_test_user, make_game, session):
    user = await create_test_user("get_current_games_success@test.com")
    game = await make_game("open")
    game_2 = await make_game("active")
    game_eliminated = await make_game("open")  # user is eliminated here → must NOT appear

    session.add(GamePlayer(
        user_id=user.id,
        game_id=game.id,
        side=None,
        is_eliminated=False
    ))
    session.add(GamePlayer(
        user_id=user.id,
        game_id=game_2.id,
        side=None,
        is_eliminated=False
    ))
    session.add(GamePlayer(
        user_id=user.id,
        game_id=game_eliminated.id,
        side=None,
        is_eliminated=True   # eliminated → must NOT appear
    ))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})

    response = await client.get(
        "/game/current",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    returned_ids = {g["id"] for g in body}
    assert len(body) == 2
    assert game.id in returned_ids
    assert game_2.id in returned_ids
    assert game_eliminated.id not in returned_ids  

async def test_get_game_state_success(client, make_game):
    game = await make_game("open")
    game_2 = await make_game("active")

    response = await client.get(f"/game/{game.id}/state")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "open"

    response = await client.get(f"/game/{game_2.id}/state")  # FIX: GET + /game/ prefix
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "active"
    
async def test_get_game_player_success(client, create_test_user, make_game, session):
    user = await create_test_user("get_gameplayer@test.cz")
    game = await make_game("open")

    session.add(GamePlayer(
        user_id=user.id,
        game_id=game.id,
        side=None,
        is_eliminated=False
    ))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})

    response = await client.get(
        f"/game/{game.id}/player",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == user.id
    assert body["game_id"] == game.id       # verify correct game
    assert body["is_eliminated"] == False   # verify player state
    assert body["side"] is None             # no side chosen yet
    assert body["round_number"] == 1        # default value


async def test_get_all_games(client, create_test_admin, make_game):  # FIX: removed unused session
    game = await make_game("open")
    game_2 = await make_game("active")
    game_3 = await make_game("finished")

    # FIX: create_test_admin is a direct fixture, not a factory — no () needed
    token = create_test_admin["token"]

    response = await client.get(
        "/game/admin/games",  # FIX: leading / + correct prefix
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()

    returned = {g["id"]: g["status"] for g in body}
    assert game.id in returned
    assert game_2.id in returned
    assert game_3.id in returned
    assert returned[game.id] == "open"
    assert returned[game_2.id] == "active"
    assert returned[game_3.id] == "finished"

