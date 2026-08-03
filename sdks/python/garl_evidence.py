"""Offline Evidence Pack verification — "verify without trusting GARL".

Used by the garl-verify CLI (`garl-verify --evidence-pack pack.json`); also
importable. Checks, in order:

  1. pack signature        ECDSA-secp256k1 over the canonical pack minus
                           signature/verification_key_id
  2. receipt signature     same construction over pack["receipt"]
  3. Merkle inclusion      leaf = SHA-256(0x00 || output_hash); fold the
                           proof siblings (0x01 domain separation, RFC 6962)
                           to the anchored root
  4. capability chain      token_hash = SHA-256(jwt wire form) per link,
                           parent linkage by hash, each link's ES256K
                           signature against the key registry, child exp
                           never after parent exp
  5. on-chain root         (optional, needs --rpc) eth_call
                           MerkleAnchor.roots(batchId) == merkle_root

Key source order: an explicit --keys file beats the live registry beats the
pack-embedded snapshot (the last is self-referential; a warning is attached).

Only dependency: python-ecdsa (already required by garl-protocol). RPC check
uses stdlib urllib. The roots(uint256) selector is precomputed (0xc2b40ae4)
so no keccak implementation is needed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import urllib.request
from dataclasses import dataclass, field

from ecdsa import SECP256k1, VerifyingKey

ROOTS_SELECTOR = "c2b40ae4"  # keccak256("roots(uint256)")[:4]
DEFAULT_RPC = "https://mainnet.base.org"


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class PackVerification:
    checks: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append(CheckResult(name, ok, detail))


def _canonical(payload: dict) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


def _verify_sig(payload: dict, sig_hex: str, pubkey_hex: str) -> bool:
    try:
        vk = VerifyingKey.from_string(bytes.fromhex(pubkey_hex), curve=SECP256k1)
        digest = hashlib.sha256(_canonical(payload)).digest()
        return bool(vk.verify_digest(bytes.fromhex(sig_hex), digest))
    except Exception:
        return False


def _strip_sig(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if k not in ("signature", "verification_key_id")}


def _b64url_decode(seg: str) -> bytes:
    return base64.urlsafe_b64decode(seg + "=" * (-len(seg) % 4))


def verify_capability_link(jwt_form: str, keys: dict[str, str]) -> tuple[bool, str]:
    """Signature + structural check of one capability-token wire form."""
    try:
        header_b64, payload_b64, sig_b64 = jwt_form.split(".")
        header = json.loads(_b64url_decode(header_b64))
        if header.get("alg") != "ES256K" or header.get("typ") != "garl-cap-v0.1":
            return False, f"unexpected header {header}"
        kid = header.get("kid", "")
        if kid not in keys:
            return False, f"kid {kid} not in key registry"
        signing_input = f"{header_b64}.{payload_b64}".encode()
        digest = hashlib.sha256(signing_input).digest()
        vk = VerifyingKey.from_string(bytes.fromhex(keys[kid]), curve=SECP256k1)
        vk.verify_digest(_b64url_decode(sig_b64), digest)
        return True, "signature ok"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def verify_evidence_pack(
    pack: dict,
    keys: dict[str, str],
    *,
    rpc_url: str | None = None,
    keys_source: str = "registry",
) -> PackVerification:
    v = PackVerification()
    if keys_source == "embedded":
        v.warnings.append(
            "keys came from the pack itself (self-referential) — pass --keys or "
            "fetch https://api.garl.ai/.well-known/garl-keys.json independently"
        )

    # 1. pack signature
    kid = pack.get("verification_key_id", "")
    if kid not in keys:
        v.add("pack signature", False, f"verification_key_id {kid!r} not in key registry")
    else:
        v.add(
            "pack signature",
            _verify_sig(_strip_sig(pack), pack.get("signature", ""), keys[kid]),
            f"key {kid}",
        )

    # 2. receipt signature
    receipt = pack.get("receipt") or {}
    rkid = receipt.get("verification_key_id", "")
    if rkid not in keys:
        v.add("receipt signature", False, f"verification_key_id {rkid!r} not in key registry")
    else:
        v.add(
            "receipt signature",
            _verify_sig(_strip_sig(receipt), receipt.get("signature", ""), keys[rkid]),
            f"key {rkid}",
        )

    # 3. Merkle inclusion (skipped, not failed, when the pack is unanchored —
    # the pack states what was true at export time)
    proof = pack.get("merkle_proof")
    if not proof:
        v.warnings.append("pack is unanchored (no merkle_proof) — inclusion not checked")
    else:
        out_hash = (receipt.get("output_hash") or "").lower()
        leaf = hashlib.sha256(b"\x00" + bytes.fromhex(out_hash)).hexdigest()
        ok_leaf = leaf == (proof.get("leaf") or "").lower()
        cursor = bytes.fromhex(leaf)
        for step in proof.get("proof", []):
            sib = bytes.fromhex(step["sibling"])
            pair = sib + cursor if step["position"] == "left" else cursor + sib
            cursor = hashlib.sha256(b"\x01" + pair).digest()
        root_ok = cursor.hex() == (proof.get("merkle_root") or "").lower()
        v.add(
            "merkle inclusion",
            ok_leaf and root_ok,
            f"leaf {'ok' if ok_leaf else 'MISMATCH'}, root {'ok' if root_ok else 'MISMATCH'}",
        )

    # 4. capability chain
    chain = pack.get("capability_chain") or []
    if not chain:
        v.warnings.append("no capability chain in pack (receipt not token-bound)")
    else:
        chain_ok, details = True, []
        prev_parent_hash: str | None = None
        prev_exp: int | None = None
        for i, link in enumerate(chain):
            if link.get("found") is False:
                chain_ok = False
                details.append(f"link {i}: token missing from registry snapshot")
                continue
            jwt_form = link.get("jwt_form") or ""
            th = hashlib.sha256(jwt_form.encode()).hexdigest()
            if th != (link.get("token_hash") or "").lower():
                chain_ok = False
                details.append(f"link {i}: token_hash != sha256(jwt_form)")
            if prev_parent_hash is not None and th != prev_parent_hash:
                chain_ok = False
                details.append(f"link {i}: not the parent referenced by link {i-1}")
            sig_ok, sig_detail = verify_capability_link(jwt_form, keys)
            if not sig_ok:
                chain_ok = False
                details.append(f"link {i}: {sig_detail}")
            claims = link.get("claims") or {}
            exp = claims.get("exp")
            if prev_exp is not None and isinstance(exp, int) and prev_exp > exp:
                chain_ok = False
                details.append(f"link {i}: child outlives parent (exp)")
            prev_exp = exp if isinstance(exp, int) else prev_exp
            prev_parent_hash = (claims.get("parent") or None)
            if link.get("revoked_at"):
                v.warnings.append(f"capability link {i} was revoked at {link['revoked_at']}")
        v.add("capability chain", chain_ok, "; ".join(details) or f"{len(chain)} link(s) ok")

    # 5. on-chain root (optional)
    anchor = pack.get("anchor")
    if rpc_url and anchor and proof:
        batch_id = proof.get("verify_proof_args", {}).get("batchId")
        contract = anchor.get("contract_address")
        root = (anchor.get("merkle_root") or proof.get("merkle_root") or "").lower()
        try:
            calldata = "0x" + ROOTS_SELECTOR + format(int(batch_id), "064x")
            req = urllib.request.Request(
                rpc_url,
                data=json.dumps({
                    "jsonrpc": "2.0", "id": 1, "method": "eth_call",
                    "params": [{"to": contract, "data": calldata}, "latest"],
                }).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "garl-verify/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                stored = json.load(resp).get("result", "").removeprefix("0x").lower()
            v.add(
                "on-chain root",
                stored == root,
                f"roots({batch_id}) on {contract}" + ("" if stored == root else f" = {stored[:16]}… ≠ pack root"),
            )
        except Exception as e:
            v.add("on-chain root", False, f"RPC error: {type(e).__name__}: {e}")
    elif anchor and proof:
        v.warnings.append("on-chain root not checked (pass --rpc, e.g. --rpc https://mainnet.base.org)")

    return v
