import { AlertTriangle, CheckCircle2, Download, FileDown, FilePlus2, FileText, RefreshCw, Search, Sheet } from "lucide-react";
import { lazy, Suspense, useMemo, useRef, useState } from "react";
import { API_ROOT, api } from "../api";
import type { DispatchState, FlatField, Job, Rule } from "../types";
import { CalculationTable } from "./CalculationTable";
import { ExceptionsPanel } from "./ExceptionsPanel";
import { ExtractionFields } from "./ExtractionFields";

const PdfViewer = lazy(() => import("./PdfViewer").then((module) => ({ default: module.PdfViewer })));

const docLabels: Record<string, string> = {
  dispatch_instruction: "Instrucción de despacho",
  bill_of_lading: "Bill of Lading",
  commercial_invoice: "Factura comercial",
  packing_list: "Packing list",
  insurance_certificate: "Certificado de seguro",
  certificate_of_origin: "Certificado de origen",
};

type Props = {
  state: DispatchState;
  lastJob: Job | null;
  onRefresh: () => Promise<void>;
  onJob: (jobId: string) => void;
};

export function ReviewWorkspace({ state, lastJob, onRefresh, onJob }: Props) {
  const [selectedId, setSelectedId] = useState(state.documents[0]?.id || "");
  const [selectedPage, setSelectedPage] = useState(1);
  const [query, setQuery] = useState("");
  const addRef = useRef<HTMLInputElement>(null);
  const calculation = state.calculation;
  const selected = state.documents.find((document) => document.id === selectedId) || state.documents[0];
  const visibleDocs = useMemo(() => state.documents.filter((document) => `${document.filename} ${document.doc_type}`.toLowerCase().includes(query.toLowerCase())), [query, state.documents]);
  const checklist = useMemo(() => {
    const received = new Map<string, number>();
    for (const document of state.documents) {
      if (document.doc_type) received.set(document.doc_type, (received.get(document.doc_type) || 0) + 1);
    }
    const required = [
      ["dispatch_instruction", 1] as const,
      ...Object.entries(state.dispatch.expected_documents).map(([type, count]) => [type, Number(count)] as const),
    ];
    return required.map(([type, expected]) => ({ type, expected, received: received.get(type) || 0 }));
  }, [state.dispatch.expected_documents, state.documents]);
  const expectedTotal = checklist.reduce((total, item) => total + item.expected, 0);
  const receivedTotal = checklist.reduce((total, item) => total + Math.min(item.received, item.expected), 0);
  const missingTotal = expectedTotal - receivedTotal;
  const incompleteCount = state.documents.filter((document) => document.doc_type === "unknown" || document.extraction_status !== "done").length;
  const reviewComplete = missingTotal === 0 && incompleteCount === 0;
  const exportBase = `${API_ROOT}/dispatches/${state.dispatch.id}/exports`;
  const declarationCount = new Set(calculation?.lines.map((line) => line.invoice) || []).size;

  async function correct(field: FlatField, value: string, reason: string) {
    const result = await api.correct(state.dispatch.id, `${selected.id}:${field.path}.value`, value, reason);
    onJob(result.job_id);
  }

  async function accept(rule: Rule, rationale: string) {
    if (!rule.exception_id) throw new Error("La excepción aún no tiene registro persistido");
    await api.acceptRisk(rule.exception_id, rationale);
    await onRefresh();
  }

  function findCitationPage(value: unknown, field: string): number {
    if (!value || typeof value !== "object") return 1;
    if (Array.isArray(value)) {
      for (const item of value) {
        const page = findCitationPage(item, field);
        if (page > 1) return page;
      }
      return 1;
    }
    const record = value as Record<string, unknown>;
    const cited = record[field];
    if (cited && typeof cited === "object" && !Array.isArray(cited)) {
      const page = Number((cited as Record<string, unknown>).page);
      if (Number.isInteger(page) && page > 0) return page;
    }
    for (const child of Object.values(record)) {
      const page = findCitationPage(child, field);
      if (page > 1) return page;
    }
    return 1;
  }

  function openSource(reference: Rule["source_refs"][number]) {
    const document = state.documents.find((item) => item.doc_type === reference.document);
    if (!document) return;
    setSelectedId(document.id);
    setSelectedPage(findCitationPage(document.extraction, reference.field));
  }

  return (
    <main className="review-page">
      <section className="dispatch-banner">
        <div><span className="kicker">Despacho en revisión</span><h1>{state.dispatch.despacho_no || "Sin número"}</h1><p>{state.dispatch.referencia || "Sin referencia"} · Chile · Importación para consumo</p></div>
        <div className={`banner-status ${reviewComplete ? "" : "incomplete"}`}>{reviewComplete ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}<span>{reviewComplete ? "Expediente completo" : "Expediente incompleto"}<strong>{receivedTotal}/{expectedTotal} requeridos{lastJob?.elapsed_seconds ? ` · Procesado en ${lastJob.elapsed_seconds.toFixed(1)} s` : ""}</strong></span></div>
        <div className="export-cluster">
          <div className="master-export">
            <a className="button secondary" href={`${exportBase}/reconciliation.xlsx`}><Sheet size={16} /> PRORRATEO MASTER completado</a>
            <small>Conserva las dos hojas operativas originales</small>
          </div>
          <a className="button secondary" href={`${exportBase}/din.json`}><FileDown size={16} /> {declarationCount} DIN JSON</a>
          <a className="button primary" href={`${exportBase}/din.pdf`}><Download size={16} /> {declarationCount} DIN PDF</a>
        </div>
      </section>

      <section className="review-grid">
        <aside className="documents-panel">
          <div className="panel-heading"><div><span className="kicker">Expediente</span><h2>Documentos</h2></div><button className="icon-button" title="Agregar PDFs" onClick={() => addRef.current?.click()}><FilePlus2 size={17} /></button></div>
          <div className="document-search"><Search size={14} /><input aria-label="Buscar documentos" placeholder="Buscar documento" value={query} onChange={(event) => setQuery(event.target.value)} /></div>
          <details className="expected-checklist" open={!reviewComplete}>
            <summary><span>{receivedTotal} de {expectedTotal} archivos requeridos</span>{missingTotal > 0 ? <strong>{missingTotal} faltantes</strong> : <CheckCircle2 size={15} />}</summary>
            <div>{checklist.map((item) => <span key={item.type} className={item.received >= item.expected ? "received" : "missing"}>{item.received >= item.expected ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}<span>{docLabels[item.type] || item.type}</span><strong>{item.received}/{item.expected}</strong></span>)}</div>
          </details>
          <div className="document-list">{visibleDocs.map((document) => { const ready = document.doc_type !== "unknown" && document.extraction_status === "done"; return <button className={`document-item ${document.id === selected.id ? "selected" : ""}`} key={document.id} onClick={() => { setSelectedId(document.id); setSelectedPage(1); }}><FileText size={18} /><span><strong>{docLabels[document.doc_type || ""] || (document.doc_type === "unknown" ? "Sin clasificar" : "Documento")}</strong><small title={document.filename}>{document.filename}</small></span>{ready ? <CheckCircle2 size={15} className="doc-ok" /> : <AlertTriangle size={15} className="doc-error" />}</button>; })}</div>
          <button className="button add-files" onClick={() => addRef.current?.click()}><FilePlus2 size={16} /> Agregar documentos</button>
          <input ref={addRef} className="visually-hidden" type="file" accept="application/pdf" multiple onChange={async (event) => { if (!event.target.files?.length) return; const result = await api.addDocuments(state.dispatch.id, event.target.files); onJob(result.job_id); }} />
        </aside>

        <div className="center-stack">
          {selected && <ExtractionFields key={`${selected.id}-fields`} document={selected} onCorrect={correct} />}
          {selected && <Suspense fallback={<section className="pdf-panel pdf-placeholder">Preparando visor…</section>}><PdfViewer key={`${selected.id}-${selectedPage}`} document={selected} initialPage={selectedPage} /></Suspense>}
        </div>

        {calculation && <ExceptionsPanel rules={calculation.rules} onAccept={accept} onSource={openSource} />}
      </section>

      {calculation && <CalculationTable calculation={calculation} />}
      <button className="floating-refresh" title="Actualizar datos" onClick={onRefresh}><RefreshCw size={16} /></button>
    </main>
  );
}
