import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db import Base, get_session
from main import app

# SQLite in-memory — no real PostgreSQL needed
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def client():
    # Create a fresh in-memory engine for each test
    engine = create_async_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestSession = async_sessionmaker(engine, expire_on_commit=False)

    # Create all tables
    async with engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.create_all)

    # Override get_session to use the test database instead of the real one
    async def override_get_session():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    # Cleanup after each test
    async with engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.drop_all)

    app.dependency_overrides.clear()
    await engine.dispose()

