"""Cold-address poller: pagination and cursor advance rules."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from solders.keypair import Keypair
from solders.signature import Signature
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from Backend.Wallet.enums import Chain
from Backend.Wallet.jobs import (
    _collect_signatures_after_cursor,
    run_cold_deposit_poller,
)
from Backend.Wallet.models import ChainCursor

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _make_sig(seed: int) -> Signature:
    """Build via from_bytes — Wallet conftest mocks Signature.from_string."""
    raw = bytes([(seed + i) % 256 for i in range(64)])
    return Signature.from_bytes(raw)


def _sig_info(sig: Signature) -> SimpleNamespace:
    return SimpleNamespace(signature=sig)


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

    assert result[0] == str(page_b[-1])
    assert result[-1] == str(page_a[0])
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
