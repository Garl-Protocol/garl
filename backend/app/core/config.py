import os

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "GARL Protocol"
    app_version: str = "1.0.2"
    debug: bool = False

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    signing_private_key_hex: str = ""

    read_auth_enabled: bool = True

    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_cors_origins(self) -> list[str]:
        env_origins = os.environ.get("ALLOWED_ORIGINS", "")
        if env_origins:
            extra = [o.strip() for o in env_origins.split(",") if o.strip()]
            merged = list(set(self.cors_origins + extra))
            return merged
        return self.cors_origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
