import asyncio
from datetime import date
from decimal import Decimal

# --- Adjust these imports to match your actual project structure ---
from Backend.db import SessionLocal     # your async session factory
from Backend.Auth.service import AuthService
from Backend.Wallet.services import WalletService
from Backend.Auth.schemas import RegisterRequest        # your Pydantic request model
from Backend.Notification.models import Notification
from Backend.Social.models import Friend
from Backend.Leader_board.model import Leaderboard
from Backend.Auth.models import User
from sqlalchemy import select

TEST_EMAIL = "test@dailyflip.dev"
TEST_PASSWORD = "Password123!"
TEST_COUNTRY = "CZ"          # adjust to whatever your schema expects (code vs full name)
TEST_NAME = "TestUser"       # add a test username
TEST_DOB = date(1995, 1, 1)  # well over 18
TEST_BALANCE = Decimal("250.00")


async def seed():
    async with SessionLocal() as session:
        # Check if test user already exists — skip registration if so
        existing = await session.execute(select(User).where(User.email == TEST_EMAIL))
        user = existing.scalar_one_or_none()

        if user:
            print(f"User {TEST_EMAIL} already exists (id={user.id}). Skipping registration.")
        else:
            register_data = RegisterRequest(
                email=TEST_EMAIL,
                password=TEST_PASSWORD,
                country=TEST_COUNTRY,
                username=TEST_NAME,
                dob=TEST_DOB,
            )
            user_response = await AuthService.register_user(register_data, session)
            print(f"Registered user: {user_response.email} (id={user_response.id})")

            # Re-fetch as ORM object since register_user returns a UserResponse, not the model
            result = await session.execute(select(User).where(User.id == user_response.id))
            user = result.scalar_one()

        # Top up wallet balance directly
        wallet_service = WalletService(session)
        wallet = await wallet_service.get_wallet(user.id)  # adjust method name if different
        wallet.balance = TEST_BALANCE
        await session.commit()

        print(f"Wallet balance set to {TEST_BALANCE}")
        print("\nLogin credentials:")
        print(f"  email:    {TEST_EMAIL}")
        print(f"  password: {TEST_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())