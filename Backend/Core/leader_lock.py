import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

import redis

SchedulerFactory = Callable[[], Awaitable[None]]


logger = logging.getLogger(__name__)

# Only renew/delete when the key still holds our owner token.
_RENEW_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""

_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""


class LeaderLock:
    def __init__(self, redis_client: redis.Redis, key: str, ttl_ms: int):
        self.key = key
        self.redis_client = redis_client
        self.ttl_ms = ttl_ms
        self.token: str | None = None
        # Local leadership flag used by `run_if_leader()` to decide whether to keep
        # running scheduler tasks.
        self.is_locked = False
    
    async def acquire(self) -> bool:
        token = str(uuid.uuid4())
        response = await self.redis_client.set(self.key, token, nx=True, px=self.ttl_ms)
        if response is not None:
            self.token = token
            return True
        return False
    
    async def renew(self) -> bool:
        if self.token is None:
            return False
        response = await self.redis_client.eval(
            _RENEW_SCRIPT, 1, self.key, self.token, str(self.ttl_ms)
        )
        return bool(response)
    
    async def release(self) -> None:
        if self.token is None:
            self.is_locked = False
            return
        await self.redis_client.eval(_RELEASE_SCRIPT, 1, self.key, self.token)
        self.token = None
        self.is_locked = False
    
    async def keep_alive(self) -> None:
        try:
            while True:
                # If we can't renew the lock anymore, leadership is lost.
                renewed = await self.renew()
                if not renewed:
                    self.is_locked = False
                    self.token = None
                    return

                await asyncio.sleep(self.ttl_ms / 3 / 1000)
        except asyncio.CancelledError:
            self.is_locked = False
            await self.release()
            raise
        except TypeError:
            # Defensive: if the redis-py client API is incompatible, we must
            # drop leadership locally so schedulers don't keep running.
            self.is_locked = False
            logger.exception("TypeError while renewing leader lock; dropping leadership.")
            return
        except redis.exceptions.RedisError:
            # On unexpected Redis errors we stop leadership locally to avoid running
            # schedulers while we no longer reliably own the lock.
            self.is_locked = False
            return
        except Exception:
            # Best-effort safety: leadership must never remain true if we fail
            # to renew/confirm the lock.
            self.is_locked = False
            logger.exception("Unexpected error in keep_alive; dropping leadership.")
            return


_SCHEDULER_RESTART_DELAY_S = 2.0


async def _run_scheduler_after_delay(factory, delay_s: float | None = None):
    """Sleep then run a scheduler coroutine factory (used after a crash restart)."""
    # Read the module constant at call time so tests can patch it.
    if delay_s is None:
        delay_s = _SCHEDULER_RESTART_DELAY_S
    await asyncio.sleep(delay_s)
    await factory()


async def run_if_leader(lock: LeaderLock, factories: list[SchedulerFactory]):
    keep_alive_task = None
    scheduler_tasks: list[asyncio.Task|None] = []

    try:
        while True:
            if await lock.acquire():
                lock.is_locked = True
                keep_alive_task = asyncio.create_task(lock.keep_alive())
                scheduler_tasks = [asyncio.create_task(factory()) for factory in factories]

                # Wait until leadership is lost. Restart a scheduler if it dies
                # while we still hold the lock (with a short backoff to avoid
                # tight crash loops when Redis is down).
                while lock.is_locked:
                    watched = [
                        t
                        for t in (keep_alive_task, *scheduler_tasks)
                        if t is not None
                    ]
                    done, _ = await asyncio.wait(
                        watched,
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    if keep_alive_task in done:
                        break

                    for i, task in enumerate(scheduler_tasks):
                        if task is None or task not in done:
                            continue
                        if not task.cancelled():
                            exc = task.exception()
                            if exc is not None:
                                logger.exception(
                                    f"scheduler {i} died; restarting",
                                    exc_info=exc,
                                )
                        scheduler_tasks[i] = asyncio.create_task(
                            _run_scheduler_after_delay(factories[i])
                        )


                # Lost the lock — cancel scheduler tasks.
                to_cancel = [t for t in scheduler_tasks if t is not None and not t.done()]
                for t in to_cancel:
                    t.cancel()
                await asyncio.gather(*to_cancel, return_exceptions=True)
                scheduler_tasks = []
                keep_alive_task = None
            else:
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        # Ensure shutdown doesn't orphan child tasks.
        tasks = [t for t in (keep_alive_task, *scheduler_tasks) if t is not None]
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # keep_alive() releases the lock on cancellation; release() is token-aware
        # so a duplicate call here would be a harmless no-op.
        try:
            await lock.release()
        except redis.exceptions.RedisError:
            logger.warning("Failed to release leader lock during shutdown.")
        raise
