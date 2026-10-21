import hashlib
import hmac
import json
import time

import pytest
from solders.signature import Signature

from Backend.config import settings

pytestmark = pytest.mark.asyncio(loop_scope="session")

# Valid base58 Solana signature (64 zero bytes) for payload validation.
VALID_TX_SIG = str(Signature.default())


def _webhook_secret() -> str:
    secret = settings.SOLANA_WEBHOOK_SECRET
    return secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)


def _sign(raw_body: bytes, timestamp: str | None = None) -> tuple[str, str]:
    ts = timestamp if timestamp is not None else str(int(time.time()))
    signed = f"{ts}.".encode("ascii") + raw_body
    digest = hmac.new(_webhook_secret().encode(), signed, hashlib.sha256).hexdigest()
    return ts, digest


async def test_solana_webhook_acks_signature_only(solana_client):
    """Signature-only payload + valid HMAC → 200; balance unchanged (no CreditOrder yet)."""
    client = solana_client["client"]
    token = solana_client["token"]

    balance_before = (
        await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})
    ).json()["balance"]

    payload = {"signature": VALID_TX_SIG}
    raw_body = json.dumps(payload).encode()
    ts, signature = _sign(raw_body)

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": signature,
            "x-webhook-timestamp": ts,
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

    payload = {"signature": VALID_TX_SIG}
    raw_body = json.dumps(payload).encode()
    ts = str(int(time.time()))

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": "completely_wrong_signature",
            "x-webhook-timestamp": ts,
        },
    )

    assert response.status_code == 401
    assert "Invalid webhook signature" in response.json()["detail"]


async def test_solana_webhook_missing_signature_header(solana_client):
    """Missing x-webhook-signature header → 401."""
    client = solana_client["client"]

    payload = {"signature": VALID_TX_SIG}
    raw_body = json.dumps(payload).encode()
    ts = str(int(time.time()))

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-timestamp": ts,
        },
    )

    assert response.status_code == 401


async def test_solana_webhook_stale_timestamp(solana_client):
    """Timestamp older than 5 minutes → 401."""
    client = solana_client["client"]

    payload = {"signature": VALID_TX_SIG}
    raw_body = json.dumps(payload).encode()
    stale_ts = str(int(time.time()) - 600)
    _, signature = _sign(raw_body, timestamp=stale_ts)

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": signature,
            "x-webhook-timestamp": stale_ts,
        },
    )

    assert response.status_code == 401
    assert "timestamp" in response.json()["detail"].lower()


async def test_solana_webhook_non_ascii_header(solana_client):
    """Non-ASCII HMAC header → 401 before compare_digest."""
    client = solana_client["client"]

    payload = {"signature": VALID_TX_SIG}
    raw_body = json.dumps(payload).encode()
    ts = str(int(time.time()))

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": "café",
            "x-webhook-timestamp": ts,
        },
    )

    assert response.status_code == 401


async def test_solana_webhook_invalid_payload_after_hmac(solana_client):
    """Malformed payload after valid HMAC → 422 (not unauthenticated 422)."""
    client = solana_client["client"]

    raw_body = json.dumps({"tx_hash": "old_field_not_accepted"}).encode()
    ts, signature = _sign(raw_body)

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": signature,
            "x-webhook-timestamp": ts,
        },
    )

    assert response.status_code == 422


async def test_solana_webhook_invalid_tx_signature_after_hmac(solana_client):
    """Invalid base58 tx signature after valid HMAC → 422."""
    client = solana_client["client"]

    raw_body = json.dumps({"signature": "not-a-valid-solana-sig"}).encode()
    ts, signature = _sign(raw_body)

    response = await client.post(
        "/wallet/webhook/solana",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "x-webhook-signature": signature,
            "x-webhook-timestamp": ts,
        },
    )

    assert response.status_code == 422
