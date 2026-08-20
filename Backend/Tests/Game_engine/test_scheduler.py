import pytest
import asyncio
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock, patch, call
from Backend.Tests.Game_engine.conftest import make_engine_with_mocks, make_mock_sleep, create_game

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _patch_scheduler(mock_service, mock_wallet, mock_leaderboard):
    """GameService + per-tick Wallet/LeaderBoard used inside each scheduler tick.

    stop_at=1: cancel after the first 60s sleep so each test covers one tick.
    """
    return (
        patch("Backend.Game.engine.GameService", return_value=mock_service),
        patch("Backend.Game.engine.WalletService", return_value=mock_wallet),
        patch("Backend.Game.engine.LeaderBoardService", return_value=mock_leaderboard),
        patch("asyncio.sleep", side_effect=make_mock_sleep(stop_at=1)),
    )


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_a_scheduler_triggers_at_19_utc():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()
    mock_service.get_active_games = AsyncMock(return_value=[])
    mock_service.ensure_open_game = AsyncMock()

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.ensure_open_game.assert_awaited_once_with(mock_wallet)


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_b_scheduler_triggers_at_19_utc():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()
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

    # DB commit
    mock_session.commit.assert_awaited_once()


@freeze_time("2025-01-01 15:00:00", tz_offset=0)
async def test_scheduler_ensures_open_game_outside_19_utc():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()
    mock_service.get_active_games = AsyncMock(return_value=[])
    mock_service.ensure_open_game = AsyncMock()

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.ensure_open_game.assert_awaited_once_with(mock_wallet)
    mock_service.get_active_games.assert_not_called()
    mock_service.execute_flip.assert_not_called()
    mock_session.commit.assert_awaited_once()


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_scheduler_iter_games():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()
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

    # DB commit
    mock_session.commit.assert_awaited_once()


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_scheduler_showdown_trigger():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()
    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()

    game_1 = create_game(1, "showdown_pending")

    mock_service.get_active_games.return_value = [game_1]

    patches = _patch_scheduler(mock_service, mock_wallet, mock_leaderboard)
    with patches[0], patches[1], patches[2], patches[3]:
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.get_active_games.assert_awaited_once()

    mock_service.try_start_showdown.assert_has_awaits([
        call(game_1.id, mock_wallet, mock_leaderboard, engine.redis_client),
    ])
    mock_service.ensure_open_game.assert_awaited_once_with(mock_wallet)


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_scheduler_game_error_continues_processing():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = AsyncMock()
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
    mock_session.commit.assert_awaited_once()  # commit runs even after error
