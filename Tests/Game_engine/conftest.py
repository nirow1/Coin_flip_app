import asyncio
from unittest.mock import AsyncMock, MagicMock
from Game.engine import GameEngine


async def async_iter(items):
    for item in items:
        yield item


def make_engine_with_mocks():
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = False
    mock_session.commit = AsyncMock()

    mock_async_session = MagicMock(return_value=mock_session)
    engine = GameEngine(
        async_session=mock_async_session,
        wallet_service=AsyncMock(),
        leaderboard=AsyncMock(),
        redis=AsyncMock(),
        pubsub=AsyncMock(),
    )
    return engine, mock_session, mock_async_session


def make_mock_sleep(stop_at=2):
    counter = 0
    async def mock_sleep(seconds):
        nonlocal counter
        counter += 1
        if counter >= stop_at:
            raise asyncio.CancelledError
    return mock_sleep


def create_game(id: int, status: str):
    game = MagicMock()
    game.id = id
    game.status = status
    return game