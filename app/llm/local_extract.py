from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pdfplumber

from app.llm.classify import classify_text
from app.schemas.domain import (
    BillOfLading,
    CertificateOfOrigin,
    Cited,
    CommercialInvoice,
    DispatchInstruction,
    DocumentType,
    InsuranceCertificate,
    InvoiceLine,
    OriginItem,
    PackingLine,
    PackingList,
)

NUMBER_RE = re.compile(r"[^0-9.-]")


def pdf_text(path: Path) -> tuple[str, int, bool]:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text(x_tolerance=2, y_tolerance=2) or "" for page in pdf.pages]
    text = "\n".join(pages)
    return text, len(pages), bool(text.strip())


def _decimal(value: str) -> Decimal:
    return Decimal(NUMBER_RE.sub("", value.replace(",", "")))


def _line(text: str, contains: str) -> str:
    return next((line.strip() for line in text.splitlines() if contains in line), contains)


def _c(value: Any, source: str, confidence: str = "0.99") -> Cited:
    return Cited(value=value, page=1, source_text=source.strip(), confidence=Decimal(confidence))


def _values(pattern: str, text: str, flags: int = 0) -> tuple[str, ...]:
    match = re.search(pattern, text, flags)
    if not match:
        raise ValueError(f"fixture pattern not found: {pattern}")
    return match.groups()


def extract_local_text(text: str, doc_type: DocumentType | None = None):
    if not text.strip():
        raise ValueError("local demo extractor cannot process an empty or scanned PDF")
    if doc_type is None:
        doc_type, _ = classify_text(text)
    parsers = {
        DocumentType.DISPATCH_INSTRUCTION: _instruction,
        DocumentType.BILL_OF_LADING: _bill_of_lading,
        DocumentType.COMMERCIAL_INVOICE: _invoice,
        DocumentType.PACKING_LIST: _packing_list,
        DocumentType.INSURANCE_CERTIFICATE: _insurance,
        DocumentType.CERTIFICATE_OF_ORIGIN: _origin,
    }
    if doc_type not in parsers:
        raise ValueError("unclassifiable document")
    return parsers[doc_type](text)


def extract_local(path: Path):
    text, _, has_text = pdf_text(path)
    if not has_text:
        raise ValueError("local demo extractor cannot process a scanned PDF")
    return extract_local_text(text)


def _instruction(text: str) -> DispatchInstruction:
    despacho, referencia = _values(r"N° Despacho (\d+)\s+Referencia ([^\n]+)", text)
    importer = _values(r"Importador / Consignatario (.+?)(?: [—-] RUT|\n)", text)[0]
    bl = _values(r"Conocimiento de embarque ([A-Z0-9-]+)", text)[0]
    invoices = list(dict.fromkeys(re.findall(r"BN\d{8}", text)))
    currency, freight = _values(r"Flete marítimo .*?\b([A-Z]{3}) ([\d,.]+)", text)
    agreement = _values(r"Acuerdo comercial invocado (.+?) [—-] certificado", text)[0]
    return DispatchInstruction(
        despacho_no=_c(despacho, _line(text, "N° Despacho")),
        referencia=_c(referencia.strip(), _line(text, "Referencia")),
        importer_name=_c(importer, _line(text, "Importador / Consignatario")),
        bl_number=_c(bl, _line(text, "Conocimiento de embarque")),
        invoice_numbers=[_c(value, _line(text, "Facturas comerciales")) for value in invoices],
        freight_amount=_c(_decimal(freight), _line(text, "Flete marítimo")),
        freight_currency=_c(currency, _line(text, "Flete marítimo")),
        agreement_name=_c(agreement, _line(text, "Acuerdo comercial invocado")),
    )


