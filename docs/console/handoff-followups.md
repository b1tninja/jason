# Handoff: forms and campaigns, and follow-ups

For a design pass on the two views in [followups-design.md](../followups-design.md): **Forms and campaigns** (what we ask, and how it is going, by the way each answer came in) and **Follow-ups** (what we do next, and when, with the count still outstanding). It builds on [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) (arrivals, the cycle board, the forms register), [handoff-form-library.md](handoff-form-library.md) (the form a member sees and the library), and [handoff-responses.md](handoff-responses.md) (one returned form). Read [handoff-reconciliation.md](handoff-reconciliation.md) and its third and fourth cuts first. The component names are proposals; the data shapes follow the design and the build corrects this page.

## The idea in six sentences

A request to members has two lives. The first is the thing itself: a form, sent in a campaign, answered by some owners in some ways. The second is the work around it: the dates the law and the board set, and the owners who have not answered. The two views read the same records and never copy one into the other. The count that matters is who is **still outstanding**, and an owner who answered by any method is not on it; how many answered by each method is a separate fact about which doors owners use. Nothing here sends a reminder, resends a notice, or completes a request: a follow-up is a plan for a person, with the command that does it. Every number says how old its source is.

## Who sees what

| Viewer | Sees |
|---|---|
| A manager, the Secretary, an administrator | both views in full: names (units and names, never addresses or answers) |
| A director | both views with counts and dates; the lists of names are held back |
| An owner | nothing here; their own requests are in the request center ([handoff-form-library.md](handoff-form-library.md)) |

## View 1: Forms and campaigns

```text
+----------------------------------------------------------------------------------------------+
| Forms and campaigns                                                       as of Oct 5, 4:30 PM |
| [ Campaigns 3 ] [ Forms 19 ] [ Closed ]                                                          |
+----------------------------------------------------------------------------------------------+
| Owner information 2027 · form v1 · handler: owner information · answers asked by Oct 23   Open |
|   asked        90 copies   (email 90 · 1 mailing, no recipients listed · PayHOA —) · 17 never sent |
|   answered      47          (PayHOA 20 · email 18 · mailed scan 7 · Google Form 0 · keyed 2)       |
|   read 46 · confirmed 44 · recorded 38   (each includes the later stages)                         |
|   outstanding   58 owners   unreachable 2          next: remind Oct 16 · answers due Oct 23     |
+----------------------------------------------------------------------------------------------+
| Request to inspect records · form v2 · handler: response clock                        Not opened |
+----------------------------------------------------------------------------------------------+
```

- **A campaign card** (`CampaignCard`): the form and its version, the handler in plain words, the cycle's dates, its status, and the **funnel** (below). One line says the next action and its date, linked to View 2.
- **The Forms tab** is the one `FormRegister` ([defined in handoff-form-library.md](handoff-form-library.md); the Forms register of [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) is the same table): each form by tier, with a campaign count and "not offered (the missing slot)" where that is so.
- **Opening a campaign** is a command (`jason campaigns --open`), shown as a `TerminalStep`; the screen offers it for a form that is ready and has no open campaign.
- **A campaign opens** to its copies: each reference sent, the unit and owner it went to, when, the channel, and whether it has an answer (`CampaignCopies`). No addresses.

### The funnel (`CampaignFunnel`)

One drawing, used on the card, the campaign page, and the dock. Four stages left to right, each a count and a bar against what was asked:

```text
Asked 90 ──▶ Answered 47 ──▶ Confirmed 44 ──▶ Recorded 38
  by how asked: email 90 · 1 mailing · PayHOA —     by how answered: PayHOA 20 · email 18 · mailed scan 7 · keyed 2
Outstanding 58      Unreachable 2 (apart)
```

- **Outstanding** is the headline and is **by owner, whichever way**: it is "asked" minus "answered by any method". It is a number and a list of names (units and names), never a share of channels.
- **By how asked** and **by how answered** are two small breakdowns, each channel a word and a count, never a color alone. They are different questions: an owner emailed a copy may answer on the PayHOA form, and that is one answer.
- **Unreachable** is drawn apart, with its own count and the follow-up the law asks (resend by first-class mail, CIV 4041(e)). It is never counted in outstanding and never hidden; the owners on it are the ones a reminder cannot reach.
- **A channel with nothing** is "—" in a quiet face, not "0", unless it was checked and found empty ("0 as of 2 h ago").
- **Each count carries its age:** the sent-copy catalog, the last check per channel, the delivery sync. A stale source is said on the stage it feeds, not only on hover.
- **States:** a campaign not yet sent (no funnel: "Not opened"); open, none answered; mid-cycle; past return-by with outstanding; complete (all answered or unreachable); closed (the funnel frozen with the date).

