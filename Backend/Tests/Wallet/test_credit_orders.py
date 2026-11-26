"""Credit orders: single-use quotes, expiry, pending cap, owner-only status."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from solders.keypair import Keypair
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from Backend.Auth.models import User
from Backend.Core.security import create_access_token, hash_password
from Backend.db import get_session
from Backend.Wallet.enums import Chain, CreditOrderStatus, QuoteKind
from Backend.Wallet.models import CreditOrder, PaymentQuote, Wallet
from Backend.Wallet.schemas import MAX_PENDING_CREDIT_ORDERS
from Backend.Wallet.services import WalletService
from Backend.config import settings

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _make_buy_quote(
    session,
    *,
    user_id: int,
    credits: int = 10,
    lamports: int = 100_000_000,
    expires_at: datetime | None = None,
) -> PaymentQuote:
    quote = PaymentQuote(
        user_id=user_id,
        kind=QuoteKind.BUY,
        chain=Chain.SOLANA,
        payload={
            "credits": credits,
            "chain": Chain.SOLANA.value,
            "lamports": lamports,
            "price": "100",
            "fee": "0.015",
            "price_source": "pyth:SOL/USD",
        },
        expires_at=expires_at or (datetime.now(UTC) + timedelta(minutes=5)),
    )
    session.add(quote)
    await session.flush()
    return quote


async def test_quote_is_single_use(session, test_user, test_wallet):
    quote = await _make_buy_quote(session, user_id=test_user.id)
    service = WalletService(session)

    first = await service.create_credit_order(user_id=test_user.id, quote_id=quote.id)
    assert first.status == CreditOrderStatus.PENDING

    with pytest.raises(HTTPException) as exc:
        await service.create_credit_order(user_id=test_user.id, quote_id=quote.id)
    assert exc.value.status_code == 400
    detail = str(exc.value.detail).lower()
    assert "already used" in detail or "invalid" in detail


async def test_expired_quote_rejected(session, test_user, test_wallet):
    quote = await _make_buy_quote(
        session,
        user_id=test_user.id,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    service = WalletService(session)

    with pytest.raises(HTTPException) as exc:
        await service.create_credit_order(user_id=test_user.id, quote_id=quote.id)
    assert exc.value.status_code == 400
    detail = str(exc.value.detail).lower()
    assert "expired" in detail or "invalid" in detail


async def test_pending_order_cap_holds(session, test_user, test_wallet):
    service = WalletService(session)

    for i in range(MAX_PENDING_CREDIT_ORDERS):
        quote = await _make_buy_quote(session, user_id=test_user.id, credits=10 + i)
        await service.create_credit_order(user_id=test_user.id, quote_id=quote.id)

    overflow = await _make_buy_quote(session, user_id=test_user.id, credits=99)
    with pytest.raises(HTTPException) as exc:
        await service.create_credit_order(user_id=test_user.id, quote_id=overflow.id)
    assert exc.value.status_code == 400
    assert "pending" in str(exc.value.detail).lower()

    n = await session.scalar(
        select(func.count())
        .select_from(CreditOrder)
        .where(
            CreditOrder.user_id == test_user.id,
            CreditOrder.status == CreditOrderStatus.PENDING,
        )
    )
    assert n == MAX_PENDING_CREDIT_ORDERS


async def test_pending_cap_ignores_expired_but_still_pending(session, test_user, test_wallet):
    """Rows still PENDING after expires_at do not burn the pending slots."""
    service = WalletService(session)
    for i in range(MAX_PENDING_CREDIT_ORDERS):
        quote = await _make_buy_quote(session, user_id=test_user.id, credits=10 + i)
        order = await service.create_credit_order(user_id=test_user.id, quote_id=quote.id)
        order.expires_at = datetime.now(UTC) - timedelta(seconds=30)
        order.status = CreditOrderStatus.PENDING
    await session.flush()

    fresh = await _make_buy_quote(session, user_id=test_user.id, credits=42)
    created = await service.create_credit_order(user_id=test_user.id, quote_id=fresh.id)
    assert created.status == CreditOrderStatus.PENDING
    assert created.expires_at > datetime.now(UTC)


async def test_create_credit_order_locks_wallet_before_pending_count(
    session, test_user, test_wallet
):
    service = WalletService(session)
    quote = await _make_buy_quote(session, user_id=test_user.id)
    events: list[str] = []
    original_lock = service.get_wallet_for_update
    original_scalar = session.scalar

    async def lock(user_id: int):
        events.append("lock")
        return await original_lock(user_id)

    async def scalar(stmt, *args, **kwargs):
        sql = str(stmt).lower()
        if "count(" in sql and "credit_order" in sql:
            events.append("count")
        return await original_scalar(stmt, *args, **kwargs)

    service.get_wallet_for_update = lock  # type: ignore[method-assign]
    session.scalar = scalar  # type: ignore[method-assign]

    await service.create_credit_order(user_id=test_user.id, quote_id=quote.id)
    assert "lock" in events and "count" in events
    assert events.index("lock") < events.index("count")


async def test_order_status_route_only_answers_owner(engine, test_app):
    """GET /wallet/credits/orders/{id} returns 404 for a non-owner."""
    async with engine.connect() as setup:
        await setup.begin()
        sf = async_sessionmaker(bind=setup, expire_on_commit=False)
        async with sf() as s:
            owner = User(
                email=f"owner-{uuid4().hex[:8]}@example.com",
                password_hash=hash_password("Secret123!"),
                country="CZ",
                dob=date(2000, 1, 1),
            )
            other = User(
                email=f"other-{uuid4().hex[:8]}@example.com",
                password_hash=hash_password("Secret123!"),
                country="CZ",
                dob=date(2000, 1, 1),
            )
            s.add_all([owner, other])
            await s.flush()
            s.add(Wallet(user_id=owner.id, balance=Decimal("0.00")))
            s.add(Wallet(user_id=other.id, balance=Decimal("0.00")))
            await s.flush()

            quote = PaymentQuote(
                user_id=owner.id,
                kind=QuoteKind.BUY,
                chain=Chain.SOLANA,
                payload={
                    "credits": 10,
                    "chain": Chain.SOLANA.value,
                    "lamports": 100_000_000,
                    "price": "100",
                    "fee": "0.015",
                    "price_source": "pyth:SOL/USD",
                },
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
                consumed_at=datetime.now(UTC),
            )
            s.add(quote)
            await s.flush()

            order = CreditOrder(
                user_id=owner.id,
                credits=Decimal("10"),
                chain=Chain.SOLANA,
                status=CreditOrderStatus.PENDING,
                order_ref=f"ref-{uuid4().hex[:12]}",
                reference_pubkey=str(Keypair().pubkey()),
                quoted_atomic_amount=100_000_000,
                receive_address=settings.SOLANA_COLD_RECEIVE_ADDRESS,
                expires_at=datetime.now(UTC) + timedelta(minutes=5),
                quote_id=quote.id,
            )
            s.add(order)
            await s.flush()
            await s.commit()
            await s.refresh(owner)
            await s.refresh(other)
            await s.refresh(order)
            owner_id, other_id, order_id = owner.id, other.id, order.id
        await setup.commit()

    async with engine.connect() as conn:
        await conn.begin()
        test_sf = async_sessionmaker(
            bind=conn, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )

        async def override_get_session():
            async with test_sf() as s:
                yield s

        test_app.dependency_overrides[get_session] = override_get_session
        transport = ASGITransport(app=test_app)
        try:
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                owner_token = create_access_token({"sub": str(owner_id)})
                other_token = create_access_token({"sub": str(other_id)})

                ac.cookies.set("access_token", owner_token)
                ok = await ac.get(f"/wallet/credits/orders/{order_id}")
                assert ok.status_code == 200
                assert ok.json()["order_id"] == order_id

                ac.cookies.set("access_token", other_token)
                denied = await ac.get(f"/wallet/credits/orders/{order_id}")
                assert denied.status_code == 404
        finally:
            test_app.dependency_overrides.pop(get_session, None)
            await conn.rollback()
