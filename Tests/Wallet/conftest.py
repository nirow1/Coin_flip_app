from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from Wallet.router import router as wallet_router
from Auth.router import router as auth_router
from httpx import AsyncClient, ASGITransport
from Core.security import hash_password
from typing import AsyncGenerator
from db import Base, get_session
from Wallet.models import Wallet
from Auth.models import User
from fastapi import FastAPI
from config import settings
from datetime import date
import pytest_asyncio

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


@pytest_asyncio.fixture(loop_scope="session")
async def test_user(session):
    user = User(
        email="test@example.com",
        password_hash=hash_password("Secret123!"),
        country="CZ",
        dob=date(2000, 1, 1)
    )

    session.add(user)
    await session.flush()
    await session.commit()
    await session.refresh(user)

    return user

@pytest_asyncio.fixture(loop_scope="session")
async def test_wallet(session, test_user):
    wallet = Wallet(user_id=test_user.id, balance=Decimal("0.00"))

    session.add(wallet)
    await session.flush()
    await session.commit()
    await session.refresh(wallet)

    return wallet

@pytest_asyncio.fixture(loop_scope="session")
async def client(test_app, engine):
    async with engine.connect() as conn:
        await conn.begin()

        test_session_factory = async_sessionmaker(bind=conn,
                                                  expire_on_commit=False,
                                                  join_transaction_mode="create_savepoint")

        async def override_get_session():
            async with test_session_factory() as s:
                yield s

        test_app.dependency_overrides[get_session] = override_get_session

        transport = ASGITransport(app=test_app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac
        finally:
            test_app.dependency_overrides.pop(get_session, None)
            await conn.rollback()

@pytest.fixture(scope="session")
def test_app():
    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")
    app.include_router(wallet_router, prefix="/wallet")
    return app


@pytest_asyncio.fixture(loop_scope="session")
async def auth_user(client):
    # Register user through the API — wallet is created automatically by register_user
    await client.post("/auth/register", json={
        "email": "router@example.com",
        "password": "Secret123!",
        "country": "CZ",
        "dob": "2000-01-01"
    })

    # Login to get JWT
    response = await client.post(
        "/auth/login",
        json={"email": "router@example.com", "password": "Secret123!"}
    )

    token = response.json()["access_token"]

    return {"token": token}

