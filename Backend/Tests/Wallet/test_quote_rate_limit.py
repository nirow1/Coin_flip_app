"""Quote rate limit: INCR and EXPIRE NX happen in one Redis transaction."""

from __future__ import annotations

import fakeredis.aioredis as fakeredis
import pytest
from fastapi import HTTPException

from Backend.Wallet.router import _enforce_quote_rate_limit
from Backend.Wallet.schemas import QUOTE_RATE_LIMIT, QUOTE_RATE_WINDOW_SEC

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_quote_rate_limit_sets_ttl_with_first_incr():
    redis = fakeredis.FakeRedis(decode_responses=True)
    await _enforce_quote_rate_limit(redis, user_id=7)

    ttl = await redis.ttl("rate:wallet:quote:7")
    assert 0 < ttl <= QUOTE_RATE_WINDOW_SEC

    # Shorten the TTL. A second hit must not start a new full window.
    await redis.expire("rate:wallet:quote:7", 5)
    await _enforce_quote_rate_limit(redis, user_id=7)
    ttl_after = await redis.ttl("rate:wallet:quote:7")
    assert 0 < ttl_after <= 5


async def test_quote_rate_limit_blocks_past_cap_and_keeps_ttl():
    redis = fakeredis.FakeRedis(decode_responses=True)
    for _ in range(QUOTE_RATE_LIMIT):
        await _enforce_quote_rate_limit(redis, user_id=8)

    with pytest.raises(HTTPException) as exc:
        await _enforce_quote_rate_limit(redis, user_id=8)
    assert exc.value.status_code == 429
    assert await redis.ttl("rate:wallet:quote:8") > 0