## View 2: Follow-ups

```text
+----------------------------------------------------------------------------------------------+
| Follow-ups                                                          2 overdue · 3 this week   |
| [ All ] [ Reminders ] [ Deadlines ] [ Resend ] [ Review ] [ Mine ]        Campaign: [ all v ]   |
+----------------------------------------------------------------------------------------------+
| OVERDUE                                                                                         |
|  ⚑ Oct 3   Resend by mail: 2 notices that bounced                CIV 4041(e)  required   [cmd] |
|            2 owners · the law's resend (no day count: proposed 3 days after the outcome was read) |
| TODAY                                                                                            |
|  ☑ Oct 5   Read 3 returned forms                                 proposed policy         [cmd] |
| THIS WEEK                                                                                        |
|  ✉ Oct 16  Remind the 58 owners who have not answered            proposed: 7 days before         |
|  ▤ Oct 23  Answers asked by                                      the campaign's date             |
| LATER                                                                                            |
|  ▤ Nov 1   Enter the answers in PayHOA                           CIV 4041(b)(1) · the law        |
|  ▤ Dec 1   Annual reports mailed                                 CIV 5300, 5310                  |
+----------------------------------------------------------------------------------------------+
```

- **Date order, in bands:** overdue, today, this week, later. A band with nothing is not drawn; "Nothing overdue as of 4:30 PM" is said once.
- **A row** (`FollowUpRow`): a kind glyph, the date, the action in a line, the **basis** as a labeled chip (the law with its citation, the documents with the section, the board's rule, **proposed** where the law is silent, or a person's), the outstanding count when there is one, and the command.
- **Basis is always shown.** "Required" (the law's) and "proposed" (not yet the board's) look different at a glance; the colors are not the only mark. A proposed number says so in words ("proposed: 7 days before"), and the board's adoption moves it to "the board's rule".
- **Acts on a row:** done, defer to a date (with a reason), drop (with a reason), each by name; until console writes exist each is a `TerminalStep`. A done row says who and when and stays visible for a day, then goes to the log.
- **Add one:** "call the printer on Thursday" with a date, by name; it appears among the others, labeled "yours".
- **The outstanding count on a row** opens the list of owners it is about (units and names). For a director it is a number only.
- **The calendar strip** (`FollowUpStrip`): the next 30 days as a line of dots by date with the kinds; the same items appear in the dock's Deadlines.
- **Filters:** by campaign, by kind, "mine". The default is everything in the next 14 days plus what is overdue.
- **States:** nothing due ("Nothing due in the next 14 days as of …"); a source not read ("The delivery sync has not run since Oct 2, so bounced notices are not shown": shown on the band, never silent); an item deferred (its new date and reason); an item dropped (the reason).

### What a follow-up never does

It never sends the reminder, never resends the notice, never records the answer, and never marks a request complete. The row's command is what a person runs, and the screen says "A person runs this".

## Intake methods, drawn once

