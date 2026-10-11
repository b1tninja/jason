# Handoff: mail workbench and payment attachments

For a design pass on two manager workflows that today are mostly CLI and MCP, with thin read-only console surfaces. Behavior is settled by existing specs and tools; this page says what the **console** should look like, what it must not invent, and what the agent proposes when a match fails.

Related (do not rewrite them; link and extend):
- [handoff-conversations-and-policies.md](handoff-conversations-and-policies.md) — conversations, handoffs, response standards
- [handoff-draft-from-item.md](handoff-draft-from-item.md) — “Draft an email” from a lead
- [handoff-followups.md](handoff-followups.md) — campaign follow-ups (forms), not vendor invoice gaps
- [screens/mail.md](screens/mail.md), [screens/finance.md](screens/finance.md)
- CLI and stores: [../gmail.md](../gmail.md), [../invoices.md](../invoices.md), `jason sync-bills`, `jason invoices --fetch`, `jason sync-tax`, `jason vendors`

Nothing below is built as a single workbench yet. `#/inbox` lists threads awaiting us (headers; “Open in Gmail”). `#/payments` shows invoice findings read-only. Sync and attach stay terminal until an approvals kind exists.

## The idea in six sentences

1. **Mail workbench.** The manager reviews association email as conversations (headers first; bodies only when a draft or signature path needs them), sees whose move it is, and can ask jason for a **follow-up plan** or a **Gmail draft** — jason never sends.
2. **Payments workbench.** PayHOA’s unapproved expense transactions drive a **sync → match → attach** loop: only the portals that have pending transactions are synced; a PDF attaches only on a unique amount-and-date match.
3. **Agent proposes, person confirms.** Every sync, attach, and draft is a plan with evidence. The console shows the plan first; the terminal’s `jason sync-bills` has **no `--yes`** and uploads unless `--dry-run` is given (see “Checked against the code”), so the console never runs it from a click until a gate exists.
4. **No match is not silence.** When no bill or invoice is found — and when a transaction routes to no source at all — jason opens an **investigation card**: other sources to try, payment evidence already on disk, and a recommended next act (or “hold for a person”).
5. **County tax is not City utilities.** ACH from the tax collector must not route to the City’s bill portal; it is its own payee class, with its own source (the tax catalog), or it stays unmatched with an investigation.
6. **Caveats stay on screen.** “Awaiting us” can be wrong if someone answered by phone; a related payment or letter is a lead, not proof.

## Checked against the code (2026-10-10)

This page was written before the engine was read line by line. The corrections below are binding on the design; each is in the sections that follow.

