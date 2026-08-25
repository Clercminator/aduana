"""Regenerate fixtures affected by the agency-confirmed valuation rules."""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).parents[1]
MONEY = Decimal("0.01")


def money(value: Decimal) -> str:
    return f"{value.quantize(MONEY, rounding=ROUND_HALF_UP):,.2f}"


def write_pdf(path: Path, title: str, lines: list[str], *, landscape_page: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    page_size = landscape(A4) if landscape_page else A4
    pdf = canvas.Canvas(str(path), pagesize=page_size, pageCompression=1)
    width, height = page_size
    pdf.setFillColor(colors.HexColor("#08213f"))
    pdf.rect(0, height - 54, width, 54, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(30, height - 34, title)
    y = height - 78
    for raw in lines:
        line = raw.replace("—", "-").replace("–", "-").replace("→", "to")
        if y < 38:
            pdf.showPage()
            y = height - 42
        pdf.setFillColor(colors.HexColor("#243b53"))
        pdf.setFont("Helvetica", 7.4 if landscape_page else 8.2)
        pdf.drawString(30, y, line)
        y -= 12
    pdf.setFillColor(colors.HexColor("#c81e1e"))
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(30, 20, "SYNTHETIC TEST DOCUMENT - NOT A REAL COMMERCIAL TRANSACTION")
    pdf.save()


def regenerate_bl_and_insurance() -> None:
    scenarios = [
        {
            "folder": "scenario_A_clean",
            "dispatch": "700611",
            "reference": "54415CLFA/26J14-1",
            "bl": "OLS-SHA-2601147",
            "booking": "BK2601147",
            "supplier": "NINGBO HOMEWARE MANUFACTURING CO., LTD.",
            "vessel": "OCEAN PIONEER V.2614E",
            "port": "SHANGHAI",
            "etd": "2026-06-14",
            "eta": "2026-07-22",
            "container": "OLSU4471902",
            "packages": 962,
            "weight": "14,820.0",
            "cbm": "58.4",
            "freight": Decimal("3200.00"),
            "declared": Decimal("55000.00"),
            "invoices": ["BN26010441", "BN26010442", "BN26010443"],
            "certificate": "MC-2026-04417",
            "sum_insured": Decimal("66930.00"),
        },
        {
            "folder": "scenario_B_exceptions",
            "dispatch": "700612",
            "reference": "54415CLFA/26J21-3",
            "bl": "OLS-NGB-2601583",
            "booking": "BK2601583",
            "supplier": "SHENZHEN BRIGHTPATH ELECTRONICS CO., LTD.",
            "vessel": "OCEAN MERIDIAN V.2619E",
            "port": "NINGBO",
            "etd": "2026-07-14",
            "eta": "2026-08-19",
            "container": "OLSU5583114",
            "packages": 741,
            "weight": "9,208.0",
            "cbm": "61.2",
            "freight": Decimal("4150.00"),
            "declared": Decimal("64370.00"),
            "invoices": ["BN26010512", "BN26010513", "BN26010515"],
            "insured_invoices": ["BN26010512", "BN26010513", "BN26010514"],
            "certificate": "MC-2026-05108",
            "sum_insured": Decimal("68000.00"),
        },
    ]
    for item in scenarios:
        target = ROOT / "fixtures" / item["folder"]
        bl_lines = [
            "OCEANLINK SHIPPING CO., LTD. BILL OF LADING",
            "Port-to-Port / Negotiable",
            "B/L Number",
            item["bl"],
            "SHIPPER / EXPORTER B/L NO. / BOOKING NO.",
            f"{item['supplier']} {item['bl']} / {item['booking']}",
            "CONSIGNEE (OR ORDER) NOTIFY PARTY",
            "FALABELLA RETAIL S.A. AGENCIA DE ADUANAS ANDES LTDA.",
            "VESSEL / VOYAGE PLACE OF RECEIPT",
            f"{item['vessel']} {item['port']}, CHINA",
            "PORT OF LOADING PORT OF DISCHARGE",
            f"{item['port']}, CHINA (ETD {item['etd']}) VALPARAISO, CHILE (ETA {item['eta']})",
            "Container No. / Seal No. No. of Pkgs Description of Goods Gross Weight Measurement",
            f"{item['container']} / 40'HC {item['packages']} SAID TO CONTAIN: {item['weight']} {item['cbm']}",
            "INVOICE NOS.:",
            " ".join(item["invoices"]),
            "FREIGHT PREPAID",
            f"SHIPPED ON BOARD {item['etd']}",
            f"INCOTERM: FOB {item['port']}",
            f"TOTAL FREIGHT THIS B/L USD {money(item['freight'])}",
            f"TOTAL DECLARED VALUE THIS B/L USD {money(item['declared'])}",
            f"Dispatch {item['dispatch']} / Ref {item['reference']}",
        ]
        write_pdf(
            target / f"01_BILL_OF_LADING_{item['bl']}.pdf",
            "BILL OF LADING",
            bl_lines,
            landscape_page=True,
        )
        insured_invoices = item.get("insured_invoices", item["invoices"])
        premium = item["sum_insured"] * Decimal("0.000462")
        insurance_lines = [
            "Compañía de Seguros Generales Cordillera S.A. CERTIFICADO DE SEGURO",
            "MARINE CARGO INSURANCE CERTIFICATE",
            f"Certificado N° {item['certificate']}",
            "ASEGURADO / ASSURED PÓLIZA FLOTANTE N°",
            "FALABELLA RETAIL S.A. FL-2026-0088",
            f"Conocimiento de embarque (B/L) {item['bl']}",
            "Mercancía asegurada 3 facturas comerciales - " + ", ".join(insured_invoices),
            f"Bultos {item['packages']} cartones - {item['container']} / 40'HC",
            "Base de valoración CFR + 15% (utilidad esperada y gastos incidentales)",
            f"Suma asegurada USD {money(item['sum_insured'])}",
            "Tasa de prima 0,0462 % sobre suma asegurada",
            f"Prima USD {money(premium)}",
            "Póliza anual vigente para 2026; la prima impresa no alimenta el cálculo aduanero.",
        ]
        write_pdf(
            target / f"04_CERTIFICADO_SEGURO_{item['certificate']}.pdf",
            "CERTIFICADO DE SEGURO",
            insurance_lines,
        )


def build_cif_scenario() -> None:
    target = ROOT / "fixtures" / "scenario_D_cif"
    dispatch = "700614"
    reference = "54415CLFA/26K02-4"
    bl = "OLS-SHA-2602401"
    invoice = "BN26010701"
    container = "OLSU7701401"
    fob = Decimal("12000.00")
    included_freight = Decimal("1200.00")
    included_insurance = Decimal("15.00")
    cif_total = fob + included_freight + included_insurance
    insured = ((fob + included_freight) * Decimal("1.15")).quantize(MONEY)
    premium = (insured * Decimal("0.000462")).quantize(MONEY)
    write_pdf(
        target / f"00_INSTRUCCION_DESPACHO_{dispatch}.pdf",
        "INSTRUCCIÓN DE DESPACHO",
        [
            "FALABELLA RETAIL S.A. INSTRUCCIÓN DE DESPACHO",
            f"N° Despacho {dispatch}",
            f"Referencia {reference}",
            "Importador / Consignatario FALABELLA RETAIL S.A.",
            f"Conocimiento de embarque {bl}",
            f"Facturas comerciales {invoice}",
            f"Flete marítimo (según B/L) USD {money(included_freight)}",
            "Acuerdo comercial invocado TLC Chile-China - certificado C26CL0125001",
        ],
    )
    write_pdf(
        target / f"01_BILL_OF_LADING_{bl}.pdf",
        "BILL OF LADING",
        [
            "OCEANLINK SHIPPING CO., LTD. BILL OF LADING",
            "B/L Number",
            bl,
            "SHIPPER / EXPORTER B/L NO. / BOOKING NO.",
            f"NINGBO CIF SUPPLIER CO., LTD. {bl} / BK2602401",
            "CONSIGNEE (OR ORDER) NOTIFY PARTY",
            "FALABELLA RETAIL S.A. AGENCIA DE ADUANAS ANDES LTDA.",
            "VESSEL / VOYAGE PLACE OF RECEIPT",
            "OCEAN ATLAS V.2631E SHANGHAI, CHINA",
            "PORT OF LOADING PORT OF DISCHARGE",
            "SHANGHAI, CHINA (ETD 2026-09-02) VALPARAISO, CHILE (ETA 2026-10-10)",
            "Container No. / Seal No. No. of Pkgs Description of Goods Gross Weight Measurement",
            f"{container} / 40'HC 200 SAID TO CONTAIN: 3,000.0 24.5",
            "INVOICE NOS.:",
            invoice,
            "SHIPPED ON BOARD 2026-09-02",
            "INCOTERM: CIF VALPARAISO",
            f"TOTAL FREIGHT THIS B/L USD {money(included_freight)}",
            f"TOTAL DECLARED VALUE THIS B/L USD {money(cif_total)}",
        ],
        landscape_page=True,
    )
    write_pdf(
        target / f"02_01_COMMERCIAL_INVOICE_{invoice}.pdf",
        "COMMERCIAL INVOICE - CIF",
        [
            "NINGBO CIF SUPPLIER CO., LTD. COMMERCIAL INVOICE",
            f"export@synthetic-demo.invalid Invoice No. {invoice}",
            "Date 2026-08-28",
            "SOLD TO / CONSIGNEE SHIPMENT",
            "FALABELLA RETAIL S.A. Vessel: OCEAN ATLAS V.2631E",
            f"B/L No.: {bl}",
            "Item Description of Goods HS Code Qty UoM Unit Price Amount",
            f"1 Kitchen appliance set 8516.60 100 PCS 132.15 {money(cif_total)}",
            f"TOTAL CIF VALPARAISO USD {money(cif_total)}",
            f"INCLUDED FREIGHT USD {money(included_freight)}",
            f"INCLUDED INSURANCE USD {money(included_insurance)}",
            "Incoterms 2020: CIF VALPARAISO Packages: 200 CTN",
            "Gross weight: 3,000.0 KGS",
            "Currency: USD",
            "Net weight: 2,750.0 KGS",
        ],
    )
    write_pdf(
        target / f"03_PACKING_LIST_{bl}.pdf",
        "PACKING LIST",
        [
            "NINGBO CIF SUPPLIER CO., LTD. PACKING LIST",
            "CONSIGNEE SHIPMENT",
            f"FALABELLA RETAIL S.A. B/L: {bl}",
            f"Container / Seal: {container} / 40'HC / CN0770140",
            "1 - 200 BN26010701 Kitchen appliance set 100 PCS 200 3,000.0 2,750.0",
            "TOTAL 200 3,000.0 2,750.0",
            "Total measurement: 24.5 CBM",
        ],
    )
    write_pdf(
        target / "04_CERTIFICADO_SEGURO_MC-2026-07001.pdf",
        "CERTIFICADO DE SEGURO",
        [
            "Compañía de Seguros Generales Cordillera S.A. CERTIFICADO DE SEGURO",
            "Certificado N° MC-2026-07001",
            "ASEGURADO / ASSURED PÓLIZA FLOTANTE N°",
            "FALABELLA RETAIL S.A. FL-2026-0088",
            f"Conocimiento de embarque (B/L) {bl}",
            f"Mercancía asegurada 1 factura comercial - {invoice}",
            "Base de valoración CFR + 15% (utilidad esperada y gastos incidentales)",
            f"Suma asegurada USD {money(insured)}",
            "Tasa de prima 0,0462 % sobre suma asegurada",
            f"Prima USD {money(premium)}",
        ],
    )
    write_pdf(
        target / "05_CERTIFICATE_OF_ORIGIN_C26CL0125001.pdf",
        "CERTIFICATE OF ORIGIN",
        [
            "CERTIFICATE OF ORIGIN",
            "Form F - CHINA-CHILE FREE TRADE AGREEMENT",
            "Issued in THE PEOPLE'S REPUBLIC OF CHINA",
            "1. EXPORTER'S NAME, ADDRESS AND COUNTRY CERTIFICATE NO.",
            "NINGBO CIF SUPPLIER CO., LTD. C26CL0125001",
            "2. PRODUCER'S NAME AND ADDRESS 5. REMARKS",
            "SAME AS EXPORTER -",
            "3. IMPORTER'S NAME, ADDRESS AND COUNTRY 4. MEANS OF TRANSPORT AND ROUTE",
            "FALABELLA RETAIL S.A. Departure date: 2026-09-02",
            f"1 {container} 200 CARTONS 8516.60 WO 3,000.0 {invoice}",
            "MADE IN CHINA - synthetic merchandise for automation testing",
            "Place and date: 2026-09-02",
        ],
    )
    manifest = {
        "scenario": "D",
        "purpose": "CIF normalization equals an economically equivalent FOB invoice",
        "invoice_total_cif_usd": str(cif_total),
        "included_freight_usd": str(included_freight),
        "included_insurance_usd": str(included_insurance),
        "expected_normalized_fob_usd": str(fob),
        "expected_policy_premium_usd": str(premium),
    }
    (target / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    regenerate_bl_and_insurance()
    build_cif_scenario()
