import random
import secrets
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt import PyJWTError
from sqlalchemy import select

from Backend.Auth.models import User
from Backend.Auth.schemas import LoginRequest, RegisterRequest, UserResponse
from Backend.config import settings
from Backend.Core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    subject_as_int,
    try_decode_token,
    verify_password,
)
from Backend.Wallet.enums import TransactionType
from Backend.Wallet.models import Transaction
from Backend.Wallet.services import WalletService

_UNAUTHORIZED = status.HTTP_401_UNAUTHORIZED


class AuthService:
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

    # todo: photo of face which is verified for age with AI
    @staticmethod
    async def register_user(data: RegisterRequest, session):
        # Validate age (must be 18+)
        age = AuthService._calculate_age(data.dob)
        if age < 18:
            raise ValueError("You must be at least 18 years old to register")

        # Check if date of birth is in the future
        if data.dob > date.today():
            raise ValueError("Date of birth cannot be in the future")

        # Check if email exists
        existing = await session.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        username_base = data.username
        discriminator = await AuthService._generate_discriminator(username_base, session)

        # Create user
        user = User(
            email=data.email,
            username=data.username,
            discriminator=discriminator,
            password_hash=hash_password(data.password),
            country=data.country,
            dob=data.dob,
        )

        session.add(user)
        await session.flush()  # Assign user.id before creating wallet
        wallet = await WalletService(session).create_wallet(user.id)
        await session.flush()

        wallet.balance = Decimal("1.00")
        session.add(
            Transaction(
                wallet_id=wallet.id,
                amount=Decimal("1.00"),
                type=TransactionType.CREDIT,
            )
        )

        await session.commit()
        await session.refresh(user)

        return UserResponse(
            id=user.id,
            email=user.email,
            country=user.country,
            created_at=user.created_at,
        )

    @staticmethod
    def _issue_session_tokens(
        user: User, session_started: datetime
    ) -> dict[str, str]:
        """Mint access + refresh + csrf for cookie setters (never return in JSON)."""
        return {
            "access_token": create_access_token({"sub": str(user.id)}),
            "refresh_token": create_refresh_token(
                {"sub": str(user.id)},
                ver=user.token_version,
                session_started=session_started,
            ),
            "csrf_token": secrets.token_urlsafe(32),
        }

    @staticmethod
    async def login_user(data: LoginRequest, session) -> dict[str, str]:
        result = await session.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        # Consistent error + hash work to limit email/timing enumeration
        if not user:
            hash_password(data.password)
            raise ValueError("Invalid email or password")

        if not verify_password(data.password, user.password_hash):
            raise ValueError("Invalid email or password")

        return AuthService._issue_session_tokens(
            user, datetime.now(timezone.utc)
        )

    @staticmethod
    async def refresh_tokens(refresh_token: str | None, session) -> dict[str, str]:
        if not refresh_token:
            raise HTTPException(
                status_code=_UNAUTHORIZED, detail="Not authenticated"
            )

        try:
            payload = decode_refresh_token(refresh_token)
            user_id = subject_as_int(payload)
            session_started_ts = int(payload["session_started"])
        except (PyJWTError, KeyError, TypeError, ValueError):
            raise HTTPException(status_code=_UNAUTHORIZED, detail="Invalid token")

        now_ts = datetime.now(timezone.utc).timestamp()
        if now_ts - session_started_ts > settings.JWT_SESSION_MAX_DAYS * 86400:
            raise HTTPException(status_code=_UNAUTHORIZED, detail="Session expired")

        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=_UNAUTHORIZED, detail="User not found")
        if payload.get("ver") != user.token_version:
            raise HTTPException(status_code=_UNAUTHORIZED, detail="Invalid token")

        return AuthService._issue_session_tokens(
            user,
            datetime.fromtimestamp(session_started_ts, tz=timezone.utc),
        )

    @staticmethod
    async def try_increment_token_version(
        access_token: str | None,
        refresh_token: str | None,
        session,
    ) -> bool:
        """Best-effort revoke: bump token_version if a cookie identifies a user."""
        payload = None
        if access_token:
            payload = try_decode_token(access_token, settings.JWT_SECRET)
        if payload is None and refresh_token:
            payload = try_decode_token(refresh_token, settings.JWT_REFRESH_SECRET)
        if payload is None:
            return False

        try:
            user_id = subject_as_int(payload)
        except (KeyError, TypeError, ValueError):
            return False

        user = await session.get(User, user_id)
        if user is None:
            return False

        user.token_version += 1
        await session.commit()
        return True

    @staticmethod
    async def get_current_user(token: str, session) -> User:
        try:
            payload = decode_access_token(token)
            user_id = subject_as_int(payload)
        except (PyJWTError, KeyError, TypeError, ValueError):
            raise HTTPException(status_code=_UNAUTHORIZED, detail="Invalid token")

        user = await session.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=_UNAUTHORIZED, detail="User not found")

        return user

    @staticmethod
    def _calculate_age(dob: date) -> int:
        """Calculate age from date of birth"""
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age

    # todo: not perfect, there is a possibility of collision, but for now it should be fine.
    @staticmethod
    async def _generate_discriminator(base_username: str, session) -> str:
        for _ in range(100):
            disc = f"{random.randint(0, 9999):04d}"

            result = await session.execute(
                select(User).where(
                    User.username == base_username,
                    User.discriminator == disc,
                )
            )

            exists = result.scalar_one_or_none()

            if not exists:
                return disc

        raise HTTPException(500, "Could not generate discriminator")
