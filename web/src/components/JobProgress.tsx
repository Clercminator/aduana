import { Clock3, Gauge, LoaderCircle } from "lucide-react";
import type { Job } from "../types";

const stageLabels: Record<string, string> = {
  queued: "En cola",
  classification: "Clasificando documentos",
  reconciliation: "Reconciliando y calculando",
  done: "Listo para revisión",
};

export function JobProgress({ job }: { job: Job }) {
  const percent = Math.round(Number(job.progress) * 100);
  const label = stageLabels[job.stage] || (job.stage.startsWith("extraction:") ? "Extrayendo campos y citas" : job.stage);
  return (
    <main className="progress-shell">
      <section className="progress-card">
        <LoaderCircle className="spin" size={38} />
        <span className="eyebrow">Proceso {job.status === "queued" ? "preparado" : "en curso"}</span>
        <h1>{label}</h1>
        <p>Los documentos independientes se procesan en paralelo. Puede dejar esta pantalla abierta.</p>
        <div className="progress-track"><span style={{ width: `${percent}%` }} /></div>
        <div className="progress-percent">{percent}%</div>
        <div className="metrics-row user-metrics">
          <div><Gauge size={19} /><span>Progreso</span><strong>{percent}%</strong></div>
          <div><Clock3 size={19} /><span>Tiempo transcurrido</span><strong>{job.elapsed_seconds ? `${job.elapsed_seconds.toFixed(1)} s` : "—"}</strong></div>
        </div>
        {job.error && <div className="inline-error" role="alert">{job.error}</div>}
      </section>
    </main>
  );
}
