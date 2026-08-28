"""Render synthetic China-Chile certificates of origin from one shared template."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

CHINA_CHILE_COO_PAGE_SIZE = (216 * mm, 330 * mm)
MAX_ITEMS = 50
INK = colors.HexColor("#111111")
MUTED = colors.HexColor("#4b5563")
DEMO_RED = colors.HexColor("#b91c1c")


@dataclass(frozen=True)
class OriginItemData:
    marks: str
    packages: str
    description: str
    hs_code: str
    origin_criterion: str
    net_weight_or_quantity: Decimal
    unit: str
    invoice_number: str
    invoice_date: str


@dataclass(frozen=True)
class OriginCertificateData:
    certificate_number: str
    exporter_name: str
    exporter_address: str
    producer: str
    consignee_name: str
    consignee_address: str
    issued_in: str
    departure_date: str
    transport_number: str
    port_of_loading: str
    port_of_discharge: str
    remarks: str
    issue_place: str
    issue_date: str
    issuing_authority: str
    items: tuple[OriginItemData, ...]
    dispatch_reference: str = ""


def _wrap(text: str, font: str, size: float, width: float) -> list[str]:
    words = str(text).split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _fit_line(text: str, font: str, maximum: float, width: float, minimum: float = 3.0) -> float:
    size = maximum
    while size > minimum and stringWidth(str(text), font, size) > width:
        size -= 0.2
    return max(size, minimum)


def _top_lines(
    pdf: canvas.Canvas,
    x: float,
    top: float,
    text: str,
    *,
    width: float,
    font: str = "Helvetica",
    size: float = 7.0,
    leading: float | None = None,
    max_lines: int | None = None,
    color=INK,
) -> None:
    leading = leading or size * 1.2
    lines = _wrap(text, font, size, width)
    if max_lines is not None:
        lines = lines[:max_lines]
    pdf.setFillColor(color)
    pdf.setFont(font, size)
    for index, line in enumerate(lines):
        pdf.drawString(x, top - size - index * leading, line)


def _box(pdf: canvas.Canvas, x: float, bottom: float, width: float, height: float) -> None:
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(0.65)
    pdf.rect(x, bottom, width, height, fill=0, stroke=1)


def _label(pdf: canvas.Canvas, x: float, top: float, text: str, width: float) -> None:
    _top_lines(
        pdf,
        x,
        top,
        text,
        width=width,
        font="Helvetica",
        size=6.8,
        leading=8.2,
        max_lines=2,
    )


def _footer(pdf: canvas.Canvas, width: float, data: OriginCertificateData) -> None:
    suffix = f" - {data.dispatch_reference}" if data.dispatch_reference else ""
    text = f"SYNTHETIC DEMO - NOT VALID FOR CUSTOMS OR COMMERCIAL USE{suffix}"
    pdf.setFillColor(DEMO_RED)
    pdf.setFont("Helvetica-Bold", 5.6)
    pdf.drawCentredString(width / 2, 13, text)


def _stamp(pdf: canvas.Canvas, x: float, y: float) -> None:
    pdf.saveState()
    pdf.translate(x, y)
    pdf.rotate(-7)
    pdf.setStrokeColor(DEMO_RED)
    pdf.setFillColor(DEMO_RED)
    pdf.setLineWidth(1.2)
    pdf.circle(0, 0, 29, stroke=1, fill=0)
    pdf.circle(0, 0, 24, stroke=1, fill=0)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawCentredString(0, 3, "SYNTHETIC")
    pdf.setFont("Helvetica", 5.5)
    pdf.drawCentredString(0, -7, "TEST ONLY")
    pdf.restoreState()


def _draw_identity_and_route(pdf: canvas.Canvas, data: OriginCertificateData) -> None:
    left = 25.0
    right = CHINA_CHILE_COO_PAGE_SIZE[0] - 25.0
    split = 310.0
    left_width = split - left
    right_width = right - split

    # Left column, Boxes 1-4.
    rows = [(780, 870), (690, 780), (620, 690), (510, 620)]
    for bottom, top in rows:
        _box(pdf, left, bottom, left_width, top - bottom)
    _label(pdf, left + 5, 866, "1. Exporter's name, address, country:", left_width - 10)
    _top_lines(
        pdf,
        left + 9,
        844,
        data.exporter_name,
        width=left_width - 18,
        font="Helvetica-Bold",
        size=7.5,
        max_lines=2,
    )
    _top_lines(
        pdf,
        left + 9,
        820,
        data.exporter_address,
        width=left_width - 18,
        size=6.4,
        leading=7.5,
        max_lines=3,
    )

    _label(pdf, left + 5, 776, "2. Producer's name and address, country:", left_width - 10)
    _top_lines(
        pdf,
        left + 9,
        751,
        data.producer,
        width=left_width - 18,
        font="Helvetica-Bold",
        size=7.4,
        leading=8.5,
        max_lines=5,
    )

    _label(pdf, left + 5, 686, "3. Consignee's name, address, country:", left_width - 10)
    _top_lines(
        pdf,
        left + 9,
        665,
        data.consignee_name,
        width=left_width - 18,
        font="Helvetica-Bold",
        size=7.3,
        max_lines=2,
    )
    _top_lines(
        pdf,
        left + 9,
        644,
        data.consignee_address,
        width=left_width - 18,
        size=6.2,
        leading=7.3,
        max_lines=2,
    )

    _label(pdf, left + 5, 616, "4. Means of transport and route (as far as known)", left_width - 10)
    route_lines = [
        f"Departure Date: {data.departure_date}",
        f"Vessel / Flight / Train / Vehicle No.: {data.transport_number}",
        f"Port of loading: {data.port_of_loading}",
        f"Port of discharge: {data.port_of_discharge}",
    ]
    pdf.setFont("Helvetica", 6.6)
    pdf.setFillColor(INK)
    for index, line in enumerate(route_lines):
        pdf.drawString(left + 12, 590 - index * 18, line)

    # Right column, certificate identification, official use, and Box 5.
    for bottom, top in ((730, 870), (630, 730), (510, 630)):
        _box(pdf, split, bottom, right_width, top - bottom)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(split + 12, 850, f"Certificate No.: {data.certificate_number}")
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawCentredString(split + right_width / 2, 808, "CERTIFICATE OF ORIGIN")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawCentredString(split + right_width / 2, 777, "Form for China-Chile FTA")
    pdf.setFont("Helvetica", 7.2)
    pdf.drawString(split + 25, 749, f"Issued in: {data.issued_in}")
    pdf.drawRightString(right - 5, 735, "(see Instruction overleaf)")

    _label(pdf, split + 5, 726, "For official Use Only", right_width - 10)
    _top_lines(
        pdf,
        split + 10,
        700,
        "SYNTHETIC FIXTURE - NO OFFICIAL ENTRY",
        width=right_width - 20,
        font="Helvetica-Bold",
        size=7,
        color=DEMO_RED,
        max_lines=2,
    )

    _label(pdf, split + 5, 626, "5. Remarks", right_width - 10)
    _top_lines(
        pdf,
        split + 10,
        603,
        data.remarks,
        width=right_width - 20,
        size=6.6,
        leading=8,
        max_lines=10,
    )


def _draw_items(pdf: canvas.Canvas, data: OriginCertificateData) -> None:
    left = 25.0
    bottom = 205.0
    top = 510.0
    widths = (34.0, 48.0, 249.0, 58.0, 50.0, 67.0, 56.0)
    headers = (
        "6. Item number",
        "7. Marks and packages No.",
        "8. Number and kind of packages; description of goods",
        "9. HS code (Six digit code)",
        "10. Origin criterion",
        "11. Net weight or quantity, with unit of measurement",
        "12. Number(s) and date(s) of invoice(s)",
    )
    header_height = 44.0
    data_height = top - bottom - header_height
    row_height = min(42.0, data_height / max(len(data.items), 1))
    table_width = sum(widths)
    _box(pdf, left, bottom, table_width, top - bottom)

    x = left
    for width, header in zip(widths, headers):
        pdf.line(x, bottom, x, top)
        _top_lines(
            pdf,
            x + 3,
            top - 3,
            header,
            width=width - 6,
            font="Helvetica",
            size=5.4,
            leading=6.2,
            max_lines=6,
        )
        x += width
    pdf.line(left + table_width, bottom, left + table_width, top)
    pdf.line(left, top - header_height, left + table_width, top - header_height)

    compact = row_height < 10
    font_size = 3.2 if compact else 5.5 if row_height < 22 else 6.2
    line_height = font_size * 1.12
    row_top = top - header_height
    for index, item in enumerate(data.items, start=1):
        row_bottom = row_top - row_height
        if row_bottom < bottom - 0.1:
            raise ValueError("certificate item rows exceed the available form area")
        pdf.setStrokeColor(colors.HexColor("#555555"))
        pdf.setLineWidth(0.35)
        pdf.line(left, row_bottom, left + table_width, row_bottom)
        description = f"{item.packages}; {item.description}"
        if index == len(data.items):
            description += " ***"
        values = (
            str(index),
            item.marks,
            description,
            item.hs_code,
            item.origin_criterion,
            f"{item.net_weight_or_quantity:,.1f} {item.unit}",
            f"{item.invoice_number} / {item.invoice_date}",
        )
        x = left
        for column, (width, value) in enumerate(zip(widths, values)):
            if compact:
                size = _fit_line(value, "Helvetica", font_size, width - 4, 2.5)
                pdf.setFont("Helvetica", size)
                pdf.setFillColor(INK)
                if column in {0, 3, 4, 5}:
                    pdf.drawCentredString(
                        x + width / 2, row_bottom + max(1.4, (row_height - size) / 2), value
                    )
                else:
                    pdf.drawString(x + 2, row_bottom + max(1.4, (row_height - size) / 2), value)
            else:
                lines = _wrap(value, "Helvetica", font_size, width - 5)
                max_lines = max(1, int((row_height - 3) / line_height))
                lines = lines[:max_lines]
                pdf.setFont("Helvetica", font_size)
                pdf.setFillColor(INK)
                for line_no, line in enumerate(lines):
                    y = row_top - font_size - 2 - line_no * line_height
                    if column in {0, 3, 4, 5}:
                        pdf.drawCentredString(x + width / 2, y, line)
                    else:
                        pdf.drawString(x + 2, y, line)
            x += width
        row_top = row_bottom


def _draw_declarations(pdf: canvas.Canvas, data: OriginCertificateData) -> None:
    left = 25.0
    right = CHINA_CHILE_COO_PAGE_SIZE[0] - 25.0
    split = 282.0
    bottom = 28.0
    top = 205.0
    _box(pdf, left, bottom, split - left, top - bottom)
    _box(pdf, split, bottom, right - split, top - bottom)

    _label(pdf, left + 5, 201, "13. Declaration by the exporter or producer", split - left - 10)
    declaration = (
        "The undersigned hereby declares that the above details and statement are correct, "
        f"that all the goods were produced in {data.issued_in} and that they comply with the "
        "origin requirements specified in the China-Chile FTA for the goods exported to CHILE."
    )
    _top_lines(
        pdf,
        left + 6,
        181,
        declaration,
        width=split - left - 12,
        size=6.2,
        leading=7.4,
        max_lines=8,
    )
    pdf.setStrokeColor(INK)
    pdf.line(left + 35, 83, split - 35, 83)
    pdf.setFont("Helvetica", 6.2)
    pdf.setFillColor(INK)
    pdf.drawCentredString((left + split) / 2, 69, f"{data.issue_place}, {data.issue_date}")
    pdf.drawString(left + 6, 40, "Place and date, signature of authorised signatory")

    _label(pdf, split + 5, 201, "14. Certification", right - split - 10)
    certification = (
        "On the basis of control carried out, it is hereby certified that the declaration "
        "made by the exporter or producer is correct."
    )
    _top_lines(
        pdf,
        split + 6,
        181,
        certification,
        width=right - split - 12,
        size=6.2,
        leading=7.4,
        max_lines=6,
    )
    _top_lines(
        pdf,
        split + 6,
        130,
        f"Authorised body: {data.issuing_authority}",
        width=right - split - 88,
        size=5.8,
        leading=6.8,
        max_lines=4,
    )
    _stamp(pdf, right - 45, 112)
    pdf.line(split + 40, 83, right - 40, 83)
    pdf.setFont("Helvetica", 6.2)
    pdf.drawCentredString((split + right) / 2, 69, f"{data.issue_place}, {data.issue_date}")
    pdf.drawString(split + 6, 40, "Place and date, signature and stamp of authorised body")


def _draw_form_page(pdf: canvas.Canvas, data: OriginCertificateData) -> None:
    width, height = CHINA_CHILE_COO_PAGE_SIZE
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, 902, "Certificate of Origin")
    _draw_identity_and_route(pdf, data)
    _draw_items(pdf, data)
    _draw_declarations(pdf, data)
    _footer(pdf, width, data)


def _instruction(pdf: canvas.Canvas, box: str, text: str, top: float, width: float) -> float:
    pdf.setFont("Times-Bold", 8)
    pdf.setFillColor(INK)
    pdf.drawString(28, top, box)
    content_x = 100 if box == "Certificate No.:" else 78
    lines = _wrap(text, "Times-Roman", 7.6, width - content_x - 28)
    pdf.setFont("Times-Roman", 7.6)
    for index, line in enumerate(lines):
        pdf.drawString(content_x, top - index * 9, line)
    return top - max(18, len(lines) * 9 + 6)


def _draw_instruction_page(pdf: canvas.Canvas, data: OriginCertificateData) -> None:
    width, height = CHINA_CHILE_COO_PAGE_SIZE
    pdf.setFillColor(INK)
    pdf.setFont("Times-Bold", 17)
    pdf.drawCentredString(width / 2, 902, "Overleaf Instruction")
    top = 870.0
    top = _instruction(
        pdf,
        "Certificate No.:",
        "Unique serial number of Certificate of Origin assigned by the authorised body.",
        top,
        width,
    )
    instructions = (
        (
            "Box 1:",
            "State the full legal name and address, including country, of the exporter in China or Chile.",
        ),
        (
            "Box 2:",
            "State the full legal name and address, including country, of the producer. List additional producers when applicable. Confidential information may be stated as AVAILABLE UPON REQUEST. If producer and exporter are the same, state SAME.",
        ),
        (
            "Box 3:",
            "State the full legal name and address, including country, of the consignee in China or Chile.",
        ),
        (
            "Box 4:",
            "Complete the means of transport and route, including departure date, transport number, port of loading and port of discharge, as far as known.",
        ),
        (
            "Box 5:",
            "State the order number, Letter of Credit number or other information. Identify a non-Party invoicing operator when applicable. For retrospective issuance state ISSUED RETROACTIVELY. For a certified copy identify the original certificate number and date.",
        ),
        ("Box 6:", "State the item number. Fifty is the maximum."),
        (
            "Box 7:",
            "State shipping marks and package numbers when they exist; otherwise state NO MARKS AND NUMBERS (N/M).",
        ),
        (
            "Box 8:",
            "State the number and kind of packages and give a description detailed enough for Customs identification and reconciliation to the invoice and HS description. State IN BULK when goods are not packed. End the description with three stars or a finishing slash.",
        ),
        (
            "Box 9:",
            "Identify the six-digit HS tariff classification for each good described in Box 8.",
        ),
        (
            "Box 10:",
            "State the origin criterion supporting preferential tariff treatment: WO, WP, RVC or PSR, as applicable.",
        ),
        ("Box 11:", "Show net weight or quantity with its unit of measurement."),
        ("Box 12:", "Show the number and date of each relevant invoice."),
        (
            "Box 13:",
            "Complete, sign and date this field by the exporter or producer applying for the certificate.",
        ),
        ("Box 14:", "Complete, sign, date and stamp this field by the authorised body."),
    )
    for box, text in instructions:
        top = _instruction(pdf, box, text, top, width)

    table_top = top - 5
    table_left = 78.0
    table_width = width - 106.0
    row_height = 21.0
    criteria = (
        ("Good wholly obtained", "WO"),
        ("Produced entirely from originating materials", "WP"),
        ("General rule based on regional value content", "RVC"),
        ("Product-specific rule", "PSR"),
    )
    _box(pdf, table_left, table_top - row_height * 5, table_width, row_height * 5)
    split = table_left + table_width - 90
    pdf.line(split, table_top - row_height * 5, split, table_top)
    for index in range(1, 5):
        y = table_top - row_height * index
        pdf.line(table_left, y, table_left + table_width, y)
    pdf.setFont("Times-Bold", 7.5)
    pdf.drawString(table_left + 5, table_top - 14, "Origin criteria")
    pdf.drawCentredString(split + 45, table_top - 14, "Insert in Box 10")
    pdf.setFont("Times-Roman", 7.3)
    for index, (description, code) in enumerate(criteria, start=1):
        y = table_top - row_height * index - 14
        pdf.drawString(table_left + 5, y, description)
        pdf.drawCentredString(split + 45, y, code)
    _footer(pdf, width, data)


def render_origin_certificate(path: Path, data: OriginCertificateData) -> None:
    if not data.items:
        raise ValueError("certificate must contain at least one item")
    if len(data.items) > MAX_ITEMS:
        raise ValueError(f"certificate supports at most {MAX_ITEMS} items")
    invalid = sorted({item.origin_criterion for item in data.items} - {"WO", "WP", "RVC", "PSR"})
    if invalid:
        raise ValueError(f"unsupported origin criteria: {', '.join(invalid)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=CHINA_CHILE_COO_PAGE_SIZE, pageCompression=1)
    _draw_form_page(pdf, data)
    pdf.showPage()
    _draw_instruction_page(pdf, data)
    pdf.showPage()
    pdf.save()
