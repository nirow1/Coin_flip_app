from abc import ABC, abstractmethod
from typing import Any


class ChainNotImplementedError(Exception):
    """Raised when a payment rail is not live yet. Map to HTTP 501 in services."""


class ChainAdapter(ABC):
    """Per-chain pay-in / pay-out operations. Amounts always come from server quotes."""

    @abstractmethod
    async def quote_native(self, **kwargs: Any) -> dict[str, Any]:
        ...

    @abstractmethod
    async def verify_deposit(self, **kwargs: Any) -> Any:
        ...

    @abstractmethod
    async def send_native(self, **kwargs: Any) -> Any:
        ...

    @abstractmethod
    async def send_usdc(self, **kwargs: Any) -> Any:
        ...
