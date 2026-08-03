"""Fully-OFFLINE end-to-end verification of a real anchored batch.

This is the "verify without trusting GARL" claim as an executable test. Using
only committed fixtures (real production data from Base mainnet batch 2) and
zero network access, it walks the entire evidence chain:

    receipt envelope --ECDSA--> published pubkey
    output_hash --RFC-6962 Merkle--> batch root
    batch root ==  root inside the anchor() calldata of the raw signed tx
    keccak256(raw signed tx) == the Base mainnet tx hash

The only fact NOT provable offline is that the tx hash is included in a Base
block — that final hop is one Basescan lookup (or the e2e-marked RPC test).

No new dependencies: keccak-256 and the EIP-1559/RLP decoder are implemented
inline (~60 lines) and self-tested against published test vectors.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from ecdsa import SECP256k1, VerifyingKey

from app.core.canonical import canonical_bytes
from app.services.merkle_batch import (
    compute_merkle_root,
    merkle_proof,
    verify_merkle_proof,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Minimal keccak-256 (the pre-NIST Keccak padding Ethereum uses, NOT sha3_256)
# ---------------------------------------------------------------------------

_KECCAK_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_KECCAK_ROT = [
    [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
]
_MASK = (1 << 64) - 1


def _rotl(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & _MASK


def _keccak_f(state: list[list[int]]) -> None:
    for rnd in range(24):
        # theta
        c = [state[x][0] ^ state[x][1] ^ state[x][2] ^ state[x][3] ^ state[x][4] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rotl(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                state[x][y] ^= d[x]
        # rho + pi
        b = [[0] * 5 for _ in range(5)]
        for x in range(5):
            for y in range(5):
                b[y][(2 * x + 3 * y) % 5] = _rotl(state[x][y], _KECCAK_ROT[x][y])
        # chi
        for x in range(5):
            for y in range(5):
                state[x][y] = b[x][y] ^ ((~b[(x + 1) % 5][y]) & b[(x + 2) % 5][y]) & _MASK
        # iota
        state[0][0] ^= _KECCAK_RC[rnd]


def keccak256(data: bytes) -> bytes:
    rate = 136  # 1088-bit rate for 256-bit output
    state = [[0] * 5 for _ in range(5)]
    # pad10*1 with Keccak domain byte 0x01 (SHA-3 would use 0x06)
    padded = data + b"\x01" + b"\x00" * ((-len(data) - 2) % rate) + b"\x80"
    for block_off in range(0, len(padded), rate):
        block = padded[block_off:block_off + rate]
        for i in range(rate // 8):
            lane = int.from_bytes(block[i * 8:(i + 1) * 8], "little")
            state[i % 5][i // 5] ^= lane
        _keccak_f(state)
    out = b""
    for i in range(4):  # 32 bytes = 4 lanes
        out += state[i % 5][i // 5].to_bytes(8, "little")
    return out


# ---------------------------------------------------------------------------
# Minimal RLP decoder (enough for an EIP-1559 transaction payload)
# ---------------------------------------------------------------------------

def _rlp_decode(buf: bytes, pos: int = 0):
    prefix = buf[pos]
    if prefix < 0x80:
        return buf[pos:pos + 1], pos + 1
    if prefix < 0xB8:
        n = prefix - 0x80
        return buf[pos + 1:pos + 1 + n], pos + 1 + n
    if prefix < 0xC0:
        ln = prefix - 0xB7
        n = int.from_bytes(buf[pos + 1:pos + 1 + ln], "big")
        start = pos + 1 + ln
        return buf[start:start + n], start + n
    if prefix < 0xF8:
        n = prefix - 0xC0
        end = pos + 1 + n
        items, p = [], pos + 1
    else:
        ln = prefix - 0xF7
        n = int.from_bytes(buf[pos + 1:pos + 1 + ln], "big")
        end = pos + 1 + ln + n
        items, p = [], pos + 1 + ln
    while p < end:
        item, p = _rlp_decode(buf, p)
        items.append(item)
    return items, end


# ---------------------------------------------------------------------------
# Fixtures (real Base mainnet data, captured 2026-08-03)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def batch():
    return json.loads((FIXTURES / "anchor_batch2.json").read_text())


@pytest.fixture(scope="module")
def raw_tx() -> bytes:
    hexstr = (FIXTURES / "anchor_batch2_rawtx.hex").read_text().strip()
    return bytes.fromhex(hexstr.removeprefix("0x"))


@pytest.fixture(scope="module")
def key_registry():
    return json.loads((FIXTURES / "garl_keys.json").read_text())


# ---------------------------------------------------------------------------
# Self-tests for the inline crypto (published vectors)
# ---------------------------------------------------------------------------

class TestInlinePrimitives:
    def test_keccak256_empty_vector(self):
        # The famous Ethereum empty-code hash (every empty account's codeHash)
        assert keccak256(b"").hex() == (
            "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
        )

    def test_keccak256_abc_vector(self):
        assert keccak256(b"abc").hex() == (
            "4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"
        )

    def test_rlp_roundtrip_shapes(self):
        # "dog" -> 0x83 'd' 'o' 'g'; list ["cat","dog"] -> 0xc8 0x83 cat 0x83 dog
        item, _ = _rlp_decode(bytes.fromhex("83646f67"))
        assert item == b"dog"
        items, _ = _rlp_decode(bytes.fromhex("c88363617483646f67"))
        assert items == [b"cat", b"dog"]


# ---------------------------------------------------------------------------
# The offline evidence chain
# ---------------------------------------------------------------------------

class TestOfflineEvidenceChain:
    def test_1_every_envelope_signature_verifies_against_published_key(self, batch, key_registry):
        keys = {k["key_id"]: k["public_key_hex"] for k in key_registry["keys"]}
        for env in batch["envelopes"]:
            kid = env["verification_key_id"]
            assert kid in keys, f"key {kid} not in published registry"
            vk = VerifyingKey.from_string(bytes.fromhex(keys[kid]), curve=SECP256k1)
            unsigned = {k: v for k, v in env.items() if k not in ("signature", "verification_key_id")}
            digest = hashlib.sha256(canonical_bytes(unsigned)).digest()
            assert vk.verify_digest(bytes.fromhex(env["signature"]), digest)

    def test_2_envelope_hashes_rebuild_the_anchored_merkle_root(self, batch):
        leaves = [
            hashlib.sha256(b"\x00" + bytes.fromhex(e["output_hash"])).hexdigest()
            for e in batch["envelopes"]
        ]
        assert compute_merkle_root(leaves) == batch["merkle_root"]

    def test_3_inclusion_proof_roundtrip_for_each_receipt(self, batch):
        leaves = [
            hashlib.sha256(b"\x00" + bytes.fromhex(e["output_hash"])).hexdigest()
            for e in batch["envelopes"]
        ]
        for i in range(len(leaves)):
            proof = merkle_proof(leaves, i)
            assert verify_merkle_proof(leaves[i], proof, batch["merkle_root"])

    def test_4_raw_tx_hashes_to_the_published_tx_hash(self, batch, raw_tx):
        assert "0x" + keccak256(raw_tx).hex() == batch["tx_hash"]

    def test_5_calldata_commits_to_root_and_count_on_the_right_contract(self, batch, raw_tx):
        # EIP-1559: 0x02 || rlp([chainId, nonce, prioFee, maxFee, gas, to,
        #                        value, data, accessList, yParity, r, s])
        assert raw_tx[0] == 0x02, "expected a type-2 (EIP-1559) transaction"
        fields, _ = _rlp_decode(raw_tx, 1)
        chain_id = int.from_bytes(fields[0], "big")
        to = "0x" + fields[5].hex()
        data = fields[7]

        assert chain_id == batch["chain_id"] == 8453
        assert to.lower() == batch["contract_address"].lower()

        selector = keccak256(b"anchor(bytes32,uint256)")[:4]
        assert data[:4] == selector, "calldata is not an anchor() call"
        root_arg = data[4:36].hex()
        count_arg = int.from_bytes(data[36:68], "big")
        assert root_arg == batch["merkle_root"]
        assert count_arg == batch["receipt_count"] == len(batch["envelopes"])


@pytest.mark.e2e
class TestOnChainAnchor:
    """The single non-offline hop: the tx exists on Base and the contract's
    stored root matches. Run with `pytest -m e2e` (needs network)."""

    def test_contract_stores_the_batch_root(self, batch):
        import requests

        rpc = "https://mainnet.base.org"
        # roots(uint256) selector on MerkleAnchor
        sel = keccak256(b"roots(uint256)")[:4].hex()
        arg = format(batch["onchain_batch_id"], "064x")
        resp = requests.post(rpc, json={
            "jsonrpc": "2.0", "id": 1, "method": "eth_call",
            "params": [{"to": batch["contract_address"], "data": "0x" + sel + arg}, "latest"],
        }, timeout=15)
        stored = resp.json()["result"].removeprefix("0x")
        assert stored == batch["merkle_root"]

    def test_tx_is_on_base(self, batch):
        import requests

        resp = requests.post("https://mainnet.base.org", json={
            "jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionReceipt",
            "params": [batch["tx_hash"]],
        }, timeout=15)
        receipt = resp.json()["result"]
        assert receipt is not None and receipt["status"] == "0x1"
