from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from fastapi import HTTPException
from Wallet.services import WalletService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

RAW_BODY = b"this is test raw body"
VALID_SIGNATURE = "valid_hmac_signature_abc123"
DESTINATION = "So11111111111111111111111111111111111111112"
AMOUNT_SOL = Decimal("10.00")
TX_HASH = "valid_tx_hash_abc123"


def _make_service():
    """Returns WalletService with a fully mocked async session."""
    session = AsyncMock()
    return WalletService(session)


async def test_process_solana_webhook_success():
    service = _make_service()

    mock_hmac = MagicMock()
    mock_hmac.hexdigest.return_value = VALID_SIGNATURE

    mock_solana_wallet = MagicMock()
    mock_solana_wallet.user_id = 1

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_solana_wallet
    service.session.execute.return_value = mock_result

    with patch("Wallet.services.hmac.new", return_value=mock_hmac), \
         patch.object(service, "deposit_sol", new_callable=AsyncMock) as mock_deposit:
        await service.process_solana_webhook(
            raw_body=RAW_BODY,
            signature=VALID_SIGNATURE,
            payload_destination=DESTINATION,
            amount_sol=AMOUNT_SOL,
            tx_hash=TX_HASH,
        )

    mock_deposit.assert_called_once_with(
        user_id=1,
        amount_sol=AMOUNT_SOL,
        tx_hash=TX_HASH,
    )



async def test_process_solana_webhook_invalid_signature():
    service = _make_service()

    mock_hmac = MagicMock()
    mock_hmac.hexdigest.return_value = VALID_SIGNATURE

    with patch("Wallet.services.hmac.new", return_value=mock_hmac), \
         patch.object(service, "deposit_sol", new_callable=AsyncMock) as mock_deposit:
        with pytest.raises(HTTPException) as exc:
            await service.process_solana_webhook(
                raw_body=RAW_BODY,
                signature="invalid_hmac_signature_abc123",
                payload_destination=DESTINATION,
                amount_sol=AMOUNT_SOL,
                tx_hash=TX_HASH,
            )

    assert exc.value.status_code == 401
    assert "Invalid webhook signature" in exc.value.detail
    mock_deposit.assert_not_called()


async def test_process_solana_webhook_not_linked_to_user():
    service = _make_service()

    mock_hmac = MagicMock()
    mock_hmac.hexdigest.return_value = VALID_SIGNATURE

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    service.session.execute.return_value = mock_result

    with patch("Wallet.services.hmac.new", return_value=mock_hmac), \
            patch.object(service, "deposit_sol", new_callable=AsyncMock) as mock_deposit:
        with pytest.raises(HTTPException) as exc:
            await service.process_solana_webhook(
                raw_body=RAW_BODY,
                signature=VALID_SIGNATURE,
                payload_destination=DESTINATION,
                amount_sol=AMOUNT_SOL,
                tx_hash=TX_HASH,
            )

    assert exc.value.status_code == 404
    assert "Solana address not linked to any user" in exc.value.detail
    mock_deposit.assert_not_called()