def _bill_of_lading(text: str) -> BillOfLading:
    bl = _values(r"B/L Number\s+([A-Z0-9-]+)", text)[0]
    vessel_full = _values(r"\n(OCEAN [A-Z ]+ V\.\d+E)\s", text)[0]
    vessel, voyage = vessel_full.rsplit(" ", 1)
    load, shipped, discharge = _values(
        r"PORT OF LOADING PORT OF DISCHARGE\s+(.+?) \(ETD (\d{4}-\d{2}-\d{2})\) (.+?) \(ETA", text
    )
    consignee_match = re.search(r"CONSIGNEE:\s*([^\n]+)", text)
    consignee = (
        consignee_match.group(1).strip()
        if consignee_match
        else _values(r"CONSIGNEE \(OR ORDER\) NOTIFY PARTY\s+(.+?) AGENCIA", text)[0].strip()
    )
    container, packages, weight, cbm = _values(
        r"([A-Z]{4}\d{7}) / 40'HC\s+(\d+)\s+SAID TO CONTAIN:\s+([\d,.]+)\s+([\d.]+)", text
    )
    freight = _values(r"TOTAL FREIGHT THIS B/L USD ([\d,.]+)", text)[0]
    declared_match = re.search(r"TOTAL DECLARED VALUE THIS B/L USD ([\d,.]+)", text)
    invoices = list(dict.fromkeys(re.findall(r"BN\d{8}", text)))
    return BillOfLading(
        bl_number=_c(bl, _line(text, bl)),
        vessel=_c(vessel, _line(text, vessel_full)),
        voyage=_c(voyage, _line(text, vessel_full)),
        port_loading=_c(load, _line(text, "PORT OF LOADING") + " " + _line(text, "(ETD")),
        port_discharge=_c(discharge, _line(text, "(ETD")),
        shipped_on_board_date=_c(date.fromisoformat(shipped), _line(text, "SHIPPED ON BOARD")),
        consignee_name=_c(consignee, _line(text, consignee)),
        gross_weight_kg=_c(_decimal(weight), _line(text, "SAID TO CONTAIN")),
        package_count=_c(int(packages), _line(text, "SAID TO CONTAIN")),
        measurement_cbm=_c(_decimal(cbm), _line(text, "SAID TO CONTAIN")),
        freight_amount=_c(_decimal(freight), _line(text, "TOTAL FREIGHT THIS B/L")),
        freight_currency=_c("USD", _line(text, "TOTAL FREIGHT THIS B/L")),
        declared_value_total=(
            _c(_decimal(declared_match.group(1)), _line(text, "TOTAL DECLARED VALUE THIS B/L"))
            if declared_match
            else Cited(value=None, confidence=Decimal("0"))
        ),
        container_number=_c(container, _line(text, container)),
        invoice_numbers_cited=[_c(value, _line(text, value)) for value in invoices],
    )


def _invoice(text: str) -> CommercialInvoice:
    number = _values(r"Invoice No\. (BN\d{8})", text)[0]
    invoice_date = _values(r"\bDate (\d{4}-\d{2}-\d{2})", text)[0]
    supplier = _values(r"(?:^|\n)([^\n]+?) COMMERCIAL INVOICE(?:\n|$)", text)[0].strip()
    consignee = _values(r"\n([^\n]+?) Vessel:", text)[0].strip()
    row = next(
        line
        for line in text.splitlines()
        if re.match(r"1 .+ \d{4}\.\d{2} [\d,]+ [A-Z]+ [\d.]+ [\d,.]+$", line)
    )
    match = re.match(r"1 (.+) (\d{4}\.\d{2}) ([\d,]+) ([A-Z]+) ([\d.]+) ([\d,.]+)$", row)
    if not match:
        raise ValueError("invoice row not parsed")
    description, hs, quantity, uom, unit_price, line_total = match.groups()
    total_match = re.search(
        r"TOTAL (?:FOB|FCA|EXW|CFR|CPT|CIF|CIP|DAP|DDP)(?: [A-Z]+)? USD ([\d,.]+)", text
    )
    if not total_match:
        raise ValueError("invoice total not parsed")
    total = total_match.group(1)
    packages = _values(r"Packages: (\d+) CTN", text)[0]
    gross = _values(r"Gross weight: ([\d,.]+) KGS", text)[0]
    net = _values(r"Net weight: ([\d,.]+) KGS", text)[0]
    included_amounts = {
        component.lower(): _c(_decimal(amount), _line(text, f"INCLUDED {component}"))
        for component, amount in re.findall(
            r"INCLUDED (FREIGHT|INSURANCE|DUTIES) USD ([\d,.]+)", text, re.IGNORECASE
        )
    }
    return CommercialInvoice(
        invoice_number=_c(number, _line(text, "Invoice No.")),
        invoice_date=_c(date.fromisoformat(invoice_date), _line(text, "Date ")),
        supplier_name=_c(supplier, supplier),
        consignee_name=_c(consignee, _line(text, consignee)),
        incoterm=_c(
            _values(r"Incoterms 2020: ((?:FOB|FCA|EXW|CFR|CPT|CIF|CIP|DAP|DDP)(?: [A-Z]+)?)", text)[
                0
            ],
            _line(text, "Incoterms 2020"),
        ),
        currency=_c("USD", _line(text, "Currency:")),
        invoice_total=_c(_decimal(total), _line(text, "TOTAL ")),
        included_amounts=included_amounts,
        package_count=_c(int(packages), _line(text, "Packages:")),
        gross_weight_kg=_c(_decimal(gross), _line(text, "Gross weight:")),
        net_weight_kg=_c(_decimal(net), _line(text, "Net weight:")),
        lines=[
            InvoiceLine(
                description=_c(description, row),
                hs_code=_c(hs, row),
                quantity=_c(_decimal(quantity), row),
                uom=_c(uom, row),
                unit_price=_c(_decimal(unit_price), row),
                line_total=_c(_decimal(line_total), row),
            )
        ],
    )


