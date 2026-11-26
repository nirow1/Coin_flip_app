from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from Backend.Wallet.services import WalletService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

RAW_BODY = b'{"signature":"valid_tx_signature_abc123"}'
VALID_SIGNATURE = "valid_hmac_signature_abc123"
TX_SIGNATURE = "valid_tx_signature_abc123"


def _make_service():
    """Returns WalletService with a fully mocked async session."""
    session = AsyncMock()
    return WalletService(session)


async def test_process_solana_webhook_acks_unmatched():
    """Valid HMAC + unknown signature → ack (no 404, no credit)."""
    service = _make_service()

    mock_hmac = MagicMock()
    mock_hmac.hexdigest.return_value = VALID_SIGNATURE

    with patch("Backend.Wallet.services.hmac.new", return_value=mock_hmac):
        await service.process_solana_webhook(
            raw_body=RAW_BODY,
            signature=VALID_SIGNATURE,
            tx_signature=TX_SIGNATURE,
        )

    service.session.execute.assert_not_called()


async def test_process_solana_webhook_invalid_signature():
    service = _make_service()

    mock_hmac = MagicMock()
    mock_hmac.hexdigest.return_value = VALID_SIGNATURE

    with patch("Backend.Wallet.services.hmac.new", return_value=mock_hmac):
        with pytest.raises(HTTPException) as exc:
            await service.process_solana_webhook(
                raw_body=RAW_BODY,
                signature="invalid_hmac_signature_abc123",
                tx_signature=TX_SIGNATURE,
            )

    assert exc.value.status_code == 401
    assert "Invalid webhook signature" in exc.value.detail
