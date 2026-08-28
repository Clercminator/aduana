"""Build a synthetic supplier-format and image-quality fixture pack."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from origin_certificate_fixture import (
    OriginCertificateData,
    OriginItemData,
    render_origin_certificate,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "fixtures" / "scenario_E_document_realism"
TMP = ROOT / "tmp" / "pdfs"
SUPPLIERS = [
    "Ningbo Harbor Home Co.",
    "Shenzhen Brightpath Ltd.",
    "Guangzhou Mesa Trading",
    "Suzhou Living Works",
    "Hangzhou Northstar Export",
    "Qingdao Ceramics Union",
    "Xiamen Ocean Housewares",
    "Foshan Lumen Factory",
    "Dongguan Cable Systems",
    "Tianjin Retail Supply",
    "Wuxi Everyday Goods",
    "Yiwu Global Merchants",
]
PALETTES = [
    ("#08213f", "#e8f1f5"),
    ("#5b2333", "#f8eaef"),
    ("#175c4c", "#e8f5f1"),
    ("#6b4f16", "#fbf3df"),
    ("#334e68", "#eaf0f5"),
    ("#6a3d9a", "#f1eafa"),
]


def stamp(pdf: canvas.Canvas, x: float, y: float, angle: float) -> None:
    pdf.saveState()
    pdf.translate(x, y)
    pdf.rotate(angle)
    pdf.setStrokeColor(colors.HexColor("#b21f2d"))
    pdf.setFillColor(colors.HexColor("#b21f2d"))
    pdf.setLineWidth(1.5)
    pdf.circle(0, 0, 34, stroke=1, fill=0)
    pdf.circle(0, 0, 29, stroke=1, fill=0)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawCentredString(0, 3, "EXPORT VERIFIED")
    pdf.setFont("Helvetica", 6)
    pdf.drawCentredString(0, -8, "SYNTHETIC STAMP")
    pdf.restoreState()


def vector_invoice(index: int, supplier: str) -> str:
    path = TARGET / f"supplier_{index:02d}_invoice_vector.pdf"
    primary, pale = PALETTES[(index - 1) % len(PALETTES)]
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    width, height = A4
    layout = (index - 1) % 5
    if layout == 0:
        pdf.setFillColor(colors.HexColor(primary))
        pdf.rect(0, height - 92, width, 92, fill=1, stroke=0)
    elif layout == 1:
        pdf.setFillColor(colors.HexColor(primary))
        pdf.rect(0, 0, 72, height, fill=1, stroke=0)
    elif layout == 2:
        pdf.setFillColor(colors.HexColor(pale))
        pdf.roundRect(28, height - 120, width - 56, 82, 12, fill=1, stroke=0)
    elif layout == 3:
        pdf.setStrokeColor(colors.HexColor(primary))
        pdf.setLineWidth(5)
        pdf.line(30, height - 30, width - 30, height - 30)
    else:
        pdf.setFillColor(colors.HexColor(pale))
        pdf.rect(0, height - 54, width, 54, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor(primary))
        pdf.rect(width - 118, 0, 118, height, fill=1, stroke=0)
    pdf.setFillColor(colors.white if layout == 0 else colors.HexColor(primary))
    pdf.setFont("Helvetica-Bold", 17)
    title_x = 88 if layout == 1 else 34
    title_y = height - 68 if layout == 3 else height - 55
    pdf.drawString(title_x, title_y, supplier.upper())
    pdf.setFillColor(colors.HexColor("#172b4d"))
    pdf.setFont("Helvetica-Bold", 13)
    pdf.drawString(title_x, height - 130, "COMMERCIAL INVOICE / FACTURA COMERCIAL")
    pdf.setFont("Helvetica", 9)
    invoice = f"REAL-{index:02d}-2026"
    details = [
        f"Invoice No. {invoice}",
        "Date 2026-08-24",
        "Sold to / Vendido a: FALABELLA RETAIL S.A.",
        "Incoterms 2020: FOB SHANGHAI",
        "Currency / Moneda: USD",
    ]
    y = height - 154
    for line in details:
        pdf.drawString(title_x, y, line)
        y -= 15
    table_y = height - 275
    content_right = width - (142 if layout == 4 else 36)
    table_width = content_right - title_x
    pdf.setFillColor(colors.HexColor(primary))
    pdf.rect(title_x, table_y, table_width, 25, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(title_x + 8, table_y + 8, "DESCRIPTION / DESCRIPCIÓN")
    pdf.drawRightString(content_right - 8, table_y + 8, "AMOUNT USD")
    pdf.setFillColor(colors.HexColor("#243b53"))
    pdf.setFont("Helvetica", 8.5)
    for row in range(4):
        row_y = table_y - 27 - row * 29
        pdf.setFillColor(colors.HexColor(pale) if row % 2 else colors.white)
        pdf.rect(title_x, row_y, table_width, 27, fill=1, stroke=0)
        pdf.setFillColor(colors.HexColor("#243b53"))
        pdf.drawString(
            title_x + 8, row_y + 9, f"Synthetic product family {index}.{row + 1} - HS 9403.20"
        )
        pdf.drawRightString(content_right - 8, row_y + 9, f"{(index + row + 1) * 875:,.2f}")
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawRightString(content_right - 8, table_y - 157, f"TOTAL USD {(index * 3500) + 8750:,.2f}")
    stamp(pdf, content_right - 82, 142 + (index % 3) * 26, -14 + index)
    pdf.setFillColor(colors.HexColor("#c81e1e"))
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(
        132 if layout == 1 else 34,
        24,
        "SYNTHETIC FORMAT FIXTURE - NOT A REAL INVOICE",
    )
    pdf.save()
    return path.name


def phone_photo_invoice(index: int, supplier: str) -> str:
    TMP.mkdir(parents=True, exist_ok=True)
    image_path = TMP / f"phone_invoice_{index:02d}.jpg"
    image = Image.new("RGB", (900, 1250), "#d7d1c6")
    draw = ImageDraw.Draw(image)
    draw.polygon([(70, 65), (830, 88), (790, 1170), (105, 1135)], fill="#fffdf5")
    font = ImageFont.load_default()
    draw.text((135, 130), supplier.upper(), fill="#172b4d", font=font)
    draw.text((135, 178), "COMMERCIAL INVOICE / FACTURA", fill="#172b4d", font=font)
    draw.text((135, 235), f"Invoice No. REAL-{index:02d}-2026", fill="#222222", font=font)
    draw.text((135, 265), "Sold to: FALABELLA RETAIL S.A.", fill="#222222", font=font)
    draw.text((135, 295), "Incoterms 2020: FOB SHANGHAI", fill="#222222", font=font)
    for row in range(10):
        y = 370 + row * 48
        draw.line((130, y, 745, y + 8), fill="#888888", width=1)
        draw.text(
            (145, y + 13),
            f"Synthetic goods {row + 1}   USD {(row + 2) * 475:,.2f}",
            fill="#333333",
            font=font,
        )
    draw.ellipse((535, 820, 720, 1005), outline="#b21f2d", width=6)
    draw.text((565, 900), "EXPORT VERIFIED", fill="#b21f2d", font=font)
    image = image.rotate(1.8 if index % 2 else -2.2, expand=False, fillcolor="#c2b9aa")
    image = image.filter(ImageFilter.GaussianBlur(radius=0.8))
    image.save(image_path, "JPEG", quality=52, optimize=True)
    path = TARGET / f"supplier_{index:02d}_invoice_phone_photo.pdf"
    pdf = canvas.Canvas(str(path), pagesize=A4, pageCompression=1)
    pdf.drawImage(
        ImageReader(image_path), 0, 0, width=A4[0], height=A4[1], preserveAspectRatio=False
    )
    pdf.save()
    image_path.unlink()
    return path.name


def origin_certificate(index: int) -> str:
    path = TARGET / f"origin_certificate_{index:02d}_stamped.pdf"
    criteria = (("WP", "RVC"), ("PSR", "WO"))[index - 1]
    render_origin_certificate(
        path,
        OriginCertificateData(
            certificate_number=f"REAL-COO-{index:02d}-2026",
            exporter_name=SUPPLIERS[index - 1].upper(),
            exporter_address=f"Synthetic industrial address {index}, Zhejiang, CHINA",
            producer="AVAILABLE UPON REQUEST" if index == 1 else "SAME",
            consignee_name="FALABELLA RETAIL S.A.",
            consignee_address="Synthetic consignee address, Santiago, CHILE",
            issued_in="CHINA",
            departure_date=f"2026-09-{10 + index:02d}",
            transport_number=f"SYNTHETIC VESSEL V.26{index:02d}",
            port_of_loading="NINGBO, CHINA",
            port_of_discharge="SAN ANTONIO, CHILE",
            remarks=(
                "ISSUED RETROACTIVELY - synthetic QA variant."
                if index == 2
                else "Third-country invoice operator: Synthetic Trading Pte. Ltd., Singapore."
            ),
            issue_place="NINGBO",
            issue_date=f"2026-09-{12 + index:02d}",
            issuing_authority="Synthetic authorised-body fixture",
            items=tuple(
                OriginItemData(
                    marks=f"QA{index:02d}-{item_no:02d}",
                    packages=f"{20 + item_no} CARTONS",
                    description=f"Synthetic format-validation product {item_no}",
                    hs_code=("6302.60", "9405.20")[item_no - 1],
                    origin_criterion=criteria[item_no - 1],
                    net_weight_or_quantity=Decimal(100 + index * 10 + item_no),
                    unit="KGS",
                    invoice_number=f"BN260109{index}{item_no}",
                    invoice_date=f"2026-09-{8 + item_no:02d}",
                )
                for item_no in (1, 2)
            ),
            dispatch_reference="Scenario E document-format QA pack",
        ),
    )
    return path.name


def regenerate_origin_certificates() -> list[str]:
    TARGET.mkdir(parents=True, exist_ok=True)
    return [origin_certificate(1), origin_certificate(2)]


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    files = []
    for index, supplier in enumerate(SUPPLIERS, start=1):
        filename = (
            phone_photo_invoice(index, supplier)
            if index in {11, 12}
            else vector_invoice(index, supplier)
        )
        files.append(
            {
                "supplier": supplier,
                "template": index,
                "file": filename,
                "language": "mixed English/Spanish" if index % 3 == 0 else "English",
                "stamp_overlay": True,
                "image_only_phone_photo": index in {11, 12},
            }
        )
    certificates = regenerate_origin_certificates()
    manifest = {
        "purpose": "document-format and OCR-routing realism",
        "distinct_supplier_templates": len(SUPPLIERS),
        "invoices": files,
        "stamped_origin_certificates": certificates,
        "origin_certificate_pages_each": 2,
        "origin_criteria_covered": ["WO", "WP", "RVC", "PSR"],
        "image_only_phone_photos": 2,
        "notes": [
            "All identities and transactions are synthetic.",
            "Phone-photo PDFs contain no text layer and are expected to route to OCR.",
            "This pack exercises document diversity; it is not an extraction accuracy benchmark.",
            "Origin certificates follow the supplied China-Chile FTA front-and-overleaf form.",
        ],
    }
    (TARGET / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