def _packing_list(text: str) -> PackingList:
    bl = _values(r"B/L: ([A-Z0-9-]+)", text)[0]
    consignee = _values(r"\n([^\n]+?) B/L:", text)[0].strip()
    container = _values(r"Container / Seal: ([A-Z]{4}\d{7})", text)[0]
    total_packages, gross, net = _values(r"TOTAL (\d+) ([\d,.]+) ([\d,.]+)", text)
    cbm = _values(r"Total measurement: ([\d.]+) CBM", text)[0]
    lines: list[PackingLine] = []
    for row in text.splitlines():
        match = re.match(
            r"\d+ - \d+ (BN\d{8}) (.+) ([\d,]+) ([A-Z]+) (\d+) ([\d,.]+) ([\d,.]+)$", row
        )
        if match:
            inv, desc, qty, uom, cartons, line_gross, line_net = match.groups()
            lines.append(
                PackingLine(
                    invoice_number=_c(inv, row),
                    description=_c(desc, row),
                    quantity=_c(_decimal(qty), row),
                    uom=_c(uom, row),
                    cartons=_c(int(cartons), row),
                    gross_weight_kg=_c(_decimal(line_gross), row),
                    net_weight_kg=_c(_decimal(line_net), row),
                )
            )
    return PackingList(
        bl_number=_c(bl, _line(text, "B/L:")),
        consignee_name=_c(consignee, _line(text, consignee)),
        container_number=_c(container, _line(text, "Container / Seal")),
        package_count=_c(int(total_packages), _line(text, "TOTAL ")),
        gross_weight_kg=_c(_decimal(gross), _line(text, "TOTAL ")),
        net_weight_kg=_c(_decimal(net), _line(text, "TOTAL ")),
        measurement_cbm=_c(_decimal(cbm), _line(text, "Total measurement")),
        lines=lines,
    )


def _insurance(text: str) -> InsuranceCertificate:
    number = _values(r"Certificado N° ([A-Z0-9-]+)", text)[0]
    assured_match = re.search(r"ASSURED:\s*(.+?) FL-", text)
    assured = (
        assured_match.group(1).strip()
        if assured_match
        else _values(r"ASEGURADO / ASSURED PÓLIZA FLOTANTE N°\s+(.+?) FL-", text)[0].strip()
    )
    bl = _values(r"Conocimiento de embarque \(B/L\) ([A-Z0-9-]+)", text)[0]
    insured = _values(r"Suma asegurada USD ([\d,.]+)", text)[0]
    rate = _values(r"Tasa de prima ([\d,]+) %", text)[0].replace(",", ".")
    premium = _values(r"Prima USD ([\d,.]+)", text)[0]
    invoices = list(dict.fromkeys(re.findall(r"BN\d{8}", text)))
    return InsuranceCertificate(
        certificate_number=_c(number, _line(text, "Certificado N°")),
        assured_name=_c(assured, _line(text, assured)),
        bl_number=_c(bl, _line(text, "Conocimiento de embarque")),
        sum_insured=_c(_decimal(insured), _line(text, "Suma asegurada")),
        premium=_c(_decimal(premium), _line(text, "Prima USD")),
        premium_rate=_c(Decimal(rate) / Decimal("100"), _line(text, "Tasa de prima")),
        currency=_c("USD", _line(text, "Suma asegurada")),
        coverage_basis=_c(
            _values(r"Base de valoración (.+)", text)[0], _line(text, "Base de valoración")
        ),
        invoices_covered=[_c(v, _line(text, "Mercancía asegurada")) for v in invoices],
    )


