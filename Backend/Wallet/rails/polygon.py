from typing import Any

from Backend.Wallet.rails.base import ChainAdapter, ChainNotImplementedError


class PolygonAdapter(ChainAdapter):
    """Polygon rail stub — not live; map ChainNotImplementedError to HTTP 501."""

    async def quote_native(self, **kwargs: Any) -> dict[str, Any]:
        raise ChainNotImplementedError("Polygon rail is not implemented")

    async def verify_deposit(self, **kwargs: Any) -> Any:
        raise ChainNotImplementedError("Polygon rail is not implemented")

    async def send_native(self, **kwargs: Any) -> Any:
        raise ChainNotImplementedError("Polygon rail is not implemented")

    async def send_usdc(self, **kwargs: Any) -> Any:
        raise ChainNotImplementedError("Polygon rail is not implemented")
