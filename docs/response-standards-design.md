# Response standards: what members can expect, and how the association measures it

A design spec for a response standard: how quickly the association acknowledges and answers each kind of member request. The pieces:
- the board adopts it as part of the community's profile;
- jason publishes it to members;
- jason applies it the same way to every channel (a PayHOA request, an email, a letter);
- jason measures it: average and median response time, on-time rates, and what is overdue now.

It follows AGENTS.md's axiom "Where the law is silent, write it down". jason proposes the standard, the board adopts it, and jason applies it the same way every time and records each use. A written standard applied consistently is also the board's best evidence of good faith. It builds on what exists:
- `ResponseRule` (`jason.community.responses`);
- `jason respond`;
- the duty schedule's adoption fields (`jason.community.schedule`);
- the conversation catalog and its handoffs ([conversations-design.md](conversations-design.md)).

## What exists today

- **Kinds and clocks.** `ResponseKind` classifies a request (records, resale, architectural, solar, EV charger, rental, variance, payment plan, hearing request, IDR, ADR, maintenance, complaint, question, other).
  - Each kind has a `ResponseRule`: its clock and the clock's source (`ClockSource.STATUTE`, `DOCUMENTS`, or `POLICY`, the last being "a clock for the board to adopt"), the owner (a schedule assignment), the first step, and an acknowledgment target (`acknowledge_days`).
  - jason's own rows are the statute's clocks: records (CIV 5210), resale (4530), solar (714), EV chargers (4745), payment plans (5665), ADR (5935). A profile's rows (`Community.response_rules()`) add the documents' clocks and the proposed policies, and replace jason's for a kind.
- **`jason respond`** lists open PayHOA requests with their kind, clock, owner, and standing. `--all` counts on-time and late answers by kind.
- **Adoption.** The duty schedule already records `adoption` (proposed or adopted) and `adopted` (the minutes or resolution).
- **Business days.** These skip weekends but not holidays (`notices.py`, `records_requests.add_business_days`), so a business-day deadline is the earliest it can fall.

What is missing:
- **Adoption** recorded on a response rule.
- **A member-facing statement** of the standard.
- **Email and letters** under the same clocks.
- **Pauses**, while the association waits on the member.
- **Metrics** beyond an on-time count.
- **A screen and a board report.**

## The standard

### One row per kind

`ResponseRule` gains the fields a standard needs. Existing rows keep working: every new field has a default.

```python
@dataclass(frozen=True)
class ResponseRule:
    kind: ResponseKind
    source: ClockSource                  # STATUTE | DOCUMENTS | POLICY
    notice: str = ""                     # STATUTE: the notice catalog key whose timing is the clock
    days: int = 0                        # the answer clock, in days
    business_days: bool = False
    authority: str = ""                  # the statute, the documents' section, or the adopted policy's key
    assignment: str = ""                 # the schedule's assignment that owns it
    first_step: str = ""
    acknowledge_days: int = 0            # the acknowledgment target (0: none)
    acknowledge_business_days: bool = True
    adoption: Adoption = Adoption.PROPOSED   # the schedule's enum; a STATUTE row is ADOPTED by law
    adopted: str = ""                    # the minutes or resolution ("board minutes 2026-11-18, item 6")
    pauses: tuple[PauseReason, ...] = () # what stops a POLICY clock (never a STATUTE clock unless the statute says)
    member_words: str = ""               # how the published standard says it to members (generated if empty)
    note: str = ""
```

There is one general row for any kind without its own: `ResponseKind.OTHER`, the general standard, e.g. "acknowledged within 2 business days, answered within 10".

### Where each clock comes from, and what can't be changed

Each layer is bounded by the one above it (`authority_order.Tier`; AGENTS.md, "Follow what is written"):
1. **The statute.** A statute's clock binds. A policy can promise faster, never slower.
2. **The governing documents.** Their clock binds the same way, unless it conflicts with a statute. Then it yields to the extent of the conflict (CIV 4205), and the conflict is a `Conflict` row.
3. **The board's policy.** It fills what the law and the documents leave open: an acknowledgment target, a maintenance request, a question, a complaint.

A proposed row that would set a policy clock slower than a statute's or the documents' clock for the same kind is refused when the profile loads, with the reason. The refusal recites the clause.

### Pauses

A clock can stop while the association waits on the member. For example: a records request whose scope is unclear, or an architectural application missing a plan.
- Only a `POLICY` clock pauses, and only for the reasons its row lists.
- A `STATUTE` or `DOCUMENTS` clock pauses only where its own words say so. The row then cites them, and they are recited, not paraphrased.
- `PauseReason` is `waiting_on_member` (information the association asked for) or `member_asked_to_wait`.
- A pause is a person's record ("Waiting on the owner for the plan, from Oct 3") or a PayHOA status the profile maps to one, never jason's guess.
- A pause ends when the member writes back on that conversation or request. The days paused are added to the due date, and the record keeps both dates.

