# Handoff: new responses, and reading a returned form

For a design pass on a new screen and the components behind it: the place a person goes to see **what has come in** in answer to a request, and to read and confirm a returned form. The behaviour is settled by [responses-design.md](../responses-design.md) (the inbox, the channels, the states, `jason responses`, the MCP tools). The console has no such screen yet; this page proposes it. The component names are proposals the build takes from the design's results. Read [handoff-reconciliation.md](handoff-reconciliation.md) and its third and fourth cuts first: their corrections still stand. The data shapes follow the design; the build confirms them and this page is corrected if it differs.

## The idea in six sentences

An owner can answer a request four ways (PayHOA's form, a Google Form, a reply email with the form typed or scanned, a mailed return), and a person should not have to search a mailbox to learn one came. The screen lists each arrival with where it came from, when, from whom, which unit, and where it stands. A returned scan is read by jason into a **reading**, which is evidence: each answer shown beside the page it came from, with how sure jason is, for a person to correct and confirm. Confirming makes the owner's answer; it writes nothing to PayHOA, which only a person's apply does, as for any answer. The screen is honest about its own age: it shows what the last check kept, when that was, and which channel failed. Nothing here replies to an owner, files a return, or completes a request.

## Who and where

- **Route:** `#/responses` (`?id=` one arrival; `?request=` and `?state=` filter), in the Overview group beside Inbox. The dock and the digest carry a count (below).
- **Sees readings and scans:** the manager, the Secretary, and an administrator. An owner's answers are private (level P3): a director sees the list's counts and states but not a scan or a reading, unless the board decides otherwise (a design decision below). An owner never sees this screen.
- **Acts:** the person who confirms or dismisses is named, and is the signed-in person when the console requires sign-in. Until console writes exist, each act shows its `Command` (`jason responses --confirm ID --by NAME`).
- **Never:** approve, deny, or assign a request; send an owner anything; mark a PayHOA request complete.

## The screen

```text
+--------------------------------------------------------------------------------------+
| New responses                                                  [Check again: command] |
| Owner information 2027 · answers by Oct 23 · 47 of 107 owners have answered            |
+--------------------------------------------------------------------------------------+
| Last checked  Gmail ok, 2 h ago · PayHOA ok, 2 h ago · Mailed scans ok · Forms ok     |
+--------------------------------------------------------------------------------------+
| [ New 3 ] [ Read 1 ] [ Confirmed 2 ] [ Recorded 41 ] [ Dismissed 1 ] [ All ]           |
+--------------------------------------------------------------------------------------+
| ✉ Email · 123 Main St · A. Owner · Oct 3, 12:24 PM                              New  > |
|   "Form attached" · 1 scan (3 pages)                                                    |
| ◫ PayHOA · 456 Oak Ln · B. Owner · Oct 3, 9:10 AM                               New  > |
|   Owner information form                                                                |
| ✉ Email · (unit not found) · C. Sender · Oct 2, 4:02 PM                         Seen > |
|   "Question about the form" · no attachment                                             |
+--------------------------------------------------------------------------------------+
```

- **Head:** the request's title, its dates in words, and the progress (answered of owners, from the ledger the Owner information screen already computes).
- **`CheckedStrip`** under it; **tabs** by state (`Tabs`, scrolling on a phone) with counts; the list of `ArrivalRow`s, newest first.
- **One arrival** opens in place on a wide screen (a right panel) and as its own page on a phone, not in a `BottomSheet`: a scan needs the room.
- **Phone:** the list is a single column of rows; the open arrival is its own page with the scan above the reading.

## The components

| Component | Where | Job |
|---|---|---|
| `CheckedStrip` | the screen's head, the dock, the digest | What the last check kept, per channel, how old, how it ended |
| `ArrivalRow` | the list | One arrival: channel, sender, unit, time, summary, attachments, state |
| `ArrivalState` | `ArrivalRow`, the open arrival | Where it stands, as a word and a glyph, and the one next step |
| `ChannelMark` | `ArrivalRow`, `CheckedStrip`, the campaign funnel | Which channel: PayHOA, email, mailed scan, Google Form, keyed from paper. The one definition (below); every other handoff points here |
| `WhoMatch` | the open arrival | How the sender was tied to an owner and a unit, and when they were not |
| `ReferenceMatch` | the open arrival | The printed reference on the copy: found, valid, repaired, missing; the copy it names against the unit written |
| `ScanReview` | the open arrival | The page beside its reading, for a person to correct and confirm |
| `FieldReading` | `ScanReview` | One question: the reading, how it was read, how sure, and a correction |
| `ChangesPreview` | the open arrival | What confirming would lead to, read-only; nothing writes here |
| `DismissForm` | the open arrival | Not an answer, with the reason |
| `NewResponsesCount` | the dock, the digest, the nav | A count that says how old it is |

Reuse what is built: `Tabs`, `DataTable` for a dense wide list, `Doc`/`DocumentViewer` for the scan, `Seal` (`read`) for what jason read, `Pill`, `Command` and `TerminalStep` (defined once, in [handoff-admin-components.md](handoff-admin-components.md#terminalstep): a `Command` that also says who runs it and why), `Confirm` for any write, `Evidence` for the arrival's acts, `Caveats`, `Glyph`. No `Stamp`: confirming a reading is not a decision. `AgeStamp` (the time a number was true) is defined once, in [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md#agestamp); `CheckedStrip` and `NewResponsesCount` are made of it.

### `CheckedStrip`

One line, from the inbox's per-channel record (`checked`, a list in the fixed channel order; corrected from the first draft's object keyed by channel; see "As built"):

```json
[{"channel": "payhoa", "lastOk": "2099-10-05T16:30:40+00:00", "lastTried": "2099-10-05T16:30:40+00:00", "ended": "ok", "reason": "", "ageHours": 2.0},
 {"channel": "gmail", "lastOk": "2099-10-02T09:00:12+00:00", "lastTried": "2099-10-05T16:30:12+00:00", "ended": "sign-in", "reason": "GoogleAuthRequired: the Google token has expired", "ageHours": 79.5},
 {"channel": "mail", "lastOk": "", "lastTried": "", "ended": "never checked", "reason": "", "ageHours": null},
 {"channel": "forms", "lastOk": "", "lastTried": "2099-10-05T16:30:12+00:00", "ended": "skipped", "reason": "no request is answered by this channel", "ageHours": null},
 {"channel": "manual", "lastOk": "", "lastTried": "", "ended": "keyed by a person (nothing to check)", "reason": "", "ageHours": null}]
```

| Channel state | Code says (`ended`) | Reads | Draw |
|---|---|---|---|
| ok | `ok` | "Gmail ok, 2 h ago" | quiet |
| never checked | `never checked` | "Gmail never checked" | `circle-dashed`; with the command |
| failed | `failed` (`reason` is the masked exception) | "Gmail failed 2 h ago: the Google token has expired" | the reason in plain words; not red until it is the only thing to do |
| needs sign-in | `sign-in` | "PayHOA needs a sign-in: run `jason login`" | the key glyph (the connection chip's `needs sign-in`), and the step |
| stale | not produced (proposed, not built) | "Gmail last checked 3 days ago" | a plain note; the threshold is the integration's (`staleAfter`) |
| not watched | `skipped` (`reason`: no request uses the channel, no client was given, or the window is closed a week past the return-by date) | "Mailed scans: no scans on disk yet" | quiet |
| keyed by a person | the literal `keyed by a person (nothing to check)` | "Keyed from paper: nothing to check" | quiet; never "never checked" |

- **Always shows age.** A count of "0 new" beside an old check is the thing most likely to mislead; the strip and every count say when it was last true.
- **The next step** is one `TerminalStep`: `jason responses --check` ("A person at the terminal, or the scheduler, checks; the console only reads what was kept").
- **No refresh button** until a console route exists; then a `Confirm`-less "Check now" is allowed because a check only reads, recorded by name.

### `ArrivalRow` and `ArrivalState`

```json
{"id": "gmail:1a10339bfc9fbdbe", "request": "owner-information-2027", "channel": "gmail",
 "at": "2099-10-03T19:24:26+00:00", "ageHours": 45.1, "who": "A. Owner", "unit": "123 Main St",
 "summary": "Form attached", "attachments": ["Scan Oct 3, 2099 at 12.17 PM.pdf"],
 "state": "new", "keptAt": "2099-10-05T16:30:12+00:00", "supersededBy": "", "note": ""}
```

(The MCP tool's shape, camelCase. The command's `--json` is the same record in snake_case, `kept_at` and `superseded_by`, with no `ageHours`.)

- **Row:** `ChannelMark`, who, the unit (or "unit not found" in a quiet face: it is a fact, not an error), the time, the summary in quotes (a subject is the sender's words), the attachment names with a paperclip, the state at the right.
- **States**, in order, with the next step each offers:

  | State | Reads | Glyph (proposed) | Next step |
  |---|---|---|---|
  | new | "New" | `circle-question-mark` | Look at it |
  | seen | "Seen" | a plain dot (not `eye-off`, which means hidden) | Read the scan, or dismiss |
  | read | "Read: needs your check" | `Seal` `read` | Correct and confirm |
  | keyed | "Confirmed by A. Admin" | `circle-check` | Apply (the Owner information screen or `jason owner-info --apply`) |
  | recorded | "Recorded in PayHOA" | `circle-check`, filled (not `badge-check`, which means approved) | none |
  | dismissed | "Dismissed: not an answer" with the reason | dimmed | none |
  | superseded | "Replaced by a later answer" with a link. **Not a state in the code:** a flag (`supersededBy` is another arrival's id) that any state can carry; draw it over the state, which still reads true | dimmed | none |

- A PayHOA or Google Form arrival is already structured: it has no `read` step. It shows "Answered in PayHOA's form" and goes to `keyed`'s place by its source; the row says the form's own date and that jason did not read a scan.
- The row never shows an email address, phone number, or mailing address. `who` is a display name.

### `ChannelMark`

A glyph and a word. **Five marks, in this fixed order** (the order of the code's `Channel`, so a person learns it): PayHOA (the form; `payhoa`), email (a reply to the association's mailbox or a group; `gmail`), mailed scan (from the mail service; `mail`), Google Form (`forms`), and keyed from paper (a form handed in at the office or an answer taken by phone, which a person types as an arrival with the method named; `manual`). This is the one definition of `ChannelMark`: [handoff-followups.md](handoff-followups.md) and [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) point here. One meaning per glyph: the glyph set already has `mail` (records, "Correspondence"), which is the email mark; the existing `mailbox` means the mailboxes at the property. A copy's own channel when it was **asked** is a smaller set (email, mail, PayHOA); the funnel draws it with the same marks where the words coincide.

### `WhoMatch`

How jason tied this arrival to someone. Facts, not a verdict.

| Case | Reads |
|---|---|
| matched by the email PayHOA holds | "Sent from the email PayHOA has for A. Owner, owner of 123 Main St" |
| matched by name | "The name matches A. Owner, owner of 123 Main St; no email on file to check it" |
| the form names another unit | "The scan names 456 Oak Ln; the sender is the owner of 123 Main St. A person decides." |
| a co-owner, an agent, a relative | "Shares a name with an owner of 123 Main St: a co-owner PayHOA lacks, a relative, or an agent. Ask." |
| no match | "No owner of record matches. The scan names 123 Main St." |
| answered before the latest deed | "The unit changed hands on …; this answer predates it" |

These are the words `member_preferences.match` already produces; the component shows them, never re-derives. The matching email is shown only as "the email PayHOA has", never as an address.

### `ReferenceMatch`

The printed marker on the copy (`Ref NP27E-4RK9T-C7`), which names the campaign and, when copies differ, the copy.

- **States:** read and checks (the campaign, and the copy's owner and unit as sent); read and repaired to the one sent marker a character away ("read as …, taken to be the sent …"); read but not any sent marker; not found (a photocopy, a retyped form, a page without it).
- **Beside it:** the unit the copy was sent to, and the unit the person wrote. Agreeing is a quiet tick; disagreeing is the one attention state ("the copy was sent to 456 Oak Ln; the answers are for 123 Main St").
- **A hint, never a verdict** ([form-reader.md](../form-reader.md)): the component says "the marker is a hint". A missing marker is not an error.

### `ScanReview`

The heart of the screen. The scan and its reading side by side, so the person checks the page, not the machine.

```text
+---------------------------------+  +--------------------------------------------------+
|  [page 1 of 3]   < >            |  | Read by jason · typed form, 3 pages              |
|                                 |  | Marker NP27E-4RK9T-C7 · matches the copy sent     |
|    (the scan, zoomable;         |  |                                                  |
|     the field being edited      |  | 1 Your name                                      |
|     highlighted on the page)    |  |   Young Cho        [typed · high]                |
|                                 |  | 4 How should the Association deliver notices?    |
|                                 |  |   [x] By email  [ ] By mail    [boxes · high]    |
|                                 |  | 6 Email address for notices                      |
|                                 |  |   a.owner@example.com   [handwriting · low]  ✎   |
|                                 |  | 13 Occupancy   (x) Owner-occupied   [boxes · high]|
|                                 |  | 19 Membership list   (blank, optional)           |
+---------------------------------+  +--------------------------------------------------+
|  Confirm as read   ·   Confirm with 1 correction   ·   Dismiss                          |
+----------------------------------------------------------------------------------------+
```

- **Layout:** on a wide screen, the page on the left (sticky, zoomable, paged), the questions on the right in the form's order and section titles. On a phone, the page above, the questions below, and tapping a question scrolls the page to its box.
- **The link between them** is the whole point: focusing a question highlights its box on the page; clicking a place on the page focuses its question.
- **Reading is evidence.** The head says "Read by jason" with the `read` seal, the method ("typed form", "scan read with OCR", "scan read with the local model"), and the time. The caveat is always on: "A reading is for you to check. Nothing is an answer until you confirm it."
- **Confirm:** "Confirm as read" when nothing was corrected; "Confirm with N corrections" when it was, listing the fields changed. The person's name is shown as the one who confirms (not editable; the signed-in name). Until console writes exist this composes the command (`jason responses --confirm ID --by "A. Admin" --set email=…`) in a `TerminalStep`.
- **No second person is required** to confirm a reading (it records nothing in PayHOA); the high-stakes answers keep the second-confirm rule where `owner-info`'s rules ask it, at apply.

### `FieldReading`

One question of the form.

- **Shows:** the question's number and printed title (small), the reading, **how it was read** (checked box, typed text, handwriting read by OCR, handwriting read by the model, the typed PDF's field), and **how sure** — a word ("high", "medium", "low") with a mark, never color alone.
- **Kinds** (match the form's `QuestionKind`): text; choice (radio, one of the options, or none); checkbox (any of the options); email; phone; address (street, then city, state, ZIP).
- **The states that matter** (draw each; they are different facts):

  | State | Reads | Why it differs |
  |---|---|---|
  | read | the answer, with how and how sure | the normal case |
  | blank, optional | "Left blank" (quiet) | an optional question the owner skipped; changes nothing |
  | blank, required | "Left blank — required" | the form needs a person to ask |
  | unreadable | "Could not read this" with the cropped image of the box | not the same as blank: the owner wrote something |
  | two readings disagree | "OCR read …; the model read …" side by side, pick one | the reading methods disagree |
  | no box marked | "No box marked" | a choice with none, as the reader reports it |
  | more than one marked | "Two boxes marked: By mail, By email" | a choice question the owner marked twice |
  | marked, differs from PayHOA | "Owner-occupied; PayHOA's unit tag says Rented out" | the response policy's board hold: shown as a fact, with "held for the board" |
  | corrected | the person's value, the reading struck through beside it, "corrected by A. Admin" | what a person changed |

- **Correction input** matches the kind (a radio group, checkboxes, a text field, an address in its parts) and starts **with the reading in it**, never empty; changing it marks the field "corrected". Escape or "Restore the reading" puts it back.
- **Low confidence is a prompt to look, not a block**: nothing is held from confirmation by a low score; the person decides. Fields at low confidence list first in a "Check these" band above the rest.
- **Never auto-confirmed:** no field is ever checked on the person's behalf, and the "Confirm" button is not the default focus.
- **A signature and date** are shown as read ("Signed", the date) with the cropped image: jason does not read a signature, it shows that a mark is there.

### `ChangesPreview`

What confirming leads to, read-only, from the answers through the rules that already exist (`member_preferences.match`, `owner_info.plan_writes`):

```text
If these answers are applied, the owner-information rules would:
  + Notices by Email        (A. Owner, member tag)
  − Notices by Mail         (A. Owner, member tag)
  + Owner Occupied          (123 Main St, unit tag)
  + Owner Info 2027         (A. Owner, member tag; the tag does not exist yet)
A person enters: the mailing address, if PayHOA's differs from the unit's.
Nothing is written until a person runs jason owner-info --apply --yes.
```

- Needs a live read of PayHOA, so the screen shows **the last plan on disk** with its age, or the command that makes one; it never reads PayHOA on its own.
- Shown as a `ConfirmList` with every tick disabled, to make plain that this page records nothing.
- "A person enters" lists what jason does not write (`owner_info.FOR_A_PERSON`).
- States: confirmed and planned; confirmed, no plan yet ("run `jason owner-info --apply` to see the writes"); confirmed, plan older than the confirmation; nothing to change ("PayHOA already matches these answers").

### `DismissForm`

A reason is required, chosen from the usual ones ("a question, not an answer", "a duplicate of …", "not the form", "from someone who is not an owner of the unit") or written. Recorded with who and when. **Not reversible today** (corrected: `--seen` moves only a new arrival, so a dismissed one stays dismissed; a keyed arrival's answers are set aside, not deleted; a recorded arrival cannot be dismissed). A restore that returns it to seen, leaving the dismissal in the acts, is proposed, not built. Shown in the acts list.

### `NewResponsesCount`

On the dock, the digest, and the nav: **"3 new"** with **"checked 2 h ago"** beneath it, always together. If the last check failed or is stale, the count is shown in a muted face with the reason: "3 new · Gmail has not been checked since Oct 2". A count of zero beside an old check reads "Nothing new as of Oct 2" — never a bare zero.

## As built (checked against the code, 2026-10-05)

The inbox, the check, the reading, the confirmation, and the manual arrival are built ([responses-design.md](../responses-design.md), `jason.tasks.response_inbox`); the console screen and its loaders are not. **The nearest thing to the console's data** is the three board MCP tools in `jason.mcp.response_inbox` (`new_responses`, `response`, `outstanding_responses`; also `jason.api`). They read disk only, mask every address and phone number, and are camelCase. `jason responses --list|--show ID --json` is the same data in snake_case. The folder is level P3 (`responses/*`), so a loader returns rows only to the permitted roles and a director gets `inbox` counts and `checked`. A loader follows the `src/jason/web/extra/<name>.py` pattern (`args -> dict`, with `found`, a note, and the caveats; see `records_requests.py`). None exists for responses.

### Shapes, with made-up values

`new_responses(state="new")` (a state word, or `all`; filters `request`, `channel`, `unit`, `days`); a miss is `{"found": false, "reason": "...", "checked": [...], "note": "..."}`, never an exception:

```json
{"found": true, "state": "new", "count": 1,
 "arrivals": [{"id": "gmail:1a10339bfc9fbdbe", "request": "owner-information-2027", "channel": "gmail",
               "at": "2099-10-03T19:24:26+00:00", "ageHours": 45.1, "who": "A. Owner", "unit": "123 Main St",
               "summary": "Form attached", "attachments": ["Scan Oct 3, 2099 at 12.17 PM.pdf"], "state": "new",
               "supersededBy": "", "note": "", "keptAt": "2099-10-05T16:30:12+00:00"}],
 "inbox": {"new": 1, "seen": 1, "read": 1, "keyed": 2, "recorded": 41, "dismissed": 1},
 "checked": [{"channel": "gmail", "lastOk": "2099-10-05T16:30:12+00:00", "lastTried": "2099-10-05T16:30:12+00:00", "ended": "ok", "reason": "", "ageHours": 2.0}],
 "note": "this reads what the last check kept; `jason responses --check` is the live read", "caveats": ["..."]}
```

`inbox` counts every kept arrival by state (the tab counts); `checked` has one row per channel, five in all.

`response(id)` (the file-name form `gmail-1a10...` is accepted):

```json
{"found": true,
 "arrival": {"id": "gmail:1a10339bfc9fbdbe", "state": "read"},
 "files": ["Scan Oct 3, 2099 at 12.17 PM.pdf"],
 "reading": {"label": "evidence for a person, never an answer: nothing here is an owner's answer until a person confirms it",
   "readAt": "2099-10-05T17:02:00+00:00", "by": "A. Admin", "model": "", "how": "scan", "isTheForm": true,
   "files": [{"name": "Scan Oct 3, 2099 at 12.17 PM.pdf", "how": "scan", "linesMatched": 31}],
   "reference": {"text": "NP27E-4RK9T-C7", "how": "text and bars", "campaign": "NP27E", "campaignMatchesRequest": true,
     "copy": {"found": true, "reference": "NP27E-4RK9T-C7", "channel": "email", "year": 2027, "firstSent": "2099-10-01T15:00:00+00:00",
              "sentToUnit": "123 Main St", "readUnit": "123 Main St", "sentToOwner": "A. Owner",
              "matchesUnit": true, "matchesOwner": true, "matchesWrittenUnit": true,
              "foundBy": "mark", "sure": "high", "putRight": false, "says": "a hint checked against what was sent, not a reading"}},
   "owner": {"unit": "123 Main St", "name": "A. Owner", "matchedBy": "the sender's address"},
   "fields": {"name": {"value": "A. Owner", "how": "ocr", "confidence": 0.91},
              "email": {"value": "[email]", "how": "model", "confidence": 0.55},
              "delivery.email": {"value": true, "how": "mark", "confidence": 0.93}},
   "answers": {"name": "A. Owner", "email": "[email]", "delivery": ["By email"]},
   "signed": "2099-10-03", "signature": "Signed", "residual": 0.8,
   "notes": []},
 "keyed": null,
 "acts": [{"at": "2099-10-05T16:30:12+00:00", "by": "A. Admin", "act": "kept", "id": "gmail:1a10339bfc9fbdbe", "why": "found by a check of gmail"}],
 "left": [{"step": "confirm", "command": "jason responses --confirm ID --by NAME [--set FIELD=VALUE]", "says": "..."},
          {"step": "apply", "command": "jason owner-info --apply --payhoa", "says": "..."}],
 "superseded": "", "checked": ["..."], "note": "...", "caveats": ["..."]}
```

`keyed` once confirmed: `{"label", "by", "at", "source": "email:1a10...", "corrected": ["email"], "problems": ["..."], "answers": {...}, "submitted", "signed", "signature", "contacts": [{"role": "owner", "name": "A. Owner", "email": "[email]"}], "reference"}`. An act's `act` is one of `kept`, `seen`, `read`, `confirm`, `dismiss`, `recorded`, `manual`, `superseded`, `restored`; `why` is a reason, and a field's name is logged but never its value. `copy` when no sent copy is on record: `{"found": false, "reason": "no printed reference was read"}` or `{"found": false, "unsent": true, "reason": "a reference we did not send: ..."}`. `outstanding_responses` is the sent-copy catalog less the answers (below and in [handoff-followups.md](handoff-followups.md#as-built-checked-against-the-code-2026-10-05)).

### States the code can be in that this page does not draw

| State | The field and value that says so |
|---|---|
| An arrival keyed by a person, channel `manual` | `channel: "manual"`; `summary` is the method ("handed in at the office"); `who` as given; `attachments` may be empty. With no scan the reading is `how: "keyed by a person"`, `isTheForm: true`, `fields: {}`, and `notes` says "a person keys each answer (`--confirm --set FIELD=VALUE`)". The correction input **cannot start with the reading in it**: it starts empty, and every answer is keyed |
| A reading that found no form | `reading.isTheForm: false`, `how: "not the form"`; `left` is one step, `decide` ("dismiss it, or read it again"; `--model` reads handwriting); `notes` says why (lines matched on N only; no blank form on disk; could not be opened; no pages; the message carries no PDF or image). The state is still `read` |
| A structured arrival (PayHOA, Google Form) | `channel` is `payhoa` or `forms`; it is never `read` or `keyed`; `left` is the one step `apply`; it goes `new` or `seen` to `recorded`. Counts treat it as read and confirmed |
| Already complete in PayHOA | `state: "seen"`, `note: "PayHOA status: complete"`: nothing waits on it |
| An email that names a copy with nothing attached | `attachments: []`, `note` names the copy by its unit as sent (rung 1 of the recognition ladder, on the subject); `--read` then says "the message carries no PDF or image to read" |
| Superseded by a later answer | `supersededBy` set, on any state; `left` is empty; `response.superseded` is a sentence |
| A confirmed answer with findings | `keyed.problems`: what `forms.check` finds in the answers; informational, a person decides |
| Confirmed but not recorded for want of a person or the board | the arrival stays `keyed`; the blockers (held for the board, a person enters the mailing address or representative) are computed in the apply's plan and are **not** on the arrival |
| Dismissed after it was keyed | `state: "dismissed"`; the keyed answers moved to `keyed/withdrawn/`; they no longer count as an answer |
| A channel skipped or never reached | `checked[].ended` is `skipped` (with its reason) or `never checked` |
| Unit not found | `unit: ""` (an email's unit is filled only once the sender's address matches an owner at `--read`) |
| The reference disagrees | `copy.matchesUnit`, `matchesOwner`, `matchesWrittenUnit` each `true`, `false`, or `null` (cannot tell, never "no"): three separate comparisons, and `notes` carries each disagreement in words. A repaired marker is `putRight: true` with `sure: "medium"` |

### Drawn on this page, not yet producible (proposed, not built)

- **`CheckedStrip`:** a per-channel count of new arrivals (the store keeps `looked` and `kept` but neither the tools nor `checked` return them); a `stale` word (no `staleAfter` reaches this path; the Status screen has rows for the two scheduled checks, `responses-gmail` and `responses-payhoa`, with a one-day threshold).
- **`WhoMatch`:** only the sender's-address match is produced (`owner.matchedBy: "the sender's address"`) with the copy comparison above. "Matched by name", "a co-owner, an agent, a relative", and "answered before the latest deed" are `member_preferences.match` results at apply time, not on an arrival.
- **`ScanReview`'s link between the page and a question:** a reading carries no page number or box for a field, so highlight-on-focus and click-on-page are not buildable from the reading as it is. The scan's pages are files under `data/responses/files/<id>/` with no route that serves them.
- **`FieldReading`:** `confidence` is a number from 0 to 1 (`0.95` for a typed PDF's field) and `how` is `typed`, `mark`, `ocr`, or `model`; the words high, medium, and low are a mapping the design chooses, with no threshold in the code. There is no per-field "left blank", "could not read", "no box marked", "two boxes marked", or "two readings disagree": a blank is absent from `answers`, and one field has one reading. The "required" side comes from the form's own question list ([handoff-form-library.md](handoff-form-library.md)). A corrected field is `keyed.corrected` (names only); the struck-through reading is the reading's own `answers` beside `keyed.answers`.
- **`ChangesPreview`:** not built for one arrival. The plan is `jason owner-info --apply --payhoa` (a dry run) over every answer; an arrival links to its plan row through its answer's source (`email:ID` is `gmail:ID`). The screen's `/api/owner-info` already carries the last plan on disk.
- **`DismissForm`'s presets and the restore:** the reason is free text (`--why`, required); no list of usual reasons exists.
- **`NewResponsesCount` on the dock and the digest:** no loader counts them; the figures are `inbox.new` and `checked`.
- **The head's "47 of 107":** not a field. `outstanding_responses` gives `sent` (copies), `answered`, `notResponded`, and `neverAsked`; the campaign funnel ([handoff-followups.md](handoff-followups.md)) is the nearer source.

### Where the first draft's shape or word differed (the code wins; the text above is corrected)

- `checked` was an object keyed by channel with `at`, `ok`, `error`, `new`, `age`; it is a list of `{channel, lastOk, lastTried, ended, reason, ageHours}` with `ended` one of `ok`, `sign-in`, `failed`, `skipped`, `never checked`.
- Four channels; there are five (`manual`).
- `superseded` was a state; it is a flag (`supersededBy`).
- Dismissal was reversible by `--seen`; it is not.
- The reading's method words: "typed form", "scan read with OCR", and "with the local model" are `reading.how` (`typed`, `scan`, `not the form`, `keyed by a person`) with `reading.model` non-empty when the model ran and each field's own `how`.
- `ChannelMark` had no email glyph; `mail` exists.
- The recognition rungs are named `subject`, `text-layer`, `field`, `mark`, `layout`, `citation`, `sender` (the spec said "text" and "bar mark").
- The arrival's fields are `keptAt` and `supersededBy` in the tools and `kept_at` and `superseded_by` in the command.

## Words

| Say | Not |
|---|---|
| Arrived, came in | Received (it may not be received by the association's records yet) |
| Read by jason | Processed, parsed, scanned in |
| Confirm | Approve, accept (it is not a decision) |
| Corrected | Edited, fixed |
| Left blank | Missing, empty, null |
| Could not read this | Error, invalid |
| Recorded in PayHOA | Synced, saved |
| Dismissed: not an answer | Deleted, rejected |
| Checked 2 h ago | Updated, refreshed |

Never "the owner said …" for a reading: "the form says …" until it is confirmed.

## What must not change

- A reading is evidence; only a person's confirmation makes it the owner's answer, and only a person's apply writes PayHOA.
- The screen never shows an email address, phone number, or mailing address; those are in the scan for the person who may see it, and nowhere else.
- No count appears without its age; no zero without the time it was true.
- jason never replies to an owner, files a return in Drive, or completes a PayHOA request from this screen.
- A scan and a reading are private (P3): outside the permitted roles and the private view they are held back as the executive-session items are ([handoff-held-setup-roster.md](handoff-held-setup-roster.md) `HeldRow`), saying only that a response is held.
- Confidence is a word and a mark, never color alone.

## Decisions that are the design's

1. Whether the open arrival is a right panel or its own page on a wide screen.
2. Whether the page and the reading are tied by highlight alone, or also by a numbered pin on the page.
3. How a low-confidence field is surfaced: a band of "Check these" above the form, or a mark in the form's order.
4. The glyph for email, and whether the four channel marks share a frame.
5. Whether directors see the list's counts and states without the scan (the proposal), or nothing.
6. Whether `NewResponsesCount` lives on the dock, the digest, or both.

## Open (the build's or a person's)

- The console routes: `GET /api/responses` (the inbox and `checked`), `GET /api/responses/<id>` (one arrival, its reading, its acts), and the three acts as writes behind the sign-in guard, recorded by name. Proposed names.
- Whether the scheduler's checks should be adopted for this cycle ([scheduler-daemon-design.md](../scheduler-daemon-design.md)).
- A person's confirmation of a reading by a second person for the high-stakes answers (a delivery election), as `SecondConfirm`, if the board wants it before apply rather than at apply.
- Reading a scan needs the form's layout and, for handwriting, the local model; a phone photo that cannot be aligned reads nothing ([form-reader.md](../form-reader.md)). The screen shows "Could not align this scan" with the page and a person keys it by hand.
