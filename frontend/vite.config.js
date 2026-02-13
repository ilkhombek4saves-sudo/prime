import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Proxy /api requests to the backend.
      // In Docker: VITE_BACKEND_URL=http://backend:8000 (set in docker-compose.yml)
      // Local dev:  leave unset → defaults to localhost:8000
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://localhost:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: (process.env.VITE_BACKEND_URL || "http://localhost:8000").replace("http", "ws"),
        ws: true,
        changeOrigin: true,
      },
    },
  },
});
