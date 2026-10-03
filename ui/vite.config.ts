/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` here and `jason-web` (port 8080) beside it; /api is proxied so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8080" } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setup.ts"] },
});
