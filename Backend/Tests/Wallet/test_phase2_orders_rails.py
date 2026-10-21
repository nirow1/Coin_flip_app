from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic import ValidationError

from Backend.Wallet.enums import Chain, WithdrawAsset
from Backend.Wallet.rails import get_adapter
from Backend.Wallet.rails.base import ChainNotImplementedError
from Backend.Wallet.schemas import (
    CreateOrderRequest,
    CreditsQuoteRequest,
    WithdrawQuoteRequest,
    WithdrawRequest,
)

# Valid base58 pubkey that is not the wrapped-SOL mint alone (still a real Pubkey).
VALID_DEST = "So11111111111111111111111111111111111111112"
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
    req = WithdrawRequest(quote_id=qid, idempotency_key="idem-key-16chars")
    assert set(WithdrawRequest.model_fields.keys()) == {"quote_id", "idempotency_key"}
    assert req.quote_id == qid


def test_withdraw_request_rejects_short_idempotency_key():
    with pytest.raises(ValidationError):
        WithdrawRequest(quote_id=uuid4(), idempotency_key="short")


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
async def test_solana_adapter_stub_raises_not_implemented():
    adapter = get_adapter(Chain.SOLANA)
    with pytest.raises(NotImplementedError):
        await adapter.quote_native()
