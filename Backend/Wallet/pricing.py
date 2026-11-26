from __future__ import annotations

import json
import time
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import TypedDict

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis

from Backend.Core.core_solana import SYSTEM_ACCOUNT_RENT_EXEMPT_LAMPORTS
from Backend.config import settings
from Backend.Wallet.enums import WithdrawAsset

# pyth SOL/USD
PYTH_HERMES_URL = "https://hermes.pyth.network/v2/updates/price/latest"
SOL_USD_FEED_ID = (
    "0xef0d8b6fda2ceba41da15d4095d1da392a0d2f8ed0c6c7bc0f4cfac8c280b56d"
)

MAX_STALE_SEC = 60
MAX_CONF_RATIO = Decimal("0.01") 
CACHE_KEY = "oracle:sol_usd"
CACHE_TTL_SEC = 10

# Buy buffer so the quote is not a free option (tune later if needed)
SPREAD = Decimal("0.01")        # 1%
SWAP_BUFFER = Decimal("0.005")  # 0.5%
PRICE_SOURCE = "pyth:SOL/USD"

USDC_DECIMALS = 6
LAMPORTS_PER_SOL_INT = 1_000_000_000

class SolUsdPrice(TypedDict):
    price: Decimal
    published_time: int


async def quote_buy_lamports(credits: int, redis: Redis) -> dict:
    sol = await get_sol_usd_price(redis)
    price = sol["price"]
    fee = SPREAD + SWAP_BUFFER
    multiplier = Decimal(1) + fee

    lamports = (
        Decimal(credits) * multiplier / price * Decimal("1e9")
    ).to_integral_value(rounding=ROUND_CEILING)
    
    return {
        "lamports": int(lamports),
        "price": str(price),
        "fee": str(fee),
        "price_source": PRICE_SOURCE,
    }


async def quote_withdraw_atomic(
    *,
    credits: Decimal,
    asset: WithdrawAsset,
    redis: Redis,
) -> dict:
    fee = settings.WITHDRAW_FEE_CREDITS
    if credits <= fee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="credits must exceed withdraw fee",
        )
    net_credits = credits - fee
    if asset == WithdrawAsset.SOL:
        sol = await get_sol_usd_price(redis)
        price = sol["price"]
        # Floor: never send more SOL than credits warrant
        lamports = (
            net_credits / price * Decimal(LAMPORTS_PER_SOL_INT)
        ).to_integral_value(rounding=ROUND_FLOOR)
        if int(lamports) < SYSTEM_ACCOUNT_RENT_EXEMPT_LAMPORTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="net SOL below rent-exempt minimum",
            )
        return {
            "net_atomic": int(lamports),
            "fee_credits": str(fee),
            "net_credits": str(net_credits),
            "price": str(price),
            "price_source": PRICE_SOURCE,
        }
     # USDC: 1 credit = $1 = 1 USDC (6 decimals)
    units = (net_credits * Decimal(10**USDC_DECIMALS)).to_integral_value(
        rounding=ROUND_FLOOR
    )
    if int(units) <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="net USDC amount is zero",
        )
    return {
        "net_atomic": int(units),
        "fee_credits": str(fee),
        "net_credits": str(net_credits),
        "price": "1",
        "price_source": "peg:USDC",
    }


async def get_sol_usd_price(redis: Redis) -> SolUsdPrice:
    cached = await redis.get(CACHE_KEY)

    if cached:
        obj = json.loads(cached)
        return SolUsdPrice(price=Decimal(obj["price"]),
                           published_time=int(obj["published_time"]))

    try:
        sol_usd = await _fetch_sol_usd_from_pyth()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Price oracle unavailable",
        ) from e

    await redis.set(
        CACHE_KEY,
        json.dumps(
            {
                "price": str(sol_usd["price"]),
                "published_time": sol_usd["published_time"],
            }
        ),
        ex=CACHE_TTL_SEC,
    )
    return sol_usd


async def _fetch_sol_usd_from_pyth() -> SolUsdPrice:
    params = [("ids[]", SOL_USD_FEED_ID)]
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(PYTH_HERMES_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    parsed = data.get("parsed") or []
    if not parsed:
        raise ValueError("empty parsed price feeds")
    return _parse_sol_usd(parsed[0])


def _parse_sol_usd(entry: dict) -> SolUsdPrice:
    p = entry["price"]
    raw_price = Decimal(str(p["price"]))
    raw_conf = Decimal(str(p["conf"]))
    expo = int(p["expo"])
    published_time = int(p["publish_time"])

    scale = Decimal(10) ** expo
    price = raw_price * scale
    conf = raw_conf * scale

    if price <= 0:
        raise ValueError(f"Non positive price: {price}")

    age = time.time() - published_time
    if age > MAX_STALE_SEC:
        raise ValueError(f"Stale price: {age:.0f}s")

    if conf / price > MAX_CONF_RATIO:
        raise ValueError("Confidence too wide")

    return SolUsdPrice(price=price, published_time=published_time)
            