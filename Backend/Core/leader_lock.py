import asyncio
import logging

import redis

from Backend.Game.engine import GameEngine

logger = logging.getLogger(__name__)


class LeaderLock:
    def __init__(self, redis_client: redis.Redis, key: str, ttl_ms: int):
        self.key = key
        self.redis_client = redis_client
        self.ttl_ms = ttl_ms
        # Local leadership flag used by `run_if_leader()` to decide whether to keep
        # running scheduler tasks.
        self.is_locked = False
    
    async def acquire(self) -> bool:
        response = await self.redis_client.set(self.key,"1", nx=True, px=self.ttl_ms)
        return response is not None
    
    async def renew(self) -> bool:
        response = await self.redis_client.pexpire(self.key, px=self.ttl_ms)
        return bool(response)
    
    async def release(self) -> None:
        await self.redis_client.delete(self.key)
        self.is_locked = False
    
    async def keep_alive(self) -> None:
        try:
            while True:
                # If we can't renew the lock anymore, leadership is lost.
                renewed = await self.renew()
                if not renewed:
                    self.is_locked = False
                    return

                await asyncio.sleep(self.ttl_ms / 3 / 1000)
        except asyncio.CancelledError:
            self.is_locked = False
            await self.release()
            raise
        except redis.exceptions.RedisError:
            # On unexpected Redis errors we stop leadership locally to avoid running
            # schedulers while we no longer reliably own the lock.
            self.is_locked = False
            return


async def run_if_leader(lock: LeaderLock, engine: GameEngine):
    keep_alive_task = None
    daily_task = None
    showdown_task = None

    try:
        while True:
            if await lock.acquire():
                lock.is_locked = True
                keep_alive_task = asyncio.create_task(lock.keep_alive())
                daily_task = asyncio.create_task(engine.daily_scheduler())
                showdown_task = asyncio.create_task(engine.showdown_scheduler())

                # Wait until leadership is lost (detected by keep_alive()).
                while lock.is_locked:
                    await asyncio.sleep(1)

                # Lost the lock — cancel scheduler tasks.
                tasks = [t for t in (keep_alive_task, daily_task, showdown_task) if t is not None]
                for t in tasks:
                    if not t.done():
                        t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

                keep_alive_task = None
                daily_task = None
                showdown_task = None
            else:
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        # Ensure shutdown doesn't orphan child tasks.
        tasks = [t for t in (keep_alive_task, daily_task, showdown_task) if t is not None]
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # Best-effort lock release (keep_alive() will also try to release on
        # cancellation, but this ensures we leave a clean state).
        try:
            await lock.release()
        except redis.exceptions.RedisError:
            # Best-effort cleanup only; cancellation is already in progress.
            logger.warning("Failed to release leader lock during shutdown.")
        raise