from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from solana.rpc.commitment import Finalized

from Backend.Core.core_solana import (
    MEMO_PROGRAM_IDS,
    account_pubkey,
    full_account_keys,
    verify_fetched_solana_transaction,
    verify_solana_transaction,
)

DESTINATION = "So11111111111111111111111111111111111111112"
SENDER = "11111111111111111111111111111111"
REFERENCE = "SysvarRent111111111111111111111111111111111"
MEMO_PROGRAM = next(iter(MEMO_PROGRAM_IDS))
MEMO = "order_ref_test_abc"
EXPECTED_LAMPORTS = 10_000_000_000


def _parsed_key(pubkey: str) -> MagicMock:
    """Simulate jsonParsed ParsedAccount where str(key) is not the base58 address."""
    key = MagicMock()
    key.pubkey = pubkey
    key.__str__ = MagicMock(return_value=f"ParsedAccount(pubkey={pubkey}, …)")
    return key


def _memo_ix(memo: str = MEMO) -> SimpleNamespace:
    return SimpleNamespace(program_id=MEMO_PROGRAM, data=None, parsed=memo)


def _make_rpc_response(
    account_keys,
    pre_balances,
    post_balances,
    err=None,
    instructions=None,
    loaded_writable=None,
    loaded_readonly=None,
    block_time=1_715_000_000,
    slot=312_456_789,
):
    """Builds a minimal mock of the object returned by client.get_transaction()."""
    message = SimpleNamespace(
        account_keys=account_keys,
        instructions=instructions if instructions is not None else [_memo_ix()],
    )
    meta = SimpleNamespace(
        err=err,
        pre_balances=pre_balances,
        post_balances=post_balances,
        loaded_addresses=SimpleNamespace(
            writable=loaded_writable or [],
            readonly=loaded_readonly or [],
        ),
    )
    inner_tx = SimpleNamespace(message=message)
    encoded = SimpleNamespace(transaction=inner_tx, meta=meta)
    resp = MagicMock()
    resp.value = SimpleNamespace(transaction=encoded, block_time=block_time, slot=slot)
    return resp


def _mock_client_with_resp(resp):
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_transaction.return_value = resp
    return mock_client


