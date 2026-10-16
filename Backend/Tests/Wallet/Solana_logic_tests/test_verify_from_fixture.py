"""Verify against a recorded-shape getTransaction JSON (ParsedAccount-style keys)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from solana.constants import LAMPORTS_PER_SOL

from Backend.Core.core_solana import account_pubkey, verify_fetched_solana_transaction

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "get_transaction_deposit.json"

DESTINATION = "So11111111111111111111111111111111111111112"
REFERENCE = "9zCtsb6bLqHbtkeKbSg4uhpjmuECo4p46yREUj5SdsjL"
MEMO = "order_ref_fixture_001"
EXPECTED_LAMPORTS = 500_000_000


class _ParsedAccount:
    """Mimics solders jsonParsed account key where str(obj) is not base58."""

    def __init__(self, pubkey: str, **_meta: object) -> None:
        self.pubkey = pubkey

    def __str__(self) -> str:
        return f"ParsedAccount(pubkey={self.pubkey}, …)"


def _key_from_json(entry: dict | str) -> _ParsedAccount | str:
    """Build a ParsedAccount-like object so str(key) != pubkey (regression guard)."""
    if isinstance(entry, str):
        return entry
    return _ParsedAccount(**entry)


def _ix_from_json(ix: dict) -> SimpleNamespace:
    return SimpleNamespace(
        program_id=ix.get("programId") or ix.get("program_id"),
        programId=ix.get("programId"),
        program=ix.get("program"),
        parsed=ix.get("parsed"),
        data=ix.get("data"),
        accounts=ix.get("accounts"),
        stackHeight=ix.get("stackHeight"),
    )


def rpc_value_from_fixture(payload: dict) -> SimpleNamespace:
    """Adapt recorded RPC JSON into the attribute shape verify_fetched expects."""
    message_json = payload["transaction"]["message"]
    meta_json = payload["meta"]
    message = SimpleNamespace(
        account_keys=[_key_from_json(k) for k in message_json["accountKeys"]],
        instructions=[_ix_from_json(ix) for ix in message_json["instructions"]],
    )
    meta = SimpleNamespace(
        err=meta_json.get("err"),
        pre_balances=meta_json["preBalances"],
        post_balances=meta_json["postBalances"],
        loaded_addresses=SimpleNamespace(
            writable=list(meta_json.get("loadedAddresses", {}).get("writable", [])),
            readonly=list(meta_json.get("loadedAddresses", {}).get("readonly", [])),
        ),
    )
    return SimpleNamespace(
        transaction=SimpleNamespace(
            transaction=SimpleNamespace(message=message),
            meta=meta,
        )
    )


def test_fixture_parsed_account_pubkey_not_str():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    key = _key_from_json(payload["transaction"]["message"]["accountKeys"][1])
    assert account_pubkey(key) == DESTINATION
    assert str(key) != DESTINATION


def test_verify_from_recorded_get_transaction_json():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    tx = rpc_value_from_fixture(payload)

    received = verify_fetched_solana_transaction(
        tx,
        tx_hash=payload["transaction"]["signatures"][0],
        expected_destination=DESTINATION,
        expected_amount_sol=Decimal(EXPECTED_LAMPORTS) / Decimal(LAMPORTS_PER_SOL),
        expected_memo=MEMO,
        expected_reference=REFERENCE,
    )

    assert received == EXPECTED_LAMPORTS


def test_verify_from_fixture_rejects_wrong_memo():
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    tx = rpc_value_from_fixture(payload)

    with pytest.raises(ValueError, match="memo"):
        verify_fetched_solana_transaction(
            tx,
            tx_hash="fixture_sig",
            expected_destination=DESTINATION,
            expected_amount_sol=Decimal("0.5"),
            expected_memo="wrong_order_ref",
            expected_reference=REFERENCE,
        )
