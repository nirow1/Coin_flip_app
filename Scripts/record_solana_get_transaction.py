"""Record a real getTransaction JSON for verify fixture tests.

Usage (from repo root, with Backend/.env loaded or env vars set):

  python Scripts/record_solana_get_transaction.py \\
    --signature <base58_sig> \\
    --out Backend/Tests/Wallet/Solana_logic_tests/fixtures/get_transaction_deposit_real.json \\
    --destination <cold> --lamports <n> --memo <order_ref> --reference <pubkey>

Sends getTransaction (jsonParsed, finalized, maxSupportedTransactionVersion=0)
and writes {result, expected} for test_verify_from_fixture.py.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Allow `python Scripts/...` from repo root.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from solana.rpc.async_api import AsyncClient  # noqa: E402
from solana.rpc.commitment import Finalized  # noqa: E402
from solders.signature import Signature  # noqa: E402

from Backend.config import settings  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signature", required=True)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--lamports", required=True, type=int)
    parser.add_argument("--memo", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--rpc-url", default=None)
    args = parser.parse_args()

    rpc = args.rpc_url or settings.SOLANA_RPC_URL
    sig = Signature.from_string(args.signature)

    async with AsyncClient(rpc, timeout=30) as client:
        resp = await client.get_transaction(
            sig,
            encoding="jsonParsed",
            commitment=Finalized,
            max_supported_transaction_version=0,
        )

    if resp.value is None:
        raise SystemExit(f"transaction {args.signature} not found / not finalized")

    # Re-fetch raw JSON via HTTP so the fixture matches RPC wire shape.
    import httpx

    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getTransaction",
        "params": [
            args.signature,
            {
                "encoding": "jsonParsed",
                "commitment": "finalized",
                "maxSupportedTransactionVersion": 0,
            },
        ],
    }
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.post(rpc, json=body)
        r.raise_for_status()
        rpc_json = r.json()

    if rpc_json.get("result") is None:
        raise SystemExit(f"RPC returned null result: {rpc_json}")

    out = {
        "result": rpc_json["result"],
        "expected": {
            "tx_hash": args.signature,
            "destination": args.destination,
            "lamports": args.lamports,
            "memo": args.memo,
            "reference": args.reference,
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
