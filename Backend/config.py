from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings

SolanaCluster = Literal["mainnet-beta", "devnet", "testnet"]


class Settings(BaseSettings):
    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    JWT_SESSION_MAX_DAYS: int = 30
    JWT_REFRESH_SECRET: str
    COOKIE_SECURE: bool = True
    CORS_ORIGINS: str = "http://localhost:5173"
    STRIPE_SECRET_KEY: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    # Solana — no mainnet RPC default; fail closed if secrets/addresses missing
    SOLANA_WEBHOOK_SECRET: str
    SOLANA_RPC_URL: str
    SOLANA_CLUSTER: SolanaCluster
    SOLANA_COLD_RECEIVE_ADDRESS: str
    SOLANA_HOT_WALLET_ADDRESS: str
    SOLANA_HOT_WALLET_SECRET: str  # keypair JSON from secret store
    SOLANA_USDC_MINT: str

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

    @field_validator(
        "SOLANA_WEBHOOK_SECRET",
        "SOLANA_RPC_URL",
        "SOLANA_COLD_RECEIVE_ADDRESS",
        "SOLANA_HOT_WALLET_ADDRESS",
        "SOLANA_HOT_WALLET_SECRET",
        "SOLANA_USDC_MINT",
    )
    @classmethod
    def require_non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must be a non-empty string")
        return v

    class Config:
        env_file = str(Path(__file__).resolve().parent / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
