from sqlalchemy import select
from Core.security import hash_password, verify_password, create_access_token
from Auth.models import User
from Auth.schemas import RegisterRequest, LoginRequest, UserResponse, TokenResponse

class AuthService:

    @staticmethod
    async def register_user(data: RegisterRequest, session):
        # check if email exists
        existing = await session.execute(select(User).where(User.email == data.email))
        if existing.scalar_one_or_none():
            raise ValueError("Email already registered")

        # create user
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

        return UserResponse(
            id=user.id,
            email=user.email,
            country=user.country,
            created_at=user.created_at
        )

    @staticmethod
    async def login_user(data: LoginRequest, session):
        # find user
        result = await session.execute(select(User).where(User.email == data.email))
        user = result.scalar_one_or_none()

        if not user or not verify_password(data.password, user.password_hash):
            raise ValueError("Invalid email or password")

        # create JWT
        token = create_access_token({"sub": str(user.id)})

        return TokenResponse(access_token=token)
