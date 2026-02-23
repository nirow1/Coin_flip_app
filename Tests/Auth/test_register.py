import pytest

@pytest.mark.asyncio
async def test_register_user(client):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "Secret123",
        "country": "CZ",
        "dob": "2000-01-01"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_register_user_incorrect_password(client):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "secret123",  # No uppercase letter — should fail validation
        "country": "CZ",
        "dob": "2000-01-01"
    })
    assert response.status_code == 422
