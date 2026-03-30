import pytest
from datetime import timedelta

pytestmark = pytest.mark.asyncio(loop_scope="session")

async def test_join_game_success(client, auth_user, open_game):
    token = auth_user["token"]

    response = await client.post(
        "/game/join",
        params={"side": "heads"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200

async def test_join_game_missing_auth(client):
    response = await client.post("/game/join",
                                 params={"side": "heads"})
    assert response.status_code == 401

async def test_join_game_invalid_token(client):
    response = await client.post("/game/join",
                                 params={"side": "heads"},
                                 headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 401
    
async def test_join_game_missing_side(client, auth_user):
    token = auth_user["token"]
    response = await client.post("/game/join",
                                 headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 422

async def test_join_game_invalid_side(client, auth_user):
    token = auth_user["token"]
    response = await client.post("/game/join",
                                 params={"side": "invalid"},
                                 headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400

async def test_join_game_already_joined(client, create_funded_user, open_game):
    # Use a fresh user — auth_user may already be in open_game from test_join_game_success
    user = await create_funded_user("already_joined_router@test.com")
    token = user["token"]

    response = await client.post("/game/join",
                                 params={"side": "heads"},
                                 headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    response = await client.post("/game/join",
                                 params={"side": "heads"},
                                 headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400

async def test_join_game_insufficient_balance(client, broke_auth_user, open_game):
    token = broke_auth_user["token"]

    response = await client.post("/game/join",
                                 params={"side": "heads"},
                                 headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400

async def test_join_game_lockout(client, create_funded_user, make_game):
    # make_game with 3-minute offset → flip in 3 min → inside the 5-minute lockout window
    # get_open_game orders by flip_time ASC so this game (soonest flip) is returned first
    await make_game("open", flip_time_offset=timedelta(minutes=3))
    user = await create_funded_user("lockout_router@test.com")
    token = user["token"]

    response = await client.post("/game/join",
                                 params={"side": "heads"},
                                 headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400
    assert "5 minutes" in response.json()["detail"]
