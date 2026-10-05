# Arrivals: catalog everything that comes in, identify the form, route by what it is

Status: design (2026-10-05). It widens [responses-design.md](responses-design.md) from "has anyone answered this request?" to "what has come in, from whom, and what is it?". The responses work is the first handler; this page is the layer above it.

## Why

In production a scheduled task syncs down what arrived (Gmail, the mail service's scans, PayHOA's requests and conversations, form responses). Then jason should know what each thing is and handle it by the process that fits. Today that knowledge is spread over classifiers that do not meet:

| Piece | What it knows | Where |
|---|---|---|
| `email_intents`, `Intent` | what an email asks, from its subject: complaint, maintenance, information, billing, question, enforcement | `tasks/intents.py`, `community/topics.py` |
| `reply_needed`, `party_class` | who a thread is with, and whether it waits on the association | `tasks/replies.py` |
| `MailKind`, `classify` | what a paper letter is: legal notice, insurance, government, escrow, bank, utility, invoice, advertising | `postscanmail/models.py`, `tasks/mail.py` |
| `DocumentKind`, `classify_document` | what an attached document is | `community/documents.py` |
| `PartyResolver`, the sender directory | who an address is: an owner on a day, a vendor, counsel, a manager | `tasks/parties.py`, `sources.sender_in` |
| `FormKey`, `FormTemplate`, `form_refs`, `form_reader` | the known forms, a copy's printed reference, a scan's reading | `community/forms.py`, `form_refs.py`, `form_reader.py` |
| the conversation catalog | which messages belong together, who answered whom | designed, not built ([conversations-design.md](conversations-design.md)) |
| the procedures | each task's steps in order | `community/procedures.py` |

None of them says "this arrived; here is what it is and what to do". An email carrying a returned form was found by a person searching a mailbox.

## The idea, in four steps

1. **Catalog.** Every arrival from every channel gets one record in one index: where it came from, when, from whom, a subject or title, its attachments' names. No bodies are stored.
2. **Identify.** Find out whether it is a known form, and which: the printed reference on a copy, a PayHOA form's id, a Google Form's id, a title and layout match. This step is cheap, deterministic, and has no judgement in it.
3. **Triage.** Say who it is from (a party class) and what kind of message it is. Rules first, in order, with the basis kept; a local model only for what no rule takes; a miss stays a miss and waits for a person.
4. **Route.** Each kind goes to the process that handles it: a known form to its form procedure, an invoice to the filing and review it already has, a member's request to its clock, a legal or government notice to the board with its dates. A route produces drafts, board items, tasks, and plans, never an outside act.

**Catalog and identify come first and stand alone.** A catalog that only says "this came in from a person who is an owner, carrying the owner-information form, copy NP27E-4RK9T for unit 123 Main St" already ends the mailbox search, feeds the response tracking, and needs no judgement call. Triage and routing are added on top, kind by kind, each as a rule row.

## Known forms, each with a known procedure

The user's point: a set of known forms implies a procedure for each. So a form is a row, not a special case:

| Field | Meaning | Example |
|---|---|---|
| `key` | the form (`FormKey`) | `owner-info` |
| `recognized by` | how an arrival is known to be this form: the marker's form code and campaigns, a PayHOA form id, a Google Form id, the printed title | marker code `NP`, PayHOA form 114542 |
| `arrives by` | the channels it may come through | PayHOA, email, mailed scan, Google Form |
| `procedure` | the SOP key that says what a person does with it (`jason sop KEY`) | `owner-info-cycle` |
| `handler` | the code that reads an arrival into an answer and plans its effect | the response inbox, then `member_preferences.match` and `owner_info.plan_writes` |
| `clocks` | the dates that run on it: return-by, the statutory day count, who sets it | answers by Oct 23; entered in PayHOA 30 days before the annual reports (4041(b)(1)) |
| `confirm` | who checks a reading, and whether a second person is needed | one person to confirm; apply is a person's yes |
| `complete` | what makes it done | recorded in PayHOA |

A new form type is a new row plus a procedure; an arrival that carries a form no row names goes to an "unknown form" lane for a person, never a guess. A check keeps the table honest: every row names a procedure that exists and a handler that is registered. The profile supplies the rows (the forms it uses, their markers and ids); the base class and the handlers are written once.

## The arrival

One record, broader than the responses design's: that design's `Arrival` becomes a form arrival, a catalog record with `identified` set.

```python
class Source(Enum): GMAIL = "gmail"; MAIL = "mail"; PAYHOA_FORM = "payhoa-form"; PAYHOA_REQUEST = "payhoa-request"; PAYHOA_CONVERSATION = "payhoa-conversation"; GOOGLE_FORM = "google-form"

@dataclass(frozen=True)
class Arrival:
    id: str                      # "<source>:<native id>"
    source: Source
    at: str                      # UTC ISO
    who: str                     # a display name; never a stored personal address
    summary: str                 # a subject, or a form's title
    attachments: tuple[Attachment, ...]       # name, type, size; no bytes
    identified: Identification | None         # the form step; see below
    triage: Triage | None                     # the triage step
    route: Route | None                       # the routing step
    state: State                              # new, seen, read, keyed, recorded, dismissed, superseded
    kept_at: str
```

