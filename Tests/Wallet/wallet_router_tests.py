import pytest
from decimal import Decimal
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_get_balance(client, auth_user):
    token = auth_user["token"]

    response = await client.get("/wallet/balance", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200

    data = response.json()
    assert "balance" in data
    assert Decimal(data["balance"]) == Decimal("0.00")

async def test_credit_wallet(client, auth_user):
    headers = {"Authorization": f"Bearer {auth_user['token']}"}

    response = await client.post(
        "/wallet/credit",
        headers=headers,
        json={"amount": "50"}
    )
    assert response.status_code == 200

    balance = await client.get("/wallet/balance", headers=headers)

    balance_data = balance.json()
    assert Decimal(balance_data["balance"]) == Decimal("50")
    data = response.json()
    assert data["amount"] == "50"

async def test_debit_wallet(client, auth_user):
    headers = {"Authorization": f"Bearer {auth_user['token']}"}

    await client.post("/wallet/credit", headers=headers, json={"amount": "100"})

    response = await client.post(
        "/wallet/debit",
        headers=headers,
        json={"amount": "30"}
    )
    assert response.status_code == 200

    balance = await client.get("/wallet/balance", headers=headers)

    balance_data = balance.json()
    assert Decimal(balance_data["balance"]) == Decimal("70")

    data = response.json()
    assert data["amount"] == "-30"

async def test_get_transactions(client: AsyncClient, auth_user):
    headers = {"Authorization": f"Bearer {auth_user['token']}"}

    # Create wallet, do credit and debit, then check via router
    await client.post("/wallet/credit", headers=headers, json={"amount": "20"})
    await client.post("/wallet/debit", headers=headers, json={"amount": "5"})
    response = await client.get("/wallet/transactions", headers=headers)
    assert response.status_code == 200

    transactions = response.json()
    assert len(transactions) == 2
    amounts = {Decimal(t["amount"]) for t in transactions}
    assert Decimal("20") in amounts
    assert Decimal("-5") in amounts

async def test_debit_insufficient_funds(client: AsyncClient, auth_user):
    headers = {"Authorization": f"Bearer {auth_user['token']}"}

    await client.post("/wallet/credit", headers=headers, json={"amount": "10"})
    response = await client.post("/wallet/debit", headers=headers, json={"amount": "15"})

    assert response.status_code == 400

async def test_get_balance_unauthorized(client: AsyncClient):
    response = await client.get("/wallet/balance")
    assert response.status_code == 401
