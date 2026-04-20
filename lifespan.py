import asyncio
from contextlib import asynccontextmanager

from Core.redis_config import create_redis_client
from Leader_board.service import LeaderBoardService
from db import init_db, SessionLocal
from fastapi import FastAPI
from Wallet.services import WalletService
from Game.engine import GameEngine

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
    daily_task = asyncio.create_task(engine.daily_scheduler())
    showdown_task = asyncio.create_task(engine.showdown_scheduler())

    yield

    # Cancel schedulers on shutdown
    daily_task.cancel()
    showdown_task.cancel()
    await asyncio.gather(daily_task, showdown_task, return_exceptions=True)
    await pubsub.unsubscribe()
    await pubsub.aclose()
    await redis_client.aclose()

