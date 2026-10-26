from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, NoReturn

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed, Finalized
from solana.rpc.models import TxOpts
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from spl.memo.constants import MEMO_PROGRAM_ID

from Backend.config import SolanaCluster, settings

logger = logging.getLogger(__name__)

# Bitcoin / Solana base58 alphabet (for raw instruction data fallback).
_B58_ALPHABET = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {c: i for i, c in enumerate(_B58_ALPHABET)}

_RPC_TIMEOUT_SEC = 10.0
_GENESIS_RETRIES = 3
_GENESIS_RETRY_DELAY_SEC = 0.5

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

# Rent-exempt minimum for a basic system account (SOL transfers that may fund new wallets).
SYSTEM_ACCOUNT_RENT_EXEMPT_LAMPORTS = 890_880


@dataclass(frozen=True)
class VerifiedSolanaTx:
    """On-chain deposit facts retained for credit matching, late-pay rules, and refunds."""

    received_lamports: int
    block_time: int | None
    slot: int | None
    fee_payer: str
    memo: str | None


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


class SendFailedOnChain(SolanaSendError):
    """Transaction landed with a program/runtime error — final; safe to refund."""

    def __init__(self, signature: str, cause: BaseException | None = None) -> None:
        detail = f"SEND_FAILED_ON_CHAIN:{signature}"
        if cause is not None:
            detail = f"{detail}:{cause}"
        super().__init__(detail, signature=signature)
        self.__cause__ = cause


class SolanaClusterMismatchError(RuntimeError):
    """RPC genesis hash does not match SOLANA_CLUSTER — configuration error."""


def _secret_str(value: object) -> str:
    """Unwrap SecretStr; plain str allowed for test mocks."""
    getter = getattr(value, "get_secret_value", None)
    if callable(getter):
        return str(getter())
    return str(value) if value is not None else ""


def load_hot_keypair() -> Keypair:
    """Load hot payout keypair from settings (secret store). Fail closed if missing."""
    secret = _secret_str(settings.SOLANA_HOT_WALLET_SECRET)
    if not secret or not secret.strip():
        raise RuntimeError("SOLANA_HOT_WALLET_SECRET is not configured")
    return Keypair.from_json(secret)


def validate_solana_web_settings() -> None:
    """Web-process checks: mint/cluster, cold/hot pubkeys valid and distinct (no keypair)."""
    cluster = settings.SOLANA_CLUSTER
    if cluster == "testnet":
        raise RuntimeError(
            "SOLANA_CLUSTER=testnet is unsupported (no official Circle USDC mint)"
        )

    expected_mint = CLUSTER_USDC_MINT.get(cluster)
    if expected_mint is None:
        raise RuntimeError(f"no expected USDC mint configured for cluster {cluster!r}")
    if settings.SOLANA_USDC_MINT != expected_mint:
        raise RuntimeError(
            f"SOLANA_USDC_MINT {settings.SOLANA_USDC_MINT!r} does not match "
            f"expected mint for cluster {cluster!r} ({expected_mint})"
        )

    try:
        cold = str(Pubkey.from_string(settings.SOLANA_COLD_RECEIVE_ADDRESS))
    except Exception as exc:
        raise RuntimeError("SOLANA_COLD_RECEIVE_ADDRESS is not a valid pubkey") from exc
    try:
        hot = str(Pubkey.from_string(settings.SOLANA_HOT_WALLET_ADDRESS))
    except Exception as exc:
        raise RuntimeError("SOLANA_HOT_WALLET_ADDRESS is not a valid pubkey") from exc

    if cold == hot:
        raise RuntimeError(
            "SOLANA_COLD_RECEIVE_ADDRESS and SOLANA_HOT_WALLET_ADDRESS must differ"
        )


def validate_solana_payout_settings() -> None:
    """Payout/reconciler only: load hot keypair and confirm it matches the hot address."""
    keypair = load_hot_keypair()
    if str(keypair.pubkey()) != settings.SOLANA_HOT_WALLET_ADDRESS:
        raise RuntimeError(
            "SOLANA_HOT_WALLET_SECRET pubkey does not match SOLANA_HOT_WALLET_ADDRESS"
        )


def validate_solana_settings_local() -> None:
    """Backward-compatible alias: web settings only (no hot keypair load)."""
    validate_solana_web_settings()


