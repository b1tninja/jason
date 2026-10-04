# Handoff: conversations, response standards, and the policy catalog

For a design pass on three connected features, before they are built. The behavior is settled by three specs:
- [conversations-design.md](../conversations-design.md): threads rejoined, who answered whom, forwards as handoffs;
- [response-standards-design.md](../response-standards-design.md): what members can expect, and the metrics;
- [policy-catalog-design.md](../policy-catalog-design.md): the policies each community adopts.

This page gives the design what it needs: the screens, the components, the data shapes with made-up samples, what must not change, and the decisions that are the design's. Nothing here is built yet. The components below are proposed names, and the build takes them from the design's results.

## The idea in five sentences

The association's mail becomes **conversations**: Gmail's split threads rejoined, each message's author and side known, automatic replies set apart. A **forward is never an answer**: it assigns work, routes misdelivered mail, or shares a copy, and an assignment is followed to its outcome or its inaction. The board adopts a **response standard**, which says how fast each kind of member request is acknowledged and answered, where the law leaves it open, and jason measures it. That standard is one entry in a **policy catalog**: policies jason knows how to apply, each of which a community adopts with its own settings, finds in its documents, or has jason draft for the board. Everything stays jason's voice: a reading is a lead, the board decides, and a person's act names the person.

## Where it lives in the console

| Screen | Where | New or changed |
|---|---|---|
| **Inbox → Conversations** | The Inbox's first tab ("Email awaiting us" today) | Changed: a filter (Waiting on us, Assigned, Waiting on them, All), the conversation as a link, the handoff column |
| **Conversation** | `#/conversations/<id>`, opened from the Inbox, a board item, a brief | New screen |
| **Service** | Governance → Service | New screen: the standard, the figures, the overdue list |
| **Policies** | Governance → Policies | New screen: the catalog's standing for this community |
| **Onboarding → Policies** | A new onboarding tab | New: one item per catalog entry |
| **Portfolio** | The manager's view across communities | New: the policies matrix, the service figures side by side |
| **Owner page** | `#/owner` | Changed: the published response standard (and the figures, if the board chooses) |
| **Dock → Deadlines** | The dock | Changed: overdue requests and stalled assignments appear |

## The components

