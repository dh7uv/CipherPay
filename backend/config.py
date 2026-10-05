from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "CipherPay"
    debug: bool = True
    seed_demo_data: bool = False
    api_v1_str: str = "/api/v1"
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "cipherpay_db"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_rate_limit: int = Field(default=60, ge=1)
    redis_rate_window_seconds: int = Field(default=60, ge=1)
    fraud_blacklisted_device_ids: str = ""
    encryption_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
    hmac_secret_key: str = "super-secret-hmac-key-here"


@lru_cache
def get_settings() -> Settings:
    return Settings()
