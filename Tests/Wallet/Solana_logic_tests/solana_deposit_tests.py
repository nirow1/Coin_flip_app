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

# --- Router-level failures ---

async def test_deposit_sol_invalid_webhook_signature(solana_client):
    """Request arrives with wrong/missing x-webhook-signature header → 401, balance unchanged."""
    client = solana_client["client"]
    token = solana_client["token"]
    public_key = solana_client["public_key"]

    balance_before = Decimal(
        (await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])

    payload = {
        "tx_hash": "sig_test_tx_hash_abc123",
        "destination_address": public_key,
        "amount_sol": "1.00",
    }

    raw_body = json.dumps(payload).encode()

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": "completely_wrong_signature",
        },
    )

    assert response.status_code == 401
    assert "Invalid webhook signature" in response.json()["detail"]

    balance_after = Decimal(
        (await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])
    assert balance_after == balance_before


# --- Router-level failures ---

async def test_deposit_sol_unknown_solana_address(solana_client):
    """Destination address in payload is not linked to any user → 404, balance unchanged."""
    client = solana_client["client"]
    token = solana_client["token"]

    balance_before = Decimal(
        (await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])

    payload = {
        "tx_hash": "unknown_addr_tx_hash_abc123",
        "destination_address": "UnknownAddress1111111111111111111111111111",
        "amount_sol": "1.00",
    }

    raw_body = json.dumps(payload).encode()
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
                "x-webhook-signature": signature,
            },
        )

    assert response.status_code == 404
    assert "Solana address not linked to any user" in response.json()["detail"]

    balance_after = Decimal(
        (await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])
    assert balance_after == balance_before


# --- Idempotency ---

async def test_deposit_sol_duplicate_tx_hash(solana_client):
    """Same tx_hash submitted twice → second call rejected, balance credited only once."""
    client     = solana_client["client"]
    token      = solana_client["token"]
    public_key = solana_client["public_key"]

    balance_before = Decimal(
        (await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])

    payload = {
        "tx_hash": "duplicate_tx_hash_abc123",
        "destination_address": public_key,
        "amount_sol": "1.00",
    }

    raw_body = json.dumps(payload).encode()
    signature = hmac.new(
        settings.SOLANA_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    headers = {"Content-Type": "application/json", "x-webhook-signature": signature}

    with patch("Wallet.services.verify_solana_transaction", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True

        first = await client.post("/wallet/webhook/solana", content=raw_body, headers=headers)
        second = await client.post("/wallet/webhook/solana", content=raw_body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 409

    balance_after = Decimal(
        (await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"])
    assert balance_after == balance_before + Decimal("1.00")
