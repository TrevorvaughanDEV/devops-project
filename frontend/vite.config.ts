import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the API runs separately on :8000 (uvicorn app.main:app).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", ws: true },
      "/healthz": "http://127.0.0.1:8000",
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
