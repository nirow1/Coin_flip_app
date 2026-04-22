import pytest
import asyncio
from datetime import datetime, timezone
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock, patch, call
from Tests.Game_engine.conftest import make_engine_with_mocks, make_mock_sleep, create_game

pytestmark = pytest.mark.asyncio(loop_scope="session")


@freeze_time("2025-01-01 19:00:00", tz_offset=0)  # 19:
async def test_a_scheduler_triggers_at_19_utc():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()
    mock_service.get_active_games = AsyncMock(return_value=[])
    mock_service.create_game = AsyncMock()

    with patch("Game.engine.GameService", return_value=mock_service), \
         patch("asyncio.sleep", side_effect=make_mock_sleep()):
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.create_game.assert_called_once()


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_b_scheduler_triggers_at_19_utc():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()

    game = MagicMock()
    game.id = 1
    game.status = "active"

    mock_service.get_active_games.return_value = [game]

    with patch("Game.engine.GameService", return_value=mock_service), \
         patch("asyncio.sleep", side_effect=make_mock_sleep()):

        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.get_active_games.assert_awaited_once()

    mock_service.execute_flip.assert_awaited_once_with(
        game.id,
        engine.wallet_service,
        engine.leaderboard_service,
    )

    mock_service.create_game.assert_awaited_once_with(datetime(2025, 1, 2, 19, 0, tzinfo=timezone.utc))

    # DB commit
    mock_session.commit.assert_awaited_once()


@freeze_time("2025-01-01 15:00:00", tz_offset=0)  # 19:
async def test_scheduler_does_not_trigger_outside_19_utc():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()
    mock_service.get_active_games = AsyncMock(return_value=[])
    mock_service.create_game = AsyncMock()

    with patch("Game.engine.GameService", return_value=mock_service), \
         patch("asyncio.sleep", side_effect=make_mock_sleep()):
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.create_game.assert_not_called()
    mock_service.get_active_games.assert_not_called()


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_scheduler_iter_games():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()

    game_1 = create_game(1, "active")
    game_2 = create_game(2, "open")
    game_3 = create_game(3, "finished")

    mock_service.get_active_games.return_value = [game_1, game_2, game_3]

    with patch("Game.engine.GameService", return_value=mock_service), \
         patch("asyncio.sleep", side_effect=make_mock_sleep()):

        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.get_active_games.assert_awaited_once()

    mock_service.execute_flip.assert_has_awaits([
        call(game_1.id, engine.wallet_service, engine.leaderboard_service),
        call(game_2.id, engine.wallet_service, engine.leaderboard_service),
    ])

    assert mock_service.execute_flip.await_count == 2
    mock_service.create_game.assert_awaited_once_with(datetime(2025, 1, 2, 19, 0, tzinfo=timezone.utc))

    # DB commit
    mock_session.commit.assert_awaited_once()


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_scheduler_showdown_trigger():
    engine, mock_session, mock_async_session = make_engine_with_mocks()

    mock_service = AsyncMock()

    game_1 = create_game(1, "showdown_pending")

    mock_service.get_active_games.return_value = [game_1]

    with patch("Game.engine.GameService", return_value=mock_service), \
         patch("asyncio.sleep", side_effect=make_mock_sleep()):

        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.get_active_games.assert_awaited_once()

    mock_service.try_start_showdown.assert_has_awaits([
        call(game_1.id, engine.wallet_service, engine.leaderboard_service, engine.redis_client),
    ])


@freeze_time("2025-01-01 19:00:00", tz_offset=0)
async def test_scheduler_game_error_continues_processing():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = AsyncMock()

    game_1 = create_game(1, "active")
    game_2 = create_game(2, "active")

    mock_service.get_active_games.return_value = [game_1, game_2]
    mock_service.execute_flip.side_effect = [Exception("DB error"), None]  # game_1 spadne

    with patch("Game.engine.GameService", return_value=mock_service), \
         patch("asyncio.sleep", side_effect=make_mock_sleep()):
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    # Game_2 musí být stále zpracována i přes chybu game_1
    assert mock_service.execute_flip.await_count == 2
    mock_session.commit.assert_awaited_once()  # commit proběhne i přes chybu
