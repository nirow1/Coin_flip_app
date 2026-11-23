import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Finalized
from solders.pubkey import Pubkey
from solders.signature import Signature
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from Backend.config import settings
from Backend.Core.core_solana import (
    SendFailedOnChain,
    SendFailedRefundable,
    SentUnconfirmed,
    broadcast_and_confirm,
)
from Backend.Wallet.enums import (
    Chain,
    CreditOrderStatus,
    TransactionType,
    WithdrawalStatus,
    WithdrawAsset,
)
from Backend.Wallet.models import ChainCursor, CreditOrder, Withdrawal
from Backend.Wallet.rails import get_adapter
from Backend.Wallet.services import WalletService

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 15.0
_RPC_TIMEOUT_SEC = 10.0
_SIG_PAGE_LIMIT = 1000
EXPIRY_INTERVAL_S = 60.0
ORDER_EXPIRY_GRACE = timedelta(minutes=15)
WITHDRAW_SENDER_INTERVAL_S = 5.0
WITHDRAW_RECONCILE_INTERVAL_S = 15.0


async def _reconcile_withdrawal(session: AsyncSession, withdrawal: Withdrawal) -> None:
    """Apply finding-2 rules to a SIGNED or BROADCAST row. CAS status updates only."""
    if not withdrawal.signature or withdrawal.last_valid_block_height is None:
        await session.execute(
            update(Withdrawal)
            .where(
                Withdrawal.id == withdrawal.id,
                Withdrawal.status.in_(
                    [WithdrawalStatus.SIGNED, WithdrawalStatus.BROADCAST]
                ),
            )
            .values(
                status=WithdrawalStatus.NEEDS_REVIEW,
                updated_at=datetime.now(UTC),
            )
        )
        logger.error("withdrawal %s missing signature/height → needs_review", withdrawal.id)
        return
    sig = Signature.from_string(withdrawal.signature)
    async with AsyncClient(
        settings.SOLANA_RPC_URL, timeout=_RPC_TIMEOUT_SEC
    ) as client:
        try:
            status_resp = await client.get_signature_statuses(
                [sig],
                search_transaction_history=True,
            )
            statuses = status_resp.value or []
            on_chain = statuses[0] if statuses else None
        except Exception:
            await session.execute(
                update(Withdrawal)
                .where(
                    Withdrawal.id == withdrawal.id,
                    Withdrawal.status.in_(
                        [WithdrawalStatus.SIGNED, WithdrawalStatus.BROADCAST]
                    ),
                )
                .values(
                    status=WithdrawalStatus.NEEDS_REVIEW,
                    updated_at=datetime.now(UTC),
                )
            )
            logger.exception(
                "withdrawal %s status RPC failed → needs_review", withdrawal.id
            )
            return

        if on_chain is not None:
            if getattr(on_chain, "err", None) is not None:
                await _refund_withdrawal(session, withdrawal)
                return
            # Landed OK
            await session.execute(
                update(Withdrawal)
                .where(
                    Withdrawal.id == withdrawal.id,
                    Withdrawal.status.in_(
                        [WithdrawalStatus.SIGNED, WithdrawalStatus.BROADCAST]
                    ),
                )
                .values(
                    status=WithdrawalStatus.CONFIRMED,
                    confirmed_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            return
        
        try:
            height_resp = await client.get_block_height()
            current_height = int(height_resp.value)
        except Exception:
            await session.execute(
                update(Withdrawal)
                .where(
                    Withdrawal.id == withdrawal.id,
                    Withdrawal.status.in_(
                        [WithdrawalStatus.SIGNED, WithdrawalStatus.BROADCAST]
                    ),
                )
                .values(
                    status=WithdrawalStatus.NEEDS_REVIEW,
                    updated_at=datetime.now(UTC),
                )
            )
            logger.exception(
                "withdrawal %s block height RPC failed → needs_review", withdrawal.id
            )
            return

        if current_height > int(withdrawal.last_valid_block_height):
            await _refund_withdrawal(session, withdrawal)
            return

        # Still inside blockhash window and absent — wait (sender may rebroadcast SIGNED)
        logger.info(
            "withdrawal %s still pending (height %s <= %s)",
            withdrawal.id,
            current_height,
            withdrawal.last_valid_block_height,
        )
        

async def _refund_withdrawal(session: AsyncSession, withdrawal: Withdrawal) -> None:
    """CAS to FAILED_REFUNDED and credit the user. Never call if funds may be in flight."""
    result = await session.execute(
        update(Withdrawal)
        .where(
            Withdrawal.id == withdrawal.id,
            Withdrawal.status.in_(
                [WithdrawalStatus.SIGNED, WithdrawalStatus.BROADCAST]
            ),
        )
        .values(
            status=WithdrawalStatus.FAILED_REFUNDED,
            updated_at=datetime.now(UTC),
        )
    )
    if result.rowcount != 1:
        return

    service = WalletService(session)
    await service.credit(
        withdrawal.user_id,
        Decimal(str(withdrawal.credits_debited)),
        transaction_type=TransactionType.REFUND,
        tx_hash=f"withdraw-refund:{withdrawal.id}",
    )
    logger.info("withdrawal %s refunded", withdrawal.id)


async def run_withdraw_reconciler(session_factory: async_sessionmaker) -> None:
    """Reconcile SIGNED/BROADCAST withdrawals. Skips while WITHDRAWALS_ENABLED is False."""
    while True:
        try:
            if not settings.WITHDRAWALS_ENABLED:
                await asyncio.sleep(WITHDRAW_RECONCILE_INTERVAL_S)
                continue

            async with session_factory() as session:
                rows = (
                    await session.scalars(
                        select(Withdrawal)
                        .where(
                            Withdrawal.status.in_(
                                [
                                    WithdrawalStatus.SIGNED,
                                    WithdrawalStatus.BROADCAST,
                                ]
                            )
                        )
                        .order_by(Withdrawal.id.asc())
                        .limit(20)
                    )
                ).all()
                for row in rows:
                    await _reconcile_withdrawal(session, row)
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("withdraw reconciler tick failed")
            
        await asyncio.sleep(WITHDRAW_RECONCILE_INTERVAL_S)


async def _persist_signed_withdrawal(session: AsyncSession, withdrawal: Withdrawal) -> bool:
    """Sign a QUEUED row and CAS to SIGNED. Returns False if CAS lost."""
    adapter = get_adapter(withdrawal.chain)
    if withdrawal.asset == WithdrawAsset.SOL:
        raw_tx, signature, last_valid = await adapter.send_native(
            destination=withdrawal.destination,
            lamports=int(withdrawal.net_atomic_amount),
        )
    else:
        raw_tx, signature, last_valid = await adapter.send_usdc(
            destination=withdrawal.destination,
            amount_units=int(withdrawal.net_atomic_amount),
        )
    result = await session.execute(
        update(Withdrawal)
        .where(
            Withdrawal.id == withdrawal.id,
            Withdrawal.status == WithdrawalStatus.QUEUED,
        )
        .values(
            status=WithdrawalStatus.SIGNED,
            raw_tx=raw_tx,
            signature=signature,
            last_valid_block_height=last_valid,
            updated_at=datetime.now(UTC),
        )
    )
    return result.rowcount == 1


async def _broadcast_persisted_withdrawal(session: AsyncSession, withdrawal: Withdrawal) -> None:
    """Broadcast already-persisted bytes; CAS SIGNED → BROADCAST/CONFIRMED."""
    if not withdrawal.raw_tx or not withdrawal.signature or withdrawal.last_valid_block_height is None:
        logger.error("withdrawal %s SIGNED but missing raw_tx/signature/height", withdrawal.id)
        return
    
    try:
        await broadcast_and_confirm(
            raw_bytes=bytes(withdrawal.raw_tx),
            signature=withdrawal.signature,
            last_valid_block_height=int(withdrawal.last_valid_block_height),
            rpc_url=settings.SOLANA_RPC_URL,
        )
        new_status = WithdrawalStatus.CONFIRMED
        confirmed_at = datetime.now(UTC)
    except SentUnconfirmed:
        new_status = WithdrawalStatus.BROADCAST
        confirmed_at = None
        logger.warning("withdrawal %s broadcast unconfirmed; reconciler will follow", withdrawal.id)
    except (SendFailedOnChain, SendFailedRefundable) as exc:
        # Leave SIGNED — Piece I reconciler decides refund vs needs_review
        logger.warning("withdrawal %s send failed (%s); leaving SIGNED for reconciler", withdrawal.id, exc)
        return
    
    values: dict = {
        "status": new_status,
        "updated_at": datetime.now(UTC),
    }
    if confirmed_at is not None:
        values["confirmed_at"] = confirmed_at
    
    await session.execute(
        update(Withdrawal)
        .where(
            Withdrawal.id == withdrawal.id,
            Withdrawal.status == WithdrawalStatus.SIGNED,
        )
        .values(**values)
    )


async def run_withdraw_sender(session_factory: async_sessionmaker) -> None:
    """Sign → persist → commit → broadcast. Skips while WITHDRAWALS_ENABLED is False."""
    while True:
        try:
            if not settings.WITHDRAWALS_ENABLED:
                await asyncio.sleep(WITHDRAW_SENDER_INTERVAL_S)
                continue

            async with session_factory() as session:
                # Crash recovery: finish broadcast for already-SIGNED rows first
                signed = await session.scalar(
                    select(Withdrawal)
                    .where(Withdrawal.status == WithdrawalStatus.SIGNED)
                    .order_by(Withdrawal.id.asc())
                    .limit(1)
                )
                if signed is not None:
                    await _broadcast_persisted_withdrawal(session, signed)
                    await session.commit()
                    continue

                queued = await session.scalar(
                    select(Withdrawal)
                    .where(Withdrawal.status == WithdrawalStatus.QUEUED)
                    .order_by(Withdrawal.id.asc())
                    .limit(1)
                )
                if queued is None:
                    await session.commit()
                else:
                    # Detach ids/fields we need after sign (RPC outside long locks)
                    wid = queued.id
                    claimed = await _persist_signed_withdrawal(session, queued)
                    if not claimed:
                        await session.rollback()
                    else:
                        await session.commit()
                        async with session_factory() as session2:
                            row = await session2.scalar(
                                select(Withdrawal).where(Withdrawal.id == wid)
                            )
                            if row is not None and row.status == WithdrawalStatus.SIGNED:
                                await _broadcast_persisted_withdrawal(session2, row)
                                await session2.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("withdraw sender tick failed")
        await asyncio.sleep(WITHDRAW_SENDER_INTERVAL_S)

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
