# Responding to members: each request's kind, clock, and owner

Members ask the association for things: records, approvals, repairs, answers. Many of those requests start a clock the law sets. The governing documents set others. Where both are silent, the board should set one ("where the law is silent, write it down"). The response handler says, for every request:
- what kind it is;
- when the answer is due;
- whose it is;
- whether it is late.

It never approves, denies, or assigns a request (AGENTS.md, Boundaries).

`jason sop respond` is the procedure.

## The records

`jason.community.responses`; the profile's rows are `Community.response_rules()` and `Community.request_kind_rules()`.

- **`ResponseKind`:** records, resale documents, architectural, solar, EV charger, rental, variance, payment plan, hearing request, internal dispute resolution, ADR, maintenance, complaint, question, other.
- **`KindRule`:** a request on a form, or with words matching a pattern, is a kind. The rules run in order, the profile's first, then jason's.
  - The statute's kinds are recognized by their words: "solar", "inspect copies of the minutes", "payment plan".
  - The documents a sale needs are recognized by their own names: 4525, 4528, "resale disclosure", "demand statement". Mentioning escrow is not enough.
  - A copy of the governing documents ("copy of the rules") is a records request; a notice of intent to rent is a rental application; asking permission to change the unit ("permission to paint") is an architectural application.
  - The architectural and maintenance forms decide their kinds.
  - On any other form, or in an email subject:
    - conduct reported is a complaint ("dog waste on the walkway", "vandalism"), but an owner asking not to be cited is not, and neither is a reply to the association's own violation report;
    - something to fix or tend is a maintenance request ("leak", "rusty", "the light is out", "dead tree"), but asking whose job it is ("responsible", "liable") is a question.
  - The general form is a question, and so is a subject that asks one.
  - A miss is `OTHER`.
- **`ResponseRule`:** the clock for one kind.
  - **`STATUTE`:** the notice catalog's timing, counted from the request:

    | Request | Clock | Statute |
    |---|---|---|
    | Records, current year | 10 business days | CIV 5210 |
    | Resale documents | 10 days | CIV 4530 |
    | Solar decision | 45 days | CIV 714 |
    | EV charger decision | 60 days | CIV 4745 |
    | Payment plan meeting | 45 days from the postmark | CIV 5665 |
    | Request for resolution | 30 days | CIV 5935 |

  - **`DOCUMENTS`:** a clause of the governing documents (a rental application within 30 days, say).
  - **`POLICY`:** a clock jason proposes where the law and the documents are silent, for the board to adopt.
  - Each rule also gives the schedule assignment that owns the kind (`jason schedule`), a first step, and, under a proposed policy, an acknowledgment within so many business days.

## What it measures

`jason respond` reads the stored PayHOA requests (`jason sync-catalog` refreshes them). For each request:
- **Received:** the request's creation, in the association's time zone.
- **Due:** by the rule's clock. Business days skip weekends but not holidays, so a business-day deadline is the earliest it can fall.
- **Responded:** the first admin comment the owner can see, or the request's closing if that came first.
- **Closed:** kept apart from the response. A maintenance request is answered when the owner is told the plan, and closed when the work is done.
- **Standing:** answered on time, answered late, overdue, due soon (within five days), or open.

```bash
jason respond                       # the open requests, the most urgent first, with each one's next step
jason respond --all                 # also the answered ones, and how many were on time, by kind
jason respond --kind "records request"
jason respond --sources             # with the leads to where each answer is written
jason respond --measure             # how well the kinds are read, against the hand-labelled gold set
```

## PayHOA's own fields

A stored request carries what a person set in PayHOA and what PayHOA itself made of it (`PAYHOA_FIELDS`): a due date, tags, an assignee, an assigned vendor, approvals, and PayHOA's AI analysis. `jason respond` shows what they hold under each request:
- **A due date set in PayHOA** is shown beside jason's clock, and flagged when it is earlier. It does not change the standing: the clock is the law's, the documents', or the proposed policy's.
- **Tags** are read by the same words rows. A tag that names a kind is marked as agreeing with jason's kind or as reading as another. It is a hint for the person; it never reclassifies.
- **PayHOA's AI analysis** is at most a lead. A kind it reads as is shown beside jason's, and jason's kind stands.
- **An assignee or a vendor** set in PayHOA is named. jason itself never assigns.

What a profile's requests actually held is in its own docs (for this profile, [mystique/docs/responses.md](../mystique/docs/responses.md)).

## Where the answer is written

`--sources` adds leads to each request (`jason.tasks.response_sources`). Each line says it is a lead.
- **By topic** (`intents.answer_sources`):
  - the governing documents' passages that match the topic's query and the request's words (BM25, the same search as `passage_search`);
  - the library's documents of the kinds that speak to the topic.
- **By name:** library files whose names share at least two uncommon words with the request (one, if the name has only one). Words in more than 2% of the names, the unit addresses' words, and the association's name do not count.
- **Precedents,** for a complaint or a hearing request: the PayHOA violations on the same conduct. A complaint that names no topic is read as a neighbor matter.
- **PayHOA's AI analysis,** when PayHOA holds one.

