from typing import AsyncGenerator
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from Auth.models import User
from Core.security import hash_password
from config import settings
from db import Base

TEST_DATABASE_URL = settings.TEST_DATABASE_URL


@pytest.fixture(scope="session")
def event_loop_policy():
    # Use default event loop policy for the session
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest_asyncio.fixture(scope="session")
async def engine():
    # Create engine once for the entire test session
    engine = create_async_engine(TEST_DATABASE_URL)

    async with engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    # Each test gets its own transaction that is always rolled back after the test
    async with engine.connect() as conn:  # type: ignore[arg-type]
        test_session = async_sessionmaker(bind=conn,
                                          expire_on_commit=False,
                                          join_transaction_mode="create_savepoint")

        async with test_session() as s:
            try:
                yield s
            finally:
                await s.rollback()


@pytest_asyncio.fixture
async def test_user(session: AsyncSession) -> User:
    user = User(
        email="test@example.com",
        password_hash=hash_password("Secret123!"),
        country="CZ",
        dob="2000-01-01"
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
