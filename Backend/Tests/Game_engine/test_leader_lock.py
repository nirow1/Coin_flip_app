import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from Backend.Core.leader_lock import LeaderLock, run_if_leader

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.asyncio
async def test_run_if_leader_restarts_dead_daily_scheduler():
    lock = LeaderLock(AsyncMock(), key="scheduler:leader", ttl_ms=10_000)
    lock.acquire = AsyncMock(return_value=True)
    lock.release = AsyncMock()

    leadership = asyncio.Event()

    async def fake_keep_alive():
        lock.is_locked = True
        leadership.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            lock.is_locked = False
            raise

    lock.keep_alive = fake_keep_alive

    engine = MagicMock()
    daily_starts: list[int] = []

    async def crash_once_daily():
        daily_starts.append(1)
        if len(daily_starts) == 1:
            raise RuntimeError("daily crashed")
        await asyncio.Event().wait()

    async def idle_showdown():
        await asyncio.Event().wait()

    engine.daily_scheduler = crash_once_daily
    engine.showdown_scheduler = idle_showdown

    with patch("Backend.Core.leader_lock._SCHEDULER_RESTART_DELAY_S", 0.01):
        leader_task = asyncio.create_task(run_if_leader(lock, engine))
        await leadership.wait()

        for _ in range(100):
            if len(daily_starts) >= 2:
                break
            await asyncio.sleep(0.01)

        leader_task.cancel()
        await asyncio.gather(leader_task, return_exceptions=True)

    assert len(daily_starts) >= 2
