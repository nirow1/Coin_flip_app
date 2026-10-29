import asyncio
import logging
from datetime import UTC, datetime, timedelta

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Finalized
from solders.pubkey import Pubkey
from solders.signature import Signature
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from Backend.config import settings
from Backend.Wallet.enums import Chain, CreditOrderStatus
from Backend.Wallet.models import ChainCursor, CreditOrder
from Backend.Wallet.services import WalletService

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 15.0
_RPC_TIMEOUT_SEC = 10.0
_SIG_PAGE_LIMIT = 1000
EXPIRY_INTERVAL_S = 60.0
ORDER_EXPIRY_GRACE = timedelta(minutes=15)


async def _collect_signatures_after_cursor(
    client: AsyncClient,
    cold_address: Pubkey,
    until: Signature | None,
) -> list[str]:
    """Newest-first pages from RPC → return oldest-first signature strings.

    `until` is the last processed sig: RPC returns only newer ones (excludes `until`).
    """
    collected = []
    before: Signature | None = None

    while True:
        response = await client.get_signatures_for_address(
            cold_address,
            before=before,
            until=until,
            limit=_SIG_PAGE_LIMIT,
            commitment=Finalized,
        )
        batch = list(response.value or [])
        if not batch:
            break
        collected.extend(batch)
        if len(batch) < _SIG_PAGE_LIMIT:
            break
        before = batch[-1].signature

    collected.reverse()
    return [str(item.signature) for item in collected]


async def _get_or_create_solana_cursor(session: AsyncSession) -> ChainCursor:
    result = await session.execute(
        select(ChainCursor).where(ChainCursor.chain == Chain.SOLANA)
    )
    cursor = result.scalar_one_or_none()
    if cursor is not None:
        return cursor
    cursor = ChainCursor(chain=Chain.SOLANA, last_signature=None, last_block=None)
    session.add(cursor)
    await session.flush()
    return cursor


async def run_cold_deposit_poller(session_factory: async_sessionmaker) -> None:
    """Leader-only cold-address watcher. One session commit per signature."""
    cold = Pubkey.from_string(settings.SOLANA_COLD_RECEIVE_ADDRESS)

    while True:
        try:
            async with AsyncClient(
                settings.SOLANA_RPC_URL, timeout=_RPC_TIMEOUT_SEC
            ) as client:
                async with session_factory() as session:
                    cursor = await _get_or_create_solana_cursor(session)
                    await session.commit()

                until = (
                    Signature.from_string(cursor.last_signature)
                    if cursor.last_signature
                    else None
                )
                sigs = await _collect_signatures_after_cursor(
                    client,
                    cold,
                    until,
                )

                # First-ever watermark: skip replaying the entire cold history.
                if until is None and sigs:
                    newest = sigs[-1]
                    async with session_factory() as session:
                        cursor = await _get_or_create_solana_cursor(session)
                        cursor.last_signature = newest
                        cursor.updated_at = datetime.now(UTC)
                        await session.commit()
                    logger.info(
                        "solana cursor bootstrapped at %s (%d prior sigs skipped)",
                        newest,
                        len(sigs),
                    )
                else:
                    for sig in sigs:
                        async with session_factory() as session:
                            service = WalletService(session)
                            await service.process_deposit_signature(sig)
                            cursor = await _get_or_create_solana_cursor(session)
                            cursor.last_signature = sig
                            cursor.updated_at = datetime.now(UTC)
                            await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("cold deposit poller tick failed")

        await asyncio.sleep(POLL_INTERVAL_S)


async def run_order_expiry_job(session_factory: async_sessionmaker) -> None:
    """Mark PENDING credit orders EXPIRED once past expires_at + grace."""
    while True:
        try:
            async with session_factory() as session:
                cutoff = datetime.now(UTC) - ORDER_EXPIRY_GRACE
                result = await session.execute(
                    update(CreditOrder)
                    .where(
                        CreditOrder.status == CreditOrderStatus.PENDING,
                        CreditOrder.expires_at < cutoff,
                    )
                    .values(status=CreditOrderStatus.EXPIRED)
                )
                await session.commit()
                if result.rowcount:
                    logger.info("expired %s pending credit order(s)", result.rowcount)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("order expiry job tick failed")

        await asyncio.sleep(EXPIRY_INTERVAL_S)
