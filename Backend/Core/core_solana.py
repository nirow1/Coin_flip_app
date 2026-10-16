from __future__ import annotations

import base64
from decimal import Decimal
from typing import Any, NoReturn

from solana.constants import LAMPORTS_PER_SOL
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Finalized
from solana.rpc.models import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from spl.memo.constants import MEMO_PROGRAM_ID

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

# Memo program IDs (v2 current + legacy v1).
MEMO_PROGRAM_IDS: frozenset[str] = frozenset(
    {
        str(MEMO_PROGRAM_ID),
        "Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo",
    }
)


class SolanaSendError(Exception):
    """Base error for hot-wallet send failures."""

    def __init__(self, message: str, signature: str | None = None) -> None:
        super().__init__(message)
        self.signature = signature


class SentUnconfirmed(SolanaSendError):
    """Signature is known; funds may be in flight. Not safe to refund."""

    def __init__(self, signature: str, cause: BaseException | None = None) -> None:
        detail = f"SENT_UNCONFIRMED:{signature}"
        if cause is not None:
            detail = f"{detail}:{cause}"
        super().__init__(detail, signature=signature)
        self.__cause__ = cause


class SendFailedRefundable(SolanaSendError):
    """Blockhash expired and signature absent on-chain — safe to refund."""

    def __init__(self, signature: str, cause: BaseException | None = None) -> None:
        detail = f"SEND_FAILED_REFUNDABLE:{signature}"
        if cause is not None:
            detail = f"{detail}:{cause}"
        super().__init__(detail, signature=signature)
        self.__cause__ = cause


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


def account_pubkey(key: Any) -> str:
    """Normalize jsonParsed ParsedAccount / Pubkey / str to base58 pubkey string."""
    if hasattr(key, "pubkey"):
        pk = key.pubkey
        return str(pk() if callable(pk) else pk)
    return str(key)


def full_account_keys(message: Any, meta: Any) -> list[str]:
    """Static message keys plus ALT loaded_addresses (writable then readonly)."""
    keys = [account_pubkey(k) for k in (message.account_keys or [])]
    loaded = getattr(meta, "loaded_addresses", None)
    if loaded is None:
        return keys
    for addr in getattr(loaded, "writable", None) or []:
        keys.append(str(addr))
    for addr in getattr(loaded, "readonly", None) or []:
        keys.append(str(addr))
    return keys


def _instruction_program_id(ix: Any, account_keys: list[str]) -> str | None:
    for attr in ("program_id", "programId"):
        if hasattr(ix, attr):
            value = getattr(ix, attr)
            if value is not None:
                return str(value)
    if isinstance(ix, dict):
        if "programId" in ix:
            return str(ix["programId"])
        if "program_id" in ix:
            return str(ix["program_id"])
        prog_idx = ix.get("programIdIndex", ix.get("program_id_index"))
        if prog_idx is not None and 0 <= int(prog_idx) < len(account_keys):
            return account_keys[int(prog_idx)]
    prog_idx = getattr(ix, "program_id_index", None)
    if prog_idx is not None and 0 <= int(prog_idx) < len(account_keys):
        return account_keys[int(prog_idx)]
    return None


