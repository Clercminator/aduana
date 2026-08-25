# Project brief — customs dispatch reconciliation system

> **Actualización 24-08-2026:** este brief conserva el diseño original, pero los cambios de
> dominio confirmados con la agencia e implementados en la sección “Cambios confirmados con
> la agencia” de `README.md` lo reemplazan donde exista contradicción. En particular: una DIN
> por factura, normalización previa a FOB, seguro configurado por cliente, dólar aduanero
> mensual, IVA recuperable fuera del costo puesto y control EXC-12.

Paste this whole file as the opening prompt in Claude Code or Codex, with the demo
dataset unpacked at `./fixtures/` and `./jurisdictions/`.

---

## 1. Vision

A jurisdiction-configurable engine that turns a pile of import paperwork into a checked,
costed, review-ready demo dispatch. It creates a provisional DIN for review only; it does
not approve, file, pay, or transmit anything to a customs authority.

The bet is that the import process is **structurally the same everywhere** and only its
*parameters* change. The document set is international standard. The reconciliation logic
contains no country-specific facts at all. What varies — how many taxes, on what base, at
what rate, in what currency, on what declaration form — is configuration.

If this holds, each new country is a config file plus an output adapter, not a fork.
That is the difference between a system and a tool rebuilt per client.

### What is genuinely universal (zero config)

- The document set: Bill of Lading, commercial invoice, packing list, insurance
  certificate, certificate of origin. Governed by shared instruments (Incoterms, the WCO
  Harmonized System, UCP 600), so the same documents in the same shapes worldwide.
- **Every reconciliation rule.** Weights must agree between documents. Cited invoices must
  exist. The consignee must be one legal entity. Arithmetic must add up. A certificate must
  cover the goods claimed under it. Not one of these contains a country-specific fact.
- The idea of pro-rata allocation of shipment-level costs across invoice-level goods.

### What is configuration

- The levy stack: an ordered list, each levy naming a rate source and a base expression
  that may reference levies above it. Chile has two. Peru has four, one of which cascades
  over the others. Same evaluator, different YAML.
- The valuation base: which allocated cost components enter the dutiable value. Chile,
  Peru, Colombia and the EU value on CIF. The United States values on FOB — freight and
  insurance are excluded entirely. That is a different base definition, but still config:
  `components: [fob, freight, insurance]` versus `[fob]`.
- Allocation basis, insurance coverage percentage, tolerances, FX source and date rule.

### What is genuinely per-jurisdiction work

The declaration output. DIN (Chile), DUA (Peru), Pedimento (Mexico), SAD (EU) — different
field sets and filing channels. A template plus an adapter behind one interface. Budget
about a week each, mostly research.

### Scope discipline

**Build the seams now, ship exactly one jurisdiction.** Config-driven levies, pluggable
valuation base, an output adapter interface. Seams cost nothing on day one and are
expensive to retrofit. Do not build a second jurisdiction speculatively — `peru.yaml` ships
only as a test that the engine generalises, never as a supported target.

### Deferred to later versions — but the seams are built in v1

These features are NOT built now. The listed seam IS built now, because each one is cheap
today and a rewrite later. Do not skip the seams.

| Deferred feature | Seam required in v1 |
|---|---|
| HS classification from descriptions | `Cited.provenance` enum: `extracted \| manual \| inferred \| derived`. An inferred value has no page or source_text. |
| Special customs regimes (temporary import, drawback, bonded warehouse) | `dispatch.regime`, single value `import_for_consumption`, passed into levy application where it is a no-op. |
| Direct filing with a customs authority | Declaration adapters return provisional value objects and generated artifacts; no submission state or filing table exists in the demo. |
| Multi-currency invoices on one B/L | **`Money(amount, currency)` value object used throughout — see §13.** The single-currency restriction is EXC-09, a rule that fires, NOT an assumption in the arithmetic. |
| Consolidated dispatches (several B/Ls) and partial clearances | `allocate()` takes an explicit scope — `allocate(invoices, cost_lines, cfg)` — never reaches for "the dispatch's B/L". |
| Multiple client organisations | `org_id` on every table from day one. See §9. |

### Genuinely out of scope, no seam needed

Automated HS tariff-rate lookup tables. Customs authority API integrations. Freight
forwarder / carrier EDI feeds. Anything that files, pays, or transmits on the user's behalf.

---

