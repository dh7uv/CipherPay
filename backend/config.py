from functools import lru_cache
import base64
import secrets
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CryptaGuard"
    debug: bool = True
    api_v1_str: str = "/api/v1"
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "cryptaguard_db"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    rate_limit_per_minute: int = 60
    suspicious_device_ids: str = ""
    cors_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    encryption_key: str = Field(default_factory=lambda: base64.b64encode(secrets.token_bytes(32)).decode("ascii"))
    hmac_secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        """Accept common deployment labels in addition to boolean env values."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev"}:
                return True
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def suspicious_devices(self) -> set[str]:
        return {device.strip() for device in self.suspicious_device_ids.split(",") if device.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
