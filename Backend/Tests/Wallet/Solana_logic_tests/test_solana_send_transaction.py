from contextlib import ExitStack
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from solana.constants import LAMPORTS_PER_SOL

from solana.rpc.commitment import Confirmed

from Backend.Core.core_solana import (
    SYSTEM_ACCOUNT_RENT_EXEMPT_LAMPORTS,
    SendFailedOnChain,
    SendFailedRefundable,
    SentUnconfirmed,
    SolanaSendError,
    broadcast_and_confirm,
    build_signed_sol_transfer,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")

DESTINATION = "So11111111111111111111111111111111111111112"
AMOUNT_SOL = Decimal("1.00")
LAMPORTS = int(AMOUNT_SOL * LAMPORTS_PER_SOL)
RPC_URL = "https://api.devnet.solana.com"
FAKE_SIGNATURE = "5J3WPMWkDNxXMBKFyPaXwDVJPcaJUCVFhxSEtBrh6vNgJ2qX8ZpYcR3TnLm7KsQwE9uAbCdEfGhIjKlMnOpQrSt"
RAW_BYTES = b"signed-tx-bytes"
HOUSE_HOT = "Hot1111111111111111111111111111111111111111"
HOUSE_COLD = "Cold111111111111111111111111111111111111111"


class _FakeSignature:
    def __init__(self, value: str) -> None:
        self._value = value

    def __str__(self) -> str:
        return self._value


class _FakeTx:
    def __init__(self, signature_str: str = FAKE_SIGNATURE) -> None:
        self.signatures = [_FakeSignature(signature_str)]

    def __bytes__(self) -> bytes:
        return RAW_BYTES


def _mock_client() -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.get_latest_blockhash.return_value.value.blockhash = MagicMock()
    mock_client.get_latest_blockhash.return_value.value.last_valid_block_height = 100
    return mock_client


def _patch_house_settings() -> object:
    return patch(
        "Backend.Core.core_solana.settings",
        SOLANA_HOT_WALLET_ADDRESS=HOUSE_HOT,
        SOLANA_COLD_RECEIVE_ADDRESS=HOUSE_COLD,
        SOLANA_HOT_WALLET_SECRET="[1]",
    )


def _build_stack(mock_client: AsyncMock, signed_tx: _FakeTx | None = None) -> ExitStack:
    stack = ExitStack()
    stack.enter_context(patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client))
    stack.enter_context(
        patch(
            "Backend.Core.core_solana.Transaction.new_signed_with_payer",
            return_value=signed_tx or _FakeTx(),
        )
    )
    stack.enter_context(_patch_house_settings())
    stack.enter_context(patch("Backend.Core.core_solana.TransferParams", return_value=MagicMock()))
    stack.enter_context(patch("Backend.Core.core_solana.transfer", return_value=MagicMock()))
    return stack


def _broadcast_stack(mock_client: AsyncMock) -> ExitStack:
    stack = ExitStack()
    stack.enter_context(patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client))
    stack.enter_context(
        patch(
            "Backend.Core.core_solana.Signature.from_string",
            return_value=_FakeSignature(FAKE_SIGNATURE),
        )
    )
    return stack


async def test_build_signed_sol_transfer_success(mock_keypair):
    """Valid destination and lamports → signed bytes, signature, block height."""
    mock_client = _mock_client()

    with _build_stack(mock_client):
        raw, signature, last_height = await build_signed_sol_transfer(
            destination_address=DESTINATION,
            lamports=LAMPORTS,
            rpc_url=RPC_URL,
        )

    mock_client.get_latest_blockhash.assert_awaited_once_with(commitment=Confirmed)

    assert signature == FAKE_SIGNATURE
    assert last_height == 100
    assert raw == RAW_BYTES
    mock_client.send_raw_transaction.assert_not_called()
    mock_client.confirm_transaction.assert_not_called()


async def test_build_signed_sol_transfer_rpc_unreachable(mock_keypair):
    """RPC node unreachable → get_latest_blockhash raises, exception propagates."""
    mock_client = _mock_client()
    mock_client.get_latest_blockhash.side_effect = Exception("RPC unreachable")

    with _build_stack(mock_client):
        with pytest.raises(Exception, match="RPC unreachable"):
            await build_signed_sol_transfer(
                destination_address=DESTINATION,
                lamports=LAMPORTS,
                rpc_url=RPC_URL,
            )

    mock_client.send_raw_transaction.assert_not_called()
    mock_client.confirm_transaction.assert_not_called()


async def test_build_signed_sol_transfer_keypair_secret_missing():
    """Empty hot wallet secret → RuntimeError before any RPC call."""
    mock_client = _mock_client()

    with patch("Backend.Core.core_solana.settings") as mock_settings, \
         patch("Backend.Core.core_solana.AsyncClient", return_value=mock_client):
        mock_settings.SOLANA_HOT_WALLET_SECRET = ""
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = HOUSE_HOT
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = HOUSE_COLD
        with pytest.raises(RuntimeError, match="SOLANA_HOT_WALLET_SECRET"):
            await build_signed_sol_transfer(
                destination_address=DESTINATION,
                lamports=LAMPORTS,
                rpc_url=RPC_URL,
            )

    mock_client.get_latest_blockhash.assert_not_called()
    mock_client.send_raw_transaction.assert_not_called()
    mock_client.confirm_transaction.assert_not_called()


