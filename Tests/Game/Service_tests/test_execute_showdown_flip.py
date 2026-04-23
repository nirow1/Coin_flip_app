import pytest
from decimal import Decimal
from unittest.mock import patch
from Game.models import GamePlayer
from Game.service import GameService

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_execute_showdown_flip_success(game_context, make_game, create_test_user, mock_leaderboard):
    service, wallet, redis = game_context
    game = await make_game("showdown_active")

    for i in range(100):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "heads" if i % 2 == 0 else "tails"
        service.session.add(GamePlayer(user_id=user.id, game_id=game.id, side=side,
                               cashout_decision="continue", is_eliminated=False))

    await service.session.flush()

    game_after_flip = await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)

    assert game_after_flip.status == "showdown_active"

    players = await service.get_all_players(game.id)
    eliminated = [p for p in players if p.is_eliminated]
    assert len(eliminated) == 50


async def test_execute_showdown_flip_winner(game_context, test_user, test_wallet, make_game, create_test_user, mock_leaderboard):
    service, wallet, redis = game_context
    game = await make_game("showdown_active")

    game.prize_pool = Decimal("101.00")
    await service.session.flush()

    service.session.add(GamePlayer(user_id=test_user.id, game_id=game.id, side="tails", cashout_decision="continue", is_eliminated=False))

    for i in range(100):
        user = await create_test_user(f"test_user{i}@test.com")
        service.session.add(GamePlayer(user_id=user.id, game_id=game.id, side="heads", cashout_decision="continue", is_eliminated=False))

    await service.session.flush()

    balance_before = (await wallet.get_wallet(test_user.id)).balance

    with patch.object(GameService, "_flip_coin", return_value="tails"):
        game_after_flip = await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)

    assert game_after_flip.status == "finished"

    balance_after = (await wallet.get_wallet(test_user.id)).balance
    assert balance_after == balance_before + Decimal("101.00")


async def test_execute_showdown_flip_not_showdown_active(game_context, make_game, mock_leaderboard):
    service, wallet, redis = game_context
    game = await make_game("active")

    with pytest.raises(ValueError, match="Showdown is not active"):
        await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)


async def test_execute_showdown_flip_winner_all_choose_one_side(game_context, make_game, create_test_user, mock_leaderboard):
    service, wallet, redis = game_context
    game = await make_game("showdown_active")

    for i in range(10):
        user = await create_test_user(f"test_user{i}@test.com")
        service.session.add(GamePlayer(user_id=user.id, game_id=game.id, side="heads", cashout_decision="continue", is_eliminated=False))

    await service.session.flush()

    game_after_flip = await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)
    assert game_after_flip.status == "showdown_active"

    players = await service.get_all_players(game.id)
    assert len(players) == 10
    assert all(p.side is None for p in players)


async def test_execute_showdown_flip_invalid_flip_explicitly(game_context, make_game, create_test_user, mock_leaderboard):
    """When no player chose the winning side (invalid flip), nobody is eliminated and all sides reset to None."""
    service, wallet, redis = game_context
    game = await make_game("showdown_active")

    for i in range(5):
        user = await create_test_user(f"invalid_flip_user{i}@test.com")
        service.session.add(GamePlayer(user_id=user.id, game_id=game.id, side="heads",
                               cashout_decision="continue", is_eliminated=False))

    await service.session.flush()

    with patch.object(GameService, "_flip_coin", return_value="tails"):
        result = await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)

    assert result.status == "showdown_active"

    players = await service.get_all_players(game.id)
    assert len(players) == 5
    assert all(not p.is_eliminated for p in players)
    assert all(p.side is None for p in players)  # sides must be reset after invalid flip


async def test_execute_showdown_flip_no_side_gets_random_assignment(game_context, make_game, create_test_user, mock_leaderboard):
    """Players with side=None must receive a random side before the flip is evaluated."""
    service, wallet, redis = game_context
    game = await make_game("showdown_active")

    for i in range(2):
        user = await create_test_user(f"noside_user{i}@test.com")
        service.session.add(GamePlayer(user_id=user.id, game_id=game.id, side=None,
                               cashout_decision="continue", is_eliminated=False))

    await service.session.flush()

    # First two _flip_coin calls assign sides (heads, tails), third call determines winning side (heads)
    # → user0 gets "heads" (survives), user1 gets "tails" (eliminated)
    with patch.object(GameService, "_flip_coin", side_effect=["heads", "tails", "heads"]):
        result = await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)

    players = await service.get_all_players(game.id)
    eliminated = [p for p in players if p.is_eliminated]
    survivors = [p for p in players if not p.is_eliminated]

    assert len(eliminated) == 1
    assert len(survivors) == 1
    # Winner's side is reset to None by _apply_eliminations
    assert survivors[0].side is None


async def test_execute_showdown_flip_round_number_increments(game_context, make_game, create_test_user, mock_leaderboard):
    """Round number must increment by 1 for every player on each flip, including invalid flips."""
    service, wallet, redis = game_context
    game = await make_game("showdown_active")

    for i in range(4):
        user = await create_test_user(f"round_user{i}@test.com")
        service.session.add(GamePlayer(user_id=user.id, game_id=game.id, side="heads",
                               round_number=3, cashout_decision="continue", is_eliminated=False))

    await service.session.flush()

    # Invalid flip (everyone on heads, coin is tails) — round still counts
    with patch.object(GameService, "_flip_coin", return_value="tails"):
        await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)

    players = await service.get_all_players(game.id)
    assert all(p.round_number == 4 for p in players)


async def test_execute_showdown_flip_invalid_flip_then_valid_flip(game_context, make_game, create_test_user, mock_leaderboard):
    """After an invalid flip resets sides, players with no new choice get fresh random sides next round."""
    service, wallet, redis = game_context
    game = await make_game("showdown_active")

    for i in range(4):
        user = await create_test_user(f"double_round_user{i}@test.com")
        service.session.add(GamePlayer(user_id=user.id, game_id=game.id, side="heads",
                               cashout_decision="continue", is_eliminated=False))

    await service.session.flush()

    # Round 1: invalid flip — all sides reset to None
    with patch.object(GameService, "_flip_coin", return_value="tails"):
        await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)

    players_after_invalid = await service._get_players_for_game(game.id)
    assert all(p.side is None for p in players_after_invalid), \
        "Sides must be None after invalid flip so next round assigns fresh random sides"

    # Round 2: nobody chose a side → all get random assignment then a real flip
    # sides: heads, tails, heads, tails → winning side: heads → 2 survive
    with patch.object(GameService, "_flip_coin", side_effect=["heads", "tails", "heads", "tails", "heads"]):
        result = await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)

    assert result.status == "showdown_active"
    all_players = await service.get_all_players(game.id)
    eliminated = [p for p in all_players if p.is_eliminated]
    assert len(eliminated) == 2


async def test_execute_showdown_flip_reddis_key_made(game_context, make_game, create_test_user, mock_leaderboard):
    service, wallet, redis = game_context
    game = await make_game("showdown_active")

    for i in range(100):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "heads" if i % 2 == 0 else "tails"
        service.session.add(GamePlayer(user_id=user.id, game_id=game.id, side=side,
                               cashout_decision="continue", is_eliminated=False))

    await service.session.flush()

    with patch.object(GameService, "_flip_coin", return_value="heads"):
        await service.execute_showdown_flip(game.id, wallet, mock_leaderboard, redis)

    keys = await redis.keys("showdown_flip:*")
    assert len(keys) == 1
    assert keys[0].startswith(f"showdown_flip:{game.id}:2")

