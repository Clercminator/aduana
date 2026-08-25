import { Calculator, FileSearch, FolderOpen, Play, ScanText, Sheet, ShieldCheck, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";

const automationSteps = [
  { label: "Documentos", Icon: FolderOpen },
  { label: "Extracción con evidencia", Icon: ScanText },
  { label: "Controles", Icon: FileSearch },
  { label: "Prorrateo", Icon: Calculator },
  { label: "Excel", Icon: Sheet },
];

type Props = {
  busy: boolean;
  error: string | null;
  onDemo: (scenario: "A" | "B" | "C" | "D") => void;
  onUpload: (files: FileList) => void;
};

export function IntakeView({ busy, error, onDemo, onUpload }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const folderRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  return (
    <main className="intake-shell">
      <section className="intake-copy">
        <div className="eyebrow"><ShieldCheck size={15} /> Automatización aduanera verificable</div>
        <h1>De documentos dispersos a un despacho listo para revisar.</h1>
        <p>
          Clasifica PDFs, extrae valores con cita, ejecuta doce controles provisionales y prepara el
          prorrateo, los tributos y una DIN por factura en minutos.
        </p>
        <ol className="automation-flow" aria-label="Flujo automatizado del despacho">
          {automationSteps.map(({ label, Icon }) => (
            <li key={label}><Icon size={17} /><span>{label}</span></li>
          ))}
        </ol>
        <div className="trust-row">
          <span><ShieldCheck size={16} /> Evidencia preservada</span>
          <span><ShieldCheck size={16} /> Cálculo determinista</span>
          <span><ShieldCheck size={16} /> Uso local / LAN</span>
        </div>
      </section>

      <section
        className={`drop-card ${dragging ? "dragging" : ""}`}
        onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (event.dataTransfer.files.length) onUpload(event.dataTransfer.files);
        }}
      >
        <UploadCloud size={40} strokeWidth={1.5} />
        <h2>Cargar carpeta de despacho</h2>
        <p>Seleccione o arrastre los PDFs sin ordenar. Los nombres no se usan para clasificar.</p>
        <div className="upload-actions">
          <button className="button primary" disabled={busy} onClick={() => folderRef.current?.click()}>
            <FolderOpen size={17} /> Elegir carpeta
          </button>
          <button className="button secondary" disabled={busy} onClick={() => fileRef.current?.click()}>
            Elegir archivos
          </button>
        </div>
        <input
          ref={folderRef}
          className="visually-hidden"
          type="file"
          accept="application/pdf"
          multiple
          {...({ webkitdirectory: "" } as React.InputHTMLAttributes<HTMLInputElement>)}
          onChange={(event) => event.target.files && onUpload(event.target.files)}
        />
        <input ref={fileRef} className="visually-hidden" type="file" accept="application/pdf" multiple onChange={(event) => event.target.files && onUpload(event.target.files)} />
        {error && <div className="inline-error" role="alert">{error}</div>}
      </section>

      <section className="demo-strip">
        <div>
          <strong>¿Quiere ver el flujo completo?</strong>
          <span>Use documentos sintéticos preparados para una demostración repetible.</span>
        </div>
        <button className="button ghost" disabled={busy} onClick={() => onDemo("A")}><Play size={16} /> Escenario A · limpio</button>
        <button className="button warning" disabled={busy} onClick={() => onDemo("B")}><Play size={16} /> Escenario B · 7 alertas</button>
        <button className="button volume" disabled={busy} onClick={() => onDemo("C")}><Play size={16} /> Escenario C · 45 PDFs</button>
        <button className="button ghost" disabled={busy} onClick={() => onDemo("D")}><Play size={16} /> Escenario D · CIF</button>
      </section>
    </main>
  );
}
