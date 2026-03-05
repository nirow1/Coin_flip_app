from Wallet.router import router as wallet_router
from Auth.router import router as auth_router
#from Game.router import router as game_router
from lifespan import lifespan
from fastapi import FastAPI

app = FastAPI(title="Daily Flip API", lifespan=lifespan)

app.include_router(auth_router, prefix="/auth")
app.include_router(wallet_router, prefix="/wallet")
#app.include_router(game_router, prefix="/game")

@app.get("/health")
async def health():
    return {"status": "ok"}
