# Handoff: the administrator's components, from what was built

For a design pass on the components the administrator's screens are made of, now that the parts behind them are built (2026-10-05):
- the integration registry and each community's connections (`jason integrations`);
- the credential vault over Keeper (`jason vault status|migrate`), and every credential read through it;
- the scheduler and each source's schedule (`jason cadence`);
- jason as a service (`jason serve`, `jason daemon status|stop`, `--install-task`);
- the Status screen's standing words, from each source's declared threshold.

[handoff-instance-and-integrations.md](handoff-instance-and-integrations.md) named the screens (Instance, Communities, Integrations, Service, Schedules, People, Community → Integrations) and a first list of components. It was written before the build. This page gives each component the data the build actually produces, every state the code can be in, the words to use, and the rules. Where the two differ, this page wins. The screens, the setup dialogs' steps, and "Secrets in the console" there still stand, and so do the corrections in [handoff-reconciliation.md](handoff-reconciliation.md) and its third and fourth cuts.

The design project may use the association's real details. What comes back into the repository is general, and every sample below is made up ("oakview", "A. Admin").

## The idea in six sentences

The administrator connects services and decides how often jason reads them; they approve nothing on a community's behalf. A connection counts only after jason's read of it succeeds, and the screen shows what was read, when, and by whose check. A credential is only ever "set" or "not set", with the vault path that names where it goes; no value is shown, copied, logged, or put in a URL. A schedule runs only after a person adopts it, never faster than its floor, never for a write, and a sign-in failure pauses it until a person acts. The service reports itself through a heartbeat, and nothing on a screen starts or stops it: the screen shows the terminal command. Every change records who made it and when, in words a person would say.

## Who sees what

| Viewer | Sees |
|---|---|
| An administrator, signed in as themselves | Every component on this page, for every community and the installation |
| A community's officer | The `ConnectionChip` for each of their community's integrations on Status and Setup, read-only, with the `why`; never the configuration, the vault, the schedules' controls, or the service |
| An owner | Nothing on this page |
| An administrator viewing the console as someone else (`--dev`) | What that person sees; no administration |

## The data

The console has no administration routes yet. The build will serve the shapes below to administrators only (403 to anyone else), read from what the commands already produce. The route names are proposals.

| Route (proposed) | Serves | Built from |
|---|---|---|
| `GET /api/instance/integrations?community=KEY` | each integration's reading, the community's or the installation's (`community=instance`) | `jason integrations list --json` (`jason.commands.integrations._row`) |
| `GET /api/instance/schedules?community=KEY` | each source's schedule row | `jason cadence --json` (`jason.scheduler`) |
| `GET /api/instance/service` | each community's heartbeat, judged | `jason daemon status --json` (`jason.serve.status`) |
| `GET /api/instance/vault` | the backend, whether it answers, the entries' names, what `.env` still names | `jason vault status` (`jason.commands.vault.status_lines`) |
| `GET /api/status` (built) | the community's sources with `lastRead`, `standing`, `staleAfter`, `fix` | `jason.web.extra.status` |

Writes from the console (changing a schedule, pausing, resuming, a live check) are a later build. Until then each control shows its `Command`. When they are built, each is a `Confirm`, recorded by the signed-in administrator's name, and refused unless the console requires sign-in.

### An integration's reading

