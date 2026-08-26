import { CircleHelp, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { api, ApiError } from "./api";
import imrLogoUrl from "./assets/imr-logo.png";
import { HelpDialog } from "./components/HelpDialog";
import { IntakeView } from "./components/IntakeView";
import { JobProgress } from "./components/JobProgress";
import { ReviewWorkspace } from "./components/ReviewWorkspace";
import type { DemoCatalog, DispatchState, Job } from "./types";

const storedOrgId = localStorage.getItem("demo_org_id") || "";

export default function App() {
  const [catalog, setCatalog] = useState<DemoCatalog | null>(null);
  const [selectedOrgId, setSelectedOrgId] = useState(storedOrgId);
  const [dispatchId, setDispatchId] = useState<string | null>(() =>
    storedOrgId ? localStorage.getItem(`demo_dispatch_id:${storedOrgId}`) : null,
  );
  const [job, setJob] = useState<Job | null>(null);
  const [state, setState] = useState<DispatchState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);
  const selectedAgency = catalog?.agencies.find((item) => item.organization_id === selectedOrgId);

  useEffect(() => {
    let active = true;
    api.agencies()
      .then((result) => {
        if (!active) return;
        setCatalog(result);
        const configured = result.agencies.some((item) => item.organization_id === selectedOrgId);
        if (!configured && result.agencies[0]) {
          const nextOrgId = result.agencies[0].organization_id;
          setSelectedOrgId(nextOrgId);
          localStorage.setItem("demo_org_id", nextOrgId);
          setDispatchId(localStorage.getItem(`demo_dispatch_id:${nextOrgId}`));
        }
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(caught instanceof Error ? caught.message : "No se pudo cargar la configuración");
        }
      });
    return () => {
      active = false;
    };
  }, [selectedOrgId]);

  const refresh = useCallback(async () => {
    if (!dispatchId || !selectedOrgId) return;
    try {
      setState(await api.dispatch(selectedOrgId, dispatchId));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "No se pudo cargar el despacho");
    }
  }, [dispatchId, selectedOrgId]);

  const followJob = useCallback(
    (jobId: string) => {
      if (!selectedOrgId) return;
      const orgId = selectedOrgId;
      setBusy(true);
      setError(null);
      const poll = async () => {
        try {
          const current = await api.job(orgId, jobId);
          setJob(current);
          if (current.status === "done") {
            setBusy(false);
            setDispatchId(current.dispatch_id);
            localStorage.setItem(`demo_dispatch_id:${orgId}`, current.dispatch_id);
            setState(await api.dispatch(orgId, current.dispatch_id));
            return;
          }
          if (current.status === "failed") {
            setBusy(false);
            setError(current.error || "El proceso falló");
            return;
          }
          window.setTimeout(poll, 500);
        } catch (caught) {
          setBusy(false);
          setError(caught instanceof Error ? caught.message : "No se pudo consultar el proceso");
        }
      };
      void poll();
    },
    [selectedOrgId],
  );

  useEffect(() => {
    if (!dispatchId || !selectedOrgId || busy || state) return;
    let active = true;
    api.dispatch(selectedOrgId, dispatchId)
      .then((result) => {
        if (active) setState(result);
      })
      .catch((caught: unknown) => {
        if (active) {
          localStorage.removeItem(`demo_dispatch_id:${selectedOrgId}`);
          setDispatchId(null);
          if (!(caught instanceof ApiError && caught.status === 404)) {
            setError(caught instanceof Error ? caught.message : "No se pudo cargar el despacho");
          }
        }
      });
    return () => {
      active = false;
    };
  }, [busy, dispatchId, selectedOrgId, state]);

  async function startDemo(scenario: "A" | "B" | "C" | "D") {
    if (!selectedOrgId) return;
    try {
      setBusy(true);
      setError(null);
      setState(null);
      const result = await api.loadDemo(selectedOrgId, scenario);
      setDispatchId(result.dispatch_id);
      followJob(result.job_id);
    } catch (caught) {
      setBusy(false);
      setError(caught instanceof Error ? caught.message : "No se pudo iniciar la demo");
    }
  }

  async function upload(files: FileList) {
    if (!selectedOrgId) return;
    try {
      setBusy(true);
      setError(null);
      const result = await api.upload(selectedOrgId, files);
      setDispatchId(result.dispatch_id);
      followJob(result.job_id);
    } catch (caught) {
      setBusy(false);
      setError(caught instanceof Error ? caught.message : "No se pudo cargar la carpeta");
    }
  }

  function reset() {
    if (selectedOrgId) localStorage.removeItem(`demo_dispatch_id:${selectedOrgId}`);
    setDispatchId(null);
    setState(null);
    setJob(null);
    setBusy(false);
    setError(null);
  }

  function selectAgency(orgId: string) {
    localStorage.setItem("demo_org_id", orgId);
    setSelectedOrgId(orgId);
    setDispatchId(localStorage.getItem(`demo_dispatch_id:${orgId}`));
    setState(null);
    setJob(null);
    setError(null);
  }

  const theme = selectedAgency
    ? ({
        "--navy": selectedAgency.branding.primary_color,
        "--teal": selectedAgency.branding.accent_color,
        "--teal-dark": selectedAgency.branding.accent_color,
      } as CSSProperties)
    : undefined;

  return (
    <div className="app-shell" style={theme}>
      <header className="topbar">
        <button className="brand" onClick={reset} aria-label="IMR Tech Control Aduanero — ir al inicio">
          <img className="brand-logo" src={imrLogoUrl} alt="" width="813" height="327" />
          <small>Control Aduanero</small>
        </button>
        <nav>
          <span className="environment-pill">{selectedAgency?.branding.short_name || "DEMO LOCAL"}</span>
          <button className="nav-button" onClick={reset}><RotateCcw size={15} /> Nuevo despacho</button>
          <button className="nav-button" onClick={() => setHelpOpen(true)}><CircleHelp size={15} /> Ayuda</button>
        </nav>
      </header>
      {busy && job ? (
        <JobProgress job={job} />
      ) : state && selectedOrgId ? (
        <ReviewWorkspace
          state={state}
          orgId={selectedOrgId}
          lastJob={job}
          onRefresh={refresh}
          onJob={followJob}
        />
      ) : (
        <IntakeView
          agencies={catalog?.agencies || []}
          uploadLimits={catalog?.upload_limits || null}
          selectedOrgId={selectedOrgId}
          busy={busy}
          error={error}
          onAgency={selectAgency}
          onDemo={startDemo}
          onUpload={upload}
        />
      )}
      <footer className="global-warning">ENTORNO DE DEMOSTRACIÓN · Documentos sintéticos · Controles aduaneros pendientes de validación</footer>
      {helpOpen ? <HelpDialog onClose={() => setHelpOpen(false)} /> : null}
    </div>
  );
}
