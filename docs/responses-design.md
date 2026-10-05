# Checking for new responses

Status: design (2026-10-05). It adds one place to ask "has anyone answered?", over every way an owner can answer a request, and a command and an MCP tool to ask it. It closes lesson `returns-by-the-same-rules`.

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

1. The records, the `Community.response_requests()` hook (default `()`) and the profile's row, the inbox store, the four channels, reading and confirming, `gather_answers` taking keyed answers, `apply` marking arrivals recorded.
2. The command.
3. The MCP tools and `jason.api`, the registry cadences, the procedure step, the lessons, and the docs.
4. Later: a Responses panel in the console (the dock's count of new responses, the list, the reading beside the scan), once the administrator's and board's screens have components for it.
