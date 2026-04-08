from decimal import Decimal
from solana.constants import LAMPORTS_PER_SOL
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solana.rpc.async_api import AsyncClient
from solders.transaction import Transaction
from solana.rpc.types import TxOpts


async def solana_send_transaction(destination_address: str, amount_sol: Decimal, rpc_url: str) -> str:
    """
    Sends SOL on-chain to the destination address.
    Returns the transaction signature.
    Raises an exception if the transaction fails.
    """
    client = AsyncClient(rpc_url)

    # Load sender's keypair – from_json expects a raw JSON string, not a parsed dict
    with open("C:\\Users\\gunmo\\Desktop\\Github_projects\\Keys\\solana_hot_wallet.json") as f:
        keypair_json = f.read()

    sender_keypair = Keypair.from_json(keypair_json)
    public_key = sender_keypair.pubkey()

    lamports = int(amount_sol * LAMPORTS_PER_SOL)

    ix = transfer(TransferParams(from_pubkey=public_key,
                                 to_pubkey=Pubkey.from_string(destination_address),
                                 lamports=lamports))

    # Fetch recent blockhash
    blockhash_resp = await client.get_latest_blockhash()
    blockhash = blockhash_resp.value.blockhash

    # Build and sign transaction
    tx = Transaction.new_signed_with_payer(
        instructions=[ix],
        payer=public_key,
        signing_keypairs=[sender_keypair],
        recent_blockhash=blockhash,
    )

    send_resp = await client.send_raw_transaction(
        bytes(tx),
        opts=TxOpts(skip_preflight=False)
    )

    signature = send_resp.value

    await client.confirm_transaction(signature)

    # Return signature as base58 string to match -> str return type
    return str(signature)

