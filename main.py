from fastapi import FastAPI
from config import settings
from db import init_db
from Auth.router import router as auth_router
from Wallet.router import router as wallet_router
from Game.router import router as game_router

app = FastAPI(title="Daily Flip API")

app.include_router(auth_router, prefix="/auth")
app.include_router(wallet_router, prefix="/wallet")
app.include_router(game_router, prefix="/game")

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/health")
async def health():
    return {"status": "ok"}
