import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// Dev: `npm run dev` here and `jason-web` (port 8080, or JASON_WEB_URL) beside it; /api and /auth (Google sign-in: its start,
// callback, and sign-out routes, `jason.web.signin`) are proxied so the browser sees one origin. Without /auth the "Sign in with
// Google" link lands on this dev server's own index.html and sign-in can never finish. The sign-in redirect URI is then this dev
// server's (http://localhost:5173/auth/google/callback), which the Google client must list for a dev run through Vite.
const env = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env ?? {};
const web = env.JASON_WEB_URL || "http://127.0.0.1:8080";
const through = { target: web, changeOrigin: false };

export default defineConfig({
  plugins: [react()],
  // Vite 6.4.3 enforces server.fs on module loads, so the two tests that import ?raw fixtures from ../tests need that folder allowed.
  // changeOrigin stays false: the write guard compares the page's Origin with the request Host, so the proxy must keep the browser's Host.
  server: { proxy: { "/api": through, "/auth": through }, fs: { allow: [".", "../tests/fixtures"] } },
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setup.ts"] },
});
