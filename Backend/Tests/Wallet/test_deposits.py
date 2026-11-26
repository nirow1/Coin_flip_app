"""Deposit matching: credit-once, dup, race, under/over/late, unmatched, two refs."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from solders.keypair import Keypair
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from Backend.Auth.models import User
from Backend.Core.core_solana import VerifiedSolanaTx
from Backend.Core.security import hash_password
from Backend.Wallet.enums import (
    Chain,
    CreditOrderStatus,
    QuoteKind,
    TransactionType,
    UnmatchedDepositStatus,
)
from Backend.Wallet.models import (
    CreditOrder,
    PaymentQuote,
    Transaction,
    UnmatchedDeposit,
    Wallet,
)
from Backend.Wallet.services import OVERPAY_MAX_RATIO, WalletService
from datetime import date

pytestmark = pytest.mark.asyncio(loop_scope="session")


def _verified(
    *,
    lamports: int,
    block_time: int | None,
    memo: str,
    fee_payer: str = "FeePayer111111111111111111111111111111111",
) -> VerifiedSolanaTx:
    return VerifiedSolanaTx(
        received_lamports=lamports,
        block_time=block_time,
        slot=1,
        fee_payer=fee_payer,
        memo=memo,
    )


async def _seed_pending_order(
    session,
    *,
    user_id: int,
    credits: Decimal = Decimal("10"),
    lamports: int = 100_000_000,
    expires_at: datetime | None = None,
    reference: str | None = None,
    order_ref: str | None = None,
    receive_address: str | None = None,
) -> CreditOrder:
    from Backend.config import settings

    ref = reference or str(Keypair().pubkey())
    memo = order_ref or f"ord-{uuid4().hex[:16]}"
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
        expires_at=expires_at or (datetime.now(UTC) + timedelta(minutes=5)),
        consumed_at=datetime.now(UTC),
    )
    session.add(quote)
    await session.flush()

    order = CreditOrder(
        user_id=user_id,
        credits=credits,
        chain=Chain.SOLANA,
        status=CreditOrderStatus.PENDING,
        order_ref=memo,
        reference_pubkey=ref,
        quoted_atomic_amount=lamports,
        receive_address=receive_address or settings.SOLANA_COLD_RECEIVE_ADDRESS,
        expires_at=expires_at or (datetime.now(UTC) + timedelta(minutes=5)),
        quote_id=quote.id,
    )
    session.add(order)
    await session.flush()
    await session.refresh(order)
    return order


async def _process_matched(
    service: WalletService,
    order: CreditOrder,
    *,
    sig: str,
    received: int,
    block_time: int | None,
) -> None:
    fake_tx = MagicMock()
    keys = [order.reference_pubkey, order.receive_address]
    memos = [order.order_ref]

    with (
        patch.object(service, "_fetch_finalized_tx", new_callable=AsyncMock, return_value=fake_tx),
        patch.object(
            service,
            "_tx_account_keys_and_memos",
            return_value=(keys, memos),
        ),
        patch.object(service, "_cold_lamports_delta", return_value=received),
        patch(
            "Backend.Wallet.services.verify_fetched_solana_transaction",
            return_value=_verified(
                lamports=received,
                block_time=block_time,
                memo=order.order_ref,
            ),
        ),
    ):
        await service.process_deposit_signature(sig)


async def test_match_credits_exactly_once(session, test_user, test_wallet):
    order = await _seed_pending_order(session, user_id=test_user.id, lamports=100_000_000)
    service = WalletService(session)
    sig = f"sig-match-{uuid4().hex}"

    await _process_matched(
        service,
        order,
        sig=sig,
        received=100_000_000,
        block_time=int(datetime.now(UTC).timestamp()),
    )
    await session.flush()

    await session.refresh(order)
    assert order.status == CreditOrderStatus.PAID
    assert order.paid_tx_hash == sig

    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == test_user.id))
    assert wallet is not None
    assert wallet.balance == Decimal("10.00")

    purchase_count = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.wallet_id == wallet.id,
            Transaction.type == TransactionType.PURCHASE,
            Transaction.tx_hash == sig,
        )
    )
    assert purchase_count == 1


async def test_duplicate_signature_is_noop(session, test_user, test_wallet):
    order = await _seed_pending_order(session, user_id=test_user.id)
    service = WalletService(session)
    sig = f"sig-dup-{uuid4().hex}"
    now_ts = int(datetime.now(UTC).timestamp())

    await _process_matched(service, order, sig=sig, received=100_000_000, block_time=now_ts)
    await session.flush()
    await _process_matched(service, order, sig=sig, received=100_000_000, block_time=now_ts)
    await session.flush()

    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == test_user.id))
    assert wallet is not None
    assert wallet.balance == Decimal("10.00")

    purchase_count = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .where(
            Transaction.wallet_id == wallet.id,
            Transaction.type == TransactionType.PURCHASE,
        )
    )
    assert purchase_count == 1


@pytest.mark.parametrize(
    "received,block_offset,reason",
    [
        (50_000_000, 0, "underpaid"),
        (int(Decimal(100_000_000) * OVERPAY_MAX_RATIO) + 1, 0, "overpaid"),
        (100_000_000, 600, "late"),  # 10 min after expiry window start
    ],
)
async def test_under_over_late_go_to_needs_review(
    session, test_user, test_wallet, received, block_offset, reason
):
    expires = datetime.now(UTC) + timedelta(minutes=5)
    order = await _seed_pending_order(
        session,
        user_id=test_user.id,
        lamports=100_000_000,
        expires_at=expires,
    )
    # For late: pay after expires_at
    if reason == "late":
        block_time = int((expires + timedelta(seconds=block_offset)).timestamp())
    else:
        block_time = int((expires - timedelta(minutes=1)).timestamp())

    service = WalletService(session)
    sig = f"sig-{reason}-{uuid4().hex}"
    await _process_matched(
        service, order, sig=sig, received=received, block_time=block_time
    )
    await session.flush()
    await session.refresh(order)

    assert order.status == CreditOrderStatus.NEEDS_REVIEW
    assert order.review_reason == reason
    assert order.paid_tx_hash == sig

    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == test_user.id))
    assert wallet is not None
    assert wallet.balance == Decimal("0.00")


async def test_unknown_deposit_becomes_unmatched_row(session, test_user, test_wallet):
    from Backend.config import settings

    service = WalletService(session)
    sig = f"sig-unmatched-{uuid4().hex}"
    cold = settings.SOLANA_COLD_RECEIVE_ADDRESS
    fake_tx = MagicMock()
    fake_tx.block_time = int(datetime.now(UTC).timestamp())

    with (
        patch.object(service, "_fetch_finalized_tx", new_callable=AsyncMock, return_value=fake_tx),
        patch.object(
            service,
            "_tx_account_keys_and_memos",
            return_value=([cold, "SomeSender1111111111111111111111111111111"], []),
        ),
        patch.object(service, "_cold_lamports_delta", return_value=42_000_000),
    ):
        await service.process_deposit_signature(sig)
    await session.flush()

    row = await session.scalar(
        select(UnmatchedDeposit).where(UnmatchedDeposit.tx_hash == sig)
    )
    assert row is not None
    assert row.status == UnmatchedDepositStatus.OPEN
    assert row.lamports == 42_000_000


async def test_two_references_credits_only_one_order(session, test_user, test_wallet):
    """One tx carrying two order references credits the lowest-id match only."""
    order_a = await _seed_pending_order(
        session, user_id=test_user.id, credits=Decimal("10"), lamports=100_000_000
    )
    order_b = await _seed_pending_order(
        session, user_id=test_user.id, credits=Decimal("20"), lamports=200_000_000
    )
    assert order_a.id < order_b.id

    service = WalletService(session)
    sig = f"sig-two-ref-{uuid4().hex}"
    fake_tx = MagicMock()
    keys = [
        order_a.reference_pubkey,
        order_b.reference_pubkey,
        order_a.receive_address,
    ]
    # Match path uses reference_pubkey IN account_keys ordered by id ASC limit 1
    with (
        patch.object(service, "_fetch_finalized_tx", new_callable=AsyncMock, return_value=fake_tx),
        patch.object(
            service,
            "_tx_account_keys_and_memos",
            return_value=(keys, [order_a.order_ref, order_b.order_ref]),
        ),
        patch.object(service, "_cold_lamports_delta", return_value=100_000_000),
        patch(
            "Backend.Wallet.services.verify_fetched_solana_transaction",
            return_value=_verified(
                lamports=100_000_000,
                block_time=int(datetime.now(UTC).timestamp()),
                memo=order_a.order_ref,
            ),
        ),
    ):
        await service.process_deposit_signature(sig)
    await session.flush()

    await session.refresh(order_a)
    await session.refresh(order_b)
    assert order_a.status == CreditOrderStatus.PAID
    assert order_b.status == CreditOrderStatus.PENDING

    wallet = await session.scalar(select(Wallet).where(Wallet.user_id == test_user.id))
    assert wallet is not None
    assert wallet.balance == Decimal("10.00")


async def test_webhook_and_poller_race_one_credit(engine):
    """Two sessions processing the same signature credit the wallet once."""
    async with engine.connect() as setup:
        await setup.begin()
        sf = async_sessionmaker(bind=setup, expire_on_commit=False)
        async with sf() as s:
            user = User(
                email=f"race-{uuid4().hex[:8]}@example.com",
                password_hash=hash_password("Secret123!"),
                country="CZ",
                dob=date(2000, 1, 1),
            )
            s.add(user)
            await s.flush()
            s.add(Wallet(user_id=user.id, balance=Decimal("0.00")))
            await s.flush()
            order = await _seed_pending_order(
                s, user_id=user.id, credits=Decimal("10"), lamports=100_000_000
            )
            await s.commit()
            await s.refresh(user)
            await s.refresh(order)
            user_id, order_id = user.id, order.id
            ref = order.reference_pubkey
            memo = order.order_ref
            cold = order.receive_address
        await setup.commit()

    sig = f"sig-race-{uuid4().hex}"
    now_ts = int(datetime.now(UTC).timestamp())

    async def run_once():
        async with engine.connect() as conn:
            await conn.begin()
            sf = async_sessionmaker(bind=conn, expire_on_commit=False)
            async with sf() as s:
                # re-load order for this session
                ord_row = await s.get(CreditOrder, order_id)
                assert ord_row is not None
                service = WalletService(s)
                fake_tx = MagicMock()
                with (
                    patch.object(
                        service,
                        "_fetch_finalized_tx",
                        new_callable=AsyncMock,
                        return_value=fake_tx,
                    ),
                    patch.object(
                        service,
                        "_tx_account_keys_and_memos",
                        return_value=([ref, cold], [memo]),
                    ),
                    patch.object(service, "_cold_lamports_delta", return_value=100_000_000),
                    patch(
                        "Backend.Wallet.services.verify_fetched_solana_transaction",
                        return_value=_verified(
                            lamports=100_000_000,
                            block_time=now_ts,
                            memo=memo,
                        ),
                    ),
                ):
                    await service.process_deposit_signature(sig)
                await conn.commit()

    await asyncio.gather(run_once(), run_once())

    async with engine.connect() as conn:
        sf = async_sessionmaker(bind=conn, expire_on_commit=False)
        async with sf() as s:
            wallet = await s.scalar(select(Wallet).where(Wallet.user_id == user_id))
            assert wallet is not None
            assert wallet.balance == Decimal("10.00")
            purchases = await s.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(
                    Transaction.wallet_id == wallet.id,
                    Transaction.type == TransactionType.PURCHASE,
                )
            )
            assert purchases == 1
            ord_row = await s.get(CreditOrder, order_id)
            assert ord_row is not None
            assert ord_row.status == CreditOrderStatus.PAID
            assert ord_row.paid_tx_hash == sig
