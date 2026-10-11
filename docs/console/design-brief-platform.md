# Design brief: the platform (the administrator's Instance, connections, schedules, vault, and jobs)

One page of orientation for the design agent, for the screens a community's **administrator** uses to run jason: the Instance page, connecting and disconnecting an integration, the schedules, the vault's panel, the jobs queue, and the health strip. It does not repeat the specs; it says what to read in what order, what to draw, what is built and what has no view, and a made-up community to draw against. The Limits screens are built and briefed in [design-brief-limits.md](design-brief-limits.md); they are a reference here, not a redraw. The Work screens are in [design-brief-work.md](design-brief-work.md).

The design project may use the association's real details. What comes back into the repository is general: no association's name, street, vendor, bank, account, or private fact; made-up samples only ("Oakview", "Example Workspace", "A. Admin", dates in 2099).

## A. The idea, and the rules that run through it

**The idea, in six sentences.**

1. The administrator holds no office and approves nothing for the board. They connect services, set how often jason reads them, watch the service, and keep the limits; the screen answers **"what is connected, what is failing, and what is mine to do?"**
2. A connection counts only after a read succeeded. Its state is one of five words (`not set up`, `needs sign-in`, `connected`, `failing`, `paused`), always with the **reason** the server sends, and a credential is only ever "set" or "not set" beside its vault path.
3. jason never connects, revokes, schedules, signs in, starts, or stops anything on its own. A **person** does, in their own name, and the console records it. Until the console has a writer, the screen shows the exact terminal command (`Command`/`TerminalStep`), who runs it, and why it is not a button.
4. Every change says **when it takes effect**: **at once**, **from the next job**, or **after the next start**, in those words, before the confirm.
5. Each community has its own Google Cloud project (an Internal app with a Web client) and its own credentials; one community's page never shows another's.
6. A secret is never shown, copied, logged, or put in a URL, a toast, or an error. A path is a name.

**The rules** (each is in the specs; a screen that breaks one is wrong):

- **Directors and officers have the same access to information.** The administrator is neither: they see **status and setup, never the board's material** unless they also hold the office. A director or officer sees a connection's *state word and date* on Status and Setup, never the configuration, the vault, the schedules' controls, or the service.
- **Administrator only, as themselves.** 401 with no sign-in; 403 for anyone else, in the owner view, and while an admin views the console as someone else ("Viewing as NAME (admin view): go back to yourself first").
- **The vault (Keeper) is the development environment's store.** The console asks it only under `jason-web --dev`, and only when the person presses the vault button. Outside `--dev` the panel says so plainly ("a production installation reads its credentials from its own secret store") and is never drawn as a failure.
- **A sign-in failure pauses and never retries on a timer.** A sign-in pause clears only by a good live check or a person's resume. Signing in alone does not resume.
- **No cadence faster than its floor; no scheduled write.** A schedule runs only after a person adopts it. A write is "never scheduled: it writes", a board decision still open.
- **A live check is a person's act at a terminal** (`jason integrations check KEY --live --by NAME`), never an agent's or a timer's.
- **State is a word and a glyph, never colour alone.** A paused row is held, not red; a countdown never ticks; a time is a time, in the community's zone, named once.
- **Disconnecting is as visible as connecting**, confirmed by typed words, recorded by name.
- **No Stamp** on any of these screens (connecting is not a decision); a `Seal` (`read`) for what jason read.

## B. Reading order

