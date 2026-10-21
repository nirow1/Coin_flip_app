import pytest
import asyncio
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock, patch, call
from Backend.Tests.Game_engine.conftest import make_engine_with_mocks, make_mock_sleep, create_game

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _configure_service(mock_service):
    mock_service.get_showdown_active_games = AsyncMock(return_value=[])
    mock_service.showdown_timer_key = AsyncMock(return_value=None)
    mock_service.ensure_open_game = AsyncMock()
    return mock_service


def _patch_scheduler(mock_service, mock_wallet, mock_leaderboard, stop_at=1):
    """GameService + per-tick Wallet/LeaderBoard used inside each scheduler tick.

    stop_at=1: cancel after the first 60s sleep so each test covers one tick.
    """
    return (
        patch("Backend.Game.engine.GameService", return_value=mock_service),
        patch("Backend.Game.engine.WalletService", return_value=mock_wallet),
        patch("Backend.Game.engine.LeaderBoardService", return_value=mock_leaderboard),
        patch("asyncio.sleep", side_effect=make_mock_sleep(stop_at=stop_at)),
    )


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_a_scheduler_triggers_at_19_utc():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()
    mock_service.get_active_games = AsyncMock(return_value=[])

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.ensure_open_game.assert_awaited_once_with(mock_wallet)
    engine.redis_client.set.assert_any_await("scheduler:last_flip_date", "2025-01-01")


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_b_scheduler_triggers_at_19_utc():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()

    game = MagicMock()
    game.id = 1
    game.status = "active"

    mock_service.get_active_games.return_value = [game]

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.get_active_games.assert_awaited_once()

    mock_service.execute_flip.assert_awaited_once_with(
        game.id,
        mock_wallet,
        mock_leaderboard,
    )

    mock_service.ensure_open_game.assert_awaited_once_with(mock_wallet)

    # One SAVEPOINT per processable game; flip commit + ensure commit
    assert mock_session.begin_nested.call_count == 1
    assert mock_session.commit.await_count == 2


@freeze_time("2025-01-01 15:00:00", tz_offset=0)
async def test_scheduler_ensures_open_game_outside_19_utc():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()
    mock_service.get_active_games = AsyncMock(return_value=[])

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.ensure_open_game.assert_awaited_once_with(mock_wallet)
    mock_service.get_active_games.assert_not_called()
    mock_service.execute_flip.assert_not_called()
    mock_session.begin_nested.assert_not_called()
    mock_session.commit.assert_awaited_once()


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_scheduler_iter_games():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()

    game_1 = create_game(1, "active")
    game_2 = create_game(2, "open")
    game_3 = create_game(3, "finished")

    mock_service.get_active_games.return_value = [game_1, game_2, game_3]

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.get_active_games.assert_awaited_once()

    mock_service.execute_flip.assert_has_awaits([
        call(game_1.id, mock_wallet, mock_leaderboard),
        call(game_2.id, mock_wallet, mock_leaderboard),
    ])

    assert mock_service.execute_flip.await_count == 2
    mock_service.ensure_open_game.assert_awaited_once_with(mock_wallet)

    # begin_nested only for processable games (active + open; not finished)
    assert mock_session.begin_nested.call_count == 2
    assert mock_session.commit.await_count == 2


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_scheduler_showdown_trigger():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()

    game_1 = create_game(1, "showdown_pending")
    timer_key = "showdown_flip:1:1"

    mock_service.get_active_games.return_value = [game_1]
    mock_service.try_start_showdown.return_value = (game_1, timer_key)

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.get_active_games.assert_awaited_once()

    mock_service.try_start_showdown.assert_has_awaits([
        call(game_1.id, mock_wallet, mock_leaderboard),
    ])
    mock_service.ensure_open_game.assert_awaited_once_with(mock_wallet)
    assert mock_session.begin_nested.call_count == 1
    assert mock_session.commit.await_count == 2
    engine.redis_client.set.assert_any_await(timer_key, "1", ex=60)
    engine.redis_client.set.assert_any_await("scheduler:last_flip_date", "2025-01-01")


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_scheduler_game_error_continues_processing():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()

    game_1 = create_game(1, "active")
    game_2 = create_game(2, "active")

    mock_service.get_active_games.return_value = [game_1, game_2]
    mock_service.execute_flip.side_effect = [Exception("DB error"), None]  # game_1 fails

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    # game_2 must still be processed despite game_1 error
    assert mock_service.execute_flip.await_count == 2
    mock_service.ensure_open_game.assert_awaited_once_with(mock_wallet)
    assert mock_session.begin_nested.call_count == 2
    assert mock_session.commit.await_count == 2  # flip commit + ensure commit


