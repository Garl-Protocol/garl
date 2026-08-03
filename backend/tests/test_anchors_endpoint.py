"""GET /api/v1/anchors — the public living-anchor-chain listing.

Covers the service (list_anchor_batches) shape/clamping logic and the route
integration, with Supabase mocked at the service boundary.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.merkle_batch import list_anchor_batches


@pytest.fixture
def client():
    return TestClient(app)


def _sb_returning(rows, count=None):
    """Supabase mock whose select chain resolves to the given rows."""
    sb = MagicMock()
    res = MagicMock()
    res.data = rows
    res.count = count if count is not None else len(rows)
    chain = MagicMock()
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.range.return_value = chain
    chain.execute.return_value = res
    sb.table.return_value = chain
    return sb


_ANCHORED_ROW = {
    "batch_id": 2,
    "root": "eb" * 32,
    "receipt_count": 2,
    "built_at": "2026-08-03T20:20:00+00:00",
    "anchored_at": "2026-08-03T20:20:28+00:00",
    "chain_id": 8453,
    "tx_hash": "0x" + "9a" * 32,
    "contract_address": "0xBeD7EdeFbEb02be9682bCdeC5fb5D7DA28b1b6F2",
    "onchain_batch_id": 2,
}

_PENDING_ROW = {
    "batch_id": 3,
    "root": "aa" * 32,
    "receipt_count": 5,
    "built_at": "2026-08-10T00:00:00+00:00",
    "anchored_at": None,
    "chain_id": None,
    "tx_hash": None,
    "contract_address": None,
    "onchain_batch_id": None,
}


class TestListAnchorBatchesService:
    def test_anchored_batch_shape(self):
        with patch("app.services.merkle_batch._get_supabase", return_value=_sb_returning([_ANCHORED_ROW])):
            out = list_anchor_batches()
        assert out["total"] == 1
        b = out["batches"][0]
        assert b["anchored"] is True
        assert b["merkle_root"] == _ANCHORED_ROW["root"]
        assert b["receipt_count"] == 2
        assert b["chain"] == "base-mainnet"
        assert b["onchain_batch_id"] == 2
        assert b["explorer_url"] == f"https://basescan.org/tx/{_ANCHORED_ROW['tx_hash']}"

    def test_pending_batch_is_visible_not_hidden(self):
        """A built-but-unbroadcast batch must appear with anchored=False —
        gaps in the chain are surfaced, never silently dropped."""
        with patch("app.services.merkle_batch._get_supabase", return_value=_sb_returning([_PENDING_ROW])):
            out = list_anchor_batches()
        b = out["batches"][0]
        assert b["anchored"] is False
        assert b["tx_hash"] is None
        assert b["explorer_url"] is None
        # falls back to DB batch_id when the on-chain id was never recorded
        assert b["onchain_batch_id"] == 3

    def test_limit_clamped_to_200(self):
        sb = _sb_returning([])
        with patch("app.services.merkle_batch._get_supabase", return_value=sb):
            out = list_anchor_batches(limit=10_000, offset=-5)
        assert out["limit"] == 200
        assert out["offset"] == 0
        sb.table.return_value.range.assert_called_once_with(0, 199)

    def test_empty_chain(self):
        with patch("app.services.merkle_batch._get_supabase", return_value=_sb_returning([], count=0)):
            out = list_anchor_batches()
        assert out == {"total": 0, "limit": 100, "offset": 0, "batches": []}


class TestAnchorsRoute:
    def test_get_anchors_ok(self, client):
        with patch("app.services.merkle_batch._get_supabase", return_value=_sb_returning([_ANCHORED_ROW, _PENDING_ROW], count=2)):
            resp = client.get("/api/v1/anchors")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert [b["batch_id"] for b in body["batches"]] == [2, 3]
        assert "max-age=60" in resp.headers["cache-control"]

    def test_get_anchors_pagination_params(self, client):
        sb = _sb_returning([])
        with patch("app.services.merkle_batch._get_supabase", return_value=sb):
            resp = client.get("/api/v1/anchors?limit=5&offset=10")
        assert resp.status_code == 200
        sb.table.return_value.range.assert_called_once_with(10, 14)
