import pytest
from decimal import Decimal
from httpx import AsyncClient
from Wallet.services import WalletService

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_get_balance(client, test_user):
    headers = {"Authorization": f"Bearer {test_user['token']}"}


    response = await client.get("/wallet/balance", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert "balance" in data
    assert Decimal(data["balance"]) == Decimal("0.00")

async def test_credit_wallet(client, test_user):
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    response = await client.post(
        "/wallet/credit",
        headers=headers,
        json={"amount": "50"}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["balance"] == "50"

async def test_debit_wallet(client, test_user):
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    await client.post("/wallet/credit", headers=headers, json={"amount": "100"})

    response = await client.post(
        "/wallet/debit",
        headers=headers,
        json={"amount": "30"}
    )
    assert response.status_code == 200

    data = response.json()
    assert data["balance"] == "70"

async def test_get_transactions(client: AsyncClient, test_user):
    headers = {"Authorization": f"Bearer {test_user['token']}"}

    # Create wallet, do credit and debit, then check via router
    await client.post("/wallet/credit", headers=headers, json={"amount": "20"})
    await client.post("/wallet/debit", headers=headers, json={"amount": "5"})
    response = await client.get("/wallet/transactions", headers=headers)
    assert response.status_code == 200

    transactions = response.json()
    assert len(transactions) == 2
    amounts = {Decimal(t["amount"]) for t in transactions}
    assert Decimal("100") in amounts
    assert Decimal("-30") in amounts

async def test_get_balance_unauthorized():
    response = await client.get("/wallet/balance")
    assert response.status_code == 401
