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

async def test_concurrent_debits(engine, committed_user_and_wallet):
    user_id, wallet_id = committed_user_and_wallet

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
        try:
            await run_in_transaction(
                engine,
                lambda s: WalletService(s).debit(user_id, Decimal("60"))
            )
            return "success"
        except (InsufficientFundsError, HTTPException):
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

            debit_txs = [t for t in txs if t.type == TransactionType.DEBIT]
            assert len(debit_txs) == 1

async def test_concurrent_credits(engine, committed_user_and_wallet):
    user_id, wallet_id = committed_user_and_wallet

    # Read starting balance before credits
    async with engine.connect() as conn:
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            service = WalletService(s)
            wallet = await service.get_wallet(user_id)
            starting_balance = wallet.balance

    async def credit_50():
        await run_in_transaction(
            engine,
            lambda s: WalletService(s).credit(user_id, Decimal("50"))
        )

    await asyncio.gather(credit_50(), credit_50())

    async with engine.connect() as conn:
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            service = WalletService(s)
            wallet = await service.get_wallet(user_id)
            assert wallet.balance == starting_balance + Decimal("100")

            txs = (
                await s.execute(
                    select(Transaction).where(Transaction.wallet_id == wallet_id)
                )
            ).scalars().all()

            credit_txs = [t for t in txs if t.type == TransactionType.CREDIT]
            assert len(credit_txs) >= 2

async def run_in_transaction(engine, coro):
    async with engine.connect() as conn:
        await conn.begin()
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            try:
                result = await coro(s)
                await conn.commit()
                return result
            except Exception:
                await conn.rollback()
                raise