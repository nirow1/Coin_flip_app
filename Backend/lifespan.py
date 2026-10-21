import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from Backend.Core.core_solana import (
    SolanaClusterMismatchError,
    assert_solana_cluster_matches_rpc,
    validate_solana_web_settings,
)
from Backend.Core.leader_lock import LeaderLock, run_if_leader
from Backend.Core.redis_config import create_redis_client
from Backend.db import SessionLocal, init_db
from Backend.Game.engine import GameEngine

logger = logging.getLogger(__name__)

_SOLANA_RECOVERY_INTERVAL_SEC = 45.0


async def _recover_solana_payments(app: FastAPI) -> None:
    """Re-check RPC while payments are disabled; enable once the check passes."""
    while not getattr(app.state, "solana_payments_enabled", False):
        try:
            await assert_solana_cluster_matches_rpc()
            app.state.solana_payments_enabled = True
            logger.info("Solana RPC recovered; payments enabled")
            return
        except SolanaClusterMismatchError:
            # Config error — do not keep retrying or flip the flag on.
            logger.error(
                "Solana cluster mismatch during recovery; payments stay disabled"
            )
            return
        except Exception as exc:
            logger.warning(
                "Solana RPC still unavailable; payments disabled: %s", exc
            )
        await asyncio.sleep(_SOLANA_RECOVERY_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Local Solana config (no hot keypair). RPC outage → payments disabled + recovery.
    # Genesis mismatch is fatal (wrong cluster config).
    validate_solana_web_settings()
    solana_recovery_task: asyncio.Task | None = None
    try:
        await assert_solana_cluster_matches_rpc()
        app.state.solana_payments_enabled = True
    except SolanaClusterMismatchError:
        raise
    except Exception as exc:
        logger.error("Solana RPC unavailable at startup; payments disabled: %s", exc)
        app.state.solana_payments_enabled = False
        solana_recovery_task = asyncio.create_task(_recover_solana_payments(app))

    # Initialize the database on startup
    await init_db()

    # Start background schedulers
    redis_client = await create_redis_client()
    pubsub = redis_client.pubsub()
    engine = GameEngine(SessionLocal, redis_client, pubsub)
    lock = LeaderLock(redis_client, key="scheduler:leader", ttl_ms=10_000)
    leader_task = asyncio.create_task(run_if_leader(lock, engine))

    yield

    # Cancel schedulers on shutdown; run_if_leader releases the lock if we hold it.
    if solana_recovery_task is not None:
        solana_recovery_task.cancel()
    leader_task.cancel()
    await asyncio.gather(
        leader_task,
        *((solana_recovery_task,) if solana_recovery_task is not None else ()),
        return_exceptions=True,
    )
    await pubsub.unsubscribe()
    await pubsub.aclose()
    await redis_client.aclose()
