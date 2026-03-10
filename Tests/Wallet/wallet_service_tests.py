import asyncio
import pytest
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from fastapi import HTTPException
from Wallet.services import WalletService
from Wallet.models import Transaction
from Wallet.enums import TransactionType
from Core.exceptions import InsufficientFundsError
from Core.security import hash_password
from Auth.models import User
from Wallet.models import Wallet
from datetime import date

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_wallet_creation(session, test_user, test_wallet):
    # test_wallet fixture already created the wallet — just verify it
    assert test_wallet.user_id == test_user.id
    assert test_wallet.balance == Decimal("0.00")


async def test_credit_wallet(session, test_user, test_wallet):
    service = WalletService(session)

    amount = Decimal("100.00")
    transaction = await service._apply_transaction(test_wallet, amount, TransactionType.CREDIT)

    updated = await service.get_wallet(test_user.id)

    assert updated.balance == Decimal("100.00")
    assert transaction.amount == Decimal("100.00")
    assert transaction.type == "credit"


async def test_debiting(session, test_user, test_wallet):
    service = WalletService(session)
    await service.credit(test_user.id, Decimal("100"))

    transaction = await service.debit(test_user.id, Decimal("30"))
    updated = await service.get_wallet(test_user.id)

    assert updated.balance == Decimal("70")
    assert transaction.amount == Decimal("-30")
    assert transaction.type == "debit"


async def test_debit_insufficient_funds(session, test_user, test_wallet):
    service = WalletService(session)

    with pytest.raises(HTTPException):
        await service.debit(test_user.id, Decimal("10"))


async def test_get_transactions(session, test_user, test_wallet):
    service = WalletService(session)
    await service.credit(test_user.id, Decimal("100"))
    await service.debit(test_user.id, Decimal("30"))

    transactions = await service.get_transactions(test_user.id)

    assert len(transactions) == 2
    assert transactions[0].amount == Decimal("-30")   # debit — highest id (desc)
    assert transactions[1].amount == Decimal("100")   # credit — lower id

async def test_concurrent_debits(engine):
    # Create a dedicated user and wallet committed to the DB
    async with engine.connect() as conn:
        await conn.begin()
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
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
            await s.commit()
            await s.refresh(user)
            await s.refresh(wallet)
        await conn.commit()

    user_id = user.id
    wallet_id = wallet.id

    # Credit 100 first using a dedicated connection
    async with engine.connect() as conn:
        await conn.begin()
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            service = WalletService(s)
            await service.credit(user_id, Decimal("100"))
        await conn.commit()

    # Each debit needs its own connection to simulate real concurrency with FOR UPDATE locking
    async def debit_60():
        async with engine.connect() as conn:
            await conn.begin()
            sf = async_sessionmaker(bind=conn, expire_on_commit=False)
            async with sf() as s:
                service = WalletService(s)
                try:
                    await service.debit(user_id, Decimal("60"))
                    await conn.commit()
                    return "success"
                except (InsufficientFundsError, HTTPException):
                    await conn.rollback()
                    return "failed"

    # Run two debits at the same time
    results = await asyncio.gather(debit_60(), debit_60())

    # One should succeed, one should fail
    assert results.count("success") == 1
    assert results.count("failed") == 1

    # Check final balance via a fresh session
    async with engine.connect() as conn:
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            service = WalletService(s)
            wallet = await service.get_wallet(user_id)
            assert wallet.balance == Decimal("40")

            # Only one debit transaction should exist
            txs = (
                await s.execute(
                    select(Transaction).where(Transaction.wallet_id == wallet_id)
                )
            ).scalars().all()

            debit_txs = [t for t in txs if t.type == "debit"]
            assert len(debit_txs) == 1

