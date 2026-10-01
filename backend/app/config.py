from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Chronos — Immutable Double-Entry Ledger & Virtual Test Clock Billing Engine"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/v1"
    ENVIRONMENT: str = "development"
    
    # Defaults to local PostgreSQL running on Homebrew or Docker
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://krishagarwal@localhost:5432/chronos"
    )
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173", "*"]
    
    # Currency
    DEFAULT_CURRENCY: str = "usd"
    
    # Concurrency / Lock timeouts
    DB_LOCK_TIMEOUT_SECONDS: float = 5.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
