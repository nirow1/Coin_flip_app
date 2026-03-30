import pytest
from Game.models import GamePlayer
from Core.security import create_access_token

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_choose_side_success(client, create_test_user, open_game, session):
    # Use a fresh user — auth_user may already be in open_game from test_join_game_success
    user = await create_test_user("choose_side_user@test.com")

    session.add(GamePlayer(
        user_id=user.id,
        game_id=open_game.id,
        side=None,
        is_eliminated=False
    ))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/choose",
        params={"side": "heads", "game_id": open_game.id},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["heads"] == 100.0
    assert body["tails"] == 0.0

async def test_choose_side_invalid_side(client, create_test_user, open_game, session):
    user = await create_test_user("invalid_side_user@test.com")  # FIX: unique email

    session.add(GamePlayer(
        user_id=user.id,
        game_id=open_game.id,
        side=None,
        is_eliminated=False
    ))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/choose",
        params={"side": "invalid", "game_id": open_game.id},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400

async def test_choose_side_player_not_in_game(client, create_test_user, make_game):
    user = await create_test_user("not_in_game_user@test.com")  # FIX: unique email
    game = await make_game("open")  # FIX: open state so choose_side is allowed

    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/choose",
        params={"side": "heads", "game_id": game.id},  # FIX: valid side so _validate_side passes
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400

async def test_choose_side_eliminated(client, create_test_user, open_game, session):
    user = await create_test_user("eliminated_user@test.com")  # FIX: unique email

    session.add(GamePlayer(
        user_id=user.id,
        game_id=open_game.id,
        side=None,
        is_eliminated=True
    ))
    await session.flush()

    token = create_access_token({"sub": str(user.id)})

    response = await client.post(
        "/game/choose",
        params={"side": "heads", "game_id": open_game.id},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