## 2. The central design constraint

**The language model reads documents and does nothing else.**

Every arithmetic operation, comparison, and rule decision is ordinary Python. If you find
yourself asking the model to compare two numbers, judge consistency, or compute a total,
that is an error — write a function.

This is not stylistic. It is what makes the output auditable, testable, reproducible, and
cheap. It is also the product: a model that helpfully reconciles a 9,847 kg packing list
against a 9,208 kg B/L destroys the only thing worth selling.

---

## 3. Domain glossary

Put this in `GLOSSARY.md` and use these exact field names.

- **B/L** — Bill of Lading. Carrier's transport document; one per shipment. Carries ocean
  freight, gross weight, package count, consignee, and the invoice numbers it covers.
- **FOB** — Free On Board. Goods value at origin port; the invoice total.
- **CFR** — Cost and Freight. FOB + freight.
- **CIF** — Cost, Insurance and Freight. FOB + freight + insurance premium.
- **Customs value** — the dutiable base. Equals CIF in CIF-valuation countries, FOB in
  FOB-valuation countries. Always use this term in code, never "CIF".
- **CoO** — Certificate of Origin. Determines whether a preferential duty rate applies.
- **FTA / TLC** — Free Trade Agreement.
- **HS code** — Harmonized System tariff classification (*partida arancelaria*).
- **Levy** — any duty or tax in the jurisdiction's stack. Chile: ad valorem, IVA.
- **IVA / IGV / VAT** — value added tax, named differently per country. Just a levy.
- **DIN** — Declaración de Ingreso, the Chilean import declaration.
- **Prorrateo** — pro-rata allocation of shipment-level costs across invoices on one B/L.
- **Despacho** — one dispatch / clearance job. The top-level unit of work.

---

## 4. Stack

- Python 3.12, **FastAPI**, **Pydantic v2**, **SQLAlchemy 2.x**, **Alembic**
- **PostgreSQL 16** via `docker compose` from day one. Money is `NUMERIC(14,4)`.
  Never `float`, never SQLite — SQLite has no exact decimal type and serialises writers,
  which breaks the concurrent extraction fan-out.
- **httpx** against **OpenRouter**, with one client per document task and bounded concurrent
  fan-out. SQLAlchemy sessions never cross worker threads; results are persisted serially.
- **pypdfium2** (Apache/BSD) for page count and word bounding boxes.
  Do NOT use PyMuPDF — it is AGPL-3.0 and this is intended to be licensed.
  Do NOT rasterize PDFs to send to the model.
- **PyYAML** for jurisdiction configs
- **pytest** + `pytest-asyncio`
- Frontend: **React + Vite + TypeScript + Tailwind**, `react-pdf` for the viewer
- Demo access: no authentication in v1. Keep `org_id` and audit-event seams, but seed one
  demo organisation and never accept real client documents in this build.

### Sending documents to the model

Send the PDF file directly. Do not convert to images — rasterizing discards the text layer
and re-derives it through OCR, which loses exact character fidelity on precisely the
strings that matter (`9,208.0`, `BN26010515`, `8544.42`).

```python
content = [
    {"type": "file", "file": {
        "filename": doc.filename,
        "file_data": f"data:application/pdf;base64,{b64}"}},
    {"type": "text", "text": prompt},
]
payload = {
    "model": settings.EXTRACT_MODEL,
    "max_tokens": settings.EXTRACT_MAX_TOKENS,
    "messages": [{"role": "user", "content": content}],
    "plugins": [{"id": "file-parser", "pdf": {"engine": "native"}}],
}
```

Do not depend on reusable native-PDF annotations: OpenRouter does not currently provide them
for its native engine. Classification uses locally extracted text when available; extraction
sends the PDF once per immutable extraction run.

Rasterization is still needed for **scanned** documents — real archives are full of phone
photos and fax-quality scans. Detect a missing text layer with pypdfium2 and fall back to
`{"engine": "mistral-ocr"}`, flagging the document as OCR-sourced so the UI can show lower
confidence.

Models via env, never literals:
```
CLASSIFY_MODEL=google/gemini-3.5-flash-lite
EXTRACT_MODEL=google/gemini-3.7-flash
EXTRACT_MAX_TOKENS=12000
DOCUMENT_CONCURRENCY=4
```

