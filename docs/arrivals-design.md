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
| `authority` | the law it serves, as the canonical citation the rest of jason uses (`jason.community.references`): the process key | `CIV 4041` |
| `procedure` | the SOP key that says what a person does with it (`jason sop KEY`) | `owner-info-cycle` |
| `handler` | the code that reads an arrival into an answer and plans its effect: fixed by `authority` for a legal form, chosen at generation for a general one, and kept in the campaign record | the response inbox, then `member_preferences.match` and `owner_info.plan_writes` |
| `clocks` | the dates that run on it: return-by, the statutory day count, who sets it | answers by Oct 23; entered in PayHOA 30 days before the annual reports (4041(b)(1)) |
| `confirm` | who checks a reading, and whether a second person is needed | one person to confirm; apply is a person's yes |
| `complete` | what makes it done | recorded in PayHOA |

A new form type is a new row plus a procedure; an arrival that carries a form no row names goes to an "unknown form" lane for a person, never a guess. A check keeps the table honest: every row names a procedure that exists and a handler that is registered. The profile supplies the rows (the forms it uses, their markers and ids); the base class and the handlers are written once.

## The citation is the process key; the reference is the copy key

Two identifiers do two jobs, and neither replaces the other:

- **The citation names the process.** `CIV 4041` is the owner information request. The same canonical string already keys the notice requirements (`jason notices`), the follow-up rules (`FollowUp.authority`: "CIV 4041(e), 4040(a)(2)"), the clocks, the conflicts, and the statutes shelf. So a known form's `authority` is the join: from `CIV 4041`, a person or a tool reaches the form, its procedure (`jason sop`), the notice requirement and its delivery rules, the clocks that run, and the board items about it. `Procedure` rows gain an `authority` (a tuple of citations) so `jason sop --authority "CIV 4041"` finds them. Other forms follow the same way: a records request by `CIV 5210`, internal dispute resolution by its section, and so on; a form for which the law gives no section takes the governing document's section it rests on.
- **The reference names the copy.** `NP27E-4RK9T-C7` is one copy of that form sent to one owner for one unit in one cycle ([form-identifiers.md](form-identifiers.md)). It is exact where the citation is general.

A citation is a **lead, not proof**: many documents cite 4041 (the annual policy statement, a reply that quotes the law), so a text that cites a form's authority is a candidate for that process, to be confirmed by the reference, the title and layout, or a person. It is most useful where there is no reference: a retyped or photocopied form still prints "Civil Code §4041" and its title; an email that quotes a section is about that process; and a returned letter that cites a section routes to the procedure that section keys. The order of strength is below.

## The handler is chosen when the form is made

jason sends only forms it has a procedure to process, so the handler is not found afterwards; it is **decided at generation and delivery and kept in the reference catalog**. Two families:

| Family | Chosen by | Examples |
|---|---|---|
| **A process handler,** tied to a legal procedure | the form's `authority`: `CIV 4041` has exactly one form-return handler, registered to it (below) | owner information (4041), a records request (5210), internal dispute resolution |
| **A general handler,** for a generic form tied to no law (`authority` is `None`) | a person, when the form is generated, from a short fixed list | collect only; append to a Google Sheet (a register); one board item or task per response; set PayHOA tags from the answers; draft a forward to a person |

