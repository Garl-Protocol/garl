import os

from pydantic_settings import BaseSettings
from functools import lru_cache


_PROD_DEFAULT_ORIGINS = ("https://garl.ai", "https://www.garl.ai")
_DEV_DEFAULT_ORIGINS = ("http://localhost:3000", "http://localhost:3001")


class Settings(BaseSettings):
    app_name: str = "GARL Protocol"
    app_version: str = "1.4.0"
    debug: bool = False

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    signing_private_key_hex: str = ""

    # On-chain Merkle anchor (Base mainnet). The backend builds batches and
    # records the anchor tx; broadcasting is operator-driven via Foundry.
    merkle_anchor_contract: str = "0xB8fd676A588C9935Fa6230610c6A924E34D5Ec17"
    merkle_anchor_chain_id: int = 8453

    read_auth_enabled: bool = True

    public_frontend_url: str = "https://garl.ai"

    cors_origins: list[str] = list(_DEV_DEFAULT_ORIGINS)

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def get_cors_origins(self) -> list[str]:
        env_origins = os.environ.get("ALLOWED_ORIGINS", "")
        env_list = [o.strip() for o in env_origins.split(",") if o.strip()]
        if self.debug:
            return list(dict.fromkeys(env_list + list(_DEV_DEFAULT_ORIGINS)))
        return env_list or list(_PROD_DEFAULT_ORIGINS)


@lru_cache
def get_settings() -> Settings:
    return Settings()
