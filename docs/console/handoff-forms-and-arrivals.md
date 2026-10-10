# Handoff: forms, arrivals, and the cycle board

For a design pass on the screens and components behind [arrivals-design.md](../arrivals-design.md), [responses-design.md](../responses-design.md), and [standard-forms.md](../standard-forms.md). It adds to [handoff-responses.md](handoff-responses.md) (one returned form, its reading, and the count), which still stands, and to [handoff-admin-components.md](handoff-admin-components.md) (the administrator's screens). Read [handoff-reconciliation.md](handoff-reconciliation.md) and its third and fourth cuts first. The component names are proposals; the data shapes follow the designs and the build corrects this page where it differs.

## The idea in six sentences

Everything that arrives (an email, a scan, a PayHOA request, a form response) is cataloged once, identified if it is a form jason sent, and sent to the process that fits. A form jason sent is recognized by the reference it carries, and the reference names the copy: which form, which owner and unit, which cycle, and which handler. What no handler takes is shown honestly as a gap for the administrator to develop, with a person handling the item in the meantime. The law's clocks around a form (answers asked by, entered by, a resend after a bounce) are shown on one board per cycle, owner by owner. Every number carries the time it was true, and no screen replies to an owner, files a return, or completes a request. The design stays calm: these are working lists for a few careful people, not an alert wall.

## The screens

| Screen | Route | Who | What it is |
|---|---|---|---|
| **Arrivals** | `#/arrivals` (the Inbox becomes its lanes) | manager, Secretary, administrator | Everything that came in, by lane: act now, forms, requests, invoices, notices, questions, needs a person |
| **Responses** | `#/responses` | as in [handoff-responses.md](handoff-responses.md) | The forms lane in detail: one arrival's scan beside its reading |
| **Cycle board** | `#/cycle` (a tab of Owner information, `#/owner-info`) | manager, Secretary, board (counts only for directors) | One row per owner: asked, delivered, responded, reviewed, reachable, and what the law asks next |
| **Forms** | `#/forms` | administrator; board read-only | Each known form: its authority, procedure, handler, campaigns, copies sent and returned |
| **Needs development** | a band on Status (`#/status`) and a page `#/instance/gaps` | administrator only | Kinds of arrival and forms with no handler; what the manager did by hand |
| **Form candidates** | `#/forms/candidates` | administrator; board read-only | What the discovery pass found in the law and the documents, for a person to confirm, hold, or drop |

## Arrivals

```text
+--------------------------------------------------------------------------------------+
| Arrivals                                                          checked 2 h ago ·   |
| [ Act now 2 ] [ Forms 3 ] [ Requests 4 ] [ Invoices 6 ] [ Notices 1 ] [ Questions 5 ]  |
| [ Needs a person 2 ]                                                                    |
+--------------------------------------------------------------------------------------+
| ⚑ Government notice · Fire department · Oct 4 · respond by Oct 18 (the sender's date)  |
|   "Annual inspection scheduled" · 1 attachment                          [ Act now ]    |
| ▤ Form · Owner information · 123 Main St · A. Owner · Oct 3         [ Recognized ]    |
|   copy sent to 123 Main St on Oct 1 · scan, 3 pages                      [ New ]       |
| ? Unknown form · outside sender · Oct 2                               [ Needs a person]|
|   "Application attached" · the page cites no form we sent                               |
+--------------------------------------------------------------------------------------+
```

- **Lanes, not a feed.** Each lane is a tab with a count and the age of its source. A row sits in one lane, the one its route chose; it can be moved by a person's correction.
- **The row** (`ArrivalRow`, widened): the party class and kind as words with a glyph, the sender's display name, the unit when known, the time, the summary in quotes (the sender's words), the attachment names, a clock when one runs ("respond by Oct 18, the sender's date"), and a `RecognitionChip` for a form.
- **A correction** ("this is from a vendor, not an owner") is one act with a reason; it is recorded and may become a proposed rule row. It never silently teaches anything.
- **Needs a person** is the lane for what no handler took and for a candidate form: it is never hidden, never auto-cleared, and shows how long each item has waited.

### `RecognitionChip`

How jason knew a form: one word and the rung, with the result's confidence as a word.

