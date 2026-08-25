"""Generate a coherent high-volume synthetic dispatch for performance demonstrations."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "fixtures" / "scenario_C_volume"
MONEY = Decimal("0.01")


def money(value: Decimal) -> str:
    return f"{value.quantize(MONEY, rounding=ROUND_HALF_UP):,.2f}"


def write_pdf(path: Path, lines: list[str], font_size: float = 7.5) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    width, height = A4
    del width
    y = height - 34
    page.setFont("Helvetica", font_size)
    for line in lines:
        line = line.replace("—", "-").replace("–", "-").replace("→", "to")
        if y < 34:
            page.showPage()
            page.setFont("Helvetica", font_size)
            y = height - 34
        page.drawString(32, y, line)
        y -= font_size + 3
    page.save()


def build_fixture() -> dict:
    dispatch = "700613"
    reference = "54415CLFA/26J28-9"
    bl = "OLS-SHA-2602288"
    container = "OLSU6622881"
    freight = Decimal("9850.00")
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
        invoice = {
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
        invoices.append(invoice)
        first_carton += cartons

    total_fob = sum((item["total"] for item in invoices), Decimal("0"))
    total_cartons = sum(item["cartons"] for item in invoices)
    total_gross = sum((item["gross"] for item in invoices), Decimal("0"))
    total_net = sum((item["net"] for item in invoices), Decimal("0"))
    measurement = Decimal("146.8")
    insured = ((total_fob + freight) * Decimal("1.15")).quantize(MONEY)
    premium = (insured * Decimal("0.000462")).quantize(MONEY)
    invoice_numbers = [item["number"] for item in invoices]

    instruction_lines = [
        "FALABELLA RETAIL S.A. INSTRUCCIÓN DE DESPACHO",
        f"N° Despacho {dispatch}",
        f"Referencia {reference}",
        "Agencia de Aduanas AGENCIA DE ADUANAS ANDES LTDA. — RUT 78.905.410-3",
        "Importador / Consignatario FALABELLA RETAIL S.A. — RUT 77.261.280-K",
        "Proveedor NINGBO HOMEWARE MANUFACTURING CO., LTD.",
        f"Conocimiento de embarque {bl} — OCEANLINK SHIPPING CO., LTD.",
        "Nave / Viaje OCEAN PACIFIC V.2628E",
        "Puerto embarque / desembarque SHANGHAI, CHINA → VALPARAISO, CHILE",
        "Fecha embarque / ETA 2026-08-28 / 2026-10-05",
        *[
            ("Facturas comerciales " if start == 0 else "Facturas comerciales (continuación) ")
            + " · ".join(invoice_numbers[start : start + 8])
            for start in range(0, len(invoice_numbers), 8)
        ],
        "Cláusula de compra FOB SHANGHAI",
        f"Flete marítimo (según B/L) USD {money(freight)} — PREPAID",
        "Seguro Póliza flotante FL-2026-0088 — Compañía de Seguros Generales Cordillera S.A.",
        "Régimen solicitado Importación para consumo — Declaración de Ingreso (DIN)",
        "Acuerdo comercial invocado TLC Chile–China — certificado de origen C26CL0124001",
        "Prorrateo de gastos Flete y seguro a prorratear por valor de factura",
        "SYNTHETIC VOLUME DEMO - 45 PDFs - NOT A REAL SHIPMENT",
    ]
    write_pdf(TARGET / f"00_INSTRUCCION_DESPACHO_{dispatch}.pdf", instruction_lines)

    bl_lines = [
        "OCEANLINK SHIPPING CO., LTD. BILL OF LADING",
        "Port-to-Port / Negotiable",
        "B/L Number",
        bl,
        "SHIPPER / EXPORTER B/L NO. / BOOKING NO.",
        f"NINGBO HOMEWARE MANUFACTURING CO., LTD. {bl} / BK2602288",
        "CONSIGNEE (OR ORDER) NOTIFY PARTY",
        "FALABELLA RETAIL S.A. AGENCIA DE ADUANAS ANDES LTDA.",
        "VESSEL / VOYAGE PLACE OF RECEIPT",
        "OCEAN PACIFIC V.2628E SHANGHAI, CHINA",
        "PORT OF LOADING PORT OF DISCHARGE",
        "SHANGHAI, CHINA (ETD 2026-08-28) VALPARAISO, CHILE (ETA 2026-10-05)",
        "Container No. / Seal No. No. of Pkgs Description of Goods Gross Weight Measurement",
        f"{container} / 40'HC {total_cartons} SAID TO CONTAIN: {total_gross:,.1f} {measurement}",
        "INVOICE NOS.:",
        *[" ".join(invoice_numbers[start : start + 6]) for start in range(0, len(invoices), 6)],
        "FREIGHT PREPAID",
        "SHIPPED ON BOARD 2026-08-28",
        "INCOTERM: FOB SHANGHAI",
        f"TOTAL FREIGHT THIS B/L USD {money(freight)}",
        f"TOTAL DECLARED VALUE THIS B/L USD {money(total_fob)}",
        "SYNTHETIC VOLUME DEMO — NOT A REAL SHIPMENT",
    ]
    write_pdf(TARGET / f"01_BILL_OF_LADING_{bl}.pdf", bl_lines)

    for index, item in enumerate(invoices, start=1):
        invoice_lines = [
            "NINGBO HOMEWARE MANUFACTURING CO., LTD. COMMERCIAL INVOICE",
            f"Tel: +86 574 8877 {1100 + index} export@synthetic-demo.invalid Invoice No. {item['number']}",
            "Date 2026-08-20",
            "SOLD TO / CONSIGNEE SHIPMENT",
            "FALABELLA RETAIL S.A. Vessel: OCEAN PACIFIC V.2628E",
            f"B/L No.: {bl}",
            "Item Description of Goods HS Code Qty UoM Unit Price Amount",
            (
                f"1 {item['description']} {item['hs_code']} {item['quantity']:,.0f} PCS "
                f"{item['unit_price']:.2f} {money(item['total'])}"
            ),
            f"TOTAL FOB SHANGHAI USD {money(item['total'])}",
            "TERMS PACKING",
            f"Incoterms 2020: FOB SHANGHAI Packages: {item['cartons']} CTN",
            f"Gross weight: {item['gross']:,.1f} KGS",
            "Currency: USD",
            f"Net weight: {item['net']:,.1f} KGS",
            "Country of Origin: CHINA",
            "SYNTHETIC VOLUME DEMO — NOT A REAL COMMERCIAL TRANSACTION",
        ]
        write_pdf(TARGET / f"02_{index:02d}_COMMERCIAL_INVOICE_{item['number']}.pdf", invoice_lines)

    packing_lines = [
        "NINGBO HOMEWARE MANUFACTURING CO., LTD. PACKING LIST",
        f"P/L No. PL-{bl}",
        "Date 2026-08-21",
        "CONSIGNEE SHIPMENT",
        f"FALABELLA RETAIL S.A. B/L: {bl}",
        f"Container / Seal: {container} / 40'HC / CN0622881",
        "Carton Nos. Invoice No. Description Qty Cartons Gross Wt Net Wt",
    ]
    packing_lines.extend(
        (
            f"{item['first_carton']} - {item['last_carton']} {item['number']} "
            f"{item['description']} {item['quantity']:,.0f} PCS {item['cartons']} "
            f"{item['gross']:,.1f} {item['net']:,.1f}"
        )
        for item in invoices
    )
    packing_lines.extend(
        [
            f"TOTAL {total_cartons} {total_gross:,.1f} {total_net:,.1f}",
            f"Total measurement: {measurement} CBM | Total packages: {total_cartons} CTN",
            "SYNTHETIC VOLUME DEMO — NOT A REAL SHIPMENT",
        ]
    )
    write_pdf(TARGET / f"03_PACKING_LIST_{bl}.pdf", packing_lines, font_size=6.8)

    insurance_lines = [
        "Compañía de Seguros Generales Cordillera S.A. CERTIFICADO DE SEGURO",
        "MARINE CARGO INSURANCE CERTIFICATE",
        "Certificado N° MC-2026-06288",
        "ASEGURADO / ASSURED PÓLIZA FLOTANTE N°",
        "FALABELLA RETAIL S.A. FL-2026-0088",
        f"Conocimiento de embarque (B/L) {bl}",
        f"Mercancía asegurada {len(invoices)} facturas comerciales - "
        + ", ".join(invoice_numbers[:8]),
        *[
            "Facturas cubiertas (continuación) " + ", ".join(invoice_numbers[start : start + 8])
            for start in range(8, len(invoices), 8)
        ],
        f"Bultos {total_cartons} cartones — {container} / 40'HC",
        "Base de valoración CFR + 15% (utilidad esperada y gastos incidentales)",
        f"Suma asegurada USD {money(insured)}",
        "Tasa de prima 0,0462 % sobre suma asegurada",
        f"Prima USD {money(premium)}",
        "SYNTHETIC VOLUME DEMO — NOT A REAL INSURANCE CERTIFICATE",
    ]
    write_pdf(TARGET / "04_CERTIFICADO_SEGURO_MC-2026-06288.pdf", insurance_lines)

    origin_lines = [
        "CERTIFICATE OF ORIGIN",
        "Form F — CHINA–CHILE FREE TRADE AGREEMENT",
        "Issued in THE PEOPLE'S REPUBLIC OF CHINA",
        "1. EXPORTER'S NAME, ADDRESS AND COUNTRY CERTIFICATE NO.",
        "NINGBO HOMEWARE MANUFACTURING CO., LTD. C26CL0124001",
        "2. PRODUCER'S NAME AND ADDRESS 5. REMARKS",
        "SAME AS EXPORTER —",
        "3. IMPORTER'S NAME, ADDRESS AND COUNTRY 4. MEANS OF TRANSPORT AND ROUTE",
        "FALABELLA RETAIL S.A. Departure date: 2026-08-28",
        "6. 7. 8. Number and kind of packages; description of 9. HS code 10. Origin 11. Gross 12. Invoice number",
    ]
    origin_lines.extend(
        (
            f"{index} {container} {item['cartons']} CARTONS {item['hs_code']} WO "
            f"{item['gross']:,.1f} {item['number']}"
        )
        for index, item in enumerate(invoices, start=1)
    )
    origin_lines.extend(
        [
            "MADE IN CHINA — synthetic merchandise for automation testing",
            "Place and date: NINGBO / SHENZHEN, 2026-08-24",
            "Place and date: 2026-08-24",
            "SYNTHETIC VOLUME DEMO — NOT A REAL CERTIFICATE",
        ]
    )
    write_pdf(TARGET / "05_CERTIFICATE_OF_ORIGIN_C26CL0124001.pdf", origin_lines, 6.6)

    manifest = {
        "scenario": "C",
        "purpose": "high-volume parallel-processing demonstration",
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
        "expected_rule_failures": 0,
    }
    (TARGET / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    print(json.dumps(build_fixture(), indent=2, ensure_ascii=False))
