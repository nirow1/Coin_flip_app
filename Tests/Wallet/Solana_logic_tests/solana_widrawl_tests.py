from unittest.mock import AsyncMock, MagicMock, patch, ANY
from decimal import Decimal
from fastapi import HTTPException
from Wallet.services import WalletService
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")

AMOUNT_SOL = Decimal("10.00")
DESTINATION = "So11111111111111111111111111111111111111112"
FAKE_SIGNATURE = "5J3WPMWkDNxXMBKFyPaXwDVJPcaJUCVFhxSEtBrh6vNgJ2qX8ZpYcR3TnLm7KsQwE9uAbCdEfGhIjKlMnOpQrSt"


def _make_service():
    """Returns WalletService with a fully mocked async session."""
    session = AsyncMock()
    return WalletService(session)


async def test_withdraw_sol_success():
    service = _make_service()

    mock_transaction = MagicMock()

    with patch("Wallet.services.solana_send_transaction", new_callable=AsyncMock) as mock_send, \
         patch.object(service, "debit", new_callable=AsyncMock, return_value=mock_transaction) as mock_debit, \
         patch.object(service, "credit", new_callable=AsyncMock) as mock_credit:

        mock_send.return_value = FAKE_SIGNATURE

        result = await service.withdraw_sol(
            user_id=1,
            amount_sol=AMOUNT_SOL,
            destination_address=DESTINATION,
        )

    mock_debit.assert_called_once_with(
        user_id=1,
        amount=AMOUNT_SOL,
        transaction_type=ANY,
    )
    mock_send.assert_called_once_with(DESTINATION, AMOUNT_SOL, ANY)
    mock_credit.assert_not_called()
    assert result["tx_signature"] == FAKE_SIGNATURE
    assert result["transaction"] == mock_transaction


async def test_withdraw_sol_confirmation_failed():
    service = _make_service()

    mock_transaction = MagicMock()

    with patch("Wallet.services.solana_send_transaction", new_callable=AsyncMock) as mock_send, \
         patch.object(service, "debit", new_callable=AsyncMock, return_value=mock_transaction) as mock_debit, \
         patch.object(service, "credit", new_callable=AsyncMock) as mock_credit:

        mock_send.side_effect = Exception(f"SENT_UNCONFIRMED:{FAKE_SIGNATURE}:confirm failed")

        with pytest.raises(HTTPException) as exc:
            await service.withdraw_sol(
                user_id=1,
                amount_sol=AMOUNT_SOL,
                destination_address=DESTINATION,
            )

    assert exc.value.status_code == 502
    assert "SOL sent but confirmation failed" in exc.value.detail
    assert "Manual review required" in exc.value.detail
    mock_debit.assert_called_once()
    mock_credit.assert_not_called()  # balance must NOT be refunded — SOL is in-flight


async def test_withdraw_sol_transaction_failed():
    service = _make_service()

    mock_transaction = MagicMock()

    with patch("Wallet.services.solana_send_transaction", new_callable=AsyncMock) as mock_send, \
            patch.object(service, "debit", new_callable=AsyncMock, return_value=mock_transaction) as mock_debit, \
            patch.object(service, "credit", new_callable=AsyncMock) as mock_credit:
        mock_send.side_effect = Exception("Transaction rejected by RPC")

        with pytest.raises(HTTPException) as exc:
            await service.withdraw_sol(
                user_id=1,
                amount_sol=AMOUNT_SOL,
                destination_address=DESTINATION,
            )

    assert exc.value.status_code == 502
    assert "On-chain transaction failed, withdrawal reversed" in exc.value.detail
    mock_debit.assert_called_once()
    mock_credit.assert_called_once_with(
        user_id=1,
        amount=AMOUNT_SOL,
        transaction_type=ANY,
    )


async def test_withdraw_sol_insufficient_funds():
    service = _make_service()

    with patch("Wallet.services.solana_send_transaction", new_callable=AsyncMock) as mock_send, \
         patch.object(service, "debit", new_callable=AsyncMock) as mock_debit, \
         patch.object(service, "credit", new_callable=AsyncMock) as mock_credit:

        mock_debit.side_effect = HTTPException(status_code=400, detail="Insufficient funds")

        with pytest.raises(HTTPException) as exc:
            await service.withdraw_sol(
                user_id=1,
                amount_sol=AMOUNT_SOL,
                destination_address=DESTINATION,
            )

    assert exc.value.status_code == 400
    assert "Insufficient funds" in exc.value.detail
    mock_send.assert_not_called()
    mock_credit.assert_not_called()
