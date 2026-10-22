from __future__ import annotations

import json
import time
from decimal import ROUND_CEILING, Decimal
from typing import TypedDict

import httpx
from fastapi import HTTPException, status
from redis.asyncio import Redis

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
            