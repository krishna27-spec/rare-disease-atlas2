import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Two builds:
//   npm run build        -> dist/        served by FastAPI, calls the live API
//   npm run build:pages  -> dist-pages/  no server: reads the static files from `python -m src.atlas.export_static`
// In dev the API runs on :8000 (uv run uvicorn src.atlas.server:app).
const api = ["search", "diseases", "disease", "clusters", "cluster", "mechanism", "connectors", "edge", "contradictions", "stats"];
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  base: mode === "pages" ? "./" : "/",
  define: { __STATIC__: mode === "pages" },
  build: { outDir: mode === "pages" ? "dist-pages" : "dist" },
  server: { proxy: Object.fromEntries(api.map((p) => [`/${p}`, "http://localhost:8000"])) },
}));
