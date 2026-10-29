import asyncio
import logging

from Backend.Core.core_solana import (
    assert_solana_cluster_matches_rpc,
    validate_solana_payout_settings,
    validate_solana_web_settings,
)
from Backend.Core.leader_lock import LeaderLock, run_if_leader
from Backend.Core.redis_config import create_redis_client
from Backend.db import SessionLocal, init_db
from Backend.Wallet.jobs import run_cold_deposit_poller, run_order_expiry_job

logger = logging.getLogger(__name__)


async def main() -> None:
    validate_solana_web_settings()
    validate_solana_payout_settings()  # loads hot keypair — worker only
    await assert_solana_cluster_matches_rpc()  # fatal on mismatch / unreachable

    await init_db()

    redis_client = await create_redis_client()
    lock = LeaderLock(redis_client, key="payments:leader", ttl_ms=10_000)

    factories = [
        lambda: run_cold_deposit_poller(SessionLocal),
        lambda: run_order_expiry_job(SessionLocal),
    ]

    leader_task = asyncio.create_task(run_if_leader(lock, factories))
    try:
        await leader_task
    except asyncio.CancelledError:  # noqa: TRY203
        raise
    finally:
        if not leader_task.done():
            leader_task.cancel()
            await asyncio.gather(leader_task, return_exceptions=True)
        await redis_client.aclose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())