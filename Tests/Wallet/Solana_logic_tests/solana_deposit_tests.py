from unittest.mock import AsyncMock, patch
from decimal import Decimal
import hashlib
import json
import hmac

import pytest

from config import settings

pytestmark = pytest.mark.asyncio(loop_scope="session")

# --- Happy path ---

async def test_deposit_sol_success(solana_client):
    """Valid tx_hash, correct destination, correct amount → 200, balance credited."""
    client      = solana_client["client"]
    token       = solana_client["token"]
    public_key  = solana_client["public_key"]

    balance_before = Decimal((await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])

    payload = {
        "tx_hash": "valid_tx_hash_abc123",
        "destination_address": public_key,
        "amount_sol": "1.00",
    }

    raw_body = json.dumps(payload).encode()

    # Compute the same HMAC the router expects
    signature = hmac.new(
        settings.SOLANA_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    with patch("Wallet.services.verify_solana_transaction", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True

        response = await client.post(
            "/wallet/webhook/solana",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "x-webhook-signature": signature,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Deposit processed"}

    balance_after = Decimal((await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])
    assert balance_after == balance_before + Decimal("1.00")


# --- on-chain verification failures ---

async def test_deposit_sol_invalid_tx(solana_client):
    """tx_hash does not exist on-chain → 400, balance unchanged."""
    client     = solana_client["client"]
    token      = solana_client["token"]
    public_key = solana_client["public_key"]

    balance_before = Decimal((await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])

    payload = {
        "tx_hash": "nonexistent_tx_hash_abc123",
        "destination_address": public_key,
        "amount_sol": "1.00",
    }

    raw_body = json.dumps(payload).encode()
    signature = hmac.new(
        settings.SOLANA_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    with patch("Wallet.services.verify_solana_transaction", new_callable=AsyncMock) as mock_verify:
        mock_verify.side_effect = ValueError("Transaction nonexistent_tx_hash_abc123 not found on-chain")

        response = await client.post(
            "/wallet/webhook/solana",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": signature,
            },
        )

    assert response.status_code == 400
    assert "not found on-chain" in response.json()["detail"]

    balance_after = Decimal((await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])
    assert balance_after == balance_before


async def test_deposit_sol_failed_onchain_tx(solana_client):
    """tx_hash exists on-chain but meta.err is set (tx failed) → 400, balance unchanged."""
    ...


async def test_deposit_sol_insufficient_amount(solana_client):
    """tx_hash is valid but transferred lamports < expected → 400, balance unchanged."""
    ...


async def test_deposit_sol_wrong_destination(solana_client):
    """tx_hash is valid but destination address doesn't match hot wallet → 400, balance unchanged."""
    ...


async def test_deposit_sol_rpc_failure(solana_client):
    """RPC node is unreachable → 400 (or 502 depending on impl), balance unchanged."""
    ...


# --- Router-level failures ---

async def test_deposit_sol_invalid_webhook_signature(solana_client):
    """Request arrives with wrong/missing x-webhook-signature header → 401, balance unchanged."""
    ...


async def test_deposit_sol_unknown_solana_address(solana_client):
    """Destination address in payload is not linked to any user → 404, balance unchanged."""
    ...


# --- Idempotency ---

async def test_deposit_sol_duplicate_tx_hash(solana_client):
    """Same tx_hash submitted twice → second call rejected, balance credited only once."""
    ...


# --- Redundant (kept as explicit safety net) ---

async def test_deposit_sol_does_not_credit_on_failure(solana_client):
    """
    Generic guard: any verification failure must never result in a balance change.
    NOTE: Overlaps with tests above if those already assert balance — can be removed
    once individual failure tests include balance assertions.
    """
    ...
