import asyncio
from fastapi.middleware.cors import CORSMiddleware
from Backend.Wallet.router import router as wallet_router
from Backend.Auth.router import router as auth_router
from Backend.Game.router import router as game_router
from Backend.lifespan import lifespan
from fastapi import FastAPI

app = FastAPI(title="Daily Flip API", lifespan=lifespan)

app.include_router(auth_router, prefix="/auth")
app.include_router(wallet_router)
app.include_router(game_router, prefix="/game")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
