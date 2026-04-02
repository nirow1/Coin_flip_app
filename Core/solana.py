from decimal import Decimal


async def solana_send_transaction(destination_address: str, amount_sol: Decimal) -> str:
    """
    Sends SOL on-chain to the destination address.
    Returns the transaction signature.
    Raises an exception if the transaction fails.

    TODO: implement using solders / solana-py:
        from solders.keypair import Keypair
        from solana.rpc.async_api import AsyncClient
        ...
    """
    raise NotImplementedError("Solana client not yet configured")