@freeze_time("2025-01-01 19:30:00", tz_offset=0)
async def test_scheduler_still_flips_after_19_when_not_yet_marked():
    """Catch-up: a late tick (sleep drift / restart) still flips once per day."""
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()
    game = create_game(1, "active")
    mock_service.get_active_games.return_value = [game]

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.execute_flip.assert_awaited_once()
    engine.redis_client.set.assert_any_await("scheduler:last_flip_date", "2025-01-01")


@freeze_time("2025-01-01 19:05:00", tz_offset=0)
async def test_scheduler_skips_flip_when_already_done_today():
    engine, mock_session, _ = make_engine_with_mocks()
    engine.redis_client.get = AsyncMock(return_value=b"2025-01-01")

    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()
    mock_service.get_active_games = AsyncMock(return_value=[])

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.get_active_games.assert_not_called()
    mock_service.execute_flip.assert_not_called()
    mock_service.ensure_open_game.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_ensure_open_game_failure_keeps_flip_commit():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()

    game = create_game(1, "active")
    mock_service.get_active_games.return_value = [game]
    mock_service.ensure_open_game.side_effect = Exception("ensure failed")

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.execute_flip.assert_awaited_once()
    # Flip session committed even though ensure raised
    assert mock_session.commit.await_count == 1
    engine.redis_client.set.assert_any_await("scheduler:last_flip_date", "2025-01-01")


@freeze_time("2025-01-01 15:00:00", tz_offset=0)
async def test_tick_error_continues_to_next_sleep():
    """Outer tick exception must not kill the while True loop."""
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()

    # Force an exception past the per-step handlers on tick 1 only.
    engine._recover_missing_showdown_timers = AsyncMock(
        side_effect=[Exception("tick boom"), None]
    )

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard, stop_at=2)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    assert engine._recover_missing_showdown_timers.await_count == 2
    # Second tick still ran ensure after the first tick's exception
    assert mock_service.ensure_open_game.await_count == 1


@freeze_time("2025-01-01 15:00:00", tz_offset=0)
async def test_recover_missing_showdown_timer():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()

    game = create_game(7, "showdown_active")
    timer_key = "showdown_flip:7:3"
    mock_service.get_showdown_active_games.return_value = [game]
    mock_service.showdown_timer_key.return_value = timer_key
    engine.redis_client.keys = AsyncMock(return_value=[])

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    engine.redis_client.keys.assert_awaited_once_with("showdown_flip:7:*")
    mock_service.showdown_timer_key.assert_awaited_once_with(7)
    engine.redis_client.set.assert_any_await(timer_key, "1", ex=60)


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_timer_set_failure_does_not_block_siblings():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = _configure_service(AsyncMock())
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()

    g1 = create_game(1, "showdown_pending")
    g2 = create_game(2, "showdown_pending")
    mock_service.get_active_games.return_value = [g1, g2]
    mock_service.try_start_showdown.side_effect = [
        (g1, "showdown_flip:1:1"),
        (g2, "showdown_flip:2:1"),
    ]

    engine.redis_client.set = AsyncMock(
        side_effect=[None, Exception("redis down"), None]
    )
    # Order: last_flip_date set, then timer 1, then timer 2 (timer1 fails)

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    # Both timer keys attempted; ensure still ran after timer failures
    set_keys = [c.args[0] for c in engine.redis_client.set.await_args_list]
    assert "showdown_flip:1:1" in set_keys
    assert "showdown_flip:2:1" in set_keys
    mock_service.ensure_open_game.assert_awaited_once()
