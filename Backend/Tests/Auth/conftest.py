import os

# Must be set before Backend.config / Backend.main import (settings loads at import time).
os.environ.setdefault("JWT_REFRESH_SECRET", "test-jwt-refresh-secret-32b-min")
os.environ.setdefault("COOKIE_SECURE", "false")

import fakeredis.aioredis as fakeredis
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from Backend.config import settings
from Backend.Core.core_redis import get_redis
from Backend.db import Base, get_session
from Backend.main import app

# Ensure http://test clients can store Secure cookies from login/refresh.
settings.COOKIE_SECURE = False

# SQLite in-memory — no real PostgreSQL needed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def client():
    # Create a fresh in-memory engine for each test
    engine = create_async_engine(
        TEST_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    TestSession = async_sessionmaker(engine, expire_on_commit=False)

    # Create all tables
    async with engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.create_all)

    # Override get_session to use the test database instead of the real one
    async def override_get_session():
        async with TestSession() as session:
            yield session

    fake_redis = fakeredis.FakeRedis(decode_responses=True)

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_redis] = override_get_redis

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Cleanup after each test
    async with engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.drop_all)

    app.dependency_overrides.clear()
    await engine.dispose()
    await fake_redis.aclose()