```python
@dataclass(frozen=True)
class Identification:
    form: str                    # a known form's key, or "" when none
    campaign: str                # the marker's campaign ("NP27E"), or ""
    copy_for: str                # the owner and unit the copy was sent to, when a copy marker names them
    how: str                     # marker, payhoa-form-id, google-form-id, title, layout, subject
    sure: str                    # high, medium, low
    note: str                    # "the marker is a hint": a repaired or unreadable marker says so

@dataclass(frozen=True)
class Triage:
    party: PartyClass            # owner, former owner or buyer, board member, manager, vendor, authority, counsel, insurer or broker, title or escrow, bank or lender, utility, automated, unknown
    kind: MessageKind            # form-return, invoice, statement, member-request, question, complaint, legal-notice, government-notice, insurance, bank or escrow, proposal or bid, bounce, auto-reply, advertising, other
    urgency: str                 # from a stated date or a kind's clock
    clock: Clock | None          # what is due, by when, who set the day
    basis: tuple[str, ...]       # the rules that took it, in order, with what each matched
    sure: str
```

`party` and `kind` are enums; JSON stores the word and the loader makes it a symbol. A personal address is not stored (as in the responses design); the sender is matched to who the records knew them to be on that day.

## Identify: the form and the reference

The reference is what ties an arrival to a request and, for a copy that differs per owner, to an owner and a unit. It is a **hint, never a verdict** ([form-identifiers.md](form-identifiers.md)): the form is recognized from its own text and layout, and a marker that is missing, smudged, or fails its check changes only that.

In order, stopping at the first sure answer:
1. **A PayHOA submission** names its form: known by id (`payhoa_forms.record_for`). No reading needed.
2. **A Google Form response** is known by the form's id.
3. **An attachment's text layer** (a PDF's own text, or the mail service's `text.txt`) searched for a marker with `form_refs.parse`. A marker whose campaign is a known row is the form and the cycle. A copy marker also names the owner and unit it was sent to.
4. **The first page by layout** (`form_reader.identify_form`) when there is no readable marker, only for a PDF or image from an outside sender, once, cached.
5. **The subject** ("Re: Owner Information", "Form attached") as a weak lead, labeled low.

The step downloads an attachment only for a message from outside the association's domains that carries a PDF or image, once, into a private place (level P3), size-capped, and never for an arrival already identified by id. The identification keeps the copy's owner and unit **beside** the unit the person wrote and the owner the sender matches; where they differ it says so ([handoff-responses.md](console/handoff-responses.md) `ReferenceMatch`).

## Triage: who and what

Rules in order; the first that takes an arrival sets each field, and each rule's name is kept as the basis. A rule is a row, so a new decision is a new row (AGENTS.md).

**Party** (who it is from), cheapest and surest first:
1. The association's own addresses and groups (a message sent, or a forward).
2. An address PayHOA holds for a current owner (an owner on that day; a former owner after a conveyance).
3. The sender directory (counsel, the manager, vendors, insurers, title companies) by address, then domain.
4. The profile's authority domains and names: the fire marshal, the city and county agencies, the state ("an authority having jurisdiction"), by domain suffix and named office.
5. Headers: bulk (`List-Id`, `Precedence`), automatic (`Auto-Submitted`), a delivery-status report (`multipart/report`).
6. A local model reads the signature and subject for what no rule took; its answer is `low` and labeled.
7. Otherwise `unknown`: a person names it, and the naming is recorded as a proposed rule row.

**Kind** (what it is), by attachment kind and the message's own marks first:
- an identified known form is a **form return**, whatever else it looks like;
- an attachment classified as an invoice, a statement, an insurance document, a legal document, or a government notice (`classify_document`, `MailKind`) gives that kind;
- a delivery-status report is a **bounce**, tied to the notice ledger when its subject or message id names a notice jason's drafts sent;
- a subject's intent (`email_intents`): complaint, maintenance, information, billing, question;
- a stated date ("respond by", "hearing") becomes the **clock**, with the day's author marked (the sender's, the statute's, or the association's policy).