```json
{"key": "zoom", "name": "Zoom", "scope": "community", "auth": "s2s-oauth",
 "state": "connected", "why": "last read 2099-10-03T03:00:00+00:00",
 "account": "", "vaultPath": "jason/community/oakview/zoom/app", "credential": "zoom",
 "credentialSet": true,
 "capabilities": [
   {"key": "meetings-read", "label": "Read meetings", "scopes": ["list meetings", "past meeting"], "writes": false, "on": true},
   {"key": "participants-read", "label": "Read who attended", "scopes": ["past meeting participants"], "writes": false, "on": false},
   {"key": "meetings-write", "label": "Create meetings (hearings)", "scopes": ["write meeting"], "writes": true, "on": false}],
 "rateLimit": {"published": "by plan: Pro 30, 20, and 10 requests a second for light, medium, and heavy APIs; …",
               "source": "https://developers.zoom.us/docs/api/rate-limits/", "readOn": "2026-10-05"},
 "connectedBy": "A. Admin", "connectedAt": "2099-10-01T17:02:00+00:00",
 "lastChecked": "2099-10-01T17:02:00+00:00", "lastCheck": "ok: a token issued; 1 meeting listed", "check": "list one meeting",
 "cadences": [{"source": "zoom", "command": "jason zoom", "cadence": "cron 0 3 * * *, floor 1h, stale after 2d",
               "every": "", "cron": "0 3 * * *", "window": "", "outside": "", "floor": "1h", "staleAfter": "2d",
               "limit": "", "note": "and 2 hours after each board meeting", "proposed": false, "manual": "",
               "lastRead": "2099-10-03T03:00:00+00:00", "standing": "current", "override": null}]}
```

