import { Check, FileText, Pencil, Quote } from "lucide-react";
import { useMemo, useState } from "react";
import type { DocumentRecord, FlatField } from "../types";

const labels: Record<string, string> = {
  despacho_no: "N.º despacho",
  referencia: "Referencia",
  bl_number: "Bill of Lading",
  invoice_number: "Factura",
  invoice_date: "Fecha factura",
  invoice_total: "Total factura",
  freight_amount: "Flete",
  premium: "Prima impresa",
  sum_insured: "Monto asegurado",
  gross_weight_kg: "Peso bruto kg",
  package_count: "Bultos",
  container_number: "Contenedor",
  certificate_number: "Certificado",
  issue_date: "Fecha de emisión",
  issuing_authority: "Autoridad emisora",
  consignee_name: "Consignatario",
  importer_name: "Importador",
  hs_code: "Código HS",
  origin_criterion: "Criterio de origen",
  net_weight_or_quantity: "Peso neto o cantidad",
  weight_or_quantity_unit: "Unidad de peso o cantidad",
  quantity: "Cantidad",
  unit_price: "Precio unitario",
  line_total: "Total línea",
};

function flatten(value: unknown, path = ""): FlatField[] {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const record = value as Record<string, unknown>;
    if ("value" in record && "provenance" in record && "confidence" in record) {
      const key = path.split(".").at(-1) || path;
      return [{ ...(record as unknown as Omit<FlatField, "path" | "label">), path, label: labels[key] || key.replaceAll("_", " ") }];
    }
    return Object.entries(record).flatMap(([key, child]) => flatten(child, path ? `${path}.${key}` : key));
  }
  if (Array.isArray(value)) return value.flatMap((child, index) => flatten(child, `${path}.${index}`));
  return [];
}

type Props = {
  document: DocumentRecord;
  onCorrect: (field: FlatField, value: string, reason: string) => Promise<void>;
};

export function ExtractionFields({ document, onCorrect }: Props) {
  const fields = useMemo(() => flatten(document.extraction).filter((field) => field.value !== null), [document.extraction]);
  const [editing, setEditing] = useState<FlatField | null>(null);
  const [value, setValue] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  return (
    <section className="fields-panel">
      <div className="panel-heading compact">
        <div><span className="kicker">Extracción citada</span><h2>Campos detectados</h2></div>
        <span className="confidence-pill"><Check size={13} /> {fields.length} campos</span>
      </div>
      <div className="field-list">
        {fields.map((field) => (
          <article className="field-row" key={field.path}>
            <div className="field-meta">
              <span>{field.label}</span>
              <strong>{String(field.value)}</strong>
              <small><FileText size={12} /> pág. {field.page || "—"} · {Math.round(Number(field.confidence) * 100)}% · {field.provenance === "manual" ? "corregido" : document.ocr_used ? "OCR" : "texto PDF"}</small>
            </div>
            <button className="icon-button subtle" title={`Editar ${field.label}`} onClick={() => { setEditing(field); setValue(String(field.value)); setReason(""); }}><Pencil size={15} /></button>
            {field.source_text && <blockquote><Quote size={12} /> {field.source_text}</blockquote>}
          </article>
        ))}
      </div>
      {editing && (
        <div className="modal-backdrop" role="presentation">
          <form className="modal" onSubmit={async (event) => { event.preventDefault(); setSaving(true); try { await onCorrect(editing, value, reason); setEditing(null); } finally { setSaving(false); } }}>
            <span className="kicker">Corrección auditable</span>
            <h2>{editing.label}</h2>
            <label>Valor corregido<input autoFocus value={value} onChange={(event) => setValue(event.target.value)} required /></label>
            <label>Motivo de la corrección<textarea value={reason} onChange={(event) => setReason(event.target.value)} minLength={3} required /></label>
            <div className="modal-actions"><button type="button" className="button secondary" onClick={() => setEditing(null)}>Cancelar</button><button className="button primary" disabled={saving}>Guardar y recalcular</button></div>
          </form>
        </div>
      )}
    </section>
  );
}
