# Handoff: from a lead or a board action item to a drafted email

For the design pass on a flow that does not exist yet as a screen. The CLI has its first case: `jason inspections` offers
`jason draft --proposal-request SYSTEM`, which drafts a request to a life safety system's servicer from the record and saves
it as a Gmail draft ([../fire-protection.md](../fire-protection.md), "Asking the servicer"). This page generalizes that case
into one console flow. It lists the components, their states, the data shapes, sample data, what the design must keep, and
the decisions the design is asked to make. Nothing here is built.

## The idea in four sentences

Most leads jason finds end in someone writing to someone:
- an overdue inspection is a request to the vendor;
- an unanswered email is a reply;
- a contract's notice window is a notice of non-renewal;
- a board action item is often a question to counsel or a request for a bid.

From any lead or action item, jason offers **"Draft an email"**. It proposes the purpose, suggests recipients with the reason
for each, and composes the email from the record. Every sentence that came from the record stays linked to its evidence, and
the reminders a person should read first sit beside it. A person picks the recipient, edits the words, and saves the draft
to Gmail. jason never sends. An email that would **commit** the association (accept a proposal, authorize work, give notice
under a contract) waits for the board's recorded decision.

## Where it starts

| Starting point | Screen | What it carries into the draft |
|---|---|---|
| A board action item | Board items ([screens/board-items.md](screens/board-items.md)), its row and its page | the item's `ask`, `summary`, `authority`, `evidence`, `due`, `session`, and its decision when one is recorded |
| An obligation overdue or with no record | Life safety ([screens/life-safety.md](screens/life-safety.md)), a system card; Schedule and duties | the obligation, its citation, the periods not on file, the last record, the servicer |
| A thread waiting on the association | Mail ([screens/mail.md](screens/mail.md)), Today | the thread's subject, its age, its parties, and what happened near it (payments, filed attachments) |
| A contract finding | Contracts ([handoff-contracts.md](handoff-contracts.md)): a notice window, a deliverable not on file | the term's words, its section, the window's dates, the delivery the clause names |
| A dock task | `ActionRegister` | the task's title, owner, and due date, plus its source item when it has one |

A member's request is **not** a starting point here. Its answer has its own clock and flow ([screens/requests.md](screens/requests.md)),
and a notice the law requires goes through the notice catalog and `DraftLetter`, never through this flow.

## The flow

```
[Source card]  ->  Purpose  ->  Recipient  ->  The draft  ->  Before you save  ->  Save to Gmail  ->  Trail on the source
 (pinned)          (proposed,     (suggested,     (from the     (reminders,          (Confirm, in a      (saved, sent, reply,
                   with why)      person picks)   record, then  some to tick)        person's name)      follow-up due)
                                                  edited)
```

1. **Source.** The lead or item stays pinned at the top, read-only, with its evidence as `Doc` chips. The person always sees
   what the email is about and what it rests on.
2. **Purpose.** jason proposes one from the source's kind (a `DraftPurpose` row) and says why ("the inspection is overdue
   and its servicer is on file"). The person can pick another. A purpose that **commits** is marked, and gated by step 5.
3. **Recipient.** The suggestions come in an order, each with its reason:
   - the contact on file (PayHOA, the sender directory);
   - the people who wrote from the counterparty's domains, most recent first;
   - for counsel, the profile's counsel contact;
   - for the board, the board's group.

   The person picks one. Nothing is pre-filled from a document's text. A recipient is checked against the content's privacy
   level: a member's name, unit, or contact details never go to a vendor.
4. **The draft.**
   - **Provenance.** The subject and body are composed from the record. Each sentence is marked by where it came from:
     *from the record* (linked to its evidence), *from the template*, or *typed by a person*.
   - **Law and governing documents.** A citation goes to an outside party as a citation, never as jason's summary. Where the
     words themselves matter, they are recited (`Recitation`).
   - **Editing.** The person edits freely. Regenerating never overwrites their words: it shows a diff, and they choose.
