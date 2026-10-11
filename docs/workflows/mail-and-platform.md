# Workflows: mail and email, and running jason itself

Status: **design**, written to the template in [../workflows-design.md](../workflows-design.md) section 5. Nothing here is built as a workflow engine; each step is checked against what the repository does today (section 7), and anything not checked says "not verified". The people and values below are made up ("123 Main St", "A. Owner", "Example Gates", dates in 2099).

## 0. How the seven tasks relate

Seven tasks, in three groups. They share one store (`data/`), one Gmail read, and one approvals engine, and they differ in who may see them.

| # | Task (definition key) | Group | Subject of a run | Whose |
|---|---|---|---|---|
| 1 | Paper mail triage (`mail-triage`) | Mail | a period of mail | manager, secretary |
| 2 | Email awaiting us, sync to answer (`email-conversation`) | Mail | one Gmail thread | manager |
| 3 | A Gmail draft from an item (`gmail-draft`) | Mail | a source: a system, a hearing, a meeting | manager, one approver |
| 4 | The response inbox and a returned form (`response-inbox`) | Mail | a request, in a cycle | manager, secretary |
| 5 | Connecting an integration and keeping it connected (`integration-connect`) | Platform | an integration for one community | **administrator** |
| 6 | Running the service (`service-run`) | Platform | a community's service on a machine | **administrator** |
| 7 | Checking work in, recording lessons (`check-in`) | Platform | a change to the repositories | **developer** |

```text
paper mail ─(1)─┐                                   ┌─(3) gmail-draft ── approvals (gmail-drafts) ── Gmail drafts, never sent
                ├─ Inbox / open items ─(2) thread ──┤
Gmail headers ──┘                                   └─ emailed request ── PayHOA request (a person; no kind yet)
reply emails, scans, PayHOA forms ─(4) inbox ── confirm ── apply (members-cycles: docs/workflows/members-cycles.md)
(5) integration-connect ── feeds every source above ── (6) service-run (worker, scheduler, heartbeat, limits)
(7) check-in ── a developer's terminal; not a board matter
```

- **(1)-(4) are the board's and the manager's work.** They appear in Work to the offices that act on them.
- **(5) and (6) are the administrator's, not the board's.** They are shown only to one of jason's admins signed in as themselves (the server refuses anyone else and an admin viewing as someone else), never in the owner view, never to a director, secretary, treasurer, or manager. An officer sees a connection's *state* on Status and Setup, never these runs. Administrators configure; they approve nothing on a community's behalf (AGENTS.md; [../console/handoff-admin-components.md](../console/handoff-admin-components.md)).
- **(7) is a developer's workflow, and also not the board's.** Tasks 5 to 7 are shown only to the administrator, and task 7 only as a read-only procedure and lessons list; it stays in the terminal and the console offers none of its acts (section 2.7).
- **jason sends, mails, scans, forwards, shreds, and discards nothing** in any of them. A write outside jason is an approvals plan a person decides (task 3), a PayHOA write a person runs with `--yes` (task 2, a gap), or an act at the mail service (task 1).

## 1. The tasks

| Task | Trigger | Subject | Read first | Today's SOP |
|---|---|---|---|---|
| `mail-triage` | each week, and when new mail is read; a stated date in a letter | a period of days; one letter at a time inside it | [../mail.md](../mail.md), [../console/screens/mail.md](../console/screens/mail.md) | none (gap) |
| `email-conversation` | a thread's last message came in and none went out; a person opens the Inbox | a Gmail thread | [../gmail.md](../gmail.md), [../console/handoff-conversations-and-policies.md](../console/handoff-conversations-and-policies.md), [../console/handoff-mail-and-payment-attachments.md](../console/handoff-mail-and-payment-attachments.md) Part A | `respond` (requests only) |
| `gmail-draft` | a lead or item that ends in an email: an overdue system inspection, a saved hearing, a meeting's agenda | a source and a case | [../console/handoff-draft-from-item.md](../console/handoff-draft-from-item.md), [../console/reconciliation-seventh-cut.md](../console/reconciliation-seventh-cut.md) section 2 | none (the CLI help only) |
| `response-inbox` | a request is out (a cycle); each check; an owner hands in paper | a request key | [../responses-design.md](../responses-design.md), [../arrivals-design.md](../arrivals-design.md), [../console/handoff-responses.md](../console/handoff-responses.md) | `owner-info-cycle` steps 12-14 |
| `integration-connect` | taking on a community; a source reads `needs sign-in` or `failing`; a credential or token ends | an integration, community or instance | [../integrations-design.md](../integrations-design.md), [../console/handoff-instance-and-integrations.md](../console/handoff-instance-and-integrations.md) | `onboard` steps 6, 14, 15 |
| `service-run` | installing the service; a heartbeat stale or stopped; a schedule to adopt; a limit to change | a community's service | [../scheduler-daemon-design.md](../scheduler-daemon-design.md), [../jobs.md](../jobs.md), [../instance-limits.md](../instance-limits.md) | `onboard` step 15 |
| `check-in` | before any commit to jason or payhoa; whenever a task goes wrong | a change | AGENTS.md "Lessons and procedures" | `check-in` |

## 2. The definitions

Columns: **kind** is one of the seven in the spine; **role** is who acts; **needs** lists step ids; **produces; evidence** is what the step makes and what shows it is done; **clock (basis)** uses `law`, `documents`, `proposed policy`, `person`, and one more this family needs, `provider` (a vendor's published limit or a credential's life; see section 11); **repeat / skip** is per unit of the subject and the skip rule. "No CLI" marks a step with no terminal command, which breaks the spine's terminal-first rule (section 8).

### 2.1 `mail-triage` (paper mail)

Subject: a period (`days`, default 30). Repeats per letter in the *act* and *review* lanes. A run's letters come from `mail_brief` (act, review, not scanned).

| id | Title | Kind | Role | Needs | Produces; evidence | Command | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| `fresh` | Is the mailbox read recently? | check | jason | none | the mail store's newest read vs the `mail` source's stale-after | `jason mail --offline` | stale after 3 days (proposed policy: the `mail` cadence is `proposed`) | once; never skipped |
| `sync` | Read the mailbox | job | worker | `fresh` failed | job link; `data/mail/items.json`, scans, envelopes | `jason mail` | `0 8 * * *`, floor 1h (proposed; runs only once a person adopts it) | once; skipped when `fresh` passes |
| `checks` | Check letters against jason's records | check | jason | `fresh` | findings: addresses, escrow clocks, tax bills, bank balances, checks, preliminary notices | `jason mail --checks` | an escrow request: Civil Code 4530(a)(1) (law, section 4) | once |
| `brief` | Read the lanes | check | jason | `fresh` | lanes, `byKind`, `upcomingDeadlines`; a sort, not a reading | `jason mail --days 30` | a letter's stated date: a reading until a person confirms it (basis `person`) | once |
| `read` | Read each letter | person | manager, secretary | `brief` | "read" attested per letter; the scan opened by a logged `Doc` view (P2) | `jason mail --item ID` | none | per act/review letter; a letter that carries a credential is held (P4): read the PDF at a terminal and attest only "read" |
| `kind` | Is the sort right, and whose is it? | branch | manager | `read` | a path: board / counsel / bill / file / another association's mail | none | none | per letter |
| `choose` | Record the choice | person | manager, secretary | `read` | a row in `data/mail/triage.json`: choice (scan, forward, shred, discard, keep), by, on, note, history | **no CLI**; `POST /api/write/mail-triage/<id>` | none | per letter; skippable with a reason for `file` urgency |
| `carry` | Carry it out at the mail service | person | manager | `choose` | attested with the date; the service may bill for a scan or a forward | the service's own site; jason does none of it | none | per letter whose choice is not *keep* |
| `await` | Wait for the scan | wait | nobody | `carry` (scan) | the next `jason mail` shows `scanned`; arrival ends the wait | `jason mail` | jason's own measure: the median delivery-to-scan time (`jason gmail`); an age, never a deadline | per scan letter |
| `act` | Act on a stated date | person | manager | `read` | a follow-up with the date; a dock task | `jason followups --add --date D --text T --by NAME` | the letter's stated date (`person` once confirmed) | per letter with a date |
| `board` | Put it before the board | decision | board; the secretary or president records | `kind` = board | a board item; the decision as taken, with its meeting | Board action items (`#/actions`); command not verified | the meeting calendar (meetings family) | per letter that needs the board |
| `close` | Close the period | check | jason | all letters chosen or marked "no action" | `chosen` equals `items` in the `mail-triage` loader | none | none | once |

