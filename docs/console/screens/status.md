# Status

`#/status`, in Overview · built · administrator only · loader `GET /api/status` (`jason.web.extra.status`)

## In the console

Built, read-only: the administrator's landing ([handoff-reconciliation.md](../handoff-reconciliation.md) correction 6; [handoff-reconciliation-4.md](../handoff-reconciliation-4.md), "New in this cut"). The administrator holds no office and approves nothing. The only control is copying a command.

- **Landing.** The role class `administrator` (one of jason's admins with no office) lands here (`DEFAULT_LANDING`). An admin who also holds an office lands on that office's screen and still has Status in the nav.
- **The nav.** Status is shown only to one of jason's admins viewing as themselves (`adminSession` in `App.tsx`): never to anyone else, never in the owner view, and never while an admin views the console as someone else under `--dev`. The server checks the same, so hiding the nav entry is not the check.

## Data

`GET /api/status` answers only one of jason's admins, signed in as themselves: 401 with no sign-in, 403 for anyone else and while an admin views as someone else. The owner view refuses it: it is not in `OWNER_SOURCES`, and `ui/src/ownerScreens.json` does not list it. It reads disk only. It calls no Google, PayHOA, Keeper, or network, and writes nothing: a SQLite store is opened read-only, and a store that is not there reads as "never read" and is not created.

| Part | Source |
|---|---|
| `sources[]`: `key`, `name`, `what`, `store`, `lastRead`, `ageSeconds`, `standing`, `note`, `fix`, `staleAfterDays`, `staleSource`, `lastJob`, `signIn` | `status.SOURCES`: each store's own stamp (`syncedAt` or `fetchedAt` in its JSON, a `synced_at` or `fetched_at` column, a store's `sync_runs`); the job queue (`data/jobs.db`) for its last run; `evidence/refreshes.jsonl` for a refresh that failed at sign-in |
| `counts`: sources by standing word ("no threshold" for none) | the rows |
| `signIns[]`: `at`, `event`, `name`, `role`, `as`, `provider`, `why` (masked); newest first, at most 20 | `web/sign-ins.jsonl` (`jason.web.signin`); never the account's email or Google `sub` |
| `gates`: `stage`, `progress`, the five `gates`, `setup` (`#/onboarding`), `command` | `onboarding_session.build` and `status_dict`, as setup reads them |
| `failures[]`: `kind` (`job`, `refresh`, `sync`), `source`, `at`, `title`, `detail` (masked), `fix`; newest first, at most 20 | failed jobs in `data/jobs.db`; failed live refreshes in `evidence/refreshes.jsonl`; a store's last sync run with `errors_json` |
| `asOf`, `caveats` | |

The sources: the PayHOA catalog, transactions, general ledger, budget, reconciliations, saved reports, and meeting notices; utility payments; Google Drive; Gmail; Zoom; scanned mail; City permits; the county's tax bills and secured roll; SMUD. Each row's `fix` is the command that refreshes it (`jason sync-catalog`, `jason drive --sync`, `jason gmail --sync`, `jason zoom`, and so on).

## Rules

- **The last read is the store's own stamp.** Never a file's modified time, and never a guess. A store with no stamp is "never read".
- **A standing word only where the records say it.**
  - `failed`: the newest queued job that runs the source's command failed after its last read.
  - `not signed in`: that failure, or a live refresh of the source's system since its last read, failed at the sign-in (Keeper or Google); or a Google source with no Google token on this machine. The fix is then the sign-in: `jason login`, or the Google command with `--interactive`.
  - `never read`: no stamp in its store.
  - `current` and `stale`: only by a threshold the source declares (`Source.stale_after_days`, with `stale_source` naming where it is written). Each source takes its integration's default `stale_after` (`jason.integrations.registry`, [integrations-design.md](../../integrations-design.md#defaults-from-rate-limits)), and the row carries it as `staleAfter` (`1h`, `2d`). A source with none shows its age and "no threshold declared". Status never invents a threshold.
- **A live refresh reads one record.** Its failure marks the source only when it was the sign-in. Any other refresh failure is listed under failures.
- **An `--offline` run reads nothing**, so it is not a refresh.

## Acceptance criteria

1. No sign-in: 401. Anyone but an admin: 403. An admin viewing as someone else: 403. The owner view: 403.
2. Each source's `lastRead` comes from its store; a missing store is "never read" and is not created.
3. No source says `current` or `stale` without a declared threshold.
4. A failed job after the last read makes its source `failed`, or `not signed in` when it failed at the sign-in, and is listed in `failures`.
5. Sign-ins carry no email address or Google `sub`.
6. The screen renders the sources with their commands, the gates (`StageSteps`), the sign-ins, and the failures, and has no control but copying a command.

Tests: `tests/test_web_status.py`, `ui/src/views/status.test.tsx`, `ui/src/views/roles.test.tsx`.
