# Checking for new responses

Status: design (2026-10-05); step 1 built (2026-10-05), see "Step 1, as built" below for where it differs; step 2 built (2026-10-05), see "Step 2, as built"; the sent-copy catalog used in the inbox (arrivals-design build step 1b) built (2026-10-05), see "Step 1b, as built". It adds one place to ask "has anyone answered?", over every way an owner can answer a request, and a command and an MCP tool to ask it. It closes lesson `returns-by-the-same-rules`.

## Why

An owner can answer the owner-information request four ways, and jason read one:
- **PayHOA's form** (a signed-in submission): read by `jason owner-info --responses` and `--apply --payhoa`.
- **A Google Form** (`FORM_IMPORTS`): read from its saved responses.
- **A reply email** carrying the filled form, typed or scanned, to the association's mailbox or a group.
- **A mailed return**, scanned into PostScanMail.

The last two reached the association and nothing told jason. A person found a reply by searching Gmail for a sender's address, read the scan by eye, and keyed it by hand. The pieces to read a scan already exist (`form_reader.read_scan`, `form_refs`, `forms --read`); what is missing is finding the arrival, keeping it, and getting a person's confirmed reading into the same rules as a PayHOA submission.

## The idea

- **An arrival** is one thing that came in answer to a request: a PayHOA submission, a form response, an email with a scan, a mailed scan. It has a stable id, a channel, a time, a sender, and a state.
- **A check** is a live, read-only look at each channel for arrivals not yet kept. It is `jason responses --check`. It reads Gmail and PayHOA, writes nothing to either, and writes only jason's own inbox on disk.
- **A reading** is what jason makes of an arrival's attachments: is it the form, which copy, what the boxes and writing say. A reading is evidence for a person, never an answer ([form-reader.md](form-reader.md)).
- **A confirmation** is a person saying "this is what it says" (`--confirm`, with corrections). It makes keyed answers: the same `FormAnswers` a PayHOA submission becomes, with the source `email:<message id>`.
- **Recording** is what `jason owner-info --apply` already does, from every answer jason holds, now including keyed ones. jason never records on its own initiative and never edits an owner's submission.
- **The MCP tool** reads the inbox from disk. jason-mcp makes no live call (AGENTS.md), so it says what the last check kept and how old it is, and names the command that checks again.

## States

An arrival moves one way, each step a named act in `acts.jsonl` (who, when, why):

| State | Meaning | Set by |
|---|---|---|
| `new` | kept by a check; nobody has looked | the check |
| `seen` | a person looked and left it | `--seen` |
| `read` | its attachments were read; a reading is kept, unconfirmed | `--read` |
| `keyed` | a person confirmed the reading (with corrections); answers kept | `--confirm` |
| `recorded` | the writes it calls for were made in PayHOA | `owner-info --apply --yes` |
| `dismissed` | not an answer (a question, a duplicate, not the form) | `--dismiss --why` |

A PayHOA submission or a form response is already structured: it goes `new` to `keyed`-equivalent without a reading (its source is its confirmation), and `recorded` when its request is completed. A later answer for the same unit and owner supersedes an earlier one under the rules that already exist (`latest`); the earlier arrival stays, marked `superseded`.

## Channels

Each channel is a small class: `check(since) -> list[Arrival]`, taking its client as an argument, so a test passes a fake and importing jason reaches no service.

| Channel | Reads | Live | A candidate is |
|---|---|---|---|
| `payhoa` | the form's submissions list (`list_form_submissions`): id, status, created | yes | any submission not yet kept, test accounts excluded |
| `gmail` | messages since the request opened that reached the association's own addresses or groups | yes | from outside the association's domains and (carrying a PDF or image, or from an address PayHOA holds for a current owner). Headers and attachment names only; nothing downloaded. A group-rewritten sender is read from `X-Original-From` (`tasks.gmail._senders`) |
| `mail` | PostScanMail items already on disk | no | a scan whose text carries the request's form marker |
| `forms` | the saved responses of a Google Form | no | a response id not yet kept |
| `manual` | nothing: a person adds it (`jason responses --add-manual`) | no | a return keyed from paper handed in or taken by phone, with the method named (`--how`); any scan is copied to `files/<id>/`, so `--read` and `--confirm` take it like a scan (with no scan a person keys each answer at `--confirm --set`); never checked, and counted by `manual` in the campaign funnel ([followups-design.md](followups-design.md)) |

