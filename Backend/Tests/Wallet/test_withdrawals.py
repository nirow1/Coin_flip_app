"""Part G withdraw tests: flag gate, atomic debit, idempotency, rebroadcast, reconciler.

DB-backed cases use Wallet conftest (Postgres TEST_DATABASE_URL).
Pure unit cases run without a database.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from solders.keypair import Keypair
from solders.transaction_status import TransactionConfirmationStatus
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from Backend.Core.security import hash_password
from Backend.Core.core_solana import (
    SendFailedOnChain,
    SendFailedRefundable,
    SentUnconfirmed,
)
from Backend.Wallet.enums import (
    Chain,
    QuoteKind,
    TransactionType,
    WithdrawAsset,
    WithdrawalStatus,
)
from Backend.Wallet.jobs import (
    WITHDRAW_SENDER_INTERVAL_S,
    _broadcast_persisted_withdrawal,
    _reconcile_withdrawal,
    run_withdraw_sender,
)
from Backend.Wallet.models import PaymentQuote, Transaction, Wallet, Withdrawal
from Backend.Wallet.router import require_withdrawals_enabled
from Backend.Wallet.services import WalletService

pytestmark = pytest.mark.asyncio(loop_scope="session")

PASSWORD = "Secret123!"
DEST = str(Keypair().pubkey())


# --- Unit (no DB) -----------------------------------------------------------


async def test_require_withdrawals_enabled_503_when_flag_off():
    with patch("Backend.Wallet.router.settings") as mock_settings:
        mock_settings.WITHDRAWALS_ENABLED = False
        with pytest.raises(HTTPException) as exc_info:
            await require_withdrawals_enabled()
    assert exc_info.value.status_code == 503
    assert "Withdrawals" in str(exc_info.value.detail)


async def test_rebroadcast_reuses_persisted_bytes():
    withdrawal = MagicMock()
    withdrawal.id = 42
    withdrawal.raw_tx = b"persisted-signed-bytes-v1"
    withdrawal.signature = "sig-base58"
    withdrawal.last_valid_block_height = 100
    withdrawal.status = WithdrawalStatus.SIGNED

    session = AsyncMock()
    session.execute = AsyncMock()

    with patch(
        "Backend.Wallet.jobs.broadcast_and_confirm",
        new_callable=AsyncMock,
        side_effect=SentUnconfirmed("sig-base58"),
    ) as broadcast:
        await _broadcast_persisted_withdrawal(session, withdrawal)

    broadcast.assert_awaited_once()
    assert broadcast.await_args.kwargs["raw_bytes"] == b"persisted-signed-bytes-v1"
    assert broadcast.await_args.kwargs["signature"] == "sig-base58"
    session.execute.assert_awaited_once()


async def test_ambiguous_reconcile_never_refunds():
    """Absent sig + blockhash still valid → no status change, no refund credit."""
    withdrawal = MagicMock()
    withdrawal.id = 7
    withdrawal.signature = "a" * 64
    withdrawal.last_valid_block_height = 500
    withdrawal.status = WithdrawalStatus.BROADCAST
    withdrawal.user_id = 1
    withdrawal.credits_debited = Decimal("10.00")

    session = AsyncMock()
    session.execute = AsyncMock()

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_signature_statuses.return_value.value = [None]
    mock_client.get_block_height.return_value.value = 100  # still < last_valid

    with (
        patch("Backend.Wallet.jobs.AsyncClient", return_value=mock_client),
        patch("Backend.Wallet.jobs.WalletService") as service_cls,
    ):
        await _reconcile_withdrawal(session, withdrawal)

    session.execute.assert_not_awaited()
    service_cls.assert_not_called()


async def test_expired_absent_signature_refunds():
    withdrawal = MagicMock()
    withdrawal.id = 8
    withdrawal.signature = "b" * 64
    withdrawal.last_valid_block_height = 50
    withdrawal.status = WithdrawalStatus.SIGNED
    withdrawal.user_id = 1
    withdrawal.credits_debited = Decimal("10.00")

    session = AsyncMock()
    result = MagicMock()
    result.rowcount = 1
    session.execute = AsyncMock(return_value=result)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_signature_statuses.return_value.value = [None]
    mock_client.get_block_height.return_value.value = 100  # past last_valid

    with (
        patch("Backend.Wallet.jobs.AsyncClient", return_value=mock_client),
        patch("Backend.Wallet.jobs.WalletService") as service_cls,
    ):
        service_cls.return_value.credit = AsyncMock()
        await _reconcile_withdrawal(session, withdrawal)

    service_cls.return_value.credit.assert_awaited_once()
    kwargs = service_cls.return_value.credit.await_args.kwargs
    assert kwargs["transaction_type"] == TransactionType.REFUND
    assert kwargs["tx_hash"] == "withdraw-refund:8"


def _assigned_status(stmt):
    for column, bind in getattr(stmt, "_values", {}).items():
        key = getattr(column, "key", None)
        if key == "status":
            return getattr(bind, "value", bind)
    return stmt.compile().params.get("status")


async def test_processed_signature_does_not_confirm_or_refund():
    """confirmation_status=processed is not final — leave the row alone."""
    withdrawal = MagicMock()
    withdrawal.id = 11
    withdrawal.signature = "c" * 64
    withdrawal.last_valid_block_height = 500
    withdrawal.status = WithdrawalStatus.BROADCAST
    withdrawal.user_id = 1
    withdrawal.credits_debited = Decimal("10.00")

    session = AsyncMock()
    session.execute = AsyncMock()

    on_chain = SimpleNamespace(
        err=None,
        confirmation_status=TransactionConfirmationStatus.Processed,
    )
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_signature_statuses.return_value.value = [on_chain]

    with (
        patch("Backend.Wallet.jobs.AsyncClient", return_value=mock_client),
        patch("Backend.Wallet.jobs.WalletService") as service_cls,
    ):
        await _reconcile_withdrawal(session, withdrawal)

    session.execute.assert_not_awaited()
    service_cls.assert_not_called()
    mock_client.get_block_height.assert_not_called()


async def test_finalized_signature_confirms():
    withdrawal = MagicMock()
    withdrawal.id = 12
    withdrawal.signature = "d" * 64
    withdrawal.last_valid_block_height = 500
    withdrawal.status = WithdrawalStatus.BROADCAST
    withdrawal.user_id = 1
    withdrawal.credits_debited = Decimal("10.00")

    session = AsyncMock()
    session.execute = AsyncMock()

    on_chain = SimpleNamespace(
        err=None,
        confirmation_status=TransactionConfirmationStatus.Finalized,
    )
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_signature_statuses.return_value.value = [on_chain]

    with (
        patch("Backend.Wallet.jobs.AsyncClient", return_value=mock_client),
        patch("Backend.Wallet.jobs.WalletService") as service_cls,
    ):
        await _reconcile_withdrawal(session, withdrawal)

    service_cls.assert_not_called()
    mock_client.get_block_height.assert_not_called()
    session.execute.assert_awaited_once()
    assert _assigned_status(session.execute.await_args.args[0]) == WithdrawalStatus.CONFIRMED


async def test_signed_without_raw_tx_moves_to_needs_review():
    withdrawal = MagicMock()
    withdrawal.id = 13
    withdrawal.raw_tx = None
    withdrawal.signature = "sig-base58"
    withdrawal.last_valid_block_height = 100
    withdrawal.status = WithdrawalStatus.SIGNED

    session = AsyncMock()
    session.execute = AsyncMock()

    with patch(
        "Backend.Wallet.jobs.broadcast_and_confirm",
        new_callable=AsyncMock,
    ) as broadcast:
        await _broadcast_persisted_withdrawal(session, withdrawal)

    broadcast.assert_not_awaited()
    session.execute.assert_awaited_once()
    assert (
        _assigned_status(session.execute.await_args.args[0])
        == WithdrawalStatus.NEEDS_REVIEW
    )


@pytest.mark.parametrize("exc_type", [SendFailedOnChain, SendFailedRefundable])
async def test_failed_send_sleeps_instead_of_spinning(exc_type):
    """A SIGNED broadcast failure must wait out the sender interval."""
    withdrawal = MagicMock()
    withdrawal.id = 14
    withdrawal.raw_tx = b"persisted-signed-bytes-v1"
    withdrawal.signature = "sig-base58"
    withdrawal.last_valid_block_height = 100
    withdrawal.status = WithdrawalStatus.SIGNED

    session = AsyncMock()
    session.scalar = AsyncMock(return_value=withdrawal)
    session.execute = AsyncMock()

    class _SessionCM:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return None

    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)
        raise asyncio.CancelledError

    with (
        patch("Backend.Wallet.jobs.settings") as mock_settings,
        patch(
            "Backend.Wallet.jobs.broadcast_and_confirm",
            new_callable=AsyncMock,
            side_effect=exc_type("sig-base58"),
        ),
        patch("Backend.Wallet.jobs.asyncio.sleep", side_effect=fake_sleep),
    ):
        mock_settings.WITHDRAWALS_ENABLED = True
        mock_settings.SOLANA_RPC_URL = "http://rpc.test"
        with pytest.raises(asyncio.CancelledError):
            await run_withdraw_sender(lambda: _SessionCM())

    assert slept == [WITHDRAW_SENDER_INTERVAL_S]
    session.execute.assert_not_awaited()


# --- Integration (Postgres) -------------------------------------------------


async def _fund(session, user_id: int, amount: Decimal = Decimal("100.00")) -> None:
    service = WalletService(session)
    await service.credit(user_id, amount, TransactionType.CREDIT)
    await session.flush()


async def _make_withdraw_quote(
    session,
    *,
    user_id: int,
    credits: Decimal = Decimal("20.00"),
    net_atomic: int = 19_500_000,
    asset: WithdrawAsset = WithdrawAsset.USDC,
) -> PaymentQuote:
    quote = PaymentQuote(
        user_id=user_id,
        kind=QuoteKind.WITHDRAW,
        chain=Chain.SOLANA,
        payload={
            "credits": str(credits),
            "chain": Chain.SOLANA.value,
            "asset": asset.value,
            "destination": DEST,
            "net_atomic": net_atomic,
            "fee_credits": "0.50",
            "net_credits": str(credits - Decimal("0.50")),
            "price": "1",
            "price_source": "peg:USDC",
            "ata": None,
            "ata_rent_lamports": 0,
        },
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    session.add(quote)
    await session.flush()
    return quote


async def test_withdraw_http_503_when_flag_off(client, auth_user):
    headers = {"Authorization": f"Bearer {auth_user['token']}"}
    with patch("Backend.Wallet.router.settings") as mock_settings:
        mock_settings.WITHDRAWALS_ENABLED = False
        quote_resp = await client.post(
            "/wallet/credits/withdraw/quote",
            headers=headers,
            json={
                "credits": "20.00",
                "asset": "usdc",
                "destination": DEST,
                "chain": "solana",
            },
        )
        withdraw_resp = await client.post(
            "/wallet/credits/withdraw",
            headers=headers,
            json={
                "quote_id": str(uuid4()),
                "idempotency_key": "idem-key-16chars",
                "password": PASSWORD,
            },
        )
    assert quote_resp.status_code == 503
    assert withdraw_resp.status_code == 503


async def test_create_withdrawal_debits_and_queues_atomically(
    session, test_user, test_wallet
):
    await _fund(session, test_user.id, Decimal("100.00"))
    quote = await _make_withdraw_quote(session, user_id=test_user.id, credits=Decimal("20.00"))

    service = WalletService(session)
    withdrawal = await service.create_withdrawal(
        user_id=test_user.id,
        quote_id=quote.id,
        idempotency_key="idem-atomic-16char",
        password=PASSWORD,
        password_hash=test_user.password_hash,
    )
    await session.flush()

    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == test_user.id))
    assert wallet is not None
    assert wallet.balance == Decimal("80.00")
    assert withdrawal.status == WithdrawalStatus.QUEUED
    assert withdrawal.credits_debited == Decimal("20.00")

    tx_count = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.wallet_id == wallet.id,
            Transaction.type == TransactionType.WITHDRAWAL,
        )
    )
    assert tx_count == 1


async def test_create_withdrawal_idempotency_replay_safe(
    session, test_user, test_wallet
):
    await _fund(session, test_user.id, Decimal("100.00"))
    quote = await _make_withdraw_quote(session, user_id=test_user.id, credits=Decimal("15.00"))
    service = WalletService(session)
    key = "idem-replay-16chars"

    first = await service.create_withdrawal(
        user_id=test_user.id,
        quote_id=quote.id,
        idempotency_key=key,
        password=PASSWORD,
        password_hash=test_user.password_hash,
    )
    second = await service.create_withdrawal(
        user_id=test_user.id,
        quote_id=quote.id,
        idempotency_key=key,
        password=PASSWORD,
        password_hash=test_user.password_hash,
    )
    await session.flush()

    assert first.id == second.id
    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == test_user.id))
    assert wallet is not None
    assert wallet.balance == Decimal("85.00")

    tx_count = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.wallet_id == wallet.id,
            Transaction.type == TransactionType.WITHDRAWAL,
        )
    )
    assert tx_count == 1


async def test_create_withdrawal_locks_wallet_before_daily_caps(
    session, test_user, test_wallet
):
    await _fund(session, test_user.id, Decimal("100.00"))
    quote = await _make_withdraw_quote(session, user_id=test_user.id, credits=Decimal("20.00"))
    service = WalletService(session)
    events: list[str] = []
    original_lock = service.get_wallet_for_update
    original_scalar = session.scalar

    async def lock(user_id: int):
        events.append("lock")
        return await original_lock(user_id)

    async def scalar(stmt, *args, **kwargs):
        sql = str(stmt).lower()
        if "sum(" in sql and "withdrawals" in sql:
            events.append("cap")
        return await original_scalar(stmt, *args, **kwargs)

    service.get_wallet_for_update = lock  # type: ignore[method-assign]
    session.scalar = scalar  # type: ignore[method-assign]

    await service.create_withdrawal(
        user_id=test_user.id,
        quote_id=quote.id,
        idempotency_key="idem-lock-16charsx",
        password=PASSWORD,
        password_hash=test_user.password_hash,
    )
    assert "lock" in events and "cap" in events
    assert events.index("lock") < events.index("cap")


async def test_create_withdrawal_quote_race_returns_existing_row(
    session, test_user, test_wallet
):
    """Loser of quote consume must get the winner's row, not 400."""
    await _fund(session, test_user.id, Decimal("100.00"))
    quote = await _make_withdraw_quote(session, user_id=test_user.id, credits=Decimal("20.00"))
    service = WalletService(session)
    key = "idem-race-16charsxx"
    winner = await service.create_withdrawal(
        user_id=test_user.id,
        quote_id=quote.id,
        idempotency_key=key,
        password=PASSWORD,
        password_hash=test_user.password_hash,
    )

    real_scalar = session.scalar
    seen = {"n": 0}

    async def hide_first_idempotency_read(stmt, *args, **kwargs):
        seen["n"] += 1
        if seen["n"] == 1:
            return None
        return await real_scalar(stmt, *args, **kwargs)

    session.scalar = hide_first_idempotency_read  # type: ignore[method-assign]
    again = await service.create_withdrawal(
        user_id=test_user.id,
        quote_id=quote.id,
        idempotency_key=key,
        password=PASSWORD,
        password_hash=test_user.password_hash,
    )

    assert again.id == winner.id
    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == test_user.id))
    assert wallet is not None
    assert wallet.balance == Decimal("80.00")