- `state` is one of five words: `not set up`, `needs sign-in`, `connected`, `failing`, `paused`.
- `why` is always present and says how the state was decided: a person's pause note; "the vault's login is not on this machine: jason login"; "no Google token on this machine: the first sign-in"; a source's failure ("Gmail: its last run failed"); the last check's words; "last read …"; "not set up; nothing read yet".
- A capability's `scopes` are the provider's own names as the registry lists them; the registry's `note` on a capability (e.g. "needs a paid plan") is its limit, and the build adds it to the reading.
- `credentialSet` is `true`, `false`, or `null` when the integration needs no credential (the law library, the local models, the county's public sources).
- `lastCheck` is already masked: emails, phone numbers, and anything shaped like a token are hidden before it is stored.
- When the vault could not be asked (Keeper not signed in), `why` adds "the vault could not be asked (…), so only .env was tested".

The integrations today. Community: Google Workspace, console sign-in, PayHOA, Zoom, PostScanMail, the utilities, the City's permits (Accela), the signed-in vendor portals. Instance: the vault, the installation's sign-in, the law library, the local models, the county's public sources, the public vendor portals, Bedrock.

### A schedule row

`jason cadence --json` gives `{"community": "oakview", "zone": "America/Los_Angeles", "schedules": [...]}`, each row:

```json
{"source": "gmail", "integration": "google-workspace", "command": "jason gmail --sync",
 "cadence": "every 30m 07-22 (1h outside), floor 2m, stale after 1h",
 "every": "30m", "cron": "", "window": "07-22", "outside": "1h", "floor": "2m", "staleAfter": "1h",
 "default": {"every": "10m", "cron": "", "window": "07-22"},
 "setting": "admin", "settingWords": "changed by A. Admin 2099-10-05T01:27-07:00",
 "setBy": "A. Admin", "setAt": "2099-10-05T08:27:55+00:00",
 "adopted": true, "held": "", "nextRun": "2099-10-05T15:30:00+00:00", "nextRunLocal": "2099-10-05T08:30-07:00",
 "lastEnqueued": "2099-10-05T15:00:04+00:00", "lastJob": 412, "lastResult": "done",
 "lastFinished": "2099-10-05T15:00:41+00:00", "failures": 0, "backoffUntil": "",
 "paused": null, "misfire": "run-once", "note": ""}
```

- `setting` is `default` (the integration's) or `admin` (a person's change, with `setBy` and `setAt`); `settingWords` says it in words.
- `held` is why the row will not run, when it will not: not adopted, manual ("a person runs it: it reads a workbook a person downloads"), refused (it writes), retired (no longer in the registry). Empty when it runs.
- `paused` is `null` or `{"by", "at", "why", "kind"}`, with `kind` `person` or `sign-in`.
- `misfire` is `run-once` (one catch-up after downtime) or `skip` (wait for the next slot).
- Times are stored in UTC (`nextRunLocal` is the community's zone), and the screen names the zone once ("times in Pacific Time").

### A heartbeat, judged

```json
{"profile": "oakview", "pid": 4120, "host": "OFFICE-PC", "started": "2099-10-05T07:00:12+00:00",
 "beat": "2099-10-05T15:31:02+00:00", "age": 21, "state": "running", "alive": true,
 "web": {"host": "127.0.0.1", "port": 8765}, "worker": true, "workerRunning": true,
 "scheduler": true, "schedulerRunning": true, "schedulerZone": "America/Los_Angeles", "schedulerTick": "2099-10-05T15:30:40+00:00",
 "schedules": [{"source": "drive", "at": "2099-10-05T15:40:00+00:00", "command": "jason drive --sync"}],
 "lanes": {"google": {"id": 413, "command": "jason drive --sync", "started": "2099-10-05T15:30:41+00:00"}, "payhoa": null, "gpu": null},
 "workerLock": {"pid": 4120, "since": "2099-10-05T07:00:13+00:00"},
 "refused": "", "failed": ""}
```

- `state` after judging: `none` (never run), `running`, `draining`, `stopped`, or `stale` (no beat for 90 seconds; `said` keeps what it last said). `age` is seconds since the last beat.
- The scheduler part is on, off, or ended (its thread stopped); `schedulerTick` is its last look.
- `refused` says why a worker did not start ("another worker holds this community"); `failed` says why a part stopped.
- The GPU lane is shared by every community on the machine; a model job waiting for another community's shows as waiting, not failed.

### The vault

```text
Backend: Keeper (this PC)
Answers: yes, 6 entries
Instance:
  jason/instance/instance/signin/oauth-client
Community oakview:
  jason/community/oakview/payhoa/login
  jason/community/oakview/zoom/app
Still named in .env (`jason vault migrate` plans the move):
  postscanmail_record_uid -> jason/community/oakview/postscanmail/api-key
  example_record_uid -> (no vault path: a person decides)
```

Names only. "Answers" can also be "no: Keeper is not signed in on this PC (jason login)", and then "Still named in .env" says some may already be moved.

## The components

| Component | On | Job |
|---|---|---|
| `ConnectionChip` | Communities, Status, Setup, `IntegrationCard` | A connection's state as a glyph and a word, with its `why` |
| `IntegrationCard` | Community → Integrations, Instance → Integrations | One integration: state, credential, account, capabilities, limits, schedules, last check, next step |
| `CredentialLine` | `IntegrationCard`, `VaultStatus` | Whether a credential is set, where it goes, and how it is being read |
| `CapabilityList` | `IntegrationCard`, `ConnectDialog` | What jason may do with the service, read first, writes marked |
| `RateLimitNote` | `IntegrationCard`, `CadenceTable` | The provider's published limit with its source and date, or that none is published |
| `CheckResult` | `IntegrationCard`, `StepCheck` | The last check: what was read, when, by whose run, or why it failed |
| `CadenceTable` / `ScheduleRow` | Schedules, `IntegrationCard` | Each source's schedule, where the setting came from, its next run, its last result |
| `CadenceEditor` | from a `ScheduleRow` | Changing a schedule within its floor, or restoring the default |
| `PauseBanner` | `ScheduleRow`, `IntegrationCard` | Why a schedule is paused, by whom, and the one step that resumes it |
| `ServiceStatus` | Instance, Service | The service per community: its parts, its heartbeat, its lanes, its next runs |
| `LaneRow` | `ServiceStatus` | One job lane and what it is doing |
| `VaultStatus` | Instance, Instance → Integrations | The vault's backend, whether it answers, its entries by owner |
| `MigrationPlan` | `VaultStatus` | What `.env` still names and where each moves |
| `StandingWord` | Status | A source's standing, with the threshold it was judged by |
| `TerminalStep` | everywhere a person must act at a terminal | The command, who runs it, and why it is not a button |

### `ConnectionChip`

- **States** (exactly five; never a sixth word):

  | State | Glyph (proposed) | Reads |
  |---|---|---|
  | not set up | `circle-dashed` | "Not set up" |
  | needs sign-in | `key-round` | "Needs sign-in" |
  | connected | `circle-check` | "Connected" |
  | failing | a new glyph, or one the design names; not `triangle-alert` (an overdue clock) or `octagon-alert` (going ahead would be wrong) | "Failing" |
  | paused | `circle-pause` | "Paused" |

- **Sizes:** a chip with the word; a dot with the glyph only, in a dense community row, with the word as its accessible name and the `why` on hover or focus.
- **Always carries** the `why` (a tooltip on the chip, a line under it on a card).
- **Never** green for "set" alone: a credential set but never read is "not set up; nothing read yet", drawn as not set up.

### `IntegrationCard`

- **Head:** the name, the `ConnectionChip`, the scope ("this community" / "the installation"), and the account (`account`, or "no account named").
- **Body, in order:**
  1. `CredentialLine`.
  2. `CapabilityList`, collapsed to "4 on, 1 off (writes)" until opened.
  3. The schedules: each cadence as a compact `ScheduleRow` (the source, its cadence in words, last read, standing).
  4. `RateLimitNote`.
  5. `CheckResult`.
- **Foot:** the one next step for the state: not set up → "Set up" (the `ConnectDialog`); needs sign-in → who signs in and the command; failing → the fix in plain words; paused → the `PauseBanner`; connected → "Check now" (a `TerminalStep` until console writes exist).
- **States to draw:** each of the five; one with no credential needed (the law library: "nothing to connect; jason checks it answers"); one with no schedules ("jason reads it only when a person asks"); an integration with instances (the signed-in vendor portals: one card, a row per portal the profile names, each with its own credential line); the vault not asked (a quiet line, not an error).

### `CredentialLine`

One line, never a field.

| Case | Reads |
|---|---|
| set, in the vault | "Credential set · `jason/community/oakview/zoom/app`" |
| set, still read from `.env` | "Credential set · read from `.env` (`zoom_record_uid`); moves to `…/zoom/app` with `jason vault migrate`" |
| not set | "No credential · goes to `…/zoom/app`" |
| none needed | "Nothing to store" |
| the vault could not be asked | "Set in `.env`; the vault could not be asked (Keeper is not signed in on this PC)" |

- The path is in a code face, copyable; the value never appears, and there is no "show", "copy secret", or reveal control.
- "Read from `.env`" is a deprecation, drawn as a note, not a warning: it works.

### `CapabilityList`

- Read capabilities first, then writes; each write marked "writes" and off by default.
- Each row: the label, the switch (read-only until console writes exist), and the provider's own scope names in a code face, smaller.
- A write capability's row says what turning it on allows ("creates the hearing's Zoom meeting") and that each write still needs a person's `--yes`.
- A capability the plan does not allow (Zoom participants without a paid plan) is drawn off with the reason, not hidden.

### `RateLimitNote`

- "Published: 6,000 units a minute per user · Google, read 2026-10-05", the source a link (`external-link`).
- Or "None published · jason keeps to a polite rate" for a provider that publishes none.
- It explains a floor: on a `ScheduleRow`, the floor's tooltip points here.

### `CheckResult`

- **Passed:** a `Seal` `read` with what was read ("a token issued; 1 meeting listed"), when, and by whom ("checked by A. Admin").
- **Failed:** the words as stored ("failed: 401 invalid client"), the likely cause, and the step to revisit in the setup dialog.
- **Never checked:** "Never checked" with the `TerminalStep` that checks.
- A check runs only for a person at a terminal (`jason integrations check KEY --live --by NAME`), never for an agent or a timer. The result says so: "a person's check".

### `CadenceTable` and `ScheduleRow`

A table on Schedules (every community, or one), a compact list on an `IntegrationCard`.

- **Columns:** source; command; cadence in words ("every 30m 07–22, 1h outside"); floor; where the setting came from; next run; last result; standing.
- **Row states** (a row can be in more than one; the first that applies is the row's lead):

  | Lead | Reads | Draw |
  |---|---|---|
  | retired | "No longer in jason's registry (since …)" | dimmed, at the bottom |
  | refused | "Never scheduled: it writes. A scheduled write is the board's decision." | `octagon-alert` is wrong here (nothing is about to go wrong); the `circle-pause` glyph with "not scheduled" |
  | manual | "A person runs it: …" with the reason | no next run |
  | not adopted | "Proposed default · not running until adopted" | the cadence in a muted face; the adopt step |
  | paused, sign-in | "Paused: needs sign-in (…). A good check or a person's resume clears it." | `PauseBanner`, sign-in variant |
  | paused, person | "Paused by A. Admin on Oct 5: PayHOA maintenance window" | `PauseBanner`, person variant |
  | backing off | "3 failures · next try after 4:10 PM" | the failures count, no red until a person's step is needed |
  | queued / running | "Queued as job 412" / "Running since 3:00 PM" | links to the job |
  | adopted | the next run | — |

- **Where the setting came from:** "Default", or "Changed by A. Admin on Oct 5". A changed row offers "Restore default".
- **Never** a countdown that ticks every second; the next run is a time.
- **The window** reads as hours in the community's zone ("7 AM–10 PM, hourly outside").

### `CadenceEditor`

- **Inputs:** every (a duration: 30m, 2h, 1d) or a cron line, with a plain-words preview ("every day at 2 AM"); the window (from, to); and who (prefilled with the signed-in administrator, not editable).
- **The floor** is shown beside the input before typing ("no faster than every 2m · Google's published rate"). A value below it is refused inline with the reason as the command gives it: "runs every 1m at its closest, faster than the floor 2m its integration declares".
- **Restore default** shows the default it restores to.
- **Adopt** is the same action as restore for a row not yet adopted: "Adopt the default (every 10m, 7 AM–10 PM)".
- Until console writes exist, the editor composes the command (`jason cadence gmail --every 30m --window 07-22 --by "A. Admin"`) in a `TerminalStep` with a copy button.

### `PauseBanner`

- **Person variant:** who, when, why, and "Resume" (or `jason cadence --resume SOURCE --by NAME`).
- **Sign-in variant:** which integration, the failure's plain words, who must sign in, and how: "Keeper is not signed in on this PC: run `jason login` at the terminal, then `jason integrations check payhoa --live`". Signing in alone does not resume (lesson `keeper-login-does-not-clear-sign-in-pause`); the banner says the second step.
- One banner per integration, not one per source: a PayHOA sign-in pause covers seven sources and says so ("7 schedules paused").

### `ServiceStatus`

One panel per community, from its judged heartbeat.

- **Head:** the state word and glyph: running ("since 7:00 AM, pid 4120 on OFFICE-PC"), draining ("finishing its current jobs"), stopped ("stopped at …"), stale ("no heartbeat for 3 minutes; the process may be hung"), none ("jason serve has not run for this community").
- **Parts:** web (on at 127.0.0.1:8765 / off / failed: …), worker (on / off / refused: another worker holds this community / failed: … / ended), scheduler (on, in Pacific Time / off).
- **Lanes:** a `LaneRow` each.
- **Next runs:** the next five, time and source.
- **How it is started:** Task Scheduler ("jason serve", at startup), by hand in a terminal, or not installed, with `jason serve --install-task` as a `TerminalStep`.
- **Stop:** "Ask it to stop" is `jason daemon stop` in a `TerminalStep`; it writes a drain request and kills nothing.
- **States to draw:** running with a busy lane; stale; stopped; never run; refused because another process holds the worker; two communities on one machine with the GPU lane busy for the other.
- **Not here:** a start button, a restart button, a kill button.

### `LaneRow`

- The lane (`gpu`, `google`, `payhoa`, `county`, `local`), its job (number, command, elapsed), or "idle".
- The GPU lane is the machine's, not the community's: it says whose job holds it ("a model job for another community").
- A job waiting for a lane says "waiting for the GPU lane", not "failed".

### `VaultStatus`

- **Head:** the backend ("Keeper, on this PC"; later SSM Parameter Store, Secrets Manager, or OpenBao when hosted) and whether it answers ("yes, 6 entries" or the reason it did not).
- **Entries:** grouped "Instance" then each community, each a path in a code face. Names only; no count of fields, no versions, no dates of change unless `describe` gives them, and then "changed Oct 5 by A. Admin".
- **Keeper's sign-in:** "Keeper needs a sign-in at the terminal: `jason login`"; from day 25 of its 30-day session, "Keeper will ask for a sign-in again by Oct 30".
- `MigrationPlan` below it while `.env` still names records.

### `MigrationPlan`

- Each `.env` key with its destination: "copy" (→ the path), "already in the vault", or "no vault path: a person decides".
- It is a plan: the screen never moves anything. The step is `jason vault migrate --yes`, run by a person at a terminal, which copies and never overwrites an entry already there; afterwards the person removes the moved keys from `.env`.
- When the vault did not answer, the plan says some may already be moved.

### `StandingWord`

On Status, each source's standing now comes from its integration's threshold.

- `current` / `stale` with the threshold as words: "stale after 1h (Google Workspace's default)". Use `staleAfter` ("1h", "2d"), never a fraction of a day.
- `failed`, `not signed in`, and `never read` as before.
- A source with no threshold shows its age and no standing word; the screen never invents one.

### `TerminalStep`

The existing `Command`, with who runs it and why it is not a button:
- "A person at the terminal on OFFICE-PC" for anything that reads a secret, signs in, or installs (`jason login`, `jason vault migrate --yes`, `jason integrations check KEY --live`, `jason serve --install-task --yes`).
- The reason in one line: "jason never checks a service live on its own" / "only a person moves credentials" / "the console never starts or stops the service".
- A copy button for the command; never a placeholder filled with a secret.

## Words

| Say | Not |
|---|---|
| Connected | Online, active, healthy |
| Needs sign-in | Expired, unauthorized, error |
| Credential set | Saved password, configured secret |
| Vault path | Secret name, key |
| Adopt the default | Enable, turn on |
| Paused by A. Admin | Disabled, off |
| Never scheduled: it writes | Not allowed, blocked |
| Floor | Minimum, rate limit (the limit is the provider's; the floor is jason's) |
| Ask it to stop | Stop, kill, shut down |
| A person's check | Test, ping |

Times: "3:00 PM", "Oct 5", in the community's zone, named once per screen. Durations: "30m", "2h", "1d" in tables; "every 30 minutes" in sentences.

## What must not change

- No secret displayed, logged, stored, copied, or put in a URL, a toast, or an error.
- An integration counts as connected only after jason's read succeeds; a credential that is set but unread is "not set up".
- A schedule runs only after a person adopts it; never faster than its floor; never a write.
- A sign-in failure pauses and stays paused until a good check or a person's resume; no timer clears it.
- Nothing on a screen starts, stops, installs, signs in, checks live, or moves a credential: each is a `TerminalStep` until a console route exists, and then a `Confirm` recorded by name.
- Administrators configure; they approve nothing on a community's behalf. No `Stamp` on these screens (connecting is not a decision); `Seal` for what jason read.

## Decisions that are the design's

1. The glyph for "failing" (one meaning per glyph; the overdue and stop glyphs are taken).
2. Whether a community row shows five dots or a summary ("6 connected, 1 needs sign-in").
3. How a sign-in pause covering many schedules reads in the `CadenceTable`: one banner over the group, or a marker on each row.
4. How `ServiceStatus` shows two communities sharing one machine's GPU lane.
5. Whether `MigrationPlan` lives on the vault's panel or as its own step in onboarding.

## Open (the build's or a person's)

- The console routes and writes above (proposed names).
- The default cadences, and whether the board allows scheduled writes ([integrations-design.md](../integrations-design.md#open-decisions)).
- The Google tokens per community and account (integrations build step 3); until then one sign-in serves the installation.
- Calendar and Tasks share one command, so Tasks runs on Calendar's schedule (lesson `calendar-and-tasks-share-a-command`).
- A Status row for the sources that have a schedule but no last-read stamp (lesson `cadence-without-status-row`).
