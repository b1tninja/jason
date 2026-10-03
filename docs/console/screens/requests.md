# Requests

A new screen, `#/requests` (`?id=` for one request), in the Overview group · phase 2 · CLI: `jason respond`

## In the console

No screen lists every member request with its clock. Three screens hold parts of it:
- **Inbox** (`#/inbox`, `open_items`) lists PayHOA requests pending among everything waiting on the association;
- **Drafts** (`#/drafts`, `request_links.drafts`) lists emailed requests PayHOA does not have, each with the command that enters it;
- **Records requests** (`#/records-requests`) handles one kind, a member's request for records, with its 5210 clock and the board's decisions.

**What this spec adds:** the whole screen, from `jason respond`: every request with the clock that runs on it, who set that clock, its standing, the leads to where the answer is written, and the acknowledgment draft. The loader to add is `member-requests` (`?open=1`, `?id=`, `?sources=1`), over `jason.api.member_requests` and `acknowledgment_draft`. Records requests keep their own screen; this one links to it for that kind.

## Purpose and personas

Members' requests and their clocks: what each one is, when it came in, which clock runs on it and who set that clock, when the answer is due, and what the next step is. The screen helps a person answer on time. It never decides a request.

- **Manager:** works the open requests most urgent first. Reads the leads to where the answer is written. Drafts an acknowledgment for a person to send.
- **Director:** reads the requests that wait on the board (architectural, solar, EV charger, rental, variance) before a meeting.
- **Treasurer:** reads the requests of a finance kind.
- **Secretary, reviewer, counsel:** no access.

**What this screen never has.** No approve, deny, or assign control, at any phase. A request's decision is made in PayHOA by a person, or by the board at a meeting. jason computes the clock and drafts the first words; that is all ([AGENTS.md](../../../AGENTS.md#boundaries)).

## Data

| Part | Source |
|---|---|
| Open requests | `jason.api.member_requests(open_only=True, limit=200)` → `responses.handle` plus `responses.email_requests`. Each row: `id`, `kind`, `unit`, `title`, `received`, `due`, `clock`, `clockSource` (statute, documents, or policy), `owner` (the schedule's role), `acknowledged`, `answered`, `closed`, `standing`, `next`, `classifiedBy` |
| The summary | `member_requests(...)["summary"]` (`responses.summary`): open by standing; answered on time against late, by kind |
| The caveat | `member_requests(...)["caveat"]`, verbatim: "Email kinds come from subjects; a proposed clock is a target until the board adopts it." |
| One request | The row above, plus PayHOA's own fields (`responses.payhoa_fields(data_dir)`: PayHOA's due date and tags) and the hints (`responses.payhoa_hints`) |
| The clock's authority, recited | `jason.api.cite_document(rule.authority)` for a statute or a document's section. A policy clock shows the rule row and "proposed, not adopted" until the board adopts it |
| Leads to the answer | `member_requests(sources=True)` → `response_sources.sources_for`: the governing documents' passages, library files by name, and precedent violations. The caveat: "Each source is a lead to read, not a ruling; a precedent shows past handling, not this matter's facts." |
| The acknowledgment draft | `jason.api.acknowledgment_draft(request_id)`: `draft`, `send` (how a person sends it), `acknowledged` |
| Emailed requests PayHOA lacks | `request_links` (`jason.mcp.county.request_links`) |

**Standing words** are `responses._standing`'s: "answered on time", "answered late (N days)", "answered", "OVERDUE (N days)", "due soon" (within five days), "open", "open, no clock". A business-day clock skips weekends but not holidays, so the due day shown is the earliest it can fall; the screen says so beside a business-day clock.

## Layout: the list

```
+------------------------------------------------------------------------------------------+
| Requests                                                                                 |
| 14 open: 2 overdue · 3 due soon · 9 open · last 12 months: 41 answered, 37 on time       |
| Synced Oct 3, 06:00 · jason sync-catalog                         CLI: jason respond [copy] |
+------------------------------------------------------------------------------------------+
| Kind [All v]  Standing [Open v]  Owner [All v]  [Filter]                                 |
+------------------------------------------------------------------------------------------+
| #      Kind            Unit  Received  Clock                     Due     Standing  Next   |
|------------------------------------------------------------------------------------------|
| 1042   architectural   12    Sep 1     45 days (documents)       Oct 16  due soon  board  |
| 1050   records         21    Sep 20    10 business days (statute) Oct 4   due soon  send   |
| email  maintenance     -     Sep 12    5 days (policy, proposed) Sep 17  OVERDUE 16 ack.   |
+------------------------------------------------------------------------------------------+
| Email kinds come from subjects; a proposed clock is a target until the board adopts it.   |
+------------------------------------------------------------------------------------------+
| EMAILED REQUESTS NOT IN PAYHOA (2)                                                       |
| Sep 28 · subject "Gate code not working" · from Owner F · likely request 1049 (score 3)   |
+------------------------------------------------------------------------------------------+
```

