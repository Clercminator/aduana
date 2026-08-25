import { CircleHelp, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import imrLogoUrl from "./assets/imr-logo.png";
import { IntakeView } from "./components/IntakeView";
import { JobProgress } from "./components/JobProgress";
import { ReviewWorkspace } from "./components/ReviewWorkspace";
import { HelpDialog } from "./components/HelpDialog";
import type { DispatchState, Job } from "./types";

export default function App() {
  const [dispatchId, setDispatchId] = useState<string | null>(() => localStorage.getItem("demo_dispatch_id"));
  const [job, setJob] = useState<Job | null>(null);
  const [state, setState] = useState<DispatchState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);

  const refresh = useCallback(async () => {
    if (!dispatchId) return;
    try { setState(await api.dispatch(dispatchId)); } catch (caught) { setError(caught instanceof Error ? caught.message : "No se pudo cargar el despacho"); }
  }, [dispatchId]);

  const followJob = useCallback((jobId: string) => {
    setBusy(true);
    setError(null);
    const poll = async () => {
      try {
        const current = await api.job(jobId);
        setJob(current);
        if (current.status === "done") { setBusy(false); setDispatchId(current.dispatch_id); localStorage.setItem("demo_dispatch_id", current.dispatch_id); setState(await api.dispatch(current.dispatch_id)); return; }
        if (current.status === "failed") { setBusy(false); setError(current.error || "El proceso falló"); return; }
        window.setTimeout(poll, 500);
      } catch (caught) { setBusy(false); setError(caught instanceof Error ? caught.message : "No se pudo consultar el proceso"); }
    };
    void poll();
  }, []);

  useEffect(() => {
    if (!dispatchId || busy || state) return;
    let active = true;
    api.dispatch(dispatchId).then((result) => {
      if (active) setState(result);
    }).catch((caught: unknown) => {
      if (active) setError(caught instanceof Error ? caught.message : "No se pudo cargar el despacho");
    });
    return () => { active = false; };
  }, [busy, dispatchId, state]);

  async function startDemo(scenario: "A" | "B" | "C" | "D") {
    try { setBusy(true); setError(null); setState(null); const result = await api.loadDemo(scenario); setDispatchId(result.dispatch_id); followJob(result.job_id); } catch (caught) { setBusy(false); setError(caught instanceof Error ? caught.message : "No se pudo iniciar la demo"); }
  }

  async function upload(files: FileList) {
    try { setBusy(true); setError(null); const result = await api.upload(files); setDispatchId(result.dispatch_id); followJob(result.job_id); } catch (caught) { setBusy(false); setError(caught instanceof Error ? caught.message : "No se pudo cargar la carpeta"); }
  }

  function reset() { localStorage.removeItem("demo_dispatch_id"); setDispatchId(null); setState(null); setJob(null); setBusy(false); setError(null); }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={reset} aria-label="IMR Tech Control Aduanero — ir al inicio">
          <img className="brand-logo" src={imrLogoUrl} alt="" width="813" height="327" />
          <small>Control Aduanero</small>
        </button>
        <nav><span className="environment-pill">DEMO LOCAL</span><button className="nav-button" onClick={reset}><RotateCcw size={15} /> Nuevo despacho</button><button className="nav-button" onClick={() => setHelpOpen(true)}><CircleHelp size={15} /> Ayuda</button></nav>
      </header>
      {busy && job ? <JobProgress job={job} /> : state ? <ReviewWorkspace state={state} lastJob={job} onRefresh={refresh} onJob={followJob} /> : <IntakeView busy={busy} error={error} onDemo={startDemo} onUpload={upload} />}
      <footer className="global-warning">ENTORNO DE DEMOSTRACIÓN · Documentos sintéticos · Controles aduaneros pendientes de validación</footer>
      {helpOpen ? <HelpDialog onClose={() => setHelpOpen(false)} /> : null}
    </div>
  );
}
