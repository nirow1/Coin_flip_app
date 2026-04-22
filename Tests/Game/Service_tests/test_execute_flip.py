from datetime import timedelta
from unittest.mock import patch
from Game.models import GamePlayer
from Game.service import GameService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_execute_flip_finished(session, make_game, create_test_user, mock_wallet, mock_leaderboard):
    service = GameService(session)
    game = await make_game("active", timedelta(seconds=1))

    user1 = await create_test_user("testuser1@test.com")
    user2 = await create_test_user("testuser2@test.com")

    # Add two players on opposite sides so one always gets eliminated
    session.add(GamePlayer(game_id=game.id, user_id=user1.id,
                           side="heads", round_number=1, is_eliminated=False))
    session.add(GamePlayer(game_id=game.id, user_id=user2.id,
                           side="tails", round_number=1, is_eliminated=False))
    await session.flush()

    game_after_flip = await service.execute_flip(game.id, mock_wallet, mock_leaderboard)

    # Game should be finished — 2 players, opposite sides, exactly 1 survivor
    assert game_after_flip.status == "finished"

    p1 = await service.get_game_player(game.id, user1.id)
    p2 = await service.get_game_player(game.id, user2.id)

    survivors = [p for p in [p1, p2] if not p.is_eliminated]
    eliminated = [p for p in [p1, p2] if p.is_eliminated]

    assert len(survivors) == 1
    assert len(eliminated) == 1
    assert eliminated[0].eliminated_at is not None


async def test_execute_flip_mixed_choices(session, make_game, create_test_user, mock_wallet, mock_leaderboard):
    service = GameService(session)
    game = await make_game("active", timedelta(seconds=1))

    # 5 tails, 5 heads — equal split guarantees exactly 5 eliminated regardless of flip result
    for i in range(10):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "tails" if i < 5 else "heads"
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=side, round_number=1, is_eliminated=False))
    await session.flush()

    game_after_flip = await service.execute_flip(game.id, mock_wallet, mock_leaderboard)

    # 5 survivors out of 10 → 5/10 = 0.5 > 0.05 threshold → status stays active
    assert game_after_flip.status == "active"

    players = await service.get_all_players(game.id)
    eliminated = [p for p in players if p.is_eliminated]
    assert len(eliminated) == 5


async def test_execute_flip_showdown_trigger(session, make_game, create_test_user, mock_wallet, mock_leaderboard):
    service = GameService(session)
    game = await make_game("active", timedelta(seconds=1))

    # 96 tails, 4 heads — if heads wins, 4 survivors remain (4% ≤ 5% threshold)
    for i in range(100):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "tails" if i < 96 else "heads"
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=side, round_number=1, is_eliminated=False))
    await session.flush()

    # Force flip to "heads" — eliminates 96 tails players, 4 survive → showdown triggered
    with patch.object(GameService, "_flip_coin", return_value="heads"):
        game_after_flip = await service.execute_flip(game.id, mock_wallet, mock_leaderboard)

    assert game_after_flip.status == "showdown_pending"


async def test_execute_flip_auto_assign(session, make_game, create_test_user, mock_wallet, mock_leaderboard):
    service = GameService(session)
    game = await make_game("active", timedelta(seconds=1))

    # 7 players chose "tails", 3 players have no side — auto-assign will pick for them
    for i in range(10):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "tails" if i < 7 else None
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=side, round_number=1, is_eliminated=False))
    await session.flush()

    # First 3 calls: auto-assign "heads" to the 3 None players
    # 4th call: actual flip returns "tails" → tails players survive, heads players eliminated
    with patch.object(GameService, "_flip_coin", side_effect=["heads", "heads", "heads", "tails"]):
        game_after_flip = await service.execute_flip(game.id, mock_wallet, mock_leaderboard)

    players = await service.get_all_players(game.id)
    eliminated = [p for p in players if p.is_eliminated]
    survivors = [p for p in players if not p.is_eliminated]

    # Auto-assign: 3 None players were assigned "heads" and lost the flip
    assert len(eliminated) == 3
    assert all(p.side == "heads" for p in eliminated)

    # Side reset: all survivors have side reset to None for next round
    assert len(survivors) == 7
    assert all(p.side is None for p in survivors)


async def test_execute_flip_all_one_side(session, make_game, create_test_user, mock_wallet, mock_leaderboard):
    service = GameService(session)
    game = await make_game("active", timedelta(seconds=1))

    # All 10 players on the same side — showdown triggers immediately
    for i in range(10):
        user = await create_test_user(f"test_user{i}@test.com")
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side="tails", round_number=1, is_eliminated=False))
    await session.flush()

    game_after_flip = await service.execute_flip(game.id, mock_wallet, mock_leaderboard)

    assert game_after_flip.status == "showdown_pending"

