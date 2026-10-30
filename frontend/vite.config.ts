import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  define: {
    "import.meta.env.VITE_USE_MOCK": JSON.stringify(mode === "mock" || process.env.VITE_USE_MOCK === "true" ? "true" : "false"),
  },
  server: {
    host: "127.0.0.1",
    strictPort: true,
    proxy: {
      "/api": { target: process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000" },
    },
  },
}));
