import { AlertOctagon, AlertTriangle, CheckCircle2, ChevronRight, FileText, Info, ShieldAlert } from "lucide-react";
import { useState } from "react";
import type { Rule } from "../types";

const severityRank = { CRITICAL: 0, WARNING: 1, INFO: 2 };

function impact(rule: Rule): string | null {
  if (!rule.financial_impact) return null;
  const preferred = rule.financial_impact.total_under_declared || rule.financial_impact.exposure || Object.values(rule.financial_impact)[0];
  return preferred ? `Impacto estimado: USD ${preferred}` : null;
}

type Props = {
  rules: Rule[];
  onAccept: (rule: Rule, rationale: string) => Promise<void>;
  onSource: (reference: Rule["source_refs"][number]) => void;
};

export function ExceptionsPanel({ rules, onAccept, onSource }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [accepting, setAccepting] = useState<Rule | null>(null);
  const [rationale, setRationale] = useState("");
  const failed = rules.filter((rule) => rule.status === "FAIL").sort((a, b) => severityRank[a.severity] - severityRank[b.severity]);
  const passed = rules.filter((rule) => rule.status === "PASS");
  const skipped = rules.filter((rule) => rule.status === "SKIPPED");

  return (
    <section className="exceptions-panel">
      <div className="panel-heading">
        <div><span className="kicker">{rules.length} controles provisionales</span><h2>Excepciones</h2></div>
        <span className={`danger-count ${failed.length === 0 && skipped.length > 0 ? "skipped" : ""}`}>{failed.length + skipped.length}</span>
      </div>
      <div className="rule-summary">
        <span className="critical-dot">{failed.filter((rule) => rule.severity === "CRITICAL").length} críticas</span>
        <span className="warning-dot">{failed.filter((rule) => rule.severity === "WARNING").length} advertencias</span>
        {skipped.length > 0 ? <span className="skipped-dot">{skipped.length} pendientes</span> : null}
        <span className="pass-dot">{passed.length} conformes</span>
      </div>
      <div className="exception-list">
        {failed.map((rule) => {
          const isOpen = expanded === rule.id;
          const Icon = rule.severity === "CRITICAL" ? AlertOctagon : AlertTriangle;
          return (
            <article className={`exception-card ${rule.severity.toLowerCase()}`} key={rule.id}>
              <button className="exception-main" onClick={() => setExpanded(isOpen ? null : rule.id)}>
                <Icon size={18} />
                <span><small>{rule.id} · {rule.severity === "CRITICAL" ? "Crítica" : "Advertencia"}</small><strong>{rule.title}</strong></span>
                <ChevronRight className={isOpen ? "rotated" : ""} size={17} />
              </button>
              {isOpen && <div className="exception-detail"><p>{rule.detail}</p>{impact(rule) && <strong>{impact(rule)}</strong>}{rule.suggested_action && <p><Info size={13} /> {rule.suggested_action}</p>}{rule.source_refs?.length > 0 && <div className="source-links">{rule.source_refs.map((reference, index) => <button key={`${reference.document}-${reference.field}-${index}`} className="text-button" onClick={() => onSource(reference)}><FileText size={14} /> Ver fuente {index + 1}</button>)}</div>}{rule.accepted_rationale ? <span className="accepted"><CheckCircle2 size={14} /> Riesgo aceptado: {rule.accepted_rationale}</span> : <button className="text-button" onClick={() => { setAccepting(rule); setRationale(""); }}><ShieldAlert size={14} /> Aceptar riesgo de demo</button>}</div>}
            </article>
          );
        })}
      </div>
      {skipped.length > 0 ? <details className="skipped-rules" open><summary><AlertTriangle size={16} /> {skipped.length} controles provisionales pendientes por documentos faltantes</summary>{skipped.map((rule) => <div key={rule.id}><span>{rule.id}</span><strong>{rule.title}</strong><small>{rule.detail}</small></div>)}</details> : null}
      <details className="passed-rules"><summary><CheckCircle2 size={16} /> {passed.length} controles provisionales conformes</summary>{passed.map((rule) => <div key={rule.id}><span>{rule.id}</span>{rule.title}</div>)}</details>
      {accepting && (
        <div className="modal-backdrop">
          <form className="modal" onSubmit={async (event) => { event.preventDefault(); await onAccept(accepting, rationale); setAccepting(null); }}>
            <span className="kicker">Aceptación solo para demo</span><h2>{accepting.title}</h2>
            <p>Esto registra una decisión auditable; no concede autorización operativa.</p>
            <label>Justificación obligatoria<textarea autoFocus minLength={3} required value={rationale} onChange={(event) => setRationale(event.target.value)} /></label>
            <div className="modal-actions"><button type="button" className="button secondary" onClick={() => setAccepting(null)}>Cancelar</button><button className="button danger">Registrar aceptación</button></div>
          </form>
        </div>
      )}
    </section>
  );
}
