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
- `layout.spec.ts` (served by Flask, on the demo draft, at 390, 768, and 1440 px): the page never scrolls sideways (in the draft, in
  focus mode, with a drawer open), focus mode hides the console's header and menu and fills the window, the segments and compare
  drawers open and close by key, button, and scrim with the focus returned, and the album's columns fill the width.
- `a11y.spec.ts` (served by Flask, on the demo draft; [docs/pdf-splitter-accessibility.md](../docs/pdf-splitter-accessibility.md)): axe-core (`axe-core`, a dev dependency here only, injected into the page) over the start page's tabs and ten editor states at 390, 768, 1440, and 320 by 256 px, in the dark scheme and in forced colours, expecting no violation; the grid's roles and counts; a cell's name holding the words it shows; a start moved with `]` again and again and by the page menu with no drag; focus kept in and returned from the page menu, keyboard map, and flags dialog; one announcement for a mark; reflow at 320 by 256; text spacing; forced colours; reduced motion; the page title and the skip link; no splitter control under 24 by 24 px.
- `pick.spec.ts` (served by Flask; [docs/google-picker.md](../docs/google-picker.md)): choosing from the person's own Google Drive through the real start and callback routes, with Google stood in for by `pick_fake.py` (installed by `serve_e2e.py` on its own app only: it points the start route at `/__e2e/google/pick`, which checks the request the way Google's documentation describes it, and hands back made-up files by a scenario from `/__e2e/pick-scenario`). It checks the button and its words, the leave and the return with the token gone from the address and the focus on the results heading, every kind of row, a held row opened as a draft and pinned to a record slot, the copies listed on the start page, a result read twice, a state that is not the one sent, and the switch off. `a11y.spec.ts` scans each of those states.
- `split-hardening.spec.ts` ([docs/console/screens/split.md](../docs/console/screens/split.md)): a confidential statement says its text is hidden and opens the private view from the notice; a library read that fails (the launcher's test-only `/__e2e/library-busy` makes the splitter's own library read raise `LibraryBusy`) shows the calm notice with a counted wait for an open, a draft's pictures, and a confirmed apply, and the review blocks the write while the duplicate check is skipped; a draft that moved after the review is refused in words and a fresh confirm writes it; a draft killed mid-apply (`/__e2e/split-seed?what=unfinished`) is finished or rolled back only after a confirm. `a11y.spec.ts` scans these states too. Each test makes its own draft (`seed`), so none depends on another; `allowStatus` names the 503s a test expects.
- `vite.spec.ts` (Vite dev server): "Sign in with Google" reaches the server through the proxy (a 302 to Google, not Vite's
  `index.html`), and the signed-out splitter settles there too.
- Every test (`tests/fixtures.ts`) fails on a console error, a request still pending at the end, or a read asked more than three
  times (four under Vite, whose strict mode runs each effect twice).
