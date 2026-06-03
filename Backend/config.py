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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
