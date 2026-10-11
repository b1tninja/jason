# Console end-to-end tests

Playwright drives the console (`ui/`) in headless Chromium against the real Flask app (`jason.web.app`), with sign-in bypassed
by a test-only launcher. Made-up data only; the real `data/` folder, Keeper, Google, and PayHOA are never reached.

## Run

```bash
npm --prefix ui run build          # the suite serves ui/dist
cd e2e
npm install                        # PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install  (browsers are not downloaded)
E2E_PYTHON=D:/code/jason/.venv/Scripts/python.exe npm run e2e
```

- `E2E_PYTHON` is the Python with jason's web extras installed (`waitress`, `flask`, PyMuPDF, `pypdf`); default `python`.
- Browsers come from the Playwright cache (`%LOCALAPPDATA%\ms-playwright` on Windows). `@playwright/test` is pinned to 1.63.0,
  which wants `chromium-1243`; if that build is missing, run `npx playwright install chromium` once.
- A run starts two servers on free ports: the launcher (`serve_e2e.py`, serving `ui/dist`) and Vite (`ui/`, proxying `/api` and
  `/auth` to the launcher). `e2e/.run/` holds the throwaway data folder and results (git-ignored).

## How sign-in is bypassed

`serve_e2e.py` builds the app with `create_app(..., sign_in=webclient.roster_sign_in())`, as the Python tests do, then adds
`/__e2e/sign-in?name=A+Manager` to its own process: it puts that roster person's account in the Flask session, as the callback does
after Google answers. The shipped app has no such route or flag. A signed-out test simply does not call it.

## What it checks

- `console.spec.ts` (served by Flask from `ui/dist`): the signed-out splitter says to sign in and asks the server a bounded number
  of times, then nothing more; other screens settle when signed out; signed in, the splitter lists drafts, uploads a made-up PDF,
  opens a made-up PDF chosen on the computer at once (pictures drawn by the browser, no `/api/split/thumb` request, the draft saved in the background), enlarges the cells and sees a sharper picture, draws made-up JPEG 2000 and CCITT scans, falls back to the server when the decoders cannot load or browser drawing is off (a test-only `/__e2e/limit` route sets a limit), shows a library file's pictures from `/api/split/thumb` with no PDF downloaded, marks a start by click, undoes it with `z`,
  reviews, previews, and writes (into the throwaway folder); the demo needs no server; Records and Limits load.
- `vite.spec.ts` (Vite dev server): "Sign in with Google" reaches the server through the proxy (a 302 to Google, not Vite's
  `index.html`), and the signed-out splitter settles there too.
- Every test (`tests/fixtures.ts`) fails on a console error, a request still pending at the end, or a read asked more than three
  times (four under Vite, whose strict mode runs each effect twice).
