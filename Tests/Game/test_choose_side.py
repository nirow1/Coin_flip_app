from Game.models import GamePlayer
from Game.services import GameService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


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


async def test_get_players_active_games(session, test_user, make_game):
    service = GameService(session)

    games = [await make_game("active"), await make_game("active")]

    for game in games:
        session.add(GamePlayer(
            game_id=game.id,
            user_id=test_user.id,
            side="heads",
            round_number=1,
            is_eliminated=False,
        ))
    await session.flush()

    joined_games = await service.get_players_active_games(test_user.id)

    game_ids = {g.id for g in joined_games}
    assert game_ids == {games[0].id, games[1].id}

