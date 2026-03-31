import pytest
from Core.security import create_access_token
from Game.models import GamePlayer

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_cashout_decision_success(client, create_test_user, make_game, session):
    user = await create_test_user("cashout_decision_success@test.com")  # FIX: unique email
    game = await make_game("showdown_pending")

    session.add(GamePlayer(user_id=user.id, game_id=game.id, side=None, is_eliminated=False))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/showdown/decision",
        params={"decision": "cashout", "game_id": game.id},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Cashout decision recorded successfully"


async def test_cashout_decision_invalid_decision(client, create_test_user, make_game, session):
    user = await create_test_user("cashout_decision_invalid@test.com")  # FIX: unique email
    game = await make_game("showdown_pending")

    session.add(GamePlayer(user_id=user.id, game_id=game.id, side=None, is_eliminated=False))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/showdown/decision",
        params={"decision": "invalid", "game_id": game.id},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert "Decision must be" in response.json()["detail"]  # FIX: actual error message


async def test_cashout_decision_not_in_showdown(client, create_test_user, make_game, session):
    user = await create_test_user("cashout_decision_not_pending@test.com")  # FIX: unique email
    game = await make_game("active")

    session.add(GamePlayer(user_id=user.id, game_id=game.id, side=None, is_eliminated=False))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/showdown/decision",
        params={"decision": "cashout", "game_id": game.id},  # FIX: valid decision so check 2 is reached
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert "Showdown is not active yet" in response.json()["detail"]  # FIX: actual error message


async def test_cashout_decision_player_not_in_game(client, create_test_user, make_game):
    user = await create_test_user("cashout_decision_not_in_game@test.com")  # FIX: unique email
    game = await make_game("showdown_pending")

    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/showdown/decision",
        params={"decision": "cashout", "game_id": game.id},  # FIX: valid decision so check 3 is reached
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert "Player not found" in response.json()["detail"]  # FIX: actual error message


async def test_cashout_decision_player_eliminated(client, create_test_user, make_game, session):
    user = await create_test_user("cashout_decision_eliminated@test.com")  # FIX: unique email
    game = await make_game("showdown_pending")

    session.add(GamePlayer(user_id=user.id, game_id=game.id, side=None, is_eliminated=True))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/showdown/decision",
        params={"decision": "cashout", "game_id": game.id},  # FIX: valid decision so check 4 is reached
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert "Eliminated" in response.json()["detail"]  # FIX: actual error message


# ─── Missing scenarios ────────────────────────────────────────────────────────

async def test_cashout_decision_missing_auth(client, make_game):
    game = await make_game("showdown_pending")

    response = await client.post(
        "/game/showdown/decision",
        params={"decision": "cashout", "game_id": game.id}
    )

    assert response.status_code == 401


async def test_cashout_decision_invalid_token(client, make_game):
    game = await make_game("showdown_pending")

    response = await client.post(
        "/game/showdown/decision",
        params={"decision": "cashout", "game_id": game.id},
        headers={"Authorization": "Bearer invalid"}
    )

    assert response.status_code == 401


async def test_cashout_decision_missing_params(client, create_test_user):
    user = await create_test_user("cashout_decision_missing_params@test.com")
    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/showdown/decision",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422

