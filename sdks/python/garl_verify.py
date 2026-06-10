"""garl-verify — offline verifier for GARL receipts.

Usage:

    garl-verify https://garl.ai/r/6ff83db8
    garl-verify 6ff83db816ac25bc...
    garl-verify --input receipt.json
    echo '{"certificate": {...}}' | garl-verify --stdin

The tool resolves the receipt via the canonical registry
(api.garl.ai/api/v1/receipts/{hash}/cert.json), fetches the public-key
registry (/.well-known/garl-keys.json), and verifies the ECDSA-secp256k1
signature locally. It does NOT trust the registry's `verified` flag —
it recomputes the signature check on your machine.

Exit code 0 if the signature verifies, 1 if not, 2 for network/input
errors. Output is concise on success and explanatory on failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from typing import Any
from urllib.parse import urlparse

try:
    import httpx
except ImportError as e:  # pragma: no cover
    print("garl-verify requires httpx — install garl-protocol >= 1.2.0", file=sys.stderr)
    raise SystemExit(2) from e

try:
    from ecdsa import VerifyingKey, SECP256k1, BadSignatureError
except ImportError as e:  # pragma: no cover
    print("garl-verify requires python-ecdsa — install garl-protocol >= 1.2.0 which pulls it in", file=sys.stderr)
    raise SystemExit(2) from e


DEFAULT_API_BASE = "https://api.garl.ai"
DEFAULT_KEY_REGISTRY = f"{DEFAULT_API_BASE}/.well-known/garl-keys.json"


def _extract_hash_or_url(arg: str) -> tuple[str, str]:
    """Return (kind, value). kind ∈ {'hash', 'url'}."""
    arg = arg.strip()
    if arg.startswith(("http://", "https://")):
        return "url", arg
    # Bare UUID → a receipt_id (the cert.json endpoint resolves it directly).
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", arg):
        return "hash", arg.lower()
    # Bare hex → assume hash (trace_hash / output_hash prefix or full).
    if all(c in "0123456789abcdefABCDEF" for c in arg) and 8 <= len(arg) <= 64:
        return "hash", arg.lower()
    raise ValueError(f"Argument is neither a URL nor a valid GARL hash prefix: {arg!r}")


def _resolve_to_cert(arg: str, api_base: str) -> dict:
    kind, value = _extract_hash_or_url(arg)
    if kind == "url":
        parsed = urlparse(value)
        # https://garl.ai/r/<short> → api.garl.ai/api/v1/receipts/<short>/cert.json
        if parsed.path.startswith("/r/"):
            short = parsed.path[3:].strip("/")
            cert_url = f"{api_base}/api/v1/receipts/{short}/cert.json"
        elif "/verify/" in parsed.path:
            h = parsed.path.rsplit("/verify/", 1)[-1]
            cert_url = f"{api_base}/api/v1/receipts/{h}/cert.json"
        else:
            # treat it as a direct cert URL
            cert_url = value
    else:
        cert_url = f"{api_base}/api/v1/receipts/{value}/cert.json"

    resp = httpx.get(cert_url, timeout=10.0, follow_redirects=True, headers={"User-Agent": "garl-verify/1.0"})
    if resp.status_code == 404:
        raise RuntimeError(
            f"No original certificate at {cert_url} (404). "
            "Pre-v0.3 legacy traces expose only /verify; use that URL instead."
        )
    resp.raise_for_status()
    cert = resp.json()
    if not isinstance(cert, dict) or not (cert.get("proof") or _is_receipt_envelope(cert)):
        raise RuntimeError(f"Response at {cert_url} is not a GARL certificate")
    return cert


def _fetch_key_registry(url: str) -> dict[str, str]:
    """Return {key_id: public_key_hex}."""
    resp = httpx.get(url, timeout=10.0, headers={"User-Agent": "garl-verify/1.0"})
    resp.raise_for_status()
    body = resp.json()
    out: dict[str, str] = {}
    for k in body.get("keys", []):
        kid = k.get("key_id")
        pk = k.get("public_key_hex")
        if kid and pk:
            out[kid] = pk
    return out


def _canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def _verify_cert(cert: dict, pubkey_hex: str) -> bool:
    proof = cert.get("proof") or {}
    payload = cert.get("payload") or {}
    sig_hex = proof.get("signature", "")
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
        digest = hashlib.sha256(_canonical_payload_bytes(payload)).digest()
        vk.verify_digest(bytes.fromhex(sig_hex), digest)
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def _is_receipt_envelope(cert: dict) -> bool:
    """A v0.1 Action Receipt is a flat envelope (no proof/payload wrapper)
    that carries its own ``signature`` + ``verification_key_id``, served at
    ``/api/v1/receipts/{id}/cert.json``."""
    return (
        isinstance(cert, dict)
        and "proof" not in cert
        and isinstance(cert.get("signature"), str)
        and isinstance(cert.get("verification_key_id"), str)
        and str(cert.get("version", "")).startswith("garl/action-receipt/")
    )


def _verify_receipt_envelope(cert: dict, pubkey_hex: str) -> bool:
    """Verify a v0.1 Action Receipt envelope.

    The backend signs the envelope BEFORE attaching ``signature`` and
    ``verification_key_id`` (see action_receipts.submit_action_receipt), so
    the signed bytes are the envelope with exactly those two keys removed,
    canonicalized the same way as every other GARL payload. ``pubkey_hex``
    MUST come from the GARL key registry — never from the envelope itself.
    """
    signed_payload = {
        k: v for k, v in cert.items()
        if k not in ("signature", "verification_key_id")
    }
    sig_hex = cert.get("signature", "")
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
        digest = hashlib.sha256(_canonical_payload_bytes(signed_payload)).digest()
        vk.verify_digest(bytes.fromhex(sig_hex), digest)
        return True
    except (BadSignatureError, ValueError, TypeError):
        return False


def _derive_key_id_from_pk(pk_hex: str) -> str:
    """Matches backend's derive_key_id: first 16 hex of sha256(pubkey_bytes)."""
    try:
        return hashlib.sha256(bytes.fromhex(pk_hex)).hexdigest()[:16]
    except ValueError:
        return "(unknown)"