`--check --from ADDRESS` is the ad hoc case: it lists every message from that address in the window, candidate or not, and keeps only candidates. A check that fails on one channel (Keeper not signed in, a revoked Google token) reports it and still checks the others; a sign-in failure is the scheduler's sign-in pause, not a retry.

The window is the request's: from the day it opened (`AnswerCycle.opened`) to a week past the return-by date, then only a person's `--since`. A check keeps the time it last succeeded per channel and reads from a day before it, so a late-arriving message is not missed; an id already kept is not kept twice.

## What the profile supplies

Nothing about one association is in the code. A profile gives `Community.response_requests()` (default `()`): one `ResponseRequest` per request that expects answers, with:
- `key` and `title` ("owner-information-2027", "Owner information request");
- `form`: the `FormTemplate` (for the reader and the question keys);
- `cycle`: the `AnswerCycle` (opened, return-by);
- `payhoa_form`: the key `payhoa_forms.record_for` looks up, or empty;
- `imports`: the Google Form import rules, if any;
- `marker_campaigns`: the form-marker campaigns that belong to it (`form_refs`), so a scan is tied to the request by its printed reference.

The association's own addresses and domains come from `Community.email_domains()`. A request with no row is not watched.

## Where it lives

```text
data/responses/
  inbox.json         arrivals by id, and per channel when it last succeeded and how it ended
  acts.jsonl         every act: who, when, what, why (an append-only log)
  files/<id>/        an arrival's attachments, downloaded by --read (private, level P3)
  readings/<id>.json the reading of each (fields, confidence, how it was read)
  keyed/<id>.json    the confirmed answers, as FormAnswers
```

The folder is a private place in `jason.web.access.PATH_RULES` (P3): an owner's answers are not the open record. Writes take the store lock (`jason.locks`, `responses-<profile>`). `gather_answers` reads `keyed/` as one more channel, so `--responses`, `--apply`, and the approvals kind `owner-info-tags` see keyed answers with no other change.

## Records

```python
class Channel(Enum): PAYHOA = "payhoa"; GMAIL = "gmail"; MAIL = "mail"; FORMS = "forms"
class State(Enum): NEW = "new"; SEEN = "seen"; READ = "read"; KEYED = "keyed"; RECORDED = "recorded"; DISMISSED = "dismissed"

@dataclass(frozen=True)
class Arrival:
    id: str                 # "<channel>:<native id>", e.g. "gmail:1a10339bfc9fbdbe", "payhoa:263284"
    request: str            # ResponseRequest.key
    channel: Channel
    at: str                 # when it arrived (UTC ISO)
    who: str                # the sender or owner as the channel names them (a display name); never a stored personal address
    unit: str               # the unit it is for, when the channel says
    summary: str            # a subject line, or the form's title
    attachments: tuple[str, ...]
    state: State
    kept_at: str            # the check that kept it
    superseded_by: str = ""
    note: str = ""
```

A personal email address is not stored on an arrival (AGENTS.md: a personal address becomes who the records knew the sender to be). `who` is the display name; the sender's address is matched to an owner at read time and only the owner's unit and name are kept.

## The command

`jason responses` (module `jason.commands.responses`). With no option it prints the inbox from disk: what is new, and when each channel was last checked and how it ended.

| Option | Does | Live |
|---|---|---|
| `--check` | look at every channel; keep new arrivals; print them | yes (read-only) |
| `--channel C` (repeatable) | with `--check`: only these channels | |
| `--from ADDRESS` | with `--check`: every message from this address in the window | |
| `--since DATE` | with `--check`: read from this day | |
| `--list` | the inbox; `--state S`, `--request K`, `--unit U`, `--new` filter | no |
| `--show ID` | one arrival: its facts, attachments, reading, acts | no |
| `--read ID` | download its attachments to `files/<id>/`, find the form and its marker, read the boxes and writing (`--model` for handwriting) | Gmail download only |
| `--confirm ID --by NAME` | keep the reading as answers; `--set FIELD=VALUE` corrects a field | no |
| `--seen ID` / `--seen-all` | mark looked at | no |
| `--dismiss ID --by NAME --why TEXT` | not an answer | no |
| `--json` | print JSON | |

