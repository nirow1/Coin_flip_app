from decimal import Decimal

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
    req = CreateOrderRequest(quote_id="abc-123")
    assert req.quote_id == "abc-123"
    assert set(CreateOrderRequest.model_fields.keys()) == {"quote_id"}


def test_create_order_rejects_missing_quote_id():
    with pytest.raises(ValidationError):
        CreateOrderRequest()


def test_withdraw_quote_rejects_below_min():
    with pytest.raises(ValidationError):
        WithdrawQuoteRequest(
            credits=Decimal("9.99"),
            asset=WithdrawAsset.SOL,
            destination="SomePubkey",
            chain=Chain.SOLANA,
        )


def test_withdraw_quote_rejects_three_decimal_places():
    with pytest.raises(ValidationError):
        WithdrawQuoteRequest(
            credits=Decimal("0.001"),
            asset=WithdrawAsset.SOL,
            destination="SomePubkey",
            chain=Chain.SOLANA,
        )


def test_withdraw_quote_accepts_two_decimals():
    req = WithdrawQuoteRequest(
        credits=Decimal("10.25"),
        asset=WithdrawAsset.USDC,
        destination="SomePubkey",
        chain=Chain.SOLANA,
    )
    assert req.credits == Decimal("10.25")


def test_withdraw_request_has_no_amount_fields():
    req = WithdrawRequest(quote_id="q1", idempotency_key="idem-1")
    assert set(WithdrawRequest.model_fields.keys()) == {"quote_id", "idempotency_key"}
    assert req.quote_id == "q1"


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
