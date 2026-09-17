from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Backend.Auth.router import router as auth_router
from Backend.config import settings
from Backend.Core.csrf import CsrfMiddleware
from Backend.Game.router import router as game_router
from Backend.Leader_board.router import router as leaderboard_router
from Backend.lifespan import lifespan
from Backend.Wallet.router import router as wallet_router

app = FastAPI(title="Daily Flip API", lifespan=lifespan)

app.include_router(auth_router, prefix="/auth")
app.include_router(wallet_router)
app.include_router(game_router, prefix="/game")
app.include_router(leaderboard_router)
# Inner first, outer last: CSRF failures still get CORS headers on the way out.
app.add_middleware(CsrfMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}