5. **Before you save.** The reminders jason found:
   - the counterparty's mail still waiting on the association, with links;
   - an agreement already on file that may cover the ask;
   - reports filed but not read;
   - a clock the email starts or answers;
   - for a purpose that commits, whether the board's decision is recorded (the meeting and the motion).

   Some are **acknowledge to continue**: the commitment gate, and a member's name or unit in an email to counsel or an agency. To a vendor, those details are
   blocked outright, not acknowledged.
   The rest are advisory.
6. **Save to Gmail.** A `Confirm`: "Save this draft to the association's Gmail as Jane Example. It is not sent." The result
   names the draft and links to it in Gmail. With Gmail not connected, the page shows the `Command` instead
   (`jason draft ... --yes`).
7. **Trail.** The source shows the email's life in its own record:
   - drafted (by, when);
   - saved to Gmail (the draft's id);
   - **sent**, when the Gmail sync sees a message with the draft's subject go out to that recipient;
   - **reply received**, when one comes in on the thread;
   - **follow-up due**, a date the person sets or the purpose proposes ("ask again in 10 business days").

   An unanswered request becomes a lead again on its follow-up date.

## The components

Existing jason-ui parts are reused where named: `Doc`/`DocList`, `Evidence`, `Recitation`, `ReadingLabel`, `Pill`, `Badge`,
`DueDate`, `Timeline`, `Checklist`, `Confirm`, `Command`, `HeldNote`, `Seal` ("drafted"), `Stamp` (a person's decision
only), `Drawer`, `Card`, `EmptyState`. `DraftLetter` stays the path for a letter or notice the board approves and mails; this
flow hands off to it when the purpose is a notice. New ones:

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `DraftFromItem` | a `Drawer` from any starting point, or a page `#/draft?source=<kind>:<id>` | `DraftSession` | the six steps as one scroll or as steps; resumed (a draft in progress for this source); a source with a draft already saved (the trail first, "Draft another" second); Gmail not connected (the command); a refused save |
| `SourceCard` | top of `DraftFromItem`, and in the trail | `DraftSource` | a board item (with its status and decision); an obligation; a thread; a contract finding; a dock task; executive session (marked, see Privacy); stale (the source changed since the draft was composed) |
| `PurposePicker` | step 2 | `DraftPurpose[]` | proposed (with why); chosen; a purpose that commits (marked, its gate named); a purpose that belongs elsewhere (a notice, a member's answer) as a link out, not a choice |
| `RecipientPicker` | step 3 | `RecipientSuggestion[]` | suggestions with their reasons and last contact; none on file (enter one, flagged "entered, not on file"); a recipient whose level the content exceeds (blocked, with why); several (to and cc) |
| `ComposedEmail` | step 4 | `ComposedEmail` | each sentence's origin (record, template, typed); a record sentence's evidence on focus and hover; a citation chip; a recited passage; edited since composed; regenerate with a diff; the plain text as it will be saved |
| `BeforeYouSave` | step 5 | `Reminder[]` | advisory reminders; acknowledge-to-continue reminders (unchecked, checked by whom); the commitment gate open (the decision recorded) or closed (`HeldNote`: "The board has not decided this; the email can ask, not accept") |
| `DraftTrail` | the source's page or row, and the dock | `DraftTrailEntry[]` | drafted; saved to Gmail; sent (detected); reply received; follow-up due, today, past; withdrawn (the person deleted the Gmail draft) |
| `FollowUp` | in `DraftTrail`, and as a dock deadline | `FollowUpClock` | set by a person; proposed by the purpose; due; answered (closed by the reply); dropped (by whom, why) |

### Data shapes (TypeScript)

```ts
type SourceKind = "board-item" | "obligation" | "thread" | "contract-finding" | "dock-task";
type Level = "P0" | "P1" | "P2" | "P3";            // security-and-privacy.md: documents and law, members' names and units,
                                                  // contact details, restricted (executive session, legal, delinquency)

interface EvidenceRef { label: string; address: string; doc?: DocRef }

interface DraftSource {
  kind: SourceKind; id: string; title: string;      // "Annual sprinkler inspection overdue"
  ask?: string; summary?: string; authority?: string; // a citation, never a paraphrase
  evidence: EvidenceRef[]; due?: string; session?: "open" | "executive";
  decision?: { meeting: string; motion: string; recordedBy: string };   // a board item's recorded vote, when there is one
  counterparty?: string;                            // the sender directory's name, when the source names one
  level: Level;                                     // the most private fact the source carries
}

interface DraftPurpose {
  key: string;                                      // "request-proposal", "request-records", "follow-up", "reply", "ask-counsel", ...
  label: string; why: string;                       // why jason proposes it for this source
  commits: boolean;                                 // accepting, authorizing, notifying under a contract
  gate?: string;                                    // what a commit needs: "the board's recorded decision"
  elsewhere?: { label: string; href: string };      // a notice or a member's answer: link out, not here
  followUpDays?: number;
}

interface RecipientSuggestion {
  address: string; name?: string; why: string;      // "the contact on file in PayHOA", "wrote us 7 times, last 2025-06-17"
  source: "payhoa" | "wrote-us" | "directory" | "profile" | "entered";
  maxLevel: Level;                                  // the most private content this recipient may receive
}

interface Sentence { text: string; origin: "record" | "template" | "person"; evidence?: EvidenceRef[];
                     citation?: string; level: Level }

interface ComposedEmail {
  to: string[]; cc: string[]; subject: string;
  paragraphs: Sentence[][];                          // the body, sentence by sentence
  signer: string;                                    // "Board of Directors, Example Village HOA" or a person
  composedAt: string; editedBy?: string; editedAt?: string;
}

interface Reminder { text: string; kind: "waiting-mail" | "agreement-on-file" | "not-read" | "clock" | "commitment"
                     | "privacy" | "decision"; link?: string; mustAcknowledge: boolean;
                     acknowledgedBy?: string; acknowledgedAt?: string }

interface DraftSession {
  source: DraftSource; purposes: DraftPurpose[]; purpose?: string;
  recipients: RecipientSuggestion[]; email?: ComposedEmail; reminders: Reminder[];
  saved?: { gmailDraftId: string; by: string; at: string; link: string };
}

interface DraftTrailEntry { at: string; what: "drafted" | "saved" | "sent" | "reply" | "follow-up" | "withdrawn";
                            by?: string; ref?: string; note?: string }
interface FollowUpClock { due: string; set: "person" | "purpose"; by?: string; closedBy?: "reply" | "person" }
```

### Sample data (made up)

- **An obligation.** "Annual sprinkler inspection and test, buildings A and B", due 2024-03-14 and overdue; the last report
  on file is 2023-03-14; the servicer is "Example Fire Protection, Inc."
  - Purpose: request a proposal and reports.
  - Recipients: office@example.com (the contact on file) and two people who wrote from the domain.
  - Reminders: a vendor email from 2025-06-18 still waiting on us; a signed proposal on file from 2024; a report filed and
    not read.
- **A thread waiting on us.** "Re: Gate repair estimate", 41 days old, from "Example Gates" with an estimate attached.
  - Purpose: follow up, or reply asking a question.
  - The commitment gate is closed: no decision is recorded, so the email can ask about the estimate but not accept it.
- **A contract finding.** A management agreement's non-renewal window: written notice at least 60 and no more than 120 days
  before the term ends, by certified mail.
  - Purpose: a notice of non-renewal. It commits, and it goes to `DraftLetter` for the board's approval and certified mail.
  - This flow shows the link out, the window's dates, and the clause recited.
- **A board item in executive session.** "Counsel's opinion on the insurance claim".
  - Purpose: ask counsel.
  - The only suggested recipient is counsel. The content is P3, and any other recipient is blocked.

## What the design must keep

- **Nothing is sent.** The end of the flow is a Gmail draft. The page never has a send button, and no word on it says
  "send" except "send it from Gmail".
- **A person picks the recipient.** The suggestions say why; none is pre-selected from a document's text or from a message
  jason read.
- **The record speaks in the record's words.** A sentence from the record links to its evidence. To an outside party:
  - the law and the governing documents are cited, or recited where the words matter, never paraphrased by jason;
  - the email says what "our records show", never that the recipient failed or breached. A lead is not a finding.
- **A commitment waits for the board.** A purpose that accepts, authorizes, or gives notice under a contract needs the
  board's recorded decision (meeting and motion), shown on the gate. Without it, the email can ask, not commit. `HeldNote`
  carries the words.
- **Privacy follows the content, not the screen.** Each sentence carries its level
  ([security-and-privacy.md](security-and-privacy.md)):
  - a member's name or unit (P1) and anyone's contact details (P2) never go to a vendor;
  - restricted material (P3: an executive-session matter, a legal matter, a delinquency) goes only to counsel or the party
    it concerns;
  - a blocked recipient says why.
- **A person's words are theirs.** Regenerating never overwrites an edit. It shows a diff, and the person chooses.
- **The trail lives on the source.** The item, the obligation, or the thread shows that an email was drafted, saved, sent,
  and answered, so the next person does not draft it twice. A follow-up date turns silence back into a lead.
- **Words on screen** follow [content/style.md](content/style.md): verbs first ("Draft an email", "Save to Gmail"), no
  "successfully", and an empty state that invites ("No email drafted for this item").
- **WCAG 2.2 AA** as in [components.md](components.md#accessibility):
  - a sentence's origin is a word as well as a mark;
  - the steps are a list a screen reader can walk;
  - an acknowledge-to-continue reminder is a real checkbox with a label;
  - the commitment gate is announced;
  - the drawer traps focus and returns it to the starting row.

## Decisions for the design

1. **Drawer or page.** The flow from a row could be a `Drawer` over the screen it starts from, a page of its own, or a
   drawer that can expand into a page. A long email from a contract finding may need the page.
2. **Showing provenance without clutter.** A margin rail of origins, an underline on focus, a toggle "show where each
   sentence came from", or a side list of facts used. It must survive a screen reader and a phone.
3. **Steps or one scroll.** A guided sequence for a first use, or everything on one page with the source pinned. Most
   drafts take one pass.
4. **Regenerate.** How the diff between the person's edit and a fresh composition is shown and merged.
5. **The commitment gate.** How "the board has not decided" reads beside an email that only asks, so a person does not take
   the gate as a block on asking.
6. **The trail on a crowded row.** A board item row has little room. A count, a last-event word ("sent 3 days ago, no
   reply"), or a glyph.
7. **Follow-ups in the dock.** Whether a follow-up due is a deadline in `DeadlineList`, a task in `ActionRegister`, or both.
8. **Phone.** A director drafting from a phone: the source collapsed to one line, the recipient a list, the body full width.

## Not part of this pass

- Sending from the console, and reading a message's body. jason's Gmail store is headers only, so "sent" and "reply" come
  from the sync's headers, and a person reads the body in Gmail.
- The purpose templates' wording. Each purpose is a base template written once and rendered with the profile's name,
  signer, and contacts. That is content work in the templates, not this design.
- The loaders. Proposed, not built:
  - `GET /api/drafts/purposes?source=`;
  - `POST /api/drafts/compose` (no write: it returns a `DraftSession`);
  - `POST /api/write/drafts/gmail` (behind `Confirm`, with `by`: it creates the Gmail draft and writes the trail);
  - `GET /api/drafts?source=`.

  The CLI parity is `jason draft`, whose first general case is `--proposal-request`. A `--item ID --purpose KEY` form is
  proposed.
- A member's answer and a notice the law requires: their flows exist, and this one links to them.
