from contextlib import asynccontextmanager
from db import init_db
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production startup
    await init_db()
    yield
    # Optional shutdown logic
