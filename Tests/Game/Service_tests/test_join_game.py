from datetime import timedelta
from decimal import Decimal
from fastapi import HTTPException
from Wallet.services import WalletService
from Game.services import GameService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_join_game_success(session, test_user, open_game, test_wallet):
    service = GameService(session)
    wallet = WalletService(session)

    await wallet.credit(test_user.id, Decimal("50.00"))

    player = await service.join_game(test_user.id, "heads", wallet)

    fetch = await service.get_game_player(player.game_id, player.user_id)
    assert fetch is not None
    assert fetch.user_id == test_user.id
    assert fetch.side == "heads"
    assert fetch.is_eliminated == False

    players_wallet = await wallet.get_wallet(test_user.id)
    assert players_wallet.balance == Decimal("49.00")

async def test_join_game_already_joined(session, open_game, create_funded_user):
    """A player cannot join the same game twice."""
    service = GameService(session)
    wallet = WalletService(session)
    user = await create_funded_user("already_joined_service@test.com")

    await service.join_game(user["user"].id, "heads", wallet)

    with pytest.raises(ValueError, match="Player is already in this game"):
        await service.join_game(user["user"].id, "heads", wallet)


async def test_join_game_insufficient_funds(session, open_game, create_funded_user):
    """A player with $0.00 balance cannot join."""
    service = GameService(session)
    wallet = WalletService(session)
    user = await create_funded_user("broke_service@test.com", balance=Decimal("0.00"))

    with pytest.raises(HTTPException) as exc_info:
        await service.join_game(user["user"].id, "heads", wallet)
    assert exc_info.value.status_code == 400


async def test_join_game_lockout(session, create_test_user, make_game):
    """Players cannot join within 5 minutes of the scheduled flip time."""
    service = GameService(session)

    from Auth.models import User
    from Wallet.models import Wallet
    from Core.security import hash_password
    from datetime import date

    # Game whose flip is 3 minutes away — inside the 5-minute lockout window.
    # get_open_game orders by flip_time ASC, so this game (soonest flip) is returned first.
    await make_game("open", flip_time_offset=timedelta(minutes=3))

    user = User(email="lockout_service@test.com", password_hash=hash_password("x"),
                country="CZ", dob=date(2000, 1, 1))
    session.add(user)
    await session.flush()
    await session.refresh(user)
    session.add(Wallet(user_id=user.id, balance=Decimal("10.00")))
    await session.flush()

    wallet = WalletService(session)
    with pytest.raises(ValueError, match="5 minutes"):
        await service.join_game(user.id, "heads", wallet)

