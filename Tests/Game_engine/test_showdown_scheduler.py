import pytest
import asyncio
from datetime import datetime, timezone
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock, patch
from Tests.Game_engine.conftest import make_engine_with_mocks, make_mock_sleep

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
        engine.leaderboard_service,
    )

    mock_service.create_game.assert_awaited_once_with(datetime(2025, 1, 2, 19, 0, tzinfo=timezone.utc))

    # DB commit
    mock_session.commit.assert_awaited_once()