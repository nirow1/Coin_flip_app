"""Verify against getTransaction JSON parsed via solders (not SimpleNamespace)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from solders.rpc.responses import GetTransactionResp

from Backend.Core.core_solana import account_pubkey, verify_fetched_solana_transaction

FIXTURES = Path(__file__).parent / "fixtures"
LEGACY_FIXTURE = FIXTURES / "get_transaction_deposit.json"
REAL_FIXTURE = FIXTURES / "get_transaction_deposit_real.json"
V0_ALT_FIXTURE = FIXTURES / "get_transaction_deposit_v0_alt.json"

DESTINATION = "So11111111111111111111111111111111111111112"
REFERENCE = "9zCtsb6bLqHbtkeKbSg4uhpjmuECo4p46yREUj5SdsjL"
MEMO = "order_ref_fixture_001"
EXPECTED_LAMPORTS = 500_000_000


def _rpc_value_from_result_json(result_obj: dict):
    """Wrap a getTransaction `result` object the way JSON-RPC returns it."""
    wrapped = json.dumps({"jsonrpc": "2.0", "id": 1, "result": result_obj})
    resp = GetTransactionResp.from_json(wrapped)
    assert resp.value is not None
    return resp.value


def test_verify_from_solders_parsed_fixture():
    """Hand-shaped fixture still validates the solders parse + verify path."""
    payload = json.loads(LEGACY_FIXTURE.read_text(encoding="utf-8"))
    tx = _rpc_value_from_result_json(payload)

    # Regression: jsonParsed ParsedAccount-style keys must not use str(key).
    first_key = tx.transaction.transaction.message.account_keys[0]
    assert account_pubkey(first_key)

    result = verify_fetched_solana_transaction(
        tx,
        tx_hash=payload["transaction"]["signatures"][0],
        expected_destination=DESTINATION,
        expected_lamports=EXPECTED_LAMPORTS,
        expected_memo=MEMO,
        expected_reference=REFERENCE,
    )

    assert result.received_lamports == EXPECTED_LAMPORTS
    assert result.memo == MEMO
    assert result.fee_payer == "J56wnxszaj6UVPigbQmBDdGSuGLnm7eSMzkkmvj6eDqU"
    assert result.block_time == 1_715_000_000
    assert result.slot == 312_456_789


def test_verify_from_fixture_rejects_wrong_memo():
    payload = json.loads(LEGACY_FIXTURE.read_text(encoding="utf-8"))
    tx = _rpc_value_from_result_json(payload)

    with pytest.raises(ValueError, match="memo"):
        verify_fetched_solana_transaction(
            tx,
            tx_hash=payload["transaction"]["signatures"][0],
            expected_destination=DESTINATION,
            expected_lamports=EXPECTED_LAMPORTS,
            expected_memo="wrong_order_ref",
            expected_reference=REFERENCE,
        )


@pytest.mark.skipif(
    not REAL_FIXTURE.exists(),
    reason="Record a real devnet deposit via Scripts/record_solana_get_transaction.py",
)
def test_verify_from_recorded_real_get_transaction():
    """Requires get_transaction_deposit_real.json (full RPC result object)."""
    meta = json.loads(REAL_FIXTURE.read_text(encoding="utf-8"))
    # File may be {result, expected_*} or bare result.
    if "result" in meta:
        payload = meta["result"]
        expected = meta.get("expected", {})
    else:
        payload = meta
        expected = {}

    tx = _rpc_value_from_result_json(payload)
    result = verify_fetched_solana_transaction(
        tx,
        tx_hash=expected.get("tx_hash") or payload["transaction"]["signatures"][0],
        expected_destination=expected["destination"],
        expected_lamports=int(expected["lamports"]),
        expected_memo=expected["memo"],
        expected_reference=expected["reference"],
    )
    assert result.received_lamports >= int(expected["lamports"])


@pytest.mark.skipif(
    not V0_ALT_FIXTURE.exists(),
    reason="Record a v0+ALT deposit via Scripts/record_solana_get_transaction.py",
)
def test_verify_from_recorded_v0_alt_get_transaction():
    meta = json.loads(V0_ALT_FIXTURE.read_text(encoding="utf-8"))
    if "result" in meta:
        payload = meta["result"]
        expected = meta.get("expected", {})
    else:
        payload = meta
        expected = {}

    tx = _rpc_value_from_result_json(payload)
    result = verify_fetched_solana_transaction(
        tx,
        tx_hash=expected.get("tx_hash") or payload["transaction"]["signatures"][0],
        expected_destination=expected["destination"],
        expected_lamports=int(expected["lamports"]),
        expected_memo=expected["memo"],
        expected_reference=expected["reference"],
    )
    assert result.received_lamports >= int(expected["lamports"])