The concurrency value is an operational limit, not a promise of fixed latency. Honor
`Retry-After` for 429/503 responses. One document failure must not cancel other documents,
and completed immutable extractions must be reused on a retry.

All model access goes through `app/llm/client.py`. No other module may import httpx or
mention OpenRouter.

---

## 5. Repository layout

```
app/
  main.py  config.py
  db/models.py  db/session.py
  llm/
    client.py             the ONLY module that talks to OpenRouter
    classify.py  extract.py
    prompts/              prompt templates as .txt, not inline strings
  schemas/
    cited.py  documents.py  dispatch.py
  engine/
    jurisdiction.py       loads + validates YAML configs
    levies.py             the ordered levy stack evaluator
    duty.py               per-line rate determination
    allocation.py         pro-rata cost spreading
    valuation.py          customs value from configured components
    fx.py                 rate lookup + conversion
    normalize.py
    rules.py              the reconciliation rules
  adapters/
    base.py               DeclarationAdapter interface
    cl_din.py             Chile DIN draft
  jobs/                   background pipeline runner
  api/
jurisdictions/
  chile.yaml              the shipped target
  peru.yaml               generalisation test ONLY, never a supported target
tests/
fixtures/
  scenario_A_clean/  scenario_B_exceptions/  ANSWER_KEY.json
web/
docker-compose.yml
```

---

## 6. Jurisdiction configuration

`jurisdictions/chile.yaml` is the authority for every rate and rule. **No rate, tax name,
percentage, or base formula may appear anywhere in Python.** Load and validate the YAML
into a Pydantic `JurisdictionConfig` at startup; fail loudly on an invalid config.

Key sections (see the shipped `chile.yaml` for the full schema):

```yaml
valuation:
  base_name: CIF
  components: [fob, freight, insurance]   # a FOB country lists only [fob]

allocation:
  basis: invoice_value                    # invoice_value | gross_weight | volume
  residual_to: largest_line
  cost_lines:
    - {code: freight,    dutiable: true,  source: bill_of_lading}
    - {code: insurance,  dutiable: true,  source: computed}
    - {code: storage,    dutiable: false, source: manual}
    - {code: agency_fee, dutiable: false, source: manual}
    - {code: inland,     dutiable: false, source: manual}

levies:
  - code: AD_VALOREM
    base: customs_value
    rate: {type: hs_lookup, default: 0.06, preference_capable: true}
  - code: IVA
    base: customs_value + AD_VALOREM
    rate: {type: flat, value: 0.19}
```

### Allocable cost lines — generalised

Freight and insurance are not the only costs. Storage, agency fees and inland transport
also belong in landed cost, they just aren't dutiable. `allocation.cost_lines` is an
arbitrary list; each carries `dutiable`, and `valuation.components` decides what enters the
customs value. This is what lets one engine serve both the declaration (dutiable components
only) and inventory costing (everything).

### The levy evaluator

```python
def apply_levies(customs_value: Decimal, hs_rate: Decimal, cfg) -> list[LevyResult]:
    env = {"customs_value": customs_value}
    for levy in cfg.levies:              # ordered
        base = eval_base(levy.base, env) # may reference earlier levy codes
        rate = hs_rate if levy.rate.type == "hs_lookup" else levy.rate.value
        env[levy.code] = amount = round_cfg(base * rate, levy.rounding)
```

`eval_base` parses with `ast.parse(mode="eval")` and walks the tree, permitting only
`Expression`, `BinOp`, `Add`, `Sub`, `Name`, `Load`, and names already present in `env`.
**Never `eval()`.** A config file is a code path.

`tests/test_levies.py` must assert that loading `peru.yaml` produces four levies with the
cascading base, using the same functions and zero code changes. That test is the proof of
the whole vision — treat it as such.

---

## 7. FX and settlement currency

Levies compute in the invoice currency but are **paid in local currency**. A USD figure is
not actionable; the treasury team needs CLP.

`app/engine/fx.py` reads `fx.source` and `fx.date_rule` from config, resolves a rate for the
governing date, and converts. Store the source amount, the rate used, and the converted
amount — never just the result. Rounding per config (CLP has no minor unit, `dp: 0`).

For v1 the rate may be entered manually per dispatch with date and source recorded. An
automated feed is a later concern. **Do not hardcode a rate.**

The exact governing rate and date rule for Chile must be confirmed with the customs agency
before production. The config field exists so this is a one-line correction.

