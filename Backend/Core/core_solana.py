from decimal import Decimal

from solana.constants import LAMPORTS_PER_SOL
from solana.rpc.async_api import AsyncClient
from solana.rpc.models import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction

from Backend.config import SolanaCluster, settings

# Official cluster genesis hashes (getGenesisHash).
CLUSTER_GENESIS_HASH: dict[SolanaCluster, str] = {
    "mainnet-beta": "5eykt4UsFv8P8NJdTREpY1vzqKqZKvdpKuc147dw2N9d",
    "devnet": "EtWTRABZaYq6iMfeYKouRu166VU2xqa1wcaWoxPkrZBG",
    "testnet": "4uhcVJyU9pJkvQyS88uRDiswHXSCkY3zQawwpjk2NsNY",
}

# Circle USDC mint per cluster (testnet has no official Circle mint).
CLUSTER_USDC_MINT: dict[SolanaCluster, str | None] = {
    "mainnet-beta": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "devnet": "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
    "testnet": None,
}


def load_hot_keypair() -> Keypair:
    """Load hot payout keypair from settings (secret store). Fail closed if missing."""
    secret = settings.SOLANA_HOT_WALLET_SECRET
    if not secret or not secret.strip():
        raise RuntimeError("SOLANA_HOT_WALLET_SECRET is not configured")
    return Keypair.from_json(secret)


def validate_solana_settings_local() -> None:
    """Fail closed on mint/cluster mismatch and hot keypair/address mismatch (no RPC)."""
    cluster = settings.SOLANA_CLUSTER
    expected_mint = CLUSTER_USDC_MINT.get(cluster)
    if expected_mint is not None and settings.SOLANA_USDC_MINT != expected_mint:
        raise RuntimeError(
            f"SOLANA_USDC_MINT {settings.SOLANA_USDC_MINT!r} does not match "
            f"expected mint for cluster {cluster!r} ({expected_mint})"
        )

    keypair = load_hot_keypair()
    if str(keypair.pubkey()) != settings.SOLANA_HOT_WALLET_ADDRESS:
        raise RuntimeError(
            "SOLANA_HOT_WALLET_SECRET pubkey does not match SOLANA_HOT_WALLET_ADDRESS"
        )


async def assert_solana_cluster_matches_rpc() -> None:
    """Confirm SOLANA_RPC_URL serves the configured SOLANA_CLUSTER (genesis hash)."""
    expected = CLUSTER_GENESIS_HASH[settings.SOLANA_CLUSTER]
    async with AsyncClient(settings.SOLANA_RPC_URL) as client:
        resp = await client.get_genesis_hash()
    actual = str(resp.value)
    if actual != expected:
        raise RuntimeError(
            f"SOLANA_RPC_URL genesis hash {actual!r} does not match "
            f"SOLANA_CLUSTER={settings.SOLANA_CLUSTER!r} (expected {expected!r})"
        )


async def solana_send_transaction(destination_address: str, amount_sol: Decimal, rpc_url: str) -> str:
    """
    Sends SOL on-chain to the destination address.
    Returns the transaction signature.
    Raises an exception if the transaction fails.
    """
    client = AsyncClient(rpc_url)

    sender_keypair = load_hot_keypair()
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

    if send_resp.value is None:
        raise Exception("send_raw_transaction failed: no signature returned")

    signature = send_resp.value

    try:
        await client.confirm_transaction(signature)
    except Exception as e:
        # SOL was already sent — raise a distinct error so callers
        # know NOT to refund (money is in-flight, not lost)
        raise Exception(f"SENT_UNCONFIRMED:{signature}:{e}")

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
