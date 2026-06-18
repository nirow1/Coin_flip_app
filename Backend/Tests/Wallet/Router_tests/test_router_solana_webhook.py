from unittest.mock import AsyncMock, patch
from decimal import Decimal
import hashlib
import json
import hmac
import pytest

from Backend.config import settings

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_solana_webhook_success(solana_client):
    client     = solana_client["client"]
    token      = solana_client["token"]
    public_key = solana_client["public_key"]

    balance_before = Decimal(
        (await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"]
    )

    payload = {
        "tx_hash": "webhook_router_success_tx_hash",
        "destination_address": public_key,
        "amount_sol": "1.00",
    }

    raw_body = json.dumps(payload).encode()
    signature = hmac.new(
        settings.SOLANA_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    with patch("Backend.Wallet.services.verify_solana_transaction", new_callable=AsyncMock) as mock_verify:
        mock_verify.return_value = True

        response = await client.post(
            "/wallet/webhook/solana",
            content=raw_body,
            headers={
                "Content-Type": "application/json",
                "x-webhook-signature": signature,
            },
        )

    assert response.status_code == 200
    assert response.json() == {"message": "Deposit processed"}

    balance_after = Decimal(
        (await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})).json()["balance"]
    )
    assert balance_after == balance_before + Decimal("1.00")


async def test_solana_webhook_invalid_signature(solana_client):
    """Wrong HMAC signature → 401."""
    client    = solana_client["client"]
    public_key = solana_client["public_key"]

    payload = {
        "tx_hash": "webhook_invalid_sig_tx_hash",
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


async def test_solana_webhook_missing_signature_header(solana_client):
    """Missing x-webhook-signature header → router passes empty string → 401."""
    client     = solana_client["client"]
    public_key = solana_client["public_key"]

    payload = {
        "tx_hash": "webhook_missing_sig_tx_hash",
        "destination_address": public_key,
        "amount_sol": "1.00",
    }
    raw_body = json.dumps(payload).encode()

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401


async def test_solana_webhook_invalid_payload(solana_client):
    """Malformed payload missing required fields → FastAPI returns 422 before service is called."""
    client = solana_client["client"]

    raw_body = json.dumps({"tx_hash": "only_one_field"}).encode()
    signature = hmac.new(
        settings.SOLANA_WEBHOOK_SECRET.encode(),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": signature,
        },
    )

    assert response.status_code == 422