---

## 8. Dispatch lifecycle

Documents do not arrive as a folder. The B/L comes from the carrier, invoices from the
supplier, the certificate of origin often last — sometimes after sailing, which is exactly
why EXC-07 exists. A dispatch fills up over days.

```
dispatch.status: awaiting_documents -> extracting -> review
dispatch.expected_documents: JSONB   -- checklist, seeded from the dispatch instruction
```

- Uploading is incremental; each upload re-runs the pipeline over everything present.
- Rules whose required documents are absent return `SKIPPED` naming the missing document,
  never an error.
- The UI shows expected-versus-received, so missing paperwork surfaces for free.
- Drop-a-whole-folder is the demo path, not an architectural assumption.

---

## 9. Data model

### Two columns that must exist on day one

**`org_id` on every tenant-owned table.** The vision may later support many agencies.
Retrofitting the ownership column is expensive, so the seam exists now and a test fails if
it is absent. The demo seeds one organisation; authentication, access enforcement and real
tenant isolation are explicitly deferred.

**`jurisdiction_config_version` on `dispatch`.** Rates change. A dispatch computed under a
6% duty must reproduce that exact figure years later when the rate has moved. If the config
means "whatever `chile.yaml` says today", every historical dispatch becomes unreproducible
the moment a rate changes — and reproducibility is the entire audit story. Configs carry
an immutable content hash; the dispatch pins the version it was computed under and
recomputation always uses the pinned one.

```sql
CREATE TABLE org (
  id UUID PRIMARY KEY, name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL
);

CREATE TABLE jurisdiction_config_version (
  id UUID PRIMARY KEY,
  jurisdiction TEXT NOT NULL,        -- 'CL'
  content_hash TEXT NOT NULL,        -- sha256 of the YAML
  content JSONB NOT NULL,            -- the parsed config, frozen
  UNIQUE (content_hash)
);

CREATE TABLE dispatch (
  id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES org(id),
  jurisdiction TEXT NOT NULL,               -- 'CL'
  jurisdiction_config_version_id UUID NOT NULL REFERENCES jurisdiction_config_version(id),
  regime TEXT NOT NULL DEFAULT 'import_for_consumption',
  despacho_no TEXT, referencia TEXT,
  status TEXT NOT NULL,                     -- awaiting_documents | extracting | review
  expected_documents JSONB,
  fx_rate NUMERIC(14,6), fx_source TEXT, fx_date DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE document (
  id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES org(id),
  dispatch_id UUID NOT NULL REFERENCES dispatch(id) ON DELETE CASCADE,
  filename TEXT NOT NULL, content_hash TEXT NOT NULL, storage_path TEXT NOT NULL,
  mime_type TEXT NOT NULL, doc_type TEXT, classify_confidence NUMERIC(4,3),
  page_count INT, has_text_layer BOOLEAN, ocr_used BOOLEAN NOT NULL DEFAULT false,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (dispatch_id, content_hash)
);

CREATE TABLE extraction_run (
  id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES org(id),
  document_id UUID NOT NULL REFERENCES document(id) ON DELETE CASCADE,
  status TEXT NOT NULL, parser TEXT NOT NULL, model TEXT, provider TEXT,
  prompt_version TEXT NOT NULL, schema_version TEXT NOT NULL,
  raw_response JSONB, payload JSONB, error TEXT,
  tokens_in INT NOT NULL, tokens_out INT NOT NULL, cost_usd NUMERIC(20,8) NOT NULL,
  latency_ms INT, created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE field_correction (
  id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES org(id),
  dispatch_id UUID NOT NULL REFERENCES dispatch(id) ON DELETE CASCADE,
  field_path TEXT NOT NULL, value JSONB NOT NULL, reason TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE job (
  id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES org(id),
  dispatch_id UUID NOT NULL REFERENCES dispatch(id) ON DELETE CASCADE,
  status TEXT NOT NULL,                     -- queued | running | done | failed
  stage TEXT, progress NUMERIC(4,3), error TEXT,
  tokens_in INT, tokens_out INT, cost_usd NUMERIC(20,8),
  started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ
);

CREATE TABLE calculation_run (
  id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES org(id),
  dispatch_id UUID NOT NULL REFERENCES dispatch(id) ON DELETE CASCADE,
  input_hash TEXT NOT NULL, engine_version TEXT NOT NULL, payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE exception_result (
  id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES org(id),
  dispatch_id UUID NOT NULL REFERENCES dispatch(id) ON DELETE CASCADE,
  calculation_run_id UUID NOT NULL REFERENCES calculation_run(id) ON DELETE CASCADE,
  rule_id TEXT NOT NULL, severity TEXT NOT NULL, result TEXT NOT NULL, payload JSONB NOT NULL,
  accepted_rationale TEXT, accepted_at TIMESTAMPTZ
);

CREATE TABLE audit_event (
  id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES org(id),
  dispatch_id UUID REFERENCES dispatch(id) ON DELETE CASCADE,
  action TEXT NOT NULL, payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE generated_artifact (
  id UUID PRIMARY KEY, org_id UUID NOT NULL REFERENCES org(id),
  dispatch_id UUID NOT NULL REFERENCES dispatch(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, path TEXT NOT NULL, content_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

No `rate_config` table — rates live in the jurisdiction YAML. On startup, hash each config
and upsert it into `jurisdiction_config_version`; a changed hash with the same
`effective_from` is an error, not an update. Historical dispatches always recompute against
their pinned version.

---

## 10. Extraction schemas

```python
class Provenance(str, Enum):
    EXTRACTED = "extracted"   # read off a page by the model
    MANUAL    = "manual"      # typed or corrected by a human
    INFERRED  = "inferred"    # proposed by a model, not present in any document (v2+)
    DERIVED   = "derived"     # computed from other fields by the engine

