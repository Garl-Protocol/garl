import hashlib
import json
import logging
import os
import time
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
from ecdsa.errors import MalformedPointError

from app.core.canonical import canonical_str
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_signing_key: SigningKey | None = None


def _get_signing_key() -> SigningKey:
    global _signing_key
    if _signing_key is not None:
        return _signing_key

    settings = get_settings()
    if not settings.signing_private_key_hex:
        if settings.debug:
            _signing_key = SigningKey.generate(curve=SECP256k1)
            logger.warning(
                "SIGNING_PRIVATE_KEY_HEX not set — ephemeral key generated. "
                "Certificates will NOT survive restarts. Set this in production."
            )
            return _signing_key
        raise RuntimeError(
            "SIGNING_PRIVATE_KEY_HEX is required. Generate one with: "
            "python3 -c \"from ecdsa import SigningKey, SECP256k1; print(SigningKey.generate(SECP256k1).to_string().hex())\""
        )

    try:
        _signing_key = SigningKey.from_string(
            bytes.fromhex(settings.signing_private_key_hex), curve=SECP256k1
        )
    except (ValueError, Exception) as e:
        raise RuntimeError(f"Invalid SIGNING_PRIVATE_KEY_HEX: {e}") from e
    return _signing_key


def get_public_key_hex() -> str:
    return _get_signing_key().get_verifying_key().to_string().hex()


def derive_key_id(public_key_hex: str) -> str:
    """Deterministic fingerprint — first 16 hex chars of SHA-256(pubkey)."""
    return hashlib.sha256(bytes.fromhex(public_key_hex)).hexdigest()[:16]


def get_active_key_id() -> str:
    return derive_key_id(get_public_key_hex())


def _load_retired_keys() -> list[dict]:
    """Optional env var GARL_RETIRED_KEYS_JSON — JSON array of:
    [{"public_key_hex": "...", "retired_at": "2026-...", "note": "..."}]
    Each entry gets a deterministic key_id derived from public_key_hex."""
    raw = os.environ.get("GARL_RETIRED_KEYS_JSON", "").strip()
    if not raw:
        return []
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("GARL_RETIRED_KEYS_JSON is not valid JSON — ignoring")
        return []
    if not isinstance(entries, list):
        return []
    out: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        pk = entry.get("public_key_hex", "").strip()
        if not pk:
            continue
        out.append(
            {
                "key_id": derive_key_id(pk),
                "public_key_hex": pk,
                "status": "retired",
                "algorithm": "ECDSA-secp256k1",
                "retired_at": entry.get("retired_at"),
                "note": entry.get("note"),
            }
        )
    return out


def get_key_registry() -> dict:
    """Public key registry document. Used by /.well-known/garl-keys.json
    and /api/v1/keys. Clients verifying an older receipt should resolve
    ``proof.key_id`` against this registry instead of trusting a
    hard-coded key — this is the only way key rotation stays observable."""
    active_pk = get_public_key_hex()
    return {
        "protocol": "garl",
        "algorithm": "ECDSA-secp256k1",
        "hash_algorithm": "SHA-256",
        "canonical_registry": "https://api.garl.ai",
        "keys": [
            {
                "key_id": derive_key_id(active_pk),
                "public_key_hex": active_pk,
                "status": "active",
                "algorithm": "ECDSA-secp256k1",
            },
            *_load_retired_keys(),
        ],
        "generated_at": int(time.time()),
    }


def sign_payload(payload: dict) -> tuple[str, str]:
    """Sign an arbitrary JSON payload; return (signature_hex, content_hash_hex).

    Uses RFC 6979 deterministic ECDSA — the same payload always produces
    the same signature. Protects against nonce-reuse on weak RNGs and
    lets callers idempotently re-derive signatures for the same data.
    """
    sk = _get_signing_key()
    canonical = canonical_str(payload)
    digest = hashlib.sha256(canonical.encode()).digest()
    signature = sk.sign_digest_deterministic(digest, hashfunc=hashlib.sha256).hex()
    return signature, digest.hex()


def sign_trace(trace_data: dict) -> dict:
    """Sign a trace payload and return a Proof-of-Success certificate.

    Uses RFC 6979 deterministic ECDSA — identical trace_data always
    yields the identical signature bytes.
    """
    sk = _get_signing_key()
    canonical = canonical_str(trace_data)
    digest = hashlib.sha256(canonical.encode()).digest()
    signature = sk.sign_digest_deterministic(digest, hashfunc=hashlib.sha256).hex()
    public_key_hex = get_public_key_hex()

    return {
        "@context": "https://garl.io/schema/v1",
        "@type": "CertifiedExecutionTrace",
        "payload": trace_data,
        "proof": {
            "type": "ECDSA-secp256k1",
            "created": int(time.time()),
            "key_id": derive_key_id(public_key_hex),
            "publicKey": public_key_hex,
            "signature": signature,
        },
    }


def verify_signature(certificate: dict) -> bool:
    proof = certificate.get("proof", {})
    payload = certificate.get("payload", {})
    try:
        pubkey_hex = proof["publicKey"]
        # Only trust signatures from a key in the GARL registry (active or
        # retired). Without this, a self-consistent (signature, publicKey) pair
        # produced by an attacker-controlled key would verify as "valid" on
        # /verify/check — proving only that *someone* signed it, not GARL.
        known_keys = {k.get("public_key_hex") for k in get_key_registry().get("keys", [])}
        if pubkey_hex not in known_keys:
            return False
        vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
        canonical = canonical_str(payload)
        digest = hashlib.sha256(canonical.encode()).digest()
        return vk.verify_digest(bytes.fromhex(proof["signature"]), digest)
    except (BadSignatureError, KeyError, ValueError, MalformedPointError, TypeError):
        return False
