from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    database_url: str = Field(
        default="postgresql://apnitormacmini3@localhost:5432/traffic_splitting",
        alias="DATABASE_URL",
    )
    redis_url: str | None = Field(default=None, alias="REDIS_URL")
    admin_api_key: str = Field(default="dev-admin-key", alias="ADMIN_API_KEY")
    ingest_api_key: str = Field(default="dev-ingest-key", alias="INGEST_API_KEY")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )
    cloudflare_account_id: str | None = Field(default=None, alias="CLOUDFLARE_ACCOUNT_ID")
    cloudflare_kv_namespace_id: str | None = Field(default=None, alias="CLOUDFLARE_KV_NAMESPACE_ID")
    cloudflare_api_token: str | None = Field(default=None, alias="CLOUDFLARE_API_TOKEN")
    stats_cache_ttl_seconds: int = Field(default=300, alias="STATS_CACHE_TTL_SECONDS")

    @property
    def cors_origin_list(self) -> list[str]:
        value = self.cors_origins.strip()
        if not value:
            return []
        if value.startswith("["):
            parsed = json.loads(value)
            return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def async_database_url(self) -> str:
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.database_url

    @property
    def sync_database_url(self) -> str:
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def cloudflare_sync_enabled(self) -> bool:
        return all(
            [
                self.cloudflare_account_id,
                self.cloudflare_kv_namespace_id,
                self.cloudflare_api_token,
            ]
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
