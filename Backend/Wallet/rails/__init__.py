from Backend.Wallet.enums import Chain
from Backend.Wallet.rails.base import ChainAdapter, ChainNotImplementedError
from Backend.Wallet.rails.polygon import PolygonAdapter
from Backend.Wallet.rails.solana import SolanaAdapter

_ADAPTERS: dict[Chain, ChainAdapter] = {
    Chain.SOLANA: SolanaAdapter(),
    Chain.POLYGON: PolygonAdapter(),
}


def get_adapter(chain: Chain) -> ChainAdapter:
    try:
        return _ADAPTERS[chain]
    except KeyError as exc:
        raise ChainNotImplementedError(f"No adapter for chain={chain}") from exc


__all__ = [
    "ChainAdapter",
    "ChainNotImplementedError",
    "PolygonAdapter",
    "SolanaAdapter",
    "get_adapter",
]