class Cited(BaseModel):
    value: str | float | int | None
    provenance: Provenance = Provenance.EXTRACTED
    page: int | None                # None unless provenance == EXTRACTED
    source_text: str | None         # None unless provenance == EXTRACTED
    confidence: float = Field(ge=0, le=1)
```

`page` and `source_text` are required when `provenance == EXTRACTED` and must be `None`
otherwise — validate this. Without the enum, v2's inferred HS codes would have to fake a
page reference, which silently corrupts the provenance guarantee the whole product rests on.

Required: `BillOfLading` (bl_number, carrier, vessel, voyage, ports,
shipped_on_board_date, consignee_name, gross_weight_kg, package_count, measurement_cbm,
freight_amount, freight_currency, **invoice_numbers_cited: list[Cited]**),
`CommercialInvoice` (invoice_number, invoice_date, supplier_name, consignee_name, incoterm,
currency, invoice_total, **lines** of description/hs_code/quantity/uom/unit_price/line_total,
package_count, gross_weight_kg, net_weight_kg), `PackingList`, `InsuranceCertificate`
(certificate_number, insurer, assured_name, bl_number, sum_insured, premium, premium_rate,
currency, coverage_basis, invoices_covered), `CertificateOfOrigin` (certificate_number,
issuing_authority, issue_date, exporter_name, importer_name, agreement_name, departure_date,
**is_retrospective: bool**, items of hs_code/description/gross_weight_kg/invoice_number),
`DispatchInstruction`.

### Extraction prompt rules — put these verbatim in every extraction prompt

```
- Return ONLY JSON matching the schema. No markdown fences, no preamble, no commentary.
- Every field is an object with value, page, source_text, confidence.
- source_text must be the literal characters as printed. Never paraphrase or normalise.
- If a field is genuinely absent, set value to null and confidence to 0.
  Do not infer it, do not compute it, do not fill it from what is typical.
- Do NOT correct anything that looks wrong, inconsistent, or like a typo.
  Report exactly what is printed. Detecting inconsistencies is not your job.
