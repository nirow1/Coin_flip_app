"""Cookie auth: dual cookies, refresh success/fail, logout revoke, CSRF on game POST."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from Backend.config import settings
from Backend.Core.security import create_refresh_token

REGISTER_BODY = {
    "email": "refresh@example.com",
    "password": "Secret123",
    "country": "CZ",
    "username": "refresher",
    "dob": "2000-01-01",
}
LOGIN_BODY = {"email": REGISTER_BODY["email"], "password": REGISTER_BODY["password"]}


def _set_cookie_map(response) -> dict[str, dict[str, str]]:
    """Parse Set-Cookie headers into {name: {value, path, ...}}."""
    parsed: dict[str, dict[str, str]] = {}
    for header in response.headers.get_list("set-cookie"):
        parts = [p.strip() for p in header.split(";")]
        name, _, value = parts[0].partition("=")
        attrs: dict[str, str] = {"value": value}
        for part in parts[1:]:
            if "=" in part:
                key, _, val = part.partition("=")
                attrs[key.strip().lower()] = val.strip()
            else:
                attrs[part.lower()] = "true"
        parsed[name] = attrs
    return parsed


async def _register_and_login(client):
    reg = await client.post("/auth/register", json=REGISTER_BODY)
    assert reg.status_code == 200, reg.text
    login = await client.post("/auth/login", json=LOGIN_BODY)
    assert login.status_code == 200, login.text
    return login


def _csrf_headers(client) -> dict[str, str]:
    token = client.cookies.get("csrf_token")
    assert token, "expected csrf_token cookie after login"
    return {"X-CSRF-Token": token}


def _set_refresh_cookie(client, value: str) -> None:
    client.cookies.set("refresh_token", value, path="/auth")


def _set_access_cookie(client, value: str) -> None:
    client.cookies.set("access_token", value, path="/")


@pytest.mark.asyncio
async def test_login_sets_access_refresh_and_csrf_cookies(client):
    login = await _register_and_login(client)
    assert login.json() == {"ok": True}

    cookies = _set_cookie_map(login)
    assert "access_token" in cookies
    assert "refresh_token" in cookies
    assert "csrf_token" in cookies

    assert cookies["access_token"].get("path", "/") == "/"
    assert cookies["refresh_token"]["path"] == "/auth"
    assert cookies["csrf_token"].get("path", "/") == "/"

    # Access + refresh are HttpOnly; CSRF must be readable by JS
    assert cookies["access_token"].get("httponly") == "true"
    assert cookies["refresh_token"].get("httponly") == "true"
    assert "httponly" not in cookies["csrf_token"]


@pytest.mark.asyncio
async def test_refresh_valid_issues_new_cookies_and_auth_works(client):
    await _register_and_login(client)

    refresh = await client.post("/auth/refresh")
    assert refresh.status_code == 200
    assert refresh.json() == {"ok": True}

    cookies = _set_cookie_map(refresh)
    assert "access_token" in cookies
    assert "refresh_token" in cookies
    assert "csrf_token" in cookies

    me = await client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == REGISTER_BODY["email"]

    mine = await client.get("/game/mine")
    # Empty list is fine — proves access cookie authenticates the game route
    assert mine.status_code == 200
    assert mine.json() == []


@pytest.mark.asyncio
async def test_refresh_missing_cookie_returns_401(client):
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_refresh_access_token_as_refresh_returns_401(client):
    await _register_and_login(client)
    access = client.cookies.get("access_token")
    assert access

    _set_refresh_cookie(client, access)
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_refresh_wrong_type_returns_401(client):
    await _register_and_login(client)
    me = await client.get("/auth/me")
    user_id = me.json()["id"]

    bad = jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "ver": 0,
            "session_started": int(datetime.now(timezone.utc).timestamp()),
            "exp": datetime.now(timezone.utc) + timedelta(days=1),
        },
        settings.JWT_REFRESH_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    _set_refresh_cookie(client, bad)
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_refresh_expired_refresh_returns_401(client):
    await _register_and_login(client)
    me = await client.get("/auth/me")
    user_id = me.json()["id"]

    expired = jwt.encode(
        {
            "sub": str(user_id),
            "type": "refresh",
            "ver": 0,
            "session_started": int(datetime.now(timezone.utc).timestamp()),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        settings.JWT_REFRESH_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    _set_refresh_cookie(client, expired)
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_refresh_mismatched_token_version_returns_401(client):
    await _register_and_login(client)
    me = await client.get("/auth/me")
    user_id = me.json()["id"]

    stale = create_refresh_token(
        {"sub": str(user_id)},
        ver=999,
        session_started=datetime.now(timezone.utc),
    )
    _set_refresh_cookie(client, stale)
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_refresh_past_absolute_session_cap_returns_401(client):
    await _register_and_login(client)
    me = await client.get("/auth/me")
    user_id = me.json()["id"]

    too_old = create_refresh_token(
        {"sub": str(user_id)},
        ver=0,
        session_started=datetime.now(timezone.utc)
        - timedelta(days=settings.JWT_SESSION_MAX_DAYS + 1),
    )
    _set_refresh_cookie(client, too_old)
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Session expired"


@pytest.mark.asyncio
async def test_logout_invalidates_previous_refresh(client):
    await _register_and_login(client)
    old_refresh = client.cookies.get("refresh_token")
    assert old_refresh

    logout = await client.post("/auth/logout", headers=_csrf_headers(client))
    assert logout.status_code == 200
    assert logout.json() == {"ok": True}

    _set_refresh_cookie(client, old_refresh)
    response = await client.post("/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_access_path_rejects_missing_type(client):
    await _register_and_login(client)
    me = await client.get("/auth/me")
    user_id = me.json()["id"]

    no_type = jwt.encode(
        {
            "sub": str(user_id),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    _set_access_cookie(client, no_type)
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_access_path_rejects_refresh_type(client):
    await _register_and_login(client)
    refresh = client.cookies.get("refresh_token")
    assert refresh

    _set_access_cookie(client, refresh)
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_access_path_rejects_invalid_signature(client):
    await _register_and_login(client)
    me = await client.get("/auth/me")
    user_id = me.json()["id"]

    forged = jwt.encode(
        {
            "sub": str(user_id),
            "type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        "wrong-secret-key-for-signature-test",
        algorithm=settings.JWT_ALGORITHM,
    )
    _set_access_cookie(client, forged)
    response = await client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


@pytest.mark.asyncio
async def test_game_join_without_csrf_returns_403(client):
    await _register_and_login(client)
    response = await client.post("/game/join", params={"side": "heads"})
    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF check failed"


@pytest.mark.asyncio
async def test_game_join_with_matching_csrf_passes_csrf_check(client):
    await _register_and_login(client)
    response = await client.post(
        "/game/join",
        params={"side": "heads"},
        headers=_csrf_headers(client),
    )
    # CSRF passed; no open game in this sqlite fixture → business 400, not 403
    assert response.status_code != 403
    assert response.status_code in (200, 400)
