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

The rung (subject, text, field, bar mark, layout, citation, sender) is a small detail line, not a headline: the person needs to trust the result, not learn the ladder.

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

- **Columns, as facts:** Asked (channel, date, outcome: delivered, opened, bounced, not shown delivered, mailed, returned, forwarded, never mailed, skipped), Responded (none, arrived by channel and date, read, confirmed, recorded, replaced by a later answer), Delivers by now (mail, email, both, or "no election: first-class mail"), Reachable (reached, or nothing has reached them), Second address (given or not, with its own outcome), Representative and occupancy (given, blank, or differs from the unit tag), and **Open obligation** (what the law or policy asks next, with its citation and the command).
- **Lenses** are the working lists; a row can be in more than one. Counts carry the age of their source, and a lens with an old source says so in its tab, not only on hover.
- **Open obligation** reads from the follow-up rules: "Resend the notice by first-class mail and ask for a working email — CIV 4041(e), 4040(a)(2) — required" or "… — policy". The citation is the recited authority (a link to the words), never a paraphrase; required and policy are marked differently so a board can see which is the law's and which is its own.
- **Deadlines** are the strip above: asked-by, entered-by, reports-mailed-by, each with days left and, once passed, days over. A row past a date shows it.
- **Directors** see the counts and the states, not a scan, an answer, or an address. Owners never see it.
- **Never:** a send, a resend, or a completion from this screen. A row offers the command; resending is a person's `--yes`.

## Forms

A register of the forms jason sends, drawn like the other registers (`RegisterGrid`).

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
| `FormRegister`, `CampaignCopies` | Forms | The known forms and each campaign's sent copies |
| `GapRow`, `HandledByHand`, `CoverageMap` | Needs development | A gap, what a person did, and the citations with no handler |
| `CandidateReview`, `ClockList`, `SourceJoin` | Form candidates | The quote beside the reading, the clocks, and the joined sources |
| `AgeStamp` | everywhere | "as of Oct 5, 4:30 PM" or "last checked 2 h ago": the time a number was true |

Reuse what is built: `Tabs`, `RegisterGrid`, `DataTable`, `Seal` (`read`), `Pill`, `Command`/`TerminalStep`, `Confirm`, `Evidence`, `Recitation`, `Glyph`, `Caveats`, `HeldRow`, `NewResponsesCount`. No `Stamp`: nothing here is a decision.

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
