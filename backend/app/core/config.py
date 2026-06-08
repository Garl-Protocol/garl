import os

from pydantic import model_validator
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
    merkle_anchor_contract: str = "0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2"
    merkle_anchor_chain_id: int = 8453

    read_auth_enabled: bool = True

    public_frontend_url: str = "https://garl.ai"

    cors_origins: list[str] = list(_DEV_DEFAULT_ORIGINS)

    # extra="ignore": an unexpected env var must never crash the service on boot.
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @model_validator(mode="after")
    def _signing_key_env_fallback(self) -> "Settings":
        # Prod historically set ECDSA_PRIVATE_KEY_HEX while code/docs reference
        # SIGNING_PRIVATE_KEY_HEX. If the canonical name is unset, fall back to
        # the legacy one so the signer never silently drops to an ephemeral key
        # (which would change every receipt signature on restart).
        if not self.signing_private_key_hex:
            legacy = os.environ.get("ECDSA_PRIVATE_KEY_HEX", "").strip()
            if legacy:
                self.signing_private_key_hex = legacy
        return self

    def get_cors_origins(self) -> list[str]:
        env_origins = os.environ.get("ALLOWED_ORIGINS", "")
        env_list = [o.strip() for o in env_origins.split(",") if o.strip()]
        if self.debug:
            return list(dict.fromkeys(env_list + list(_DEV_DEFAULT_ORIGINS)))
        return env_list or list(_PROD_DEFAULT_ORIGINS)


@lru_cache
def get_settings() -> Settings:
    return Settings()
