from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from Core.core_solana import  solana_send_transaction
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


DESTINATION = "So11111111111111111111111111111111111111112"
AMOUNT_SOL = Decimal("1.00")
FAKE_SIGNATURE = "5J3WPMWkDNxXMBKFyPaXwDVJPcaJUCVFhxSEtBrh6vNgJ2qX8ZpYcR3TnLm7KsQwE9uAbCdEfGhIjKlMnOpQrSt"


async def test_solana_send_transaction_success(mock_keypair):
    """Valid destination and amount → transaction sent, signature returned."""
    mock_client = AsyncMock()

    # Mock get_latest_blockhash
    mock_client.get_latest_blockhash.return_value.value.blockhash = MagicMock()

    # Mock send_raw_transaction
    mock_client.send_raw_transaction.return_value.value = FAKE_SIGNATURE

    # Mock confirm_transaction
    mock_client.confirm_transaction.return_value = MagicMock()

    with patch("Core.core_solana.AsyncClient", return_value=mock_client), \
         patch("Core.core_solana.Transaction.new_signed_with_payer", return_value=MagicMock()), \
         patch("Core.core_solana.Pubkey.from_string", return_value=MagicMock()), \
         patch("Core.core_solana.TransferParams", return_value=MagicMock()), \
         patch("Core.core_solana.transfer", return_value=MagicMock()):

        result = await solana_send_transaction(
            destination_address=DESTINATION,
            amount_sol=AMOUNT_SOL,
            rpc_url="https://api.mainnet-beta.solana.com",
        )

    assert result == str(FAKE_SIGNATURE)
    mock_client.send_raw_transaction.assert_called_once()
    mock_client.confirm_transaction.assert_called_once()


async def test_solana_send_transaction_rpc_unreachable(mock_keypair):
    """RPC node unreachable → get_latest_blockhash raises, exception propagates."""
    mock_client = AsyncMock()
    mock_client.get_latest_blockhash.side_effect = Exception("RPC unreachable")

    with patch("Core.core_solana.AsyncClient", return_value=mock_client), \
         patch("Core.core_solana.Transaction.new_signed_with_payer", return_value=MagicMock()), \
         patch("Core.core_solana.Pubkey.from_string", return_value=MagicMock()), \
         patch("Core.core_solana.TransferParams", return_value=MagicMock()), \
         patch("Core.core_solana.transfer", return_value=MagicMock()):
        with pytest.raises(Exception, match="RPC unreachable"):
            await solana_send_transaction(
                destination_address=DESTINATION,
                amount_sol=AMOUNT_SOL,
                rpc_url="https://api.mainnet-beta.solana.com",
            )

    mock_client.send_raw_transaction.assert_not_called()
    mock_client.confirm_transaction.assert_not_called()
 
 
async def test_solana_send_transaction_send_fails(mock_keypair):
    """send_raw_transaction returns value=None → Exception raised, confirm never called."""
    mock_client = AsyncMock()
    mock_client.get_latest_blockhash.return_value.value.blockhash = MagicMock()
    mock_client.send_raw_transaction.return_value.value = None

    with patch("Core.core_solana.AsyncClient", return_value=mock_client), \
            patch("Core.core_solana.Transaction.new_signed_with_payer", return_value=MagicMock()), \
            patch("Core.core_solana.Pubkey.from_string", return_value=MagicMock()), \
            patch("Core.core_solana.TransferParams", return_value=MagicMock()), \
            patch("Core.core_solana.transfer", return_value=MagicMock()):
        with pytest.raises(Exception, match="send_raw_transaction failed: no signature returned"):
            await solana_send_transaction(
                destination_address=DESTINATION,
                amount_sol=AMOUNT_SOL,
                rpc_url="https://api.mainnet-beta.solana.com",
            )

    mock_client.confirm_transaction.assert_not_called()


async def test_solana_send_transaction_confirm_fails(mock_keypair):
    mock_client = AsyncMock()
    mock_client.get_latest_blockhash.return_value.value.blockhash = MagicMock()
    mock_client.send_raw_transaction.return_value.value = FAKE_SIGNATURE
    mock_client.confirm_transaction.side_effect = Exception("Transaction failed to confirm")

    with patch("Core.core_solana.AsyncClient", return_value=mock_client), \
            patch("Core.core_solana.Transaction.new_signed_with_payer", return_value=MagicMock()), \
            patch("Core.core_solana.Pubkey.from_string", return_value=MagicMock()), \
            patch("Core.core_solana.TransferParams", return_value=MagicMock()), \
            patch("Core.core_solana.transfer", return_value=MagicMock()):
        with pytest.raises(Exception, match="SENT_UNCONFIRMED"):
            await solana_send_transaction(
                destination_address=DESTINATION,
                amount_sol=AMOUNT_SOL,
                rpc_url="https://api.mainnet-beta.solana.com",
            )

    mock_client.send_raw_transaction.assert_called_once()


async def test_solana_send_transaction_keypair_file_not_found():
    """Keypair file missing → FileNotFoundError propagates before any RPC call."""
    mock_client = AsyncMock()

    with patch("builtins.open", side_effect=FileNotFoundError("No such file or directory")), \
         patch("Core.core_solana.AsyncClient", return_value=mock_client):
        with pytest.raises(FileNotFoundError):
            await solana_send_transaction(
                destination_address=DESTINATION,
                amount_sol=AMOUNT_SOL,
                rpc_url="https://api.mainnet-beta.solana.com",
            )

    mock_client.get_latest_blockhash.assert_not_called()
    mock_client.send_raw_transaction.assert_not_called()
    mock_client.confirm_transaction.assert_not_called()
