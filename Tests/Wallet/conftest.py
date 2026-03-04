from datetime import date
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from Auth.models import User
from Core.security import hash_password
from config import settings
from db import Base, get_session
from main import app

TEST_DATABASE_URL = settings.TEST_DATABASE_URL


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine():
    # Create engine once for the entire test session
    _engine = create_async_engine(TEST_DATABASE_URL)

    async with _engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.create_all)

    yield _engine

    async with _engine.begin() as conn:  # type: ignore[arg-type]
        await conn.run_sync(Base.metadata.drop_all)

    await _engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    # Each test gets its own transaction that is always rolled back after the test
    async with engine.connect() as conn:  # type: ignore[arg-type]
        await conn.begin()  # Start outer transaction

        test_session = async_sessionmaker(bind=conn,
                                          expire_on_commit=False,
                                          join_transaction_mode="create_savepoint")

        async with test_session() as s:
            try:
                yield s
            finally:
                await conn.rollback()  # Rollback the outer transaction, wiping all test data


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def test_user(engine) -> User:
    # Create the test user once for the entire session using its own connection
    async with engine.connect() as conn:
        await conn.begin()
        test_session = async_sessionmaker(bind=conn,
                                          expire_on_commit=False,
                                          join_transaction_mode="create_savepoint")
        async with test_session() as s:
            user = User(
                email="test@example.com",
                password_hash=hash_password("Secret123!"),
                country="CZ",
                dob=date(2000, 1, 1)
            )
            s.add(user)
            await s.flush()
            await s.refresh(user)
        await conn.commit()
    return user

@pytest_asyncio.fixture(loop_scope="session")
async def client(session):
    async def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()

@pytest_asyncio.fixture(loop_scope="session")
async def auth_user(client, session):
    # Create user
    user = User(
        email="router@example.com",
        password_hash=hash_password("Secret123!"),
        country="CZ",
        dob=date(2000, 1, 1)
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # Login to get JWT
    response = await client.post(
        "/auth/login",
        data={"username": user.email, "password": "Secret123!"}
    )

    token = response.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})

    return {"user": user, "token": token}

