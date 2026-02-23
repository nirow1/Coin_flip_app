import pytest

@pytest.mark.asyncio
async def test_login_user(client):
    # First, register a user to ensure we have a valid account to log in with
    await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "Secret123",
        "country": "CZ",
        "dob": "2000-01-01"
    })

    # Now, attempt to log in with the registered user's credentials
    response = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "Secret123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_login_wrong_password(client):
    # Register a user first
    await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "Secret123",
        "country": "CZ",
        "dob": "2000-01-01"
    })

    # Attempt login with wrong password
    response = await client.post("/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPass123"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"

@pytest.mark.asyncio
async def test_login_wrong_email(client):
    # Attempt login with an email that doesn't exist
    response = await client.post("/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "Secret123"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"
