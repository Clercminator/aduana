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


def extract_local(path: Path):
    text, _, has_text = pdf_text(path)
    if not has_text:
        raise ValueError("local demo extractor cannot process a scanned PDF")
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
    consignee = _values(r"CONSIGNEE \(OR ORDER\) NOTIFY PARTY\s+(.+?) AGENCIA", text)[0].strip()
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
        consignee_name=_c(consignee, _line(text, "FALABELLA RETAIL S.A.")),
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
    invoice_date = _values(r"\nDate (\d{4}-\d{2}-\d{2})", text)[0]
    supplier = text.split(" COMMERCIAL INVOICE", 1)[0].splitlines()[0].strip()
    consignee = _values(r"SOLD TO / CONSIGNEE SHIPMENT\s+(.+?) Vessel:", text)[0].strip()
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
        consignee_name=_c(consignee, _line(text, "FALABELLA RETAIL")),
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
    consignee = _values(r"CONSIGNEE SHIPMENT\s+(.+?) B/L:", text)[0].strip()
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
        consignee_name=_c(consignee, _line(text, "FALABELLA RETAIL")),
        container_number=_c(container, _line(text, "Container / Seal")),
        package_count=_c(int(total_packages), _line(text, "TOTAL ")),
        gross_weight_kg=_c(_decimal(gross), _line(text, "TOTAL ")),
        net_weight_kg=_c(_decimal(net), _line(text, "TOTAL ")),
        measurement_cbm=_c(_decimal(cbm), _line(text, "Total measurement")),
        lines=lines,
    )


def _insurance(text: str) -> InsuranceCertificate:
    number = _values(r"Certificado N° ([A-Z0-9-]+)", text)[0]
    assured = _values(r"ASEGURADO / ASSURED PÓLIZA FLOTANTE N°\s+(.+?) FL-", text)[0].strip()
    bl = _values(r"Conocimiento de embarque \(B/L\) ([A-Z0-9-]+)", text)[0]
    insured = _values(r"Suma asegurada USD ([\d,.]+)", text)[0]
    rate = _values(r"Tasa de prima ([\d,]+) %", text)[0].replace(",", ".")
    premium = _values(r"Prima USD ([\d,.]+)", text)[0]
    invoices = list(dict.fromkeys(re.findall(r"BN\d{8}", text)))
    return InsuranceCertificate(
        certificate_number=_c(number, _line(text, "Certificado N°")),
        assured_name=_c(assured, _line(text, "FALABELLA RETAIL")),
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
    number = _values(r"CERTIFICATE NO\.\s+.+? ([A-Z]\d{2}CL\d+)", text, re.S)[0]
    exporter = text.splitlines()[3].split(number)[0].strip()
    importer_line = next(
        line.strip() for line in text.splitlines() if line.strip().startswith("FALABELLA RETAIL")
    )
    importer = importer_line.split("Departure date:", 1)[0].strip()
    departure = _values(r"Departure date: (\d{4}-\d{2}-\d{2})", text)[0]
    issue_dates = re.findall(r"Place and date:.*?(\d{4}-\d{2}-\d{2})", text)
    issue = issue_dates[-1]
    container_matches = re.findall(r"([A-Z]{4}\d{7})", text)
    container = container_matches[0] if container_matches else None
    items: list[OriginItem] = []
    for row in text.splitlines():
        match = re.match(
            r"\d+ [A-Z0-9]+ \d+ CARTONS (\d{4}\.\d{2}) [A-Z]+ ([\d,.]+) (BN\d{8})", row
        )
        if match:
            hs, gross, invoice = match.groups()
            items.append(
                OriginItem(
                    hs_code=_c(hs, row),
                    description=_c(_line(text, "MADE IN CHINA"), _line(text, "MADE IN CHINA")),
                    gross_weight_kg=_c(_decimal(gross), row),
                    invoice_number=_c(invoice, row),
                )
            )
    return CertificateOfOrigin(
        certificate_number=_c(number, _line(text, number)),
        issue_date=_c(date.fromisoformat(issue), _line(text, issue)),
        exporter_name=_c(exporter, _line(text, exporter)),
        importer_name=_c(importer, _line(text, "FALABELLA RETAIL")),
        agreement_name=_c("TLC Chile–China", _line(text, "FREE TRADE AGREEMENT")),
        departure_date=_c(date.fromisoformat(departure), _line(text, "Departure date")),
        is_retrospective=_c("ISSUED RETROSPECTIVELY" in text.upper(), _line(text, "5. REMARKS")),
        container_number=_c(container, _line(text, container))
        if container
        else Cited(value=None, confidence=Decimal("0")),
        items=items,
    )
