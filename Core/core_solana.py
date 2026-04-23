from decimal import Decimal
from solana.constants import LAMPORTS_PER_SOL
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import transfer, TransferParams
from solana.rpc.async_api import AsyncClient
from solders.transaction import Transaction
from solders.signature import Signature
from solana.rpc.types import TxOpts


async def solana_send_transaction(destination_address: str, amount_sol: Decimal, rpc_url: str) -> str:
    """
    Sends SOL on-chain to the destination address.
    Returns the transaction signature.
    Raises an exception if the transaction fails.
    """
    client = AsyncClient(rpc_url)

    # Load sender's keypair – from_json expects a raw JSON string, not a parsed dict
    # todo: this will have to be in a save storage outside pc when released
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


async def verify_solana_transaction(tx_hash: str, expected_destination: str, expected_amount_sol: Decimal, rpc_url: str) -> bool:
    """
    Verifies that a given Solana transaction:
      - is confirmed on-chain
      - transfers SOL to expected_destination
      - transfers at least expected_amount_sol
    Returns True if valid, raises ValueError with a reason if not.
    """
    client = AsyncClient(rpc_url)

    sig = Signature.from_string(tx_hash)

    resp = await client.get_transaction(sig, encoding="jsonParsed")

    if resp.value is None:
        raise ValueError(f"Transaction {tx_hash} not found on-chain")

    tx = resp.value
    if tx.transaction.meta is None or tx.transaction.meta.err is not None:
        raise ValueError(f"Transaction {tx_hash} failed on-chain")

    # Inspect pre/post balances to confirm the credit
    account_keys = tx.transaction.transaction.message.account_keys
    pre_balances = tx.transaction.meta.pre_balances
    post_balances = tx.transaction.meta.post_balances

    destination_pubkey = Pubkey.from_string(expected_destination)
    expected_lamports = int(expected_amount_sol * LAMPORTS_PER_SOL)

    for i, key in enumerate(account_keys):
        if str(key) == str(destination_pubkey):
            received_lamports = post_balances[i] - pre_balances[i]
            if received_lamports < expected_lamports:
                raise ValueError(
                    f"Transaction {tx_hash} credited only {received_lamports} lamports, "
                    f"expected at least {expected_lamports}"
                )
            return True

    raise ValueError(f"Destination address {expected_destination} not found in transaction {tx_hash}")


