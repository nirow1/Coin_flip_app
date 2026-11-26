import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from solders.signature import Signature

from Backend.config import settings
from Backend.Wallet.router import solana_webhook

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

    # Signature.from_string is mocked in the wallet conftest, so a real RPC
    # call cannot run. A missing tx must still ack.
    with patch(
        "Backend.Wallet.services.WalletService._fetch_finalized_tx",
        new_callable=AsyncMock,
        return_value=None,
    ):
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


async def test_solana_webhook_non_ascii_header():
    """Non-ASCII HMAC header → 401 before compare_digest.

    httpx refuses to send a non-ASCII header, so this calls the route directly.
    """
    raw_body = json.dumps({"signature": VALID_TX_SIG}).encode()
    request = _WebhookRequest(
        {
            "content-length": str(len(raw_body)),
            "x-webhook-signature": "café",
            "x-webhook-timestamp": str(int(time.time())),
        },
        body=raw_body,
    )
    with pytest.raises(HTTPException) as exc:
        await solana_webhook(request, session=AsyncMock(), _=None)  # type: ignore[arg-type]
    assert exc.value.status_code == 401


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


class _WebhookRequest:
    def __init__(self, headers: dict[str, str], body: bytes = b"{}") -> None:
        self.headers = headers
        self._body = body
        self.body_reads = 0

    async def body(self) -> bytes:
        self.body_reads += 1
        return self._body


async def test_webhook_missing_content_length_is_413_before_body_read():
    request = _WebhookRequest({})
    with pytest.raises(HTTPException) as exc:
        await solana_webhook(request, session=None, _=None)  # type: ignore[arg-type]
    assert exc.value.status_code == 413
    assert request.body_reads == 0


async def test_webhook_oversized_content_length_is_413_before_body_read():
    request = _WebhookRequest({"content-length": "4097"})
    with pytest.raises(HTTPException) as exc:
        await solana_webhook(request, session=None, _=None)  # type: ignore[arg-type]
    assert exc.value.status_code == 413
    assert "too large" in str(exc.value.detail).lower()
    assert request.body_reads == 0


async def test_webhook_small_content_length_still_reads_body_for_hmac():
    """A short declared length is accepted far enough to verify the HMAC."""
    request = _WebhookRequest(
        {
            "content-length": "2",
            "x-webhook-signature": "ab",
            "x-webhook-timestamp": "1",
        }
    )
    with pytest.raises(HTTPException) as exc:
        await solana_webhook(request, session=None, _=None)  # type: ignore[arg-type]
    assert request.body_reads == 1
    assert exc.value.status_code == 401


def _strict_signature_from_string(value: str):
    """Real base58 check. The wallet conftest replaces Signature.from_string."""
    import base58
    from solders.signature import Signature as Sig

    raw = base58.b58decode(value)
    if len(raw) != 64:
        raise ValueError("signature must be 64 bytes")
    return Sig.from_bytes(raw)


async def test_solana_webhook_invalid_tx_signature_after_hmac(solana_client):
    """Invalid base58 tx signature after valid HMAC → 422."""
    client = solana_client["client"]

    raw_body = json.dumps({"signature": "not-a-valid-solana-sig"}).encode()
    ts, signature = _sign(raw_body)

    with patch(
        "Backend.Wallet.schemas.Signature.from_string",
        side_effect=_strict_signature_from_string,
    ):
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
