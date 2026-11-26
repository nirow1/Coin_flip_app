"""Cold-address poller: pagination and cursor advance rules."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from Backend.Auth.models import User
from Backend.Core.core_solana import MEMO_PROGRAM_IDS
from Backend.Core.security import hash_password
from Backend.config import settings as app_settings
from Backend.Wallet.enums import Chain, CreditOrderStatus, QuoteKind, TransactionType
from Backend.Wallet.jobs import (
    _collect_signatures_after_cursor,
    run_cold_deposit_poller,
)
from Backend.Wallet.models import (
    ChainCursor,
    CreditOrder,
    PaymentQuote,
    Transaction,
    Wallet,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _make_sig(seed: int) -> Signature:
    """Build via from_bytes — Wallet conftest mocks Signature.from_string."""
    raw = bytes([(seed + i) % 256 for i in range(64)])
    return Signature.from_bytes(raw)


def _sig_info(sig: Signature, err: object | None = None) -> SimpleNamespace:
    return SimpleNamespace(signature=sig, err=err)


async def test_collect_signatures_paginates_oldest_first():
    """Two RPC pages → returned oldest-first; `before` walks newer→older."""
    page_a = [_make_sig(i) for i in range(5)]
    page_b = [_make_sig(100 + i) for i in range(3)]
    call_n = {"n": 0}

    class FakeClient:
        async def get_signatures_for_address(
            self, address, before=None, until=None, limit=None, commitment=None
        ):
            call_n["n"] += 1
            if call_n["n"] == 1:
                assert before is None
                return SimpleNamespace(value=[_sig_info(s) for s in page_a])
            assert before == page_a[-1]
            return SimpleNamespace(value=[_sig_info(s) for s in page_b])

    with patch("Backend.Wallet.jobs._SIG_PAGE_LIMIT", len(page_a)):
        result = await _collect_signatures_after_cursor(
            FakeClient(), MagicMock(), until=None
        )

    assert result[0].signature == str(page_b[-1])
    assert result[0].err is None
    assert result[-1].signature == str(page_a[0])
    assert len(result) == len(page_a) + len(page_b)
    assert call_n["n"] == 2


async def test_poller_does_not_advance_cursor_on_process_failure(engine):
    """If process_deposit_signature raises, that signature must not become the cursor."""
    prior_obj = _make_sig(42)
    failing_obj = _make_sig(99)
    prior = str(prior_obj)
    failing = str(failing_obj)

    async with engine.connect() as setup:
        await setup.begin()
        sf = async_sessionmaker(bind=setup, expire_on_commit=False)
        async with sf() as s:
            existing = await s.scalar(
                select(ChainCursor).where(ChainCursor.chain == Chain.SOLANA)
            )
            if existing is None:
                s.add(
                    ChainCursor(
                        chain=Chain.SOLANA,
                        last_signature=prior,
                        last_block=None,
                        updated_at=datetime.now(UTC),
                    )
                )
            else:
                existing.last_signature = prior
                existing.updated_at = datetime.now(UTC)
            await s.commit()
        await setup.commit()

    started = asyncio.Event()

    async def boom_process(self, sig):
        started.set()
        raise RuntimeError("rpc explode")

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_signatures_for_address = AsyncMock(
        return_value=SimpleNamespace(value=[_sig_info(failing_obj)])
    )

    def restore_from_string(value: str) -> Signature:
        if value == prior:
            return prior_obj
        if value == failing:
            return failing_obj
        # Fallback: keep bytes-stable for any other string length issues
        return prior_obj

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    with (
        patch("Backend.Wallet.jobs.AsyncClient", return_value=mock_client),
        patch(
            "Backend.Wallet.jobs.WalletService.process_deposit_signature",
            boom_process,
        ),
        patch("Backend.Wallet.jobs.POLL_INTERVAL_S", 60),
        patch("Backend.Wallet.jobs.settings") as mock_settings,
        patch(
            "Backend.Wallet.jobs.Signature.from_string",
            side_effect=restore_from_string,
        ),
    ):
        mock_settings.SOLANA_RPC_URL = "http://localhost"
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = str(Keypair().pubkey())

        task = asyncio.create_task(run_cold_deposit_poller(session_factory))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            await asyncio.sleep(0.1)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async with engine.connect() as conn:
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            cursor = await s.scalar(
                select(ChainCursor).where(ChainCursor.chain == Chain.SOLANA)
            )
            assert cursor is not None
            assert cursor.last_signature == prior
            assert cursor.last_signature != failing


async def test_collect_signatures_preserves_err():
    ok = _make_sig(1)
    bad = _make_sig(2)

    class FakeClient:
        async def get_signatures_for_address(
            self, address, before=None, until=None, limit=None, commitment=None
        ):
            return SimpleNamespace(
                value=[
                    _sig_info(ok),
                    _sig_info(bad, err={"InstructionError": [0, "Custom"]}),
                ]
            )

    result = await _collect_signatures_after_cursor(FakeClient(), MagicMock(), until=None)

    assert [row.signature for row in result] == [str(bad), str(ok)]
    assert result[0].err == {"InstructionError": [0, "Custom"]}
    assert result[1].err is None


async def _set_cursor(engine, last_signature: str | None) -> None:
    async with engine.connect() as setup:
        await setup.begin()
        sf = async_sessionmaker(bind=setup, expire_on_commit=False)
        async with sf() as s:
            existing = await s.scalar(
                select(ChainCursor).where(ChainCursor.chain == Chain.SOLANA)
            )
            if existing is None:
                s.add(
                    ChainCursor(
                        chain=Chain.SOLANA,
                        last_signature=last_signature,
                        last_block=None,
                        updated_at=datetime.now(UTC),
                    )
                )
            else:
                existing.last_signature = last_signature
                existing.updated_at = datetime.now(UTC)
            await s.commit()
        await setup.commit()


async def _delete_solana_cursor(engine) -> None:
    async with engine.connect() as setup:
        await setup.begin()
        sf = async_sessionmaker(bind=setup, expire_on_commit=False)
        async with sf() as s:
            await s.execute(delete(ChainCursor).where(ChainCursor.chain == Chain.SOLANA))
            await s.commit()
        await setup.commit()


async def _read_cursor(engine) -> str | None:
    async with engine.connect() as conn:
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            cursor = await s.scalar(
                select(ChainCursor).where(ChainCursor.chain == Chain.SOLANA)
            )
            return None if cursor is None else cursor.last_signature


async def _wait_cursor(engine, expected: str, timeout: float = 8.0) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    last = None
    while loop.time() < deadline:
        last = await _read_cursor(engine)
        if last == expected:
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"cursor stayed {last!r}, expected {expected!r}")


def _deposit_tx(
    *,
    sender: str,
    cold: str,
    reference: str,
    memo: str,
    lamports: int,
) -> SimpleNamespace:
    memo_program = next(iter(MEMO_PROGRAM_IDS))
    message = SimpleNamespace(
        account_keys=[sender, cold, reference],
        instructions=[
            SimpleNamespace(program_id=memo_program, data=None, parsed=memo)
        ],
    )
    meta = SimpleNamespace(
        err=None,
        pre_balances=[lamports * 2, 0, 0],
        post_balances=[lamports, lamports, 0],
        loaded_addresses=SimpleNamespace(writable=[], readonly=[]),
    )
    encoded = SimpleNamespace(
        transaction=SimpleNamespace(message=message),
        meta=meta,
    )
    return SimpleNamespace(
        transaction=encoded,
        block_time=int(datetime.now(UTC).timestamp()),
        slot=1,
    )


async def _seed_order(session, user_id: int, *, credits: Decimal, cold: str) -> CreditOrder:
    lamports = 100_000_000
    quote = PaymentQuote(
        user_id=user_id,
        kind=QuoteKind.BUY,
        chain=Chain.SOLANA,
        payload={
            "credits": int(credits),
            "chain": Chain.SOLANA.value,
            "lamports": lamports,
            "price": "100",
            "fee": "0.015",
            "price_source": "pyth:SOL/USD",
        },
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        consumed_at=datetime.now(UTC),
    )
    session.add(quote)
    await session.flush()
    order = CreditOrder(
        user_id=user_id,
        credits=credits,
        chain=Chain.SOLANA,
        status=CreditOrderStatus.PENDING,
        order_ref=f"ord-{uuid4().hex[:16]}",
        reference_pubkey=str(Keypair().pubkey()),
        quoted_atomic_amount=lamports,
        receive_address=cold,
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
        quote_id=quote.id,
    )
    session.add(order)
    await session.flush()
    await session.refresh(order)
    return order


async def test_poller_skips_err_signature_and_processes_later(engine):
    """On-chain err is not passed to process, and the cursor still moves past it."""
    prior_obj = _make_sig(70)
    err_obj = _make_sig(71)
    later_obj = _make_sig(72)
    prior, err_sig, later = str(prior_obj), str(err_obj), str(later_obj)
    await _set_cursor(engine, prior)

    seen: list[str] = []

    async def record(self, sig: str) -> None:
        seen.append(sig)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    # RPC is newest-first; collector reverses to oldest-first (err, then later).
    mock_client.get_signatures_for_address = AsyncMock(
        return_value=SimpleNamespace(
            value=[
                _sig_info(later_obj),
                _sig_info(err_obj, err={"InstructionError": [0, "Custom"]}),
            ]
        )
    )

    def restore_from_string(value: str) -> Signature:
        return {prior: prior_obj, err_sig: err_obj, later: later_obj}.get(value, prior_obj)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    with (
        patch("Backend.Wallet.jobs.AsyncClient", return_value=mock_client),
        patch("Backend.Wallet.jobs.WalletService.process_deposit_signature", record),
        patch("Backend.Wallet.jobs.POLL_INTERVAL_S", 60),
        patch("Backend.Wallet.jobs.settings") as mock_settings,
        patch("Backend.Wallet.jobs.Signature.from_string", side_effect=restore_from_string),
    ):
        mock_settings.SOLANA_RPC_URL = "http://localhost"
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = str(Keypair().pubkey())
        task = asyncio.create_task(run_cold_deposit_poller(session_factory))
        try:
            await _wait_cursor(engine, later)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    assert seen == [later]
    assert await _read_cursor(engine) == later


async def test_poller_advances_past_verify_failure_and_processes_later_sig(engine):
    """Mismatched verify parks the order and does not block the next signature."""
    prior_obj = _make_sig(80)
    bad_obj = _make_sig(81)
    good_obj = _make_sig(82)
    prior, bad_sig, good_sig = str(prior_obj), str(bad_obj), str(good_obj)
    cold = str(Pubkey.from_string(app_settings.SOLANA_COLD_RECEIVE_ADDRESS))
    sender = str(Keypair().pubkey())

    async with engine.connect() as setup:
        await setup.begin()
        sf = async_sessionmaker(bind=setup, expire_on_commit=False)
        async with sf() as s:
            user = User(
                email=f"poller-a-{uuid4().hex[:8]}@example.com",
                password_hash=hash_password("Secret123!"),
                country="CZ",
                dob=date(2000, 1, 1),
            )
            s.add(user)
            await s.flush()
            s.add(Wallet(user_id=user.id, balance=Decimal("0.00")))
            await s.flush()
            bad_order = await _seed_order(s, user.id, credits=Decimal("10"), cold=cold)
            good_order = await _seed_order(s, user.id, credits=Decimal("4"), cold=cold)
            existing = await s.scalar(
                select(ChainCursor).where(ChainCursor.chain == Chain.SOLANA)
            )
            if existing is None:
                s.add(
                    ChainCursor(
                        chain=Chain.SOLANA,
                        last_signature=prior,
                        last_block=None,
                        updated_at=datetime.now(UTC),
                    )
                )
            else:
                existing.last_signature = prior
                existing.updated_at = datetime.now(UTC)
            await s.commit()
            user_id = user.id
            bad_id, good_id = bad_order.id, good_order.id
            bad_tx = _deposit_tx(
                sender=sender,
                cold=cold,
                reference=bad_order.reference_pubkey,
                memo="not-the-order-ref",
                lamports=100_000_000,
            )
            good_tx = _deposit_tx(
                sender=sender,
                cold=cold,
                reference=good_order.reference_pubkey,
                memo=good_order.order_ref,
                lamports=100_000_000,
            )
        await setup.commit()

    async def fake_fetch(self, tx_signature: str):
        if tx_signature == bad_sig:
            return bad_tx
        if tx_signature == good_sig:
            return good_tx
        raise AssertionError(tx_signature)

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_signatures_for_address = AsyncMock(
        return_value=SimpleNamespace(
            value=[
                _sig_info(good_obj),
                _sig_info(bad_obj),
            ]
        )
    )

    def restore_from_string(value: str) -> Signature:
        return {prior: prior_obj, bad_sig: bad_obj, good_sig: good_obj}.get(value, prior_obj)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    with (
        patch("Backend.Wallet.jobs.AsyncClient", return_value=mock_client),
        patch("Backend.Wallet.services.WalletService._fetch_finalized_tx", fake_fetch),
        patch("Backend.Wallet.jobs.POLL_INTERVAL_S", 60),
        patch("Backend.Wallet.jobs.settings") as mock_settings,
        patch("Backend.Wallet.jobs.Signature.from_string", side_effect=restore_from_string),
    ):
        mock_settings.SOLANA_RPC_URL = "http://localhost"
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = app_settings.SOLANA_COLD_RECEIVE_ADDRESS
        task = asyncio.create_task(run_cold_deposit_poller(session_factory))
        try:
            await _wait_cursor(engine, good_sig)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async with engine.connect() as conn:
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            bad = await s.get(CreditOrder, bad_id)
            good = await s.get(CreditOrder, good_id)
            assert bad is not None and good is not None
            assert bad.status == CreditOrderStatus.NEEDS_REVIEW
            assert bad.review_reason is not None
            assert bad.review_reason.startswith("verify_failed:")
            assert "memo" in bad.review_reason
            assert bad.paid_tx_hash == bad_sig
            assert good.status == CreditOrderStatus.PAID
            assert good.paid_tx_hash == good_sig

            wallet = await s.scalar(select(Wallet).where(Wallet.user_id == user_id))
            assert wallet is not None
            assert wallet.balance == Decimal("4.00")
            purchases = await s.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(
                    Transaction.wallet_id == wallet.id,
                    Transaction.type == TransactionType.PURCHASE,
                )
            )
            assert purchases == 1
            cursor = await s.scalar(
                select(ChainCursor).where(ChainCursor.chain == Chain.SOLANA)
            )
            assert cursor is not None
            assert cursor.last_signature == good_sig


def _rpc_client(sig_infos: list) -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_signatures_for_address = AsyncMock(
        return_value=SimpleNamespace(value=sig_infos)
    )
    return mock_client


async def _run_poller_until(engine, mock_client, record, expected_sig: str) -> None:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    with (
        patch("Backend.Wallet.jobs.AsyncClient", return_value=mock_client),
        patch("Backend.Wallet.jobs.WalletService.process_deposit_signature", record),
        patch("Backend.Wallet.jobs.POLL_INTERVAL_S", 60),
        patch("Backend.Wallet.jobs.settings") as mock_settings,
    ):
        mock_settings.SOLANA_RPC_URL = "http://localhost"
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = str(Keypair().pubkey())
        task = asyncio.create_task(run_cold_deposit_poller(session_factory))
        try:
            await _wait_cursor(engine, expected_sig)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_poller_processes_when_bootstrapped_cursor_has_no_signature(engine):
    """Existing row + last_signature None still credits the next cold sig."""
    deposit_obj = _make_sig(11)
    deposit = str(deposit_obj)
    await _set_cursor(engine, None)
    seen: list[str] = []

    async def record(self, sig: str) -> None:
        seen.append(sig)

    await _run_poller_until(engine, _rpc_client([_sig_info(deposit_obj)]), record, deposit)

    assert seen == [deposit]
    assert await _read_cursor(engine) == deposit


async def test_poller_creates_cursor_then_processes_first_deposit(engine):
    """No chain_cursors row: persist it, then credit the first deposit."""
    deposit_obj = _make_sig(21)
    deposit = str(deposit_obj)
    await _delete_solana_cursor(engine)
    assert await _read_cursor(engine) is None
    seen: list[str] = []

    async def record(self, sig: str) -> None:
        async with engine.connect() as conn:
            sf = async_sessionmaker(bind=conn, expire_on_commit=False)
            async with sf() as s:
                cursor = await s.scalar(
                    select(ChainCursor).where(ChainCursor.chain == Chain.SOLANA)
                )
                assert cursor is not None
                assert cursor.last_signature is None
        seen.append(sig)

    await _run_poller_until(engine, _rpc_client([_sig_info(deposit_obj)]), record, deposit)

    assert seen == [deposit]
    assert await _read_cursor(engine) == deposit


async def test_poller_leaves_cursor_when_transaction_not_fetched(engine):
    """getTransaction returning None must not watermark that signature."""
    prior_obj = _make_sig(55)
    missing_obj = _make_sig(56)
    prior = str(prior_obj)
    missing = str(missing_obj)
    await _set_cursor(engine, prior)
    started = asyncio.Event()

    async def fake_fetch(self, tx_signature: str):
        started.set()
        assert tx_signature == missing
        return None

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_signatures_for_address = AsyncMock(
        return_value=SimpleNamespace(value=[_sig_info(missing_obj)])
    )

    def restore_from_string(value: str) -> Signature:
        if value == prior:
            return prior_obj
        if value == missing:
            return missing_obj
        return prior_obj

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    with (
        patch("Backend.Wallet.jobs.AsyncClient", return_value=mock_client),
        patch("Backend.Wallet.services.WalletService._fetch_finalized_tx", fake_fetch),
        patch("Backend.Wallet.jobs.POLL_INTERVAL_S", 60),
        patch("Backend.Wallet.jobs.settings") as mock_settings,
        patch("Backend.Wallet.jobs.Signature.from_string", side_effect=restore_from_string),
    ):
        mock_settings.SOLANA_RPC_URL = "http://localhost"
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = str(Keypair().pubkey())
        task = asyncio.create_task(run_cold_deposit_poller(session_factory))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            await asyncio.sleep(0.2)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    assert await _read_cursor(engine) == prior
