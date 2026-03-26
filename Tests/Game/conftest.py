from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from typing import AsyncGenerator
from Auth.models import User
from Core.security import hash_password
from Game.models import Game
from Wallet.models import Wallet
from config import settings
import pytest_asyncio
from db import Base


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
async def create_test_user(session):
    async def _create_test_user(email: str) -> User:
        user = User(
            email=email,
            password_hash=hash_password("Secret123!"),
            country="CZ",
            dob=date(2000, 1, 1)
        )
        session.add(user)
        await session.flush()
        await session.commit()
        await session.refresh(user)
        return user

    return _create_test_user

@pytest_asyncio.fixture(loop_scope="session")
async def test_wallet(session, test_user):
    wallet = Wallet(user_id=test_user.id, balance=Decimal("0.00"))
    session.add(wallet)
    
    await session.flush()
    await session.commit()
    await session.refresh(wallet)
    
    return wallet

@pytest_asyncio.fixture(loop_scope="session")
async def open_game(session):
    now = datetime.now(timezone.utc)
    game = Game(
        status="open",
        start_date=now,
        # Flip time is 1 hour in the future so the 5-minute lockout does not trigger
        flip_time=now + timedelta(hours=1),
        prize_pool=Decimal("0.00"),
        current_player_count=0,
    )
    session.add(game)
    await session.flush()
    await session.refresh(game)
    return game


@pytest_asyncio.fixture(loop_scope="session")
async def make_game(session):
    async def _make_game(status: str, flip_time_offset: timedelta = timedelta(hours=1)) -> Game:
        now = datetime.now(timezone.utc)
        game = Game(
            status=status,
            start_date=now,
            flip_time=now + flip_time_offset,
            prize_pool=Decimal("0.00"),
            current_player_count=0,
        )
        session.add(game)
        await session.flush()
        await session.refresh(game)
        return game

    return _make_game