def _verify_kwargs(**overrides):
    base = dict(
        expected_destination=DESTINATION,
        expected_lamports=EXPECTED_LAMPORTS,
        expected_memo=MEMO,
        expected_reference=REFERENCE,
        rpc_url="https://api.mainnet-beta.solana.com",
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_success():
    """Valid tx: destination via .pubkey, memo + reference, returns VerifiedSolanaTx."""
    resp = _make_rpc_response(
        account_keys=[
            _parsed_key(SENDER),
            _parsed_key(DESTINATION),
            _parsed_key(MEMO_PROGRAM),
            _parsed_key(REFERENCE),
        ],
        pre_balances=[15_000_000_000, 0, 1, 0],
        post_balances=[15_000_000_000 - EXPECTED_LAMPORTS, EXPECTED_LAMPORTS, 1, 0],
    )
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        result = await verify_solana_transaction(
            tx_hash="valid_tx_hash_abc123",
            **_verify_kwargs(),
        )

    assert result.received_lamports == EXPECTED_LAMPORTS
    assert result.fee_payer == SENDER
    assert result.memo == MEMO
    assert result.block_time == 1_715_000_000
    assert result.slot == 312_456_789
    mock_client.get_transaction.assert_called_once()
    call_kwargs = mock_client.get_transaction.call_args.kwargs
    assert call_kwargs["encoding"] == "jsonParsed"
    assert call_kwargs["commitment"] == Finalized
    assert call_kwargs["max_supported_transaction_version"] == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_not_found():
    resp = MagicMock()
    resp.value = None
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="not found on-chain"):
            await verify_solana_transaction(
                tx_hash="nonexistent_tx_hash_abc123",
                **_verify_kwargs(),
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_meta_is_none():
    resp = MagicMock()
    resp.value.transaction.meta = None
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="failed on-chain"):
            await verify_solana_transaction(
                tx_hash="tx_with_no_meta_abc123",
                **_verify_kwargs(),
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_failed():
    resp = _make_rpc_response(
        account_keys=[
            _parsed_key(SENDER),
            _parsed_key(DESTINATION),
            _parsed_key(MEMO_PROGRAM),
            _parsed_key(REFERENCE),
        ],
        pre_balances=[15_000_000_000, 0, 1, 0],
        post_balances=[15_000_000_000 - EXPECTED_LAMPORTS, EXPECTED_LAMPORTS, 1, 0],
        err=MagicMock(),
    )
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="failed on-chain"):
            await verify_solana_transaction(
                tx_hash="failed_tx_hash_abc123",
                **_verify_kwargs(),
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_destination_not_found():
    resp = _make_rpc_response(
        account_keys=[
            _parsed_key(SENDER),
            _parsed_key("Vote111111111111111111111111111111111111111"),
            _parsed_key(MEMO_PROGRAM),
            _parsed_key(REFERENCE),
        ],
        pre_balances=[0, 5_000_000_000, 1, 0],
        post_balances=[0, 5_000_000_000, 1, 0],
    )
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        with pytest.raises(
            ValueError,
            match=f"Destination address {DESTINATION} not found in transaction",
        ):
            await verify_solana_transaction(
                tx_hash="no_destination_tx_hash_abc123",
                **_verify_kwargs(),
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_insufficient_amount():
    short = EXPECTED_LAMPORTS - 5_000_000
    resp = _make_rpc_response(
        account_keys=[
            _parsed_key(SENDER),
            _parsed_key(DESTINATION),
            _parsed_key(MEMO_PROGRAM),
            _parsed_key(REFERENCE),
        ],
        pre_balances=[15_000_000_000, 0, 1, 0],
        post_balances=[15_000_000_000 - short, short, 1, 0],
    )
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match=f"credited only {short} lamports"):
            await verify_solana_transaction(
                tx_hash="underpay_tx_hash_abc123",
                **_verify_kwargs(),
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_accepts_overpayment():
    over = EXPECTED_LAMPORTS + 5_000_000
    resp = _make_rpc_response(
        account_keys=[
            _parsed_key(SENDER),
            _parsed_key(DESTINATION),
            _parsed_key(MEMO_PROGRAM),
            _parsed_key(REFERENCE),
        ],
        pre_balances=[15_000_000_000, 0, 1, 0],
        post_balances=[15_000_000_000 - over, over, 1, 0],
    )
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        result = await verify_solana_transaction(
            tx_hash="overpay_tx_hash_abc123",
            **_verify_kwargs(),
        )

    assert result.received_lamports == over


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_wrong_memo():
    resp = _make_rpc_response(
        account_keys=[
            _parsed_key(SENDER),
            _parsed_key(DESTINATION),
            _parsed_key(MEMO_PROGRAM),
            _parsed_key(REFERENCE),
        ],
        pre_balances=[15_000_000_000, 0, 1, 0],
        post_balances=[15_000_000_000 - EXPECTED_LAMPORTS, EXPECTED_LAMPORTS, 1, 0],
        instructions=[_memo_ix("wrong_memo")],
    )
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="memo"):
            await verify_solana_transaction(
                tx_hash="wrong_memo_tx",
                **_verify_kwargs(),
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_any_matching_memo():
    """Accept if any of several memo instructions matches."""
    resp = _make_rpc_response(
        account_keys=[
            _parsed_key(SENDER),
            _parsed_key(DESTINATION),
            _parsed_key(MEMO_PROGRAM),
            _parsed_key(REFERENCE),
        ],
        pre_balances=[15_000_000_000, 0, 1, 0],
        post_balances=[15_000_000_000 - EXPECTED_LAMPORTS, EXPECTED_LAMPORTS, 1, 0],
        instructions=[_memo_ix("noise"), _memo_ix(MEMO)],
    )
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        result = await verify_solana_transaction(
            tx_hash="multi_memo_tx",
            **_verify_kwargs(),
        )

    assert result.received_lamports == EXPECTED_LAMPORTS


@pytest.mark.asyncio(loop_scope="session")
async def test_verify_solana_transaction_missing_reference():
    resp = _make_rpc_response(
        account_keys=[
            _parsed_key(SENDER),
            _parsed_key(DESTINATION),
            _parsed_key(MEMO_PROGRAM),
        ],
        pre_balances=[15_000_000_000, 0, 1],
        post_balances=[15_000_000_000 - EXPECTED_LAMPORTS, EXPECTED_LAMPORTS, 1],
    )
    mock_client = _mock_client_with_resp(resp)

    with patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        with pytest.raises(ValueError, match="reference"):
            await verify_solana_transaction(
                tx_hash="no_ref_tx",
                **_verify_kwargs(),
            )


def test_json_parsed_does_not_append_loaded_addresses():
    """jsonParsed already expands ALTs into account_keys — do not double-count."""
    message = SimpleNamespace(
        account_keys=[_parsed_key(SENDER), _parsed_key(DESTINATION)],
    )
    meta = SimpleNamespace(
        loaded_addresses=SimpleNamespace(writable=[DESTINATION], readonly=[]),
    )
    keys = full_account_keys(message, meta, encoding="jsonParsed")
    assert keys == [SENDER, DESTINATION]
    assert account_pubkey(_parsed_key(DESTINATION)) == DESTINATION


def test_raw_encoding_appends_loaded_addresses():
    """json/base64 encodings need meta.loaded_addresses appended."""
    message = SimpleNamespace(
        account_keys=[_parsed_key(SENDER), _parsed_key(MEMO_PROGRAM), _parsed_key(REFERENCE)],
        instructions=[_memo_ix()],
    )
    meta = SimpleNamespace(
        err=None,
        pre_balances=[15_000_000_000, 1, 0, 0],
        post_balances=[15_000_000_000 - EXPECTED_LAMPORTS, 1, 0, EXPECTED_LAMPORTS],
        loaded_addresses=SimpleNamespace(writable=[DESTINATION], readonly=[]),
    )
    keys = full_account_keys(message, meta, encoding="json")
    assert keys[-1] == DESTINATION

    tx = SimpleNamespace(
        transaction=SimpleNamespace(
            transaction=SimpleNamespace(message=message),
            meta=meta,
        ),
        block_time=None,
        slot=None,
    )
    result = verify_fetched_solana_transaction(
        tx,
        tx_hash="alt_tx",
        expected_destination=DESTINATION,
        expected_lamports=EXPECTED_LAMPORTS,
        expected_memo=MEMO,
        expected_reference=REFERENCE,
        encoding="json",
    )
    assert result.received_lamports == EXPECTED_LAMPORTS
    assert result.fee_payer == SENDER
