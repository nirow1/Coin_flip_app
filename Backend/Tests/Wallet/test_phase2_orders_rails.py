from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from pydantic import ValidationError
from solders.keypair import Keypair

from Backend.Wallet.enums import Chain, WithdrawAsset
from Backend.Wallet.rails import get_adapter
from Backend.Wallet.rails.base import ChainNotImplementedError
from Backend.Wallet.schemas import (
    CreateOrderRequest,
    CreditsQuoteRequest,
    WithdrawQuoteRequest,
    WithdrawRequest,
)

# On-curve system wallet pubkey — NOT the wSOL mint (finding 5 / Piece C).
VALID_DEST = str(Keypair().pubkey())
WSOL_MINT = "So11111111111111111111111111111111111111112"
HOUSE_HOT = "HotHouse1111111111111111111111111111111111"
HOUSE_COLD = "ColdHouse111111111111111111111111111111111"


def test_credits_quote_rejects_zero():
    with pytest.raises(ValidationError):
        CreditsQuoteRequest(credits=0, chain=Chain.SOLANA)


def test_credits_quote_rejects_above_max():
    with pytest.raises(ValidationError):
        CreditsQuoteRequest(credits=10001, chain=Chain.SOLANA)


def test_credits_quote_accepts_bounds():
    low = CreditsQuoteRequest(credits=1, chain=Chain.SOLANA)
    high = CreditsQuoteRequest(credits=10000, chain=Chain.POLYGON)
    assert low.credits == 1
    assert high.credits == 10000


def test_create_order_requires_quote_id_only():
    qid = uuid4()
    req = CreateOrderRequest(quote_id=qid)
    assert req.quote_id == qid
    assert set(CreateOrderRequest.model_fields.keys()) == {"quote_id"}


def test_create_order_rejects_missing_quote_id():
    with pytest.raises(ValidationError):
        CreateOrderRequest()


def test_create_order_rejects_non_uuid_quote_id():
    with pytest.raises(ValidationError):
        CreateOrderRequest(quote_id="abc-123")


def test_withdraw_quote_rejects_below_min():
    with pytest.raises(ValidationError):
        WithdrawQuoteRequest(
            credits=Decimal("9.99"),
            asset=WithdrawAsset.SOL,
            destination=VALID_DEST,
            chain=Chain.SOLANA,
        )


def test_withdraw_quote_rejects_above_max():
    with pytest.raises(ValidationError):
        WithdrawQuoteRequest(
            credits=Decimal("10000.01"),
            asset=WithdrawAsset.SOL,
            destination=VALID_DEST,
            chain=Chain.SOLANA,
        )


def test_withdraw_quote_rejects_three_decimal_places():
    with pytest.raises(ValidationError):
        WithdrawQuoteRequest(
            credits=Decimal("10.001"),
            asset=WithdrawAsset.SOL,
            destination=VALID_DEST,
            chain=Chain.SOLANA,
        )


def test_withdraw_quote_rejects_invalid_destination():
    with pytest.raises(ValidationError):
        WithdrawQuoteRequest(
            credits=Decimal("10.00"),
            asset=WithdrawAsset.SOL,
            destination="not-a-pubkey",
            chain=Chain.SOLANA,
        )


def test_withdraw_quote_rejects_house_destination():
    with patch("Backend.Wallet.schemas.settings") as mock_settings:
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = VALID_DEST
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = HOUSE_COLD
        with pytest.raises(ValidationError, match="house"):
            WithdrawQuoteRequest(
                credits=Decimal("10.00"),
                asset=WithdrawAsset.SOL,
                destination=VALID_DEST,
                chain=Chain.SOLANA,
            )


def test_withdraw_quote_accepts_two_decimals():
    with patch("Backend.Wallet.schemas.settings") as mock_settings:
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = HOUSE_HOT
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = HOUSE_COLD
        req = WithdrawQuoteRequest(
            credits=Decimal("10.25"),
            asset=WithdrawAsset.USDC,
            destination=VALID_DEST,
            chain=Chain.SOLANA,
        )
    assert req.credits == Decimal("10.25")
    assert req.destination == VALID_DEST


