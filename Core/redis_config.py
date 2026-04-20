from redis.asyncio import Redis
from config import settings


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
    # K = Keyspace events, x = expired events
    await client.config_set("notify-keyspace-events", "Kx")

    return client

