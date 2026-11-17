import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const analysisProxy = {
  "/analysis": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
  },
  "/chatbot": {
    target: "http://127.0.0.1:8001",
    changeOrigin: true,
  },
};

export default defineConfig({
  plugins: [react()],
  server: { proxy: analysisProxy },
  preview: { proxy: analysisProxy },
});