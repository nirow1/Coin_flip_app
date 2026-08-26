from redis.asyncio import Redis
from Backend.config import settings


async def create_redis_client() -> Redis:
    """
    Creates and configures a Redis client.
    Enables keyspace expiration events (Kx) required by showdown_scheduler.
    """
    client = Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True
    )

    # Enable keyspace notifications for expired events.
    # K = Keyspace events, x = expired events.
    # Managed Redis (e.g. Railway) may disallow CONFIG SET — don't block boot.
    try:
        await client.config_set("notify-keyspace-events", "Kx")
    except Exception:
        pass

    return client