### Exclusions

These are not member requests and are not measured:
- automatic mail (the conversation catalog's `auto`);
- notices and bulk mail;
- the association's internal mail;
- vendors' invoices;
- spam.

A conversation that is not a request (a thank-you, an FYI) closes as `not_a_request`, by a person's word or the classifier's `OTHER` with no question in it. That closure is shown and counted apart.

## Adopting it

jason proposes. The board adopts. The steps:

1. **The proposal.** `jason respond --standards` prints the full standard:
   - each kind's clock, with its source;
   - the statute's or documents' words, recited from disk (`jason cite`);
   - the proposed policy clocks, marked proposed;
   - the member-facing text.

   `--board-item` drafts it as a board item for the next agenda (`jason board`, behind `--yes`), with the decision brief's options: adopt as proposed, adopt with changes, or keep it internal only.
2. **Whether it needs member notice.** A standard that sets procedures on a subject Civil Code 4355(a) lists is a rule change with notice to members (4360). Procedures for reviewing a proposed physical change are the likely one for architectural applications; this is a reading for counsel to confirm. Adopt it through `jason rule-change`. The rest is a board policy adopted at an open meeting. The brief recites 4355(a) and labels the reading.
3. **The record.** The adoption is the board's vote at a meeting. A person records the motion and the roll call on the Decisions screen (`data/board/decisions.json`), never a click standing in for the board. Each adopted row's `adoption` and `adopted` are set in the profile from the decision. Until then every policy row is `PROPOSED`. A proposed clock is measured internally, labeled proposed, and never published.
4. **Changes** go the same way, and the old version is kept, so a request is measured against the standard in force on the day it arrived.

## Publishing it

A base template, `response-standards`, written once (AGENTS.md, "Templates are written once"), renders the adopted rows in the members' words:
- what the association acknowledges and answers, and how fast;
- where the law sets the time, the law's words and its citation;
- what pauses a clock;
- how to ask (the channels the profile lists);
- what counts as a request.

It goes:
- on the owners' page (`#/owner`);
- in the welcome letter;
- on the association's website (the profile's `SitePage`);
- with the annual policy statement as an attachment, if the board chooses. The statement's own required contents (5310) are not changed.

Only adopted rows are published. A proposed one never is. The page names the adoption and its date.

## One request, any channel

Every channel becomes one record, the `Request` that `jason respond` already handles. The source is new:

