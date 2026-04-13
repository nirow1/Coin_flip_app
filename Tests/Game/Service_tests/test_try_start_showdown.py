from decimal import Decimal
from Game.models import GamePlayer
from Game.service import GameService
from Wallet.models import Wallet
from Wallet.services import WalletService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_try_start_showdown_success(session, test_user, test_wallet, create_test_user, make_game):
    service = GameService(session)
    wallet = WalletService(session)
    game = await make_game("showdown_pending")

    # Set a non-zero prize pool so payouts are meaningful (11 players × 1.00)
    game.prize_pool = Decimal("11.00")
    await session.flush()

    # test_user cashes out — needs a wallet (provided by test_wallet fixture)
    session.add(GamePlayer(game_id=game.id, user_id=test_user.id,
                           side=None, round_number=1, is_eliminated=False, cashout_decision="cashout"))

    for i in range(10):
        user = await create_test_user(f"test_user{i}@test.com")
        decision = "continue" if i < 5 else "cashout"

        # Cashout players need a wallet so credit can be applied
        if decision == "cashout":
            session.add(Wallet(user_id=user.id, balance=Decimal("0.00")))

        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=None, round_number=1, is_eliminated=False, cashout_decision=decision))

    await session.flush()

    # Check test_user balance before cashout
    balance_before = (await wallet.get_wallet(test_user.id)).balance

    showdown_game = await service.try_start_showdown(game.id, wallet)

    # Filter only active (non-eliminated) players
    all_players = await service.get_all_players(showdown_game.id)
    remaining_players = [p for p in all_players if not p.is_eliminated]

    assert showdown_game.status == "showdown_active"
    assert len(remaining_players) == 5
    assert showdown_game.prize_pool == Decimal("5.00")

    # test_user received payout: 11.00 / 11 players = 1.00
    balance_after = (await wallet.get_wallet(test_user.id)).balance
    assert balance_after == balance_before + Decimal("1.00")


async def test_try_start_showdown_all_cashout(session, create_test_user, make_game):
    service = GameService(session)
    wallet = WalletService(session)
    game = await make_game("showdown_pending")

    # 5 players, all cashout — prize_pool finishes at 0.00
    game.prize_pool = Decimal("5.00")
    await session.flush()

    for i in range(5):
        user = await create_test_user(f"all_cashout_user{i}@test.com")
        session.add(Wallet(user_id=user.id, balance=Decimal("0.00")))
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=None, round_number=1, is_eliminated=False,
                               cashout_decision="cashout"))
    await session.flush()

    result = await service.try_start_showdown(game.id, wallet)

    all_players = await service.get_all_players(result.id)

    # All players cashed out — game is finished, everyone eliminated
    assert result.status == "finished"
    assert all(p.is_eliminated for p in all_players)


async def test_try_start_showdown_one_continuer(session, create_test_user, make_game):
    service = GameService(session)
    wallet = WalletService(session)
    game = await make_game("showdown_pending")

    # 4 cashout + 1 continuer — winner gets the remaining prize_pool
    game.prize_pool = Decimal("5.00")
    await session.flush()

    winner_user = await create_test_user("winner@test.com")
    session.add(Wallet(user_id=winner_user.id, balance=Decimal("0.00")))
    session.add(GamePlayer(game_id=game.id, user_id=winner_user.id,
                           side=None, round_number=1, is_eliminated=False,
                           cashout_decision="continue"))

    for i in range(4):
        user = await create_test_user(f"one_cont_cashout{i}@test.com")
        session.add(Wallet(user_id=user.id, balance=Decimal("0.00")))
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=None, round_number=1, is_eliminated=False,
                               cashout_decision="cashout"))
    await session.flush()

    result = await service.try_start_showdown(game.id, wallet)

    # payout per cashout player = 5.00 / 5 = 1.00
    # total cashout = 4 × 1.00 = 4.00 → remaining prize_pool = 1.00 → winner gets 1.00
    winner_wallet = await wallet.get_wallet(winner_user.id)

    assert result.status == "finished"
    assert winner_wallet.balance == Decimal("1.00")


async def test_try_start_showdown_no_cashout(session, create_test_user, make_game):
    service = GameService(session)
    wallet = WalletService(session)
    game = await make_game("showdown_pending")

    game.prize_pool = Decimal("5.00")
    await session.flush()

    for i in range(5):
        user = await create_test_user(f"no_cashout_user{i}@test.com")
        # No wallet needed — no cashouts are processed
        session.add(GamePlayer(game_id=game.id, user_id=user.id,
                               side=None, round_number=1, is_eliminated=False,
                               cashout_decision="continue"))
    await session.flush()

    result = await service.try_start_showdown(game.id, wallet)

    all_players = await service.get_all_players(result.id)
    active_players = [p for p in all_players if not p.is_eliminated]

    # No one cashed out — showdown continues, prize_pool unchanged
    assert result.status == "showdown_active"
    assert len(active_players) == 5
    assert result.prize_pool == Decimal("5.00")


async def test_try_start_showdown_wrong_status(session, make_game):
    service = GameService(session)
    wallet = WalletService(session)

    # Game is not in showdown_pending
    game = await make_game("active")

    with pytest.raises(ValueError, match="Showdown is not pending"):
        await service.try_start_showdown(game.id, wallet)
