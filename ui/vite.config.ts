import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` here and `jason-web` (port 8080) beside it; /api is proxied so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  // Vite 6.4.3 enforces server.fs on module loads, so the two tests that import ?raw fixtures from ../tests need that folder allowed.
  server: { proxy: { "/api": "http://127.0.0.1:8080" }, fs: { allow: [".", "../tests/fixtures"] } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setup.ts"] },
});