async def assert_solana_cluster_matches_rpc() -> None:
    """Confirm SOLANA_RPC_URL serves the configured SOLANA_CLUSTER (genesis hash).

    Raises RuntimeError on mismatch or if RPC stays unreachable after retries.
    """
    expected = CLUSTER_GENESIS_HASH[settings.SOLANA_CLUSTER]
    last_error: BaseException | None = None

    for attempt in range(1, _GENESIS_RETRIES + 1):
        try:
            async with AsyncClient(
                settings.SOLANA_RPC_URL, timeout=_RPC_TIMEOUT_SEC
            ) as client:
                resp = await client.get_genesis_hash()
            actual = str(resp.value)
            if actual != expected:
                raise SolanaClusterMismatchError(
                    f"SOLANA_RPC_URL genesis hash {actual!r} does not match "
                    f"SOLANA_CLUSTER={settings.SOLANA_CLUSTER!r} (expected {expected!r})"
                )
            return
        except SolanaClusterMismatchError:
            raise
        except Exception as exc:
            last_error = exc
            logger.warning(
                "solana genesis check attempt %s/%s failed: %s",
                attempt,
                _GENESIS_RETRIES,
                exc,
            )
            if attempt < _GENESIS_RETRIES:
                await asyncio.sleep(_GENESIS_RETRY_DELAY_SEC)

    raise RuntimeError(
        f"SOLANA_RPC_URL genesis check failed after {_GENESIS_RETRIES} attempts"
    ) from last_error


def account_pubkey(key: Any) -> str:
    """Normalize jsonParsed ParsedAccount / Pubkey / str to base58 pubkey string."""
    if hasattr(key, "pubkey"):
        pk = key.pubkey
        return str(pk() if callable(pk) else pk)
    return str(key)


def full_account_keys(
    message: Any,
    meta: Any,
    *,
    encoding: str = "jsonParsed",
) -> list[str]:
    """Build the account key list used for balance/reference lookups.

    jsonParsed already expands ALT addresses into message.account_keys — do not
    append meta.loaded_addresses (that double-counts). For json/base64 encodings,
    append loaded writable then readonly.
    """
    keys = [account_pubkey(k) for k in (message.account_keys or [])]
    if encoding == "jsonParsed":
        return keys

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


def _b58decode(data: str) -> bytes:
    """Decode Solana base58 without an extra dependency."""
    if not data:
        return b""
    num = 0
    for ch in data.encode("ascii"):
        try:
            num = num * 58 + _B58_INDEX[ch]
        except KeyError as exc:
            raise ValueError("invalid base58 character") from exc
    combined = num.to_bytes((num.bit_length() + 7) // 8 or 1, "big")
    pad = 0
    for ch in data:
        if ch == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + combined.lstrip(b"\x00")


def _instruction_memo_text(ix: Any) -> str | None:
    """Extract memo UTF-8. Prefer jsonParsed `parsed`; raw `data` is base58 only."""
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
        try:
            return _decode_memo_bytes(_b58decode(data))
        except Exception:
            # Last resort: treat as plain UTF-8 (some mock fixtures).
            return data
    return None


def iter_memos(message: Any, account_keys: list[str]) -> list[str]:
    """Return every Memo program instruction payload in the message."""
    memos: list[str] = []
    instructions = getattr(message, "instructions", None) or []
    for ix in instructions:
        program_id = _instruction_program_id(ix, account_keys)
        if program_id not in MEMO_PROGRAM_IDS:
            continue
        memo = _instruction_memo_text(ix)
        if memo is not None:
            memos.append(memo)
    return memos


def extract_memo(message: Any, account_keys: list[str]) -> str | None:
    """Return the first Memo program instruction payload, if any."""
    memos = iter_memos(message, account_keys)
    return memos[0] if memos else None


def memo_matches(message: Any, account_keys: list[str], expected_memo: str) -> bool:
    """True if any Memo instruction equals expected_memo."""
    return expected_memo in iter_memos(message, account_keys)


def verify_fetched_solana_transaction(
    tx: Any,
    *,
    tx_hash: str,
    expected_destination: str,
    expected_lamports: int,
    expected_memo: str,
    expected_reference: str,
    encoding: str = "jsonParsed",
) -> VerifiedSolanaTx:
    """
    Verify an already-fetched getTransaction value.
    Returns VerifiedSolanaTx (lamports, block_time, slot, fee_payer, memo).
    """
    meta = tx.transaction.meta
    if meta is None or meta.err is not None:
        raise ValueError(f"Transaction {tx_hash} failed on-chain")

    message = tx.transaction.transaction.message
    account_keys = full_account_keys(message, meta, encoding=encoding)
    pre_balances = meta.pre_balances
    post_balances = meta.post_balances

    if not account_keys:
        raise ValueError(f"Transaction {tx_hash} has no account keys")

    destination = str(Pubkey.from_string(expected_destination))
    reference = str(Pubkey.from_string(expected_reference))

    received_lamports: int | None = None
    for i, key in enumerate(account_keys):
        if key == destination:
            if i >= len(pre_balances) or i >= len(post_balances):
                raise ValueError(
                    f"Transaction {tx_hash} balance arrays shorter than account keys"
                )
            received_lamports = int(post_balances[i]) - int(pre_balances[i])
            break

    if received_lamports is None:
        raise ValueError(
            f"Destination address {expected_destination} not found in transaction {tx_hash}"
        )


    if reference not in account_keys:
        raise ValueError(
            f"Solana Pay reference {expected_reference} not found in transaction {tx_hash}"
        )

    memos = iter_memos(message, account_keys)
    if not memos:
        raise ValueError(f"Transaction {tx_hash} has no memo instruction")
    if expected_memo not in memos:
        raise ValueError(
            f"Transaction {tx_hash} memo(s) {memos!r} do not match expected {expected_memo!r}"
        )

    block_time = getattr(tx, "block_time", None)
    if block_time is None:
        block_time = getattr(tx, "blockTime", None)
    slot = getattr(tx, "slot", None)

    return VerifiedSolanaTx(
        received_lamports=received_lamports,
        block_time=int(block_time) if block_time is not None else None,
        slot=int(slot) if slot is not None else None,
        fee_payer=account_keys[0],
        memo=expected_memo,
    )


async def verify_solana_transaction(
    tx_hash: str,
    expected_destination: str,
    expected_lamports: int,
    expected_memo: str,
    expected_reference: str,
    rpc_url: str,
) -> VerifiedSolanaTx:
    """
    Verifies a finalized Solana deposit transaction.
    Returns VerifiedSolanaTx. Raises ValueError with a reason if checks fail.
    """
    sig = Signature.from_string(tx_hash)

    async with AsyncClient(rpc_url, timeout=_RPC_TIMEOUT_SEC) as client:
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
        expected_lamports=expected_lamports,
        expected_memo=expected_memo,
        expected_reference=expected_reference,
        encoding="jsonParsed",
    )