async def test_create_withdrawal_integrity_error_returns_raced_row():
    """Insert race: flush hits the unique key, then we return the existing row."""
    existing = SimpleNamespace(id=7, status=WithdrawalStatus.QUEUED)
    session = AsyncMock()
    session.add = MagicMock()
    reads = [None, existing]

    async def scalar(_stmt):
        return reads.pop(0)

    session.scalar = scalar
    session.flush = AsyncMock(side_effect=IntegrityError("INSERT", {}, Exception("dup")))
    session.rollback = AsyncMock()

    service = WalletService(session)

    async def fake_consume(**_kwargs):
        return {
            "payload": {
                "credits": "20.00",
                "net_atomic": 19_500_000,
                "asset": WithdrawAsset.USDC.value,
                "chain": Chain.SOLANA.value,
                "destination": DEST,
            },
            "expires_at": datetime.now(UTC) + timedelta(minutes=5),
        }

    service.consume_quote = fake_consume  # type: ignore[method-assign]
    service.get_wallet_for_update = AsyncMock(return_value=SimpleNamespace())  # type: ignore[method-assign]
    service._withdrawn_credits_since = AsyncMock(return_value=Decimal("0"))  # type: ignore[method-assign]
    service.debit = AsyncMock()  # type: ignore[method-assign]

    result = await service.create_withdrawal(
        user_id=1,
        quote_id=str(uuid4()),
        idempotency_key="idem-integ-16chars",
        password=PASSWORD,
        password_hash=hash_password(PASSWORD),
    )
    assert result is existing
    session.rollback.assert_awaited()
    assert reads == []