A passage is text to read beside the request, not a ruling. A precedent shows how the association handled that conduct before; a new complaint still needs its own facts, notice, and hearing. `--json --sources` gives the same leads as data.

## Acknowledgments

`jason respond --draft ID` (or `all`) drafts the first answer to an open request that no one has acknowledged:
- what was received and when;
- a date only where the law or the documents set one: a proposed policy's day is the board's target, not a promise.

A person sends it:
- **A PayHOA request** gets a comment: `jason request-comment ID "<the text>"`.
- **An email request** gets a Gmail draft reply in its own thread: `jason respond --draft email:ID --gmail`.
  - Without `--yes` it is a dry run: the thread, the subject ("Re:" once), and the text.
  - `--yes` saves the draft (`GmailDrafts`, which has no send method). It reads the thread's last message in for its Message-ID, so Gmail files the reply in the thread.
  - The recipient is that message's writer: the original sender a Google Group rewrote (X-Original-From), else its Reply-To, else its From. `--to ADDRESS` names another. The address is read when the draft is made and never stored.
  - Each draft's id is recorded in `data/responses/gmail-drafts.json`, and a request already drafted is not drafted again.
  - The draft waits in Gmail. A person reads it, edits it, and sends it there.

## Requests made by email

A records request by email starts the same clock as one on a PayHOA form. `jason respond` also reads the owners' threads (`email_requests`).

- **Which threads count:**
  - between the association and an owner, with no business on it;
  - not already joined to a PayHOA request (`request_links`);
  - whose subject names a kind, or a maintenance topic.
- **The clock** runs from the first message in. The response is the first message out after it.
- **Classification:** email is read by its headers, so a kind comes from the subject alone.
  - A mention is not an application. "Solar question" is not a solar application, which needs the words of installing or asking.
  - A reply to the association's own courtesy notice is not a complaint (`KindRule.exclude`).
  - A repair or a conduct named in the association's own word is not a request (`ANNOUNCEMENT`): a notice, a schedule, an inspection, a survey, an update, a proposal, a meeting, a new vendor, "Your ...", or a reply to a violation. This never overrides a kind the subject names outright: a notice of intent to rent is still a rental application.
  - A subject that names no kind is a maintenance request when its topic is maintenance and repairs, landscaping, or pests (`MAINTENANCE_TOPICS`, the topics' own values). A contract, an expense, a quote, an invoice, or whose responsibility it is makes it business or a question instead. Utilities and bins are left out: an owner's thread about the meter reader or the bins was rarely a repair.
  - Who started the thread is not read. The first stored message is often the association's answer to a call, or to mail synced earlier.
  - A question, or a subject that says nothing, is left to `jason replies`.
- `--no-email` leaves these out.

## How well the kinds are read

`jason respond --measure` scores `classify` against a hand-labelled gold set, `data/responses/kind-gold.json` (`jason.tasks.request_kinds`). The gold set is private: it carries the requests' titles and the threads' subjects.
- **What is labelled:** each PayHOA request by its title and message, and each owner's email thread that could be a request by its subject alone, the same text jason reads.
- **The labels:**
  - "question" is the catch-all for a request the association answers that no other kind covers: a parking permit, an account or billing matter, an insurance certificate.
  - "other" is a subject that says nothing, or a thread that is not a member's request.
- **The scores:** precision and recall per kind, for each source and for both together, and every miss with the rule that decided it.

A profile's measurements are in its own docs (for this profile, [mystique/docs/responses.md](../mystique/docs/responses.md)).

The rules were fixed against this same set, so the "after" column is an upper bound until new requests are labelled and measured. Label new requests as they come, and measure again before changing a rule.

Most email misses that remain are questions read as "other", which costs nothing: both are left to `jason replies`. The rest are subjects naming a vendor's notice or a repair project, and complaints whose subjects name no conduct.

## Limits

- **Letters:** none of the association's scanned letters through October 2026 was a request with a clock.
  - The title companies' letters were closing notices with a check enclosed: a new owner to record (`new_owners`), and a check to match to its deposit (`mail_checks`).
  - The owners' letters were statements.
  - A request that does arrive by letter (a payment plan request, whose clock runs from its postmark under 5665) is read from `jason mail` by a person, for now.
- **Email kinds come from subjects:** a vague subject is a miss, and a precise one can still mislead. Read the thread before acting.
- **A proposed clock is a target,** not a rule, until the board adopts it.
- **Insurance documents are not read as records requests.** A request for a certificate or a copy of the master policy is labelled a question. Whether it is an association record under Civil Code 5200 (which would start the 10-business-day clock of 5210) is for counsel.
- **Old email requests:** a thread that names a repair and never got an email answer shows as overdue, however old it is. It may have been answered by phone or in person. Close it by answering in the thread, or read it and decide.
