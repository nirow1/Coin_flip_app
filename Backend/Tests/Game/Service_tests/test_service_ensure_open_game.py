from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import fakeredis.aioredis as fakeredis
import pytest
from freezegun import freeze_time
from sqlalchemy import select

from Backend.Game.service import GameService
from Backend.Wallet.enums import TransactionType
from Backend.Wallet.models import Transaction, Wallet
from Backend.Wallet.services import WalletService

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_next_daily_flip_time_before_19_utc():
    now = datetime(2025, 1, 1, 15, 0, tzinfo=timezone.utc)
    assert GameService.next_daily_flip_time(now) == datetime(2025, 1, 1, 19, 0, tzinfo=timezone.utc)


async def test_next_daily_flip_time_at_or_after_19_utc():
    now = datetime(2025, 1, 1, 19, 0, tzinfo=timezone.utc)
    assert GameService.next_daily_flip_time(now) == datetime(2025, 1, 2, 19, 0, tzinfo=timezone.utc)

    later = datetime(2025, 1, 1, 19, 5, tzinfo=timezone.utc)
    assert GameService.next_daily_flip_time(later) == datetime(2025, 1, 2, 19, 0, tzinfo=timezone.utc)


async def test_ensure_open_game_creates_when_empty(session):
    service = GameService(session)
    wallet = WalletService(session)

    with freeze_time("2025-01-01 15:00:00", tz_offset=0):
        game = await service.ensure_open_game(wallet)

    assert game.status == "open"
    assert game.flip_time == datetime(2025, 1, 1, 19, 0, tzinfo=timezone.utc)
    assert await service.get_open_game() is not None


async def test_ensure_open_game_idempotent_when_valid_open_exists(session, make_game):
    service = GameService(session)
    wallet = WalletService(session)
    existing = await make_game("open", flip_time_offset=timedelta(hours=2))

    game = await service.ensure_open_game(wallet)

    assert game.id == existing.id
    open_games = await service.get_open_games()
    assert len(open_games) == 1


async def test_cancel_stale_refunds_players_and_cancels(session, make_game, create_funded_user):
    service = GameService(session)
    wallet = WalletService(session)
    redis = fakeredis.FakeRedis(decode_responses=True)

    game = await make_game("open", flip_time_offset=timedelta(hours=2))
    user_a = await create_funded_user("ensure_refund_a@test.com", balance=Decimal("10.00"))
    user_b = await create_funded_user("ensure_refund_b@test.com", balance=Decimal("10.00"))

    await service.join_game(user_a["user"].id, "heads", wallet, redis)
    await service.join_game(user_b["user"].id, "tails", wallet, redis)

    # Move flip into the past past the 1-minute grace window.
    game.flip_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    await session.flush()

    await service.cancel_stale_open_games(wallet)
    await session.refresh(game)

    assert game.status == "canceled"
    assert game.prize_pool == Decimal("0")

    wallet_a = await wallet.get_wallet(user_a["user"].id)
    wallet_b = await wallet.get_wallet(user_b["user"].id)
    assert wallet_a.balance == Decimal("10.00")
    assert wallet_b.balance == Decimal("10.00")

    txs = (
        await session.execute(
            select(Transaction).join(Wallet, Transaction.wallet_id == Wallet.id).where(
                Wallet.user_id.in_([user_a["user"].id, user_b["user"].id]),
                Transaction.type == TransactionType.REFUND,
            )
        )
    ).scalars().all()
    assert len(txs) == 2


async def test_cancel_stale_does_not_cancel_future_open(session, make_game):
    service = GameService(session)
    wallet = WalletService(session)
    future = await make_game("open", flip_time_offset=timedelta(hours=3))

    await service.cancel_stale_open_games(wallet)
    await session.refresh(future)

    assert future.status == "open"


async def test_cancel_stale_respects_grace_window(session, make_game):
    """Open games within 1 minute past flip_time are not canceled yet."""
    service = GameService(session)
    wallet = WalletService(session)
    barely_past = await make_game("open", flip_time_offset=timedelta(seconds=-30))

    await service.cancel_stale_open_games(wallet)
    await session.refresh(barely_past)

    assert barely_past.status == "open"


async def test_ensure_open_game_cancels_stale_then_creates(session, make_game):
    service = GameService(session)
    wallet = WalletService(session)
    stale = await make_game("open", flip_time_offset=timedelta(minutes=-10))

    game = await service.ensure_open_game(wallet)

    await session.refresh(stale)
    assert stale.status == "canceled"
    assert game.status == "open"
    assert game.id != stale.id
    assert game.flip_time == GameService.next_daily_flip_time()


async def test_cancel_game_refunds_inviter_via_paid_by(session, make_game, create_funded_user):
    service = GameService(session)
    wallet = WalletService(session)

    inviter = await create_funded_user("ensure_inviter@test.com", balance=Decimal("10.00"))
    friend = await create_funded_user("ensure_friend@test.com", balance=Decimal("5.00"))
    game = await make_game("open", flip_time_offset=timedelta(minutes=-10))

    await wallet.debit(inviter["user"].id, Decimal("1.00"))
    await service._add_player_to_game(
        game, friend["user"].id, None, paid_by_user_id=inviter["user"].id
    )

    await service.cancel_game(game.id, wallet)
    await session.refresh(game)

    assert game.status == "canceled"
    inviter_wallet = await wallet.get_wallet(inviter["user"].id)
    friend_wallet = await wallet.get_wallet(friend["user"].id)
    assert inviter_wallet.balance == Decimal("10.00")
    assert friend_wallet.balance == Decimal("5.00")


async def test_cancel_game_aborts_canceled_mark_if_refund_fails(session, make_game, create_funded_user):
    service = GameService(session)
    wallet = WalletService(session)
    user = await create_funded_user("ensure_abort@test.com", balance=Decimal("10.00"))
    game = await make_game("open", flip_time_offset=timedelta(minutes=-10))
    await service._add_player_to_game(game, user["user"].id, "heads", paid_by_user_id=user["user"].id)
    game.prize_pool = Decimal("1.00")
    await session.flush()

    wallet.credit = AsyncMock(side_effect=RuntimeError("wallet down"))

    with pytest.raises(RuntimeError, match="wallet down"):
        await service.cancel_game(game.id, wallet)

    await session.refresh(game)
    assert game.status == "open"
    assert game.prize_pool == Decimal("1.00")


async def test_lockout_handles_naive_flip_time(session, make_game, create_funded_user):
    """Naive flip_time from DB is treated as UTC for the 5-minute lockout."""
    service = GameService(session)
    wallet = WalletService(session)
    redis = fakeredis.FakeRedis(decode_responses=True)
    user = await create_funded_user("ensure_naive_lockout@test.com")

    game = await make_game("open", flip_time_offset=timedelta(minutes=3))
    game.flip_time = game.flip_time.replace(tzinfo=None)
    await session.flush()

    with pytest.raises(ValueError, match="5 minutes"):
        await service.join_game(user["user"].id, "heads", wallet, redis)
