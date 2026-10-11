// The console's end-to-end suite (e2e/README.md). Two servers start for a run, both on 127.0.0.1 and free ports:
//   built     the real Flask app (e2e/serve_e2e.py) serving ui/dist, on a throwaway data folder, sign-in bypassed by the launcher
//   vite-dev  `vite` for ui/, proxying /api and /auth to the first, as a person runs the console while developing
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.listen(0, "127.0.0.1", () => { const { port } = s.address(); s.close(() => resolve(port)); });
    s.on("error", reject);
  });
}

// Chosen once in the main process and handed to the workers through the environment.
process.env.E2E_PORT ||= String(await freePort());
process.env.E2E_VITE_PORT ||= String(await freePort());
const port = process.env.E2E_PORT;
const vite = process.env.E2E_VITE_PORT;
const python = process.env.E2E_PYTHON || "python";
const data = path.join(here, ".run", "data");
process.env.E2E_DATA = data;

export default defineConfig({
  testDir: "./tests",
  outputDir: path.join(here, ".run", "results"),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  reporter: [["list"]],
  use: { headless: true, trace: "retain-on-failure" },
  projects: [
    { name: "built", testIgnore: /vite\.spec/, use: { baseURL: `http://127.0.0.1:${port}` } },
    { name: "vite-dev", testMatch: /vite\.spec/, use: { baseURL: `http://127.0.0.1:${vite}` } },
  ],
  webServer: [
    {
      command: `"${python}" e2e/serve_e2e.py --port ${port} --data "${data}" --fresh`,
      cwd: path.join(here, ".."),
      url: `http://127.0.0.1:${port}/api/health`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { PYTHONPATH: path.join(here, "..", "src"), PYTHONUNBUFFERED: "1" },
    },
    {
      command: `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${vite} --strictPort`,
      cwd: path.join(here, "..", "ui"),
      url: `http://127.0.0.1:${vite}/`,
      timeout: 120_000,
      reuseExistingServer: false,
      env: { JASON_WEB_URL: `http://127.0.0.1:${port}` },
    },
  ],
});
