import pytest
from decimal import Decimal
from fastapi import HTTPException
from Wallet.services import WalletService

@pytest.mark.asyncio
async def test_wallet_creation(session, test_user):
    service = WalletService(session)
    wallet =  await service.create_wallet(test_user.id)

    assert wallet.user_id == test_user.id
    assert wallet.balance == Decimal(0)

@pytest.mark.asyncio
async def test_credit_wallet(session, test_user):
    service = WalletService(session)
    wallet = await service.create_wallet(test_user.id)

    # Credit the wallet
    amount = Decimal("100.00")
    transaction = await service._apply_transaction(wallet, amount, "credit")

    updated = await service.get_wallet(test_user.id)

    assert updated.balance == Decimal("50")
    assert transaction.amount == Decimal("50")
    assert transaction.type == "credit"

@pytest.mark.asyncio
async def test_debiting(session, test_user):
    service = WalletService(session)
    await service.create_wallet(test_user.id)
    await service.credit(test_user.id, Decimal("100"))

    transaction = await service.debit(test_user.id, Decimal("30"))
    updated = await service.get_wallet(test_user.id)

    assert updated.balance == Decimal("70")
    assert transaction.amount == Decimal("-30")
    assert transaction.type == "debit"

@pytest.mark.asyncio
async def test_debit_insufficient_funds(session, test_user):
    service = WalletService(session)
    await service.create_wallet(test_user.id)

    with pytest.raises(HTTPException):
        await service.debit(test_user.id, Decimal("10"))

@pytest.mark.asyncio
async def test_get_transactions(session, test_user):
    service = WalletService(session)
    await service.create_wallet(test_user.id)
    await service.credit(test_user.id, Decimal("100"))
    await service.debit(test_user.id, Decimal("30"))

    wallet = await service.get_wallet(test_user.id)
    transactions = await service.get_transactions(wallet.id)

    assert len(transactions) == 2
    assert transactions[0].amount == Decimal("-30")
    assert transactions[1].amount == Decimal("100")

