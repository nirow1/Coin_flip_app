from unittest.mock import MagicMock, patch

import pytest

from Backend.Core.core_solana import (
    validate_solana_payout_settings,
    validate_solana_settings_local,
    validate_solana_web_settings,
)

DEVNET_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
# Valid distinct pubkeys (system program + token program).
COLD = "11111111111111111111111111111111"
HOT = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"


def test_validate_solana_web_settings_rejects_mint_cluster_mismatch():
    with patch("Backend.Core.core_solana.settings") as mock_settings:
        mock_settings.SOLANA_CLUSTER = "devnet"
        mock_settings.SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = COLD
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = HOT

        with pytest.raises(RuntimeError, match="SOLANA_USDC_MINT"):
            validate_solana_web_settings()


def test_validate_solana_web_settings_rejects_testnet():
    with patch("Backend.Core.core_solana.settings") as mock_settings:
        mock_settings.SOLANA_CLUSTER = "testnet"
        mock_settings.SOLANA_USDC_MINT = "anything"
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = COLD
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = HOT

        with pytest.raises(RuntimeError, match="testnet"):
            validate_solana_web_settings()


def test_validate_solana_web_settings_rejects_same_cold_and_hot():
    with patch("Backend.Core.core_solana.settings") as mock_settings:
        mock_settings.SOLANA_CLUSTER = "devnet"
        mock_settings.SOLANA_USDC_MINT = DEVNET_MINT
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = COLD
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = COLD

        with pytest.raises(RuntimeError, match="must differ"):
            validate_solana_web_settings()


def test_validate_solana_settings_local_is_web_only():
    """Alias must not load the hot keypair."""
    with patch("Backend.Core.core_solana.settings") as mock_settings, \
         patch("Backend.Core.core_solana.load_hot_keypair") as load_kp:
        mock_settings.SOLANA_CLUSTER = "devnet"
        mock_settings.SOLANA_USDC_MINT = DEVNET_MINT
        mock_settings.SOLANA_COLD_RECEIVE_ADDRESS = COLD
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = HOT

        validate_solana_settings_local()
        load_kp.assert_not_called()


def test_validate_solana_payout_settings_rejects_keypair_address_mismatch():
    mock_keypair = MagicMock()
    mock_keypair.pubkey.return_value = "ActualPubkey111111111111111111111111111"

    with patch("Backend.Core.core_solana.settings") as mock_settings, \
         patch("Backend.Core.core_solana.load_hot_keypair", return_value=mock_keypair):
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = "DifferentAddress111111111111111111111"

        with pytest.raises(RuntimeError, match="does not match SOLANA_HOT_WALLET_ADDRESS"):
            validate_solana_payout_settings()
