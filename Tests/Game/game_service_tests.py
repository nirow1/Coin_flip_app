from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from fastapi import HTTPException
from Game.models import GamePlayer
from Wallet.services import WalletService
from Game.services import GameService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

async def test_join_game_success(session, test_user, open_game, test_wallet):
    service = GameService(session)
    wallet = WalletService(session)

    await wallet.credit(test_user.id, Decimal("50.00"))

    player = await service.join_game(test_user.id, "heads", wallet)

    fetch = await service.get_game_player(player.game_id, player.user_id)
    # assert: player exists in game_players
    assert fetch is not None

    # assert: game player state
    assert fetch.user_id == test_user.id
    assert fetch.side == "heads"
    assert fetch.is_eliminated == False

    # assert: wallet balance decreased
    players_wallet = await wallet.get_wallet(test_user.id)
    assert players_wallet.balance == Decimal("49.00")
    
async def test_join_game_fail(session, test_user, open_game, test_wallet):
    service = GameService(session)
    wallet = WalletService(session)

    # Fail 1: insufficient funds — wallet has 0.00 balance, debit of 1.00 is rejected
    with pytest.raises(HTTPException) as exc_info:
        await service.join_game(test_user.id, "heads", wallet)
    assert exc_info.value.status_code == 400

    # Fail 2: player already joined — credit wallet, join once, then try again
    await wallet.credit(test_user.id, Decimal("50.00"))
    await service.join_game(test_user.id, "heads", wallet)

    with pytest.raises(ValueError, match="Player is already in this game"):
        await service.join_game(test_user.id, "heads", wallet)

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
        player = GamePlayer(
            game_id=game.id,
            user_id=test_user.id,
            side="heads",
            round_number=1,
            is_eliminated=False,
        )
        session.add(player)
    await session.flush()

    joined_games = await service.get_players_active_games(test_user.id)

    game_ids = {g.id for g in joined_games}
    assert game_ids == {games[0].id, games[1].id}

async def test_execute_flip_finished(session, make_game, create_test_user):
    service = GameService(session)
    game = await make_game("active", timedelta(seconds=1))

    # create_test_user flushes and commits internally — user.id is set, session.add not needed
    user1 = await create_test_user("testuser1@test.com")
    user2 = await create_test_user("testuser2@test.com")

    # Add two players on opposite sides so one always gets eliminated
    session.add(GamePlayer(game_id=game.id, user_id=user1.id,
                           side="heads", round_number=1, is_eliminated=False))
    session.add(GamePlayer(game_id=game.id, user_id=user2.id,
                           side="tails", round_number=1, is_eliminated=False))
    await session.flush()

    game_after_flip = await service.execute_flip(game.id)

    # Game should be finished — 2 players, opposite sides, exactly 1 survivor
    assert game_after_flip.status == "finished"

    # Exactly one player eliminated, one survivor
    p1 = await service.get_game_player(game.id, user1.id)
    p2 = await service.get_game_player(game.id, user2.id)

    survivors = [p for p in [p1, p2] if not p.is_eliminated]
    eliminated = [p for p in [p1, p2] if p.is_eliminated]

    assert len(survivors) == 1
    assert len(eliminated) == 1
    assert eliminated[0].eliminated_at is not None
    
async def test_execute_flip_mixed_choices(session, make_game, create_test_user):
    service = GameService(session)
    game = await make_game("active", timedelta(seconds=1))

    # 5 tails, 5 heads — equal split guarantees exactly 5 eliminated regardless of flip result
    for i in range(10):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "tails" if i < 5 else "heads"
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=side, round_number=1, is_eliminated=False))

    await session.flush()

    game_after_flip = await service.execute_flip(game.id)

    # 5 survivors out of 10 → 5/10 = 0.5 > 0.05 threshold → status stays active
    assert game_after_flip.status == "active"

    players = await service.get_all_players(game.id)

    eliminated = [p for p in players if p.is_eliminated]

    assert len(eliminated) == 5

async def test_execute_flip_showdown_trigger(session, make_game, create_test_user):
    service = GameService(session)
    game = await make_game("active", timedelta(seconds=1))

    # 5 tails, 5 heads — equal split guarantees exactly 5 eliminated regardless of flip result
    for i in range(100):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "tails" if i < 96 else "heads"
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=side, round_number=1, is_eliminated=False))

    await session.flush()

    with patch.object(GameService, "_flip_coin", return_value="heads"):
        game_after_flip = await service.execute_flip(game.id)

    assert game_after_flip.status == "showdown_pending"

async def test_execute_flip_auto_assign(session, make_game, create_test_user):
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
        game_after_flip = await service.execute_flip(game.id)

    players = await service.get_all_players(game.id)
    eliminated = [p for p in players if p.is_eliminated]
    survivors = [p for p in players if not p.is_eliminated]

    # Auto-assign: 3 None players were assigned "heads" and lost the flip
    assert len(eliminated) == 3
    assert all(p.side == "heads" for p in eliminated)

    # Side reset: all survivors have side reset to None for next round
    assert len(survivors) == 7
    assert all(p.side is None for p in survivors)

async def test_execute_flip_all_one_side(session, make_game, create_test_user):
    service = GameService(session)
    game = await make_game("active", timedelta(seconds=1))

    for i in range(10):
        user = await create_test_user(f"test_user{i}@test.com")
        side = "tails"
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=side, round_number=1, is_eliminated=False))
    await session.flush()
    
    game_after_flip = await service.execute_flip(game.id)
    
    assert game_after_flip.status == "showdown_pending"