Kinds that need a person at once (legal notice, government notice, an insurer's cancellation, a records request) are marked urgent and carry any date found. Counsel's mail and anything touching a matter in executive session is held back from the open views as the executive items are (level P4/P3); nothing here quotes it.

## Route: the process that fits

A route is a row: kind (and party, where it matters) to a handler and a procedure. A handler's output is a draft, a board item, a task, a filing plan, or a plan of writes, each behind the approval and confirmation that already exist.

| Kind | Goes to | Existing parts |
|---|---|---|
| form return | its known form's handler and procedure | the response inbox, then `owner-info --apply` |
| member request | the request's clock and acknowledgment draft | `tasks/responses.py` (members' requests), `acknowledgment_draft` |
| invoice, statement | the vendor filing plan and invoice review; payment is the bill process | `tasks/vendor_files.py`, `invoice_review.py` |
| legal notice | a board item with its dates, the case file, and counsel's question; never an answer | `board_items`, `case_file`, `legal_cases` |
| government notice | the inspection or permit record and a task with the date | `inspections`, `permits`, `life_safety` |
| insurance | the policy review and renewals | `insurance` |
| bounce, auto-reply | the notice ledger's follow-up (a bounce), or nothing (an auto-reply) | `notice_ledger.FOLLOW_UPS` |
| question, complaint | the reply queue with the leads to the answer; a draft for a person to send | `reply_needed`, `intents` |
| proposal or bid | the bid record | the vendor files |
| advertising, other | none | |

A route can also open a **clock**: a request's response day, a notice's follow-up, a form's return-by. Clocks are registered as schedule occurrences (`jason schedule`) so "each occurrence done" covers them.

## Running it in production

- **Collect** is the scheduler's job: the existing cadences for `gmail`, `mail`, the PayHOA reads, and the Google Forms, each paused by its own sign-in failure and never faster than its floor ([scheduler-daemon-design.md](scheduler-daemon-design.md)).
- **The arrivals pass** (`jason arrivals --run`, a registry source) reads what those syncs left on disk, catalogs what is new, identifies, triages, routes, and stops. It makes no outside call except the one attachment download for the identify step, and it never sends, files, or completes anything.
- **Honest ages:** every view says when each source was last synced and when the pass last ran, so "nothing new" always carries its time.
- **Idempotent and resumable:** an arrival is kept once by id; a failure on one channel is reported and the others continue; a rule change re-triages unrouted arrivals only.
- **Corrections:** a person's correction of a party or kind is recorded with who and when, and becomes a proposed rule row (never silently learned). A scorecard (`extraction_scorecard`) counts hits and corrections per rule, so a bad rule is seen.

## Interfaces

- **CLI:** `jason arrivals` (no option: what is new, by kind, with the ages), `--run`, `--list` with `--source`, `--kind`, `--party`, `--form`, `--state`, `--show ID`, `--correct ID --party X --kind Y --by NAME --why`, `--unknown` (the lane for a person). `jason responses` stays as the form handler's view of its arrivals.
- **MCP** (disk only, board profile): `arrivals` (the catalog by lane, with ages), `arrival` (one, with its identification, triage basis, route, and acts), `unknown_arrivals`. Each carries its caveats; a classification is a reading with its basis, not a fact.
- **Console:** the Inbox (`#/inbox`) becomes the arrivals lanes (act now, forms, requests, invoices, notices, questions, unknown), and `#/responses` is the forms lane in detail. The design agent's spec follows once the data shapes are built.

## What must not change

- Cataloging and identifying write nothing to Gmail, PayHOA, Drive, or the mail service, and send nothing.
- A classification is a reading with its basis; a person corrects it; a miss stays a miss.
- A route produces drafts, board items, tasks, and plans; every outside act stays a person's `--yes`.
- No body, no personal address, and no privileged or executive-session content is stored or shown outside the levels that allow it.
- The code names no association: the sender directory, the authority domains, the forms' markers, and the clocks are the profile's rows.

## Build order

1. **The responses core** (building now): the form arrival, its reading and confirmation, the keyed answers. It is the first handler.
2. **Catalog and identify**, sources Gmail, the mail service, PayHOA forms and requests, and Google Forms, with the known-forms table: the cheap step on its own, and the `Arrival` widened from the form arrival. `jason arrivals`, its MCP tools, and the cadence.
3. **Triage by rule** from the classifiers that exist (party, kind, clock), the correction path and the scorecard, then the local model for the remainder.
4. **Routes** kind by kind, each with its procedure step and lesson, starting with the ones that already have a handler (member requests, invoices, bounces).
5. **Console** (the Inbox as lanes) and the design agent's spec.
6. The conversation catalog ([conversations-design.md](conversations-design.md)) feeds the triage once built: a reply is a continuation, a forward is an assignment.

## Open decisions

- Whether the local model may classify an arrival no rule takes, and at what cost to the GPU lock; the proposal is yes, labeled `low`, never the sole basis for a route that opens a clock.
- The authority domains and named offices are the profile's to list; the first list is the board's to confirm.
- Whether counsel's mail is cataloged by sender and date only, with no subject, as a rule for privileged communications.
- Retention: how long an attachment kept for the identify step stays on disk once the arrival is recorded or dismissed.