async def test_build_signed_sol_transfer_rejects_zero_lamports(mock_keypair):
    with pytest.raises(ValueError, match="positive"):
        await build_signed_sol_transfer(
            destination_address=DESTINATION,
            lamports=0,
            rpc_url=RPC_URL,
        )


async def test_build_signed_sol_transfer_rejects_below_rent(mock_keypair):
    with pytest.raises(ValueError, match="rent-exempt"):
        await build_signed_sol_transfer(
            destination_address=DESTINATION,
            lamports=SYSTEM_ACCOUNT_RENT_EXEMPT_LAMPORTS - 1,
            rpc_url=RPC_URL,
        )


async def test_build_signed_sol_transfer_rejects_house_destination(mock_keypair):
    with patch("Backend.Core.core_solana.settings") as mock_settings:
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = DESTINATION
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = HOUSE_COLD
        mock_settings.SOLANA_HOT_WALLET_SECRET = "[1]"
        with pytest.raises(ValueError, match="house"):
            await build_signed_sol_transfer(
                destination_address=DESTINATION,
                lamports=LAMPORTS,
                rpc_url=RPC_URL,
            )


async def test_broadcast_and_confirm_success():
    mock_client = _mock_client()
    mock_client.send_raw_transaction.return_value.value = MagicMock()
    ok_status = MagicMock()
    ok_status.err = None
    mock_client.confirm_transaction.return_value.value = [ok_status]

    with _broadcast_stack(mock_client):
        result = await broadcast_and_confirm(
            RAW_BYTES,
            FAKE_SIGNATURE,
            100,
            RPC_URL,
        )

    assert result == FAKE_SIGNATURE
    mock_client.send_raw_transaction.assert_called_once()
    mock_client.confirm_transaction.assert_called_once()
    assert mock_client.confirm_transaction.call_args.kwargs["last_valid_block_height"] == 100


async def test_broadcast_and_confirm_send_fails_sig_present_not_refundable():
    """send_raw_transaction raises but signature present on-chain → SentUnconfirmed."""
    mock_client = _mock_client()
    mock_client.send_raw_transaction.side_effect = Exception("RPC send error")
    present = MagicMock()
    present.err = None
    mock_client.get_signature_statuses.return_value.value = [present]

    with _broadcast_stack(mock_client):
        with pytest.raises(SentUnconfirmed) as exc_info:
            await broadcast_and_confirm(
                RAW_BYTES,
                FAKE_SIGNATURE,
                100,
                RPC_URL,
            )

    assert exc_info.value.signature == FAKE_SIGNATURE
    mock_client.confirm_transaction.assert_not_called()


async def test_broadcast_and_confirm_send_fails_refundable():
    """Absent on-chain + blockhash expired → SendFailedRefundable."""
    mock_client = _mock_client()
    mock_client.send_raw_transaction.side_effect = Exception("RPC send error")
    mock_client.get_signature_statuses.return_value.value = [None]
    mock_client.get_block_height.return_value.value = 100

    with _broadcast_stack(mock_client):
        with pytest.raises(SendFailedRefundable) as exc_info:
            await broadcast_and_confirm(
                RAW_BYTES,
                FAKE_SIGNATURE,
                50,
                RPC_URL,
            )

    assert exc_info.value.signature == FAKE_SIGNATURE
    assert isinstance(exc_info.value, SolanaSendError)


async def test_broadcast_and_confirm_send_returns_none_classifies():
    """send_raw_transaction returns value=None → classify via on-chain lookup."""
    mock_client = _mock_client()
    mock_client.send_raw_transaction.return_value.value = None
    mock_client.get_signature_statuses.return_value.value = [None]
    mock_client.get_block_height.return_value.value = 200  # expired

    with _broadcast_stack(mock_client):
        with pytest.raises(SendFailedRefundable):
            await broadcast_and_confirm(
                RAW_BYTES,
                FAKE_SIGNATURE,
                100,
                RPC_URL,
            )

    mock_client.confirm_transaction.assert_not_called()


async def test_broadcast_and_confirm_confirm_fails():
    mock_client = _mock_client()
    mock_client.send_raw_transaction.return_value.value = MagicMock()
    mock_client.confirm_transaction.side_effect = Exception("Transaction failed to confirm")
    present = MagicMock()
    present.err = None
    mock_client.get_signature_statuses.return_value.value = [present]  # in-flight

    with _broadcast_stack(mock_client):
        with pytest.raises(SentUnconfirmed) as exc_info:
            await broadcast_and_confirm(
                RAW_BYTES,
                FAKE_SIGNATURE,
                100,
                RPC_URL,
            )

    assert exc_info.value.signature == FAKE_SIGNATURE
    mock_client.send_raw_transaction.assert_called_once()
    mock_client.get_signature_statuses.assert_called()
    assert mock_client.get_signature_statuses.call_args.kwargs.get(
        "search_transaction_history"
    ) is True


async def test_broadcast_and_confirm_rejects_on_chain_err():
    mock_client = _mock_client()
    mock_client.send_raw_transaction.return_value.value = MagicMock()
    bad_status = MagicMock()
    bad_status.err = {"InstructionError": [0, "Custom"]}
    mock_client.confirm_transaction.return_value.value = [bad_status]

    with _broadcast_stack(mock_client):
        with pytest.raises(SendFailedOnChain) as exc_info:
            await broadcast_and_confirm(
                RAW_BYTES,
                FAKE_SIGNATURE,
                100,
                RPC_URL,
            )

    assert exc_info.value.signature == FAKE_SIGNATURE
    assert isinstance(exc_info.value, SolanaSendError)
