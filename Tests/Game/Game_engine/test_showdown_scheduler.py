import asyncio
import pytest
from freezegun import freeze_time
from unittest.mock import AsyncMock, MagicMock, patch
from Game.engine import GameEngine

pytestmark = pytest.mark.asyncio(loop_scope="session")


@freeze_time("2025-01-01 19:00:00", tz_offset=0)  # 19:
async def test_a_scheduler_triggers_at_19_utc():
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    mock_async_session = MagicMock(return_value=mock_session)

    mock_service = AsyncMock()
    mock_service.get_active_games = AsyncMock(return_value=[])
    mock_service.create_game = AsyncMock()

    mock_wallet = AsyncMock()
    mock_leaderboard = AsyncMock()
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()

    engine = GameEngine(mock_async_session, mock_wallet, mock_leaderboard, mock_redis, mock_pubsub)

    # asyncio.sleep raises after first call so the while loop stops
    sleep_call_count = 0

    async def mock_sleep(seconds):
        nonlocal sleep_call_count
        sleep_call_count += 1
        if sleep_call_count >= 2:
            raise asyncio.CancelledError

    with patch("Game.engine.GameService", return_value=mock_service), \
         patch("asyncio.sleep", side_effect=mock_sleep):
        with pytest.raises(asyncio.CancelledError):
            await engine.daily_scheduler()

    mock_service.create_game.assert_called_once()



async def test_b_scheduler_triggers_at_19_utc():
    mock_session = AsyncMock()