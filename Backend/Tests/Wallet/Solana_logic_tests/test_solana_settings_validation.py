from unittest.mock import MagicMock, patch

import pytest

from Backend.Core.core_solana import validate_solana_settings_local


def test_validate_solana_settings_rejects_mint_cluster_mismatch():
    with patch("Backend.Core.core_solana.settings") as mock_settings:
        mock_settings.SOLANA_CLUSTER = "devnet"
        # Mainnet mint while cluster is devnet
        mock_settings.SOLANA_USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        mock_settings.SOLANA_HOT_WALLET_SECRET = "[1]"
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = "ignored"

        with pytest.raises(RuntimeError, match="SOLANA_USDC_MINT"):
            validate_solana_settings_local()


def test_validate_solana_settings_rejects_keypair_address_mismatch():
    mock_keypair = MagicMock()
    mock_keypair.pubkey.return_value = "ActualPubkey111111111111111111111111111"

    with patch("Backend.Core.core_solana.settings") as mock_settings, \
         patch("Backend.Core.core_solana.load_hot_keypair", return_value=mock_keypair):
        mock_settings.SOLANA_CLUSTER = "devnet"
        mock_settings.SOLANA_USDC_MINT = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
        mock_settings.SOLANA_HOT_WALLET_ADDRESS = "DifferentAddress111111111111111111111"

        with pytest.raises(RuntimeError, match="does not match SOLANA_HOT_WALLET_ADDRESS"):
            validate_solana_settings_local()
