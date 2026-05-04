"""Material import routes for the local Web API."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Request

from kronos.web.app import get_context
from kronos.web.schemas import MaterialImportRequest, MaterialImportResponse

router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.post("", response_model=MaterialImportResponse)
def import_material(
    payload: MaterialImportRequest,
    request: Request,
) -> MaterialImportResponse:
    """Import one user-provided research material into local append-only storage."""
    context = get_context(request)
    material = MaterialImportResponse(
        material_id=f"material-{uuid4().hex}",
        title_zh=payload.title_zh,
        source_type=payload.source_type,
        candidate_id=payload.candidate_id,
        tags=payload.tags,
        stored_at=datetime.now(UTC),
    )
    record = {
        **material.model_dump(mode="json"),
        "content": payload.content,
    }
    context.material_store_path.parent.mkdir(parents=True, exist_ok=True)
    with context.material_store_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False))
        handle.write("\n")
    return material
