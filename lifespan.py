import asyncio
from contextlib import asynccontextmanager
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
    engine = GameEngine(SessionLocal, wallet_service)
    daily_task = asyncio.create_task(engine.daily_scheduler())
    showdown_task = asyncio.create_task(engine.showdown_scheduler())

    yield

    # Cancel schedulers on shutdown
    daily_task.cancel()
    showdown_task.cancel()
