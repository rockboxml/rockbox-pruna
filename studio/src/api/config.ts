// API base URL for the orchestrator.
//
// Empty string = same-origin relative URLs, which is how BOTH the single-service
// deploy (FastAPI serves the SPA + API on one origin) and the Vite dev proxy
// work — no configuration needed. Set `VITE_API_BASE_URL` at build time to point
// the SPA at a separately-hosted API (e.g. a standalone orchestrator service);
// the backend must then allow this SPA's origin via `ALLOWED_ORIGINS` (CORS).
export const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

/** Resolve an API path against the configured base. Absolute URLs pass through. */
export function apiUrl(path: string): string {
  if (/^https?:\/\//.test(path)) return path;
  return `${API_BASE}${path}`;
}