- **The catalog row.** A **campaign** record is made when a form is generated (`data/forms/campaigns.json`, beside `references.json`): the campaign code (`NP27E`), the form, the `authority` or `None`, the **handler key and its options** (the sheet and tab, the tag map, the person to forward to), the cycle dates, and who chose it and when. Every copy's reference in `references.json` points at its campaign, so an arrival with a reference is routed to its handler by one lookup, with no guessing and no "no handler" case.
- **The invariant: a reference exists only if a handler does.** The generators (`jason forms --pdf`, `--payhoa`, `broadcast`, `owner-info --email-batch` and `--mail-batch`, the packet) refuse to make a marker for a form whose handler is not chosen and registered. A form with an `authority` takes its registered process handler; a form with none must name a general handler. There is no way to send a form nobody can process.
- **A limited, fixed set.** General handlers are a short registry written in code, each with a typed options record, a dry-run plan, and the approval and confirmation every outside write already needs. A profile cannot add a handler by data; adding one is development, which is what keeps the list safe to choose from. Form **templates** (a survey, a sign-up, an RSVP, a volunteer list, a contact update) pair a layout with a default handler, and a template may carry its own custom handler.
- **Aggregating into PayHOA or a sheet.** A Google Sheet is a register the association already keeps ([registers.md](registers.md)): each confirmed response appends a row, written only after a person confirms, as an approved plan. Aggregating into a **PayHOA form** is different: PayHOA takes a submission from the signed-in owner, and jason never creates or edits an owner's submission (AGENTS.md), so the proposal is the nearest safe equivalents (tags from the answers, a request comment, a register row). Whether PayHOA offers an administrator a way to enter a submission for an owner is unverified; if it does, it is the board's decision, not a default.
- **What stays outside.** A response that arrives with no reference (a retyped or photocopied form, a form some other party sent) is not from a campaign; a person attaches it to one, the choice is recorded, and it is then handled like any other. A reference that is not in the catalog is "not ours" and goes to the unknown lane.

## Handlers are registered to citations; no handler is a finding

The routing question becomes one lookup: **is there a registered handler for this citation?** A handler declares the law it serves where it is written, so the code and the process it implements cannot drift apart.

```python
from jason.handlers import handler, Role

@handler("CIV 4041", role=Role.FORM_RETURN, form="owner-info", procedure="owner-info-cycle",
         channels=(Channel.PAYHOA, Channel.GMAIL, Channel.MAIL, Channel.FORMS))
class OwnerInformationReturns:
    def accepts(self, arrival): ...      # is this arrival one of mine? (the identification, the form key)
    def read(self, arrival): ...         # evidence: a reading, never an answer
    def plan(self, keyed): ...           # what it would change; a plan, not a write

@handler("CIV 4041(e)", "CIV 4040(a)(2)", role=Role.BOUNCE, procedure="notice-delivery")
class UndeliverableNotices: ...          # an email that bounced: resend by mail, ask for a working address

@handler("CIV 5210", role=Role.REQUEST, procedure="records-request") 
class RecordsRequests: ...
```

- **Registration.** `@handler(*citations, role=..., procedure=..., ...)` adds a `Handler` row to the registry as the module is imported. The set of handler modules is an explicit list in `jason.handlers` (importing jason loads no profile; handlers are general code, and a profile supplies only the data they read: which forms, markers, and ids). The citations are the canonical strings of `jason.community.references` (`CIV 4041`, `CIV 4041(e)`), and a handler for a section covers its subdivisions: a lookup for `CIV 4041(e)` finds a handler for `CIV 4041(e)` first, then `CIV 4041`.
- **Roles.** Several handlers may serve one section, each for a different job: a form return, a bounce or undeliverable notice, a member's request, a notice's delivery, a legal or government notice. The role is part of the route, so `CIV 4041` with a bounce goes to the bounce handler and with a returned form to the form handler.
- **Lookup.** An arrival carries candidate citations: its identified form's `authority`, a statute its text cites (the references grammar, `CIV 4041`), a notice it answers (the ledger's `FollowUp.authority`), a clock's authority. The router asks the registry for a handler of the arrival's role under each, and the first whose `accepts` says yes takes it. The arrival keeps which handler took it and why.
- **Kept honest by tests.** Every handler's citations parse and are on the statutes shelf (`citation_gaps`); its `procedure` exists and lists it; every known form's `authority` has a registered form-return handler; no two handlers claim the same citation and role.
- **Existing code is registered, not rewritten.** The owner-information returns (4041), the notice delivery follow-ups (4041(e), 4040, 4050), the members' request clocks (5210 and the response standard), the election, rule-change, and hearing notices, and the annual disclosures already carry their authority in rule rows (`NoticeRule.authority`, `FollowUp.authority`, the duties catalog). Each gets a thin `@handler` that points at it.

**No handler is a finding, not an error.** For a form jason made, a missing handler is caught earlier, at generation: the form is not made, and the refusal names the missing handler for the admin. What remains is the **unsolicited**: a message that is not a form return and whose kind has no route, a legal or government notice, a request of a kind with no handler, or a form from some other party. When such an arrival's role and citations have no registered handler, or no citation can be named at all, it goes to the **needs a person** lane (the manager handles it by hand; nothing is dropped, and nothing is guessed), and jason records a **gap**:

| Field | |
|---|---|
| `key` | the citation and role, or the kind and the party when no citation was found ("CIV 5915 / request", "government notice / authority") |
| `seen` | how many arrivals, first and last date, and which channels |
| `examples` | arrival ids only (never a subject, a sender, or any content) |
| `handled by hand` | when a person marks an arrival done, what they did, in their own words and by name: the first draft of the procedure |
| `state` | open, acknowledged by the admin, in development, built (closed by a handler registering for it) |

Gaps are brought to the **administrator**, who is the person that can develop a handler:
- the Status screen's "needs development" band (and `jason handlers --gaps`, and an administrator-only MCP tool), listing each gap with its count and age, most arrivals first;
- the dock for an administrator shows the count; nothing is shown about the content;
- a gap that recurs becomes a candidate lesson and, once a person acknowledges it, a development item with the steps the manager took by hand;
- a gap closes by itself when a handler registers for its key, and the arrivals waiting on it are routed on the next pass (the registry is the only thing that changes).

The same list is the **coverage report** the project can read the other way: the citations the association's procedures, notice catalog, and documents' duties name that no handler serves (`jason handlers --coverage`) is a map of what jason does not yet do, ranked by how often arrivals of that kind have come in.

## Recognition is the crux

With the handler fixed by the campaign, the whole problem is one function: **given a message or an attachment, is it a response to a form we sent, and which copy?** `recognize(message, attachments) -> Recognition` is the first thing built and the thing most worth testing, because every later step trusts it.

A sent copy carries its reference in several places by design (`fillable.stamp_reference`, `delivery_engines`, `owner_send`), so there are many chances to read it. In order of cost, and so of how early they are tried:

| Rung | Signal | Where the copy put it | Cost |
|---|---|---|---|
| 1 | `[Ref NP27E-…]` in the **subject** (a reply keeps it) or a quoted body | the email's subject (`subject_for(reference, unit)`) and message | headers only |
| 2 | the same in an attachment's **text layer** | the PDF's printed "Ref" at each page's top right | one download; no OCR |
| 3 | the hidden `reference` **field** of a returned fillable PDF | `fillable.REFERENCE_FIELD` | one download; no OCR |
| 4 | the **bar mark** and printed Ref on a scan or photo | the bars at the top left (`form_marks`) and the printed marker, read after OCR | one download; OCR |
| 5 | the **form by layout** and printed title, when no marker survives | `form_reader.identify_form` | one download; OCR; once, cached |
| 6 | the **cited authority** and title in the text (`CIV 4041`) | the form's own header | free once the text is read |
| 7 | **who sent it**: an owner who was sent a copy and has not answered, with a PDF or image, in the window | the sent-copy catalog and the ledger | free |

Rungs 1 to 4 end in the catalog (`form_references.lookup`) and so in a copy, owner, unit, and cycle: **recognized**. Rungs 5 and 6 give a form and a process but no copy: a **candidate**, which a person attaches to a campaign. Rung 7 alone is never enough; it only decides which attachments are worth the download. Nothing recognized or unrecognized is ever final: the result keeps the rung that decided it, and a person's correction is recorded.

The result has three outcomes, and the third is as important as the first two:
- **Recognized:** a copy of a form we sent, with the owner and unit as sent.
- **Candidate:** looks like one of our forms; a person decides.
- **Not ours:** an invoice, the governing documents, an unrelated PDF, a form from another party. It leaves this path and is triaged as any other message.

**It is measured, not trusted.** The corpus is built with the tools that exist (`form_scans.simulate` and `jason form-fuzz`: scans at several resolutions, turns, blur, JPEG, and phone-like skew), with the negatives a mailbox really holds (invoices, certificates, minutes, other forms, blank pages). A test fixes the floor: every simulated return that keeps its marker is recognized, none of the negatives is, and a marker one character off is repaired only to the one sent marker it is near. In production a person's corrections feed a scorecard of misses and false hits per rung, so a rung that misleads is seen and its rule changed (never silently learned).

**The cost is bounded.** Rung 1 reads headers for every message. A download happens only for a message from outside the association's domains that carries a PDF or image and passes rung 7, once, size-capped, and never for an arrival that rungs 1 to 3 already settled.