def test_withdraw_request_has_no_amount_fields():
    qid = uuid4()
    req = WithdrawRequest(
        quote_id=qid,
        idempotency_key="idem-key-16chars",
        password="Secret123!",
    )
    assert set(WithdrawRequest.model_fields.keys()) == {
        "quote_id",
        "idempotency_key",
        "password",
    }
    assert req.quote_id == qid


def test_withdraw_request_rejects_short_idempotency_key():
    with pytest.raises(ValidationError):
        WithdrawRequest(
            quote_id=uuid4(),
            idempotency_key="short",
            password="Secret123!",
        )


@pytest.mark.asyncio
async def test_polygon_adapter_raises_not_implemented():
    adapter = get_adapter(Chain.POLYGON)
    with pytest.raises(ChainNotImplementedError, match="Polygon"):
        await adapter.quote_native()
    with pytest.raises(ChainNotImplementedError, match="Polygon"):
        await adapter.verify_deposit()
    with pytest.raises(ChainNotImplementedError, match="Polygon"):
        await adapter.send_native()
    with pytest.raises(ChainNotImplementedError, match="Polygon"):
        await adapter.send_usdc()


@pytest.mark.asyncio
async def test_solana_adapter_quote_native_delegates_to_pricing():
    adapter = get_adapter(Chain.SOLANA)
    redis = AsyncMock()
    priced = {
        "lamports": 1_000_000_000,
        "price": "100.0",
        "fee": "0.015",
        "price_source": "pyth:SOL/USD",
    }
    with patch(
        "Backend.Wallet.rails.solana.quote_buy_lamports",
        new_callable=AsyncMock,
        return_value=priced,
    ) as quote:
        result = await adapter.quote_native(credits=10, redis=redis)

    quote.assert_awaited_once_with(10, redis)
    assert result == priced


@pytest.mark.asyncio
async def test_solana_adapter_verify_deposit_delegates_to_wallet_service():
    adapter = get_adapter(Chain.SOLANA)
    session = MagicMock()
    with patch(
        "Backend.Wallet.rails.solana.WalletService"
    ) as service_cls:
        service_cls.return_value.process_deposit_signature = AsyncMock()
        await adapter.verify_deposit(session=session, signature="sig123")

    service_cls.assert_called_once_with(session)
    service_cls.return_value.process_deposit_signature.assert_awaited_once_with(
        "sig123"
    )


@pytest.mark.asyncio
async def test_solana_adapter_send_delegates_to_builders():
    adapter = get_adapter(Chain.SOLANA)
    signed = (b"raw", "sig", 100)
    with patch(
        "Backend.Wallet.rails.solana.build_signed_sol_transfer",
        new_callable=AsyncMock,
        return_value=signed,
    ) as sol:
        assert await adapter.send_native(destination=VALID_DEST, lamports=1_000_000) == signed
    sol.assert_awaited_once()

    with patch(
        "Backend.Wallet.rails.solana.build_signed_usdc_transfer",
        new_callable=AsyncMock,
        return_value=signed,
    ) as usdc:
        assert (
            await adapter.send_usdc(destination=VALID_DEST, amount_units=1_000_000)
            == signed
        )
    usdc.assert_awaited_once()


@pytest.mark.asyncio
async def test_assert_withdraw_destination_rejects_wsol_mint():
    """wSOL mint is a valid pubkey but not a system wallet — finding 5."""
    from Backend.Core.core_solana import assert_solana_withdraw_destination

    account = MagicMock()
    # Token program owns the mint account (not System Program)
    account.owner = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
    account.executable = False

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_account_info.return_value.value = account

    with (
        patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client),
        patch(
            "Backend.Core.core_solana.settings",
            SOLANA_HOT_WALLET_ADDRESS=HOUSE_HOT,
            SOLANA_COLD_RECEIVE_ADDRESS=HOUSE_COLD,
            SOLANA_RPC_URL="http://localhost",
            SOLANA_USDC_MINT="4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
        ),
    ):
        with pytest.raises(ValueError, match="system account"):
            await assert_solana_withdraw_destination(
                destination=WSOL_MINT,
                asset=WithdrawAsset.SOL,
            )
