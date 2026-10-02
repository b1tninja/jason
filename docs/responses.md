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
  - The form decides the rest.
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
```

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
  - A thread whose subject says nothing is left to `jason replies`.
- `--no-email` leaves these out.

## Limits

- **Letters:** requests made by letter (`jason mail`) are not yet in the handler's clocks.
- **Email kinds come from subjects:** a vague subject is a miss, and a precise one can still mislead. Read the thread before acting.
- **A proposed clock is a target,** not a rule, until the board adopts it.
- **Not built yet:** acknowledgment drafts. A first comment, drafted for a person to send, is the natural next step (`request_actions` writes comments).
