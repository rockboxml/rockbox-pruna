/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the orchestrator API. Empty = same-origin (default). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
