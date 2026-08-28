from __future__ import annotations

import io
import math
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

WATERMARK = "BORRADOR DEMO - NO APTO PARA PRESENTACIÓN."
DIN_PAGE_SIZE = (216 * mm, 330 * mm)
_BLUE = colors.HexColor("#8299b2")
_PALE_BLUE = colors.HexColor("#dbe3e9")
_INK = colors.HexColor("#111827")
_MUTED = colors.HexColor("#4b5563")
_ANNEX_LINES_PER_PAGE = 24


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except Exception:
        return Decimal("0")


def _sum(lines: list[dict[str, Any]], path: tuple[str, ...]) -> Decimal:
    total = Decimal("0")
    for line in lines:
        value: Any = line
        for key in path:
            value = value.get(key, {}) if isinstance(value, dict) else None
        total += _decimal(value)
    return total


def _cited_value(payload: dict[str, Any] | None, key: str, default: Any = None) -> Any:
    if not payload:
        return default
    value = payload.get(key, default)
    if isinstance(value, dict) and "value" in value:
        return value.get("value", default)
    return value


def _document_extractions(state: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for document in state.get("documents") or []:
        extraction = document.get("extraction") or document.get("payload")
        if not isinstance(extraction, dict):
            continue
        doc_type = document.get("doc_type") or extraction.get("doc_type")
        output.append({"doc_type": doc_type, "payload": extraction})
    return output


def _first_document(documents: list[dict[str, Any]], doc_type: str) -> dict[str, Any]:
    return next((item["payload"] for item in documents if item.get("doc_type") == doc_type), {})


def _invoice_document(documents: list[dict[str, Any]], invoice_number: str) -> dict[str, Any]:
    for item in documents:
        if item.get("doc_type") != "commercial_invoice":
            continue
        payload = item["payload"]
        if str(_cited_value(payload, "invoice_number") or "") == invoice_number:
            return payload
    return {}


def _packing_values(packing: dict[str, Any], invoice_number: str) -> tuple[Any, Any]:
    for line in packing.get("lines") or []:
        if str(_cited_value(line, "invoice_number") or "") == invoice_number:
            return _cited_value(line, "cartons"), _cited_value(line, "gross_weight_kg")
    return _cited_value(packing, "package_count"), _cited_value(packing, "gross_weight_kg")


def _country_from_agreement(agreement: Any) -> str:
    normalized = str(agreement or "").casefold()
    if "china" in normalized:
        return "CHINA"
    if "united states" in normalized or "eeuu" in normalized:
        return "ESTADOS UNIDOS"
    if "europe" in normalized or "unión europea" in normalized:
        return "UNIÓN EUROPEA"
    return ""


def _levy_summary(lines: list[dict[str, Any]]) -> list[dict[str, str]]:
    by_code: dict[str, dict[str, Any]] = {}
    for line in lines:
        for levy in line.get("levies") or []:
            code = str(levy.get("code") or "OTRO")
            target = by_code.setdefault(
                code,
                {
                    "label": str(levy.get("label") or code),
                    "amount": Decimal("0"),
                    "rates": set(),
                },
            )
            amount = levy.get("amount") or {}
            target["amount"] += _decimal(
                amount.get("amount") if isinstance(amount, dict) else amount
            )
            target["rates"].add(_decimal(levy.get("rate")))
    output: list[dict[str, str]] = []
    for code, values in by_code.items():
        rates = sorted(values["rates"])
        rate = rates[0] if len(rates) == 1 else None
        output.append(
            {
                "code": code,
                "label": values["label"],
                "rate": format(rate, "f") if rate is not None else "variable",
                "amount": format(values["amount"], "f"),
            }
        )
    return output


def _form_context(
    state: dict[str, Any], invoice_number: str, lines: list[dict[str, Any]]
) -> dict[str, Any]:
    documents = _document_extractions(state)
    invoice = _invoice_document(documents, invoice_number)
    instruction = _first_document(documents, "dispatch_instruction")
    bill = _first_document(documents, "bill_of_lading")
    packing = _first_document(documents, "packing_list")
    origin = _first_document(documents, "certificate_of_origin")
    dispatch = state.get("dispatch") or {}
    totals = (state.get("calculation") or {}).get("totals") or {}
    packages, gross_weight = _packing_values(packing, invoice_number)
    agreement = _cited_value(origin, "agreement_name") or _cited_value(
        instruction, "agreement_name"
    )
    currency = _cited_value(invoice, "currency") or totals.get("currency")
    fob = _sum(lines, ("fob",))
    freight = _sum(lines, ("allocations", "freight"))
    insurance = _sum(lines, ("allocations", "insurance"))
    customs_value = _sum(lines, ("customs_value",))
    payable = _sum(lines, ("declaration_view", "payable_levies"))
    fx_rate = _decimal(totals.get("fx_rate"))
    settlement = (payable * fx_rate).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return {
        "identification_number": "NO ASIGNADO",
        "customs_office": "",
        "customs_broker": "",
        "operation_type": "IMPORTACIÓN PARA CONSUMO",
        "importer_name": _cited_value(invoice, "consignee_name")
        or _cited_value(bill, "consignee_name")
        or _cited_value(instruction, "importer_name"),
        "importer_address": "",
        "importer_rut": "",
        "legal_representative": "",
        "supplier_name": _cited_value(invoice, "supplier_name"),
        "supplier_address": "",
        "country": _country_from_agreement(agreement),
        "transport_mode": "MARÍTIMA" if _cited_value(bill, "vessel") else "",
        "port_loading": _cited_value(bill, "port_loading"),
        "port_discharge": _cited_value(bill, "port_discharge"),
        "vessel": _cited_value(bill, "vessel"),
        "voyage": _cited_value(bill, "voyage"),
        "bl_number": _cited_value(bill, "bl_number"),
        "shipped_on_board_date": _cited_value(bill, "shipped_on_board_date"),
        "container_number": _cited_value(bill, "container_number")
        or _cited_value(packing, "container_number"),
        "warehouse": "",
        "manifest": "",
        "regime": dispatch.get("regime") or "import_for_consumption",
        "currency": currency,
        "incoterm": _cited_value(invoice, "incoterm"),
        "agreement": agreement,
        "origin_certificate": _cited_value(origin, "certificate_number"),
        "packages": packages,
        "gross_weight_kg": gross_weight,
        "fob": format(fob, "f"),
        "freight": format(freight, "f"),
        "insurance": format(insurance, "f"),
        "customs_value": format(customs_value, "f"),
        "total_payable": format(payable, "f"),
        "settlement_currency": totals.get("settlement_currency"),
        "total_payable_settlement": format(settlement, "f"),
        "fx_rate": totals.get("fx_rate"),
        "fx_source": totals.get("fx_source"),
        "fx_period": totals.get("fx_period"),
        "acceptance_date": dispatch.get("din_acceptance_date"),
        "invoice_date": _cited_value(invoice, "invoice_date"),
        "levies": _levy_summary(lines),
        "total_items": len(lines),
        "annex_pages": math.ceil(max(0, len(lines) - 1) / _ANNEX_LINES_PER_PAGE),
    }


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
        fx_rate = _decimal(totals.get("fx_rate"))
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
                "form": _form_context(state, invoice, invoice_lines),
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


def _display(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _money(value: Any, digits: int = 2) -> str:
    amount = _decimal(value).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    rendered = f"{amount:,.{digits}f}"
    return rendered.replace(",", "_").replace(".", ",").replace("_", ".")


def _percentage(value: Any) -> str:
    if str(value) == "variable":
        return "VARIABLE"
    return f"{_money(_decimal(value) * Decimal('100'), 2)}%"


def _date(value: Any) -> str:
    text = _display(value)
    if not text:
        return ""
    try:
        return date.fromisoformat(text[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return text


class _DINCanvas:
    def __init__(self, pdf: canvas.Canvas):
        self.pdf = pdf
        self.width, self.height = DIN_PAGE_SIZE
        self.pdf.setLineJoin(0)

    def _y(self, top: float) -> float:
        return self.height - top

    def line(self, x1: float, top1: float, x2: float, top2: float, width: float = 0.65) -> None:
        self.pdf.setStrokeColor(colors.black)
        self.pdf.setLineWidth(width)
        self.pdf.line(x1, self._y(top1), x2, self._y(top2))

    def rect(
        self,
        x: float,
        top: float,
        width: float,
        height: float,
        *,
        fill: Any | None = None,
        stroke_width: float = 0.65,
    ) -> None:
        self.pdf.setLineWidth(stroke_width)
        self.pdf.setStrokeColor(colors.black)
        if fill is None:
            self.pdf.setFillColor(colors.white)
            fill_value = 0
        else:
            self.pdf.setFillColor(fill)
            fill_value = 1
        self.pdf.rect(x, self._y(top + height), width, height, stroke=1, fill=fill_value)

    def text(
        self,
        x: float,
        top: float,
        value: Any,
        *,
        size: float = 7,
        bold: bool = False,
        color: Any = _INK,
        max_width: float | None = None,
        align: str = "left",
    ) -> None:
        text = _display(value)
        if not text:
            return
        font = "Helvetica-Bold" if bold else "Helvetica"
        if max_width is not None:
            text = self._fit(text, font, size, max_width)
        self.pdf.setFont(font, size)
        self.pdf.setFillColor(color)
        if align == "center":
            self.pdf.drawCentredString(x, self._y(top), text)
        elif align == "right":
            self.pdf.drawRightString(x, self._y(top), text)
        else:
            self.pdf.drawString(x, self._y(top), text)

    @staticmethod
    def _fit(text: str, font: str, size: float, max_width: float) -> str:
        if stringWidth(text, font, size) <= max_width:
            return text
        suffix = "..."
        while text and stringWidth(text + suffix, font, size) > max_width:
            text = text[:-1]
        return text.rstrip() + suffix

    def field(
        self,
        x: float,
        top: float,
        width: float,
        height: float,
        label: str,
        value: Any = "",
        *,
        fill: Any | None = None,
        value_size: float = 7.5,
        value_bold: bool = False,
        center: bool = False,
    ) -> None:
        self.rect(x, top, width, height, fill=fill)
        self.text(x + 3, top + 6, label, size=5.2, color=_MUTED, max_width=width - 6)
        if center:
            self.text(
                x + width / 2,
                top + height - 5,
                value,
                size=value_size,
                bold=value_bold,
                max_width=width - 8,
                align="center",
            )
        else:
            self.text(
                x + 4,
                top + height - 5,
                value,
                size=value_size,
                bold=value_bold,
                max_width=width - 8,
            )

    def section(self, x: float, top: float, width: float, title: str, height: float = 16) -> None:
        self.rect(x, top, width, height, fill=_BLUE, stroke_width=0.9)
        size = 10.0
        while size > 7 and stringWidth(title, "Helvetica-Bold", size) > width - 8:
            size -= 0.5
        self.text(x + 4, top + 12, title, size=size, bold=True, max_width=width - 8)

    def watermark(self) -> None:
        self.pdf.saveState()
        try:
            self.pdf.setFillAlpha(0.055)
        except AttributeError:
            pass
        self.pdf.setFillColor(colors.HexColor("#b91c1c"))
        self.pdf.setFont("Helvetica-Bold", 19)
        self.pdf.translate(self.width / 2, self.height / 2)
        self.pdf.rotate(34)
        self.pdf.drawCentredString(0, 0, WATERMARK)
        self.pdf.restoreState()


def _draw_header(form: _DINCanvas, payload: dict[str, Any], page_label: str) -> None:
    ctx = payload["form"]
    dispatch = payload["dispatch"]
    left, right, width = 18.0, 594.0, 576.0
    form.rect(left, 14, width, 64, stroke_width=1.2)
    form.text(left + 15, 29, "SERVICIO NACIONAL DE ADUANAS / CHILE", size=10, bold=True)
    form.text(left + 15, 54, "DECLARACIÓN DE INGRESO", size=20, bold=True)
    form.text(
        left + 15,
        70,
        f"DESPACHO {dispatch.get('despacho_no') or '-'} / FACTURA {payload['invoice']}",
        size=7.5,
        bold=True,
        max_width=390,
    )
    split = 435.0
    form.line(split, 14, split, 78, width=1.0)
    form.line(486, 14, 486, 78, width=1.0)
    form.line(split, 45, right, 45, width=1.0)
    form.text(split + 3, 24, "FORM", size=5.2)
    form.text(460.5, 37, "15", size=10, bold=True, align="center")
    form.text(511.5, 34, "07", size=12, bold=True, align="center")
    form.text(492, 24, "NÚMERO DE IDENTIFICACIÓN", size=5.2, bold=True, max_width=96)
    form.text(540, 38, ctx["identification_number"], size=7, bold=True, align="center")
    form.text(492, 55, "FECHA DE VENCIMIENTO", size=5.2, bold=True)
    form.text(540, 70, "PENDIENTE", size=7.5, bold=True, align="center")
    form.field(left, 78, 150, 24, "Aduana", ctx["customs_office"], fill=_PALE_BLUE)
    form.field(left + 150, 78, 40, 24, "Cód.", "25", center=True)
    form.field(left + 190, 78, 178, 24, "Despachador", ctx["customs_broker"], fill=_PALE_BLUE)
    form.field(left + 368, 78, 40, 24, "Cód.", "26", center=True)
    form.field(left + 408, 78, 168, 24, "Tipo de operación", ctx["operation_type"])
    form.text(428, 70, page_label, size=5.5, color=_MUTED, align="right")


def _draw_identification(form: _DINCanvas, payload: dict[str, Any]) -> None:
    ctx = payload["form"]
    left = 18.0
    form.section(left, 102, 576, "IDENTIFICACIÓN")
    form.field(left, 118, 240, 25, "Consignatario o importador", ctx["importer_name"])
    form.field(left + 240, 118, 240, 25, "Dirección", ctx["importer_address"])
    form.field(left + 480, 118, 96, 25, "Comuna", "")
    form.field(left, 143, 38, 25, "Cód.", "03", center=True)
    form.field(left + 38, 143, 118, 25, "RUT", ctx["importer_rut"])
    form.field(left + 156, 143, 198, 25, "Representante legal", ctx["legal_representative"])
    form.field(left + 354, 143, 126, 25, "RUT", "")
    form.field(left + 480, 143, 96, 25, "Ref. interna", payload["dispatch"].get("referencia"))
    form.field(left, 168, 240, 25, "Consignante", ctx["supplier_name"])
    form.field(left + 240, 168, 240, 25, "Dirección", ctx["supplier_address"])
    form.field(left + 480, 168, 76, 25, "País", ctx["country"])
    form.field(left + 556, 168, 20, 25, "Cód.", "")


def _draw_transport_and_finance(form: _DINCanvas, payload: dict[str, Any]) -> None:
    ctx = payload["form"]
    left, split = 18.0, 318.0
    form.section(left, 193, 300, "ORIGEN, TRANSPORTE Y ALMACENAJE")
    form.section(split, 193, 276, "RÉGIMEN SUSPENSIVO")
    form.field(left, 209, 100, 20, "País origen", ctx["country"])
    form.field(left + 100, 209, 100, 20, "País adquisición", ctx["country"])
    form.field(left + 200, 209, 100, 20, "Vía transporte", ctx["transport_mode"])
    form.field(left, 229, 150, 20, "Puerto embarque", ctx["port_loading"])
    form.field(left + 150, 229, 150, 20, "Puerto desembarque", ctx["port_discharge"])
    form.field(left, 249, 180, 20, "Nave / compañía transportadora", ctx["vessel"])
    form.field(left + 180, 249, 60, 20, "Viaje", ctx["voyage"])
    form.field(left + 240, 249, 60, 20, "Cód. país", "")
    form.field(left, 269, 180, 20, "Manifiesto", ctx["manifest"])
    form.field(left + 180, 269, 120, 20, "Fecha embarque", _date(ctx["shipped_on_board_date"]))
    form.field(left, 289, 180, 20, "Documento transporte", ctx["bl_number"])
    form.field(left + 180, 289, 120, 20, "Fecha documento", "")
    form.field(left, 309, 180, 21, "Almacenista", ctx["warehouse"])
    form.field(left + 180, 309, 60, 21, "Recepción", "")
    form.field(left + 240, 309, 60, 21, "Retiro", "")
    form.field(split, 209, 180, 20, "Dirección almacenamiento", ctx["warehouse"])
    form.field(split + 180, 209, 96, 20, "Comuna", "")
    form.field(split, 229, 55, 20, "Ad. control", "")
    form.field(split + 55, 229, 55, 20, "Plazo", "")
    form.field(split + 110, 229, 55, 20, "Parcial", "")
    form.field(split + 165, 229, 55, 20, "Hojas insumo", ctx["annex_pages"], center=True)
    form.field(split + 220, 229, 56, 20, "Total insumos", ctx["total_items"], center=True)
    form.field(split, 249, 80, 21, "Número", "")
    form.field(split + 80, 249, 70, 21, "Fecha", "")
    form.field(split + 150, 249, 66, 21, "Aduana", "")
    form.field(split + 216, 249, 60, 21, "Hojas anexas", ctx["annex_pages"], center=True)
    form.section(split, 270, 276, "ANTECEDENTES FINANCIEROS", height=16)
    form.field(split, 286, 125, 22, "Régimen importación", "IMPORT. CONSUMO")
    form.field(split + 125, 286, 85, 22, "Cód. Bco. comercial", "")
    form.field(split + 210, 286, 66, 22, "Divisas", "0", center=True)
    form.field(split, 308, 75, 22, "Forma pago", "PENDIENTE")
    form.field(split + 75, 308, 50, 22, "Días", "")
    form.field(split + 125, 308, 65, 22, "Moneda", ctx["currency"])
    form.field(split + 190, 308, 86, 22, "Cláusula compra", ctx["incoterm"])


def _draw_merchandise(form: _DINCanvas, payload: dict[str, Any]) -> None:
    ctx = payload["form"]
    lines = payload["lines"]
    line = lines[0] if lines else {}
    levies = line.get("levies") or []
    duty = next((levy for levy in levies if levy.get("code") == "AD_VALOREM"), {})
    iva = next((levy for levy in levies if levy.get("code") == "IVA"), {})
    left = 18.0
    form.section(left, 330, 576, "DESCRIPCIÓN DE MERCANCÍAS")
    form.field(left, 346, 28, 24, "ITEM", "1", value_size=9, value_bold=True, center=True)
    form.field(left + 28, 346, 340, 24, "Nombre", line.get("description"), value_size=7.4)
    form.field(left + 368, 346, 90, 24, "Cód. arancel", line.get("hs_code"), value_bold=True)
    form.field(
        left + 458,
        346,
        118,
        24,
        "Valor CIF item",
        _money(line.get("customs_value")),
        value_bold=True,
    )
    form.field(left, 370, 184, 21, "Atributo 1", f"Factura {payload['invoice']}")
    form.field(left + 184, 370, 184, 21, "Atributo 2", f"Incoterm {ctx['incoterm'] or '-'}")
    form.field(
        left + 368, 370, 90, 21, "Ad valorem", _percentage(line.get("duty_rate")), center=True
    )
    form.field(
        left + 458, 370, 118, 21, "Cód. 223", _money((duty.get("amount") or {}).get("amount"))
    )
    form.field(left, 391, 184, 21, "Atributo 3", f"Cantidad {_display(line.get('quantity'), '-')}")
    form.field(left + 184, 391, 184, 21, "Atributo 4", f"Unidad {_display(line.get('uom'), '-')}")
    form.field(left + 368, 391, 90, 21, "IVA", _percentage(iva.get("rate")), center=True)
    form.field(
        left + 458, 391, 118, 21, "Cód. 178", _money((iva.get("amount") or {}).get("amount"))
    )
    form.field(left, 412, 184, 21, "Atributo 5", _display(line.get("duty_reason")))
    form.field(
        left + 184,
        412,
        184,
        21,
        "Atributo 6",
        f"Cert. origen {_display(ctx['origin_certificate'], 'PENDIENTE')}",
    )
    form.field(left + 368, 412, 90, 21, "Otro 1", "")
    form.field(left + 458, 412, 118, 21, "Valor", "0,00")
    quantity = _decimal(line.get("quantity"))
    unit_fob = _decimal(line.get("fob")) / quantity if quantity else Decimal("0")
    form.field(left, 433, 92, 21, "Ajuste", "")
    form.field(left + 92, 433, 92, 21, "Cantidad mercancía", _money(quantity, 4))
    form.field(left + 184, 433, 92, 21, "Unidad medida", line.get("uom"), center=True)
    form.field(left + 276, 433, 92, 21, "Precio FOB unitario", _money(unit_fob, 6))
    form.field(left + 368, 433, 90, 21, "Otros", "")
    form.field(left + 458, 433, 118, 21, "Valor", "0,00")
    form.field(left, 454, 92, 23, "Cód. arancelario tratado", line.get("hs_code"))
    form.field(left + 92, 454, 92, 23, "Acuerdo comercial", ctx["agreement"])
    extra_note = (
        f"Item principal; {len(lines) - 1} item(s) adicional(es) en hoja de insumos"
        if len(lines) > 1
        else "Item único de la factura"
    )
    form.field(left + 184, 454, 184, 23, "Observaciones", extra_note)
    form.field(left + 368, 454, 90, 23, "Total tributos item", _money(line.get("levy_total")))
    form.field(left + 458, 454, 118, 23, "Valor FOB item", _money(line.get("fob")))
    form.field(left, 477, 184, 23, "Tipo bulto", "BULTOS")
    form.field(left + 184, 477, 92, 23, "Cantidad", ctx["packages"])
    form.field(left + 276, 477, 92, 23, "Total items", ctx["total_items"], center=True)
    form.field(left + 368, 477, 90, 23, "Peso bruto kg", _money(ctx["gross_weight_kg"], 2))
    form.field(left + 458, 477, 118, 23, "Valor CIF", _money(ctx["customs_value"]), value_bold=True)


def _draw_summary_and_observations(form: _DINCanvas, payload: dict[str, Any]) -> None:
    ctx = payload["form"]
    left = 18.0
    form.field(left, 500, 92, 22, "Tipo bulto", "BULTOS", fill=_PALE_BLUE)
    form.field(left + 92, 500, 92, 22, "Cantidad", ctx["packages"])
    form.field(left + 184, 500, 92, 22, "Total hojas", 1 + ctx["annex_pages"])
    form.field(left + 276, 500, 92, 22, "Valor FOB", _money(ctx["fob"]))
    form.section(left + 368, 500, 208, "CUENTAS Y VALORES", height=22)
    form.field(left, 522, 92, 22, "Contenedor", ctx["container_number"])
    form.field(left + 92, 522, 92, 22, "Documento transporte", ctx["bl_number"])
    form.field(left + 184, 522, 92, 22, "Total bultos", ctx["packages"])
    form.field(left + 276, 522, 92, 22, "Flete", _money(ctx["freight"]))
    levy_rows = ctx["levies"][:2]
    for index in range(2):
        levy = levy_rows[index] if index < len(levy_rows) else {}
        top = 522 + index * 22
        code = (
            "223"
            if levy.get("code") == "AD_VALOREM"
            else "178"
            if levy.get("code") == "IVA"
            else ""
        )
        form.field(left + 368, top, 42, 22, "Cód.", code or levy.get("code"), center=True)
        form.field(
            left + 410, top, 166, 22, levy.get("label") or "Tributo", _money(levy.get("amount"))
        )
    form.field(left, 544, 92, 26, "Nave", ctx["vessel"])
    form.field(left + 92, 544, 92, 26, "Viaje", ctx["voyage"])
    form.field(left + 184, 544, 92, 26, "Peso bruto", _money(ctx["gross_weight_kg"], 2))
    form.field(left + 276, 544, 92, 26, "Seguro", _money(ctx["insurance"]))
    if len(levy_rows) < 2:
        form.field(left + 368, 544, 42, 26, "Cód.", "", center=True)
        form.field(left + 410, 544, 166, 26, "Tributo", "")
    form.section(left, 570, 250, "IDENTIFICACIÓN DE BULTOS", height=18)
    form.section(left + 250, 570, 218, "OBSERVACIONES BANCO CENTRAL - S.N.A.", height=18)
    form.section(left + 468, 570, 108, "RESUMEN", height=18)
    form.rect(left, 588, 250, 88)
    form.text(
        left + 8,
        604,
        f"CONTENEDOR: {_display(ctx['container_number'], 'PENDIENTE')}",
        size=7,
        bold=True,
        max_width=234,
    )
    form.text(
        left + 8,
        620,
        f"BULTOS: {_display(ctx['packages'], 'PENDIENTE')} / PESO BRUTO: {_money(ctx['gross_weight_kg'], 2)} KG",
        size=7,
        max_width=234,
    )
    form.text(
        left + 8, 636, f"B/L: {_display(ctx['bl_number'], 'PENDIENTE')}", size=7, max_width=234
    )
    form.rect(left + 250, 588, 218, 88)
    observations = [
        f"CERT. ORIGEN: {_display(ctx['origin_certificate'], 'PENDIENTE')}",
        f"ACUERDO: {_display(ctx['agreement'], 'PENDIENTE')}",
        f"FX: {_display(ctx['fx_source'], 'PENDIENTE')}",
        "DATOS OFICIALES FALTANTES QUEDAN EN BLANCO.",
    ]
    for index, text in enumerate(observations):
        form.text(left + 258, 604 + index * 15, text, size=6.2, max_width=202)
    for index, (label, value) in enumerate(
        [
            ("FOB", ctx["fob"]),
            ("FLETE", ctx["freight"]),
            ("SEGURO", ctx["insurance"]),
            ("CIF", ctx["customs_value"]),
        ]
    ):
        form.field(left + 468, 588 + index * 22, 108, 22, label, _money(value), value_bold=True)


def _draw_authorization_and_tax(form: _DINCanvas, payload: dict[str, Any]) -> None:
    ctx = payload["form"]
    left = 18.0
    form.section(left, 676, 190, "AUTORIZA RETIRO MERCANCÍAS", height=18)
    form.section(left + 190, 676, 200, "OPERACIONES CON PAGO DIFERIDO", height=18)
    form.field(
        left + 390,
        676,
        186,
        28,
        "TOTAL GIRO US$ - Cód. 191",
        _money(ctx["total_payable"]),
        value_bold=True,
    )
    form.field(left, 694, 125, 24, "Tipo de inspección", "PENDIENTE")
    form.field(left + 125, 694, 65, 24, "Resultado", "")
    form.field(left, 718, 125, 24, "Nombre fiscalizador", "")
    form.field(left + 125, 718, 65, 24, "Código", "")
    form.field(left, 742, 190, 77, "Observaciones", "")
    form.field(left + 190, 694, 100, 24, "Fecha vencimiento", "")
    form.field(left + 290, 694, 100, 24, "Valor US$", "")
    for index, code in enumerate(("501", "502", "503", "504")):
        top = 718 + index * 23
        form.field(left + 190, top, 35, 23, "", code, center=True)
        form.field(left + 225, top, 65, 23, "Fecha", "")
        form.field(left + 290, top, 35, 23, "", str(int(code) + 100), center=True)
        form.field(left + 325, top, 65, 23, "Valor", "")
    form.field(left + 390, 704, 93, 24, "TOTAL DIFERIDO - 699", "0,00")
    form.field(left + 483, 704, 93, 24, "CUOTA CONTADO - 199", _money(ctx["total_payable"]))
    form.field(left + 390, 728, 93, 25, "Tipo de cambio - 61", _money(ctx["fx_rate"], 3))
    form.field(
        left + 483,
        728,
        93,
        25,
        "TOTAL CLP - 91",
        _money(ctx["total_payable_settlement"], 0),
        value_bold=True,
    )
    form.section(left + 390, 753, 186, "USO EXCLUSIVO SERVICIO DE TESORERÍAS", height=18)
    form.field(left + 390, 771, 93, 24, "IPC - 92", "")
    form.field(left + 483, 771, 93, 24, "Intereses y multas - 93", "")
    form.field(left + 390, 795, 93, 24, "Total a pagar - 94", "")
    form.field(
        left + 483, 795, 93, 24, "Fecha aceptación", _date(ctx["acceptance_date"]), value_bold=True
    )


def _draw_signatures(form: _DINCanvas, payload: dict[str, Any]) -> None:
    left = 18.0
    labels = [
        "SERVICIO NACIONAL DE ADUANAS / CHILE",
        "FIRMA AUTORIZADA DEL BANCO CENTRAL DE CHILE",
        "FIRMA IMPORTADOR O DESPACHADOR - FECHA",
    ]
    widths = [190, 190, 196]
    x = left
    for label, width in zip(labels, widths):
        form.rect(x, 819, width, 94)
        form.line(x + 20, 891, x + width - 20, 891, width=0.6)
        form.text(x + width / 2, 904, label, size=5.5, align="center", max_width=width - 18)
        x += width
    form.text(
        left,
        928,
        f"{WATERMARK} Documento provisional de preparación y revisión; no acredita presentación ante Aduanas.",
        size=5.6,
        color=_MUTED,
        max_width=576,
    )


def _draw_main_page(
    pdf: canvas.Canvas, payload: dict[str, Any], page_number: int, total: int
) -> None:
    form = _DINCanvas(pdf)
    _draw_header(form, payload, f"HOJA PRINCIPAL {page_number}/{total}")
    _draw_identification(form, payload)
    _draw_transport_and_finance(form, payload)
    _draw_merchandise(form, payload)
    _draw_summary_and_observations(form, payload)
    _draw_authorization_and_tax(form, payload)
    _draw_signatures(form, payload)
    form.watermark()


def _draw_annex_page(
    pdf: canvas.Canvas,
    payload: dict[str, Any],
    annex_lines: list[dict[str, Any]],
    annex_number: int,
    annex_total: int,
    page_number: int,
    total_pages: int,
) -> None:
    form = _DINCanvas(pdf)
    left, width = 18.0, 576.0
    form.rect(left, 14, width, 64, stroke_width=1.2)
    form.text(left + 14, 30, "SERVICIO NACIONAL DE ADUANAS / CHILE", size=9, bold=True)
    form.text(left + 14, 53, "HOJA DE INSUMOS - DECLARACIÓN DE INGRESO", size=16, bold=True)
    form.text(
        left + 14,
        69,
        f"Factura {payload['invoice']} / Anexo {annex_number} de {annex_total}",
        size=7.5,
        bold=True,
    )
    form.text(590, 30, f"PÁGINA {page_number}/{total_pages}", size=6, align="right")
    form.text(590, 49, "NÚMERO: NO ASIGNADO", size=7, bold=True, align="right")
    form.section(left, 88, width, "DETALLE DE ÍTEMS")
    columns = [28, 218, 65, 55, 65, 70, 75]
    labels = ["ITEM", "DESCRIPCIÓN", "CÓD. ARANCEL", "CANT.", "UNIDAD", "FOB US$", "CIF US$"]
    x = left
    for label, column_width in zip(labels, columns):
        form.field(x, 104, column_width, 24, label, "", fill=_PALE_BLUE)
        x += column_width
    row_top = 128.0
    row_height = 29.0
    start_item = 2 + (annex_number - 1) * _ANNEX_LINES_PER_PAGE
    for offset, line in enumerate(annex_lines):
        values = [
            start_item + offset,
            line.get("description"),
            line.get("hs_code"),
            _money(line.get("quantity"), 4),
            line.get("uom"),
            _money(line.get("fob")),
            _money(line.get("customs_value")),
        ]
        x = left
        for value, column_width in zip(values, columns):
            form.field(x, row_top, column_width, row_height, "", value, value_size=6.5)
            x += column_width
        row_top += row_height
    form.field(left, 842, 192, 34, "Factura", payload["invoice"], value_bold=True)
    form.field(
        left + 192,
        842,
        192,
        34,
        "Total items declaración",
        payload["form"]["total_items"],
        value_bold=True,
    )
    form.field(
        left + 384,
        842,
        192,
        34,
        "Valor CIF declaración",
        _money(payload["form"]["customs_value"]),
        value_bold=True,
    )
    form.text(
        left,
        902,
        "Hoja de insumos provisional. Los identificadores y validaciones oficiales permanecen pendientes.",
        size=6,
        color=_MUTED,
        max_width=width,
    )
    form.watermark()


def render_din_pdf(state: dict[str, Any]) -> bytes:
    payloads = din_payload(state)
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=DIN_PAGE_SIZE, pageCompression=1)
    if not payloads:
        form = _DINCanvas(pdf)
        form.section(18, 30, 576, "DECLARACIÓN DE INGRESO")
        form.text(
            306,
            90,
            "NO HAY FACTURAS DISPONIBLES PARA GENERAR DIN",
            size=12,
            bold=True,
            color=colors.HexColor("#b91c1c"),
            align="center",
        )
        form.watermark()
        pdf.showPage()
    else:
        total_pages = sum(1 + payload["form"]["annex_pages"] for payload in payloads)
        page_number = 0
        for payload in payloads:
            page_number += 1
            _draw_main_page(pdf, payload, page_number, total_pages)
            pdf.showPage()
            extra_lines = payload["lines"][1:]
            chunks = [
                extra_lines[index : index + _ANNEX_LINES_PER_PAGE]
                for index in range(0, len(extra_lines), _ANNEX_LINES_PER_PAGE)
            ]
            for annex_number, annex_lines in enumerate(chunks, start=1):
                page_number += 1
                _draw_annex_page(
                    pdf, payload, annex_lines, annex_number, len(chunks), page_number, total_pages
                )
                pdf.showPage()
    pdf.save()
    return buffer.getvalue()
