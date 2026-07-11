import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API + artifact routes to the orchestrator so the SPA uses relative URLs
// in both dev and prod. SSE works through the proxy; the run-stream hook also
// passes ?lastEventId= for reconnect replay.
const api = "http://localhost:8001";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/runs": { target: api, changeOrigin: true },
      "/artifacts": api,
      "/characters": api,
      "/locations": api,
      "/entities": api,
      "/skills": api,
      "/health": api,
    },
  },
});
