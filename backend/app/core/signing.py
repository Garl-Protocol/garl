import hashlib
import json
import logging
import time
from ecdsa import SigningKey, VerifyingKey, SECP256k1, BadSignatureError
from ecdsa.errors import MalformedPointError

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


def sign_trace(trace_data: dict) -> dict:
    """Sign a trace payload and return a Proof-of-Success certificate."""
    sk = _get_signing_key()
    canonical = json.dumps(trace_data, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).digest()
    signature = sk.sign_digest(digest).hex()

    return {
        "@context": "https://garl.io/schema/v1",
        "@type": "CertifiedExecutionTrace",
        "payload": trace_data,
        "proof": {
            "type": "ECDSA-secp256k1",
            "created": int(time.time()),
            "publicKey": get_public_key_hex(),
            "signature": signature,
        },
    }


def verify_signature(certificate: dict) -> bool:
    proof = certificate.get("proof", {})
    payload = certificate.get("payload", {})
    try:
        vk = VerifyingKey.from_string(
            bytes.fromhex(proof["publicKey"]), curve=SECP256k1
        )
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode()).digest()
        return vk.verify_digest(bytes.fromhex(proof["signature"]), digest)
    except (BadSignatureError, KeyError, ValueError, MalformedPointError, TypeError):
        return False
