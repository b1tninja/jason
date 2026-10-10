# The policy catalog: a common set of capabilities each community configures by adopting policies

jason does the same work for every association: notices, records requests, collections, hearings, architectural review, elections, meetings, mail, approvals. Much of that work turns on a choice the law leaves to the association:
- how fast to answer;
- how long to keep a record;
- what a fine is;
- who may see what.

AGENTS.md's axiom is that such a choice is settled once in writing, never case by case: "Where the law is silent, write it down". This spec makes it a catalog:
- **jason defines once**, in general code, each policy it knows how to apply: its parameters, its legal bounds, its base text, and how it is adopted.
- **A community adopts** an instance of each, with its own parameters, the board's adoption on record, and its version history.
- **Onboarding walks the catalog.** For each policy it asks whether the association has one, finds it in the documents if so, and if not, proposes one for the board.

jason proposes. The board adopts. jason never makes a rule. The statute sections named below are pointers to the provisions each policy turns on. Each template recites them from the statutes on disk (`jason cite`) when it is built, never from this page. Whether a given policy is required, and in what form, is the statute's to say and counsel's to read.

## What exists, and what this generalizes

- **A private policy canvas** for one community already sorts its open questions into four instruments and lists candidates and their status.
- **Two response policies:** `owner_responses.RULES`, the owner-information response policy, which turns "hold for the board" into a rule once adopted, and `ResponseRule` with `ClockSource.POLICY`.
- **The duty schedule** records `Adoption` (proposed, adopted, declined, not applicable) and `adopted` (the minutes or resolution).
- **Three commands:** `jason rule-change` drafts a 4355(a) rule change's notice (4360); `jason conflicts` and `--leads` find where a document yields to a later statute; `jason law-history` checks a provision's citations.
- **Base templates** (`DocumentTemplate` rows) are written once and filled per community.
- **The onboarding items** (`jason.community.onboarding`) ask, find leads, and record answers.

The catalog ties these together. A policy becomes a typed record with parameters that jason's capabilities read, instead of a document and a scattered set of rule rows.

## The instruments

Every catalog entry names how it is adopted. That decides the steps, and nothing about it is jason's choice:

