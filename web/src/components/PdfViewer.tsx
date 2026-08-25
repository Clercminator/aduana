import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import workerSrc from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import { assetUrl } from "../api";
import type { DocumentRecord } from "../types";

pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;
const pdfOptions = { standardFontDataUrl: "/" };

export function PdfViewer({ document, initialPage = 1 }: { document: DocumentRecord; initialPage?: number }) {
  const [pages, setPages] = useState(1);
  const [page, setPage] = useState(initialPage);
  const url = assetUrl(document.file_url);
  return (
    <section className="pdf-panel">
      <div className="panel-heading compact">
        <div>
          <span className="kicker">Vista del documento</span>
          <h2 title={document.filename}>{document.filename}</h2>
        </div>
        <a className="icon-button" href={url} target="_blank" rel="noreferrer" title="Abrir PDF en otra pestaña"><ExternalLink size={16} /></a>
      </div>
      <div className="pdf-canvas-wrap">
        <Document file={url} options={pdfOptions} loading={<div className="pdf-placeholder">Cargando PDF…</div>} error={<div className="pdf-placeholder">No se pudo mostrar el PDF.</div>} onLoadSuccess={({ numPages }) => { setPages(numPages); setPage(Math.min(Math.max(initialPage, 1), numPages)); }}>
          <Page pageNumber={page} width={460} renderTextLayer={false} renderAnnotationLayer={false} />
        </Document>
      </div>
      <div className="pdf-toolbar">
        <button className="icon-button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}><ChevronLeft size={17} /></button>
        <span>Página {page} de {pages}</span>
        <button className="icon-button" disabled={page >= pages} onClick={() => setPage((value) => value + 1)}><ChevronRight size={17} /></button>
      </div>
    </section>
  );
}
