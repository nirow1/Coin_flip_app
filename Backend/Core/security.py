from datetime import datetime, timedelta

import bcrypt
import jwt

from Backend.config import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    if expires_minutes is None:
        expires_minutes = settings.JWT_EXPIRE_MINUTES
    
    to_encode = data.copy()
    to_encode["type"] = "access"  
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=expires_minutes)
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")

def create_refresh_token(data: dict, ver: int, session_started: datetime) -> str:
    to_encode = data.copy()
    to_encode["type"] = "refresh"
    to_encode["ver"] = ver
    to_encode["session_started"] = int(session_started.timestamp())
    to_encode["exp"] = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS)

    return jwt.encode(to_encode, settings.JWT_REFRESH_SECRET, algorithm="HS256")
