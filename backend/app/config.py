"""Configuration settings for BenchLab.
Loads from environment variables and .env file.
Provides safe scrubbing of sensitive credentials.
"""

from functools import lru_cache
from typing import Any, Dict
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project metadata
    project_name: str = "benchlab"
    environment: str = "development"
    spec_version: str = "1.0"

    # PostgreSQL configuration (DEC-001: 17.2-alpine)
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str = "benchlab_user"
    postgres_password: str = "benchlab_dev_password_change_me"
    postgres_db: str = "benchlab_db"
    postgres_max_connections: int = 50
    postgres_work_mem: str = "16MB"

    # MongoDB configuration (DEC-001: 8.0.4)
    mongo_host: str = "127.0.0.1"
    mongo_port: int = 27017
    mongo_initdb_root_username: str = "benchlab_user"
    mongo_initdb_root_password: str = "benchlab_dev_password_change_me"
    mongo_db: str = "benchlab_db"
    mongo_max_pool_size: int = 50

    # Resource quotas (DEC-002: 2 vCPU, 2048MB)
    container_cpu_limit: float = 2.0
    container_mem_limit: str = "2048m"

    # API & Runner settings
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_debug: bool = False
    results_dir: str = "results"
    datasets_dir: str = "data"

    # Frontend
    frontend_port: int = 5173
    vite_api_base_url: str = "http://127.0.0.1:8000"

    # Timeouts & Benchmark defaults
    default_seed: int = 42
    server_timeout_seconds: int = 30
    client_timeout_seconds: int = 35
    percentile_method: str = "linear"

    @property
    def postgres_dsn(self) -> str:
        """Construct PostgreSQL connection DSN string."""
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def mongo_uri(self) -> str:
        """Construct MongoDB connection URI."""
        return (
            f"mongodb://{self.mongo_initdb_root_username}:{self.mongo_initdb_root_password}@"
            f"{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource=admin"
        )

    def get_sanitized_config(self) -> Dict[str, Any]:
        """Return configuration dictionary with all secrets and passwords redacted."""
        raw = self.model_dump()
        sensitive_keywords = ("password", "secret", "token", "key")
        sanitized = {}
        for k, v in raw.items():
            if any(s in k.lower() for s in sensitive_keywords):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = v
        # Also redact DSN / URI representations
        sanitized["postgres_dsn"] = (
            f"postgresql://{self.postgres_user}:***REDACTED***@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        sanitized["mongo_uri"] = (
            f"mongodb://{self.mongo_initdb_root_username}:***REDACTED***@"
            f"{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource=admin"
        )
        return sanitized


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
