# Handoff: contracts, parties, and licenses

For the design pass on components that do not exist yet. The behavior, the words, and the data are settled in
[../contracts.md](../contracts.md) and the readers it names; this page is what the design needs to draw them: the components,
their states, the data shapes the loaders will return, sample data, what the design must keep, and the decisions it is asked to
make. Nothing here is built. The first build will use the sample data below as test fixtures (made-up names only), and the real
payloads have the same shapes as `jason contract-terms --json` today.

## The idea in four sentences

A contract is read once, as it comes in, into **terms**: each one the contract's own words, with whose duty it is, its topic, its
clock, and what qualifies it (a release, a party's room to act, a code it brings in, a consent it needs, a warranty it gives). From
the terms jason draws what a board needs before it signs, renews, or ends an agreement: **what the counterparty owes** (reports,
logs, notices, records), the **notice windows** and how notice must be delivered, the **scope** and what is outside it, the
**warranties**, who **signed**, and the **licenses** printed on the paper. Every one of these is a lead read beside the contract's
words and the statute, never a legal conclusion: jason is not counsel, and a question of meaning goes to counsel. A closer reading
by a model is a person's choice, and a model that sends the words off the machine (Bedrock) is chosen per document, in a named
person's name.

## Where it lives in the console

| Surface | Route (proposed) | Audience | What it is for |
|---|---|---|---|
| Contracts | `#/contracts` (Records) | manager, board | every agreement and proposal read, with its counterparty, term, status, and the findings that need a person |
| One contract | `#/contracts?key=<key>` | manager, board | the reading whole: summary, what is owed, notice, scope, warranties, terms by topic, signing |
| Vendors | `#/vendors` (or a tab on the existing vendor pages) | manager, board | each counterparty with its agreements, licenses, what it owes, and what is on file |
| Licenses | a tab under Vendors | manager, board | the license register: every number read from every file, its holder, and where to check it |
| Ingest | Onboarding → Ingest, and the intake queue | manager | a new file's kind, weighed from its words, and the question when the name and the words disagree |
| Life safety | the Vendors table on [screens/life-safety.md](screens/life-safety.md) | manager, board | `LicenseChip` and "owes us" come from here |

A director reads a contract's review before a meeting on a phone as often as at a desk: every component works at 360px.

## The components

Existing jason-ui parts are reused where named (`Doc`/`DocList`, `DocumentViewer`, `Recitation`, `ReadingLabel`, `Pill`, `Badge`,
`Findings`, `Caveats`, `Evidence`, `DataTable`, `Tabs`, `Card`, `DueDate`, `Timeline`, `Checklist`, `Confirm`, `Command`, `Money`,
`SearchBox`, `QuestionCard`, `HeldNote`, `EmptyState`). New ones:

| Component | Where it renders | Data | States to design |
| --- | --- | --- | --- |
| `ContractList` | Contracts | `ContractSummary[]` | grouped by counterparty or by status (in force, proposal, ended, unsigned copy); a row's findings count by severity; read by grammar or by a model (and which); confidential (locked, the name still shown to roles that may see it); a file not read yet (a `Command`); empty (an invitation to ingest) |
| `ContractHeader` | One contract, top | `ContractSummary` | counterparty with the other names it goes by ("dba", short forms, role labels); the association's side as named in the paper; the term and renewal in words; signed, blank copy, or e-signed; method chip; licenses as `LicenseChip`s; the caveat line ("a reading, not legal advice") |
| `PartyTag` | on every term, scope item, warranty | `PartyReading` | association, counterparty, either party, unstated; **read from the words** vs **a reading** (a passive duty in the vendor's own form, a line under a role label, a "will" sentence), the reading's note on focus; unstated is an invitation to say whose, never an error color |
| `TermRow` | One contract → Terms | `ContractTerm` | the quote whole (expandable past ~220 characters), its section and caption; kind word (duty, prohibition, permission, right, condition, statement, exemption); `PartyTag`; topic; the clock (`DueDate` for a deadline, the recurrence in words, a notice window); qualifier chips (exemption kind, discretion degree and what over, consent of whom, standard brought in, warranty months); deliverable mark; read by grammar or added or filled by a model; the source `Doc` at the quote's place |
| `TermsByTopic` | One contract → Terms | `ContractTerm[]` | topics as collapsible groups with counts, in the reader's order (parties first, statutory notices last); filters by party, kind, and qualifier ("only exemptions", "only the counterparty's room to change the price"); search over the words; a 300-term management agreement and a 12-term proposal both readable |
| `OwedList` | One contract, and Vendors | `ContractTerm[]` (the deliverables) | what the counterparty must produce: a log, a report, a notice, records at the end, a written warranty; each with its clock and its words; **on file** (a `Doc` matched in the library), **not on file**, or **not yet due**; "Track this" proposes a register row or a board item behind `Confirm` |
| `NoticeWindow` | One contract (term and notice) | `NoticeWindowView` | a band on a dated axis: the term's end, the window's first and last days, today, and the delivery the clause names (written, certified mail, email); a notice outside either edge marked "may not count"; a window with one edge; "the term's end needs input" when the start date is a blank the text could not read |
| `ScopeList` | One contract → Scope | `ScopeItem[]`, `excluded: string[]` | three groups: the work, what the price includes, and options or alternates (outside the base price, with their cost); then **not included** (the exclusions list and work "by others" or "by owner"); an item under the association's own role label marked as the association's work |
| `WarrantyList` | One contract, Vendors | `Warranty[]` | holder (`PartyTag`), what it covers, how long, from when; an end date only when the start is a date on record (else "from completion: needs the completion date"); a written warranty promised and whether it is on file; a warranty with no holder ("The roof's warranty is ten years") shown as unattributed, never as the vendor's |
| `OptionsMarked` | One contract (proposals) | `OptionMark[]` | each offered option with its mark: chosen, not chosen, or **not read** (with "read from the signed page" and how: text, or the page layout); a mark the layout could not place; never a guessed tick |
| `SigningBlocks` | One contract, bottom; `ContractList` row | `SigningBlock[]` | each side: signed (by, title, date), blank, e-signed (the audit trail's signer); the **unsigned copy** banner ("this copy is not the signed agreement; the signed copy is the record") with a link to find it |
| `ContractFindings` | One contract, beside the header | `Finding[]` | `Findings` grouped by severity (check, info); each finding's authority opens its `Recitation`; finding words from the reader (notice window, arbitration, shortened limitations, one-way indemnity, the counterparty's one-side change, an effort promised instead of a result, a counterparty's release, a code incorporated, options not read, unsigned copy); "a lead for a person; a question of meaning goes to counsel" |
| `StatutoryNotice` | One contract, inside Terms | `ContractTerm[]` on the statutory notice topic | collapsed by default: "Prints the Notice to Owner (Civil Code 8000-8848): the Legislature's words, not a promise of either party"; open shows the words |
| `LicenseChip` | everywhere a license appears | `LicenseMention` | board and number ("CSLB 123456", "DRE 01234567"); class; holder as read; the board's page as an outbound link (opens the board's site; jason reads the number, the board's page is the record); **holder differs** from the counterparty; **board not named** ("likely CSLB; confirm"); no holder read |
| `LicenseRegister` | Vendors → Licenses | `LicenseRow[]` | a table: number, board, class, holder, the documents it appears in (`Doc` chips), when read; filters by board; a number in several documents once; a number whose holder is only in a logo |
| `ModelReview` | One contract, an action | `ModelReviewState` | "Read more closely with a model": local (Ollama, which model, the GPU lane's queue) or Bedrock; Bedrock's `Confirm` says the words go to AWS and names the person; a **confidential** file refused unless the person allows it for this run; queued, running, done; trust ("fill only" or "full"); after: what the model added, what it filled, and **what it proposed that is not in the text** (dropped, with why) |
| `KindVerdict` | Ingest report, intake queue | `KindAnalysis` | the verdict word (confirmed, a person's, disagrees, weak, proposed, unknown) with its meaning; the top candidates with their scores and reasons ("a parties clause", "a signature block", "the association is not a party"); a third-party agreement (an owner's lease or property-management agreement) set apart from the association's own contracts; the question as a `QuestionCard` |

### Data shapes (TypeScript)

The shapes are `TermsReading.as_dict()` (`jason.tasks.contract_terms`), a term's `to_dict()`, and `licenses.LicenseMention`.

```ts
type Party = "association" | "counterparty" | "either" | "unstated";
type TermKind = "duty" | "prohibition" | "permission" | "right" | "condition" | "statement" | "exemption";

interface ContractSummary {
  key: string; name: string;                 // "file-roof-proposal", "Roof repair proposal.pdf"
  counterparty: string;                      // "Example Home Services"
  parties: { association: string[]; counterparty: string[]; names: Record<string, string> };
  method: string;                            // "grammar" | "hybrid:ollama" | "hybrid:bedrock (full)"
  confidential: boolean; readAt: string;
  counts: { terms: number; deliverables: number; byTopic: Record<string, number>;
            byParty: Record<Party, number>; findings: Record<string, number> };
  licenses: LicenseMention[]; signatures: SigningBlock[]; doc?: DocRef;
}

interface ContractTerm {
  id: string; section: string; caption: string; start: number; end: number;
  quote: string;                             // the contract's own words, never a paraphrase
  kind: TermKind; party: Party; topic: string; party_words: string;
  note: string;                              // set when the party is a reading: "(passive, in the counterparty's own form)"
  deadline: { text: string; days?: number; relation: string } | null;
  recurrence: string; recurrence_months: number; window_days: [number, number] | null;
  conditions: string[]; notice: boolean; delivery: string[];
  amounts: number[];                         // integer cents
  percents: number[]; deliverable: boolean;
  method: string;                            // "grammar" | "model:<backend>" | "hybrid:<backend>"
  exemption: string;                         // "not obligated" | "not responsible or liable" | "excluded from the work" | ...
  discretion: string; discretion_over: string;   // "one-side change", "price"
  standards: string[];                       // ["NFPA 25 (2013 California Edition)", "Title 19"]
  warranty_months: number; consent: string;  // consent: a Party, or the words when no party is named
}

interface ScopeItem { text: string; kind: "work item" | "included in the price" | "optional or alternate";
                      heading: string; party: Party }
interface Warranty { holder: string; party: Party; note: string; form: string; covers: string[]; covered: string;
                     months: number | null; start: string; written: boolean; deliverable: boolean; sentence: string }
interface OptionMark { label: string; checked: boolean | null; marker: string; source?: "text" | "layout" }
interface SigningBlock { for: string; signer: string; title: string; date: string; signed: boolean;
                         kind: "form" | "audit" }
interface LicenseMention { board: string; label: string; number: string; classification: string;
                           jurisdiction: string; holder: string; quote: string; verify: string; note: string }
interface Finding { code: string; message: string; severity: "info" | "check"; authority: string }

interface NoticeWindowView {               // composed by the loader from a term with window_days
  term: string;                            // the term id
  termEnd?: string; termEndSource: "recorded" | "implied" | "needs input";
  opens?: string; closes?: string;         // ISO dates: termEnd minus the longest and the shortest notice
  delivery: string[]; today: string;
  sent?: { day: string; by: string; doc?: DocRef };   // a notice on record, placed in or outside the window
}

interface KindAnalysis {
  verdict: "confirmed" | "person" | "disagrees" | "weak" | "proposed" | "unknown";
  kind: string; candidates: { kind: string; score: number; reasons: string[] }[];
  thirdParty?: string;                     // "lease" | "property management" | "loan"
  notes: string[];
}

interface ModelReviewState {
  backend: "ollama" | "bedrock"; model: string; trust: "fill" | "full";
  status: "idle" | "queued" | "running" | "done" | "refused" | "unavailable";
  refusedWhy?: string;                     // "confidential: a person allows it for this run"
  added: number; filled: number; dropped: { why: string; candidate: string }[];
}
```

### Sample data (made up)

- **A management agreement,** "Example Management, LLC" for "Example Village HOA": 300 terms over 22 sections, a term of one
  year renewing unless either party gives written notice at least 60 and no more than 120 days before the end, delivered by
  certified mail; the manager may adjust its fees "in its sole discretion" (one-side change over fees); "Manager shall not be
  obligated to attend meetings on weekends" (an exemption); "Manager will endeavor to make helpful suggestions" (an effort); an
  arbitration clause; DRE 01234567; e-signed by both sides. A notice of non-renewal on record two days after the window closed.
- **A roof repair proposal,** "Sample Holdings Inc. dba Example Home Services (EHS)": four scope lines, "Work will not be conducted
  during weekends", "EHS will provide a written warranty of five (5) years" (a deliverable, not on file), the Notice to Owner
  printed, a CSLB number with no board named, both signature blocks blank (an unsigned copy).
- **A sprinkler inspection proposal:** three options (five-year, annual, quarterly) whose marks the text could not place, read from
  the page layout as annual and quarterly chosen; "in strict accordance with NFPA 25 (2013 California Edition)" and Title 19; the
  report to the owner and the fire authority owed after each inspection; signed by a director with title and date.
- **A paving proposal** with an "Exclusions:" list (permits, engineering, base repairs), an alternate at extra cost, and "warrants
  its workmanship for one (1) year from completion".
- **An owner's property-management agreement** that reached the association's files: `KindVerdict` "disagrees", third party
  (property management), "the association is not a party".

## What the design must keep

- **The words come first.** Every term, scope item, warranty, and finding shows the contract's own words, whole or expanded on
  request, with its section; any reading follows, labeled (`ReadingLabel`). A summary never stands in for the quote.
- **A finding is a lead, not a determination.** No word on screen says "illegal", "unenforceable", "void", "breach", or "you must".
  A finding says what the words do and what to read beside them ("a notice outside either edge may not count", "whether it shortens
  the statute's four years is a question for counsel"), with the statute recited, not paraphrased.
- **Whose duty it is, as read.** A party the words name is shown plainly; a party jason infers (a passive duty in the vendor's own
  form, a line under a role label, a "will" sentence) carries its reading note, and "unstated" stays unstated until a person says.
  Never fill an unstated party by color or position.
- **Never a guessed tick.** An option the text cannot read is "not read", and the layout's reading names its source. The same for a
  signer, a date, and a warranty's holder: blank is blank.
- **The signed copy is the record.** An unsigned copy says so at the top, wherever it is shown.
- **The board's page is the license's record.** A `LicenseChip` shows what the paper printed and links out to check it; it never
  says "active", "valid", or "in good standing".
- **A model is a person's choice, and Bedrock is named as off the machine.** The `Confirm` for a remote model names the service and
  the person; a confidential file is refused unless allowed for that run; what the model proposed that is not in the text is shown
  as dropped, never merged quietly.
- **Nothing is sent or signed.** A notice of non-renewal is a draft a person sends (`DraftLetter`); "Track this" is a proposal
  behind `Confirm`; jason never signs, accepts, or rejects a proposal.
- **Privacy.** Contracts are association records (Civil Code 5200), but a confidential one (counsel's engagement, a settlement) is
  held back unless the role may see it. An owner's own lease or management agreement that reached the files is the owner's: it is
  set apart, never listed among the association's contracts, and never shown to another owner.
- **Amounts** are integer cents through `Money`; a fee schedule's figures are the contract's, not the books'.
- **Words on screen** follow [content/style.md](content/style.md); **WCAG 2.2 AA** as in
  [components.md](components.md#accessibility): every kind, party, verdict, and severity is a word; the notice window has a text
  equivalent ("Notice may be sent from March 3 to May 2, 2027, by certified mail"); topic groups are disclosure buttons; the terms
  list is a list, filters are a labeled group; a print layout for the one-contract review.

## Decisions for the design

1. **Where it lives.** Contracts under Records, Vendors as its own item, or one Vendors screen with each counterparty's
   agreements inside? A management agreement is both a contract and the manager's mandate.
2. **Density.** A management agreement reads to about 300 terms. Choose the default view: what is owed, notice, and findings first
   with the terms collapsed by topic, or a two-pane reader (the document on one side, the terms on the other, linked by place).
3. **The reading beside the document.** Clicking a term opens the PDF at its words (`DocumentViewer` with a highlight), or the
   unwrapped text? The offsets are into the unwrapped text today; a page anchor is a backend decision this can drive.
4. **Showing an inferred party.** A dotted outline, a superscript "as read", or a word after the party? It must survive a print and
   a screen reader.
5. **The notice window.** A horizontal band on a calendar strip, or a sentence with two dates and a `DueDate`? Both edges and the
   delivery must be visible at 360px.
6. **Comparing agreements.** Two managers' agreements side by side by topic (term, notice, fees, records at transition) for a
   board choosing between them. In this pass or the next?
7. **From what is owed to a register.** A deliverable the board wants tracked becomes a register row or a board item. Design the
   proposal and where it lands.
8. **The review as paper.** A two-to-four page print of one contract's review for a board packet: header, findings with their
   statutes recited, what is owed, notice, then the terms by topic.
9. **The kind question.** When the name says "vendor agreement" and the words say "an owner's lease", how much of the analysis the
   manager sees before answering.

## Not part of this pass

- The backend. The loaders are proposed, not built: `GET /api/contracts` (from `data/contracts/terms`, `contract_terms.load`),
  `GET /api/contracts/<key>` (one reading, with `NoticeWindowView` composed from the term's window and the term's end),
  `GET /api/licenses` (`data/parties/licenses.json`), and `POST /api/write/contracts/read` (queues `jason contract-terms` as a
  job, the model chosen by the person). The CLI does all of it today (`jason contract-terms`, `jason licenses`,
  `jason ingest --terms-model`).
- Matching a deliverable to a document on file, and a warranty's end date from a completion on record: proposed loaders over the
  library and the books.
- Drafting a notice of non-renewal or termination (`DraftLetter` and its template are the existing path).
- Any statement of what a clause means beyond what is recited from it; the questions for counsel.