| Channel | Received | Acknowledged | Answered | Kind |
|---|---|---|---|---|
| PayHOA request | its creation | the first comment to the owner, or a status the profile maps (`acknowledged`) | its completion status, or the board's decision comment | `classify(form, text)`, as today |
| Email (a conversation) | the first outside message's time | the first association message to the asker (not an automatic one, not a forward) | see below | `classify("", subject + the first message's subject line)` and `email_intents` |
| Letter (mail triage) | the scan's received date | the first association letter or email to the sender, linked by a person | a person's record | the triage kind, mapped to a `ResponseKind` |
| In person, by phone | a person's record (`jason respond --log`) | the same | the same | chosen by the person |

**Answered, for email.** An email exchange has no completion status, so:
1. **A person's word.** "Answered" on the conversation (named, logged), the same as recording a handoff's outcome. This wins.
2. **Otherwise jason's reading,** labeled as jason's: answered when the last non-automatic message is the association's to the asker, and nothing new arrived from the asker for `quiet_days` (profile, default 14). The answer's time is that message's time.

**One request, not two.** An email about a PayHOA request (`request_links`) is the same request: the earlier receipt and the first acknowledgment across both channels count.

**Handoffs inside a request.** An assignment to counsel or a vendor is the association's own work. It does not pause the member's clock (a forward is never an answer). It is measured separately: how long assignees take, and how many stall.

## Metrics

`jason.tasks.response_metrics.measure(period, *, by=("kind",), as_of=today)` returns figures over the requests received in a period (a month, a quarter, a year, or a range).

| Metric | Definition |
|---|---|
| Received | Requests received in the period, by kind and channel |
| Acknowledged on time | Share acknowledged within the kind's acknowledgment target, of those with a target |
| Answered on time | Share answered within the clock in force on the day received, pauses added |
| Time to acknowledge | Median, mean, and 90th percentile, in business days |
| Time to answer | Median, mean, and 90th percentile, in the clock's unit (days or business days) |
| Overdue now | Open requests past their due date: count, the oldest, by kind and owner |
| Due soon | Open requests due within 3 business days |
| Paused | Open requests on a pause, and for how long |
| Assignee time | For handoffs: median time from the forward to the assignee's reply, by assignee kind; stalled count |
| Not a request | Conversations closed as not a request (shown so the exclusions can be checked) |

- **Means mislead on small numbers.** The median leads, and the mean is shown beside it because members and boards ask for an average. A figure from fewer than 5 requests is shown with its count, and never as a rate alone ("2 of 3 on time").
- **Statute clocks and policy clocks are reported apart.** Missing a statutory clock is a compliance finding. Missing a policy clock is a service figure. A late statutory answer is listed by name for the board, in executive session where the subject requires it.
- **Business days skip weekends.** Holidays are skipped when the profile lists them (`Community.holidays()`, default `()`); otherwise a caveat says they were not. How a court counts a period is for counsel.
- **The standard in force.** Each request is measured against the version of its kind's rule in force when it arrived.

## Where it shows

- **CLI:** `jason respond --metrics [--period 2026-Q3] [--by kind|channel|owner|month]`; `jason respond --overdue`.
- **MCP** (read-only): `response_metrics` and `overdue_requests`, with their caveats.
- **jason-web:** `GET /api/response-metrics?period=&by=` and `GET /api/requests?standing=overdue`.
- **The console: a "Service" screen** under Governance:
  - `Stat` tiles: answered on time, median time to answer, overdue now, stalled assignments;
  - a monthly trend (on-time share and median time, by month);
  - the table by kind, with clock sources marked;
  - the overdue list, with a `Doc` chip for each request;
  - the standard itself: adopted rows, proposed rows marked proposed.
- **The dock:** overdue requests and stalled assignments appear in Deadlines.
- **Board reports:**
  - `{REPORT:response-metrics}` for a packet: the quarter's figures, the late statutory answers by name, the stalled assignments, and the standard's adoption status;
  - `jason sop` gains a quarterly step to put it on the agenda.
- **Members:**
  - the published standard always;
  - the association's own aggregate figures (on time, median) only if the board decides to publish them. That is a choice the brief offers, not a default.

## Privacy

- **Metrics** are aggregates (P1 at most).
- **The overdue list** names members and units (P1) and never shows contents.
- **Executive-session matters** are in the private view only: a payment plan request (5665), a hearing request, a dispute. They are counted in the aggregates without names.
- **Notes** on pauses and outcomes go through `intake.secret_reason`, with contact details masked.

## Tests

- A policy row slower than a statute's clock for its kind is refused with the clause recited.
- A proposed row is measured, labeled proposed, and never published; an adopted row is published with its adoption.
- A request is measured against the rule version in force when it arrived.
- A pause on a `POLICY` clock moves the due date. A `STATUTE` clock does not pause unless its row cites words that allow it.
- **Email:**
  - the first association message to the asker is the acknowledgment;
  - an auto-reply or a forward is neither an acknowledgment nor an answer;
  - "answered" by a person wins over the quiet-days reading.
- An email linked to a PayHOA request is one request.
- **Metrics:**
  - the median, mean, and 90th percentile on a fixture set;
  - fewer than 5 requests is shown as a count;
  - business days with and without the profile's holidays;
  - statute and policy reported apart.
- The template renders only adopted rows and recites statutory clocks from disk.

## Rollout

| Step | Ships | Accepts when |
|---|---|---|
| 1. The standard as data | The new `ResponseRule` fields, adoption, the slower-than-law refusal, versions, `jason respond --standards` | The proposal prints with recitations; existing rows and `jason respond` are unchanged |
| 2. Metrics on PayHOA requests | `response_metrics`, `--metrics`, `--overdue`, the MCP tools | Figures match a hand count on a fixture month |
| 3. Email and letters | Requests from the conversation catalog (after its step 3) and mail triage; pauses; `--log` for in-person requests | One request per exchange across channels; no auto-reply or forward counts |
| 4. Adoption and publishing | The board item, the rule-change path where 4355(a) applies, the `response-standards` template, the owner page | An adopted standard appears on the owner page with its adoption; a proposed one never does |
| 5. The Service screen and the board report | The screen, the dock entries, `{REPORT:response-metrics}`, the quarterly SOP step | The board sees the quarter's figures and the late statutory answers by name |

## For the board to decide

- **The standard itself:** the acknowledgment target, and the answer clock for each kind the law and the documents leave open. jason proposes figures from the association's own history: the median and 75th percentile it already achieves, so the first standard is one it can meet.
- **Whether to publish the association's own figures** to members, and how often.
- **The quiet days** after which an email exchange counts as answered, absent a person's word.
- **Whether a board member's personal-account reply counts as the association's** (the conversation catalog's `board_counts`).
- **Holidays:** whether the association observes a list, for business-day counts.
