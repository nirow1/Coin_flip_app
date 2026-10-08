from typing import Any

from Backend.Wallet.rails.base import ChainAdapter


class SolanaAdapter(ChainAdapter):
    """Live Solana rail — wired in Phase 3–4 against core_solana."""

    async def quote_native(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError("SolanaAdapter.quote_native — Phase 4")

    async def verify_deposit(self, **kwargs: Any) -> Any:
        raise NotImplementedError("SolanaAdapter.verify_deposit — Phase 3")

    async def send_native(self, **kwargs: Any) -> Any:
        raise NotImplementedError("SolanaAdapter.send_native — Phase 3/6")

    async def send_usdc(self, **kwargs: Any) -> Any:
        raise NotImplementedError("SolanaAdapter.send_usdc — Phase 3/6")
