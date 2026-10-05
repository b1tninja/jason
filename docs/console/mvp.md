# From here: the first build, and what follows

The console is jason-ui served by jason-web ([architecture.md](architecture.md)). Much of what this page once listed as the first build already exists. This page says what is built, what the first build still needs (the engine's approvals in the browser), its acceptance criteria, how the CLI's `--yes` paths move onto approvals, what to do with the HTML prototype library, and the decisions still open.

## Built

| Piece | Where | Notes |
|---|---|---|
| The console frame, the dock, and the screens | `ui/` (`ConsoleShell`, `SCREENS` in `App.tsx`), `src/jason/web/` | [web-ui.md](../web-ui.md) lists every view and loader |
| Letters through their stages | `jason.tasks.approvals`, `#/approvals` (`ApprovalsInbox`, `DraftLetter`) | A board approval is a vote recorded by the president or the secretary with the meeting's date |
| The board loop | `#/agenda`, `#/room`, `#/decisions`, `#/meetings`, `#/minutes-review` | Votes by name, the CIV 4930 guard, executive session as the host's act |
| The approvals engine | `jason.approvals`: model, registry (`owner-info-tags`), store, audit, engine | `pytest tests/test_approvals.py` |
| `jason approvals` | `jason.commands.approvals` | Plan, show, decide, submit, confirm, decline, withdraw, apply (check without `--yes`), audit |
| Read-only MCP tools | `approvals_list`, `approval_show` (governance profile) | No tool decides or applies |
| The CLI's `--yes` in the audit log | `jason owner-info --apply --payhoa --yes [--by NAME]` → `audit.record_cli` | One line a write and a completion, then `cli.applied` |
| The prerequisites the earlier spec listed | one live read (`owner_info_apply.ReadOnce`), a result for each write (`execute_each`), unapplied writes stay pending, stable ids and bases, a rule on each write, `community()` in the adapter, `--by` on the CLI, `jason approvals` registered | Lessons `plan-reads-once`, `apply-loses-partial-results`, `complete-only-after-writes` (fixed) |

**Also built since this page was first written:**
- the write guard (`jason.web.guard`);
- the approvals routes (`jason.web.approvals`, with `--allow-apply`), covered by `tests/test_web_approvals.py`;
- the jason-ui plan review (`PlanReview`, listed by the `PlanApprovals` view in `#/approvals`, with `WriteRow`, `HeldNote`, `ChangedBanner`, `ApproveBar`, `SecondConfirm`, `CostLine`, `ApplyResult`, `AuditLog`);
- the components for the later screens (`Recitation`, `ReadingLabel`, `QuestionCard`, `StageSteps`), with the onboarding session in the Setup tab of `#/onboarding`;
- Sign in with Google (`jason.web.signin`), the private view, the owner view's loaders, and the role class.

**What the criteria below still find missing** (judged on the committed code):
- **The nav count** is the letters waiting on a person (`/api/approvals`'s `pending`, or the dock's `approvals` when someone is signed in). It does not add the plans waiting on a person.
- **The plan header** shows who asked, the read time, the fingerprint, who signed, the clock, and the cost. It does not show the kind's risk or reversibility: `GET /api/approvals/<id>` answers the approval alone, with no `kind` record.
- **An item's rule** shows as its citation ("Rule: …") and opens no `Recitation`: `PlanPanel` passes `PlanReview` no `recitations`, and the `cite` loader it would read does not exist ([screens/approvals.md](screens/approvals.md)).
- **Two people and plan age** read defaults: `PlanPanel` passes `twoPerson` from a field the answer does not carry, and `maxAgeHours` is the component's default of 24, not the kind's `max_age_hours`. The kind built today is one-person with 24 hours, so nothing is wrong yet; the first two-person kind would show no second-person step.
- **A plan older than its kind allows** is refused by the engine ("plan again", `engine.problems`), but the banner says "Decisions stand; apply reads live again first, or re-plan now". The words are corrected in the UI, not here.
- **A person's hold** shows "held for the board by NAME" with the reason, but not the `jason board` command that proposes its board item.
- **"No GET changes `data/approvals/`"** has no test that walks every GET route; `tests/test_web_approvals.py` checks that a GET to `check` is 405.

## The first build: engine approvals in `#/approvals`

The `owner-info-tags` kind, end to end in the browser, beside the letters. Every criterion is a test, or a check a person makes once. Most are built and tested (`tests/test_web_approvals.py`, `tests/test_approvals.py`, `ui/src/components/plans.test.tsx`, `ui/src/views/planapprovals.test.tsx`); the boxes stay open until a person has made the once-only checks, and the list above names what the committed code does not yet meet.

### The server

- [ ] `jason-web` binds `127.0.0.1:8080` by default. A request to `/api/*` with a foreign `Host` gets 421; a write with a foreign or missing `Origin`, a cross-site `Sec-Fetch-Site`, or no token gets 403 before its handler runs.
- [ ] No GET changes `data/approvals/`. A test walks every GET route.
- [ ] `POST /api/approvals/<id>/apply` is refused without `--allow-apply`, with the terminal command in the answer. With it, the server prints that apply is on, and `GET /api/session` reports `applyEnabled`.
- [ ] An apply needs the token in `X-Jason-Token` (not the cookie alone), a `by`, and `confirm` equal to the approval's fingerprint; otherwise nothing is written.
- [ ] `check` and `apply` with no Keeper session answer 503 with "run `jason login` in a terminal". No route asks for a credential.
- [ ] Every answer that leaves the approvals routes has emails and phone numbers masked.

### The screen

- [ ] `#/approvals` lists letters and engine approvals in one inbox, each row saying which it is. The nav count is the letters awaiting approval plus the plans waiting on a person. (As built, one screen holds two sections: "Plans of writes", a table, above "Letters", the grouped inbox; and the nav count is the letters alone.)
- [ ] One approval shows its header: the kind's title, status, requested by, the read time, the fingerprint's first 12 hex, the clock (`summary.deadlines` for the cycle), the cost (`CostLine`: "No cost" for tag changes), and reversibility from the kind.
- [ ] Items are grouped by owner (`group`). Each `WriteRow` shows the change before → after, why, the rule (opening its `Recitation` where `cite_document` resolves it), and the evidence.
- [ ] Held for the board, for a person, confirm with the owner, and what follows are in their own sections, with `HeldNote` on the held. **None has a checkbox**, and the server refuses a decision on one.
- [ ] A completion whose writes are not all approved says it will stay open, and approving it is refused with the writes it waits on.
- [ ] `ApproveBar` approves, rejects (reason required), or holds (reason required) the selected items, each through `Confirm`. Its submit button names the count and the person: "Approve 5 of 8 changes as Jane Example"; undecided items keep it unavailable, saying how many are left.
- [ ] Decisions save as made (`in_review`); leaving and returning keeps them.
- [ ] `SecondConfirm` appears when the kind or a high-stakes item needs a second person. Its name field starts empty; the first signer and the requester are refused.
- [ ] **Check** re-reads live and shows what apply would do (`ChangedBanner` when anything changed), writing nothing.
- [ ] With apply off, the approved approval shows the `Command` (`jason approvals apply ID --yes --by NAME`). With apply on, **Apply** goes through `Confirm`, echoing the fingerprint shown.
- [ ] A refused apply (changed since review) shows that nothing was written and links the new approval, which shows the earlier decisions as hints only.
- [ ] `ApplyResult` shows applied, failed, uncertain, blocked, and not applied, failures open, matching the audit log's `item.*` events.
- [ ] `AuditLog` shows the approval's events in order, and "chain verified" or the first broken line from `GET /api/approvals/audit?verify=1`.
- [ ] A person's hold shows "held for the board by NAME", apart from the planner's "held for the board", and the `jason board` command that proposes its board item until the engine proposes it ([approval-workflow.md](approval-workflow.md#12-the-board-decides-by-vote)).

### Parity

- [ ] A plan made with `jason approvals plan owner-info-tags --by NAME` is decided in the browser and applied in the terminal, and the other way round. The audit log records `via` for each act.
- [ ] `jason-mcp --profile governance` still has only `approvals_list` and `approval_show` for approvals.
- [ ] `jason owner-info --apply --payhoa --yes --by NAME` works as before and writes the same audit lines with `via: "cli"`.

### Non-functional

- [ ] A keyboard-only pass of review, decide, submit, confirm, and apply, with focus never under the sticky `ApproveBar`; a screen-reader pass of the approval page.
- [ ] Each new component has a test and a design-sync preview with plainly fake data.
- [ ] Nothing in `src/jason/web/`, `ui/src/`, or `docs/console/` names an association fact (`tests/test_profile.py`).
- [ ] The test suite runs with no network, no Keeper, and no Google token.

## After the first build

| Phase | What ships | Writes it adds |
|---|---|---|
| **2. The governance screens** | The screens with no counterpart, read-only first: Requests, Notices, Governing documents (with `Recitation` and `ReadingLabel`, both built, and a cite box), and the bands the specs add to existing screens ([information-architecture.md](information-architecture.md#where-the-proposed-screens-go)). The onboarding session (`StageSteps`, `QuestionCard`) is built, in the Setup tab of `#/onboarding` | `data/` records a person signs: an intake answer and its second person (`answer_intake_question`, `onboarding_confirm`), a duty done (`record_completion`), a posting recorded |
| **3. More kinds** | Registry rows with planners and appliers: Gmail drafts, calendar, Tasks, private Docs (a letter's Doc after its words are approved), PayHOA form updates, `delivery --audit --apply` | Each kind's own write, behind its row and `--allow-apply` |
| **4. Money and members** | Mailroom sends, owner email and mail batches, publishing forms, Vault holds: the two-person kinds. Members and units, once P2 masking exists | Postage, notices to members, legal holds |
| **5. Sign-in** | A credential for each officer (built: Sign in with Google, `jason.web.signin`; [setup.md](../setup.md#5-console-sign-in-jason-web)), roles enforced at each loader, the private view | The same writes, with authenticated names; apply without a server-wide flag, if the board so decides |

## Moving the CLI's `--yes` paths onto approvals

The CLI keeps working at every step. Each step changes one kind at a time, when its planner and applier exist.

| Step | What changes | `--yes` then means |
|---|---|---|
| **1. Audit everything** | Every `--yes` path writes `cli.applied` with `via: "cli"`, the person from `--by` or `--confirmed-by`, else the operating-system user. Built for `owner-info --apply --payhoa`; the rest follow | What it means today, now on the record |
| **2. Plan and apply through the engine** | The kind's planner and applier exist. `jason <command> --yes --by NAME` becomes sugar: plan, approve every approvable item as NAME, submit, apply, with the same re-plan check. `--by` becomes required for R2 kinds | "I approve all of this plan", recorded as an approval |
| **3. Two people where the registry says so** | A two-person kind refuses a bare `--yes` and takes `--approval ID` instead, applying only an approval with both signatures (`jason mailroom --send --approval ID`) | Not accepted for two-person kinds |
| **4. Jobs carry the approval** | `jason jobs add --confirm NAME -- approvals apply ID --yes --by NAME`. The worker runs approvals by id | — |
| **5. Retire bare `--yes` for R2 and R3** | `--yes` stays for R0 and R1 with `--by`. R2 and R3 go through an approval | R0 and R1 only |

The ungated writes come first, given a dry run, `--yes`, and then a registry row: `board --sheet`, `board --create-sheet`, `board --tasks`, `property-history --sheet`, and `request-comment` (lesson `google-writes-without-yes`, open).

## The HTML prototype library

`src/jason/console/ui/` is a static HTML and CSS component library (tokens, base styles, 30 components, previews, and four sample screens), uncommitted: it exists only in the working tree of the main checkout, and a commit of this repository has no `src/jason/console/`. It was written for the withdrawn server-rendered plan, and its ideas are ported into jason-ui where [components.md](components.md) maps them (the components it once marked being added are built).

**Recommendation: keep it as a design reference outside the package until the port is done, then drop it.**

1. **Now:** move it to `docs/console/prototypes/` (a person does this; it is not moved here). It is documentation, not code: nothing imports it, and under `src/jason/` it would ship in the wheel and read as a second UI. Keep its README, with a first line saying it is a reference for jason-ui and not served.
2. **What to carry over before dropping it:**
   - the measured contrast table for both schemes (jason-ui's tokens need the same table, measured against its own `--bg` and `--panel`, and a profile's brand tokens);
   - the `held` role color, as a jason-ui token for `HeldNote`;
   - the four sample screens (`approvals.html`, `approvals-changed.html`, `today.html`, `reader.html`) as design-sync previews of the composed screens;
   - the accessibility notes: the approve bar's reserved height, write rows that become cards under 760 px, row checkboxes in a label that fills the cell;
   - `masked-field` and `job-status`, which it lists as still to build, stay in [components.md](components.md#still-proposed). `private-switch` is built since, as `PrivateSwitch` (with `PrivateBand` and `PrivateAsk`).
3. **Drop it** once each jason-ui counterpart has a design-sync preview and the contrast table exists. Its `@dsCard` markers are for a design system that would duplicate jason-ui's; it should not be published as one.

Two design systems for one console would drift. jason-ui is the one that ships, so it is the one the design project syncs.

## Open decisions

For the person deciding the build. Each has a recommendation; none is decided here.

1. **The approvals store.** Keep the engine's JSON store as built (`data/approvals/apr-*.json`, `audit.jsonl`), beside the letters' store, rather than the earlier SQLite plan? Recommended: keep it, and close the lesson `approvals-store-location`.
2. **Names on engine approvals.** Should the console's door refuse a `by` that is not one of the profile's officers, as the letters' approvals already do? Recommended: yes for `via: "console"`; the CLI's `--by` stays free text until sign-in.
3. **Which kinds need two people.** As proposed: Mailroom sends, email and mail batches, publishing a Google Form, Vault holds, scheduling a hearing, switching a document's reading, and a PayHOA form update that changes an answered question (as a high-stakes item). Should completing an owner-information request, which emails the owner the board's comment, be one person under the board's rule (as built) or two?
4. **Reviewer and counsel.** `OfficerRole` has neither. Add them as roles, or as a separate grant in the profile? Until sign-in, is a self-asserted name acceptable for first signatures?
5. **Plan age.** Is 24 hours the right `max_age_hours` for every kind, or shorter for sends?
6. **A person's hold.** Should submitting a hold propose its board item automatically (`tasks.board_items.propose`, signed by the person), so it reaches the agenda without a second step? Recommended: yes; the engine records the hold only today.
7. **Plans from the browser.** Plans are made in the terminal; there is no plan route. Keep it so (a plan reads PayHOA live), or add a plan route behind the same flag as apply?
8. **The audit log off the machine.** Is a hash-chained local file enough, or should each day's last hash go somewhere a person keeps apart from this machine, such as the board's records?
9. **Outside resources.** Self-host Mermaid and the profile's font so the bundle loads nothing from elsewhere, and set a Content-Security-Policy naming only the Google and Zoom frames? Recommended: yes.
10. **The owner view of the new screens.** Requests, Notices, and Governing documents start board-only. Which, if any, get an owner version, and with what left out?
11. **The prototype library.** Move it to `docs/console/prototypes/` now and drop it after the port, as recommended above, or drop it now?
12. **Remote access.** Out of scope until the board adopts a written policy on who may see what, and there is sign-in. Confirm that it stays out.
13. **Requiring sign-in.** Google sign-in is built, but it is required only when the person starting jason-web passes `--require-sign-in`. Once every officer's address is on the roster, should that be the norm? And should apply then need a signed-in officer rather than `--allow-apply` alone? Recommended: require sign-in once the roster has every officer's address. Keep `--allow-apply` as well, as a second, separate act.
14. **A portfolio in one console.** Managers now have portfolios (`data/access/managers.json`), but one jason-web serves one community. Should jason serve several profiles in one process, with a community switch for a manager, scoped stores, and per-community sign-in? Or should it stay one jason-web per community, behind a small launcher? Recommended: one process per community for now, since each store, lock, and Keeper read assumes one profile. Revisit once a second community is onboarded ([profiles.md](../profiles.md)).

**Decided, and where.** The stack (React and Flask under waitress, not Starlette and Jinja2), the port (8080), and the absence of a token sign-in page were decided by what was built ([web-ui.md](../web-ui.md#why-this-shape)). Refusing the whole apply when any approved item changed, and keeping the MCP tools read-only, are built into the engine ([approval-workflow.md](approval-workflow.md#6-re-plan-before-apply)). The board's approval as a recorded vote, polls as member input, roll calls by name, executive session kept out, and no recommendation on a brief are the design handoff's ([web-ui-decisions.md](../web-ui-decisions.md#built-the-console-approvals-decisions-agenda-meeting-room-the-dock)).