## Layout: one request

```
+------------------------------------------------------------------------------------------+
| Requests > 1042 · architectural · Unit 12                                    due soon     |
+------------------------------------------------------------------------------------------+
| THE CLOCK                                                                                |
| Received Sep 1, 2099 · due Oct 16, 2099 [13 days left] [Legal]                            |
| Set by: the governing documents · owner: the board                                       |
| [Recitation] Declaration 8.2 ... the words whole, version in force, caveat ...           |
| [ReadingLabel: jason's reading] The 45 days run from the day the request was received.   |
+------------------------------------------------------------------------------------------+
| PAYHOA'S FIELDS                     | WHERE THE ANSWER IS WRITTEN (leads)                 |
| Due date: Oct 15 · tags: ARC        | Declaration 8.2 [Document] · Rules R-3 [Document]   |
| Acknowledged: no                    | 2 earlier decisions on similar requests [Record]    |
| Answered: no                        | Each source is a lead to read, not a ruling.        |
+-------------------------------------+-----------------------------------------------------+
| ACKNOWLEDGMENT DRAFT                                       for a person to read and send  |
| Thank you. The Association received your architectural on September 1, 2099, and it is   |
| being reviewed. Under Declaration 8.2, the Association will respond by October 16, 2099. |
| The Board decides applications at its meetings; we will let you know the meeting it is on.|
| - Example Village HOA                                                                    |
| [Copy the text]   Send it from PayHOA, on the request's page.                            |
+------------------------------------------------------------------------------------------+
```

## Components

`ScreenHeader`, `DataTable`, `Pill` (the standing words), `DueDate`, `Card`, `Recitation`, `ReadingLabel`, `Evidence`, `Clock`, `Caveats` (verbatim), `Command`, `RemoteView`.

## Actions

| Control | Does | Approval? | CLI |
|---|---|---|---|
| Filter | the loader's `kind`, `standing`, `owner` (a role) | No | `jason respond --kind KIND` |
| Show leads | Reads again with `sources=1` | No | `jason respond --sources` |
| Copy the acknowledgment | Copies the draft text | No | `jason respond --draft ID` |
| Save as a Gmail draft (an emailed request) | shown as a command; later the `gmail.draft` kind (phase 3) | Later: an approval (R1) | `jason respond --draft ID --gmail --yes` |
| Enter an emailed request in PayHOA | the command `#/drafts` already shows; later `payhoa.request.create`. The request is entered, never approved, denied, or assigned | Later: an approval (R2, no undo: the owner sees it) | `jason request-links --create THREAD --yes` |
| Open the unit | `#/members?unit=<id>`, once that screen exists | No | — |

**Posting the acknowledgment to PayHOA is not a console action.** `jason request-comment ID "text"` posts a comment that PayHOA emails to the owner, and it has no dry run and no `--yes` today (lesson `google-writes-without-yes`). Until it has a gate and a registry row ([approval-workflow.md](../approval-workflow.md#writes-with-no-gate-today)), the console shows the text to copy and says: "Send it from PayHOA, on the request's page."

## States

- **No catalog:** "Requests are unavailable: no PayHOA requests on disk. Run `jason sync-catalog`."
- **No open requests:** "No open requests. 41 answered in the last 12 months, 37 on time." The answered summary still shows.
- **A request with no clock:** "open, no clock" and, under the clock: "No rule sets a clock for this kind. If one should, it is a proposal for the board." Never a made-up due day.
- **A policy clock not adopted:** the clock reads "5 days (a proposed policy, not adopted)". It is ranked after a statute's or the documents' within one urgency, and the acknowledgment draft gives no date for it.
- **Already acknowledged:** the draft section says "Acknowledged Sep 3" and offers no draft.
- **Kind read from an email subject:** a note beside the kind: "Read from the subject; check it." (`classifiedBy`).

## Privacy

- Unit and request kind are P1. The request's title can name a person or an address, so it is P1 for the manager and director and hidden from the treasurer except on finance kinds.
- An emailed request's sender is shown by name; the address is P2, masked, with Show.
- The thread's body is not on this screen. It opens in Gmail through its link.
- Precedent violations among the leads show the unit and kind only; their detail is P3 in the private view.
- The screen is not in the owner view. An owner asks for records through `#/records-requests?view=owner`, as built.

## Acceptance criteria

1. Neither the list nor one request has a button or link labeled approve, deny, assign, or close for a request.
2. Rows sort as `member_requests` sorts them: open first, then by due day.
3. Each standing renders with `responses._standing`'s words.
4. A statute's clock links its recitation, and the recitation renders before any reading of it.
5. A policy clock not adopted is labeled "proposed, not adopted" everywhere it shows, and the acknowledgment draft has no date for it.
6. The acknowledgment draft renders exactly `acknowledgment_draft`'s `draft` text, unedited, with "for a person to read and send".
7. Leads carry the caveat verbatim.
8. A missing catalog renders the unavailable state with `jason sync-catalog`.
