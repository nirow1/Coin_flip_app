from contextlib import asynccontextmanager
from fastapi import FastAPI
from config import settings
from db import init_db
from Auth.router import router as auth_router
#from Wallet.router import router as wallet_router
#from Game.router import router as game_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Code that runs when the application starts
    await init_db()
    yield
    # Shutdown: Code that runs when the application shuts down (if needed)
    # Example: await close_db_connections()

app = FastAPI(title="Daily Flip API", lifespan=lifespan)

app.include_router(auth_router, prefix="/auth")
#app.include_router(wallet_router, prefix="/wallet")
#app.include_router(game_router, prefix="/game")


@app.get("/health")
async def health():
    return {"status": "ok"}
