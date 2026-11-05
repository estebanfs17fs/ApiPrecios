import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En desarrollo, /api se reenvía a la API (por defecto la que corre en el puerto 8000).
const api = process.env.API_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": api } },
  preview: { proxy: { "/api": api } },
});
