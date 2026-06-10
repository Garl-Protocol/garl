from supabase import create_client, Client
from app.core.config import get_settings

_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError(
                "Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."
            )
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client


def is_unique_violation(exc: Exception) -> bool:
    """True if a Supabase/PostgREST error is a Postgres unique-constraint
    violation (SQLSTATE 23505). Used to translate the rare check-then-insert
    race on UNIQUE columns (trace_hash, output_hash) into a clean duplicate
    response instead of a 500."""
    text = str(getattr(exc, "code", "")) + " " + str(exc)
    text = text.lower()
    return "23505" in text or "duplicate key value" in text or "unique constraint" in text