def _origin(text: str) -> CertificateOfOrigin:
    front = text.split("Overleaf Instruction", 1)[0]
    number = _values(r"Certificate No\.:\s*([A-Z0-9-]+)", front, re.I)[0]

    def following_value(label: str) -> str:
        lines = [line.strip() for line in front.splitlines() if line.strip()]
        start = next(
            index for index, line in enumerate(lines) if label.casefold() in line.casefold()
        )
        skipped = (
            "certificate no.",
            "certificate of origin",
            "form for china-chile",
            "issued in:",
            "(see instruction",
            "for official use",
            "synthetic fixture",
        )
        return next(line for line in lines[start + 1 :] if not line.casefold().startswith(skipped))

    exporter = following_value("1. Exporter's name")
    consignee = following_value("3. Consignee's name")
    issuing_authority = _values(r"Authorised body:\s*([^\n]+)", front, re.I)[0].strip()
    departure = _values(r"Departure Date:\s*(\d{4}-\d{2}-\d{2})", front, re.I)[0]
    issue_dates = re.findall(r"\n[A-Z][A-Z ]+,\s*(\d{4}-\d{2}-\d{2})", front)
    if not issue_dates:
        issue_dates = re.findall(r"Place and date:.*?(\d{4}-\d{2}-\d{2})", front)
    issue = issue_dates[-1]
    issue_source = next(
        (
            line.strip()
            for line in front.splitlines()
            if line.strip().endswith(issue) and "," in line
        ),
        _line(front, issue),
    )
    container_matches = re.findall(r"([A-Z]{4}\d{7})", front)
    container = container_matches[0] if container_matches else None
    items: list[OriginItem] = []
    row_pattern = re.compile(
        r"(?m)^\s*\d{1,2}\s+[A-Z0-9/-]+\s+(.+?)\s+(\d{4}\.\d{2})\s+"
        r"(WO|WP|RVC|PSR)\s+([\d,.]+)\s+([A-Z]+)\s+(BN\d{8})\s*/\s*"
        r"(\d{4}-\d{2}-\d{2})"
    )
    for match in row_pattern.finditer(front):
        goods, hs, criterion, amount, unit, invoice, invoice_date = match.groups()
        description = goods.split(";", 1)[-1].strip().rstrip(" *")
        source = " ".join(match.group(0).split())
        items.append(
            OriginItem(
                hs_code=_c(hs, source),
                description=_c(description, source),
                origin_criterion=_c(criterion, source),
                net_weight_or_quantity=_c(_decimal(amount), source),
                weight_or_quantity_unit=_c(unit, source),
                invoice_number=_c(invoice, source),
                invoice_date=_c(date.fromisoformat(invoice_date), source),
            )
        )
    return CertificateOfOrigin(
        certificate_number=_c(number, _line(text, number)),
        issue_date=_c(date.fromisoformat(issue), issue_source),
        exporter_name=_c(exporter, _line(text, exporter)),
        issuing_authority=_c(issuing_authority, _line(front, "Authorised body:")),
        consignee_name=_c(consignee, _line(text, consignee)),
        agreement_name=_c(
            "CHINA-CHILE FREE TRADE AGREEMENT", _line(text, "Form for China-Chile FTA")
        ),
        departure_date=_c(date.fromisoformat(departure), _line(text, "Departure Date")),
        is_retrospective=_c("ISSUED RETROACTIVELY" in front.upper(), _line(front, "5. Remarks")),
        container_number=_c(container, _line(text, container))
        if container
        else Cited(value=None, confidence=Decimal("0")),
        items=items,
    )