| Instrument | When | Adopted by |
|---|---|---|
| `OPERATING_RULE` | A rule on a subject Civil Code 4355(a) lists (common-area use, discipline and fines, payment plans, dispute resolution, architectural review, elections, among others) | Written; general notice to members with the text and its purpose before the vote (4360); `jason rule-change` |
| `BOARD_POLICY` | Anything else that applies generally: procedures, records, meetings, communications | A vote at an open meeting, recorded in the minutes |
| `STATUTE_DEFAULT` | The law supplies a procedure when the association adopts none (the statute's own fallback) | Nothing: jason applies the statute's default and says so, until the association adopts its own |
| `DOCUMENTS` | The governing documents already settle it | Nothing to adopt: jason reads the clause (`GoverningDocument`) and binds the policy to it |
| `COUNSEL_FIRST` | The law or the documents are unclear rather than silent | Counsel's reading, then a policy if there is room for one |
| `CONFIGURATION` | jason's own operation: who sees what, which mailboxes, what needs two people | A board resolution, or the manager under authority the board delegated in writing |

## The catalog

Grouped by the capability each configures. Each row is one `PolicyTemplate`. "Bound" is what the law or the documents fix, which no parameter can loosen.

### Notices and members' information

| Key | Instrument | Turns on | jason capability it configures | Parameters |
|---|---|---|---|---|
| `notice-delivery` | Board policy | 4040, 4041, 4045, 5310 | Owner information, notice delivery plans, the Mailroom | How co-owners' elections combine, blanks, bounces, correction handling, the posting location |
| `designated-recipient` | Board policy (in the annual policy statement) | 4035, 5310 | `Community.identity()`, letter reply-to | The recipient, the address, the email |
| `electronic-delivery` | Board policy, or a rule where 4355(a) reaches it | 4040, 4041 | Email delivery, the owner-information form | Consent wording, the fallback when email bounces |

### Requests and responses

| Key | Instrument | Turns on | Capability | Parameters | Bound |
|---|---|---|---|---|---|
| `response-standards` | Board policy (an operating rule for 4355(a) subjects) | 5210, 714, 4745, 5665, 5935, the documents | `jason respond`, the conversation catalog, the metrics ([response-standards-design.md](response-standards-design.md)) | Acknowledgment and answer clocks per kind, pauses, quiet days, publication of figures | Never slower than a statute's or the documents' clock |
| `handoff-follow-up` | Configuration | — | Handoffs ([conversations-design.md](conversations-design.md#handoffs-a-forward-is-an-assignment)) | Follow-up days per assignee kind, and whether stalled legal assignments go to the board | A retainer's or a contract's stated time |
| `records-requests` | Board policy | 5200–5240 | Records requests, fees, redaction | Fees (actual cost), formats, the member-list opt-out wording | The statute's periods and the cost limit |
| `complaints` | Board policy | — | Complaint intake, the action register | What a complaint needs, who sees it, how the complainant is told the outcome | — |

### Enforcement, disputes, architectural review

| Key | Instrument | Turns on | Capability | Parameters |
|---|---|---|---|---|
| `enforcement-and-fines` | Operating rule | 5850, 5855, 4355(a) | Hearings, notices of hearing, decisions | The fine schedule, warnings before a fine, cure periods |
| `idr-procedure` | Operating rule, else `STATUTE_DEFAULT` | 5910, 5915 | Disputes | The procedure's steps and times; without one, the statute's |
| `adr-response` | Statute | 5925–5965 | ADR requests | (none: the statute's) |
| `architectural-review` | Operating rule | 4765, 714, 4745, the documents | Architectural requests, response clocks | The application's contents, the reviewer, the clocks, the appeal |
| `rental` | Documents, else operating rule | 4741, the documents | The rental register, occupancy | The application, the documents' cap and term |

### Money

| Key | Instrument | Turns on | Capability | Parameters |
|---|---|---|---|---|
| `collection` | Board policy (in the annual policy statement) | 5310, 5650–5730 | Delinquency, notices, the lien workflow | Late charge and interest within the statute's limits, the steps and their timing, payment methods |
| `payment-plans` | Operating rule | 5665, 4355(a) | Payment plan requests | Minimum terms, the meeting procedure |
| `reserve-funding-and-borrowing` | Board policy | 5510, 5515, 5550, 5560 | Reserves, transfer findings | The funding plan, the borrowing procedure, repayment |
| `financial-review` | Board policy | 5500 | Books checks, the review cadence | Monthly or quarterly per item, within the statute's minimum |
| `spending-authority` | Board policy (and the management agreement) | the documents and the management agreement (Civil Code 5610 is the emergency exception to assessment increases, not a spending authority) | Approvals, invoices | The manager's limit, emergencies, which kinds need two signatures |
| `vendor-selection` | Board policy | The documents | Vendors, contracts, insurance certificates | Bids above an amount, insurance minimums, conflicts (5350) |

### Meetings, elections, records

| Key | Instrument | Turns on | Capability | Parameters |
|---|---|---|---|---|
| `meeting-schedule` | Board resolution | 4920, 4925 | Meeting planning, the calendar | Regular dates, location, teleconference |
| `meeting-records` | Board policy | 4950, 5200 | Zoom recordings, transcripts, AI summaries, minutes | What is kept, for how long, the executive-session rule |
| `election-rules` | Operating rule | 5105, 5100–5145 | The election calendar and notices | The inspector, the candidate rules, electronic voting where the law allows it |
| `records-retention` | Board policy | 5200, 5210, the documents | The library, holds, destruction | Periods per record kind beyond the statute's, who keeps them, holds |
| `resolution-register` | Board policy | — | Decisions, the minutes | Numbering, where adopted texts are kept |

### jason's own operation

| Key | Instrument | Capability | Parameters |
|---|---|---|---|
| `data-access` | Configuration | Console roles and levels ([security-and-privacy.md](console/security-and-privacy.md)) | Which offices open P2 and P3, the private view's limits, reveal logging |
| `approvals` | Configuration | The approvals engine | Which kinds need a second person, cost thresholds |
| `mail-reading` | Configuration | The Gmail sync | Which mailboxes, the groups jason's mailbox joins ([setup.md](setup.md#6-jasons-mailbox)) |
| `automation-disclosure` | Board policy | Letters and notices jason drafts | Whether letters say they were drafted with jason, and how |
| `owner-view` | Board policy | The owner page | What members see: published standards, figures, documents |

## The model

General code, `jason.community.policies`:

```python
class Instrument(Enum):
    OPERATING_RULE = "operating rule"; BOARD_POLICY = "board policy"; STATUTE_DEFAULT = "statute's default"
    DOCUMENTS = "governing documents"; COUNSEL_FIRST = "counsel first"; CONFIGURATION = "configuration"

@dataclass(frozen=True)
class Param:
    key: str                      # "ack_days", "fine_first", "keep_years"
    kind: type                    # int, Money (integer cents), Duration, an Enum, a tuple of rows
    default: Any                  # jason's proposed default; never applied as adopted
    bound: str = ""               # the citation that limits it; checked when the profile loads
    check: Callable | None = None # the bound as code: a fine within the schedule's max, a clock not slower than law

@dataclass(frozen=True)
class PolicyTemplate:
    key: str
    title: str
    instrument: Instrument
    authorities: tuple[str, ...]  # citations recited from disk in the draft and the brief
    capability: str               # the module or command that reads it
    params: tuple[Param, ...]
    template: str                 # the base text's DocumentTemplate key ({PARAM} tokens)
    required: str = ""            # "" | the citation that requires a policy of this kind (the brief recites it)
    fallback: Fallback = Fallback.HOLD   # what jason does with no adopted policy: STATUTE_DEFAULT | PROPOSED | HOLD
    review_months: int = 12       # how often the board reviews it
    lead_kinds: tuple = ()        # the document kinds onboarding searches for an existing one
```

In the profile (`Community.policies()`, default `()`), each adoption is a row:

```python
@dataclass(frozen=True)
class AdoptedPolicy:
    key: str                      # the template's
    version: int
    params: Mapping[str, Any]     # the community's values, checked against each Param's bound
    adoption: Adoption            # the schedule's enum: PROPOSED | ADOPTED | DECLINED | NOT_APPLICABLE
    adopted: str = ""             # the minutes or resolution ("board minutes 2026-11-18, item 6")
    effective: date | None = None
    rule_change: str = ""         # the jason rule-change key, for an operating rule (its 4360 notice)
    document: str = ""            # the GoverningDocument or Drive id that holds the adopted text
    supersedes: int = 0           # the version it replaces; every version is kept
    note: str = ""
```

**How a capability reads it.** It asks `community.policy("response-standards")`, which returns the adopted version in force on a date, or none. With none, the template's `fallback` decides what jason does:

| Fallback | jason does | Says |
|---|---|---|
| `STATUTE_DEFAULT` | Applies the statute's own procedure (an IDR without an adopted procedure) | "The statute's default applies: the association has adopted none (CIV 5915)", recited |
| `PROPOSED` | Applies the proposed default internally, to measure and plan, never to members | "jason's proposed default, not adopted", in every caveat it touches; nothing member-facing |
| `HOLD` | Decides nothing: the question goes to the board's canvas | "No policy: held for the board", the same as the owner-information response policy |

**Versions.** A decision is always made against the version in force on its day: a request is measured against the standard in force when it arrived, and a fine against the schedule in force when the violation was noticed.

**Bounds** are checked when the profile loads. A parameter outside its legal bound is refused with the clause recited, the same rule as `ResponseRule`'s "never slower than the law".

## Onboarding walks the catalog

A new onboarding group, `POLICIES`, gets one item per template, generated from the catalog rather than written by hand. Each item:

1. **Asks** whether the association has adopted a policy on this, and where it is.
2. **Finds leads** in the library and Drive by the template's `lead_kinds` (a collection policy, a fine schedule, election rules, an architectural guideline), and in the minutes by phrase. A found document is a lead, never a finding: a person confirms it.
3. **Binds** a confirmed document. The `AdoptedPolicy` row points at it (`document`), with `adopted` from the minutes. jason reads the parameters it can from the text (a fine amount, a clock), each shown beside the sentence it came from for a person to confirm (AGENTS.md: quote, then cite).
4. **Proposes**, when there is none:
   - a draft from the base template, with parameters proposed from the association's own history where jason has it. A response clock is set from the median and 75th percentile already achieved, a retention period from the statute's minimum plus the board's practice;
   - a board item, or a rule change when the instrument is an operating rule;
   - the decision brief's options: adopt, adopt with changes, decline (and how the duty is met otherwise), or ask counsel.
5. **Records** the board's decision. Adopted, declined, and not applicable are each a row, so "missing" means only "not yet decided".

The required ones come first, ordered by the template's `required` citation and by what is due soonest (the annual policy statement's contents before its deadline).

## The Policies screen

A console screen under Governance lists the catalog for the community:

| Column | Shows |
|---|---|
| Policy | The title and its instrument |
| Standing | Adopted (version, date), Proposed (draft, board item), Declined, Not applicable, Statute's default in use, Held for the board, Required and missing |
| Configures | What jason does with it, in words |
| Review | The next review date (`review_months`); overdue reviews flagged |
| Law changed | A later statute touching its authorities (`jason conflicts --leads`), as a lead |

Each row opens the adopted text, as a `Doc` on its document, beside its parameters, versions, the decision that adopted it, and its rule-change notice.

**Across communities.** A manager with a portfolio sees the same columns across the communities they manage. A policy one association adopted can be offered to another as a starting draft, never as an adoption.

## The yearly review

`jason sop policy-review` runs each year with `law-review`. For every adopted policy:
- whether a statute it cites changed since its adoption (`jason law-history`, `conflicts --leads`);
- whether its parameters still sit inside their bounds;
- whether the association met it: the response metrics for `response-standards`, retention destruction runs for `records-retention`, and so on.

Each finding is a lead for the board, and any change goes through the same adoption path.

## Limits

- **jason proposes; the board adopts.** No policy is in force until its adoption is recorded.
- **Templates are starting points.** They recite the law and offer common choices; they are not legal advice. Where the law is unclear, the instrument is `COUNSEL_FIRST`.
- **A policy yields to what is above it.** The statute, then the governing documents (`authority_order.Tier`). A conflict is a `Conflict` row, never a silent override.
- **The documents first.** A policy the documents settle is bound to the clause, not re-adopted.
- **Member-facing only when adopted.** A proposed policy is never published, never mailed, and never cited to a member.

## Rollout

| Step | Ships |
|---|---|
| 1. The model | `Instrument`, `Param`, `PolicyTemplate`, `AdoptedPolicy`, `Community.policies()`, `community.policy(key, on=date)`, the bound checks, the fallbacks |
| 2. Three templates that already have code | `response-standards` (from `ResponseRule`), `notice-delivery` (from the owner-information response policy), `records-retention` (from the library's holds) |
| 3. Onboarding's `POLICIES` group | The items generated from the catalog; the lead finder; binding a found document; the brief and board item for a proposal |
| 4. The Policies screen and the yearly review | The screen, the portfolio view, `jason sop policy-review` |
| 5. The rest of the catalog | One template at a time, each with its capability reading it and its test |

## For the board and counsel

- **The catalog's list itself:** which of these the association wants, and in what order. The required ones (those whose `required` citation the brief recites) first.
- **For each template's statute pointers:** counsel's reading of what is required and in what form, before a template is offered as a draft to any community.
- **Delegation:** which `CONFIGURATION` policies the board delegates to the manager in writing, and which it keeps.
