"""Export API — PDF export for clinical cases."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.case import Case
from app.models.user import User
from app.services.audit import log_action
from app.services.pdf_export import generate_case_pdf

router = APIRouter(tags=["export"])


@router.get("/cases/{case_id}/export/pdf")
async def export_case_pdf(
    case_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Generate and return a PDF report for a clinical case."""
    result = await db.execute(select(Case).where(Case.id == case_id))
    case = result.scalar_one_or_none()

    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    if case.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    pdf_bytes = await generate_case_pdf(db, str(case_id), str(current_user.id))

    await log_action(
        db,
        user_id=current_user.id,
        action="export_pdf",
        entity_type="case",
        entity_id=case_id,
    )
    await db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=case_{case_id}.pdf",
        },
    )