The channels have one set of marks used everywhere, defined once as `ChannelMark` in [handoff-responses.md](handoff-responses.md#channelmark): **PayHOA's form**, **email**, **mailed scan**, **Google Form**, and **keyed from paper** (a form handed in or taken by phone, which a person types as an arrival with the method named). A channel in a breakdown is its mark and a word; the order is fixed so a person learns it.

## Components

| Component | On | Job |
|---|---|---|
| `CampaignCard`, `CampaignFunnel`, `CampaignCopies` | View 1 | A campaign, its funnel by how asked and how answered, and its sent copies. `CampaignCopies` is defined here once; [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) points to it |
| `OutstandingList` | both | The owners still outstanding, units and names; counts only for a director |
| `UnreachablePanel` | View 1, the dock | Owners no ask has reached, with the follow-up the law asks |
| `FollowUpRow`, `FollowUpBand`, `FollowUpStrip` | View 2 | A dated action, the bands by date, and the 30-day strip |
| `BasisChip` | View 2 | Law (with citation), documents (with section), the board's rule, proposed, or a person's |

Reuse what is built: `Tabs`, `RegisterGrid`, `Seal`, `Pill`, `Command`/`TerminalStep` ([defined once](handoff-admin-components.md#terminalstep)), `Confirm`, `Glyph`, `Caveats`, `ChannelMark` ([defined once](handoff-responses.md#channelmark)), `AgeStamp` ([defined once](handoff-forms-and-arrivals.md#agestamp): "as of Oct 5, 4:30 PM", the time a number was true), `Recitation`, `HeldRow` (for what a director may not see; a director's counts-only list is a state of `OutstandingList`, not a held item). No `Stamp`: a follow-up is not a decision.

## As built (checked against the code, 2026-10-05)

Both views' data is built ([followups-design.md](../followups-design.md), steps 1 and 2): `jason campaigns [--show CODE] --json` and the MCP tool `campaign_status` for View 1; `jason followups --json` and the tool `followups` for View 2. Disk only; names and units only. The console screens, the dock's Deadlines, the board calendar, and the per-owner cycle board are not built. The tools are the nearer shape (masked, with `sourceAge` on each item). No loader exists, and no `PathRule` names `followups/*` or `forms/campaigns.json`, so the build assigns their level; the names in a list are owners' names and units, and a director gets the counts.

### The shapes, with made-up values

A campaign's funnel (`campaign_status`'s `campaigns[]`; `jason campaigns --show CODE --json` puts the same under `funnel` beside the campaign's own row):

```json
{"found": true, "campaign": "NP27E", "form": "owner-info", "version": "1", "year": 2027, "channel": "email",
 "status": "open", "returnBy": "2099-10-23", "request": "owner-information-2027", "at": "2099-10-05T20:30:00+00:00",
 "asked": {"total": 90, "byChannel": {"email": 90}, "mailings": 1, "source": "the sent-copy catalog", "ageHours": 6.0,
           "newestSent": "2099-10-01T15:00:00+00:00"},
 "answered": {"request": "owner-information-2027", "answered": 47, "read": 46, "confirmed": 44, "recorded": 38,
   "byChannel": {"payhoa": {"answered": 20, "read": 20, "confirmed": 20, "recorded": 18, "checkedHoursAgo": 2.0, "checked": "last succeeded 2099-10-05T18:30:40+00:00; last try ended ok"},
                 "gmail": {"answered": 18, "read": 17, "confirmed": 15, "recorded": 13, "checkedHoursAgo": 2.0, "checked": "last succeeded 2099-10-05T18:30:12+00:00; last try ended ok"},
                 "mail": {"answered": 7, "read": 7, "confirmed": 7, "recorded": 5, "checkedHoursAgo": 2.0, "checked": "last succeeded 2099-10-05T18:30:44+00:00; last try ended ok"},
                 "forms": {"answered": 0, "read": 0, "confirmed": 0, "recorded": 0, "checkedHoursAgo": null, "checked": "never checked"},
                 "manual": {"answered": 2, "read": 2, "confirmed": 2, "recorded": 2, "checkedHoursAgo": null, "checked": "keyed by a person: nothing to check"}},
   "inboxExists": true, "inboxAgeHours": 2.0, "source": "the response inbox, as the last check and the people who keyed returns kept it"},
 "outstanding": {"count": 58, "owners": [{"unit": "456 Oak Ln", "name": "B. Owner", "channel": "email", "sentAt": "2099-10-01T15:00:00+00:00", "daysSinceSent": 4}],
                 "neverAsked": 17, "source": "the sent-copy catalog less the answers kept", "ageHours": 6.0},
 "unreachable": {"count": 2, "owners": [{"unit": "789 Elm Ct", "why": "email bounced"}], "source": "the notice ledger",
                 "ageHours": 30.0, "syncedAt": "2099-10-04T14:00:00+00:00", "attempts": 3},
 "ages": {"catalogHours": 6.0, "inboxHours": 2.0, "checks": {"payhoa": 2.0, "gmail": 2.0, "mail": 2.0, "forms": null, "manual": null},
          "ledgerHours": 30.0, "ledgerSyncedAt": "2099-10-04T14:00:00+00:00"},
 "missing": [], "notes": [], "nextFollowUp": null}
```

`jason campaigns --json` is `{"campaigns": [row, ...]}` with the campaign's own record on each row (`code`, `form`, `formKey`, `version`, `asOf`, `authority`, `handler`, `options`, `procedure`, `channel`, `year`, `cycle: {opened, returnBy}`, `by`, `chosenAt`, `status` `open` or `closed`, `closedBy`, `closedAt`, `adopted`, and `written`), the counts (`copies`, `mailings`, `returned`, `recorded`, `request`), `funnel`, and `nextFollowUp`.

A follow-up (`followups`, and `jason followups --json`'s `items`; the tool adds `sourceAge`):

```json
{"id": "fu-1a2b3c4d5e", "kind": "remind", "due": "2099-10-16", "windowEnd": "2099-10-23", "subject": "NP27E",
 "what": "Remind 58 owners who have not answered the NP27E request", "basis": "proposed policy",
 "cite": "proposed: remind 7 days before the return-by date (the board has not adopted a number)",
 "dueNote": "proposed: 7 days before 2099-10-23", "outstanding": 58, "names": ["456 Oak Ln (B. Owner)"], "reason": "",
 "state": "upcoming", "by": "", "at": "", "why": "", "deferredTo": "",
 "command": "jason owner-info --email-batch --follow-up reminder --message FILE.md (a dry run; --yes sends)",
 "campaign": "NP27E", "source": "campaign",
 "sourceAge": {"source": "the campaign record", "ageHours": 20.0, "catalogAgeHours": 6.0, "says": "the campaign record written 2099-10-04T22:00; the sent-copy catalog written 2099-10-05T14:00"}}
```

The tool's envelope: `{"found": true, "asOf", "within", "count", "counts": {"overdue": 2, "due": 1, "upcoming": 3}, "items": [...], "ages": {"campaign", "catalog", "inbox", "ledger", "person"}, "note", "caveats"}`, each age `{source, exists, at, ageHours, reason}` (the inbox adds `lastCheck`, `lastCheckAgeHours`). The command's `--json` has `counts: {overdue, dueToday, coming}`.

### States the code can be in that this page does not draw

| State | The field and value that says so |
|---|---|
| A campaign the profile already runs, its row not yet written | `written: false`, `adopted: true`, `by: "the profile (its response requests)"` (`jason campaigns --adopt` writes it) |
| No request watches the campaign | `answered: null`, and `missing[]` says so; `outstanding.count: null` with `reason` |
| A count that cannot be made | `null`, never zero, with a `reason` or a `missing` row: no emailed copy on record (a mailing names no recipient); no notice ledger on disk; the ledger holds no delivery of this campaign's copies yet; no owner list (`neverAsked: null`, `neverAskedReason`) |
| One request watched by several campaigns | `notes`: "the answers are the request's, not this campaign's alone" (an arrival is attributed to a campaign only by a copy it names) |
| A closed campaign | `status: "closed"`, `closedBy`, `closedAt`. Its funnel is still read live from disk; it is not frozen |
| A mailing and no emailed copy | `asked.total: 0`, `asked.mailings: 1` |
| An outstanding reminder with nobody to remind | `outstanding: 0`, `what`: "Nobody is outstanding: there is no one to remind (mark this done, or drop it)"; jason never marks it done |
| A count not known on a follow-up | `outstanding: null`, `reason` |
| A follow-up from an arrival | `kind: "review"`, `source: "inbox"`, `outstanding: 1`, `names: ["A. Owner (123 Main St)"]`, `campaign: ""`; stages read, confirm, record |
| A follow-up from a request's clock | `source: "clock"`, `kind` `acknowledge`, `decide`, `answer-due`, or `review`; basis `law`, `documents`, or `proposed policy` from who set the clock; business days run Monday to Friday with no holiday subtracted (the earliest the clock can run out) |
| A follow-up the person acted on | `state` `done` (`by`, `at`, `why` is the note), `deferred` (`deferredTo`, `why`), `dropped` (`why`); a deferred item is `deferred` until its day, then `due` or `overdue` from it, with `due` still the original day and `deferredTo` the new one |
| A source missing | `ages[source].exists: false` with `reason`; the derived items from it are simply absent (no ledger, no resend items), so "the delivery sync has not run" must be read from `ages`, not from an item |
| A person's own item | `kind: "manual"`, `basis: "person"`, `source: "person"`, `cite: "added by A. Admin on 2099-10-04"`, `campaign` optional |

### Drawn on this page, not yet producible (proposed, not built)

- **The board's rule as a basis.** `basis` has four values, `law`, `documents`, `proposed policy`, `person`. A campaign's own `remind-days` setting is `person` (`cite`: "set by NAME when the campaign was opened"). The profile hook that adopts a number, and the move to "the board's rule", is the open decision in followups-design; until then every proposed number stays proposed.
- **"Mine" and "yours":** no owner field. The only attribution is `by` on an act and the `cite` of a manual item.
- **A done row stays visible for a day:** a done item leaves the default list at once (`--all`, or the tool's `state: "done"`, lists it).
- **The 30-day strip** is not a field; it is composed from `items`. The dock's Deadlines do not carry follow-ups.
- **A form stale against an amendment** is not derived.
- **A frozen funnel at close,** and the funnel stages "complete" and "past return-by with outstanding": derived by the screen from `outstanding.count`, `returnBy`, and `status`.
- **"Not opened":** a form with no campaign is not a campaign row; it is a `ready` or `adjusted` form in the library with no open campaign for it (the library table's join). `jason campaigns --open FORM --channel C --cycle-year Y --by NAME [--handler KEY] [--option NAME=VALUE] [--return-by DATE]` is the step the card offers.
- **"Asked 107 owners":** not countable. `asked.total` counts emailed copies; a mailed letter's marker names the mailing, so its recipients are not listed, and the owners the law mails appear as `neverAsked` (a count and a list on `jason responses --outstanding`) until they answer. PayHOA's own form carries no marker jason stamps, so nobody is "asked by PayHOA" in the catalog.
- **A role-aware read:** every tool lists names. The director's counts-only view is the loader's work.

### Where the first draft's shape or word differed (the code wins; the text above is corrected)

- Eleven kinds, not four filters: `remind`, `return-by`, `enter-by`, `reports-mailed`, `resend`, `acknowledge`, `review`, `decide`, `answer-due`, `close`, `manual`. The View's filters group them: Reminders is `remind`; Deadlines is `return-by`, `enter-by`, `reports-mailed`, `answer-due`, `close`; Resend is `resend` (its `what` says "ask" when the follow-up is to ask a member for an address, not to resend); Review is `review`, `acknowledge`, `decide`.
- States: six words, `upcoming`, `due` (today), `overdue`, `done`, `deferred`, `dropped`; the bands (overdue, today, this week, later) are the view's.
- The proposed numbers (`PROPOSED_DAYS`): remind 7 days before the return-by date; resend 3 days and ask 7 days after the outcome was read; read 3 days and confirm 3 days after the arrival was kept or read; record 7 days after it was confirmed (or came structured); close 7 days after the return-by date. The draft's "proposed 5 days" resend is 3.
- The funnel's stages are cumulative: `read` includes `confirmed` and `recorded`; a structured arrival (PayHOA, a Google Form) counts as read and confirmed. The draft's card read as exclusive buckets.
- `answered.byChannel` is keyed by the inbox's channel words (`payhoa`, `gmail`, `mail`, `forms`, `manual`); `asked.byChannel` by how a copy was sent (`email`, `mail`). "Email" is `gmail` in one and `email` in the other.
- A campaign's status is `open` or `closed` only.
- Unreachable owners come from the notice ledger (`Delivery` words `bounced`, `failed`, `unknown`, `skipped`, `returned` with no attempt that arrived); an owner whose attempts are still pending stays outstanding.

## Words

| Say | Not |
|---|---|
| Outstanding (has not answered) | Pending, missing |
| Unreachable (no ask has reached them) | Bounced, failed |
| Asked, answered, confirmed, recorded | Sent, completed |
| Answers asked by | Deadline (the association's request date; the law's dates are named for what they are) |
| Proposed: 7 days before | Default, recommended |
| Required (the law) / the board's rule / proposed | Mandatory, optional |
| Keyed from paper | Manual entry |
| A person runs this | Click to send |

## What must not change

- jason sends nothing, resends nothing, and completes nothing from either view.
- Outstanding is by owner, whichever way they answered; an unreachable owner is never counted as outstanding and never hidden.
- No count without its age; no zero without the time it was true; a dash for a source never read.
- A proposed policy is labeled proposed, in words; the board's adoption is shown as the board's.
- Names and units only; never an address or an answer; directors see counts.
- Attention is never color alone; the bands and chips are readable in print.

## Decisions that are the design's

1. Whether the two views are two screens or two tabs of one page, and how the funnel and the next follow-up link to each other.
2. How the funnel draws "by how asked" and "by how answered" so a person never mistakes them for stages.
3. How the bands read on a phone (a single list with sticky band headings, or a week strip first).
4. How a deferred item shows its old and new date without looking overdue.
5. Whether `FollowUpStrip` belongs in the dock only, in the screen only, or both.
6. The glyphs for the follow-up kinds (remind, deadline, resend, review) and for "unreachable" (one meaning per glyph).

## Open (the build's or a person's)

- The console routes (proposed): `GET /api/campaigns`, `/api/campaigns/<code>` (the funnel), `GET /api/followups`, and the acts as writes behind the sign-in guard, recorded by name.
- The numbers where the law is silent (days to remind, to resend by mail, to read and confirm) are the board's to adopt.
- Whether follow-ups go to the board calendar and tasks by default or when a person asks.
