import sys
import types

from solana.rpc.types import TxOpts

models = types.ModuleType("solana.rpc.models")
models.TxOpts = TxOpts
sys.modules["solana.rpc.models"] = models

import pytest

raise SystemExit(
    pytest.main(
        [
            "Tests/Game/Service_tests/test_service_get_players_games.py",
            "Tests/Game/Router_tests/test_router_get_my_games.py",
            "-v",
        ]
    )
)
