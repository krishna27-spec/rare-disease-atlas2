import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the API runs on :8000 (uv run uvicorn src.atlas.server:app); in production FastAPI serves web/dist itself.
const api = ["search", "diseases", "disease", "clusters", "cluster", "mechanism", "connectors", "edge", "contradictions", "stats", "ten-x"];
export default defineConfig({
  plugins: [react()],
  server: { proxy: Object.fromEntries(api.map((p) => [`/${p}`, "http://localhost:8000"])) },
});