def _print_result(cert: dict, ok: bool, registry_url: str, args: argparse.Namespace) -> int:
    proof = cert.get("proof") or {}
    key_id = proof.get("key_id") or (_derive_key_id_from_pk(proof.get("publicKey", "")) if proof.get("publicKey") else "(unknown)")
    signing_epoch = proof.get("signing_epoch", "original")
    rekor = proof.get("rekor")
    payload = cert.get("payload") or {}
    summary: dict[str, Any] = {
        "verified": ok,
        "key_id": key_id,
        "registry": registry_url,
        "signing_epoch": signing_epoch,
        "agent_id": payload.get("agent_id"),
        "trace_id": payload.get("trace_id"),
        "status": payload.get("status"),
    }
    if rekor:
        summary["rekor_url"] = rekor.get("url")
        summary["rekor_uuid"] = rekor.get("uuid")
    if args.json:
        print(json.dumps(summary, indent=2 if args.pretty else None))
    else:
        icon = "✓" if ok else "✗"
        print(f"{icon} verified={ok}  key_id={key_id}  signing_epoch={signing_epoch}")
        if rekor:
            print(f"  rekor: {rekor.get('url')}")
        if not ok:
            print("  signature did NOT verify against the registry public key.")
    return 0 if ok else 1


def _print_receipt_result(cert: dict, ok: bool, key_id: str, registry_url: str, args: argparse.Namespace) -> int:
    summary: dict[str, Any] = {
        "verified": ok,
        "key_id": key_id,
        "registry": registry_url,
        "receipt_id": cert.get("receipt_id"),
        "agent_identity": cert.get("agent_identity"),
        "action_type": cert.get("action_type"),
        "side_effect": cert.get("side_effect"),
        "output_hash": cert.get("output_hash"),
    }
    if args.json:
        print(json.dumps(summary, indent=2 if args.pretty else None))
    else:
        icon = "✓" if ok else "✗"
        print(f"{icon} verified={ok}  key_id={key_id}  receipt_id={cert.get('receipt_id')}")
        print(f"  action_type={cert.get('action_type')}  side_effect={cert.get('side_effect')}")
        if not ok:
            print("  signature did NOT verify against the registry public key.")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="garl-verify",
        description="Offline verifier for GARL receipts (ECDSA-secp256k1).",
    )
    parser.add_argument("target", nargs="?", help="Receipt URL (https://garl.ai/r/...) or raw trace hash prefix")
    parser.add_argument("--input", help="Path to a certificate JSON file to verify instead of fetching")
    parser.add_argument("--stdin", action="store_true", help="Read certificate JSON from stdin")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="GARL canonical API base (default: %(default)s)")
    parser.add_argument("--key-registry", default=DEFAULT_KEY_REGISTRY, help="Public key registry URL (default: %(default)s)")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON (requires --json)")
    args = parser.parse_args(argv)

    try:
        if args.stdin:
            cert = json.load(sys.stdin)
        elif args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                cert = json.load(f)
        elif args.target:
            cert = _resolve_to_cert(args.target, args.api_base)
        else:
            parser.error("provide a receipt URL/hash, --input, or --stdin")
            return 2
    except Exception as e:  # noqa: BLE001
        print(f"garl-verify: {e}", file=sys.stderr)
        return 2

    try:
        registry = _fetch_key_registry(args.key_registry)
    except Exception as e:  # noqa: BLE001
        print(f"garl-verify: could not load key registry {args.key_registry}: {e}", file=sys.stderr)
        return 2

    # v0.1 Action Receipt envelope path — resolve the key from the registry
    # by verification_key_id and verify the envelope-minus-signature. The
    # registry lookup is the trust anchor; the envelope never vouches for
    # its own key.
    if _is_receipt_envelope(cert):
        kid = cert.get("verification_key_id")
        pk_hex = registry.get(kid)
        if not pk_hex:
            print(
                "garl-verify: receipt's verification_key_id is not in the registry — "
                "refusing to verify against an unknown key",
                file=sys.stderr,
            )
            return 1
        ok = _verify_receipt_envelope(cert, pk_hex)
        return _print_receipt_result(cert, ok, kid, args.key_registry, args)

    proof = cert.get("proof") or {}
    key_id = proof.get("key_id")
    pk_hex = None
    if key_id and key_id in registry:
        pk_hex = registry[key_id]
    else:
        # Fall back to proof.publicKey when the embedded key matches an
        # entry in the registry. Never verify against a raw embedded key
        # that the registry doesn't know about — that would trust the
        # receipt to vouch for its own key.
        embedded = proof.get("publicKey")
        if embedded and embedded in registry.values():
            pk_hex = embedded
        elif embedded:
            print(
                "garl-verify: certificate's key is not in the registry — refusing to verify against a self-vouched key",
                file=sys.stderr,
            )
            return 1

    if not pk_hex:
        print("garl-verify: no verifying key available", file=sys.stderr)
        return 1

    ok = _verify_cert(cert, pk_hex)
    return _print_result(cert, ok, args.key_registry, args)


if __name__ == "__main__":
    sys.exit(main())
