from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings

SolanaCluster = Literal["mainnet-beta", "devnet", "testnet"]


class Settings(BaseSettings):
    DATABASE_URL: str
    TEST_DATABASE_URL: str = ""
    JWT_SECRET: SecretStr
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_EXPIRE_DAYS: int = 7
    JWT_SESSION_MAX_DAYS: int = 30
    JWT_REFRESH_SECRET: SecretStr
    COOKIE_SECURE: bool = True
    CORS_ORIGINS: str = "http://localhost:5173"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Solana — no mainnet RPC default; fail closed if secrets/addresses missing
    SOLANA_WEBHOOK_SECRET: SecretStr
    SOLANA_RPC_URL: str
    SOLANA_CLUSTER: SolanaCluster
    SOLANA_COLD_RECEIVE_ADDRESS: str
    SOLANA_HOT_WALLET_ADDRESS: str
    # Keypair JSON — required for payout/reconciler workers only; optional for API web.
    SOLANA_HOT_WALLET_SECRET: SecretStr | None = None
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

    @field_validator("SOLANA_HOT_WALLET_SECRET", mode="before")
    @classmethod
    def empty_hot_secret_as_none(cls, v: object) -> object:
        """Treat missing/blank hot secret as unset (web processes need not have it)."""
        if v is None:
            return None
        if isinstance(v, SecretStr):
            raw = v.get_secret_value()
        else:
            raw = v
        if not isinstance(raw, str) or not raw.strip():
            return None
        return v

    @field_validator(
        "SOLANA_WEBHOOK_SECRET",
        "JWT_SECRET",
        "JWT_REFRESH_SECRET",
        mode="before",
    )
    @classmethod
    def require_non_empty_secret(cls, v: object) -> object:
        if isinstance(v, SecretStr):
            raw = v.get_secret_value()
        else:
            raw = v
        if not isinstance(raw, str) or not raw.strip():
            raise ValueError("must be a non-empty string")
        return v

    @field_validator(
        "SOLANA_RPC_URL",
        "SOLANA_COLD_RECEIVE_ADDRESS",
        "SOLANA_HOT_WALLET_ADDRESS",
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