A check run by the scheduler uses `--check --by scheduler`; a person's act names the person. `--confirm` and `--dismiss` refuse without `--by`. `--read` and `--check` run only for a person at a console or the scheduler (the live-read guard, `commands.integrations.at_terminal`), never an agent's redirected stdin.

## The MCP tools

In the board profile (disk only; each carries its caveats):

- `new_responses(request="", channel="", unit="", state="new", days=0)`: arrivals in a state (new by default), newest first, with `checked` per channel (when it last succeeded, how it ended, how old) and the line "this reads what the last check kept; `jason responses --check` is the live read". Names, units, dates, channels, and attachment names; no email address, phone number, or mailing address.
- `response(id)`: one arrival, its reading (each field with its confidence and how it was read), its keyed answers with contact values masked (`jason.audit.mask`), its acts, and what is left (read, confirm, apply). A reading is labeled evidence, never an answer.

Both are in `jason.api`. Neither writes. Every act is the CLI's, by a named person.

## Cadence

The check is a registry source (`jason.integrations.registry`), so the scheduler runs it once a person adopts it, never faster than its floor, and a sign-in failure pauses it:
- `responses-gmail` under Google Workspace: `jason responses --check --channel gmail --channel mail --channel forms --by scheduler`, every 1h, 07-22 outside 4h, floor 15m, stale after 1d; proposed.
- `responses-payhoa` under PayHOA: `jason responses --check --channel payhoa --by scheduler`, every 2h, window 07-22, floor 1h, stale after 1d; proposed.

## What must not change

- A check writes nothing to Gmail, PayHOA, or Drive, and nothing leaves jason but a read.
- A reading is evidence; only a person's `--confirm` makes keyed answers, and only `owner-info --apply --yes` (a person's yes) writes PayHOA.
- No personal address is stored on an arrival; an attachment is kept only by a person's or the scheduler's `--read`, in a private place.
- jason never replies to an owner, files a return in Drive, or completes a request because of an email; those are a person's acts.
- The code names no association: requests, addresses, and form markers come from the profile.

## Build order