### 2.2 `email-conversation` (a thread, sync to answer)

Subject: a Gmail `threadId`. A person opens the run from an Inbox row; jason does not open one on its own (decision, section 11).

| id | Title | Kind | Role | Needs | Produces; evidence | Command | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| `fresh` | Is Gmail read recently? | check | jason | none | the store's `syncedAt` and window (730 days) vs `gmail` stale-after | `jason gmail` | stale after 1h (proposed policy; the cadence needs a person's adoption) | each open |
| `sync` | Read Gmail headers | job | worker | `fresh` failed | the store under `data/gmail`; headers only, no bodies | `jason gmail --sync` | every 10m 07-22, hourly outside, floor 2m (provider: Gmail's published quota; adoption proposed) | skipped when fresh |
| `listed` | Whose move is it? | check | jason | `fresh` | status: awaiting us / awaiting them / notice / internal, from the last message; always with the caveat "someone may have answered by phone" | `jason threads --status "awaiting us"` | none | once; reopened by a later inbound message |
| `read` | Read what it asks | person | manager | `listed` | intent and topics (a reading, labeled); where the answer is likely written (leads, not rulings) | `jason inbox`; `jason replies` | reply history: three in four answered within N days at that level (jason's count, not a standard) | once |
| `route` | Which path? | branch | manager | `read` | member request / vendor / counsel / government / notice (close) / executive or legal (hold for the private view) | none | none | once |
| `request` | Enter an emailed request in PayHOA | plan | manager | `route` = request | a PayHOA request that is never approved, denied, or assigned | `jason request-links --create THREAD --message TEXT --yes` (a person's `--yes`; **no approvals kind** yet) | a records request: Civil Code 5210(b) (law, section 4) | skipped unless the path |
| `leads` | What sits near it | check | jason | `read` | payments, letters, Drive files, PayHOA requests from 14 days before to 60 after: leads, never answers | `jason threads`; `jason party UNIT` | none | once |
| `decide` | Decide the reply | person | manager (the board if it commits the association) | `route`, `leads` | an outcome: reply, answered by other means, forward, no reply needed | none | none | once |
| `draft` | Prepare a draft | plan | manager | `decide` = reply | a Gmail draft: a built case through task 3, or a reply in the thread for an emailed request | `jason respond --draft email:ID --gmail --yes` | none | skipped unless a reply |
| `assign` | Forward or assign | person | manager | `decide` = forward | assignee and a follow-up date as the person states them; a forward is never an answer | `jason followups --add` | the person's date (`person`) | skipped unless a forward |
| `send` | Send it | person | manager | `draft` applied | attested; evidence is a later outbound message the next sync sees (jason has no send method) | Gmail | none | once |
| `wait` | Wait for the other side | wait | nobody | `send` or `assign` | an inbound message arrives, or the follow-up date passes | `jason gmail --sync` | follow-up date (`person`); "past the usual time" is labeled as reply history | until arrival |
| `follow` | Ask again | person | manager | `wait` expired | a follow-up done, deferred, or dropped, with a reason | `jason followups --done/--defer/--drop ID --by NAME` | the person's date | repeats |
| `handled` | Mark handled offline | person | manager | any | an append-only note with name and date; a later message reopens the run | **no CLI, no store yet** | none | optional |
| `close` | Close | check | jason | `send`, `handled`, or `route` = notice | status is awaiting them or internal, or a person's note | none | none | once |

### 2.3 `gmail-draft` (a draft from an item, never sent)

Subject: `proposal-request:<system key>`, `hearing:<unit address>`, or `meeting-notice:<ISO date>`. These are the three cases of the built kind `gmail-drafts`; a free-text reply composer is not built.

| id | Title | Kind | Role | Needs | Produces; evidence | Command | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| `source` | Is the source there and current? | check | jason | none | a system in `jason inspections`; a saved hearing; the agenda file `data/board/agenda-DATE.md` | `jason inspections`; `jason hearing`; `jason board --agenda DOC_ID` writes the agenda | none | once; the run says "stale" when the source changes later |
| `purpose` | Choose the case | person | manager | `source` | one of the three cases | none | none | once |
| `commits` | Does it commit the association? | branch | manager | `purpose` | none of the three cases accepts, authorizes, or gives notice under a contract; a purpose that does is not a case, so the path ends | none | none | once |
| `board-ok` | The board's recorded decision | decision | board; secretary or president records | `commits` = yes | the meeting and motion | meetings family | the next meeting | skipped for the built cases |
| `recipient` | Choose `to` and `cc` | person | manager | `purpose` | one plain address each, at most 10; none is a default, nothing comes from a document's text; for a proposal request jason lists addresses on file as suggestions | none | none | once; a member's name or unit never goes to a vendor (a person's check: the kind has no automatic block) |
| `preview` | See the email without a recipient | check | jason | `purpose` | the subject and suggested addresses; a plan with no `to` has no item | `jason draft --proposal-request SYSTEM` (dry run) | none | once |
| `plan` | Plan, decide, apply | plan | manager plans; one named approver decides | `recipient` | one item (subject, recipients, attachment names, body with any line giving a code withheld); a basis hash of the composed email; applied = a draft id | `jason approvals plan gmail-drafts --scope JSON --by NAME`; `decide`, `submit`, `apply ID --yes --by NAME` | the plan is planned again after 6 hours (the kind's `max_age_hours`) | once; a changed source supersedes it |
| `send` | Read it in Gmail and send | person | manager | `plan` applied | attested; jason never sends | Gmail | none | once |
| `trail` | Sent? Answered? | wait | nobody | `send` | a later outbound or inbound message on the sync's headers; a draft deleted in Gmail reads "withdrawn" | `jason gmail --sync` | none | until arrival |
| `follow` | Ask again | person | manager | `trail` | a follow-up | `jason followups --add` | the person's date, or the purpose's proposed number (labeled proposed) | optional |

### 2.4 `response-inbox` (an arrival, recognized, read, confirmed)

Subject: a request key. The cycle's dates, the return-by clocks, and the apply belong to the members family (`docs/workflows/members-cycles.md`); this definition ends at *confirmed* and hands over.

| id | Title | Kind | Role | Needs | Produces; evidence | Command | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| `check` | Look at every channel | job | worker | an adopted cadence, or a person | arrivals kept as `new`; a `checked` row per channel (PayHOA, email, mailed scan, Google Form, keyed) | `jason responses --check` | stale after 1 day (proposed; `responses-gmail` hourly, `responses-payhoa` every 2h, both `proposed`) | repeats per cadence; a channel no request uses is skipped |
| `channels` | Did each channel answer? | check | jason | `check` | `ended`: ok / sign-in / failed / skipped / never checked, each with its age | `jason responses --list` | a sign-in end pauses the integration's sources (section 3) | each open |
| `recognize` | Whose copy is it? | check | jason | `check` | recognized (a sent copy, by rung), candidate (a form, no copy), or not ours; the rung and how sure | inside `--check` and `--read` | none | per arrival |
| `branch` | Recognized, candidate, or not ours | branch | jason by fact, then a person | `recognize` | recognized goes on; a candidate is attached to a campaign by a person (command not verified); not ours leaves | none | none | per arrival |
| `look` | Look at it | person | manager, secretary | `recognize` | `seen` with the name | `jason responses --seen ID --by NAME` | none | per arrival |
| `read` | Read the returned form | job | worker (GPU lane with `--model`) | `look`, files | one reading per file hash; evidence for a person, never an answer | `jason responses --read ID --by NAME` | model preflight and the GPU lock | per arrival with a file; a PayHOA or Google Form arrival is structured and skips it |
| `confirm` | Confirm what it says | person | manager, secretary | `read` | keyed answers; corrected fields by name (P3) | `jason responses --confirm ID --by NAME [--set F=V]` | none | per arrival |
| `dismiss` | Not an answer | person | manager | before *recorded* | dismissed with a reason; not reversible today | `jason responses --dismiss ID --by NAME --why TEXT` | none | optional |
| `manual` | Key a paper return | person | manager | none | a `manual` arrival naming how it came | `jason responses --add-manual` | none | optional |
| `outstanding` | Who has not answered | check | jason | `check` | owners sent a copy less answers; never-asked and unreachable apart | `jason responses --outstanding` | cycle dates (members family) | each open |
| `handover` | Apply the confirmed answers | plan | members family (`owner-info-tags`) | `confirm` | `recorded` once the writes are made (`mark_recorded`) | `jason owner-info --apply --payhoa` | the cycle's entry date (members family) | link only |

### 2.5 `integration-connect` (administrator only)

Subject: an integration for one community, or for the instance. One run per integration; it stays open as the watch (`keep`). The vault is the development environment's store (Keeper); a production installation reads from its own secret store, chosen when it is hosted. The console asks the vault only under `jason-web --dev`.

| id | Title | Kind | Role | Needs | Produces; evidence | Command | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| `which` | Which community and data folder? | check | jason | none | the community in use and where the choice came from | `jason which`; `jason use --list` | none | once; never skipped (lesson `a-default-community-must-be-visible`) |
| `state` | Read the integration's state | check | jason | `which` | one of five: not set up, needs sign-in, connected, failing, paused, with its `why` | `jason integrations list` | stale after the integration's `stale_after` (provider defaults, proposed) | each open |
| `vault` | Does the credential store answer? | check | jason | `which` | the backend, "Answers: yes, N entries", names only; or "Keeper is not signed in" | `jason vault status` | Keeper's 30-day idle logout (provider); the design warns from day 25 (not verified as built) | each open |
| `login` | Sign in to the store | person | administrator at a terminal | `vault` failed | a fresh Keeper session | `jason login` | 30 days idle (provider) | skipped when `vault` passes |
| `provider` | Set up the provider's console | person | administrator | `which` | per registry setup step (37 across integrations): a Cloud project, APIs, branding, audience Internal, scopes, a Web client; or a Zoom app | the provider's site; [../google-workspace-setup.md](../google-workspace-setup.md) | a redirect URI may take minutes to hours (provider) | per setup step; skippable if the integration needs none |
| `credential` | Put the credential in the store | person | administrator at a terminal | `provider` | the entry is "set" at its path, never its value | `jason google setup --from-file F --yes`; `jason vault migrate` then `--yes` | none | once; `jason integrations import` is named by the registry and **does not exist** |
| `signin` | Consent once | person | administrator at a browser | `credential` | a token per name saved to the store at once | `jason google sign-in --name drive --interactive` | a refresh token is given once; never retry `invalid_grant` | once per token name |
| `check` | A read that proves it | person | administrator at a terminal | `signin` | `connected`, with `connectedBy` and a `read` seal; only a person at a terminal, never an agent or a timer | `jason integrations check KEY --live --by NAME` | none | once; repeats after any failure |
| `capabilities` | Which capabilities are on | decision | administrator (configuration, not a decision for the board) | `check` | read capabilities on; a write capability off until used, each use still needing `--yes` | not verified at a terminal | none | optional |
| `adopt` | Adopt the schedules | person | administrator | `check` | each source adopted, never faster than its floor, never a write | `jason cadence --restore SOURCE --by NAME` | defaults and floors (provider-published; adoption proposed) | per source |
| `first` | Wait for the first scheduled read | wait | nobody | `adopt` | the source's `lastRead` stamp on Status | scheduler | next run time | per source |
| `keep` | Stay connected | wait | nobody | `check` | reopens on `needs sign-in`, `failing`, `paused`, a token near its end | `jason integrations list` | Keeper day 25; Google tokens end after six months unused, on a password change with Gmail scopes, at the 101st token, or after seven days in Testing (provider) | repeats; each end opens `signin` or `login` again |
| `disconnect` | Disconnect | person | administrator | none | revoke, delete the entry, pause schedules, log it | designed, **not built** | none | optional |

### 2.6 `service-run` (administrator only)

Subject: a community's service. A run is an episode: an install, or a recovery after a stale or stopped heartbeat. Day-to-day, healthy operation is a state on Status, not an open run.

| id | Title | Kind | Role | Needs | Produces; evidence | Command | Clock (basis) | Repeat / skip |
|---|---|---|---|---|---|---|---|---|
| `which` | Which community? | check | jason | none | the community and data folder | `jason which` | none | once |
| `heartbeat` | Is the service alive? | check | jason | `which` | state: none / running / draining / stale / stopped; the beat's age; `refused`; `failed`; the worker lock holder | `jason daemon status` | stale after 90 s; beat every 30 s (provider-free, jason's own constants) | each open |
| `start` | Start it | person | administrator at a terminal | `heartbeat` = none/stopped | a running process; the Task Scheduler entry at startup | `jason serve`; `jason serve --install-task` then `--yes` (a terminal run as administrator) | none | once; skipped when running |
| `refused` | Why did it refuse? | branch | administrator | `heartbeat` refused | another worker holds the community (a second process), or a part failed | `jason daemon status` | none | only if refused |
| `limits` | Check the limits in force | check | jason | `which` | each limit's value, source, range, last change | `jason limits` | none | each open |
| `limit` | Change a limit | person | administrator | `limits` | a dry run, then a confirmed change with a reason (no names in it); recorded under the signed-in name | `jason limits --set KEY=VALUE --reason TEXT --by NAME`, then again with `--yes` | none | optional; per limit |
| `adopt` | Adopt the schedules | person | administrator | `heartbeat` running | as `integration-connect` `adopt` | `jason cadence`; `--restore SOURCE --by NAME` | defaults and floors | per source |
| `write-sched` | Allow a scheduled write? | decision | board | `adopt` | recorded or refused; until then the scheduler refuses every `--yes` command | none (a standing open decision) | none | one-off |
| `paused` | A sign-in pause | branch | administrator | `adopt` | a pause by sign-in or by a person; a sign-in pause clears only on a good live check or `--resume` | `jason cadence --resume SOURCE --by NAME` after `jason integrations check KEY --live` | none | per paused integration |
| `jobs` | Read the queue | check | jason | `heartbeat` | queued, running, failed, done; a failed write waits for a person | `jason jobs` | a failed read retries 3 times, 5 minutes apart | each open |
| `drain` | Ask it to stop | person | administrator | `heartbeat` running | `drain.json` written; lanes finish their running job; nothing is killed | `jason daemon stop` | none | optional |
| `verify` | Everything current? | check | jason | `adopt` | Status standing per source; heartbeat fresh; free space on the drive jason writes to | `jason storage --check` | each source's `stale_after` | once |

### 2.7 `check-in` (developer; never in the console)

| id | Title | Kind | Role | Needs | Produces; evidence | Command | Repeat / skip |
|---|---|---|---|---|---|---|---|
| `facts` | Keep the community's facts in the profile | check | developer | none | no association fact in general code, docs, or fixtures (the boundary test) | `pytest tests/test_profile.py` | each change |
| `path` | Is the new file's name free? | check | developer | none | the path does not exist, or it is a file meant to change (lesson `new-module-name-already-taken`) | `ls PATH; git status --short PATH` | per new file |
| `fixtures` | Made-up values in fixtures | check | developer | none | the operator's own ids stay in `.env` (lesson `no-real-data-in-fixtures`) | none | per fixture |
| `scan` | Scan what will be committed | check | developer | `facts` | no owner or deed party, personal mailbox, signed link, token; no vendor, street, or association name in a general module's comment (lesson `comment-carried-profile-facts`) | `git diff --staged` | each commit |
| `commit` | Commit; push only when told | person | developer | `scan` | a commit by path (other sessions stage in the shared index) | `git commit -- PATHS` | once |
| `lesson` | Record what went wrong | person | developer | any failure | a lesson in `src/jason/community/lessons.py` (general) or the profile's `lessons.py` (private), with a guard if fixed; the procedure step names it | `jason lessons --area AREA` reads; the edit is in code | when a task goes wrong |
| `procedure` | Update the procedure | person | developer | `lesson` | the step added or changed in `procedures.py` | `jason sop KEY` reads | with each lesson |

**What the console never offers for this definition:** a Start button, a commit, a push, a diff or git status view, a lesson or procedure editor, or the profile's private lessons. The administrator may read `jason sop` and `jason lessons` as copied commands, nothing more. Git and the lessons file are not stores the console writes.

## 3. Branches and failure paths

| Where | What happens | The run says |
|---|---|---|
| `mail-triage` `fresh` fails and `sync` fails | the mail integration is `needs sign-in` or `failing`: the run goes `blocked` on `integration-connect`; no letters are listed as new | "Mail was last read DATE. The mailbox could not be read: REASON." Never an empty lane without the age |
| A letter carries a credential | held (P4): no scan, no envelope, no text; `read` records only "read at a terminal" | "Held: this letter holds a credential; it opens in no screen." |
| A letter names another association only | `misdirected`: `kind` branch sends it to "another association's mail" (P3), not to the board | "Not this association's mail: for a person to return or correct with the sender" |
| `choose` is changed later | a later choice replaces it and the history line keeps the change; a correction is a later event | "shred -> keep by A. Manager on 2099-10-04" |
| `await` never arrives (the scan never shows) | after the median delivery-to-scan time, jason opens a follow-up and the step reads "not scanned yet, N days", not failed | the person decides to ask the service |
| `email-conversation` `listed` is stale or the store's window is shorter than the question | an older question is a live read-only Gmail search, not a store search | "Last synced 3 days ago; what is awaiting us may be out of date" |
| A reply went out by phone, in person, or from another mailbox | jason cannot see it | the caveat stays visible; `handled` is the person's word |
| A thread is executive, legal, or counsel's | held for the private view; a director sees nothing of it | "Held: opens in the private view" |
| `request` rejected by the person | recorded; the thread stays in the run at `decide` | "Not entered in PayHOA: REASON" |
| `gmail-draft` `plan` has no recipient | no item; the step reads "nothing to approve: jason never picks who an email goes to" | the subject it would carry |
| `plan` source changed under a done step | the applier composes again; the hash differs; nothing is saved; the plan is `superseded` | `changed` event: "the source changed since the plan; nothing saved" |
| `plan` apply timed out | Gmail may have saved it: result `uncertain` | "Look in Gmail's drafts before planning again" |
| The draft is deleted in Gmail | the trail reads "withdrawn"; the run reopens at `plan` | "Draft not found in Gmail" |
| `response-inbox` `check` ends `sign-in` for a channel | the channel's row says so with the step; no retry on a timer; the scheduler pauses the integration | "PayHOA needs a sign-in: run `jason login`" |
| `recognize` finds a reference jason did not send | a finding, not an arrival to confirm | "A reference we did not send" |
| `read` finds no form | `isTheForm` false; the state stays `read`; the person dismisses or reads again | "Not the form" |
| `integration-connect` `check` fails | `failing` (or `needs sign-in` when the words name a sign-in); `connected` is never shown; a good live check clears it | the failure in plain words, masked of emails, numbers, and tokens |
| `signin` loses the token (revoked, six months unused) | `keep` reopens `signin`; every source of the integration is paused | "Sign in again; do not retry `invalid_grant`" |
| `adopt` is refused faster than the floor | refused with the floor and its source | "runs every 1m at its closest, faster than the floor 2m" |
| `service-run` heartbeat stale | the process may be hung; Task Scheduler restarts a failure, not a hang (lesson `task-restart-on-failure-limits`, open) | "No heartbeat for N minutes" |
| `service-run` a job fails | a read backs off (5 minutes doubling to a day, or a `Retry-After`); a write waits for a person | the job's last log lines, masked |
| A store changes under a done step | `changed` event with the difference; the step reads "changed since" | e.g. "mail read again; 3 new letters" |
| `choose` by two people, nearly together | the later write replaces the earlier and both stay in `history`; the store lock keeps the file whole | "changed by J. Example 2099-10-11 after S. Placeholder 2099-10-11" |
| `carry` is never done | nothing in jason can tell; the letter stays in its lane with its age | no step turns done on a guess |
| `confirm` names the wrong unit | the copy comparison (sent to, written, read) shows the difference; a person decides | "the copy was sent to 456 Oak Ln; the answers are for 123 Main St" |
| `read` cannot run (no GPU, model not loaded, commit short) | the job goes back for ten minutes without using an attempt; the person can key by hand | "Waiting for the model" |
| `credential` the registry names `integrations import` | the command is absent; the step shows the command that exists | "`jason google setup --from-file`" |
| `adopt` while a source's command writes | refused for good, not a missing adoption | "Never scheduled: it writes. A scheduled write is the board's decision." |
| `drain` while a lane runs a write | the lane finishes the job; a write is never cut | "draining: finishing its current jobs" |
| `check-in` finds a name in a general comment | the commit waits; the lesson is recorded | no console path |

## 4. The clocks and their basis

Only two statutes set a clock in this family, and both belong to a request or a request-like letter. Each is recited whole from `data/authorities`; jason's readings are labeled apart and the board or counsel reads where two readings remain.

**Civil Code 5210(b)** (current text, amended 2025, operative 2026-01-01), for an emailed or mailed records request from a member:

> "(b) When a member properly requests access to association records, access to the requested records shall be granted within the following time periods: (1) Association records prepared during the current fiscal year, within 10 business days following the association's receipt of the request. (2) Association records prepared during the previous two fiscal years, within 30 calendar days following the association's receipt of the request."

Paragraphs (3) to (6) name other timeframes (Articles 2 and 7, 5565, 5810, minutes, committee minutes, the membership list); the full subdivision governs. Whether a given letter or email is a "proper" request for "association records" is a reading, and not for jason to settle.

**Civil Code 4530(a)(1)**, for an escrow or resale request that arrives by mail or email:

> "Upon written request, the association shall, within 10 days of the mailing or delivery of the request, provide the owner of a separate interest, or any other recipient authorized by the owner, with a copy of all of the requested documents specified in Section 4525."

`jason mail --checks` counts the 10 days from the day the mail service received the request. That start day is jason's reading of "mailing or delivery"; the sender's mailing day may be earlier.

**Retention.** Civil Code 5210(a)(1) says association records are subject to inspection "For the current fiscal year and for each of the previous two fiscal years." Whether a shred or discard choice (task 1) for a letter that is an association record fits is a **question for the board and counsel**; the policy catalog lists a `records-retention` entry as a board policy (see [../policy-catalog-design.md](../policy-catalog-design.md)); whether this association has adopted one is not verified here. Until one is adopted, `choose` records the person's choice and the run shows the question beside any `shred` or `discard` of a legal, insurance, tax, or escrow letter. jason decides nothing.

| Clock | Where | Basis | Note |
|---|---|---|---|
| Records request, current fiscal year: 10 business days | `email-conversation` `request` | `law` | Business days skip weekends, not holidays, so the date is the earliest it can fall |
| Records request, previous two fiscal years: 30 calendar days | same | `law` | |
| Escrow or resale request: 10 days | `mail-triage` `checks` | `law` | start day is a reading |
| Acknowledge or answer a general email within N days | `email-conversation` | no basis | **The law is silent.** A question for the board; `response-standards` is a proposed policy ([../response-standards-design.md](../response-standards-design.md)); until adopted, no date, "no usual reply time on record" |
| "Likely needs a response", "past the usual time" | `email-conversation` | jason's count | Three replies in four, at least two days old, from the association's own history; says what the association did, not what it must do |
| A date a letter states | `mail-triage` `act` | `person` once confirmed | Before that, a reading from words near "due", "respond", "effective" |
| Follow-up date after a draft, a forward, or a thread | `follow` | `person` | A purpose's suggested number (for example, ask again in 10 business days) is `proposed policy` and carries no stamp |
| Mail, Gmail, responses stale-after (3d, 1h, 1d) | `fresh`, `check` | `proposed policy` | The integration defaults are for the board or administrator to adopt |
| Cadence floors, quotas, token lives, Keeper 30-day logout | `integration-connect`, `service-run` | `provider` | Published figures read 2026-10-05 ([../integrations-design.md](../integrations-design.md)) |
| Heartbeat stale at 90 s, beat 30 s | `service-run` | jason's constants | `serve.STALE_AFTER`, `serve.BEAT_SECONDS` |
| A scheduled write | `write-sched` | the board's | Open; the scheduler refuses meanwhile |

## 5. The screens

All routes sit under `#/work`, consistent with [../workflows-design.md](../workflows-design.md) section 4. None exists. Every row says what is built under it; a view that does not exist is marked **to add**.

| Route | Shows | From (loader and fields) | Built components | To add |
|---|---|---|---|---|
| `#/work/mail-triage/<period>` | the run rail; the lanes act / review / not scanned; per letter the Doc, the sort, the choice with its history, the stated dates | `mail-triage`: `act`, `review`, `unscanned`, `chosen`, `choices`, row `scan` (a `DocRef`) or `held`, `choice{choice,by,on,note,history}`, `deadlines`, `caveats` | `Doc` (variants `row`, `inline`), `Confirm`, `Tabs`, `DueDate`, `Pill`, `Caveats`; the existing `#/mail-triage` view | `WorkflowRail`, `RunStepPanel`; the triage choice moves into the step panel |
| `#/work/email/<threadId>` (a drawer from `#/inbox`) | `SyncBanner` (age, stale, never), the thread's headers, `FollowUpSuggestion`, `RelatedLeads`, the route choice, the draft entry | `open-items`: `threadsAwaitingUs[]{last,ageDays,who,subject,topics,link,likelyNeedsResponse,pastUsualTime,replyRate}`; `request-links`: `drafts`; `status`: the `gmail` row's `lastRead`, `standing` (administrator only today) | `Caveats`, `Command`, `DataTable`, `Evidence`, `Findings`, `Pill` | `SyncBanner`, `FollowUpSuggestion`, `RelatedLeads`; loaders `email-threads` (to add), `handled` store; Gmail's age on a non-administrator loader |
| `#/work/gmail-draft/<case>:<key>` | the three-case form (case, key, `to`, `cc`, signer, horizon, pdf), then the plan | `POST /api/approvals/plan {kind:"gmail-drafts", scope}` (exists; no screen calls it), `GET /api/approvals`, kinds `/api/approvals/kinds` | `PlanReview`, `ApprovalsView`, `Confirm`, `Command` | `DraftFromItem` (the three-case cut), the "stale source" banner, a trail store |
| `#/work/responses/<request>` | `CheckedStrip`, arrivals by state with counts and age, the open arrival, the reading beside the page | `responses`: `arrivals[]`, `inbox`, `checked[]`; `response?id=`: `reading`, `keyed`, `acts`, `left`; `outstanding-responses`; `campaign-status` | `Tabs`, `DataTable`, `Seal`, `Command`, `Evidence` | `CheckedStrip`, `ArrivalRow`, `ChannelMark`, `ScanReview` (the reading carries no page or box, so highlight-on-focus is not buildable), `NewResponsesCount` |
| `#/work/integration/<community>/<key>` | `ConnectionChip`, `IntegrationCard`, the stepper over setup steps, `TerminalStep` for each terminal act | `instance-integrations`: `integrations[]{key,state,why,credentialSet,vaultPath,capabilities,cadences,connectedBy,lastChecked,lastCheck}`, `vault{asked,answered,why}` | `Command`, `StageSteps`, `Pill`, `Seal`, `Caveats` | `ConnectionChip`, `IntegrationCard`, `CredentialLine`, `CapabilityList`, `RateLimitNote`, `CheckResult`, `PauseBanner`, `ConnectDialog` |
| `#/work/service/<community>` | `ServiceStatus` (parts, lanes, next runs), the schedule table, the vault panel, the limits link | `instance-service`: `communities[]{state,alive,age,lanes,schedules,refused,failed,drain}`, `staleAfterSeconds`; `instance-schedules`: `communities[].schedules[]{held,adopted,nextRun,lastResult,paused}`; `limits`, `instance-limits`; `jobs` | `LimitsView` (built; the dry-run then confirm pattern), `JobsView` (`Kanban`), `StatusView`, `Command` | `ServiceStatus`, `LaneRow`, `CadenceTable`, `CadenceEditor`, `VaultStatus`, `MigrationPlan`; a vault JSON loader |

**The Work list for this family** (each row: label, current step, due and its basis, age):

| Definition | Group | Row reads | Due and basis |
|---|---|---|---|
| `mail-triage` | Yours | "Mail since 2099-09-12: 4 letters without a choice" | none, or the nearest stated date (`person` once confirmed) |
| `mail-triage` | Waiting on a clock | "Letter from Example Escrow: stated date 2099-10-20" | the letter's date; escrow 10 days is `law` |
| `mail-triage` | Board | "Letter on the agenda of 2099-10-21" | the meeting (meetings family) |
| `email-conversation` | Yours | "Re: Gate repair estimate: 41 days, awaiting us" | none unless a records request (`law`) |
| `email-conversation` | Waiting on others | "Sent 2099-10-12; follow-up 2099-10-26" | `person` |
| `gmail-draft` | Waiting on others | "Plan waits on A. Director, current until 15:00" | the plan's 6 hours (jason's constant on the kind, not a deadline) |
| `response-inbox` | Yours | "3 new arrivals; checked 2 h ago" (always with its age) | cycle dates (members family) |
| `integration-connect`, `service-run` | Administration (admin only) | "Google Workspace needs sign-in: 7 schedules paused" | none; a token's end is `provider` |

**States, per screen.** Words are the server's where it has them.

| State | Mail triage run | Email run | Draft run | Response inbox | Administration runs |
|---|---|---|---|---|---|
| Loading | spinner, no counts | same | same | same | same |
| Empty | "Nothing in this lane." with the period and the store's age | "Nothing is awaiting the association in the last 30 days, as of the last read DATE" | "No email drafted for this item" | "Nothing new as of DATE" (never a bare zero) | "No communities have run the service" |
| Missing | "No mail on disk; run `jason mail`" (the loader's own note) | "No mail read yet" with `jason gmail --sync` | the source is not found: the command that makes it | "never checked" with `jason responses --check` | "never seeded" with `jason cadence` |
| Stale | the mail store's age first, in the page's top line | "last synced 3 days ago" before any row | "the source changed since the plan" | the channel's age and `ended` | the heartbeat's age; a source's standing from `stale_after` |
| Blocked | by `integration-connect` (the mailbox cannot be read) | by the same (Gmail) | by an unrecorded board decision, only for a commitment | by a channel's sign-in | by the step or fact, named |
| Changed since | "read again: 3 new letters" | a later inbound message reopens `listed` | the hash differs; nothing saved | a later arrival supersedes | a heartbeat or a connection moved |
| Director | counts of letters by lane; no senders | counts of threads | none | counts, states, ages; `countsOnly` | none (not shown) |
- **No send, scan, forward, shred, or discard control exists.** A copied `Command` carries the real command; the page never runs one. A check a live service answers (`integrations check --live`) is a `TerminalStep` ("A person at the terminal on this PC").
- **Use the existing screens.** `#/mail-triage`, `#/inbox`, `#/approvals`, `#/status`, `#/jobs`, `#/setup/limits`, `#/instance/limits` keep their routes; a run page links to them rather than copying them.
- **Print and export.** A run's history as a `Doc` with evidence addresses; never a letter's text for a P4 letter.

## 6. Privacy and roles

| Step or surface | Level | Who acts | Who reads | A director sees |
|---|---|---|---|---|
| Letter scan, envelope (`mail/*`) | P2; a credential letter P4 (never served); another association's mail P3 | manager, secretary | offices that open P2 | counts of letters by lane (not enforced on the server today: gap) |
| Triage choice, note | P1 (a name and a choice) | manager, secretary | the same | counts |
| Thread headers, subjects, senders | P2 | manager | offices that open P2 | counts |
| A thread naming a member | P1 name and unit; executive or counsel content P3 | manager | private view for P3 | "held" |
| Draft body | P1 to P3 by content; a code line withheld from the approval record | manager plans; one named approver | the approvals audience | "held" |
| Response inbox: list, reading, keyed answers | P3 (`responses/*`) | manager, secretary | offices that open P3 in the private view | counts, states, ages; no names, no `arrivals`; `countsOnly: true` (built) |
| Integration state, `why`, vault path | not secret; masked of emails, numbers, tokens | administrator | administrator only | nothing |
| Credential value | P4 | nobody; never shown, logged, copied, or put in a URL | nobody | nothing |
| Heartbeat `dataDir`, lanes, host | machine detail | administrator | administrator only | nothing |
| `check-in` | developer's terminal | developer | developer | nothing |

- A signed-in write replaces `by` with the signed-in name (the sign-in layer), so the triage screen's typed-name field is only for an installation with no sign-in.
- A run never shows an email address, phone number, or mailing address on a list. An owner's name appears only where the viewer opens P1 or P2, and only where the step needs it.
- A forward is never an answer; an automatic reply is set apart; a reading is "jason's reading" until a person confirms it.

## 7. What exists now (checked against the repository)

| Piece | Where | State |
|---|---|---|
| Mail sync, sort, brief, checks | `jason mail` (`--offline`, `--full`, `--resort`, `--reread-ocr`, `--days`, `--item`, `--checks`); `jason.tasks.mail`; MCP `mail_brief`, `mail_item`, `mail_checks` | built |
| Triage choice store | `jason.tasks.mail_triage.choose`, `data/mail/triage.json`, history kept, store lock | built; **web write only, no CLI** |
| Mail screens | `#/mail-triage` (`MailTriageView`: lanes, `Doc`, Confirm per choice), `#/inbox` (`InboxView`), loaders `mail-triage`, `open-items`, write `mail-triage` | built; the choice sends the typed name unless sign-in overwrites it |
| Gmail sync and threads | `jason gmail --sync`, `jason threads`, `jason inbox`, `jason replies`, `jason party`, `jason open-items`; MCP `email_threads`, `reply_needed`, `email_intents` | built; **no web loader** for threads, intents, or replies except `open-items` |
| Gmail's age on the Inbox | `status` row `gmail` (administrator only) | the Inbox shows no sync age |
| Conversation catalog, handoffs | [../conversations-design.md](../conversations-design.md) | design only; no `gmail_catalog`, no `Handoff` rows (searched `src/jason`) |
| Emailed request to PayHOA | `jason request-links --create THREAD --yes`; loader `request-links`; `DraftsView` shows the draft and a `Command` | built; a person's `--yes`; no approvals kind |
| Reply draft in the thread | `jason respond --draft email:ID --gmail [--yes]` | built; not an approvals kind |
| Gmail draft approvals kind | `gmail-drafts` (`jason.approvals.kinds.gmail_drafts`): cases `proposal-request`, `hearing`, `meeting-notice`; R1, one-person, 6 hours; `to` and `cc` chosen by the person; apply recomposes and saves nothing on a different hash | built; `jason approvals plan gmail-drafts --scope JSON`; route `POST /api/approvals/plan` exists; **no screen calls it** |
| `jason draft` | `--hearing`, `--proposal-request`, `--meeting-notice`, `--list`, `--show`, `--edit`, `--to`, `--pdf`, `--signer`, `--horizon`, `--yes` | built; no `--cc`, no `--item`, no `--purpose` |
| Free-text composer, trail store, per-sentence provenance | [../console/handoff-draft-from-item.md](../console/handoff-draft-from-item.md) | design only |
| Response inbox | `jason responses` (`--check`, `--list`, `--show`, `--read`, `--confirm`, `--seen`, `--dismiss`, `--outstanding`, `--add-manual`); `jason.tasks.response_inbox`, `recognize` (seven rungs); loaders `responses`, `response`, `outstanding-responses`, `campaign-status`, `followups`, `form-library` with director counts only | built; **no screen** under `ui/src` calls them |
| Follow-ups | `jason followups` (`--done`, `--defer`, `--drop`, `--add`); loader `followups`; no web writer | built; terminal acts |
| Integrations | `jason integrations list`, `check [--live --by]` only; registry, connections; `jason google status/scopes/setup/adopt-installation-record/sign-in`; `jason vault status/migrate`; `jason login` | built; **`import`, `connect`, `disconnect` do not exist** |
| Administrator loaders | `instance-service`, `instance-integrations` (`?scope=instance&vault=1`, vault asked only under `--dev`), `instance-schedules`, `status`, `limits`, `instance-limits`; each refuses a non-admin | built |
| Administrator views | `#/status` (`StatusView`), `#/setup/limits`, `#/instance/limits` (`LimitsView`), `#/jobs` (`JobsView`) | built; **no view for the three instance loaders** (searched `ui/src`) |
| Scheduler, worker, service | `jason.scheduler` (adoption, floors, sign-in pause, `WRITES_REFUSED`), `jason.jobs` (lanes, `--confirm` for a write), `jason.serve` (heartbeat 30 s, stale 90 s, drain), `jason serve`, `jason daemon status/stop`, `jason cadence` (`--restore`, `--restore-all`, `--pause`, `--resume`, `--run-now`) | built |
| Scheduler cadences | `gmail` every 10m 07-22 (floor 2m, stale 1h), `mail` `0 8 * * *` (proposed), `responses-gmail` and `responses-payhoa` (proposed) | built as defaults; none runs until adopted |
| SOPs | `check-in`, `respond`, `owner-info-cycle`, `onboard` | built; none for mail triage, email, drafts, or the service |
| Lessons | `jason lessons --area`, `jason sop KEY`; edited in `src/jason/community/lessons.py`; no area for integrations or the service | built; open: `serve-logs-nowhere-under-task-scheduler`, `scheduler-log-unrotated`, `task-restart-on-failure-limits` |

**Not verified:** how a capability is switched on or off at a terminal; a command to attach a `candidate` arrival to a campaign; the command that puts a letter before the board; whether any scheduled cadence is adopted on this machine (it is runtime data); `jason integrations check` on an instance integration with no source.

## 8. Gaps and the build order

Gaps found while checking (each is a build item or a decision):

- **The triage choice has no CLI.** The write is web-only, so a run cannot be driven from a terminal. Add `jason mail --choose ID --choice C --by NAME`, calling `choose`.
- **The triage and Inbox loaders carry no office check,** and director counts-only is applied only to the requests loaders. A director reading `mail-triage` or `open-items` gets letters and threads by name. Enforce on the server, as `counts_only` does for responses.
- **The Inbox shows no sync age.** The Gmail age is in `status`, which is the administrator's.
- **No web loader for threads, intents, or reply rates,** and no "handled offline" store.
- **No approvals kind** for entering an emailed request in PayHOA (`payhoa-requests-from-email`, R2, one person) or for a reply draft in a thread. `gmail-drafts` covers three cases only.
- **No screen starts a `gmail-drafts` plan,** though the route exists. The plan needs this server's token header and live reads on.
- **`gmail-drafts` has no automatic privacy block:** a hearing body names a unit and goes to the recipient the person chose; the vendor rule (a member's name never goes to a vendor) is a person's check today.
- **The responses loaders have no screen,** and a reading carries no page number or box, so `ScanReview`'s highlight-on-focus cannot be built from it.
- **The registry's setup steps name `jason integrations import`,** which does not exist. The console's `ConnectDialog` and `TerminalStep` need the real commands (`jason google setup --from-file`, `jason vault migrate`).
- **Three instance loaders have no view;** the vault has no JSON form; draining and the other part states are not drawn.
- **No mail, email, draft, or service SOP,** and no lesson area for integrations or the service.
- **The service has no log under Task Scheduler** and does not restart a hung process (open lessons).

Build order, smallest first (the spine's order holds: the engine, then one family):

1. **Read-only runs for the administrator's definitions.** `integration-connect` and `service-run` fold entirely from stores that exist (connections, heartbeats, schedules, Status). Build them as derived views over the three instance loaders first, with the three missing views. No run store needed.
2. **A CLI for the triage choice** and the director counts-only check on `mail-triage` and `open-items`.
3. **`mail-triage` as a run** over `mail-triage` (state folds from `triage.json` and `items.json`).
4. **The Gmail age on the Inbox** and an `email-threads` loader; then `email-conversation` as a drawer.
5. **A start form for `gmail-drafts`** (three cases), calling `POST /api/approvals/plan`, landing in the Approvals screen.
6. **The responses screen** (`CheckedStrip`, `ArrivalRow`, then `ScanReview` after the reader emits page and box), tied to the members family.
7. **New approvals kinds** (`payhoa-requests-from-email`) and the free-text composer last.
8. **SOP rows** for `mail-triage`, `email-conversation`, `gmail-draft`, `integration-connect`, and `service-run`, so the definitions read the existing `Procedure` rows.

## 9. Sample runs (made up)

### 9.1 An email awaiting us, to a saved draft (`email-conversation` then `gmail-draft`)

Thread "Re: Gate repair estimate", from Example Gates (a vendor), 41 days old, with an estimate attached. Manager: J. Example. Today in the sample: 2099-10-12.

| Step | State | Detail |
|---|---|---|
| `fresh` | done | Gmail last read 2099-10-12 07:10; stale after 1h; fresh |
| `listed` | done | awaiting us; "someone may have answered by phone; jason cannot see that" |
| `read` | done | intent: request for information; topics: maintenance; a lead: a PayHOA payment to Example Gates 2099-08-02 (not an answer) |
| `route` | done | vendor path |
| `leads` | done | 1 payment, 0 letters, 0 Drive files |
| `decide` | done | reply; asks about the estimate; does not accept it (no recorded board decision) |
| `request` | skipped | path is vendor |
| `draft` | needs a person | no free-text composer; J. Example writes the reply in Gmail; not a built case |
| `send` | not started | |
| `wait` | not started | follow-up date proposed by the person: 2099-10-26 |

Second run, `gmail-draft`, for a different item: "Annual sprinkler inspection overdue", system key `sprinklers`.

| Step | State | Detail |
|---|---|---|
| `source` | done | system `sprinklers` found; last report 2098-03-14 |
| `purpose` | done | `proposal-request` |
| `commits` | done | no: asks for a proposal and reports; accepts nothing |
| `recipient` | done | `to`: office@example.com, chosen by J. Example from 3 addresses on file |
| `preview` | done | subject shown; 3 suggestions listed |
| `plan` | waiting | planned 2099-10-12 09:00; 1 item; waits on one named approver (A. Director); plan current for 6 hours |
| `send` | not started | |
| `trail` | not started | |

### 9.2 A week of paper mail (`mail-triage`)

Period 2099-10-05 to 2099-10-11, 6 letters. Manager: J. Example; Secretary: S. Placeholder.

| Step | State | Detail |
|---|---|---|
| `fresh` | done | mail read 2099-10-11 08:00; stale after 3 days; fresh |
| `checks` | done | 1 finding: a letter addressed to the site rather than the box |
| `brief` | done | act 1, review 2, not scanned 3, file 0 |
| `read` | 2 of 3 done | the act letter and one review letter read; one review letter is held (credential), read at a terminal |
| `choose` | 2 of 6 | act letter: *keep* by J. Example 2099-10-11; review letter: *scan* |
| `carry` | needs a person | the *scan* letter: J. Example asks the service, which may bill |
| `await` | waiting | scan requested 2099-10-11; usual delivery-to-scan 2 days (jason's measure) |
| `act` | waiting | the act letter states 2099-10-20; follow-up added by J. Example |
| `board` | not applicable | no letter needs the board |
| `close` | blocked | 4 letters have no choice; 3 are not scanned |

### 9.3 The event log of the reconnection (excerpt, newest last)

| At (UTC) | Event | By | Detail |
|---|---|---|---|
| 2099-10-12 13:00 | `opened` | A. Admin | definition `integration-connect`; subject google-workspace for `example-village` |
| 2099-10-12 13:00 | `check-ran` | jason | `state`: needs sign-in; `why`: no Google token on this machine |
| 2099-10-12 13:01 | `check-ran` | jason | `vault`: answers, 6 entries |
| 2099-10-12 13:01 | `skipped` | jason | `login`, `provider`, `credential`: their evidence holds |
| 2099-10-12 13:20 | `attested` | A. Admin | `signin`: token `drive` saved to the store at its path (no value logged) |
| 2099-10-12 13:22 | `check-ran` | A. Admin | `check`: ok, "a Drive list and a Gmail profile read succeeded" |
| 2099-10-12 13:22 | `step-ready` | jason | `adopt` for 7 paused sources |
| 2099-10-12 13:25 | `changed` | jason | `adopt`: `jason cadence` shows the 7 schedules no longer paused; the good check cleared the pause, so no `--resume` was needed |
| 2099-10-12 13:41 | `job-finished` | scheduler | `first`: `gmail` read, job 412 done |
| 2099-10-12 13:41 | `waited` | jason | `keep`: watching; reopens on `needs sign-in` |

### 9.4 Reconnecting after a sign-in pause (`integration-connect`, administrator)

The vault answered; the mailbox's Google token ended.

| Step | State | Detail |
|---|---|---|
| `which` | done | community `example-village`, data folder shown to the administrator only |
| `state` | done | `needs sign-in`: "no Google token on this machine: the first sign-in" |
| `vault` | done | "Answers: yes, 6 entries" (asked under `--dev`); production would read its own store |
| `login` | skipped | vault passes |
| `provider` | skipped | client already stored |
| `credential` | skipped | |
| `signin` | needs a person | A. Admin runs `jason google sign-in --name drive --interactive` at the terminal |
| `check` | not started | `jason integrations check google-workspace --live --by "A. Admin"` |
| `adopt` | blocked | 7 schedules paused by the sign-in; a good check clears it |
| `first` | not started | |
| `keep` | waiting | reopens on the next `needs sign-in` |

## 10. Acceptance criteria

A test could check each:

1. **Derived state.** A `mail-triage` run's `chosen` equals the count of letters with a `choice` in the loader; changing a choice appends a history line and leaves the old one; with sign-in required the recorded `by` is the signed-in name.
2. **Held letters.** A letter marked as carrying a credential shows `held` and no `scan`; its `read` step offers no Doc; its text is absent from the run page and the export.
3. **No act-for-jason control.** No step of any definition here has a command that sends, mails, forwards, shreds, discards, or scans. A test scans every definition's `command` for those verbs and for `--approve`.
4. **Stale first.** An Inbox row with a Gmail store older than the integration's stale-after shows the age before the row; "awaiting us" always carries the phone-or-meeting caveat.
5. **Draft.** A `gmail-drafts` plan with no `to` has zero items and says "nothing to approve"; a changed source between plan and apply saves nothing and marks the step `changed`; the page has no word "send" except "send it from Gmail".
6. **Recipient.** No address is pre-filled from a document's text; a malformed address is refused with the kind's own sentence.
7. **Response inbox.** A director's `responses` and `outstanding-responses` return `countsOnly: true` and no owner key; `response` is refused; no list row shows an email address.
8. **Recognition.** A reference one character off is "taken to be" the sent one and says so; a reference jason did not send is a finding, not an arrival.
9. **Integration.** `connected` is never shown before a person's `--live` check succeeds; a credential reads only "set" or "not set" with its path; no response, log line, or URL carries a value; the vault panel says "not asked (not in dev)" outside `--dev`.
10. **Service.** A heartbeat older than 90 s reads `stale`; `jason daemon stop` writes only the drain request; no start, restart, or kill control exists.
11. **Schedules.** A row never adopted has no next run; a command with `--yes` is `refused` and never scheduled; a sign-in pause clears only by a good live check or `--resume`.
12. **Visibility.** `integration-connect` and `service-run` runs are absent from `work` for any viewer who is not an admin as themselves (401/403), absent in the owner view, and absent while an admin views as someone else.
13. **Check-in.** No route starts, advances, or lists a `check-in` run; no route runs git or edits the lessons file.
14. **Clocks.** Every clock on every run shows a basis; a `proposed policy` number carries no `Stamp`; Civil Code 5210(b) and 4530(a)(1) appear as their stored words, then any reading, labeled.
15. **Boundary.** The page and its screens name no association, street, vendor, person, case number, or id (the boundary test).

## 11. Decisions that are not this page's

1. **Run granularity.** Recommended: a mail run per period with a step per letter; an email run per thread, opened by a person from an Inbox row, never by jason.
2. **A fifth basis, `provider`,** for a vendor's published limit or a credential's life (Keeper's 30 days, Google token ends, quotas, floors), and a way to label a counterparty's stated date. Today the spine reads them as `documents` or `person`, which is wrong for both. Recommended: add `provider`.
3. **Shred or discard of a legal, insurance, tax, or escrow letter.** Whether the manager's choice alone suffices, or the board adopts a `records-retention` policy first. A question for the board and counsel; jason records the choice and the question.
4. **A general email response standard.** The law is silent; the board adopts one or none.
5. **The administrator group in Work.** Recommended: present only to an admin as themselves; the board's Work list never mentions these runs, not even by count.
6. **Whether the console ever starts `check-in`.** Recommended: never.
7. **Whether the free-text reply composer waits for the board's view of per-sentence provenance,** or ships as a thread reply through a second approvals kind.
