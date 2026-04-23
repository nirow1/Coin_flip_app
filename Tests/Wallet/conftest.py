from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from Wallet.router import router as wallet_router
from Auth.router import router as auth_router
from httpx import AsyncClient, ASGITransport
from Core.security import hash_password, create_access_token
from typing import AsyncGenerator
from db import Base, get_session
from Wallet.models import Wallet, UserSolanaWallet
from sqlalchemy import select
from Auth.models import User
from fastapi import FastAPI
from config import settings
from decimal import Decimal
from datetime import date
import pytest_asyncio

# --- Import all models so SQLAlchemy can resolve every relationship on User ---
import Notification.models      # noqa: F401  (Notification, relationship on User)
import Social.models            # noqa: F401  (Friend, relationship on User)
import Leader_board.model       # noqa: F401  (Leaderboard, relationship on User)
import Game.models              # noqa: F401  (any Game models referencing Base)
import pytest

TEST_DATABASE_URL = settings.TEST_DATABASE_URL

FAKE_SOLANA_ADDRESS = "So11111111111111111111111111111111111111112"


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
                                                  expire_on_commit=False)

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
    app.include_router(wallet_router)
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

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def committed_user_and_wallet(engine):
    async with engine.connect() as conn:
        await conn.begin()
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            # Check if user already exists from a previous interrupted run
            result = await s.execute(select(User).where(User.email == "concurrent@example.com"))
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    email="concurrent@example.com",
                    password_hash=hash_password("Secret123!"),
                    country="CZ",
                    dob=date(2000, 1, 1)
                )
                s.add(user)
                await s.flush()

                wallet = Wallet(user_id=user.id, balance=Decimal("0.00"))
                s.add(wallet)
            else:
                result = await s.execute(select(Wallet).where(Wallet.user_id == user.id))
                wallet = result.scalar_one()

            await s.commit()
            await s.refresh(user)
            await s.refresh(wallet)
        await conn.commit()

    return [user.id, wallet.id]

@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def solana_engine():
    _engine = create_async_engine(TEST_DATABASE_URL)
    async with _engine.connect() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()
    yield _engine
    async with _engine.connect() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.commit()
    await _engine.dispose()


@pytest.fixture(scope="session")
def solana_app():
    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")
    app.include_router(wallet_router)
    return app


@pytest_asyncio.fixture(loop_scope="session")
async def solana_client(solana_engine, solana_app):
    """
    Provides an AsyncClient with:
      - a committed User, Wallet, and UserSolanaWallet in the DB
      - get_session overridden to use a rolled-back test connection
      - a pre-built JWT token for the user
    Returns a dict: {"client": AsyncClient, "token": str, "public_key": str, "user_id": int}
    """
    # --- Commit real data so it's visible across connections ---
    async with solana_engine.connect() as setup_conn:
        await setup_conn.begin()
        sf = async_sessionmaker(bind=setup_conn, expire_on_commit=False)
        async with sf() as s:
            user = User(
                email="solana_deposit@example.com",
                password_hash=hash_password("Secret123!"),
                country="CZ",
                dob=date(2000, 1, 1),
            )
            s.add(user)
            await s.flush()

            wallet = Wallet(user_id=user.id, balance=Decimal("0.00"))
            s.add(wallet)
            await s.flush()

            solana_wallet = UserSolanaWallet(
                user_id=user.id,
                public_key=FAKE_SOLANA_ADDRESS,
                private_key_encrypted=b"dummy",
            )
            s.add(solana_wallet)
            await s.commit()
            await s.refresh(user)
            await s.refresh(wallet)

        await setup_conn.commit()

    token = create_access_token({"sub": str(user.id)})

    # --- Per-test rolled-back connection for the client ---
    async with solana_engine.connect() as conn:
        await conn.begin()
        test_sf = async_sessionmaker(bind=conn, expire_on_commit=False,
                                     join_transaction_mode="create_savepoint")

        async def override_get_session():
            async with test_sf() as s:
                yield s

        solana_app.dependency_overrides[get_session] = override_get_session

        transport = ASGITransport(app=solana_app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield {"client": ac, "token": token,
                       "public_key": FAKE_SOLANA_ADDRESS, "user_id": user.id}
        finally:
            solana_app.dependency_overrides.pop(get_session, None)
            await conn.rollback()

