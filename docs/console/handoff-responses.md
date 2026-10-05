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
| `ChannelMark` | `ArrivalRow`, `CheckedStrip` | Which channel: email, PayHOA, mailed scan, Google Form |
| `WhoMatch` | the open arrival | How the sender was tied to an owner and a unit, and when they were not |
| `ReferenceMatch` | the open arrival | The printed reference on the copy: found, valid, repaired, missing; the copy it names against the unit written |
| `ScanReview` | the open arrival | The page beside its reading, for a person to correct and confirm |
| `FieldReading` | `ScanReview` | One question: the reading, how it was read, how sure, and a correction |
| `ChangesPreview` | the open arrival | What confirming would lead to, read-only; nothing writes here |
| `DismissForm` | the open arrival | Not an answer, with the reason |
| `NewResponsesCount` | the dock, the digest, the nav | A count that says how old it is |

Reuse what is built: `Tabs`, `DataTable` for a dense wide list, `Doc`/`DocumentViewer` for the scan, `Seal` (`read`) for what jason read, `Pill`, `Command` and the admin handoff's `TerminalStep`, `Confirm` for any write, `Evidence` for the arrival's acts, `Caveats`, `Glyph`. No `Stamp`: confirming a reading is not a decision.

### `CheckedStrip`

One line, from the inbox's per-channel record (`checked`):

```json
{"gmail": {"at": "2099-10-05T16:30:12+00:00", "ok": true, "error": "", "new": 2, "age": "2 h"},
 "payhoa": {"at": "2099-10-05T16:30:40+00:00", "ok": true, "error": "", "new": 1, "age": "2 h"},
 "mail":  {"at": "2099-10-05T16:30:44+00:00", "ok": true, "error": "", "new": 0, "age": "2 h"},
 "forms": {"at": "", "ok": null, "error": "", "new": 0, "age": ""}}
```

| Channel state | Reads | Draw |
|---|---|---|
| ok | "Gmail ok, 2 h ago" | quiet |
| never checked | "Gmail never checked" | `circle-dashed`; with the command |
| failed | "Gmail failed 2 h ago: the Google token has expired" | the reason in the provider's plain words; not red until it is the only thing to do |
| needs sign-in | "PayHOA needs a sign-in: run `jason login`" | the key glyph (the connection chip's `needs sign-in`), and the step |
| stale | "Gmail last checked 3 days ago" | a plain note; the threshold is the integration's (`staleAfter`) |
| not watched | "Mailed scans: no scans on disk yet" | quiet |

- **Always shows age.** A count of "0 new" beside an old check is the thing most likely to mislead; the strip and every count say when it was last true.
- **The next step** is one `TerminalStep`: `jason responses --check` ("A person at the terminal, or the scheduler, checks; the console only reads what was kept").
- **No refresh button** until a console route exists; then a `Confirm`-less "Check now" is allowed because a check only reads, recorded by name.

### `ArrivalRow` and `ArrivalState`

```json
{"id": "gmail:1a10339bfc9fbdbe", "request": "owner-information-2027", "channel": "gmail",
 "at": "2099-10-03T19:24:26+00:00", "who": "A. Owner", "unit": "123 Main St",
 "summary": "Form attached", "attachments": ["Scan Oct 3, 2099 at 12.17 PM.pdf"],
 "state": "new", "keptAt": "2099-10-05T16:30:12+00:00", "supersededBy": "", "note": ""}
```

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
  | superseded | "Replaced by a later answer" with a link | dimmed | none |

- A PayHOA or Google Form arrival is already structured: it has no `read` step. It shows "Answered in PayHOA's form" and goes to `keyed`'s place by its source; the row says the form's own date and that jason did not read a scan.
- The row never shows an email address, phone number, or mailing address. `who` is a display name.

### `ChannelMark`

A glyph and a word. Four marks: email (a reply to the association's mailbox or a group), PayHOA (the form), mailed (a scan from the mail service), Google Form. One meaning per glyph: if the glyph set has no email mark, the design adds one; the existing `mailbox` means the mailboxes at the property.

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

A reason is required, chosen from the usual ones ("a question, not an answer", "a duplicate of …", "not the form", "from someone who is not an owner of the unit") or written. Recorded with who and when. Reversible by `--seen` on the same arrival (it returns to seen; the dismissal stays in the acts). Shown in the acts list.

### `NewResponsesCount`

On the dock, the digest, and the nav: **"3 new"** with **"checked 2 h ago"** beneath it, always together. If the last check failed or is stale, the count is shown in a muted face with the reason: "3 new · Gmail has not been checked since Oct 2". A count of zero beside an old check reads "Nothing new as of Oct 2" — never a bare zero.

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
