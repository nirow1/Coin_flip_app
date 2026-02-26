from email.policy import HTTP

from sqlalchemy import select
from datetime import date
from Core.security import hash_password, verify_password, create_access_token
from Auth.models import User
from jose import JWTError, jwt
from fastapi import HTTPException, status
from Auth.schemas import RegisterRequest, LoginRequest, UserResponse, TokenResponse

SECRET_KEY = "your-secret-key" # use your real key
ALGORITHM = "HS256"

class AuthService:
    @staticmethod
    def _calculate_age(dob: date) -> int:
        """Calculate age from date of birth"""
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age

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

        # Create user
        user = User(
            email=data.email,
            username=None,
            password_hash=hash_password(data.password),
            country=data.country,
            dob=data.dob
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        # TODO: Create wallet for user
        # await WalletService.create_wallet(user.id, session)

        return UserResponse(
            id=user.id,
            email=user.email,
            country=user.country,
            created_at=user.created_at
        )

    @staticmethod
    async def login_user(data: LoginRequest, session) -> TokenResponse:
        # Find user
        result = await session.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        # Use consistent error message to prevent email enumeration attacks
        if not user:
            # Still hash the password to prevent timing attacks
            hash_password(data.password)
            raise ValueError("Invalid email or password")

        if not verify_password(data.password, user.password_hash):
            raise ValueError("Invalid email or password")

        # Create JWT with user ID
        token = create_access_token({"sub": str(user.id)})

        return TokenResponse(access_token=token)

    @staticmethod
    async def get_current_user(token: str, session) -> UserResponse:
        # Decode token to get user ID
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))

        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token" )
