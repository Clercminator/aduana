import { FileSearch, FolderOpen, Sheet, ShieldAlert, X } from "lucide-react";

export function HelpDialog({ onClose }: { onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="modal help-dialog" role="dialog" aria-modal="true" aria-labelledby="help-title">
        <button className="icon-button help-close" title="Cerrar ayuda" onClick={onClose}><X size={16} /></button>
        <span className="kicker">Guía rápida</span>
        <h2 id="help-title">Guía de demostración</h2>
        <ol>
          <li><FolderOpen size={17} /><span><strong>Cargue el expediente sin ordenar</strong>Use ocho PDFs para A/B, 45 PDFs para volumen C o seis PDFs para CIF D.</span></li>
          <li><FileSearch size={17} /><span><strong>Revise evidencia y controles provisionales</strong>Abra fuentes, contraste la página y corrija solo con un motivo escrito.</span></li>
          <li><ShieldAlert size={17} /><span><strong>Explique el riesgo</strong>El escenario B demuestra tres alertas críticas y cuatro advertencias.</span></li>
          <li><Sheet size={17} /><span><strong>Descargue el PRORRATEO MASTER completado</strong>La copia conserva las dos hojas operativas originales y agrega trazabilidad.</span></li>
        </ol>
        <p>Use C para demostrar volumen y velocidad, A para el flujo limpio y B para detección e impacto financiero.</p>
        <div className="help-notice">Solo use documentos sintéticos. La aceptación de riesgo es trazabilidad de demo, no autorización.</div>
        <div className="modal-actions"><button className="button primary" onClick={onClose}>Entendido</button></div>
      </section>
    </div>
  );
}