1. [handoff-instance-and-integrations.md](handoff-instance-and-integrations.md), top to bottom, including its "As built" section (the code wins where it differs).
2. [handoff-admin-components.md](handoff-admin-components.md): every component's data and states (`ConnectionChip`, `IntegrationCard`, `CredentialLine`, `CapabilityList`, `CadenceTable`, `CadenceEditor`, `PauseBanner`, `ServiceStatus`, `LaneRow`, `VaultStatus`, `MigrationPlan`, `TerminalStep`).
3. This page's sections D and H beside each other.
4. [screens/integration-disconnect.md](screens/integration-disconnect.md) (the dialog, whole), [screens/status.md](screens/status.md) (built), [screens/limits.md](screens/limits.md) and [design-brief-limits.md](design-brief-limits.md) (reference).
5. [../workflows/mail-and-platform.md](../workflows/mail-and-platform.md) sections 2.5, 2.6, 3, and 9.3 to 9.4 (connecting as a run; the check-in definition is never drawn).
6. [../integrations-design.md](../integrations-design.md) (the vault, the five states, defaults and floors) and [../instance-limits.md](../instance-limits.md) section 4.
7. [handoff-held-setup-roster.md](handoff-held-setup-roster.md#personsteps) for `PersonSteps`; [handoff-storage-and-settings.md](handoff-storage-and-settings.md) only for the machine strip (section C8).

## C. The screens

### C1. Instance (`#/instance`), the overview

A page of cards: the **status strip** (C8) first; then **Communities** (a `CommunityRow` each: its profile, its five integration chips or a summary, its service state, "needs a person" count); then **the installation's own integrations** (the vault, the sign-in client, the law library, local models, county caches); then **what needs a person**, a short list of `TerminalStep`s. Draw: one community healthy; one with a sign-in pause covering seven schedules; one never run; one whose scheduler is "never seeded".

### C2. A community's integrations (`#/setup/integrations`, and the instance's own) with the five states

An `IntegrationCard` per integration. Draw each card in **all five states, each with its reason**:

| State | The card shows | The one next step |
|---|---|---|
| not set up | "No credential · goes to `…/zoom/app`"; "nothing read yet" (a credential set and never read is drawn here) | Set up (opens C3) |
| needs sign-in | who must sign in and where; its schedules held "paused, needs sign-in" | the `TerminalStep` (`jason login`, or `jason google sign-in --name drive --interactive`), then the live check |
| connected | account, capabilities ("4 on, 1 off"), `connectedBy` and date, last checked, next read, a `read` seal | Check now (a `TerminalStep`) |
| failing | the failure in plain words (masked), the likely cause, the setup step to revisit | the fix in words |
| paused | `PauseBanner`: by whom, when, why; "7 schedules paused" once per integration | resume (`jason cadence --resume SOURCE --by NAME`) |

Also draw: an integration needing no credential ("nothing to connect; jason checks it answers"); one with no schedule ("jason reads it only when a person asks"); signed-in vendor portals (one card, a row per portal); the vault not asked (a quiet line); a capability the plan does not allow, drawn off with its reason; the officer's read-only `ConnectionChip` row (state word and date only).

### C3. Connect an integration, as a run in Work

`integration-connect` is a run, administrator only, opened by a person, one per integration and community, that stays open as the watch. It appears **only in the administrator's own Work list** (a separate "Administration" group), never in the board's, not even as a count. The rail is the definition's steps (2.5): `which`, `state`, `vault`, `login`, `provider`, `credential`, `signin`, `check`, `capabilities`, `adopt`, `first`, `keep`, `disconnect`. The step panel is the dialog: for a `provider` step, a **stepper over the registry's setup steps** (Google nine, Zoom four, PayHOA four) with "The administrator does" and "jason checks"; the menu path in words, a link to the provider; a `RedirectUri` (copyable; "can take from five minutes to a few hours to take effect"); `StepCheck` (not yet, checking, passed with a `read` seal, failed in plain words, cannot check). Every terminal act is a `TerminalStep`: `jason google setup --from-file F --yes`, `jason vault migrate` then `--yes`, `jason google sign-in --name drive --interactive`, `jason integrations check KEY --live --by NAME`. Draw the reconnection of sample 9.4 (steps done, skipped with their evidence, one needing a person, one blocked) and the event log of 9.3. Draw a Gmail-only account stopping at step 1 ("a community needs Google Workspace").

### C4. The cadence and schedule editor

`#/instance/schedules`: a `CadenceTable` for every community or one: source, command, cadence in words, floor (with its tooltip pointing to the `RateLimitNote`), where the setting came from ("Default" or "Changed by A. Admin on Oct 5"), next run, last result, standing. The `CadenceEditor` opens under a row: every (30m, 2h, 1d) or a cron line with a plain-words preview; the window; the floor beside the input ("no faster than every 2m · Google's published rate"); a below-floor value refused inline in the command's words; "Restore default" and "Adopt the default (every 10m, 7 AM-10 PM)"; the effect line. Draw each lead state: retired, refused (writes), manual, not adopted, paused (sign-in, person), backing off, queued, running, adopted. Until a writer exists the editor composes `jason cadence gmail --every 30m --window 07-22 --by "A. Admin"` as a `TerminalStep`.

### C5. The disconnect dialog

Whole spec in [screens/integration-disconnect.md](screens/integration-disconnect.md): the four ordered steps (pause schedules, try to revoke, delete the vault entry, log and set "not set up"), what stops, **what a person still does outside jason** (`PersonSteps`), what it never does, "to undo: reconnect from the start", the typed words, and **Pause instead**. Draw the plan, the result (each step `done`, `person must`, `already done`, or `failed: REASON`), a failure partway, the vault-will-not-answer plan, a local-file-token note, and the refusals (the vault, the sign-in client, an instance integration, nothing to disconnect). Revoke is not built for any provider; Zoom has nothing to revoke.

### C6. The vault panel (on Instance, in the installation's integrations)

Three states, each a word and a glyph:

1. **Answers**: backend "Keeper, on this PC"; "Answers: yes, 6 entries"; the paths grouped Instance then each community, in a code face, names only; from day 25 of Keeper's 30-day session, "Keeper will ask for a sign-in again by Oct 30".
2. **Needs a sign-in**: "Keeper needs a sign-in at the terminal" with `jason login` as a `TerminalStep`; "some may already be moved".
3. **Not asked**: outside `--dev`, or before the button is pressed: "The vault was not asked" / "Keeper is the development environment's store; a production installation reads its credentials from its own secret store". A quiet line, not an error; no entries drawn.

Below it, `MigrationPlan` while `.env` still names records (copy, already in the vault, no vault path: a person decides). The panel never moves anything; the step is `jason vault migrate --yes`. No show, copy-secret, or reveal control anywhere. `SecretDrop` and `FileDrop` are drawn **only as "for a hosted install, later"**.

### C7. The limits pages (reference)

`#/setup/limits` and `#/instance/limits` are built (`LimitsView`) and briefed. Draw only their **doors**: a card on Instance ("Limits in force: 31; 2 held to their range") linking to the instance table, and the Setup link from a community's page. Do not redraw the tables, the editor, or the refusals. Take from them the pattern every write here follows: a dry run, then one confirm labelled with the change, a required reason with "no names", and the role shown.

### C8. The jobs queue and the health strip

- **Jobs (`#/jobs`)**, built: a `Kanban` of five lanes (queued, running, done, failed, cancelled); each card the command, the resource lane, attempts, who confirmed a write, and an opened log. It adds, runs, and cancels nothing. Draw it with a failed write "waiting for a person", a read backing off, and a job waiting for the GPU lane (the heartbeat does not show this yet).
- **The status strip** (proposed, on Instance and as one line above Status): service state (running since 7:00 AM / stale: no beat for 3 minutes / stopped / never run); connections ("6 connected, 1 needs sign-in, 1 paused"); schedules held ("7 held: sign-in"); sources stale or failed (from Status's counts); jobs failed (a count linking to `#/jobs`); and, when built, "The machine: 2 problems" ([handoff-storage-and-settings.md](handoff-storage-and-settings.md)). Each part is a word and a glyph and links to its page. Draw all-clear, one thing wrong, and the strip with the service stale.
- **Status (`#/status`)**, built: sources with standing words, failures, sign-ins, setup gates. Draw its place beside the strip; do not redraw it.

## D. The shared components, each once

Reuse (built): `Card`, `Command`, `Confirm`, `Findings`, `Caveats`, `Pill`, `Badge`, `Glyph`, `Seal`, `DataTable`, `Tabs`, `Kanban`, `StageSteps`, `RemoteView`, `ScreenHeader`. Specified in the handoffs, **none built in `ui/src`**, so draw them from the built parts and say so:

| Component | What it is | Data | States |
|---|---|---|---|
| `ConnectionChip` | state as glyph + word + reason | `state`, `why` | the five; a dot size for a dense row |
| `IntegrationCard` | one integration | the reading (`state, why, credentialSet, vaultPath, capabilities, cadences, connectedBy, lastCheck`) | C2 |
| `CredentialLine`, `CapabilityList`, `RateLimitNote`, `CheckResult` | the card's lines | as the admin-components page | as there |
| `PauseBanner` | why paused, by whom, the step that resumes | `paused{by,at,why,kind}` | person; sign-in; one per integration |
| `CadenceTable`, `ScheduleRow`, `CadenceEditor` | C4 | a schedule row | the lead states; floor refusal |
| `EffectLine` (new) | when a change takes effect | one of three words | at once; from the next job; after the next start |
| `ServiceStatus`, `LaneRow` | the service | the judged heartbeat | none, running, draining, stale, stopped; refused; lane busy |
| `VaultStatus`, `MigrationPlan` | C6 | `vault{asked, answered, why}` + names | answers; needs sign-in; not asked |
| `ConnectDialog`/`StepCheck`/`RedirectUri`, `DisconnectConfirm`/`TypedConfirm` | C3, C5 | registry `setup_steps`; the plan | as the specs |
| `TerminalStep`, `PersonSteps` | one terminal act; an ordered list | command, who, why | not done; done from a record |
| `StatusStrip` (new) | C8 | counts from the loaders | all-clear; some wrong; stale |

**`EffectLine` wording** (proposed; the mapping is the build's to confirm): a limit is "at once, for new acts" and "after the next start" where the registry says `restart`; a pause is "at once"; a cadence change or adoption is read by the scheduler on its next look (its interval is not verified here), shown as **from the next job**; a credential change is "from the next job"; a running service may hold its vault session up to 15 minutes idle, so say so.

**Fixed words** (use exactly): "not set up", "needs sign-in", "connected", "failing", "paused", "Credential set", "No credential", "Adopt the default", "Paused by A. Admin", "Never scheduled: it writes", "Floor", "Ask it to stop", "A person's check", "A person at the terminal on OFFICE-PC", "The vault was not asked", "Viewing as NAME (admin view): go back to yourself first".

## E. Glyphs

Use the console's glyphs. Proposed in the handoffs: not set up `circle-dashed`, needs sign-in `key-round`, connected `circle-check`, paused `circle-pause`. **Name replacements** where one glyph carries two meanings (`circle-pause` already means "held for the board", `key-round` "access", `circle-check` "on the record"). **Failing needs a glyph** that is neither the overdue clock (`triangle-alert`) nor "going ahead would be wrong" (`octagon-alert`). New ones, named for the idea: service stale (a heartbeat that stopped), draining (finishing), a terminal step (a person at a machine), the vault (a locked store), and the three effect words. One meaning per glyph. The limits sources keep `circle-dashed`, `settings-2`, `landmark`, `pencil`.

## F. Decisions that are the design's, in one list

1. Instance as its own nav group (recommended) or Status growing into it.
2. A community row: five dots or a summary ("6 connected, 1 needs sign-in").
3. The glyph for "failing".
4. A sign-in pause over many schedules: one banner over the group (recommended) or a mark on each row.
5. `ConnectDialog`: a page per step or a checklist with expanding steps (Google's nine); resume from the failed step or from the start with the done collapsed.
6. How two communities share one GPU lane on `ServiceStatus`.
7. Whether the Administration group in Work is a tab or a group on the list.
8. The disconnect result's layout and the wording of the typed confirmation.
9. Whether `MigrationPlan` sits on the vault panel or inside the connect run.
10. How the status strip folds on a phone.

**Not the design's:** whether the board allows scheduled writes; the default cadences; the secret manager when hosted; whether officers see the administrator's name on a disconnect (recommended: date only); whether the console ever writes a settings file or starts the service.

## G. What can be designed now, and what waits

| Part | Built today | Waits on |
|---|---|---|
| Instance data | Three read-only loaders, admin only, disk only: `instance-service`, `instance-integrations` (`?scope=instance`, `?vault=1`), `instance-schedules`; plus `instance-limits` | **No view reads the first three** (searched `ui/src`); no `instance-vault` loader and no vault JSON (`?vault=1` returns names only under `--dev`) |
| Screens that exist | `#/status` (`StatusView`), `#/jobs` (`JobsView`), `#/setup/limits`, `#/instance/limits` (`LimitsView`), `#/communities`, `#/people` | `#/instance`, `/communities`, `/integrations`, `/service`, `/schedules`; the cards, the dialogs, the strip |
| CLI | `jason integrations list` and `check [--live --by]` **only**; `jason cadence` (`--every --cron --window --pause --resume --restore --run-now`); `jason daemon status\|stop`; `jason serve --install-task`; `jason vault status\|migrate`; `jason login`; `jason google status\|scopes\|setup\|sign-in`; `jason limits` | `jason integrations import\|connect\|disconnect` **do not exist** (two registry steps still name `import`) |
| Writes from the console | Limits only (`POST /api/write/limits/...`) | cadence changes, pause/resume/run-now, a live check, the disconnect, `SecretDrop`/`FileDrop`: each a `TerminalStep` until a route exists |
| Revoke at the provider; a log of connection acts | not built | `integration-acts.jsonl` and each provider's revoke |
| `integration-connect` and `service-run` as runs | designed | the run engine (`jason.workflows`, not built) and their definitions |
| Scheduler | adoption, floors, sign-in pause, write refusal, heartbeat 30 s, stale 90 s, misfire | cadences ship as defaults; none runs until a person adopts it; the default values are still open |
| Officers' read-only chips | none: Status is admin only | a loader for the state word and date |

Draw everything above from section H. Mark every part with no view "specified, not built".

## H. A made-up community to design against

"Oakview" (zone Pacific, machine OFFICE-PC, Google domain `example.org`, workspace "Example Workspace") with a second profile, "Pinecrest", never run. Today in the sample is Oct 12, 2099. Administrator: A. Admin. Officers read only: S. Placeholder (treasurer).

| Integration (Oakview) | State | Reason and detail |
|---|---|---|
| Google Workspace | needs sign-in | "no Google token on this machine: the first sign-in"; 7 schedules paused (sign-in); client in the vault |
| PayHOA | connected | connected by A. Admin Oct 1, last checked Oct 3, "ok: organization read"; no published rate, polite pace |
| Zoom | failing | "failed: 401 invalid client"; the setup step to revisit is the scopes |
| PostScanMail | paused | "Paused by A. Admin on Oct 5: provider maintenance" |
| Utilities (Example Electric) | not set up | credential never read |
| Law library (instance) | connected | "the checkout is there"; nothing to store |

- **Service**: Oakview running since 7:00 AM; the google lane busy (job 413, `jason drive --sync`, 1 minute); next five runs listed. Pinecrest: "jason serve has not run for this community". Variation: stale ("no heartbeat for 3 minutes; the process may be hung"); refused ("another worker holds this community").
- **Schedules** (Oakview): `gmail` every 10m 07-22, floor 2m, stale after 1h, held by the sign-in pause; `zoom` cron 0 3 * * *, floor 1h, changed by A. Admin Oct 5; `mail` proposed, not adopted; `county-secured` manual (a person downloads the workbook); a write command refused ("Never scheduled: it writes"); `payhoa-catalog` backing off, 3 failures, next try 4:10 PM. A below-floor entry (1m on Gmail) for the refusal.
- **Vault**: answers, 6 entries (`jason/instance/instance/signin/oauth-client`, `jason/community/oakview/payhoa/login`, `.../zoom/app`, and three more); `.env` still names two records ("copy" and "no vault path: a person decides"). Variant: "Keeper needs a sign-in" (day 27 of 30). Variant: not asked.
- **Jobs**: queued 2, running 1, done 40, failed 1 (a write waiting for a person), cancelled 0.
- **Status strip, Oakview**: service running since 7:00 AM; 5 community connections: 1 connected, 1 needs sign-in, 1 failing, 1 paused, 1 not set up; 7 schedules held; 2 sources stale; 1 job failed.
- **Disconnect**: Zoom for Oakview, connected Mar 2, 2099 by A. Admin, 3 schedules, vault entry `jason/community/oakview/zoom/app`, one record still named in `.env` (not edited), typed words "zoom oakview".
- **Reconnection run** (Google Workspace): steps `which`, `state`, `vault` done; `login`, `provider`, `credential` skipped (evidence holds); `signin` needs a person; `check` not started; `adopt` blocked (7 schedules); `keep` waiting.