| The draft said | The code does | What the design does |
|---|---|---|
| “Dry-run is the default” | `jason sync-bills` uploads unless `--dry-run`; it has no `--yes` (`--approve` is a separate opt-in). | The console shows a dry run as the plan, always first. The terminal command it copies is the **dry run**; the live one is a person's, typed. **Build:** `sync-bills` needs a `--yes` for uploads, as every other write has (`owner-info --apply --yes`, `mailroom --send --yes`); until then it must never be scheduled (`scheduler.WRITES_REFUSED` keys on `--yes`, so it would not refuse it). |
| `--dry-run` “without portal sync or uploads” is a local read | It still reads PayHOA live: `iter_transactions` then `get_transaction` for every routed transaction. | The queue is **not** read from a dry run on load. It is derived from the stored snapshot (`data/payhoa/transactions.json`, written by `jason invoices --fetch`, with its `syncedAt`), routed offline (`BillSourceRegistry.route` calls only the profile's rules). A live dry run is a job or a terminal command whose result is kept and shown with its age. |
| Transactions that no source owns appear as `unmatched` | They are **dropped silently**: `list_pending_utility_transactions` and `attach_bills` both `continue` when `route()` is `None`. | A county ACH that no rule owns never reaches “no match”. The engine gains an **unrouted** class (below) so the queue can list it and open an investigation. This is the design's main build item. |
| “Match: amount (cents) + `bill_date` or `due_date` within ±N days” | The SMUD source matches the bill date **or the due date**. The City source (`idoxs`) matches the **bill date only** (`need_matches_bill`). The window is 7 days by default (`--date-window-days`). | Say which date matched, per source. Do not promise a due-date match for every source. |
| “Unique match only; ambiguous = investigation” | The cache stage flags `ambiguous` (several distinct bills). The live resolve stage takes the **first** unused match, so a dry run and a live run can disagree. | The dry-run result is labelled “from the cache”; a live result that differs is shown as a difference, not hidden. **Build:** resolve must report ambiguity as the cache stage does. |
| Queue states: needs sync, matched, no match, already attached, skipped | `MatchResult.status`: `matched`, `uploaded`, `approved`, `skipped` (already attached), `ambiguous`, `no_match`, `error`. “Needs sync” is not a status; it is a source with a pending transaction (`sources_needed`). | Use the engine's words. Add `unrouted` and `stale` (see states). |
| Sources: `smud`, `idoxs`, `proactive`, `signalservice`, … | The registry holds `smud`, `idoxs`, then **each vendor portal the profile declares** (`vendor_portals()`). | Mocks use `smud`, `idoxs`, and plainly fake vendor keys (`example-alarm`). A profile's vendors are not named here. |
| County tax: “not a `BillSource` today — propose an adapter for the collector's portal” | `jason sync-tax` already stores each parcel's account, bill values, levies, **and the printed bill PDFs** (`TaxStore`, `bills_dir`). | A county-tax `BillSource` can be a thin reader over the `TaxStore` — no portal login at attach time. The portal adapter is only for a county whose tax adapter does not exist yet ([../placer.md](../placer.md)). |
| `sync-tax` works for any county | `sync_tax` takes a county tax office adapter (today one county's); another county needs its own. | The design says “the county tax catalog (when the profile's county has an adapter)”; otherwise the investigation says so and offers manual attach. |
| The routing fix is “treat as `county-tax`” in code | Routing is the profile's `transaction_rules()` (`TransactionRule`, matched by `first_utility`); `Utility` is a closed set. | The fix is **a new rule row and a new payee class**, not a branch in `is_city_sac_transaction`. A new decision is a new rule row (AGENTS.md); a miss stays a miss. |

## Personas and jobs

| Who | Job | Sees |
|---|---|---|
| Manager | Clear email awaiting us; keep PayHOA attachments current before the treasurer’s review | Both workbenches; runs the syncs at a terminal |
| Treasurer | Trust `#/payments` findings; approve attaches; chase missing invoices | Payments in full (amounts are P1), the investigation, outcomes |
| Director | Read counts and high-stakes threads; does not run syncs | Counts and the queue's totals; no bank notices, no body text |

Amounts and payees are P1; a bank notice, a mailed tax bill, and a thread's headers are P2 (`access.PATH_RULES`: `transactions/`, `mail/`, `gmail/`). An office that does not open P2 sees counts and “held” where a notice would be.

## Part A — Mail / conversations workbench

### Where it lives

| Screen | Route | Status |
|---|---|---|
| Inbox (today) | `#/inbox` | Built: open items; the email tab is “Email awaiting us” (`threadsAwaitingUs`: thread, age, likely needs a reply, past the usual time, reply rate) and Gmail links |
| Conversations (proposed) | Inbox → Conversations filter; detail `#/conversations/<id>` | Spec’d in [handoff-conversations-and-policies.md](handoff-conversations-and-policies.md); **not built** (no `gmail_catalog`, no conversation or handoff loader; [handoff-reconciliation-5.md](handoff-reconciliation-5.md#the-screens)) |
| Draft from item | Drawer or `#/draft?source=thread:<id>` | Spec’d in [handoff-draft-from-item.md](handoff-draft-from-item.md); the CLI has first cases (`jason draft --hearing / --proposal-request / --meeting-notice`, `--list`, `--show`, `--edit`) |
| Follow-ups (email) | Band on the conversation and the dock | Distinct from forms follow-ups; “ask again by DATE” |

### First cut: what can ship on what is built

The conversation detail waits on the Gmail catalog. The first cut is the **Inbox's email tab made a workbench**, on `open_items` (`threadsAwaitingUs`) and `email_threads`:
- the tab gains the sync age, a suggestion per row, and “Draft a reply” that opens the existing draft cases;
- a row opens a drawer, not a route, with the thread's headers, the leads, and the draft entry points;
- when the conversations loader exists, the drawer becomes `#/conversations/<id>` with the same parts.

### Flow

```
Sync Gmail (headers) → List conversations (awaiting us / them / notice)
    → Open conversation (ledger of messages, parties, related leads)
        → Suggest follow-up (date, why, command)
        → Draft reply (Purpose → Recipient → Compose → Before you save → Save to Gmail)
        → Mark handled offline (person names outcome; never auto)
```

### Components (reuse and gaps)

Built and reusable now: `Caveats`, `Command`, `Confirm`, `DataTable`, `Doc`, `DueDate`, `Findings`, `Pill`, `Stat`, `Tabs`, `RemoteView`, `Evidence`. **Spec’d, not built** (draw them from the built parts and say so): `ConversationList`, `MessageRow`, `HandoffCard`, `DraftFromItem`, `ComposedEmail`, `DraftTrail`.

Add for this cut:

| Component | Role | Data and states |
|---|---|---|
| `SyncBanner` | Last Gmail sync age; **Sync now** copies `jason gmail --sync --days N` (the same pattern as finance's “copy the sync command” until a job kind exists) | `syncedAt` of the Gmail store. States: fresh; **older than the integration's stale-after** (`gmail` cadence, `jason cadence`) → “last synced 3 days ago; what is awaiting us may be out of date”; never synced → the command and “no mail read yet”. The page runs nothing; the command is a read (Gmail scope) and writes only `data/gmail/` |
| `FollowUpSuggestion` | One line: action, proposed date, basis (response standard / past reply rate / stalled handoff), command | Basis is a word: `response standard` (a `ResponseRule`), `reply rate` (the sender's history, shown with its count: “replied to 4 of 5”), `stalled handoff`. A date counted from a number the board has not adopted carries **“proposed”** and no `Stamp`. With no basis, no date: “no usual reply time on record”. Fixed copy: “ask again by DATE” is a person's date once they accept it |
| `RelatedLeads` | Payments, paper letters, Drive filings, unit requests near the thread — labeled **leads** | Each lead: kind, label, why it is near (same amount, same sender, same unit), a `Doc` or link. Joined by sender and subject words, amount, or unit; **never shown as an answer** to the thread. P2 leads (a bank notice) show only to an office that opens P2 |

### Hard rules (mail)

- Headers by default; bodies only on explicit draft or signature paths ([../gmail.md](../gmail.md)).
- jason never sends; Save to Gmail only. A Gmail draft is a Google write the web layer does not make today: until a draft approvals kind exists, “Draft a reply” is a `Command` (`jason draft …`) the person runs, and the drawer shows the draft's trail after.
- Committing purposes (accept a bid, authorize work) need a recorded board decision ([handoff-draft-from-item.md](handoff-draft-from-item.md)).
- Owner PII never goes to a vendor recipient.
- The “awaiting us” caveat is always visible: “A thread is listed when the last message was not ours. Someone may have answered by phone or at a meeting; jason cannot see that.”
- “Mark handled offline” is the person's word with a name and date in a store of jason's own (append only); it never changes the Gmail thread, and a later message from the sender reopens it.

### Backend already usable

- `jason gmail --sync --days N`, `jason threads`, MCP `email_threads`, `reply_needed`, `email_intents`, `open_items`
- Draft CLI; a future approvals kind for Gmail drafts ([mvp.md](mvp.md) phase 3)

## Part B — Payments / bill attach workbench

### Where it lives

| Screen | Route | Status |
|---|---|---|
| Payments with questions | `#/payments` | Built read-only: budget, reconciliations, invoice findings (`/api/invoices`), collections |
| **Bill attach** (new) | `#/payments/attach` or a tab on `#/payments` (recommended: a tab, beside “Invoice review”) | Not built; wraps `sync-bills` and the investigation |
| Invoice review (existing band) | `#/payments` | After attach; `jason invoices --fetch` refreshes findings and the snapshot the queue reads |

### What the queue reads

Two sources, kept apart and each shown with its age:

| Source | What it is | Read how |
|---|---|---|
| **The snapshot** | Every PayHOA transaction as last fetched (`data/payhoa/transactions.json`, `syncedAt`), with its attachments listed | Offline. Routing is offline too. This is the queue, and it is as old as the last `jason invoices --fetch`. |
| **A dry run** | The engine's live result: for each routed transaction, `matched / ambiguous / no_match / skipped`, with the bill and where it was found | A job or the terminal (`jason sync-bills --dry-run`), PayHOA read-only; its result is kept (`data/bills/last-dry-run.json`, to add) and shown **with its age and the snapshot it ran against**. |

A queue row from the snapshot alone says “matched: not yet checked” (no claim); only a kept dry run says matched, ambiguous, or no match. If the snapshot is older than the stale-after, the whole queue says so first.

### Flow (PayHOA-first — same as the CLI)

```
1. List unapproved PayHOA expense transactions               (snapshot, offline)
2. Route each to a payee class and, where one owns it, a BillSource   (offline; the profile's rules)
       smud | idoxs | <a declared vendor portal> | county-tax | unrouted
3. Sync only sources that still have a pending transaction with no attachment   (job / terminal; read-only)
4. Match: exact amount (cents), the source's date within ±N days; unique only
5. Upload the PDF to the PayHOA transaction (the PDF downloads lazily)           (the write)
6. On no_match, ambiguous, or unrouted → InvestigationCard (Part C)
7. Optionally refresh the invoice review (download missing attachments; check amounts)
```

Steps 1-2 are the page. Step 3 and the dry run are reads a person starts. Step 5 is the only write, and the only step behind a gate.

### Routing: a payee class is a rule row

Routing is the profile's `TransactionRule` rows (description pattern, category, the utility they select), applied in order by `first_utility`; **a miss stays a miss**. Today a rule can only select a `Utility` (a closed set). The design needs the engine to say what a transaction is when no source owns it:

- **`PayeeClass`** (closed set, general): `electric-utility`, `city-utility`, `field-vendor`, `insurance`, `county-tax`, `platform-fee`, `unknown`. A rule row carries one; the profile's rows say which description text selects which class. The county tax collector's ACH text is **a rule row in the profile**, never a pattern in general code.
- **`unrouted`** is the engine's result when no row matches: the transaction is still listed (amount, date, description, category, vendor, attachments), with class `unknown` and the investigation open.
- A transaction a rule selects for a class with no `BillSource` (`county-tax` until its reader exists; `insurance`) is **routed, with no source**: the queue shows the class and the investigation's first step, not “needs sync”.

### Layout sketch

```
+----------------------------------------------------------------------------------+
| Bill attachments            PayHOA snapshot Oct 9 · last dry run Oct 9 (against it)  |
| [Copy dry run]  [Copy sync + attach]   Unapproved without a PDF: 24                  |
| Sources needed: idoxs, smud, example-alarm        County tax: 1 · unrouted: 2         |
+----------------------------------------------------------------------------------+
| QUEUE (unapproved, routed)                                                          |
|  Oct 9  City ACH         $28.26   idoxs        matched (cache) → [Attach]           |
|  Oct 7  Electric         $61.29   smud         matched (due date) → [Attach]        |
|  Oct 7  County ACH       $363.57  county-tax   no source yet → Investigation →      |
|  Oct 5  ACH (unknown)    $412.00  unrouted     Investigation →                      |
+----------------------------------------------------------------------------------+
| SELECTED TRANSACTION                                                                |
|  Evidence: bank description · category · existing attachments                       |
|  Candidates: 0 / 1 / many bills with why (amount, which date matched, account)      |
|  Investigation (if empty): sources tried · next to try · payment proof found        |
+----------------------------------------------------------------------------------+
```

### Components

| Component | Role | Data and states |
|---|---|---|
| `PendingUtilityQueue` | Unapproved transactions with class, source, amount, date, status | One `DataTable`. Status words: `not checked`, `matched`, `ambiguous`, `no match`, `already attached`, `uploaded`, `error`, `unrouted`, `no source yet`. Amounts right-aligned, integer cents shown as dollars. Filter by source and status; sort by date. Empty: “No unapproved transaction without a PDF in the snapshot of DATE.” Stale and missing snapshot: first row of the page, with `jason invoices --fetch` |
| `SourceSyncStrip` | Per source: last sync summary (accounts, bills new, PDFs) | From each source's own store stamp (`syncedAt`, `sync_runs`), as the Status screen reads sources; “never synced” and “failed (the command)” are states. Reads no portal |
| `MatchPanel` | The chosen bill, PDF preview via `Doc`, attach Confirm | Shows exactly what the engine would upload (file name, bill id, bill date, which date matched, amount) beside the transaction. Confirm text: “Upload BILL.pdf to transaction N (AMOUNT, DATE) in PayHOA, in the name of NAME. PayHOA marks nothing approved.” **Attach is a `Command` until an approvals kind exists.** |
| `InvestigationCard` | See Part C | |
| `InvoiceGapList` | From `invoice_review`: no attachment / wrong invoice / amount not on PDF — with vendor portal copy when known | Built data (`/api/invoices`, `problems_only`); a row's “Investigate” opens the same card for a payment already approved |

### Actions and CLI parity

| UI control | CLI / engine | Note |
|---|---|---|
| Dry run | `jason sync-bills --dry-run` | Reads PayHOA live; no portal sync and no upload. A copied command |
| Sync and attach | `jason sync-bills` (or `--source X`) | **Uploads to PayHOA.** Copied only on the plan's own row, after a dry run, with the person's name; never scheduled |
| Cache only | `jason sync-bills --skip-sync` | Attach from local caches, no portal read |
| Refresh invoice store | `jason invoices --fetch` | Rewrites the snapshot the queue reads |
| Vendor portal sync | `jason vendors --sync` / `--verify` | Portal sign-in at a terminal |
| County tax catalog | `jason sync-tax` | A read of the county tax office for the profile's parcels |
| Utility digests | `jason fetch-bills`, `jason utilities --payments` | Downloads and payment history |

Until an approvals kind exists the UI shows `Command` and copy; with `--allow-apply` later, Confirm and `--by`.

### Hard rules (payments)

- Exact cents; ± window on the date the source matches on (the issue date; for the electric utility also the due date, since its bank payments often align with it). Say which.
- Unique match only; ambiguous = investigation, not attach.
- Never auto-approve the PayHOA transaction unless the person opts in (`--approve`). The console does not offer it in the first cut.
- Utility payments stay out of the general invoice amount check ([../invoices.md](../invoices.md)); county tax is not the City's bill portal.
- Amounts are integer cents everywhere.
- A PDF that does not match is never attached to “get it off the list”.

## Part C — Investigation when no invoice or bill is found

### Principle

A `no_match`, an `ambiguous`, an `unrouted`, or a routed-but-sourceless transaction is a **work item**, not a log line. jason lists what it already tried, what else could hold the document or **proof of payment**, and one recommended next step. The person chooses; jason does not invent a PDF.

### What is offline and what is not

Every search the card makes on load is a read of a store already on disk, with that store's age. A search that would need a portal, Gmail, or PayHOA is a **proposed command**, not something the card runs.

| Search | Reads | Offline |
|---|---|---|
| Payee class and routing | the profile's transaction rules against the stored description | yes |
| Tax catalog | `TaxStore` (`tax.db`): accounts, bill values, due and delinquent dates, bill PDFs | yes (as old as `sync-tax`) |
| Library | printed bills and tax statements the association kept (`library_search`, financial tax model) | yes |
| Paper mail | `mail_brief`: scans, senders, kinds | yes |
| Payment evidence | Gmail headers (subject and sender, **not bodies**) for the amount; a bank export under `transactions/`; the same attachment on another transaction | yes |
| Vendor portals | `data/vendors/<key>/reports.json` and the ledgers | yes (as old as `jason vendors --sync`) |
| Parcel list | the secured roll (`sync-secured`) | yes |
| County or vendor portal itself | the live site | **no**: a proposed human step or command |

### Data shape

```ts
interface Investigation {
  transactionId: number;
  amountCents: number;
  date: string;                 // ISO date
  description: string;
  routing: { payeeClass: PayeeClass; source: string | null; byRule: string | null;   // the rule row that selected it, null if none
             wasRoutedAs?: string };                                                  // what an earlier run chose, if different
  tried: { source: string; result: "none" | "near" | "ambiguous" | "not read";
           readAt: string | null; note: string }[];                                  // every store searched, with its age
  candidates: {
    kind: "bill" | "receipt" | "bank-notice" | "mail-scan" | "portal-invoice" | "tax-catalog";
    label: string;
    amountCents?: number;
    date?: string;
    dateMeaning?: "bill" | "due" | "sent" | "delinquent";
    confidence: "exact" | "near" | "lead";   // exact = amount and date in window; lead = a subject or a name only
    evidence: "document" | "payment-proof";   // a bill is a document; a bank notice only proves payment
    why: string;
    doc?: DocRef;                             // P2 items only for an office that opens P2
    link?: string;                            // Gmail / portal / CLI hint
  }[];
  recommend: { action: string; command?: string; reason: string };
  outcome?: { kind: Outcome; by: string; at: string; doc?: DocRef; note?: string };   // the person's word, append only
  asOf: string;
  caveats: string[];
}
type Outcome = "attached-bill" | "attached-receipt-only" | "not-our-bill" | "waiting-for-mail" | "escalated";
```

Differences from the first sketch: `routing` carries the rule that decided (a miss shows `byRule: null`, which is the design's cue to propose a rule row); `tried` carries each store's age; a candidate says whether it is a **document or only proof of payment**; and the person's outcome is recorded, not implied.

### Case study: county tax ACH (made-up)

**Setup (fake).** Unapproved PayHOA payment $363.57 on 2026-10-07; the bank description names a county tax collector ACH, not City utilities. An earlier routing sent it toward the City portal and nothing matched. Gmail headers show a bank notice “You sent $363.57…”.

**Sources the agent proposes (in order):**

| Priority | Source | What it gives | jason already |
|---|---|---|---|
| 1 | **Re-classify payee** | A county tax collector is not City utilities | A rule row in the profile; until it exists the card says “no rule selects this payee: propose one” |
| 2 | **The tax catalog (`sync-tax`)** | Secured tax bills for the community's parcels: bill number, amounts, due or delinquent dates, **and the printed bill PDF** | `TaxStore`; MCP `tax_account`, `tax_search`, `secured_*` |
| 3 | **Library printed bills** | Common-area tax PDFs the association kept | financial tax models / library |
| 4 | **Paper mail** | A “property tax bill” or collector letter | `mail_brief`, mail triage |
| 5 | **Bank or Gmail payment notices** | “You sent $X” / bill-pay confirmations — **evidence of payment**, not the tax bill | Gmail headers and subjects; a body only if a person asks |
| 6 | **The county tax collector's portal** | The authoritative bill PDF and account history | Not read by jason; a manual download, or an adapter declared in [../adapters.md](../adapters.md) |
| 7 | **PayHOA or bank export already on disk** | An attachment on another transaction; a monthly export under `transactions/` | `invoices --fetch` reuse paths |
| 8 | **Secured roll / parcel list** | Which parcel the bill is for; owner-of-record can lag a sale | `sync-secured` |

**Recommended act (wording for the UI):**

> This looks like a **county tax collector** ACH, not City utilities.
> **Tried:** the City portal's amount match — none.
> **Found:** a bank payment notice in Gmail for the same amount (a lead: payment sent; not the bill).
> **Next:** (1) `jason sync-tax`, then look for this amount near this date in the catalog; (2) check scanned and unscanned mail for a property tax bill; (3) if the catalog has the bill line but no PDF, download it from the county's site or attach the mailed bill; (4) if only proof of payment is needed for review, link the bank notice and record “receipt only; bill PDF still missing”.

**What not to do:** attach a City utility bill, invent a match on a close electric amount, or treat the bank email as the tax bill.

### Investigation playbook by payee class

| Class | Primary document source | Payment evidence | Fallback |
|---|---|---|---|
| Electric utility | Utility portal cache | ACH description + due date | Digital bill email (rare) |
| City utilities | City bill portal (`idoxs`) | ACH | — |
| Field vendors (pest, alarms, …) | Vendor portal (`jason vendors`) | ACH + the portal's payment ledger | Email invoice filed to Drive |
| Insurance | Agency email / signing service / mail | ACH / check | `#/insurance` letters |
| **County tax** | `sync-tax` + the collector's site + mail | Bank “payment sent” email, check image | Library prior-year bill |
| Platform fees | Often none expected | Ledger | Group “no attachment” by payee (already in invoice review) |
| Unknown ACH | Investigation: contacts + a Gmail header search by amount | Bank notice | Hold for the treasurer |

### Agent “propose what I would do” panel

For the console (and for an MCP agent), a fixed checklist, always in this order:

1. Name the payee class from the bank description, and say whether a rule selected it (and which) or none did.
2. List the stores already searched, each with its age, and whether the amount ± window was searched.
3. Search **payment evidence** (Gmail subject amount, a bank export, a duplicate attachment).
4. Search **document stores** (tax catalog, mail, vendor portal, library).
5. Propose **one** next command or human step (a portal login, a request for a scan, a rule row for the profile).
6. Offer the outcomes a person can record: `attached-bill`, `attached-receipt-only`, `not-our-bill`, `waiting-for-mail`, `escalated`.

The outcome is stored (`data/bills/investigations.json`, to add: append only, with who and when). A later sync that finds the bill reopens a `waiting-for-mail` or `attached-receipt-only` card as “a bill now matches”.

## States (both parts)

| State | What the page says |
|---|---|
| Snapshot missing | “No PayHOA snapshot. `jason invoices --fetch` reads it.” The queue is empty and says why; no count, no zero |
| Snapshot stale | The page's first line: “The snapshot is N days old; a transaction made since is not listed.” The age uses the PayHOA integration's stale-after |
| Dry run older than the snapshot | “The last dry run is older than the snapshot; run it again.” Its matches are shown greyed |
| Source never synced | The source's chip says “never synced” and the command; its transactions show `not checked` |
| Source failed or not signed in | The Status screen's standing word and fix (`failed`, `not signed in`), not a retry button |
| A store the investigation needs is missing | That row of `tried` says `not read` with the command that fills it; the card still lists the others |
| No unapproved transactions | “Nothing waits on a PDF in the snapshot of DATE.” Never “all caught up” |
| Admin viewing as someone else | Reads only; “Copy” buttons stay, nothing writes |

## Privacy

- Owner addresses are never stored or shown (party labels: “owner of UNIT”).
- Amounts and payees are P1; a bank notice (header), a mailed tax bill, and an attachment are P2: an office that does not open P2 sees the lead's kind and amount-match word without its subject, sender, or file.
- Opening an attachment is a logged `Doc` view (P2).
- Tax bills and bank notices can carry parcel or account numbers — mask in lists; full PDF on click.
- Executive or counsel threads: hold or board-only (same as the conversations handoff).
- The investigation's `tried` and `candidates` carry names and amounts, never a body, never an address.

## Where it goes

Routes are proposed, consistent with [information-architecture.md](information-architecture.md#where-the-proposed-screens-go); none of the new attach or conversation detail routes exists yet. Loaders are keys, read through `GET /api/<key>` (the built pattern); the writes are `POST /api/write/<store>/<key>`.

| Screen | Group, route | Loader to add | Wraps |
|---|---|---|---|
| Conversations (extends Inbox) | Overview, `#/inbox` filter + `#/conversations/<id>` | as [handoff-conversations-and-policies.md](handoff-conversations-and-policies.md) | `email_threads`, `reply_needed`, `open_items` |
| Draft from thread | Drawer / `#/draft?source=thread:<id>` | as [handoff-draft-from-item.md](handoff-draft-from-item.md) | `jason draft` |
| Bill attach | Money, a tab of `#/payments` | `bill-attach` (`?source=`, `?status=`): the snapshot's queue, routed offline, with the kept dry run beside it and each store's age | the snapshot, `BillSourceRegistry.route`, the kept dry-run result |
| Investigation | the same tab, a drawer | `bill-investigation` (`?tx=`): the card above | the offline stores in the table; writes the outcome only |
| Outcome | — | `POST /api/write/bill-investigation/<tx>` `{outcome, doc?, note?}`: the signer's name, append only | `data/bills/investigations.json` |
| Invoice gaps (band) | Money, existing `#/payments` | `invoices` (built) | `invoice_review`; refresh via `Command` for `jason invoices --fetch` |

### What the build adds (in this order)

1. **`PayeeClass` and an `unrouted` result** in the engine, so a transaction no source owns is listed instead of dropped; the profile's rule rows carry the class. (Pure code and tests; no network.)
2. **`sync-bills` gains `--yes` for uploads** (a dry run needs none), so it joins every other write and the scheduler's guard covers it. The resolve stage reports ambiguity as the cache stage does.
3. **A kept dry run** (`data/bills/last-dry-run.json`: the results, the snapshot's `syncedAt`, the date window, when and by whom) written by `sync-bills --dry-run`.
4. **`bill-attach` and `bill-investigation` loaders** over the snapshot, the kept dry run, and the offline stores; the investigation helper (`jason.tasks.bill_investigation`), pure over stores.
5. **A county-tax `BillSource` over `TaxStore`** (where the profile's county has a tax adapter), so a catalog bill with its PDF attaches like any other.
6. **The outcome store and its writer**, then an approvals kind `payhoa-attach-bills` (plan = transaction → PDF), parallel to `owner-info-tags`.

## Approvals and writes

| Act | Risk | Gate |
|---|---|---|
| Sync portals (read) | Low | Job or terminal; no PayHOA write |
| Live dry run (PayHOA read) | Low | Job or terminal; its result is kept |
| Attach PDF to PayHOA transaction | Medium | `--yes` and `--by` at the terminal; later Confirm + `by`; optional second person |
| Approve PayHOA transaction | Higher | Explicit opt-in (`--approve`); default off; not offered in the first cut |
| Save Gmail draft | Medium | `jason draft` at a terminal; later Confirm + `by`; never send |
| Record an investigation outcome | Low | The signer's name; append only; changes nothing outside jason |
| Mark conversation handled offline | Low | Person names outcome |

Prefer one approvals kind later: `payhoa-attach-bills` (plan = list of transaction → PDF), parallel to `owner-info-tags`. Until then, the screen shows the terminal command.

## Sample data (made up)

- **Thread:** “Parking permit” — awaiting us, age 0, owner of 123 Main St, likely reply, related pending PayHOA request.
- **Transaction A:** City ACH $28.26 → `idoxs` → matched from the cache (bill date) → attach.
- **Transaction B:** electric ACH $61.29 → `smud` → matched on the **due date** → attach.
- **Transaction C:** county tax ACH $363.57 → class `county-tax` (rule “Example County Tax Collector ACH”), no source yet → InvestigationCard: tax catalog lead + Gmail “You sent $363.57” lead (payment proof, not the bill) + recommend `jason sync-tax` / mail / the county's site.
- **Transaction D:** ACH with no matching rule, $412.00 → `unrouted` → InvestigationCard, class `unknown`, “no rule selects this payee: propose one”.
- **Transaction E:** `example-alarm` $150.00 → two bills of the same amount in the window → `ambiguous` → investigation lists both and attaches neither.

## Open design decisions

Each with a recommendation; the first four are the treasurer's or the board's, not jason's.

1. **One workbench or two?** Two entry points (Mail vs Payments) sharing `DraftFromItem` and `InvestigationCard`, not one mega-screen. **Recommended.**
2. **Does attach live behind approvals from day one, or Command-copy first?** Command first ([mvp.md](mvp.md)); the approvals kind in a later money phase.
3. **County tax `BillSource`:** a reader over the `TaxStore` (the PDFs are already kept) first; the collector's portal only where no tax adapter exists. **Recommended.**
4. **May a bank “payment sent” email satisfy the treasurer's monthly review** when the bill PDF is still missing, or must the bill always be attached? A policy for the board or the treasurer; jason does not invent it. Until it is written the outcome `attached-receipt-only` is recorded as such and the invoice review keeps the transaction listed.
5. **Gmail bodies in the conversation screen:** never / only for draft / only with “Show message”? Headers-first is the current product rule; keep it.
6. **Where does a person's “propose a rule row” go?** To the board's action register as a finding, not a code change; once the profile owner adds the row, the transaction routes. Recommended.
7. **Should `sync-bills` ever run on a schedule?** No: it uploads. A scheduled **dry run** (read-only) with the result kept is reasonable once the kept result exists; a person adopts it in `jason cadence` like any source.

## Acceptance criteria (first cut)

**Mail.** From `#/inbox`, the manager sees awaiting-us after the sync age (with a stale warning past the integration's limit); opens a thread's drawer; gets a follow-up suggestion with its basis (or “no usual reply time on record”); can start the draft case; a draft saves only by the terminal command (later Confirm); the caveat is visible.

**Payments.** The queue is built from the snapshot, shows its age, and lists every unapproved transaction without a PDF **including unrouted and county-tax ones**; a kept dry run adds matched, ambiguous, and no match per row with the date that matched; a county ACH opens the InvestigationCard with tax-catalog, mail, and bank-notice leads, each with its store's age; ambiguous attaches nothing; the outcome is recorded with a name and can be changed only by a later outcome; the invoice review band still works after `--fetch`.

**Tests.** Fake data only; no live PayHOA, Gmail, or portal in unit tests; the profile boundary tests unchanged: no profile vendor, county, or collector name in general code or docs.

## What the design must keep

- Local-first; nothing on load calls PayHOA, Google, or Keeper ([README.md](README.md) principles).
- A reading or match is a lead ([content/style.md](content/style.md)).
- jason never sends mail and never mails a letter on its own initiative ([AGENTS.md](../../AGENTS.md)).
- General docs and samples use plainly fake names (“123 Main St”, “Example County”), never a profile's facts ([AGENTS.md](../../AGENTS.md)).
