import hashlib
import hmac
import json

import pytest

from Backend.config import settings

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_solana_webhook_acks_signature_only(solana_client):
    """Signature-only payload + valid HMAC → 200; balance unchanged (no CreditOrder yet)."""
    client = solana_client["client"]
    token = solana_client["token"]

    balance_before = (
        await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})
    ).json()["balance"]

    payload = {"signature": "webhook_router_ack_tx_sig"}
    raw_body = json.dumps(payload).encode()
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

    assert response.status_code == 200
    assert response.json() == {"message": "ok"}

    balance_after = (
        await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})
    ).json()["balance"]
    assert balance_after == balance_before


async def test_solana_webhook_invalid_signature(solana_client):
    """Wrong HMAC signature → 401."""
    client = solana_client["client"]

    payload = {"signature": "webhook_invalid_sig_tx"}
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
    client = solana_client["client"]

    payload = {"signature": "webhook_missing_sig_tx"}
    raw_body = json.dumps(payload).encode()

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 401


async def test_solana_webhook_invalid_payload(solana_client):
    """Malformed payload missing signature → FastAPI returns 422 before service is called."""
    client = solana_client["client"]

    raw_body = json.dumps({"tx_hash": "old_field_not_accepted"}).encode()
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
