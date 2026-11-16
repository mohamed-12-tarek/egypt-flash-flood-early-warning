import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The analysis API (port 8000) is a different origin from the Vite dev server,
// so the browser blocks it with CORS. Proxying through Vite makes the browser
// see same-origin requests (/analysis/...) without touching the backend.
const analysisProxy = {
  "/analysis": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: { proxy: analysisProxy },
  preview: { proxy: analysisProxy },
});