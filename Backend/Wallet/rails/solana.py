from typing import Any

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

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

    async def send_native(self, **kwargs: Any) -> Any:
        raise NotImplementedError("SolanaAdapter.send_native — withdraw phase")

    async def send_usdc(self, **kwargs: Any) -> Any:
        raise NotImplementedError("SolanaAdapter.send_usdc — withdraw phase")