- Numbers: digits only, no thousands separators, dot as the decimal mark.
- Dates: YYYY-MM-DD.
```

The "do not correct" rule is load-bearing and appears twice in this brief deliberately.
It is the instruction most likely to be softened during refactoring, and softening it
deletes the product.

On `ValidationError`: retry once with the error appended. On a second failure mark the
document `extraction_failed` and surface it for manual entry. Never fabricate a value.

---

## 11. Reconciliation rules

Decorated functions in `app/engine/rules.py`. Each declares required document types and
returns `SKIPPED` naming any absent one. **No rule may reference a country, a rate, or a
tax name.** Tolerances come from the jurisdiction config.

| ID | Severity | Rule |
|---|---|---|
| EXC-01 | CRITICAL | Packing list total gross weight vs B/L gross weight, within `tolerances.weight_pct`. |
| EXC-02 | CRITICAL | Invoice numbers cited on the B/L exist in the extracted set, and vice versa. Report both directions. |
| EXC-03 | CRITICAL | Every HS code in any invoice line is covered by the CoO. Uncovered lines lose preference — include the quantified duty impact. |
| EXC-04 | WARNING | Sum insured >= `insurance.coverage_pct` x CFR. Report the shortfall. |
| EXC-05 | WARNING | Per line, quantity x unit_price == line_total; lines sum to invoice_total. |
| EXC-06 | WARNING | Consignee identical across B/L, invoices, insurance and CoO after normalisation. Legal-suffix differences (S.A. vs SpA) MUST fire. |
| EXC-07 | WARNING | CoO `issue_date` <= B/L `shipped_on_board_date`, unless `is_retrospective`. **Risk flag only** — see below. |
| EXC-08 | WARNING | Container number consistent across B/L, packing list and CoO. |
| EXC-09 | WARNING | All invoices on the dispatch share one currency. |
| CHK-10 | INFO | Packing list package count == B/L package count. |
| CHK-11 | INFO | B/L freight == freight in the dispatch instruction. |

Every exception carries `source_refs` pointing at the specific extracted fields on **both**
sides of the comparison, so the UI shows exactly which two cells disagree.

EXC-01, EXC-02, EXC-03, EXC-06, EXC-08 and CHK-11 each need two documents. That is the
product — make it visible in the code.

### EXC-07 must not change the rate

A post-dated certificate does **not** automatically void preference — customs may accept or
reject it. `duty_rate` applies the preference and returns a reason string noting the risk;
EXC-07 raises the flag with a quantified worst case in `financial_impact`. Denying the
preference in the duty engine would silently pre-decide a customs judgement and hide a real
exposure behind a confident-looking number.

---

## 12. Duty engine

```python
def duty_rate(hs_code, coo, sailing_date, cfg) -> tuple[Decimal, str]:
    """Returns (rate, human-readable reason). The reason is displayed and audit-logged."""
```

1. No CoO → general rate from config, reason "no certificate of origin"
2. `hs_code` not in the CoO's covered set → general rate, reason naming code and certificate
3. CoO covers it → preferential rate, reason naming agreement and certificate; if the CoO is
   post-dated and not retrospective, append an AT RISK note — but do not change the rate
4. Rate determined **per invoice line**, never once per dispatch. That is the specific defect
   in the spreadsheet this replaces.

---

## 13. Allocation and valuation

### Money is a value object, not a Decimal

```python
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str          # ISO 4217
    def __add__(self, other): assert self.currency == other.currency; ...
    def __mul__(self, rate: Decimal) -> "Money": ...
```

Every monetary value in the engine, the schemas and the ORM is a `Money`. Arithmetic
between different currencies raises. `NUMERIC(14,4)` plus a `currency` column in Postgres.

v1 restricts a dispatch to one invoice currency — but that restriction lives in EXC-09,
a rule that fires and is visible to the user. It must NOT be an assumption baked into the
arithmetic. `share_i = fob_i / sum(fob)` silently assumes commensurability; with bare
Decimals that assumption spreads into allocation, valuation, levies and every test, and
supporting multi-currency in v2 becomes a rewrite rather than a change to one rule.

### Scope-agnostic allocation

```python
def allocate(invoices: list[Invoice], cost_lines: list[CostLine], cfg) -> list[Allocation]
```

`allocate` must never reach for "the dispatch's B/L". It receives an explicit scope. In v1
the caller always passes the whole dispatch; in v2 a consolidated dispatch calls it once per
B/L group and a partial clearance calls it on a subset — with no change to the math.

All arithmetic in `Decimal`, rounding per config.

```
share_i         = fob_i / sum(fob)                      # or weight/volume per config
for each cost line c:
    alloc_i_c   = round(total_c * share_i)