async def _classify_send_failure(
    client: AsyncClient,
    signature: Signature,
    last_valid_block_height: int,
    cause: BaseException,
) -> NoReturn:
    """Raise SentUnconfirmed, SendFailedOnChain, or SendFailedRefundable."""
    sig_str = str(signature)
    try:
        status_resp = await client.get_signature_statuses(
            [signature],
            search_transaction_history=True,
        )
        statuses = status_resp.value or []
        on_chain = statuses[0] if statuses else None
    except Exception:
        raise SentUnconfirmed(sig_str, cause) from cause

    if on_chain is not None:
        if getattr(on_chain, "err", None) is not None:
            raise SendFailedOnChain(sig_str, cause) from cause
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
    if lamports <= 0:
        raise ValueError("lamports must be positive")
    if lamports < SYSTEM_ACCOUNT_RENT_EXEMPT_LAMPORTS:
        raise ValueError(
            f"lamports below rent-exempt minimum ({SYSTEM_ACCOUNT_RENT_EXEMPT_LAMPORTS})"
        )

    try:
        dest_pubkey = Pubkey.from_string(destination_address)
    except Exception as exc:
        raise ValueError("destination must be a valid Solana public key") from exc

    dest = str(dest_pubkey)
    house = {
        settings.SOLANA_HOT_WALLET_ADDRESS,
        settings.SOLANA_COLD_RECEIVE_ADDRESS,
    }
    if dest in house:
        raise ValueError("destination must not be a house address")

    sender_keypair = load_hot_keypair()
    public_key = sender_keypair.pubkey()

    ix = transfer(
        TransferParams(
            from_pubkey=public_key,
            to_pubkey=dest_pubkey,
            lamports=lamports,
        )
    )

    async with AsyncClient(rpc_url) as client:
        blockhash_resp = await client.get_latest_blockhash(commitment=Confirmed)
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
    Raises SentUnconfirmed, SendFailedOnChain, or SendFailedRefundable
    (never bare Exception for money paths).
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
            status_resp = await client.confirm_transaction(
                sig,
                last_valid_block_height=last_valid_block_height,
            )
        except Exception as e:
            await _classify_send_failure(client, sig, last_valid_block_height, e)

        statuses = status_resp.value or []
        on_chain = statuses[0] if statuses else None
        if on_chain is None:
            raise SentUnconfirmed(
                signature,
                SolanaSendError("transaction status missing after confirm", signature),
            )
        if on_chain.err is not None:
            raise SendFailedOnChain(
                signature,
                SolanaSendError(
                    f"transaction confirmed with error: {on_chain.err}",
                    signature,
                ),
            )

    return signature