import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from Backend.worker import main

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.mark.asyncio
async def test_worker_main_validates_payout_settings_and_uses_payments_leader_key():
    """Worker must load hot-key settings and lock under payments:leader (not scheduler)."""
    seen: dict = {}
    started = asyncio.Event()

    async def fake_run_if_leader(lock, factories):
        seen["lock_key"] = lock.key
        seen["factories"] = list(factories)
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            raise

    mock_redis = AsyncMock()
    mock_redis.aclose = AsyncMock()

    with (
        patch("Backend.worker.validate_solana_web_settings") as web,
        patch("Backend.worker.validate_solana_payout_settings") as payout,
        patch(
            "Backend.worker.assert_solana_cluster_matches_rpc",
            new_callable=AsyncMock,
        ) as genesis,
        patch("Backend.worker.init_db", new_callable=AsyncMock) as init_db,
        patch(
            "Backend.worker.create_redis_client",
            new_callable=AsyncMock,
            return_value=mock_redis,
        ),
        patch("Backend.worker.run_if_leader", side_effect=fake_run_if_leader),
    ):
        task = asyncio.create_task(main())
        await started.wait()

        web.assert_called_once_with()
        payout.assert_called_once_with()
        genesis.assert_awaited_once_with()
        init_db.assert_awaited_once_with()
        assert seen["lock_key"] == "payments:leader"
        assert len(seen["factories"]) == 2
        assert all(callable(f) for f in seen["factories"])

        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    mock_redis.aclose.assert_awaited()


@pytest.mark.asyncio
async def test_worker_main_does_not_start_if_payout_validation_fails():
    with (
        patch("Backend.worker.validate_solana_web_settings"),
        patch(
            "Backend.worker.validate_solana_payout_settings",
            side_effect=RuntimeError("hot key mismatch"),
        ),
        patch(
            "Backend.worker.assert_solana_cluster_matches_rpc",
            new_callable=AsyncMock,
        ) as genesis,
        patch("Backend.worker.init_db", new_callable=AsyncMock) as init_db,
        patch("Backend.worker.create_redis_client", new_callable=AsyncMock) as redis,
        patch("Backend.worker.run_if_leader", new_callable=AsyncMock) as run_leader,
    ):
        with pytest.raises(RuntimeError, match="hot key mismatch"):
            await main()

        genesis.assert_not_awaited()
        init_db.assert_not_awaited()
        redis.assert_not_awaited()
        run_leader.assert_not_awaited()


@pytest.mark.asyncio
async def test_worker_main_does_not_start_if_genesis_check_fails():
    with (
        patch("Backend.worker.validate_solana_web_settings"),
        patch("Backend.worker.validate_solana_payout_settings"),
        patch(
            "Backend.worker.assert_solana_cluster_matches_rpc",
            new_callable=AsyncMock,
            side_effect=RuntimeError("cluster mismatch"),
        ),
        patch("Backend.worker.init_db", new_callable=AsyncMock) as init_db,
        patch("Backend.worker.create_redis_client", new_callable=AsyncMock) as redis,
        patch("Backend.worker.run_if_leader", new_callable=AsyncMock) as run_leader,
    ):
        with pytest.raises(RuntimeError, match="cluster mismatch"):
            await main()

        init_db.assert_not_awaited()
        redis.assert_not_awaited()
        run_leader.assert_not_awaited()
