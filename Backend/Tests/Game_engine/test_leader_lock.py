import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from Backend.Core.leader_lock import LeaderLock, run_if_leader

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _lock_with_stable_leadership() -> tuple[LeaderLock, asyncio.Event]:
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
    return lock, leadership


@pytest.mark.asyncio
async def test_run_if_leader_restarts_dead_scheduler():
    lock, leadership = _lock_with_stable_leadership()
    starts: list[int] = []

    async def crash_once():
        starts.append(1)
        if len(starts) == 1:
            raise RuntimeError("scheduler crashed")
        await asyncio.Event().wait()

    async def idle():
        await asyncio.Event().wait()

    with patch("Backend.Core.leader_lock._SCHEDULER_RESTART_DELAY_S", 0.01):
        leader_task = asyncio.create_task(
            run_if_leader(lock, [crash_once, idle])
        )
        await leadership.wait()

        for _ in range(100):
            if len(starts) >= 2:
                break
            await asyncio.sleep(0.01)

        leader_task.cancel()
        await asyncio.gather(leader_task, return_exceptions=True)

    assert len(starts) >= 2


@pytest.mark.asyncio
async def test_run_if_leader_empty_factories_stays_on_keep_alive():
    """Payments worker shell: no jobs yet — leadership must not crash."""
    lock, leadership = _lock_with_stable_leadership()

    leader_task = asyncio.create_task(run_if_leader(lock, []))
    await leadership.wait()
    await asyncio.sleep(0.05)

    assert not leader_task.done()

    leader_task.cancel()
    await asyncio.gather(leader_task, return_exceptions=True)
