export type CitedValue = {
  value: unknown;
  provenance: "extracted" | "manual" | "derived" | "inferred";
  page?: number | null;
  source_text?: string | null;
  confidence: string;
};

export type DocumentRecord = {
  id: string;
  filename: string;
  content_hash: string;
  doc_type: string | null;
  classify_confidence: string | null;
  page_count: number | null;
  has_text_layer: boolean | null;
  ocr_used: boolean;
  file_url: string;
  extraction: Record<string, unknown> | null;
  extraction_status: string;
};

export type Rule = {
  id: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  status: "PASS" | "FAIL" | "SKIPPED";
  title: string;
  detail: string;
  suggested_action?: string | null;
  financial_impact?: Record<string, string> | null;
  source_refs: Array<{ document: string; field: string }>;
  exception_id?: string;
  accepted_rationale?: string | null;
};

export type CalculationLine = {
  invoice: string;
  description: string;
  hs_code: string;
  fob: string;
  share: string;
  allocations: Record<string, string>;
  residual_codes: string[];
  customs_value: string;
  duty_rate: string;
  duty_reason: string;
  levy_total: string;
  landed_cost: string;
  levies: Array<{
    code: string;
    label: string;
    base_expression: string;
    rate: string;
    amount: { amount: string; currency: string };
    recoverable: boolean;
  }>;
};

export type DispatchState = {
  dispatch: {
    id: string;
    despacho_no: string | null;
    referencia: string | null;
    status: string;
    regime: string;
    jurisdiction: string;
    jurisdiction_config_hash: string | null;
    client_config_hash: string | null;
    client: string | null;
    din_acceptance_date: string | null;
    fx_period: string | null;
    expected_documents: Record<string, number>;
    created_at: string;
  };
  documents: DocumentRecord[];
  calculation: null | {
    label: string;
    rules: Rule[];
    lines: CalculationLine[];
    totals: Record<string, any>;
    scenarios: Record<string, { total: string; settlement_total: string }>;
  };
  calculation_run: null | {
    id: string;
    input_hash: string;
    engine_version: string;
    created_at: string;
  };
  audit: Array<{ action: string; payload: Record<string, unknown>; created_at: string }>;
  artifacts: Array<{ id: string; kind: string; content_hash: string; created_at: string }>;
};

export type Job = {
  id: string;
  dispatch_id: string;
  status: "queued" | "running" | "done" | "failed";
  stage: string;
  progress: string;
  error: string | null;
  elapsed_seconds: number | null;
};

export type FlatField = CitedValue & { path: string; label: string };