| Result | Reads | Draw |
|---|---|---|
| Recognized | "Recognized: copy NP27E-4RK9T, sent to 123 Main St on Oct 1" | quiet; the copy's owner and unit as sent beside the unit written on the page |
| Recognized, repaired | "A reference one character off was read as the sent copy …" | the one note that a repair happened; never silent |
| A reference we did not send | "This reference matches no copy jason sent" | the single attention state for recognition; not an error, a finding for a person |
| Candidate | "Looks like the owner information form (title and the cited law); no reference survived" | a person attaches it to a campaign |
| Not ours | "Not one of our forms" | leaves this lane |
| Disagrees | "The copy was sent to 456 Oak Ln; the page says 123 Main St" | the other attention state; both units shown |

The rung (the code's names: `subject`, `text-layer`, `field`, `mark`, `layout`, `citation`, `sender`, numbered 1 to 7) is a small detail line, not a headline: the person needs to trust the result, not learn the ladder.

## The cycle board

The answer to "who has responded, who has not, whose response awaits review, and what does the law ask next?" One row per current owner and unit, extending the Owner information screen. It is built from the sent-copy catalog (the asked side), the notice ledger (deliveries and bounces), the response inbox (arrivals), and the PayHOA tags.

```text
+------------------------------------------------------------------------------------------------+
| Owner information 2027 · answers asked by Oct 23 · entered in PayHOA by Nov 1 · reports mailed by Dec 1 |
| Read: sent copies Oct 5 · notices synced Oct 5 · responses checked Oct 5, 4:30 PM                        |
| [ Haven't answered 41 ] [ Waiting for review 3 ] [ Ready to record 6 ] [ Can't reach 4 ] [ Second addresses 2 ] [ Done 51 ] |
+------------------------------------------------------------------------------------------------+
| 123 Main St · A. Owner   Asked: email Oct 1 ✓ delivered | Responded: scan Oct 3, read | Next: confirm   |
| 456 Oak Ln · B. Owner    Asked: email Oct 1 ✗ bounced   | Responded: none            | Next: resend by mail (CIV 4041(e)) |
+------------------------------------------------------------------------------------------------+
```

- **Columns, as facts:** Asked (channel, date, outcome, in the notice ledger's ten words: pending, mailed, delivered, opened, bounced, not shown delivered (`unknown`), skipped (no email on file), failed, returned, forwarded (`rerouted`); corrected from the first draft's "never mailed", which is `failed` or `skipped`), Responded (none, arrived by channel and date, read, confirmed, recorded, replaced by a later answer), Delivers by now (mail, email, both, or "no election: first-class mail"), Reachable (reached, or nothing has reached them), Second address (given or not, with its own outcome), Representative and occupancy (given, blank, or differs from the unit tag), and **Open obligation** (what the law or policy asks next, with its citation and the command).
- **Lenses** are the working lists; a row can be in more than one. Counts carry the age of their source, and a lens with an old source says so in its tab, not only on hover.
- **Open obligation** reads from the follow-up rules: "Resend the notice by first-class mail and ask for a working email — CIV 4041(e), 4040(a)(2) — required" or "… — policy". The citation is the recited authority (a link to the words), never a paraphrase; required and policy are marked differently so a board can see which is the law's and which is its own.
- **Deadlines** are the strip above: asked-by, entered-by, reports-mailed-by, each with days left and, once passed, days over. A row past a date shows it.
- **Directors** see the counts and the states, not a scan, an answer, or an address. Owners never see it.
- **Never:** a send, a resend, or a completion from this screen. A row offers the command; resending is a person's `--yes`.

## Forms

A register of the forms jason sends, drawn like the other registers (`RegisterGrid`). **It is the same table as the form library** ([handoff-form-library.md](handoff-form-library.md#3-the-form-library-the-administrators)): one `FormRegister` of `LibraryRow`s, defined there. This section lists only what the Forms screen adds to a row: its campaigns and the references seen that no copy jason sent carries.

| Column | |
|---|---|
| Form | its title and key |
| Authority | the citation, a link to the words (`CIV 4041`), or "none (offered)" |
| Procedure | the SOP key, a link to `jason sop` |
| Handler | its name; for a general form, the options chosen (the sheet, the tag map) and by whom |
| Campaigns | each cycle's campaign code, dates, copies sent, returned, recorded |
| Status | ready; handler missing (the form could not be made); unknown references seen |

- **A form with no handler cannot be made:** the generator refuses and this row says why, with "bring to the administrator" and a link to the gap.
- **Reference catalog:** a campaign opens to its sent copies: the reference, the unit, the channel, when it was sent, and whether it has an arrival. No addresses.
- Read-only for the board; the administrator's changes are commands until console writes exist.

## Needs development

The page the administrator reads to decide what to build next. It shows no content of any arrival.

```text
+--------------------------------------------------------------------------------------+
| Needs development                                              as of Oct 5, 4:30 PM   |
| 3 kinds of arrival have no handler. The manager handled each by hand meanwhile.        |
+--------------------------------------------------------------------------------------+
| CIV 5915 / request     9 arrivals · first Aug 3 · last Oct 2 · email, PayHOA   Open     |
|   handled by hand: "Replied with the director's name and a meeting time" (A. Manager)  |
| Government notice / authority   4 arrivals · first Sep 12 · last Oct 4        Acknowledged |
| …                                                                                      |
+--------------------------------------------------------------------------------------+
```

- **A gap** has its key (a citation and role, or a kind and sender class), a count, first and last dates, the channels, and arrival ids only. **What a person did by hand** is shown in their own words and by name: it is the first draft of the procedure.
- **States:** open, acknowledged by the administrator, in development, built. A gap closes itself when a handler registers for its key; the page says "built; 9 waiting arrivals routed" rather than just disappearing.
- **Coverage, the other way:** a second tab lists the citations the association's procedures, notice catalog, and document duties name that no handler serves, ranked by how often arrivals of that kind have come in. It is a map of what jason does not yet do.
- **The administrator's dock** shows the count of open gaps and nothing else about them.

## Form candidates

The review screen for the discovery pass ([standard-forms.md](../standard-forms.md)). A calm two-column reading screen like `ScanReview`, but for law and documents.

- **Left:** the quote, verbatim, with its citation and where it is written (a statute section, or a document and section); the seeds that took it ("written request", "within N days of").
- **Right:** the model's reading as a form to check: who submits, to whom, what, required content, each clock (for the member, for the body, what happens if it passes), who decides, in writing, with reasons and reconsideration. Each line is labeled "a reading for a person"; a field whose quote was not found in the span is missing and says why.
- **Known as:** whether it matches a request kind jason already reads ("architectural application"), a notice requirement, or nothing ("new").
- **Group:** the statute and the document sections that carry it out, side by side, with the reason they were joined. A document that asks more than the statute's minimum is shown as a document that asks more (followed as written); one that asks less than the statute requires is shown as a possible conflict for the board and counsel, never decided here.
- **Acts:** confirm (becomes a known-form candidate; creates nothing), hold (for the board, when the law is silent on a clock the form needs: a proposed policy), drop (with a reason). Each by name.
- **Honesty:** the model ran or it did not, and the screen says which; "seeds only" means no reading yet.

## Components

| Component | On | Job |
|---|---|---|
| `ArrivalRow` (widened), `LaneTabs` | Arrivals | A row in a lane; lanes with counts and ages |
| `RecognitionChip` | Arrivals, Responses | How a form was recognized, with its rung and any disagreement |
| `CycleRow`, `CycleLens`, `DeadlineStrip` | Cycle board | An owner's facts; the working lists; the cycle's dates with days left |
| `ObligationNote` | Cycle board | What the law or policy asks next, required or policy, with its recited authority and command |
| `FormRegister` (defined in [handoff-form-library.md](handoff-form-library.md)), `CampaignCopies` (defined in [handoff-followups.md](handoff-followups.md)) | Forms | The known forms (one register for the library and this screen) and each campaign's sent copies |
| `GapRow`, `HandledByHand`, `CoverageMap` | Needs development | A gap, what a person did, and the citations with no handler |
| `CandidateReview`, `ClockList`, `SourceJoin` | Form candidates | The quote beside the reading, the clocks, and the joined sources |
| `AgeStamp` | everywhere | "as of Oct 5, 4:30 PM" or "last checked 2 h ago": the time a number was true (defined below, once) |

### `AgeStamp`

The one definition; the other handoffs point here. It draws the time a number or a list was true, from the source's own stamp, never the page's load time: "as of Oct 5, 4:30 PM" for a read of disk, "last checked 2 h ago" for a live check, "synced Oct 2" for a ledger. It takes a source's name when a page has several ("the notice ledger, synced Oct 2"), and a missing source is a dash with its reason, never a bare zero. The tools return the age as hours (`ageHours`, a number, or `null`) beside the stamp; the component words it. It is not the built `Freshness` of `CitedSections` (a citations report's made-on and law-checked line), and not components.md's proposed `Freshness`: those are the same idea at section scale, and the design may fold them into this.

Reuse what is built: `Tabs`, `RegisterGrid`, `DataTable`, `Seal` (`read`), `Pill`, `Command`/`TerminalStep` ([defined once](handoff-admin-components.md#terminalstep)), `Confirm`, `Evidence`, `Recitation`, `Glyph`, `Caveats`, `HeldRow`, `NewResponsesCount` ([handoff-responses.md](handoff-responses.md)), `ChannelMark` ([handoff-responses.md](handoff-responses.md#channelmark)), and `ScrollRow` for a lane row on a phone. `LaneTabs` is `Tabs` with a count and an `AgeStamp` per tab. No `Stamp`: nothing here is a decision.

## As built (checked against the code, 2026-10-05)

Three of the six screens have their data; three do not.

| Screen | Built (the command, the tool) | Not built |
|---|---|---|
| Arrivals | `Recognition` is a function (`jason.tasks.recognize.recognize`, the seven rungs), its result kept on a reading (`jason responses --show ID --json`: `reading.recognition` and `copy`) and, for a reply whose subject carries a sent reference, as the arrival's `note`. The inbox is the forms lane ([handoff-responses.md](handoff-responses.md#as-built-checked-against-the-code-2026-10-05)) | The catalog of every arrival. `Arrival` has no party class, kind, lane, clock, route, or identification, and there is no `jason arrivals` or correction act. `#/inbox` today lists PayHOA requests pending, not arrivals |
| Cycle board | The pieces: `outstanding_responses` (asked less answered, by owner and unit), the campaign funnel, the notice ledger (`Delivery`), the owner-information plan per owner (`/api/owner-info`; `OwnerStatus`, `delivery`), the follow-ups for the dates | The per-owner join. No row has asked, delivered, responded, reachable, and the next obligation together (followups-design build step 3) |
| Forms | `jason form-library --json` for the register; `jason campaigns --json` for its campaigns ([handoff-form-library.md](handoff-form-library.md#as-built-checked-against-the-code-2026-10-05)) | "Unknown references seen" per form; the handler's `built` flag is not in the JSON |
| Needs development | Nothing. `form_library/handlers.py` is a seven-row table (five general handlers, each `built=False`; two process handlers), the interim for a registry that is not written | The handler registry (`jason.handlers`), the gap record, `jason handlers --gaps|--coverage`, "handled by hand", the coverage map. The page is wholly proposed |
| Form candidates | `jason discover-forms --list|--show ID --json`, the three acts | The comparison "a document asks more or less than the statute" (a join is a lead, not a comparison) |

### Shapes, with made-up values

A recognition (`jason responses --show ID --json`, under `reading.recognition`; the MCP `response` tool returns only the copy, below):

```json
{"outcome": "recognized", "rung": "mark", "rungNumber": 4, "sure": "medium",
 "note": "The marker on page 1 of Scan.pdf carries reference NP27E-4RK9T-C7: the copy sent on 2099-10-01 to 123 Main St. One character was put right to make it the reference of a sent copy; it is a hint to confirm against the copy, not a reading.",
 "form": "owner-info", "authority": "CIV 4041", "reference": "NP27E-4RK9T-C7", "how": "put right",
 "matchesRequest": true, "unsent": false, "worthDownload": false,
 "tried": ["subject", "text-layer", "field", "mark"], "lines": 0}
```

`outcome` is `recognized`, `candidate`, or `not-ours`; `sure` is `high`, `medium`, or `low` (a word, as the design wants). A candidate has `form` and `authority` and `copy` is null; a not-ours has `rung` the last content rung tried. The copy as sent (`SentCopy`, also each row of the sent-copy catalog `data/forms/references.json`; ids, never an address):

```json
{"reference": "NP27E-4RK9T-C7", "form": "owner-info", "year": 2027, "channel": "email", "identity": "copy",
 "unit": "123 Main St", "unitId": 101, "membershipId": 5001, "firstSent": "2099-10-01T15:00:00+00:00",
 "lastSent": "2099-10-01T15:00:00+00:00", "campaign": "NP27E", "handler": "owner-information", "formVersion": "1"}
```

`identity` is `copy` (one owner and unit) or `campaign` (a mailed letter: the marker names the mailing, so no owner or unit is compared and the catalog lists no recipients). On a reading, the copy adds `owner` (the name as sent), `rung`, `sure`, `putRight`, `matchesUnit`, `matchesOwner`, `matchesWritten` (the MCP tool calls the last `matchesWrittenUnit`).

A form candidate (`jason discover-forms --show ID --json`; `--list --json` gives `{"candidates": [...]}`):

```json
{"candidate": {"id": "fc-3f2a9b0c11", "source": "statute", "citation": "CIV 5210",
   "quote": "the span's own words, copied from the source", "seeds": ["written request", "within N days of"],
   "reading": {"isRequest": true, "whoSubmits": "a member", "toWhom": "the association", "what": "inspect records",
     "requiredContent": ["a written request that identifies the records"],
     "clocks": [{"forWhom": "the association", "howLong": "10 business days", "ifPasses": "", "source": "statute"}],
     "decision": {"who": "the board", "inWriting": true, "reasons": false, "reconsideration": ""},
     "authority": "CIV 5210", "quote": "the operative words", "model": "a-local-model", "readAt": "2099-10-05T12:00:00+00:00"},
   "knownAs": "records", "knownWhy": "why it says so", "group": "g-12", "status": "new", "note": ""},
 "joins": [{"statute": "fc-3f2a9b0c11", "document": "fc-77d0e1aa02", "basis": "citation", "reason": "the document cites CIV 5210", "strength": 1.0}],
 "acts": [{"at": "2099-10-05T13:00:00+00:00", "by": "A. Admin", "act": "confirm", "candidate": "fc-3f2a9b0c11", "why": "", "detail": ""}]}
```

`status` is `new`, `confirmed`, `held`, or `dropped`; `reading` is null for "seeds only"; `source` is `statute` or `document`; a clock's `source` is `statute`, `governing documents`, `proposed policy`, or `none`; a join's `basis` is `citation`, `kind`, or `terms`.

### States the code can be in that this page does not draw

| State | The field and value that says so |
|---|---|
| A recognized copy of another campaign | `recognition.matchesRequest: false` (the note says "Its campaign is not this request's") |
| A reference of ours on a message that also carries one we did not send | `unsent: true` with a candidate or not-ours outcome; the note names where it was found |
| Two markers on one page disagree | no copy is named; the note says "the printed marker and the bar mark name different copies, so neither is used" |
| A not-ours worth downloading | `worthDownload: true`: a PDF or image, named and not downloaded, from an owner who was sent a copy and has not answered. Rung 7 never decides the result |
| Not recognized because the files could not be read | the note lists "could not be opened" or "Tesseract is not available, so printed text on a scan could not be read" |
| A mailed copy | `identity: "campaign"`, no unit or owner to compare |
| A candidate dropped by the reader | `status: "dropped"`, `note: "quote not found"`: the model's quote was not in the span word for word, so the reading and the candidate went together (a person's own drop has a reason in the acts) |
| A held candidate | `status: "held"`; `hold` requires a reason |
| A form with a handler that is not written | `handler` names one of the five general handlers; its `built` is false and a campaign may still be opened for it (not in the JSON) |

### Routes built (2026-10-10; `jason.web.extra.request_views`)

Loaders over what the CLI and the MCP tools read, so the console and a terminal show the same numbers. Keys, not paths (`GET /api/<key>`):

| Key | Reads | Takes | Replaces the proposed |
|---|---|---|---|
| `responses` | the arrivals the last `jason responses --check` kept, with each channel's last check | `state`, `channel`, `unit`, `request`, `days` | `/api/arrivals` |
| `response` | one arrival: reading (evidence), keyed answers, acts, what is left | `id` (`gmail:ID`, `payhoa:ID`, `mail:ID`, `forms:ID`) | `/api/arrivals/<id>` |
| `outstanding-responses` | who was sent a copy and has no answer, by owner and unit | `request` | part of `/api/cycle` |
| `campaign-status` | a campaign's funnel by channel, outstanding, unreachable | `code` | part of `/api/cycle` |
| `followups` | the dated actions with their basis and state ([handoff-followups.md](handoff-followups.md)) | `days`, `campaign`, `kind`, `state` | |
| `form-library` | the forms the profile offers, each with status and findings | `tier` | `/api/forms` |

- **Who.** A signed-in person whose office opens owners' names and units (P2); anyone else gets the sentence `access.may_see` gives (403), and the owner view never reads them.
- **An arrival's own words are held.** `response` returns the arrival (who, unit, channel, state, attachments' names) to P2, but its reading, keyed answers, and acts only where the viewer may see an owner's private material (P3, in the private view); otherwise `held: true` with the reason. Each opening is logged to `access/served.jsonl`, never its contents; an opening that cannot be logged is not served.
- **Read only.** No write route: marking a follow-up done, confirming a reading, and applying an answer stay terminal steps (`Command`) until a sign-in-guarded writer exists. Not built: `/api/cycle` (the per-owner join of asked, delivered, responded, reachable), `/api/instance/gaps`, `/api/form-candidates`, and a counts-only variant for directors.

### Drawn on this page, not yet producible (proposed, not built)

- Everything in **Arrivals** beyond the forms lane: lanes and their counts, the party class and kind as words, the clock ("respond by Oct 18, the sender's date"), the correction act that may become a proposed rule row, "needs a person" and its waiting time. `Needs a person` is the unknown lane of [arrivals-design.md](../arrivals-design.md) build step 3.
- **`RecognitionChip`'s "Disagrees":** not a field of `Recognition`; it is the reading's copy comparison (`matchesUnit`, `matchesOwner`, `matchesWritten` false), so the chip is drawn from a reading, not from an arrival that has none.
- **The cycle board:** `CycleRow`, `CycleLens`, `DeadlineStrip`, and `ObligationNote` as one row per owner. The lenses can be counted today only separately (haven't answered, can't reach, waiting for review, ready to record, done); "second addresses" has no source. `AnswerCycle.deadlines(today)` gives the strip's dates with days left: opened, return by, entered by (30 days before the reports, CIV 4041(b)(1)), reports mailed (CIV 5300, 5310). `ObligationNote`'s "required" and "policy" are the follow-up's `basis` (`law` or `documents`, `proposed policy`, `person`).
- **The form candidates' "possible conflict":** not computed; a statute and its document sections are joined, never compared.
- **The Forms register's** "handler missing" is the form's status `failing` with a `handler and procedure` finding; "unknown references seen" is not aggregated.

### Where the first draft's shape or word differed (the code wins; the text above is corrected)

- The delivery outcomes: "never mailed" and "forwarded" are the ledger's `failed` or `skipped` and `rerouted`; the ledger also has `pending`.
- The rungs' names (corrected above).
- "A field whose quote was not found in the span is missing and says why": the whole reading is dropped with its candidate, with the note "quote not found".
- A campaign "opens to its copies": the copies are the sent-copy catalog's rows for the campaign's prefix, joined to the answers by `outstanding_responses` (`outstanding` and `answeredCopies`, each with `reference`, `unit`, `owner`, `channel`, `sentAt`, `daysSinceSent`, and `answeredBy`, a list of arrival ids), not a field of the campaign.
- `Confidence` for a recognition is a word in the code (`sure`); for a field it is a number ([handoff-responses.md](handoff-responses.md)).

## Words

| Say | Not |
|---|---|
| Recognized | Matched, verified |
| Needs a person | Failed, unknown error |
| Handled by hand | Manually processed |
| Needs development | Unsupported, missing feature |
| Required (the law) / policy (the board's) | Mandatory, optional |
| Asked, delivered, bounced, not shown delivered | Sent, failed |
| Answers asked by | Deadline (it is the association's request date; the law's dates are named for what they are) |

## What must not change

- Cataloging and recognizing write nothing to Gmail, PayHOA, Drive, or the mail service, and send nothing.
- A recognition is a reading with its rung; only a person's attach or correction changes it, and the change is recorded.
- No count without its age; no zero without the time it was true.
- No screen sends, resends, files, replies, or completes a request. A required follow-up shows its command.
- Gaps and candidates show no content of any arrival and no owner's private facts; directors see counts and states, not readings.
- Confidence and attention are never color alone.

## Decisions that are the design's

1. Whether Arrivals replaces the Inbox or sits beside it, and how a letter from the mail service and an email from a vendor share a row.
2. Whether a lane is a tab, a section, or a filter, on a phone.
3. How the cycle board's seven columns collapse on a narrow screen (a card per owner, or a list of lenses first).
4. How a required follow-up is told apart from a policy one at a glance.
5. Whether Forms and Needs development are two screens or two tabs of one administrator page.
6. The glyph for "needs development", for "recognized", and for "a reference we did not send" (one meaning per glyph).

## Open (the build's or a person's)

- The console routes (proposed): `GET /api/arrivals`, `/api/arrivals/<id>`, `/api/cycle`, `/api/forms`, `/api/instance/gaps`, `/api/form-candidates`; the acts as writes behind the sign-in guard.
- The cycle board's join (asked, delivered, responded, reachable) is designed and not built.
- The handler registry and the campaign record are designed and not built.
