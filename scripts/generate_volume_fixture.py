"""Generate a coherent high-volume synthetic dispatch for performance demonstrations."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from origin_certificate_fixture import (
    OriginCertificateData,
    OriginItemData,
    render_origin_certificate,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "fixtures" / "scenario_C_volume"
MONEY = Decimal("0.01")


def money(value: Decimal) -> str:
    return f"{value.quantize(MONEY, rounding=ROUND_HALF_UP):,.2f}"


NAVY = colors.HexColor("#17365D")
TEAL = colors.HexColor("#008F83")
PALE = colors.HexColor("#EAF4F5")
INK = colors.HexColor("#172B4D")
MUTED = colors.HexColor("#52677D")
RED = colors.HexColor("#B42318")
GRID = colors.HexColor("#8091A5")


def clean(text: object) -> str:
    return str(text).replace("—", "-").replace("–", "-").replace("→", "to")


def draw_text(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    text: object,
    *,
    size: float = 8,
    bold: bool = False,
    color=INK,
) -> None:
    pdf.setFillColor(color)
    pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    pdf.drawString(x, y, clean(text))


def draw_right(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    text: object,
    *,
    size: float = 8,
    bold: bool = False,
    color=INK,
) -> None:
    pdf.setFillColor(color)
    pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    pdf.drawRightString(x, y, clean(text))


def box(pdf: canvas.Canvas, x: float, y: float, width: float, height: float, *, fill=None) -> None:
    if fill is not None:
        pdf.setFillColor(fill)
    pdf.setStrokeColor(GRID)
    pdf.setLineWidth(0.6)
    pdf.rect(x, y, width, height, fill=1 if fill is not None else 0, stroke=1)


def synthetic_footer(pdf: canvas.Canvas, width: float, label: str) -> None:
    pdf.setFillColor(colors.HexColor("#FFF1F0"))
    pdf.rect(0, 0, width, 24, fill=1, stroke=0)
    pdf.setFillColor(RED)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawCentredString(width / 2, 9, clean(f"SYNTHETIC DEMO - {label} - NOT A REAL TRANSACTION"))


def company_header(pdf: canvas.Canvas, width: float, title: str, subtitle: str) -> None:
    pdf.setFillColor(NAVY)
    pdf.rect(0, A4[1] - 86, width, 86, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 17)
    pdf.drawString(34, A4[1] - 38, "NINGBO HOMEWARE")
    pdf.setFont("Helvetica", 8)
    pdf.drawString(34, A4[1] - 56, subtitle)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawRightString(width - 34, A4[1] - 43, title)


def write_instruction(
    path: Path,
    dispatch: str,
    reference: str,
    bl: str,
    invoice_numbers: list[str],
    freight: Decimal,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    width, height = A4
    pdf.setFillColor(NAVY)
    pdf.rect(0, height - 86, width, 86, fill=1, stroke=0)
    draw_text(
        pdf,
        34,
        height - 37,
        "FALABELLA RETAIL S.A. INSTRUCCIÓN DE DESPACHO",
        size=15,
        bold=True,
        color=colors.white,
    )
    draw_text(
        pdf, 34, height - 57, "Orden de trabajo para agencia de aduanas", size=8, color=colors.white
    )
    box(pdf, 34, height - 154, width - 68, 50, fill=PALE)
    draw_text(pdf, 48, height - 126, f"N° Despacho {dispatch}", size=12, bold=True)
    draw_text(pdf, 250, height - 126, f"Referencia {reference}", size=12, bold=True)

    details = [
        "Agencia de Aduanas AGENCIA DE ADUANAS ANDES LTDA. - RUT 78.905.410-3",
        "Importador / Consignatario FALABELLA RETAIL S.A. - RUT 77.261.280-K",
        "Proveedor NINGBO HOMEWARE MANUFACTURING CO., LTD.",
        f"Conocimiento de embarque {bl} - OCEANLINK SHIPPING CO., LTD.",
        "Nave / Viaje OCEAN PACIFIC V.2628E",
        "Puerto embarque / desembarque SHANGHAI, CHINA to VALPARAISO, CHILE",
        "Fecha embarque / ETA 2026-08-28 / 2026-10-05",
    ]
    draw_text(pdf, 34, height - 184, "DATOS DEL EMBARQUE", size=9, bold=True, color=TEAL)
    y = height - 207
    for line in details:
        box(pdf, 34, y - 7, width - 68, 19, fill=colors.white)
        draw_text(pdf, 43, y, line, size=7.5)
        y -= 19

    draw_text(pdf, 34, y - 3, "FACTURAS COMERCIALES", size=9, bold=True, color=TEAL)
    y -= 25
    for start in range(0, len(invoice_numbers), 8):
        label = "Facturas comerciales" if start == 0 else "Facturas comerciales (continuación)"
        line = label + " " + " ".join(invoice_numbers[start : start + 8])
        box(pdf, 34, y - 7, width - 68, 19, fill=colors.white)
        draw_text(pdf, 43, y, line, size=6.8)
        y -= 19

    terms = [
        "Cláusula de compra FOB SHANGHAI",
        f"Flete marítimo (según B/L) USD {money(freight)} - PREPAID",
        "Seguro Póliza flotante FL-2026-0088 - Compañía de Seguros Generales Cordillera S.A.",
        "Régimen solicitado Importación para consumo - Declaración de Ingreso (DIN)",
        "Acuerdo comercial invocado TLC Chile-China - certificado de origen C26CL0124001",
        "Prorrateo de gastos Flete y seguro a prorratear por valor de factura",
    ]
    draw_text(pdf, 34, y - 3, "INSTRUCCIONES OPERATIVAS", size=9, bold=True, color=TEAL)
    y -= 25
    box(pdf, 34, y - 104, width - 68, 116, fill=colors.white)
    for line in terms:
        draw_text(pdf, 45, y, line, size=7.4)
        y -= 17
    draw_text(pdf, 396, 53, "Firma autorizada", size=7, color=MUTED)
    pdf.setStrokeColor(GRID)
    pdf.line(370, 62, width - 34, 62)
    synthetic_footer(pdf, width, "45 PDF VOLUME PACKET")
    pdf.save()


def write_bill_of_lading(
    path: Path,
    bl: str,
    container: str,
    invoice_numbers: list[str],
    total_cartons: int,
    total_gross: Decimal,
    measurement: Decimal,
    freight: Decimal,
    total_fob: Decimal,
) -> None:
    page_size = landscape(A4)
    pdf = canvas.Canvas(str(path), pagesize=page_size, pageCompression=1)
    width, height = page_size
    pdf.setFillColor(colors.HexColor("#147DAA"))
    pdf.rect(0, height - 62, width, 62, fill=1, stroke=0)
    draw_text(
        pdf,
        28,
        height - 31,
        "OCEANLINK SHIPPING CO., LTD. BILL OF LADING",
        size=15,
        bold=True,
        color=colors.white,
    )
    draw_text(pdf, 28, height - 47, "Port-to-Port / Negotiable", size=7, color=colors.white)
    box(pdf, width - 210, height - 54, 180, 38, fill=colors.white)
    draw_text(pdf, width - 200, height - 31, "B/L Number", size=7, bold=True)
    draw_text(pdf, width - 200, height - 46, bl, size=10, bold=True)

    y = height - 86
    box(pdf, 28, y - 70, 380, 82, fill=colors.white)
    draw_text(pdf, 38, y, "SHIPPER / EXPORTER B/L NO. / BOOKING NO.", size=7, bold=True)
    draw_text(pdf, 38, y - 18, f"NINGBO HOMEWARE MANUFACTURING CO., LTD. {bl} / BK2602288", size=8)
    draw_text(pdf, 38, y - 36, "88 Harbor Industrial Road, Ningbo, Zhejiang, China", size=7)
    draw_text(pdf, 38, y - 53, "Export contact: shipping@synthetic-demo.invalid", size=7)
    box(pdf, 408, y - 70, width - 436, 82, fill=colors.white)
    draw_text(pdf, 418, y, "CONSIGNEE (OR ORDER) NOTIFY PARTY", size=7, bold=True)
    draw_text(pdf, 418, y - 18, "CONSIGNEE: FALABELLA RETAIL S.A.", size=8)
    draw_text(
        pdf, 418, y - 36, "NOTIFY PARTY: AGENCIA DE ADUANAS ANDES LTDA. - Santiago, Chile", size=7
    )

    y -= 91
    box(pdf, 28, y - 56, width - 56, 68, fill=PALE)
    draw_text(pdf, 38, y, "VESSEL / VOYAGE PLACE OF RECEIPT", size=7, bold=True)
    draw_text(pdf, 38, y - 17, "OCEAN PACIFIC V.2628E SHANGHAI, CHINA", size=8)
    draw_text(pdf, 38, y - 37, "PORT OF LOADING PORT OF DISCHARGE", size=7, bold=True)
    draw_text(
        pdf,
        270,
        y - 37,
        "SHANGHAI, CHINA (ETD 2026-08-28) VALPARAISO, CHILE (ETA 2026-10-05)",
        size=7.2,
    )

    y -= 79
    box(pdf, 28, y - 68, width - 56, 80, fill=colors.white)
    draw_text(
        pdf,
        38,
        y,
        "Container No. / Seal No. No. of Pkgs Description of Goods Gross Weight Measurement",
        size=7,
        bold=True,
    )
    draw_text(
        pdf,
        38,
        y - 20,
        f"{container} / 40'HC {total_cartons} SAID TO CONTAIN: {total_gross:,.1f} {measurement}",
        size=10,
        bold=True,
    )
    draw_text(
        pdf,
        38,
        y - 42,
        "HOUSEHOLD TEXTILES, TABLEWARE, LIGHTING, AUDIO EQUIPMENT AND CABLE",
        size=7.5,
    )
    draw_text(pdf, 590, y - 42, "FREIGHT PREPAID", size=8, bold=True, color=TEAL)

    y -= 92
    draw_text(pdf, 28, y, "INVOICE NOS.:", size=7, bold=True)
    y -= 16
    for start in range(0, len(invoice_numbers), 10):
        draw_text(pdf, 38, y, " ".join(invoice_numbers[start : start + 10]), size=6.8)
        y -= 15

    box(pdf, 28, 43, width - 56, 69, fill=colors.white)
    draw_text(pdf, 38, 91, "SHIPPED ON BOARD 2026-08-28", size=7.5, bold=True)
    draw_text(pdf, 38, 73, "INCOTERM: FOB SHANGHAI", size=7.5)
    draw_text(pdf, 310, 91, f"TOTAL FREIGHT THIS B/L USD {money(freight)}", size=8, bold=True)
    draw_text(
        pdf, 310, 73, f"TOTAL DECLARED VALUE THIS B/L USD {money(total_fob)}", size=8, bold=True
    )
    draw_text(pdf, 640, 73, "Signed for the carrier", size=7, color=MUTED)
    synthetic_footer(pdf, width, "SAMPLE OCEAN BILL OF LADING")
    pdf.save()


def write_invoice(path: Path, item: dict, index: int, bl: str) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    width, height = A4
    company_header(
        pdf, width, "COMMERCIAL INVOICE", "88 Harbor Industrial Road - Ningbo, Zhejiang, China"
    )
    draw_text(
        pdf,
        34,
        height - 102,
        "NINGBO HOMEWARE MANUFACTURING CO., LTD. COMMERCIAL INVOICE",
        size=7,
        color=MUTED,
    )

    box(pdf, 34, height - 220, 255, 100, fill=colors.white)
    draw_text(pdf, 45, height - 138, "SOLD TO / CONSIGNEE SHIPMENT", size=8, bold=True, color=TEAL)
    draw_text(
        pdf, 45, height - 158, "FALABELLA RETAIL S.A. Vessel: OCEAN PACIFIC V.2628E", size=7.5
    )
    draw_text(pdf, 45, height - 176, "Rosario Norte 660, Las Condes, Santiago, Chile", size=7)
    draw_text(pdf, 45, height - 194, f"B/L No.: {bl}", size=7.5)

    box(pdf, 306, height - 220, width - 340, 100, fill=PALE)
    draw_text(pdf, 318, height - 138, f"Invoice No. {item['number']}", size=10, bold=True)
    draw_text(pdf, 318, height - 158, "Date 2026-08-20", size=8)
    draw_text(pdf, 318, height - 176, "Currency: USD", size=8)
    draw_text(pdf, 318, height - 194, "Purchase order: PO-26-0817", size=8)

    table_top = height - 252
    columns = [34, 58, 286, 352, 404, 464, width - 34]
    box(pdf, 34, table_top - 28, width - 68, 28, fill=NAVY)
    headers = ["ITEM", "DESCRIPTION OF GOODS", "HS CODE", "QTY/UOM", "UNIT PRICE", "AMOUNT USD"]
    for x, label in zip(columns[:-1], headers):
        draw_text(pdf, x + 4, table_top - 18, label, size=6.5, bold=True, color=colors.white)
    row_bottom = table_top - 88
    box(pdf, 34, row_bottom, width - 68, 60, fill=colors.white)
    draw_text(pdf, 42, table_top - 52, "1", size=7.2)
    draw_text(pdf, 62, table_top - 52, item["description"], size=7.2)
    draw_text(pdf, 292, table_top - 52, item["hs_code"], size=7.2)
    draw_right(pdf, 378, table_top - 52, f"{item['quantity']:,.0f}", size=7.2)
    draw_text(pdf, 384, table_top - 52, "PCS", size=7.2)
    draw_right(pdf, 459, table_top - 52, f"{item['unit_price']:.2f}", size=7.2)
    draw_right(pdf, width - 42, table_top - 52, money(item["total"]), size=7.2)
    for x in columns[1:-1]:
        pdf.setStrokeColor(GRID)
        pdf.line(x, row_bottom, x, table_top)

    totals_y = row_bottom - 88
    box(pdf, 318, totals_y, width - 352, 72, fill=PALE)
    draw_right(
        pdf,
        width - 46,
        totals_y + 48,
        f"TOTAL FOB SHANGHAI USD {money(item['total'])}",
        size=10,
        bold=True,
    )
    draw_right(
        pdf,
        width - 46,
        totals_y + 27,
        f"Amount in words: US dollars {money(item['total'])}",
        size=7,
    )

    details_y = totals_y - 122
    box(pdf, 34, details_y, width - 68, 104, fill=colors.white)
    draw_text(
        pdf, 45, details_y + 84, "SHIPPING AND PACKING DETAILS", size=8, bold=True, color=TEAL
    )
    draw_text(
        pdf,
        45,
        details_y + 63,
        f"Incoterms 2020: FOB SHANGHAI Packages: {item['cartons']} CTN",
        size=8,
    )
    draw_text(pdf, 45, details_y + 44, f"Gross weight: {item['gross']:,.1f} KGS", size=8)
    draw_text(pdf, 258, details_y + 44, f"Net weight: {item['net']:,.1f} KGS", size=8)
    draw_text(pdf, 45, details_y + 25, "Country of Origin: CHINA", size=8)
    draw_text(
        pdf,
        258,
        details_y + 25,
        f"Container: OLSU6622881 - Invoice sequence {index:02d}/40",
        size=8,
    )

    draw_text(
        pdf,
        34,
        74,
        "We certify that the prices shown are true and correct for this synthetic demonstration.",
        size=7,
        color=MUTED,
    )
    pdf.setStrokeColor(GRID)
    pdf.line(358, 74, width - 34, 74)
    draw_text(pdf, 412, 61, "Authorized signature", size=7, color=MUTED)
    synthetic_footer(pdf, width, "SAMPLE COMMERCIAL INVOICE")
    pdf.save()


def _packing_header(
    pdf: canvas.Canvas, width: float, height: float, bl: str, container: str, page_no: int
) -> float:
    company_header(pdf, width, "PACKING LIST", "Packing and logistics department")
    draw_text(
        pdf,
        34,
        height - 102,
        "NINGBO HOMEWARE MANUFACTURING CO., LTD. PACKING LIST",
        size=7,
        color=MUTED,
    )
    box(pdf, 34, height - 196, 255, 76, fill=colors.white)
    draw_text(pdf, 45, height - 138, "CONSIGNEE SHIPMENT", size=8, bold=True, color=TEAL)
    draw_text(pdf, 45, height - 158, f"FALABELLA RETAIL S.A. B/L: {bl}", size=8)
    draw_text(pdf, 45, height - 178, "Valparaiso, Chile", size=7)
    box(pdf, 306, height - 196, width - 340, 76, fill=PALE)
    draw_text(pdf, 318, height - 138, f"P/L No. PL-{bl}", size=8, bold=True)
    draw_text(pdf, 318, height - 156, "Date 2026-08-21", size=8)
    draw_text(pdf, 318, height - 174, f"Container / Seal: {container} / 40'HC / CN0622881", size=7)
    draw_right(pdf, width - 34, 31, f"Page {page_no} of 2", size=7, color=MUTED)
    return height - 222


def write_packing_list(
    path: Path,
    invoices: list[dict],
    bl: str,
    container: str,
    total_cartons: int,
    total_gross: Decimal,
    total_net: Decimal,
    measurement: Decimal,
) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    width, height = A4
    for page_no, page_items in enumerate((invoices[:20], invoices[20:]), start=1):
        table_top = _packing_header(pdf, width, height, bl, container, page_no)
        box(pdf, 34, table_top - 24, width - 68, 24, fill=NAVY)
        draw_text(
            pdf,
            39,
            table_top - 16,
            "CARTON NOS. / INVOICE / DESCRIPTION / QTY / CARTONS / GROSS KG / NET KG",
            size=6.4,
            bold=True,
            color=colors.white,
        )
        y = table_top - 42
        for item in page_items:
            box(
                pdf,
                34,
                y - 8,
                width - 68,
                19,
                fill=colors.white if item["number"][-2:] != "10" else PALE,
            )
            row = (
                f"{item['first_carton']} - {item['last_carton']} {item['number']} "
                f"{item['description']} {item['quantity']:,.0f} PCS {item['cartons']} "
                f"{item['gross']:,.1f} {item['net']:,.1f}"
            )
            draw_text(pdf, 40, y, row, size=6.2)
            y -= 20
        if page_no == 2:
            y -= 4
            box(pdf, 34, y - 46, width - 68, 56, fill=PALE)
            draw_text(
                pdf,
                44,
                y - 4,
                f"TOTAL {total_cartons} {total_gross:,.1f} {total_net:,.1f}",
                size=9,
                bold=True,
            )
            draw_text(
                pdf,
                44,
                y - 24,
                f"Total measurement: {measurement} CBM | Total packages: {total_cartons} CTN",
                size=8,
            )
        synthetic_footer(pdf, width, "SAMPLE PACKING LIST")
        if page_no == 1:
            pdf.showPage()
    pdf.save()


def write_insurance(
    path: Path,
    bl: str,
    invoice_numbers: list[str],
    total_cartons: int,
    container: str,
    insured: Decimal,
    premium: Decimal,
) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    width, height = A4
    pdf.setFillColor(colors.HexColor("#1F4B99"))
    pdf.rect(0, height - 78, width, 78, fill=1, stroke=0)
    draw_text(pdf, 34, height - 34, "CORDILLERA SEGUROS", size=17, bold=True, color=colors.white)
    draw_text(
        pdf, 34, height - 54, "Protección para carga internacional", size=8, color=colors.white
    )
    draw_right(
        pdf,
        width - 34,
        height - 42,
        "CERTIFICADO DE SEGURO",
        size=16,
        bold=True,
        color=colors.white,
    )
    draw_text(
        pdf,
        34,
        height - 96,
        "Compañía de Seguros Generales Cordillera S.A. CERTIFICADO DE SEGURO",
        size=7,
        color=MUTED,
    )
    draw_text(pdf, 34, height - 112, "MARINE CARGO INSURANCE CERTIFICATE", size=9, bold=True)

    box(pdf, 34, height - 210, width - 68, 78, fill=PALE)
    draw_text(pdf, 46, height - 154, "Certificado N° MC-2026-06288", size=10, bold=True)
    draw_text(pdf, 46, height - 176, "ASEGURADO / ASSURED PÓLIZA FLOTANTE N°", size=7, bold=True)
    draw_text(pdf, 46, height - 194, "ASSURED: FALABELLA RETAIL S.A. FL-2026-0088", size=9)
    draw_text(pdf, 330, height - 176, f"Conocimiento de embarque (B/L) {bl}", size=7.5)

    y = height - 242
    draw_text(pdf, 34, y, "MERCANCÍA ASEGURADA", size=8, bold=True, color=TEAL)
    y -= 20
    for start in range(0, len(invoice_numbers), 8):
        label = (
            "Mercancía asegurada 40 facturas comerciales -"
            if start == 0
            else "Facturas cubiertas (continuación)"
        )
        line = label + " " + ", ".join(invoice_numbers[start : start + 8])
        box(pdf, 34, y - 8, width - 68, 20, fill=colors.white)
        draw_text(pdf, 42, y, line, size=6.3)
        y -= 20

    y -= 10
    box(pdf, 34, y - 124, width - 68, 136, fill=colors.white)
    draw_text(pdf, 46, y - 8, "DESCRIPCIÓN DE LA COBERTURA", size=8, bold=True, color=TEAL)
    draw_text(pdf, 46, y - 31, f"Bultos {total_cartons} cartones - {container} / 40'HC", size=8)
    draw_text(
        pdf,
        46,
        y - 52,
        "Base de valoración CFR + 15% (utilidad esperada y gastos incidentales)",
        size=8,
    )
    draw_text(pdf, 46, y - 76, f"Suma asegurada USD {money(insured)}", size=11, bold=True)
    draw_text(pdf, 46, y - 99, "Tasa de prima 0,0462 % sobre suma asegurada", size=8)
    draw_text(pdf, 330, y - 99, f"Prima USD {money(premium)}", size=10, bold=True)
    pdf.setStrokeColor(GRID)
    pdf.line(355, 73, width - 34, 73)
    draw_text(pdf, 400, 60, "Firma autorizada", size=7, color=MUTED)
    synthetic_footer(pdf, width, "SAMPLE MARINE CARGO CERTIFICATE")
    pdf.save()


def write_origin(
    path: Path,
    invoices: list[dict],
    container: str,
) -> None:
    items = tuple(
        OriginItemData(
            marks=container,
            packages=f"{item['cartons']} CARTONS",
            description=item["description"],
            hs_code=item["hs_code"],
            origin_criterion="WO",
            net_weight_or_quantity=item["net"],
            unit="KGS",
            invoice_number=item["number"],
            invoice_date="2026-08-20",
        )
        for item in invoices
    )
    render_origin_certificate(
        path,
        OriginCertificateData(
            certificate_number="C26CL0124001",
            exporter_name="NINGBO HOMEWARE MANUFACTURING CO., LTD.",
            exporter_address="88 Harbor Industrial Road, Ningbo, Zhejiang, CHINA",
            producer="SAME",
            consignee_name="FALABELLA RETAIL S.A.",
            consignee_address="Rosario Norte 660, Las Condes, Santiago, CHILE",
            issued_in="CHINA",
            departure_date="2026-08-28",
            transport_number="OCEAN PACIFIC V.2628E",
            port_of_loading="SHANGHAI, CHINA",
            port_of_discharge="VALPARAISO, CHILE",
            remarks="Purchase order PO-26-0817.",
            issue_place="NINGBO",
            issue_date="2026-08-24",
            issuing_authority="China Council for the Promotion of International Trade, Ningbo",
            items=items,
            dispatch_reference="Dispatch 700613 / Ref 54415CLFA/26J28-9",
        ),
    )


def _volume_invoice_data() -> list[dict]:
    products = [
        ("Cotton bath towels assorted", "6302.60", Decimal("5.00")),
        ("Ceramic tableware set", "6912.00", Decimal("25.00")),
        ("Glass storage jars", "7010.90", Decimal("4.00")),
        ("LED desk lamps", "9405.20", Decimal("20.00")),
        ("Bluetooth speakers", "8518.22", Decimal("30.00")),
        ("Insulated copper cable", "8544.42", Decimal("8.00")),
    ]
    invoices: list[dict] = []
    first_carton = 1
    for index in range(1, 41):
        description, hs_code, unit_price = products[(index - 1) % len(products)]
        quantity = Decimal(400 + index * 20)
        total = quantity * unit_price
        cartons = 35 + index
        gross = Decimal(cartons) * Decimal("12.5")
        net = gross - Decimal(cartons) * Decimal("1.25")
        invoices.append(
            {
                "number": f"BN260106{index:02d}",
                "description": description,
                "hs_code": hs_code,
                "unit_price": unit_price,
                "quantity": quantity,
                "total": total,
                "cartons": cartons,
                "gross": gross,
                "net": net,
                "first_carton": first_carton,
                "last_carton": first_carton + cartons - 1,
            }
        )
        first_carton += cartons
    return invoices


def regenerate_origin_certificate() -> None:
    write_origin(
        TARGET / "05_CERTIFICATE_OF_ORIGIN_C26CL0124001.pdf",
        _volume_invoice_data(),
        "OLSU6622881",
    )


def build_fixture() -> dict:
    dispatch = "700613"
    reference = "54415CLFA/26J28-9"
    bl = "OLS-SHA-2602288"
    container = "OLSU6622881"
    freight = Decimal("9850.00")
    invoices = _volume_invoice_data()

    total_fob = sum((item["total"] for item in invoices), Decimal("0"))
    total_cartons = sum(item["cartons"] for item in invoices)
    total_gross = sum((item["gross"] for item in invoices), Decimal("0"))
    total_net = sum((item["net"] for item in invoices), Decimal("0"))
    measurement = Decimal("146.8")
    insured = ((total_fob + freight) * Decimal("1.15")).quantize(MONEY)
    premium = (insured * Decimal("0.000462")).quantize(MONEY)
    invoice_numbers = [item["number"] for item in invoices]

    write_instruction(
        TARGET / f"00_INSTRUCCION_DESPACHO_{dispatch}.pdf",
        dispatch,
        reference,
        bl,
        invoice_numbers,
        freight,
    )
    write_bill_of_lading(
        TARGET / f"01_BILL_OF_LADING_{bl}.pdf",
        bl,
        container,
        invoice_numbers,
        total_cartons,
        total_gross,
        measurement,
        freight,
        total_fob,
    )

    for index, item in enumerate(invoices, start=1):
        write_invoice(
            TARGET / f"02_{index:02d}_COMMERCIAL_INVOICE_{item['number']}.pdf",
            item,
            index,
            bl,
        )

    write_packing_list(
        TARGET / f"03_PACKING_LIST_{bl}.pdf",
        invoices,
        bl,
        container,
        total_cartons,
        total_gross,
        total_net,
        measurement,
    )
    write_insurance(
        TARGET / "04_CERTIFICADO_SEGURO_MC-2026-06288.pdf",
        bl,
        invoice_numbers,
        total_cartons,
        container,
        insured,
        premium,
    )
    write_origin(
        TARGET / "05_CERTIFICATE_OF_ORIGIN_C26CL0124001.pdf",
        invoices,
        container,
    )

    manifest = {
        "scenario": "C",
        "purpose": "high-volume parallel-processing demonstration with realistic document layouts",
        "document_style": "synthetic documents modeled on common trade-document forms",
        "uploaded_pdfs": 45,
        "commercial_invoices": 40,
        "despacho": dispatch,
        "reference": reference,
        "bl_number": bl,
        "total_fob_usd": str(total_fob),
        "freight_usd": str(freight),
        "insurance_premium_usd": str(premium),
        "sum_insured_usd": str(insured),
        "total_cartons": total_cartons,
        "gross_weight_kg": str(total_gross),
        "origin_certificate_format": "China-Chile FTA reference form, front plus overleaf",
        "origin_certificate_page_size_mm": "216x330",
        "origin_certificate_items": len(invoices),
        "expected_rule_failures": 0,
    }
    (TARGET / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(build_fixture(), indent=2, ensure_ascii=False))