1. The records, the `Community.response_requests()` hook (default `()`) and the profile's row, the inbox store, the channels (five with the manual one), reading and confirming, `gather_answers` taking keyed answers, `apply` marking arrivals recorded. (Built.)
2. The command. (Built.)
3. The MCP tools and `jason.api`, the registry cadences, the procedure step, the lessons, and the docs. (Built; see "Step 3, as built".)
4. Later: a Responses panel in the console (the dock's count of new responses, the list, the reading beside the scan), once the administrator's and board's screens have components for it.

## Step 3, as built

- **Tools.** `new_responses` and `response` are `jason.mcp.response_inbox` (a module of their own with a `TOOLS` tuple, as `jason.mcp.citations`), in `PROFILES["board"]` (forty tools then; forty-one with `outstanding_responses`) and `jason.api`. They read `data/responses` through `list_arrivals`, `channel_status`, and `show`; they call no service and write nothing. A miss is `{found: False, reason, ...}` with `checked` and the verbatim line "this reads what the last check kept; `jason responses --check` is the live read"; an unreadable inbox is a miss, not an exception.
- **`checked`** lists every channel (five, with the manual one); one no check has reached is `never checked`. A sign-in failure ends as `sign-in`, a failure as `failed`, and `ageHours` is the age of the last success (None when there is none).
- **Masking.** `jason.approvals.audit.mask` (the design's `jason.audit.mask`): an email, phone number, or street address in an answer, a note, or an act becomes `[email]`, `[phone]`, `[address]`; a field named for contact details (email, phone, mailing address) with a value the pattern missed becomes `[masked]`. A unit's own address is the unit's and stays. `response(id)` accepts the file-name form (`gmail-abc`) for an id.
- **The reference** is compared with `tasks/form_references` (the copies jason sent): `reading.reference.copy` says whether a sent copy is on record under the printed reference and whether it was sent to the unit the sender's address belongs to (`matchesUnit`: true, false, or null when either unit is unknown). The reading now keeps the copy and the membership id, so the owner is compared by id too (see "Step 1b, as built").
- **What is left** (`left`) is read, confirm, apply for an email or a scan nobody has read; confirm, apply for a read form; apply for a keyed answer or a structured arrival (PayHOA, a Google Form); decide for a reading that found no form; nothing for a recorded, dismissed, or superseded one. Each is a person's step.
- **Cadences.** `responses-gmail` (Google Workspace) and `responses-payhoa` (PayHOA) are proposed in `jason.integrations.registry`, as the table above says. `jobs.job_class` puts `responses --check` on PayHOA's lane when `--channel payhoa` is the only channel and on Google's lane otherwise, `responses --read` on Google's, and the rest on the local lane. Status (`jason.web.extra.status`) has a row for each, read from the inbox's per-channel `lastOk`; a channel whose last try failed is listed among the failures.
- **The procedure.** `owner-info-cycle` has a step before the triage: check, list, read, confirm. Its record step says a confirmed answer is planned by `--apply` like a PayHOA answer. Lessons: `returns-by-the-same-rules` (fixed), `form-return-found-by-searching-the-mailbox` (fixed), `payhoa-submission-list-row-shape-unconfirmed` (open: a live look at a submission's list row is still owed), `new-module-name-already-taken` (fixed, with a step in `check-in`).

## Step 1, as built

The records are `jason.community.response_inbox` (`Channel`, `State`, `Arrival`, `ResponseRequest`, `Window`; `Community.response_requests()`, default `()`; the profile's row in `mystique/forms.py`). The store, channels, check, acts, and the apply's hook are `jason.tasks.response_inbox`. `gather_answers` reads `keyed/` as one more channel; `jason.web.access.PATH_RULES` places `responses/*` at P3. Tests: `tests/test_response_inbox.py`. What differs from the design above:

- **Module names.** `response_inbox`, not `responses`: `jason.community.responses` and `jason.tasks.responses` already hold the clocks for members' requests. The command module `jason.commands.responses` is free.
- **`ResponseRequest.blank`** is a new field: the request's fillable PDF, relative to the data folder, which a scan is read against (`read_layout`). The design had no place for it.
- **On disk the colon is a hyphen** (`files/gmail-1a10339bfc9fbdbe/`, `readings/gmail-….json`, `keyed/gmail-….json`): a colon is not allowed in a Windows file name. The id in every record keeps the colon.
- **A PayHOA submission already `complete`** is kept as `seen` (with a note), not `new`: nothing waits on it. A later check marks a kept one `seen` when PayHOA completes it.
- **A Gmail candidate** ignores a signature's logo or inline picture (an image named like `image001.png`, a GIF, or under 15 KB). A message must reach an association address or group (To or Cc on an own domain, or a group's List-Id), as the design says.
- **Windows.** A request whose window is closed (a week past its return-by date) is skipped with the reason unless a person gives `--since`; a check with `--since` or `--from` does not move the per-request time the last check succeeded, so the next plain check still reads from there.
- **`recorded`** is marked by an observer `owner_info_apply.plan_apply` attaches to the plan's writes (`ApplyPlan.observer`, a plain attribute on each `Write`, not a field). `execute_each` tells it the results, so the CLI's `--apply --yes` and the approvals kind both mark an arrival recorded when every write it calls for is made and nothing is left for the board or a person (the same test that completes a PayHOA request). It acts as `by`, else the operating-system user. With no writes at all `execute_each` is not called; the command then calls `plan.observer.heard([])`.
- **Keyed answers name the unit, not a sign-in.** `FormAnswers.unit_id` is the unit the sender's address matched at read time (else the form's own unit address is used), `membership_id` is left empty, and the owner is matched by name (and the email the form gives), so an emailed return is never taken for a signed-in one.

## Step 2, as built

The command is `jason.commands.responses` (registered in `jason.commands.MODULES`; tests: `tests/test_responses_command.py`; options: [cli.md](cli.md)). It is a thin layer over `jason.tasks.response_inbox`. What differs from "The command" above:

- **No option** prints what is new grouped by request, a count of the other states, each channel (when it last succeeded and how old that is, how the last try ended, or "never checked"), and the line naming `--check`. `--json` prints the same.
- **The clients are built lazily.** `Jason` is made, and entered, only when a channel asks for PayHOA's or Gmail's client, so a check of `mail` and `forms` alone signs in to nothing. Gmail is asked with `interactive=False`.
- **`--check` and `--read`** run for a person at a console (`commands.integrations.at_terminal`) or with `--by scheduler`; otherwise they are refused (exit 2) before anything is reached. A check without `--by` acts as the operating-system user. The exit is 1 when any channel failed or needs a sign-in (the others were still checked), else 0. `--from` never prints or stores the address; it lists each message found with `kept`, `already kept`, or `listed only, not kept: <why>`.
- **`--read`** prints the reading as a person checks it: how it was read, the sender matched to an owner and unit, the printed reference and whether its campaign names the request, the copy sent under that reference (`tasks.form_references`: ids and hashes) and whether it was sent to the unit and owner the sender's address matched, each field with how it was read and its confidence, the answers it would keep, and the reader's notes. `--model` runs `jason.local_ai.preflight` first; `LocalAIUnavailable` is a refusal with its reason.
- **Masking.** `--show`, `--read`, and `--confirm` print through `jason.approvals.audit.mask`: no email address, phone number, or street address. A unit's label is not a contact detail and is kept.
- **Refusals** (a `ResponseError`, a stray option, a malformed `--since` or `--set`) print `jason responses: <reason>` on stderr and exit 2. An option that does not go with the action (`--state` without `--list`) is refused, not ignored.
- **`owner-info --apply`** passes `--by` (else `--confirmed-by`) to `plan_apply` as the person who records, so the `recorded` act names them, and calls `plan.observer.heard([])` when the plan has no writes: an answer PayHOA already shows is marked recorded (with or without `--yes`; only jason's own inbox changes). It writes nothing different to PayHOA.

## Step 1b, as built

The inbox uses the sent-copy catalog ([arrivals-design.md](arrivals-design.md), build step 1b; the ladder and its corpus are `jason.tasks.recognize` and `tests/test_recognize.py`). What changed here:

- **The Gmail check** reads rung 1 on the subject it already holds (`GmailChannel.judge`): a reply whose subject carries a reference jason sent is kept as a candidate with no attachment and no download, and its `note` says which copy (the unit as sent). `GmailChannel` takes an optional `data_dir`, which `check` passes; without one it judges as before. A PDF or image from an owner who was sent a copy of the request and has not answered says so in its reason (rung 7, which only describes the candidate). `Message` and `Arrival` gain `note` (the recognition's words); the sender is not matched to a unit by a hint.
- **`read()`** calls `recognize` (`images=False`) with the subject and the downloaded files (a mailed scan's text is the mail service's `text.txt`), takes the page's marker from the form reader, compares the copy with the owner the sender matched and the unit the form names, and keeps `copy`, `recognition`, and the owner's `membershipId` on the reading. A reference no sent copy carries is noted as one we did not send (only when a catalog is on disk). A disagreement is a note in plain words ("the copy was sent to 102 Example Way, but the sender's address belongs to 101 Example Way").
- **`copy_of(data_dir, reading, community=...)`** is what the command and the tools read: the reading's recorded copy, else (an older reading, or one whose copy was not on record then) the catalog's copy under the printed reference.
- **`--outstanding`**, the `outstanding_responses` tool, and `jason.api.outstanding_responses` are `jason.tasks.response_outstanding` over the catalog and the answers kept (`response_inbox.answered_by`: an arrival that was not dismissed, its reading's or keyed answers' unit, owner, and copy). Disk only, names and units only; tool count: the board profile is forty-one.
- **Tests:** `tests/test_response_recognition.py`, `tests/test_response_outstanding.py`; two earlier tests changed where this step changed behavior (the reading's `owner` now has `membershipId`; a reading shows the copy it recorded, so the test that changes the catalog afterwards first drops the stored copy; a copy sent to another unit changes both its label and its id).
