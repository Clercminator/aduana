from __future__ import annotations

import io
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

WATERMARK = "BORRADOR DEMO - NO APTO PARA PRESENTACIÓN."


def _sum(lines: list[dict[str, Any]], path: tuple[str, ...]) -> Decimal:
    total = Decimal("0")
    for line in lines:
        value: Any = line
        for key in path:
            value = value.get(key, {}) if isinstance(value, dict) else None
        total += Decimal(str(value or "0"))
    return total


def din_payload(state: dict[str, Any]) -> list[dict[str, Any]]:
    calculation = state.get("calculation") or {}
    dispatch = state.get("dispatch") or {}
    lines = calculation.get("lines", [])
    totals = calculation.get("totals", {})
    grouped: dict[str, list[dict[str, Any]]] = {}
    for line in lines:
        grouped.setdefault(str(line.get("invoice") or "sin número"), []).append(line)
    generated_at = datetime.now(UTC).isoformat()
    declarations: list[dict[str, Any]] = []
    for invoice, invoice_lines in grouped.items():
        customs_value = _sum(invoice_lines, ("customs_value",))
        payable = _sum(invoice_lines, ("declaration_view", "payable_levies"))
        landed = _sum(invoice_lines, ("cost_view", "landed_cost"))
        recoverable = _sum(invoice_lines, ("cost_view", "recoverable_levies_excluded"))
        fx_rate = Decimal(str(totals.get("fx_rate", "0")))
        settlement = (payable * fx_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        declarations.append(
            {
                "notice": WATERMARK,
                "mapping_status": "provisional_pending_customs_expert_validation",
                "generated_at": generated_at,
                "dispatch": {
                    "despacho_no": dispatch.get("despacho_no"),
                    "referencia": dispatch.get("referencia"),
                    "jurisdiction": "CL",
                    "regime": dispatch.get("regime"),
                    "din_acceptance_date": dispatch.get("din_acceptance_date"),
                },
                "invoice": invoice,
                "lines": invoice_lines,
                "declaration_view": {
                    "customs_value": format(customs_value, "f"),
                    "total_payable": format(payable, "f"),
                    "settlement_currency": totals.get("settlement_currency"),
                    "total_payable_settlement": format(settlement, "f"),
                },
                "cost_view": {
                    "landed_cost": format(landed, "f"),
                    "recoverable_levies_excluded": format(recoverable, "f"),
                },
                "fx": {
                    "rate": totals.get("fx_rate"),
                    "source": totals.get("fx_source"),
                    "period": totals.get("fx_period"),
                },
                "rules": calculation.get("rules", []),
            }
        )
    return declarations


def _declaration_story(payload: dict[str, Any], styles: dict[str, ParagraphStyle]) -> list[Any]:
    dispatch = payload["dispatch"]
    declaration = payload["declaration_view"]
    cost = payload["cost_view"]
    story: list[Any] = [
        Paragraph("Borrador de Declaración de Ingreso", styles["title"]),
        Paragraph(f"Factura {payload['invoice']}", styles["subtitle"]),
        Paragraph(WATERMARK, styles["warning"]),
        Spacer(1, 4 * mm),
    ]
    header = Table(
        [
            [
                "Despacho",
                dispatch.get("despacho_no") or "-",
                "Referencia",
                dispatch.get("referencia") or "-",
                "Aceptación DIN",
                dispatch.get("din_acceptance_date") or "-",
            ],
            [
                "Valor aduanero",
                f"USD {declaration.get('customs_value', '-')}",
                "Pago declaración",
                f"USD {declaration.get('total_payable', '-')}",
                "Costo puesto",
                f"USD {cost.get('landed_cost', '-')}",
            ],
        ],
        colWidths=[24 * mm, 45 * mm, 24 * mm, 55 * mm, 24 * mm, 55 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b8c2cf")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#edf3f7")),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTNAME", (4, 0), (4, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([header, Spacer(1, 5 * mm), Paragraph("Ítems y tributos", styles["heading"])])
    rows = [
        [
            "Factura",
            "Descripción",
            "HS",
            "FOB USD",
            "Flete",
            "Seguro",
            "Valor aduanero",
            "Tasa",
            "Tributos USD",
        ]
    ]
    for line in payload["lines"]:
        allocations = line.get("allocations", {})
        duty_pct = Decimal(str(line.get("duty_rate", "0"))) * Decimal("100")
        rows.append(
            [
                line.get("invoice"),
                Paragraph(str(line.get("description") or ""), styles["small"]),
                line.get("hs_code"),
                line.get("fob"),
                allocations.get("freight", "0"),
                allocations.get("insurance", "0"),
                line.get("customs_value"),
                f"{duty_pct.quantize(Decimal('0.01'))}%",
                line.get("levy_total"),
            ]
        )
    table = Table(
        rows,
        repeatRows=1,
        colWidths=[28 * mm, 65 * mm, 20 * mm, 23 * mm, 20 * mm, 20 * mm, 29 * mm, 18 * mm, 25 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#08213f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c8d0d9")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fb")]),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    fx = payload["fx"]
    story.extend(
        [
            table,
            Spacer(1, 4 * mm),
            Paragraph(
                f"Dólar aduanero mensual: {fx.get('rate', '-')} - {fx.get('source', '-')} - período {fx.get('period', '-')}",
                styles["small"],
            ),
            Paragraph(
                f"IVA recuperable excluido del costo: USD {cost.get('recoverable_levies_excluded', '-')}",
                styles["small"],
            ),
            Spacer(1, 3 * mm),
            Paragraph(
                "Documento provisional para demostración. La estructura DIN y el mapeo de campos requieren validación de un experto aduanero antes de cualquier uso real.",
                styles["warning"],
            ),
        ]
    )
    return story


def render_din_pdf(state: dict[str, Any]) -> bytes:
    payloads = din_payload(state)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=11 * mm,
        bottomMargin=11 * mm,
    )
    samples = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "title",
            parent=samples["Title"],
            fontName="Helvetica-Bold",
            fontSize=17,
            textColor=colors.HexColor("#08213f"),
            alignment=TA_LEFT,
            spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=samples["Heading2"],
            fontSize=11,
            textColor=colors.HexColor("#08213f"),
        ),
        "heading": samples["Heading2"],
        "warning": ParagraphStyle(
            "warning",
            parent=samples["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.HexColor("#c81e1e"),
            alignment=TA_CENTER,
            leading=12,
        ),
        "small": ParagraphStyle("small", parent=samples["Normal"], fontSize=8, leading=10),
    }
    story: list[Any] = []
    for index, payload in enumerate(payloads):
        if index:
            story.append(PageBreak())
        story.extend(_declaration_story(payload, styles))
    if not story:
        story.append(Paragraph("No hay facturas disponibles para generar DIN.", styles["warning"]))

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#65758b"))
        canvas.drawString(12 * mm, 7 * mm, "IMR Tech - Automatización de despachos")
        canvas.drawRightString(landscape(A4)[0] - 12 * mm, 7 * mm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