insured_i       = round((fob_i + alloc_i_freight) * insurance.coverage_pct)
premium_i       = allocate(printed_insurance_premium, share_i)
customs_value_i = fob_i + sum(alloc_i_c for c in valuation.components)
levies_i        = apply_levies(customs_value_i, duty_rate(...), cfg)
landed_cost_i   = fob_i + sum(all alloc_i_c) + sum(non-recoverable levies)
```

After allocation assert each `sum(alloc_i_c) == total_c`. Rounding leaves a residual of a
cent or two — assign it per `allocation.residual_to` and record that it was done. Never let
allocated costs silently disagree with the source figure.

The printed/evidenced insurance premium is the insurance cost used in customs value. The
configured coverage percentage is used only by EXC-04 to compare the sum insured with the
required coverage. An `estimated_premium_rate` is a visibly derived fallback when no premium
is evidenced; it must never replace a printed premium.

Output two views: the **declaration view** (dutiable components only) and the **landed cost
view** (everything). Same engine.

---

## 14. API

```
POST   /api/intake/batches                              multipart intake + job
POST   /api/dispatches/{id}/documents                   multipart, incremental
GET    /api/jobs/{id}                                   stage, progress, failures, elapsed time
GET    /api/dispatches/{id}                             full effective review state
POST   /api/dispatches/{id}/run                         idempotent affected-stage rerun
PATCH  /api/dispatches/{id}/fields/{field_path}         append correction + required reason
POST   /api/exceptions/{id}/accept-risk                 demo rationale required
GET    /api/dispatches/{id}/exports/reconciliation.xlsx
GET    /api/dispatches/{id}/exports/din.json
GET    /api/dispatches/{id}/exports/din.pdf
```

`/run` is a database-backed background job, not a synchronous request. A separate worker
claims queued rows with `FOR UPDATE SKIP LOCKED`, so work survives API and worker restarts.
Token usage and provider cost are retained as operator telemetry in PostgreSQL and exposed
only through the local operator reporting script. They are not returned to the browser.

---

## 15. Frontend

Single review screen, three panes.

- **Left** — expected-versus-received document checklist, type badge, classify confidence,
  OCR-sourced marker. Click opens the PDF.
- **Centre** — extracted fields by document. Value, confidence pill (green >0.9, amber
  0.7–0.9, red <0.7), and `source_text`. Clicking opens the PDF at the right page with the
  cited page available in the embedded PDF viewer. Fields are editable; edits are audited
  with the original preserved. Bounding-box highlighting is deferred.
- **Right** — exception queue, CRITICAL first. Detail, suggested action, links to both
  source fields and financial impact where quantified. Demo risk acceptance demands a
  typed rationale and creates an audit event; it is explicitly not authorization.

Below: the allocation table with the duty reason string per line, the levy breakdown by code
(labels from config — never hardcode "IVA"), and the total payable in both source and
settlement currency with the FX rate and date shown.

No approval or filing control is implemented in the prototype.

Exports use the contact's `PRORRATEO MASTER.xlsx` as an immutable base. The generated copy
preserves `Prorrateo General` and `Prorrateo resumen`, then appends `Resumen`, `Documentos`,
`Extracciones`, `Validaciones`, `Prorrateo`, `Tributos` and `Trazabilidad`. It replaces the
estimated insurance cost with the fully allocated printed premium and records per-line duty
rates without modifying the source workbook. `Resumen` and `Trazabilidad` record the
SHA-256 hashes of the source template, pinned jurisdiction config and calculation inputs.
DIN JSON and PDF outputs must show
`BORRADOR DEMO — NO APTO PARA PRESENTACIÓN.` prominently.

---

## 16. Testing — write these first

`fixtures/ANSWER_KEY.json` is ground truth for both scenarios: full per-line allocation,
levy breakdown, FX conversion, and the expected verdict on every rule.

1. `test_levies.py` — the Chile stack produces two levies; **loading `peru.yaml` produces
   four with the cascading base, same functions, zero code changes**. Also: `eval_base`
   rejects function calls, attribute access, and unknown names.
2. `test_allocation.py` — reproduces the answer key exactly, to the cent, from hand-written
   input JSON. Residual assignment verified.
3. `test_rules.py` — scenario A all pass; scenario B produces exactly the expected
   CRITICAL/WARNING set with detail strings naming the right numbers. EXC-07 must NOT alter
   any rate.
4. `test_duty.py` — all branches, including the post-dated-CoO reason string.
5. `test_valuation.py` — a config with `components: [fob]` excludes freight and insurance
   from customs value while still allocating them for landed cost.
6. `test_money.py` — adding two different currencies raises. Allocation over a mixed-currency
   invoice set raises rather than silently summing.
7. `test_tenancy.py` — introspect every tenant-owned SQLAlchemy model and fail if any lacks
   `org_id`. Cross-organisation authorization tests begin when authentication is introduced.
8. `test_config_versioning.py` — a dispatch pinned to a config with a 6% rate still computes
   6% after a newer config version with a different rate is loaded.

All green before a single model call is written.

Fixture acceptance is exact: Scenario A has eleven PASS results, allocates USD 38.66 of
printed premium, and yields USD 11,065.35 / CLP 10,660,911 payable. Scenario B has exactly
three CRITICAL and four WARNING failures plus four PASS results, allocates USD 39.28 of
printed premium, and provisionally yields USD 13,719.81 / CLP 13,218,351 payable.

Scenario C is a performance fixture rather than new fiscal ground truth: 29 uploaded PDFs,
including 24 invoices and consolidated packing/origin documents. It must extract 29/29,
produce 11 PASS results and total USD 47,701.97 payable under the same provisional Chile
configuration. It demonstrates within-dispatch volume, not multi-dispatch fleet capacity.

---

## 17. Build order

**M1 — deterministic core.** No model, no UI. Jurisdiction loader, levy evaluator, duty,
allocation, valuation, FX, rules, Postgres and migrations. Full test suite green.

**M2 — extraction.** Classify and extract via OpenRouter with the job runner. Document I/O
fans out with bounded concurrency; database writes and reconciliation remain deterministic.
All fixture folders go from raw PDFs to a complete reconciled dispatch, zero manual entry.
Log tokens and cost per dispatch for the operator, never in the end-user progress UI.

**M3 — review UI.** Three panes, PDF-page access, corrections and demo risk acceptance with audit.

**M4 — harden.** Docker one-command startup, OCR fallback for scans, error states for
missing documents and API timeouts, DIN adapter output.

Do not start M2 before M1 is green. The deterministic core carries the value and is the only
part that can be proven correct. An agent left alone will reach for the model call first
because it is the interesting part, and you will end up with a good extractor sitting on
unverified arithmetic.

---

## 18. Non-negotiables

1. **No `float` near money, and no bare `Decimal` either.** Every monetary value is a
   `Money(amount, currency)`. `NUMERIC(14,4)` + a currency column in Postgres.
2. **No rate, tax name, percentage or base formula in Python.** All of it in the
   jurisdiction YAML. Grep for `0.06`, `0.19`, `1.15`, `"IVA"` — zero hits outside
   `jurisdictions/` and tests.
3. **No model call decides anything.** The model reads and returns JSON. Every comparison,
   computation and verdict is a tested Python function.
4. **Every extracted field carries page and source_text.** A value without provenance is a bug.
5. **The demo never files.** Accepting risk requires a note and an audit row, but is not an
   authorization decision.
6. **One module talks to the LLM.** `app/llm/client.py`. Model IDs from env.
7. **Do not rasterize PDFs for text-layer documents.** Send the file, `engine: native`.
8. **Never invent a value to satisfy a schema.** Null plus zero confidence, then surface it.
9. **`eval_base` uses a restricted AST walk, never `eval()`.** A config file is a code path.
10. **`peru.yaml` is a test fixture, not a product.** Never referenced outside tests.
11. **`org_id` on every tenant-owned table.** Authorization and isolation remain deferred.
12. **Every dispatch pins its jurisdiction config version.** Recomputation uses the pinned
    version, never the current file.
13. **`allocate()` takes an explicit scope.** It must never reach for "the dispatch's B/L".
14. **`page` and `source_text` are set only when `provenance == EXTRACTED`.** Never fake a
    page reference for an inferred or derived value.

## 19. Anti-patterns

- Asking the model to "check if these documents are consistent". That is `rules.py`.
- Asking the model to compute customs value or any levy. That is `levies.py`.
- One duty rate per dispatch. It is per line, driven by CoO coverage.
- Auto-correcting a value that looks like a typo. Raise an exception instead.
- Hardcoding two levies because Chile has two. Iterate the configured stack.
- Naming a levy "IVA" in code or UI. Read the label from config.
- Reporting a total only in the invoice currency. Always show the settlement currency too.
- Silently dropping an unclassifiable document. Surface it for the user to label.
- Denying FTA preference in the duty engine because a certificate looks irregular.
  Apply the rate, flag the risk, quantify the exposure, let a human decide.
- Building a second jurisdiction adapter speculatively.