def _decode_memo_bytes(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace")


def _instruction_memo_text(ix: Any) -> str | None:
    """Extract memo UTF-8 from parsed or partially-decoded instruction."""
    parsed = getattr(ix, "parsed", None)
    if isinstance(ix, dict):
        parsed = ix.get("parsed", parsed)
    if isinstance(parsed, str):
        return parsed
    if isinstance(parsed, dict):
        info = parsed.get("info", parsed)
        if isinstance(info, str):
            return info
        if isinstance(info, dict) and "memo" in info:
            return str(info["memo"])
        if "type" in parsed and parsed.get("type") == "memo" and isinstance(info, dict):
            return str(info.get("memo", ""))

    data = getattr(ix, "data", None)
    if isinstance(ix, dict):
        data = ix.get("data", data)
    if data is None:
        return None
    if isinstance(data, bytes):
        return _decode_memo_bytes(data)
    if isinstance(data, str):
        # jsonParsed memo is usually already UTF-8 in `parsed`; `data` may be raw text
        # or base64 (encoding=json partially-decoded). Prefer UTF-8 string as-is.
        try:
            decoded = base64.b64decode(data, validate=True)
            if decoded:
                return _decode_memo_bytes(decoded)
        except Exception:
            pass
        return data
    return None


def extract_memo(message: Any, account_keys: list[str]) -> str | None:
    """Return the first Memo program instruction payload, if any."""
    instructions = getattr(message, "instructions", None) or []
    for ix in instructions:
        program_id = _instruction_program_id(ix, account_keys)
        if program_id not in MEMO_PROGRAM_IDS:
            continue
        memo = _instruction_memo_text(ix)
        if memo is not None:
            return memo
    return None


def verify_fetched_solana_transaction(
    tx: Any,
    *,
    tx_hash: str,
    expected_destination: str,
    expected_amount_sol: Decimal,
    expected_memo: str,
    expected_reference: str,
) -> int:
    """
    Verify an already-fetched getTransaction value.
    Returns received lamports at expected_destination.
    """
    meta = tx.transaction.meta
    if meta is None or meta.err is not None:
        raise ValueError(f"Transaction {tx_hash} failed on-chain")

    message = tx.transaction.transaction.message
    account_keys = full_account_keys(message, meta)
    pre_balances = meta.pre_balances
    post_balances = meta.post_balances

    destination = str(Pubkey.from_string(expected_destination))
    reference = str(Pubkey.from_string(expected_reference))
    expected_lamports = int(expected_amount_sol * LAMPORTS_PER_SOL)

    received_lamports: int | None = None
    for i, key in enumerate(account_keys):
        if key == destination:
            if i >= len(pre_balances) or i >= len(post_balances):
                raise ValueError(f"Transaction {tx_hash} balance arrays shorter than account keys")
            received_lamports = int(post_balances[i]) - int(pre_balances[i])
            break

    if received_lamports is None:
        raise ValueError(
            f"Destination address {expected_destination} not found in transaction {tx_hash}"
        )
    if received_lamports < expected_lamports:
        raise ValueError(
            f"Transaction {tx_hash} credited only {received_lamports} lamports, "
            f"expected at least {expected_lamports}"
        )

    if reference not in account_keys:
        raise ValueError(
            f"Solana Pay reference {expected_reference} not found in transaction {tx_hash}"
        )

    memo = extract_memo(message, account_keys)
    if memo is None:
        raise ValueError(f"Transaction {tx_hash} has no memo instruction")
    if memo != expected_memo:
        raise ValueError(
            f"Transaction {tx_hash} memo {memo!r} does not match expected {expected_memo!r}"
        )

    return received_lamports


async def verify_solana_transaction(
    tx_hash: str,
    expected_destination: str,
    expected_amount_sol: Decimal,
    expected_memo: str,
    expected_reference: str,
    rpc_url: str,
) -> int:
    """
    Verifies a finalized Solana deposit transaction and returns received lamports.
    Raises ValueError with a reason if checks fail.
    """
    sig = Signature.from_string(tx_hash)

    async with AsyncClient(rpc_url) as client:
        resp = await client.get_transaction(
            sig,
            encoding="jsonParsed",
            commitment=Finalized,
            max_supported_transaction_version=0,
        )

    if resp.value is None:
        raise ValueError(f"Transaction {tx_hash} not found on-chain")

    return verify_fetched_solana_transaction(
        resp.value,
        tx_hash=tx_hash,
        expected_destination=expected_destination,
        expected_amount_sol=expected_amount_sol,
        expected_memo=expected_memo,
        expected_reference=expected_reference,
    )


async def _classify_send_failure(
    client: AsyncClient,
    signature: Signature,
    last_valid_block_height: int,
    cause: BaseException,
) -> NoReturn:
    """Raise SentUnconfirmed or SendFailedRefundable based on on-chain status."""
    sig_str = str(signature)
    try:
        status_resp = await client.get_signature_statuses([signature])
        statuses = status_resp.value or []
        on_chain = statuses[0] if statuses else None
    except Exception:
        raise SentUnconfirmed(sig_str, cause) from cause

    if on_chain is not None:
        raise SentUnconfirmed(sig_str, cause) from cause

    try:
        height_resp = await client.get_block_height()
        current_height = int(height_resp.value)
    except Exception:
        raise SentUnconfirmed(sig_str, cause) from cause

    if current_height > last_valid_block_height:
        raise SendFailedRefundable(sig_str, cause) from cause

    raise SentUnconfirmed(sig_str, cause) from cause


async def build_signed_sol_transfer(
    destination_address: str,
    lamports: int,
    rpc_url: str,
) -> tuple[bytes, str, int]:
    """
    Build and sign a SOL transfer without broadcasting.
    Returns (raw_tx_bytes, signature_base58, last_valid_block_height).
    """
    sender_keypair = load_hot_keypair()
    public_key = sender_keypair.pubkey()

    ix = transfer(
        TransferParams(
            from_pubkey=public_key,
            to_pubkey=Pubkey.from_string(destination_address),
            lamports=lamports,
        )
    )

    async with AsyncClient(rpc_url) as client:
        blockhash_resp = await client.get_latest_blockhash()
        blockhash = blockhash_resp.value.blockhash
        last_valid_block_height = int(blockhash_resp.value.last_valid_block_height)

    tx = Transaction.new_signed_with_payer(
        instructions=[ix],
        payer=public_key,
        signing_keypairs=[sender_keypair],
        recent_blockhash=blockhash,
    )
    signature = str(tx.signatures[0])
    return bytes(tx), signature, last_valid_block_height


async def broadcast_and_confirm(
    raw_bytes: bytes,
    signature: str,
    last_valid_block_height: int,
    rpc_url: str,
) -> str:
    """
    Broadcast a pre-signed transfer and wait for confirmation.
    Raises SentUnconfirmed or SendFailedRefundable (never bare Exception for money paths).
    """
    sig = Signature.from_string(signature)

    async with AsyncClient(rpc_url) as client:
        try:
            send_resp = await client.send_raw_transaction(
                raw_bytes,
                opts=TxOpts(skip_preflight=False),
            )
        except Exception as e:
            await _classify_send_failure(client, sig, last_valid_block_height, e)

        if send_resp.value is None:
            await _classify_send_failure(
                client,
                sig,
                last_valid_block_height,
                SolanaSendError(
                    "send_raw_transaction failed: no signature returned",
                    signature,
                ),
            )

        try:
            await client.confirm_transaction(sig)
        except Exception as e:
            raise SentUnconfirmed(signature, e) from e

    return signature