| Component | Where | States to design |
|---|---|---|
| `ConversationList` | Inbox → Conversations | each filter; empty per filter ("Nothing is waiting on the association"); a stalled assignment row; the cap caveat ("only messages since …") |
| `ConversationLine` | The conversation's header, a brief, the dock | waiting on us (with days), answered (by whom, when), assigned and replied but the asker still waiting, routed (never ours), not a request |
| `MessageRow` | The conversation's ledger | a member's message; the association's reply; a reply from a board member's personal address (marked); group mail ("via the board's group"); an automatic reply (collapsed, never an answer); a message with attachments (`Doc` chips); deep replies (indent capped at 3) |
| `ForwardCard` | Inside a `MessageRow` that forwards something | exact (an attached message), close, approximate (a forwarded-message block), a guess (the subject only); the original in the store (a link to its row) or not |
| `HandoffCard` | Beside the forward that opened it | an assignment on jason's reading ("is that right?"); confirmed by a person; replied; stalled (follow up was …); answered the asker; reassigned; closed by a person with an outcome; routing; a copy |
| `JoinEvidence` | The conversation, "why these are together" | joined by the reply headers; by Gmail's thread; by Outlook's conversation id; by the same subject within 60 days (a lead) |
| `StandardTable` | Service; Policies → response standards; the owner page | each kind with its clock and source (the law, the documents, the board's policy); adopted vs proposed; pauses; the member-facing words |
| `ServiceFigures` | Service | `Stat` tiles (answered on time, median time to answer, overdue now, stalled assignments); small numbers shown as counts |
| `ServiceTrend` | Service | on-time share and median time by month; a gap month; the standard's adoption marked on the line |
| `OverdueList` | Service; the dock | overdue by kind and owner, a statutory clock missed (marked apart from a policy clock), paused requests |
| `PolicyRow` | Policies | adopted (version, date); proposed (draft, board item); declined; not applicable; the statute's default in use; held for the board; required and missing; review overdue; the law changed since |
| `PolicyDetail` | Policies → a policy | the adopted text (`Doc`), its parameters beside their bounds, versions, the decision that adopted it, the rule-change notice, what jason does with it |
| `PolicyProposal` | Onboarding → Policies; Policies → a missing one | found in the documents (a lead to confirm, each parameter beside its sentence); none found (jason's draft, the proposed parameters and where they came from, the brief's options) |
| `PortfolioMatrix` | Portfolio | communities × policies, each cell a standing word; the service figures per community |

Existing components do the rest:
- `Doc` for every document, attachment, and adopted text;
- `Pill` and `Badge` for standing and side words;
- `DueDate` for clocks;
- `Timeline` for a handoff's trail and a policy's versions;
- `Recitation` and `ReadingLabel` for the law's words and jason's reading;
- `Confirm` for every write;
- `DataTable`, `Stat`, `Caveats`, `ScreenHeader`.

### Data shapes (TypeScript)

```ts
type Side = "association" | "board" | "member" | "vendor" | "counsel" | "government" | "other" | "unknown";
type Awaiting = "association" | "other" | "none";
type Intent = "assignment" | "routing" | "copy";
type HandoffStatus = "assigned" | "replied" | "answered_asker" | "stalled" | "reassigned" | "closed" | "routed" | "shared";
type Outcome = "handled_offline" | "answered_elsewhere" | "no_action_needed" | "withdrawn" | "to_board" | "other";

interface ConversationRow {
  convId: string; subject: string; awaiting: Awaiting; firstAt: string; lastAt: string; ageDays: number;
  messages: number; sides: Partial<Record<Side, number>>;
  lastOutside?: { author: string; side: Side; at: string };
  lastAssociation?: { author: string; at: string };
  handoffs: Handoff[]; topics: string[]; likelyNeedsResponse?: boolean; pastUsualTime?: boolean;
  gmailLinks: { mailbox: string; url: string }[];
}
interface Message {
  msgKey: string; at: string; author: string; authorName: string; side: Side; personal?: boolean;
  to: string[]; cc: string[]; subject: string; auto: boolean; autoReason?: string; viaGroup?: string;
  depth: number; parent?: string; attachments: DocRef[];
  edges: { kind: "reply" | "forward" | "resend" | "attached"; to: string; evidence: string; confidence: number }[];
  forward?: { method: string; originalFrom?: string; originalDate?: string; originalSubject?: string;
              original?: string; confidence: number };
}
interface Handoff {
  handoffId: string; assignee: string; kind: "counsel" | "manager" | "vendor" | "board" | "insurer" | "agency" | "accountant" | "other";
  intent: Intent; intentSource: "rule" | "reading" | "person"; at: string; followUpBy?: string;
  status: HandoffStatus; statusAt: string;
  events: { at: string; status: HandoffStatus; source: "mail" | "person" | "clock"; by?: string; outcome?: Outcome; note?: string }[];
}
interface Conversation extends ConversationRow { messages_: Message[]; why: { words: string; confidence: number }[]; caveats: string[] }

interface StandardRow {
  kind: string; source: "statute" | "governing documents" | "proposed policy"; authority: string;
  acknowledgeDays?: number; answerDays: number; businessDays: boolean; adoption: "proposed" | "adopted" | "declined";
  adopted?: string; pauses: string[]; memberWords: string; recital?: Citation;   // the law's words, from disk
}
interface ServiceFigures {
  period: string; received: number; ackOnTime: { n: number; of: number }; answeredOnTime: { n: number; of: number };
  timeToAnswer: { median: number; mean: number; p90: number; unit: "days" | "business days" };
  overdueNow: number; dueSoon: number; paused: number; stalledAssignments: number;
  byKind: { kind: string; source: StandardRow["source"]; received: number; onTime: number; medianDays: number }[];
  byMonth: { month: string; onTimeShare: number; medianDays: number; received: number }[];
  statutoryMisses: { kind: string; who: string; due: string; answered?: string }[];   // named for the board only
  caveats: string[];
}

interface PolicyRow {
  key: string; title: string; instrument: "operating rule" | "board policy" | "statute's default" | "governing documents" | "counsel first" | "configuration";
  standing: "adopted" | "proposed" | "declined" | "not applicable" | "statute's default" | "held" | "required, missing";
  version?: number; adopted?: string; effective?: string; configures: string; nextReview?: string;
  lawChanged?: { section: string; since: string }[]; required?: string; document?: DocRef; boardItem?: string;
}
interface PolicyParam { key: string; label: string; value: unknown; proposed?: unknown; from?: string; bound?: string;
                        source?: { quote: string; doc: DocRef } }
```

### Sample data (made up)

- **Conversation:** "Gate code for the pool". Jane Doe, 123 Main St, member, writes Sep 30. Re: from the association's manager on Oct 1. An automatic reply from a director, out of office. Jane writes back with a new subject, "pool gate still broken". It rejoins by the reply headers. The manager forwards it to Example Pool Co. (vendor), an assignment on jason's reading, follow up by Oct 8. No word: stalled on Oct 9.
- **Misdelivered:** a letter for "Cedar Hollow HOA" scanned at Example Village, forwarded on. Routing; nobody waits.
- **A copy:** the manager forwards an insurer's notice to the board's group with no words. A copy, shared.
- **Service, Q3:**
  - 42 received; acknowledged on time 38 of 40; answered on time 35 of 42;
  - median 4 days, mean 6.1, 90th 13;
  - overdue 3, stalled assignments 1;
  - one statutory miss: a records request answered on day 12 of 10 business days.
- **Policies:**
  - `response-standards` proposed (draft, board item for Nov 18);
  - `notice-delivery` adopted v2 (minutes 2026-06-17);
  - `idr-procedure`, the statute's default in use;
  - `election-rules` adopted 2019, and the law changed since (a 2025 amendment to a cited section);
  - `records-retention` held for the board;
  - `enforcement-and-fines` required and missing.

## What the design must keep

- **A forward is never an answer.** No screen shows a forward as resolving a member's question. A `HandoffCard` sits beside the asker's wait, never in place of it.
- **jason's reading is labeled until a person confirms it.** The intent of a forward, a subject-only join, a found policy document, and a parameter read from a sentence: each says "jason's reading" or "a lead" until a person's word replaces it, and then shows who.
- **Automatic replies are set apart,** collapsed, and never styled as answers.
- **Every write names a person** through `Confirm`: an intent, an outcome, a follow-up draft, an action-register task, a board item, a policy draft. jason drafts and never sends.
- **The law's words come first** (AGENTS.md, "Recite the rule; label the reading"). A statutory clock, a policy's bound, and a required policy show the statute's words (`Recitation`), then any reading, labeled.
- **Statute and policy are reported apart.** A missed statutory clock is a compliance finding, listed by name for the board, in the private view where the subject is executive. A missed policy clock is a service figure.
- **Small numbers as counts.** "2 of 3 on time", never "67%" alone. The median leads; the mean is beside it because people ask for it.
- **Proposed is never member-facing.** The owner page shows only adopted standards with their adoption. A proposed policy is never shown, mailed, or cited to a member.
- **Privacy:** addresses masked until a logged reveal; names P1; executive and legal conversations only in the private view; the owner view never lists conversations.
- **The board decides by vote.** Adoption is a recorded vote at a meeting, never a click in the console. The console records it and links the minutes.
- **WCAG 2.2 AA:**
  - the ledger is a list of articles labelled "NAME, DATE";
  - edges and sides are words, never icons or color alone;
  - the trend has a table equivalent;
  - the matrix has row and column headers.

## Decisions for the design

1. **The ledger's shape.** A threaded indent (capped at 3) or a flat chronological list with "in reply to NAME, DATE" lines, or both, switchable. Mail reads like a chat for some people and like a file for others.
2. **Sides.** How the association's messages read against a member's: alignment, a rule, a label. It must hold for three or more parties (a member, the manager, a vendor, counsel) and for a board member's personal address.
3. **The handoff's place.** Inline beside its forward, in a side column, or both (a summary in the header, the card at the forward).
4. **Confidence in words.** The four words (exact, close, approximate, a guess) are settled. Their visual weight is the design's.
5. **The Assigned filter.** Stalled first. Whether "follow up by" reads as a `DueDate` or a sentence, and how the four next steps (draft a follow-up, add to the register, take it to the board, record the outcome) are ranked.
6. **The Service screen's first glance.** Which figure leads (on time, or overdue now), and how a statutory miss stands out without alarming a screen the board reads every quarter.
7. **The trend.** The console has no chart component yet: one series or two, the adoption marker, a month with few requests.
8. **The standard in members' words.** The owner page's layout for a published standard: a table, a list, or a short letter. Where the law sets the time, its words.
9. **The Policies screen.** A table, cards grouped by area, or a checklist ordered by what is required and due. "Required and missing" must not read as an accusation, only as the next step.
10. **The proposal flow in onboarding.** Found document → confirm each parameter beside its sentence, or none found → review jason's draft with its proposed parameters and their sources → the brief's options. One screen or a stepper.
11. **The portfolio matrix** at 10 communities × 25 policies: grouping, density, and what a cell shows.

## Not part of this pass

- **Gmail bodies in the document viewer** (`gmail:` documents): their own pass, after the catalog exists.
- **The sync's internals**, the threading algorithm, and the metrics' arithmetic: settled by the specs.
- **Each policy's base text:** written per template, with counsel, as the catalog is built.