## The sent-copy catalog: the reference is already known

Every copy jason sends is recorded when it goes: `data/forms/references.json`, written by `jason.tasks.form_references.record` (ids and hashes, never an address). Each entry is the copy's marker with its form, year, channel, unit, membership, when it was first and last sent, the file, and the fingerprints of what was filled in. At the time of writing it holds a marker for every emailed owner copy. A mailed letter's marker names the campaign only (every copy is the same), so the unit comes from the address written on the page.

That catalog does two jobs the arrivals layer must use:

1. **Identify an arrival exactly.** A reference found in an arrival's subject, quoted reply, or attachment text is looked up (`form_references.lookup`, which also takes a marker one character off to the one sent marker it is near). A hit gives the form, the cycle, and **the owner and unit the copy was sent to**, which is compared with the unit written on the page and the owner the sender matches. This is the strongest identification there is, and it needs no model.
2. **Say who has not answered.** The sent copies are the **asked** side: every reference sent, to whom, when. Subtract the owners with an arrival or an answer, and what remains is who was asked and has not responded; owners with no reference and no letter batch are who was never asked. This is the outstanding list the cycle board shows, with the deliveries' outcomes from the notice ledger beside it.

The response inbox as first built checks a marker's campaign only; it does not yet look the copy up. Using the catalog there is the first change to make ([Build order](#build-order), step 1b).

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
3. **A reference in the text,** looked up in the sent-copy catalog (`form_references.lookup`): the subject, a quoted reply's body (read only for a candidate message), an attachment's text layer or the mail service's `text.txt`. A hit names the copy: form, cycle, owner, and unit as sent. A marker that matches no sent copy is kept as a finding ("a reference we did not send").
4. **The first page by layout** (`form_reader.identify_form`) when there is no readable marker, only for a PDF or image from an outside sender, once, cached.
5. **The printed title and the cited authority:** the page's text names a known form's title or cites its authority (`CIV 4041`). A candidate for that process, labeled medium; it needs a reference, a layout match, or a person to be sure.
6. **The subject** ("Re: Owner Information", "Form attached") as a weak lead, labeled low.

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

1. **The responses core** (built; the command and MCP tools follow): the form arrival, its reading and confirmation, the keyed answers. It is the first handler.
   - **1a.** The campaign record and the generation gate: `data/forms/campaigns.json` (handler key, options, `authority` or `None`, who chose it), every reference pointing at its campaign, and the generators refusing a marker with no registered handler. The first two general handlers: collect only, and the Google Sheet register.
   - **1b.** Use the sent-copy catalog in the core: look a found reference up (`form_references.lookup`), keep the owner and unit as sent on the reading, compare them with the unit written and the sender, and read a candidate message's body for a quoted reference. Add `authority` to the form row and to `Procedure`. Then `jason responses --outstanding`: the asked-and-not-answered list, from the catalog less the arrivals.
2. **Catalog and identify**, sources Gmail, the mail service, PayHOA forms and requests, and Google Forms, with the known-forms table: the cheap step on its own, and the `Arrival` widened from the form arrival. `jason arrivals`, its MCP tools, and the cadence.
3. **Triage by rule** from the classifiers that exist (party, kind, clock), the correction path and the scorecard, then the local model for the remainder.
4. **The handler registry** (`jason.handlers`: `@handler`, `Role`, the lookup by citation and role, the gap record, `jason handlers --gaps --coverage`), then **routes** kind by kind, each registered to its citation with its procedure step and lesson, starting with the ones that already have code (owner-information returns, the notice follow-ups, member requests, invoices, bounces).
5. **Console** (the Inbox as lanes) and the design agent's spec.
6. The conversation catalog ([conversations-design.md](conversations-design.md)) feeds the triage once built: a reply is a continuation, a forward is an assignment.

## Open decisions

- Whether the local model may classify an arrival no rule takes, and at what cost to the GPU lock; the proposal is yes, labeled `low`, never the sole basis for a route that opens a clock.
- The authority domains and named offices are the profile's to list; the first list is the board's to confirm.
- Whether counsel's mail is cataloged by sender and date only, with no subject, as a rule for privileged communications.
- Retention: how long an attachment kept for the identify step stays on disk once the arrival is recorded or dismissed.
