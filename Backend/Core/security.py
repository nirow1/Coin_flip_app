from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from jwt import PyJWTError

from Backend.config import settings

_JWT_ALGORITHMS = [settings.JWT_ALGORITHM]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    if expires_minutes is None:
        expires_minutes = settings.JWT_EXPIRE_MINUTES

    to_encode = data.copy()
    to_encode["type"] = "access"
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict, ver: int, session_started: datetime) -> str:
    to_encode = data.copy()
    to_encode["type"] = "refresh"
    to_encode["ver"] = ver
    to_encode["session_started"] = int(session_started.timestamp())
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_EXPIRE_DAYS
    )

    return jwt.encode(
        to_encode, settings.JWT_REFRESH_SECRET, algorithm=settings.JWT_ALGORITHM
    )


def decode_token(
    token: str,
    secret: str,
    *,
    expected_type: str | None = None,
) -> dict:
    """Decode a JWT; optionally require an explicit `type` claim (fail closed)."""
    payload = jwt.decode(token, secret, algorithms=_JWT_ALGORITHMS)
    if expected_type is not None and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return payload


def try_decode_token(
    token: str,
    secret: str,
    *,
    expected_type: str | None = None,
) -> dict | None:
    """Best-effort decode; returns None on any validation failure."""
    try:
        return decode_token(token, secret, expected_type=expected_type)
    except (PyJWTError, TypeError, ValueError):
        return None


def decode_access_token(token: str) -> dict:
    return decode_token(token, settings.JWT_SECRET, expected_type="access")


def decode_refresh_token(token: str) -> dict:
    return decode_token(token, settings.JWT_REFRESH_SECRET, expected_type="refresh")


def subject_as_int(payload: dict) -> int:
    return int(payload["sub"])
