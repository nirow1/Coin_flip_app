from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from Backend.config import settings
from Backend.Core.core_solana import (
    build_signed_sol_transfer,
    build_signed_usdc_transfer,
)
from Backend.Wallet.pricing import quote_buy_lamports
from Backend.Wallet.rails.base import ChainAdapter
from Backend.Wallet.services import WalletService


class SolanaAdapter(ChainAdapter):
    """Live Solana rail — pricing + deposit verify; send lands in withdraw work."""

    async def quote_native(
        self, *, credits: int, redis: Redis, **kwargs: Any
    ) -> dict[str, Any]:
        return await quote_buy_lamports(credits, redis)

    async def verify_deposit(
        self, *, session: AsyncSession, signature: str, **kwargs: Any
    ) -> None:
        await WalletService(session).process_deposit_signature(signature)

    async def send_native(
        self, *, destination: str, lamports: int, **kwargs: Any
    ) -> tuple[bytes, str, int]:
        return await build_signed_sol_transfer(
            destination_address=destination,
            lamports=lamports,
            rpc_url=settings.SOLANA_RPC_URL,
        )

    async def send_usdc(
        self, *, destination: str, amount_units: int, **kwargs: Any
    ) -> tuple[bytes, str, int]:
        return await build_signed_usdc_transfer(
            destination_owner=destination,
            amount_units=amount_units,
            rpc_url=settings.SOLANA_RPC_URL,
        )
