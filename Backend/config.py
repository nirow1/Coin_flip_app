from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    STRIPE_SECRET_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"
    SOLANA_WEBHOOK_SECRET: str = ""
    SOLANA_RPC_URL: str = "https://api.mainnet-beta.solana.com"
    SOLANA_HOT_WALLET_ADDRESS: str = ""
    # Comma-separated list, e.g. "http://localhost:5173,https://your-app.pages.dev"
    CORS_ORIGINS: str = "http://localhost:5173"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, v: object) -> object:
        """Railway Postgres uses postgres://; SQLAlchemy async needs +asyncpg."""
        if not isinstance(v, str):
            return v
        if v.startswith("postgres://"):
            v = "postgresql://" + v.removeprefix("postgres://")
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v.removeprefix("postgresql://")
        return v

    class Config:
        env_file = str(Path(__file__).resolve().parent / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
