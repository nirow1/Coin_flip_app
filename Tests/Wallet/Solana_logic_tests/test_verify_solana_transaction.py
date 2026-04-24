from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal
from solana.constants import LAMPORTS_PER_SOL
from Core.core_solana import verify_solana_transaction
import pytest

pytestmark = pytest.mark.asyncio(loop_scope="session")


@pytest.fixture(autouse=True)
def mock_signature():
    """Prevent base58 decode errors — all tests use fake tx_hash strings."""
    with patch("Core.core_solana.Signature.from_string", return_value=MagicMock()):
        yield

DESTINATION = "So11111111111111111111111111111111111111112"
AMOUNT_SOL = Decimal("1.00")
EXPECTED_LAMPORTS = int(AMOUNT_SOL * LAMPORTS_PER_SOL)


def _make_rpc_response(account_keys, pre_balances, post_balances, err=None):
    """Builds a minimal mock of the object returned by client.get_transaction()."""
    resp = MagicMock()
    resp.value.transaction.meta.err = err
    resp.value.transaction.meta.pre_balances = pre_balances
    resp.value.transaction.meta.post_balances = post_balances
    resp.value.transaction.transaction.message.account_keys = account_keys
    return resp


async def test_verify_solana_transaction_success():
    """Valid tx: destination found, sufficient lamports, no error → returns True."""
    resp = _make_rpc_response(
        account_keys=[DESTINATION, "SomeSenderAddress111111111111111111111111"],
        pre_balances=[0, 5_000_000_000],
        post_balances=[EXPECTED_LAMPORTS, 5_000_000_000 - EXPECTED_LAMPORTS],
    )

    mock_client = AsyncMock()
    mock_client.get_transaction.return_value = resp

    with patch("Core.core_solana.AsyncClient", return_value=mock_client):
        result = await verify_solana_transaction(
            tx_hash="valid_tx_hash_abc123",
            expected_destination=DESTINATION,
            expected_amount_sol=AMOUNT_SOL,
            rpc_url="https://api.mainnet-beta.solana.com",
        )

    assert result is True
