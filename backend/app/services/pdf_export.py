"""PDF Export service — generates clinical case reports using reportlab."""
from __future__ import annotations

from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.case import Case
from app.models.clinical_fact import ClinicalFactModel
from app.models.document import DocumentModel, LabValueModel
from app.models.message import Message
from app.models.patient import PatientTimelineEvent

# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

_TRIAGE_COLORS = {
    "GREEN": colors.HexColor("#16a34a"),
    "YELLOW": colors.HexColor("#ca8a04"),
    "RED": colors.HexColor("#dc2626"),
}


def _build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    styles: dict[str, ParagraphStyle] = {}

    styles["title"] = ParagraphStyle(
        "title",
        parent=base["Title"],
        fontSize=20,
        textColor=colors.HexColor("#1e3a5f"),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    styles["subtitle"] = ParagraphStyle(
        "subtitle",
        parent=base["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#6b7280"),
        alignment=TA_CENTER,
        spaceAfter=20,
    )
    styles["section"] = ParagraphStyle(
        "section",
        parent=base["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1e3a5f"),
        spaceBefore=14,
        spaceAfter=6,
    )
    styles["body"] = ParagraphStyle(
        "body",
        parent=base["Normal"],
        fontSize=9,
        leading=14,
        spaceAfter=4,
    )
    styles["label"] = ParagraphStyle(
        "label",
        parent=base["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#6b7280"),
    )
    return styles


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------


async def generate_case_pdf(
    db: AsyncSession,
    case_id: str,
    user_id: str,
) -> bytes:
    """
    Generate a PDF report for a clinical case.
    Returns raw PDF bytes.
    Raises ValueError if case not found.
    """
    styles = _build_styles()
    elements: list[Any] = []

    # ------------------------------------------------------------------
    # 1. Fetch data
    # ------------------------------------------------------------------
    case_result = await db.execute(select(Case).where(Case.id == case_id))
    case = case_result.scalar_one_or_none()
    if case is None:
        raise ValueError(f"Case {case_id} not found")

    msgs_result = await db.execute(
        select(Message)
        .where(Message.case_id == case_id)
        .order_by(Message.created_at)
    )
    messages = msgs_result.scalars().all()

    facts_result = await db.execute(
        select(ClinicalFactModel).where(ClinicalFactModel.case_id == case_id)
    )
    facts = facts_result.scalars().all()

    # IMPORTANT: filter by case_id AND user_id — a patient can have multiple
    # cases and labs from one case must NOT appear in another case's PDF.
    labs_result = await db.execute(
        select(LabValueModel)
        .join(DocumentModel, LabValueModel.document_id == DocumentModel.id)
        .where(DocumentModel.user_id == user_id)
        .where(DocumentModel.case_id == case_id)
    )
    lab_values = labs_result.scalars().all()

    timeline_result = await db.execute(
        select(PatientTimelineEvent)
        .where(PatientTimelineEvent.case_id == case_id)
        .order_by(PatientTimelineEvent.occurred_at)
    )
    timeline = timeline_result.scalars().all()

    # ------------------------------------------------------------------
    # 2. Build PDF elements
    # ------------------------------------------------------------------
    # Header
    elements.append(Paragraph("MedAgent — Reporte Clínico", styles["title"]))
    elements.append(
        Paragraph(
            f"Generado el {_fmt_date(case.created_at)} | Caso ID: {case_id[:8]}…",
            styles["subtitle"],
        )
    )
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb")))
    elements.append(Spacer(1, 0.3 * cm))

    # Case info table
    triage_color = _TRIAGE_COLORS.get(case.triage_level or "", colors.grey)
    case_data = [
        ["Título", case.title or "Sin título"],
        ["Motivo de consulta", case.chief_complaint or "—"],
        ["Estado", case.status.upper()],
        ["Triage", case.triage_level or "—"],
        ["Confianza triage", f"{(case.triage_confidence or 0) * 100:.0f}%"],
        ["Creado", _fmt_date(case.created_at)],
        ["Resuelto", _fmt_date(case.resolved_at) if case.resolved_at else "En curso"],
    ]
    case_table = Table(case_data, colWidths=[5 * cm, 12 * cm])
    case_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#6b7280")),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(case_table)
    elements.append(Spacer(1, 0.4 * cm))

    # Clinical facts
    if facts:
        elements.append(Paragraph("Hallazgos Clínicos", styles["section"]))
        fact_data = [["Tipo", "Valor", "Agente", "Confianza"]]
        for f in facts:
            fact_data.append([
                f.fact_type or "—",
                str(f.value)[:60] if hasattr(f, "value") and f.value else "—",
                f.source_agent or "—",
                f"{(f.confidence or 0) * 100:.0f}%" if f.confidence else "—",
            ])
        ft = Table(fact_data, colWidths=[4 * cm, 8 * cm, 3 * cm, 2 * cm])
        ft.setStyle(_table_header_style())
        elements.append(ft)
        elements.append(Spacer(1, 0.3 * cm))

    # Lab values
    if lab_values:
        elements.append(Paragraph("Valores de Laboratorio", styles["section"]))
        lab_data = [["Prueba", "Valor", "Unidad", "Referencia", "Flag"]]
        for lv in lab_values:
            lab_data.append([
                lv.test_name or "—",
                str(lv.value) if lv.value else "—",
                lv.unit or "—",
                lv.reference_range or "—",
                lv.flag or "—",
            ])
        lt = Table(lab_data, colWidths=[5 * cm, 3 * cm, 2.5 * cm, 4 * cm, 2.5 * cm])
        lt.setStyle(_table_header_style())
        elements.append(lt)
        elements.append(Spacer(1, 0.3 * cm))

    # Timeline
    if timeline:
        elements.append(Paragraph("Línea de Tiempo Clínica", styles["section"]))
        tl_data = [["Fecha", "Tipo", "Resumen"]]
        for ev in timeline:
            tl_data.append([
                _fmt_date(ev.occurred_at),
                ev.event_type or "—",
                (ev.summary or "")[:80],
            ])
        tlt = Table(tl_data, colWidths=[4 * cm, 3.5 * cm, 9.5 * cm])
        tlt.setStyle(_table_header_style())
        elements.append(tlt)
        elements.append(Spacer(1, 0.3 * cm))

    # Conversation transcript (last 20 messages max)
    user_msgs = [m for m in messages if m.role == "user"][-20:]
    assistant_msgs = [m for m in messages if m.role == "assistant"][-20:]
    if messages:
        elements.append(Paragraph("Transcripción (extracto)", styles["section"]))
        for msg in messages[-30:]:
            role_label = "Paciente" if msg.role == "user" else "MedAgent"
            elements.append(
                Paragraph(
                    f"<b>{role_label}:</b> {(msg.content or '')[:300]}",
                    styles["body"],
                )
            )
        elements.append(Spacer(1, 0.3 * cm))

    # Footer note
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e5e7eb")))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(
        Paragraph(
            "⚠ Este reporte es orientativo. No reemplaza el criterio médico profesional.",
            styles["label"],
        )
    )

    # ------------------------------------------------------------------
    # 3. Build PDF
    # ------------------------------------------------------------------
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    doc.build(elements)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _fmt_date(dt) -> str:
    if dt is None:
        return "—"
    try:
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(dt)


def _table_header_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
