from redis.asyncio import Redis

from Backend.config import settings

redis_client = Redis(
    settings.REDIS_URL,
    decode_responses=True,
)

async def get_redis() -> Redis:
    return redis_client
