"""Pricing: Pyth staleness/confidence rejects and ceil lamports math."""

from __future__ import annotations

import time
from decimal import ROUND_CEILING, Decimal
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from Backend.Wallet import pricing
from Backend.Wallet.pricing import (
    MAX_CONF_RATIO,
    MAX_STALE_SEC,
    SPREAD,
    SWAP_BUFFER,
    _parse_sol_usd,
    quote_buy_lamports,
)


def _pyth_entry(
    *,
    price: int = 100_000_000,
    conf: int = 100_000,
    expo: int = -6,
    publish_time: int | None = None,
) -> dict:
    return {
        "price": {
            "price": str(price),
            "conf": str(conf),
            "expo": expo,
            "publish_time": publish_time if publish_time is not None else int(time.time()),
        }
    }


def test_parse_sol_usd_rejects_stale_price():
    entry = _pyth_entry(publish_time=int(time.time()) - (MAX_STALE_SEC + 5))
    with pytest.raises(ValueError, match="Stale"):
        _parse_sol_usd(entry)


def test_parse_sol_usd_rejects_wide_confidence():
    # conf/price > 1%
    price = 100_000_000  # $100 with expo -6
    conf = int(price * (MAX_CONF_RATIO + Decimal("0.001")))
    entry = _pyth_entry(price=price, conf=conf)
    with pytest.raises(ValueError, match="Confidence"):
        _parse_sol_usd(entry)


def test_parse_sol_usd_accepts_fresh_tight_price():
    entry = _pyth_entry(price=150_000_000, conf=50_000)  # $150, conf $0.05
    parsed = _parse_sol_usd(entry)
    assert parsed["price"] == Decimal("150")
    assert parsed["published_time"] == entry["price"]["publish_time"]


@pytest.mark.asyncio
async def test_quote_buy_lamports_rounds_up():
    """ceil(credits * (1+fee) / price * 1e9) — fractional lamports must round up."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()

    # Use price 99.99 so credits*multiplier/price*1e9 is not an integer.
    price = Decimal("99.99")
    fee = SPREAD + SWAP_BUFFER
    raw = Decimal(1) * (Decimal(1) + fee) / price * Decimal("1e9")
    assert raw != raw.to_integral_value()

    with patch(
        "Backend.Wallet.pricing.get_sol_usd_price",
        new_callable=AsyncMock,
        return_value={"price": price, "published_time": int(time.time())},
    ):
        result = await quote_buy_lamports(1, redis)

    expected = int(raw.to_integral_value(rounding=ROUND_CEILING))
    assert result["lamports"] == expected
    assert result["lamports"] == int(raw) + 1  # must have rounded up
    assert result["price"] == str(price)
    assert result["fee"] == str(fee)
    assert result["price_source"] == pricing.PRICE_SOURCE


@pytest.mark.asyncio
async def test_get_sol_usd_price_fail_closed_on_fetch_error():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)

    with patch(
        "Backend.Wallet.pricing._fetch_sol_usd_from_pyth",
        new_callable=AsyncMock,
        side_effect=RuntimeError("hermes down"),
    ):
        with pytest.raises(HTTPException) as exc:
            await pricing.get_sol_usd_price(redis)

    assert exc.value.status_code == 503
    assert "oracle" in str(exc.value.detail).lower()
