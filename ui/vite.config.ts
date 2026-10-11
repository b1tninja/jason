import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` here and `jason-web` (port 8080) beside it; /api is proxied so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  // Vite 6.4.3 enforces server.fs on module loads, so the two tests that import ?raw fixtures from ../tests need that folder allowed.
  // changeOrigin stays false: the write guard compares the page's Origin with the request Host, so the proxy must keep the browser's Host.
  server: { proxy: { "/api": { target: "http://127.0.0.1:8080", changeOrigin: false } }, fs: { allow: [".", "../tests/fixtures"] } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setup.ts"] },
});
