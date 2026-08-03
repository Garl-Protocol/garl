"""
Evidence Pack API surface (EU AI Act Art. 12/19 exportable log unit).

Public read — receipts are public evidence, and the pack only bundles
already-public material (envelope, capability-chain facts, Merkle proof,
key registry). Kept in its own router (mounted from app.main) so the
heavily-owned app/api/routes.py stays untouched.

The PDF endpoint deliberately returns a plain ``fastapi.Response`` with an
in-memory bytes body — NOT FileResponse/StaticFiles/StreamingResponse
(see the starlette CVE note in backend/requirements.txt).
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException, Request, Response

# Reuse the existing helpers rather than replicating them. routes.py does not
# import this module, so there is no circular-import risk (same approach as
# app/api/alert_routes.py).
from app.api.routes import _check_rate_limit, _get_client_ip

logger = logging.getLogger(__name__)

evidence_router = APIRouter(prefix="/api/v1", tags=["Evidence Pack"])


def _build_pack_or_404(receipt_id: str) -> dict:
    from app.services.evidence_pack import build_evidence_pack

    pack = build_evidence_pack((receipt_id or "").strip())
    if pack is None:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return pack


@evidence_router.get(
    "/receipts/{receipt_id}/evidence-pack",
    summary="Signed Evidence Pack for one receipt (JSON)",
)
async def get_evidence_pack(receipt_id: str, request: Request):
    """One verifiable bundle per receipt: signed envelope, capability chain,
    Merkle inclusion proof + anchor coordinates, session alerts, key registry,
    and offline verification steps. The pack itself is signed. Accepts a
    receipt_id (UUID) or an output_hash (64-hex). 404 if unknown."""
    _check_rate_limit(_get_client_ip(request), "default", request)
    return _build_pack_or_404(receipt_id)


@evidence_router.get(
    "/receipts/{receipt_id}/evidence-pack.pdf",
    summary="Evidence Pack rendered as a PDF document",
)
async def get_evidence_pack_pdf(receipt_id: str, request: Request):
    """Same pack as the JSON endpoint, rendered as a factual A4 document
    for auditors / local retention. 404 if the receipt is unknown."""
    _check_rate_limit(_get_client_ip(request), "default", request)
    pack = _build_pack_or_404(receipt_id)

    from app.services.evidence_pack import render_evidence_pack_pdf

    pdf_bytes = render_evidence_pack_pdf(pack)
    rid = (pack.get("receipt") or {}).get("receipt_id") or receipt_id
    # Header-safe short id for the filename (receipt_id is a UUID or 64-hex).
    short = re.sub(r"[^a-zA-Z0-9]", "", str(rid))[:8] or "receipt"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="garl-evidence-{short}.pdf"'
        },
    )
