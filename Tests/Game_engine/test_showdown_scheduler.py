import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from Tests.Game_engine.conftest import make_engine_with_mocks, async_iter

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_showdown_scheduler_processes_expired_key():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = AsyncMock()

    messages = [
        {"type": "pmessage", "data": "showdown_flip:5:2"},
        {"type": "subscribe", "data": "showdown_flip:5:3"},  # non-pmessage → stops processing
    ]
    engine.pubsub.listen = MagicMock(return_value=async_iter(messages))

    with patch("Game.engine.GameService", return_value=mock_service):
        await engine.showdown_scheduler()

    mock_service.execute_showdown_flip.assert_awaited_once_with(
        5, engine.wallet_service, engine.leaderboard_service, engine.redis_client
    )


async def test_showdown_scheduler_ignore_malformed_key():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = AsyncMock()

    messages = [
        {"type": "pmessage", "data": "showdown:5:2"},  # wrong prefix → skip
        {"type": "subscribe", "data": "showdown_flip:5:3"},
    ]
    engine.pubsub.listen = MagicMock(return_value=async_iter(messages))

    with patch("Game.engine.GameService", return_value=mock_service):
        await engine.showdown_scheduler()

    assert mock_service.execute_showdown_flip.await_count == 0  # ← fixed from execute_flip


async def test_showdown_scheduler_ignores_non_pmessage():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = AsyncMock()

    messages = [
        {"type": "subscribe", "data": "showdown_flip:5:2"},
        {"type": "psubscribe", "data": "showdown_flip:5:3"},
    ]
    engine.pubsub.listen = MagicMock(return_value=async_iter(messages))

    with patch("Game.engine.GameService", return_value=mock_service):
        await engine.showdown_scheduler()

    assert mock_service.execute_showdown_flip.await_count == 0


async def test_showdown_scheduler_error_does_not_crash():
    engine, mock_session, _ = make_engine_with_mocks()
    mock_service = AsyncMock()
    mock_service.execute_showdown_flip.side_effect = Exception("DB error")

    messages = [
        {"type": "pmessage", "data": "showdown_flip:5:2"},  # raises exception
        {"type": "pmessage", "data": "showdown_flip:6:1"},  # must still be processed
        {"type": "subscribe", "data": "stop"},
    ]
    engine.pubsub.listen = MagicMock(return_value=async_iter(messages))

    with patch("Game.engine.GameService", return_value=mock_service):
        await engine.showdown_scheduler()  # must not raise

    assert mock_service.execute_showdown_flip.await_count == 2
