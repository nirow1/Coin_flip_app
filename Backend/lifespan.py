import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from Backend.Core.leader_lock import LeaderLock, run_if_leader
from Backend.Core.redis_config import create_redis_client
from Backend.db import SessionLocal, init_db
from Backend.Game.engine import GameEngine
from Backend.Leader_board.service import LeaderBoardService
from Backend.Wallet.services import WalletService


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize the database on startup
    await init_db()

    # Start background schedulers
    wallet_service = WalletService(SessionLocal)
    redis_client = await create_redis_client()
    pubsub = redis_client.pubsub()
    leaderboard_service = LeaderBoardService(SessionLocal)
    engine = GameEngine(SessionLocal, wallet_service, leaderboard_service, redis_client, pubsub)
    lock = LeaderLock(redis_client, key="scheduler:leader", ttl_ms=10_000)
    leader_task = asyncio.create_task(run_if_leader(lock, engine))

    yield

    # Cancel schedulers on shutdown; run_if_leader releases the lock if we hold it.
    leader_task.cancel()
    await asyncio.gather(leader_task, return_exceptions=True)
    await pubsub.unsubscribe()
    await pubsub.aclose()
    await redis_client.aclose()

