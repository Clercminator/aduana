import type { DispatchState, Job } from "./types";

export const API_ROOT = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000/api`;
export const API_DOCS_URL = `${API_ROOT.replace(/\/api$/, "")}/docs`;

function responseError(body: string, status: number): string {
  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") return parsed.detail;
    if (parsed.detail) return JSON.stringify(parsed.detail);
  } catch {
    // Non-JSON provider and proxy errors are already useful as plain text.
  }
  return body || `Error HTTP ${status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, init);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(responseError(detail, response.status));
  }
  return response.json() as Promise<T>;
}

export function assetUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_ROOT.replace(/\/api$/, "")}${path}`;
}

export const api = {
  loadDemo: (scenario: "A" | "B" | "C" | "D") =>
    request<{ dispatch_id: string; job_id: string; added: number; duplicates: number }>(`/demo/load/${scenario}`, { method: "POST" }),
  upload: (files: FileList | File[]) => {
    const body = new FormData();
    Array.from(files).forEach((file) => body.append("files", file));
    return request<{ dispatch_id: string; job_id: string; added: number; duplicates: number }>("/intake/batches", { method: "POST", body });
  },
  addDocuments: (dispatchId: string, files: FileList | File[]) => {
    const body = new FormData();
    Array.from(files).forEach((file) => body.append("files", file));
    return request<{ dispatch_id: string; job_id: string; added: number; duplicates: number }>(`/dispatches/${dispatchId}/documents`, { method: "POST", body });
  },
  job: (id: string) => request<Job>(`/jobs/${id}`),
  dispatch: (id: string) => request<DispatchState>(`/dispatches/${id}`),
  correct: (dispatchId: string, fieldPath: string, value: unknown, reason: string) =>
    request<{ job_id: string }>(`/dispatches/${dispatchId}/fields/${encodeURIComponent(fieldPath)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value, reason }),
    }),
  acceptRisk: (exceptionId: string, rationale: string) =>
    request(`/exceptions/${exceptionId}/accept-risk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rationale }),
    }),
};
