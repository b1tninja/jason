# The console handoff's fifth cut, reconciled with what is built

The design agent's fifth cut (2026-10-10, `Jason UI5.zip`) adds fourteen screens to the console, built from the specs synced after the fourth cut: Conversations, Policies, Service, Requests, Contracts and Compare, Community facts, My unit manual, Paint, Title history, Life safety, Governing documents, the Reference shelf, and Instance and integrations. Its `FIFTH-CUT.md` maps each to its spec.

Five readers checked the screens against their specs, the repo, and the statutes on disk (`data/authorities`). This page is for both readers, as [handoff-reconciliation.md](handoff-reconciliation.md) is:
- **the design agent:** what to change, and why;
- **the build:** what is built, what each screen assumes that is not, and what to add.

It answers [handoff-reconciliation-4.md](handoff-reconciliation-4.md) and extends [design-brief-forms.md](design-brief-forms.md).

## In one paragraph

The screens are sound as layouts and as copy. The components they use exist, and their prop names match the built ones. The caveats, the labels on readings, the "a lead, not a finding" wording, the "nothing on this page sends" notes, and the states drawn apart are the right ones, and most can be adopted as they stand. What the cut gets wrong is what earlier cuts got wrong:
1. **Nearly every screen is a fixture.** Only the Facts, Status, Instrument graph, and the five inspection loaders have routes. Conversations, Policies, Service, Requests, Contracts, Instance, Life safety, Title history, and Paint's building table have none. Each screen carries its own data and its own writes.
2. **The browser is given writes the build does not have.** A button flips local state and the screen says "in Approvals" or "saved to Drive".
3. **Law and rule text is paraphrased, partial, or invented.** Several statute recitations are wrong; clocks and amounts are shown as the rule where they are the board's to set.
4. **"Today", dates, owners, and counts are written into the templates.**
5. **Command strings, integration keys, vault paths, and state words are invented,** so a person who copies one gets an error.

## Corrections for the design agent

### Law and rules (checked against the stored text)

1. **Recite, then label.** No screen uses `Recitation` or `ReadingLabel` for its statute text; they paraphrase. These recitations differ from the stored copy:
   - **Civil Code 5665.** The screen cites 5665(c) and "within 45 days of the request". The stored text is 5665(b): the board meets with the owner "within 45 days of the postmark of the request, if the request is mailed within 15 days of the date of the postmark of the notice". The condition and the postmark basis are the operative words.
   - **Civil Code 714(e)(2)(B)** (solar). "Deemed approved" drops "unless that delay is the result of a reasonable request for additional information", which is the statute's own pause.
   - **Civil Code 5210(b).** "30 days for earlier years" overstates (b)(2): "the previous two fiscal years", "within 30 calendar days". (b)(1) is "the current fiscal year", "within 10 business days". Which record belongs to which paragraph is a reading, and the screen asserts it as a fact (the "2025 reserve study" row).
   - **Civil Code 4041(e).** "Asks that the notice be resent by mail" is a reading. The text: the association "shall resend the notice to a mailing or email address identified by the member pursuant to Section 4040".
   - **Civil Code 4360.** "Notice of the text and its purpose before the vote" drops the 28 days and the emergency exception in (a) and (d).
   - **Civil Code 5850.** The fine bound omits (c)'s cap and (d)'s health-and-safety exception.
   - **Civil Code 5205.** "No more than actual cost" omits (g)'s charge for redaction.
   - **Civil Code 5650(b)(2)-(3).** The late charge and the interest are limits ("not exceeding"). The declaration may set less. The screen shows them as the adopted values.
   - **Civil Code 5610** is the emergency exception to assessment increases. The Policies screen cites it for spending authority, and [policy-catalog-design.md](../policy-catalog-design.md) has the same error (corrected below). **Civil Code 5105(b)** is cited for candidate qualifications, which are in (a)(3), subject to (b). **Civil Code 4080** is cited for the articles; it defines "association".
   - **19 CCR 904.1(a)** is quoted as "sprinklers shall be inspected… per NFPA 25", graded `official`. The stored regulation text says a license is not required for inspections. A false recitation at the top grade is worse than none.
   - **Contracts:** "Notice to Owner" is cited to "Civil Code 8000-8848", which the shelf does not hold ([statutory_notices.py](../../src/jason/community/statutory_notices.py) says so). The arbitration check cites 5925-5965 where the reader cites CCP 1281, and "records at transition are owed to the association" is attributed to 5200-5240, which is the member's right to inspect.
   - **Facts:** "a policy on a 4355(a) subject needs member notice" is applied to a deductible-allocation guideline, which is not one of the seven 4355(a) subjects.
   - **NFPA 72 and NFPA 13D** words in Life safety are not on disk; they are shown as quoted text with a grade. A reading from secondary sources is graded and labelled so ([fire-protection.md](../fire-protection.md)).
2. **A clock from the documents is not the board's to be assumed.** Service shows the architectural review as "CC&R: 30 days, recited from the documents". The documents state no time (Civil Code 4765(a)(1) asks the procedure to state a maximum), so 30 days is a proposed policy. This is the board's open question shown as settled. Show it as "proposed, not adopted; no clock". The complaint answer ("15") and the review-window dates are the same.
3. **Amounts the board sets are not facts.** The adopted-looking rows in Policies (the spending threshold, the first fine, one written warning, 14 days to cure, the late-charge terms) and the CC&R section numbers beside them are invented. A fixture row says "sample" in words on screen, as `FIFTH-CUT.md` promises. No screen does.
4. **Invented clocks.** Life safety's "report within 15 days of the test" and "within 30 days of the notice" are not the program's; the notices have their own clocks ([cross-connection-control.md](../cross-connection-control.md)). Contracts' notice-window geometry is hard-coded percentages. The follow-up days in Requests (F-1 "2 days late", F-2 "14 days before") are not the build's proposed days (remind 7 before, resend 3 after the outcome is read), and F-5's "Nov 5" is later than the law allows: Civil Code 4041(b)(1) asks answers 30 days before the annual reports.
5. **The reserve study and the policy conditions are quoted from the stored copy, whole.** The insurance condition in Life safety quotes one prong of two. A partial quote of a condition is not "recite whole". The red banner states an impairment is open as a fact; "impairs" is a person-confirmed field, so the banner is labelled.
6. **The Reference shelf sample contradicts the shelf.** Its gap rows mark sections held on the shelf (5105, 5650, a corporations section) as not found or renumbered, and the proposal text is not the spec's "A; B" form. Build the sample from real standings.

### What the browser may do

7. **Every write in a template is in-memory.** "I did this", the arrival Confirm, "Take it to the board", "Draft the board item", "Draft a reply", "Track this", "Add a report", and the deficiency actions change local state; the Confirm text then says the result is in Approvals, in Drive, or in the dock. Until the route exists, each is a `TerminalStep` (the `Command` component with the real command), as the specs say. The summaries name the person (`--by`) and the signed-in name is the session's, never a literal in the template.
8. **A Gmail draft is a Google write the web layer does not do.** "Draft a reply" and "Draft a follow-up" invent an approvals record at a Drive path with a `.docx`. A reply is `responses.make_reply` at a terminal (a Gmail draft), or a letters transition for a Doc ([handoff-reconciliation.md](handoff-reconciliation.md), item 20: a Google Doc plan a person applies, the approver from the roster, never "the manager").
9. **Dates and owners come from the duty and the board.** A dock task takes its owner from the duty and its due date from the board's lead time (item 12). Contracts' "Track this" (a named owner, a fixed date), Paint's task, and Conversations' register task each break that. The seven-day figure is jason's default and is labelled so.
10. **Bedrock is a terminal act until it is gated.** Contracts' "Queue the reading" with a remote model sends the association's contract text to a cloud service from a click, with no confidential-file refusal, no signed-in name, and no preflight.
11. **Interior colour reports are the owner's act.** Paint lets a manager enter an owner's report and shows the reporter ("Unit 4, 2026-08") and the contractor's name. The spec shows a confirmation count only and never a contractor.
12. **A deficiency is cleared only by a linked record,** and the loader refuses a subject line. Life safety decides this in the client (`opt.ok`), and "Record insurer told" stamps a pre-written email the person never picked. Under the legal hold the store is append-only with `by` and `at`.
13. **Facts' "Assemble the packet"** claims "saved to Drive" with the president as approver. The packet is a read (`GET /api/loss-packet/export`), and each step of the ladder is confirmed by a person (`POST /api/write/loss-packet/confirm`).
14. **A negative search is evidence, so it needs a job.** Title history's "Look it up" returns "not found" at once. "Pin this association" has no endpoint: pins are profile code today.
15. **Promises the system does not keep.** The unit manual says the board "cannot change" a shared entry and that it "adds nothing to resale disclosures". Both are open decisions in [unit-records-design.md](../unit-records-design.md); check the statute before promising privacy or retention.
16. **"Draft a note to the agent"** (Life safety) is inert and in no spec. Remove it, or add it to the spec.

### Privacy and facts

17. **The profile's own name is still in the package.** It is a prop default, a data namespace, the whole of the Documents sample, and a regular expression in Life safety. The same screens carry sample data that mirrors real records: a failed test, a contract date, a split of the buildings, a report on a portal only. Treat these as real. The design project is private and may use them (item "Real details" in [handoff-reconciliation-4.md](handoff-reconciliation-4.md)); **this package is not committed to the repo**, and what comes back stays general. The fifth cut's README says no real facts remain; that is not so.
18. **Gate what is private.** Life safety shows the impairment and the insurer record (P2) and the amounts paid (P1) to everyone; Requests shows an owner's mailing address, "rents the unit", and "tenant in residence" in an evidence sample, where the spec says never an address; Title history shows an association-placed lien (P3) inline in a non-private view, and the masked view leaks role labels ("Owner A′ (their trust)", a prefilled search for "Owner B"); the Service overdue list carries request subjects and notes, not only a member and a unit. Directors see counts only (Service), and the owner view lists no entry that is not the owner's own.
19. **Invented identifiers that could match a real one.** Licence numbers on vendor rows and unit and building labels that do not match the profile's structure. Use plainly fake ones ("123 Main St", "24CV000123").
20. **Hard-coded people, vendors, and the Drive path** ("Drive/Correspondence", a named manager who "manages three communities") are facts in a template. They come from loaders. The portfolio view needs reads across communities, and there is one profile per installation with its own Google project ([profiles.md](../profiles.md)); show it only for a manager role, and only once a mechanism exists.

### Vocabulary and commands

21. **State words are the build's.**
    - Connections: `not set up`, `needs sign-in`, `connected`, `failing`, `paused`. A sign-in failure is `needs sign-in`, never `paused` or "not connected".
    - Follow-ups: `upcoming`, `due`, `overdue`, `done`, `deferred`, `dropped`. Not `late`.
    - Arrivals: `new`, `seen`, `read`, `keyed`, `recorded`, `dismissed`, with `supersededBy` as a flag. Not `received`, `confirmed`, `unmatched`. A structured arrival (PayHOA) goes from new or seen to recorded and is never read or keyed.
    - Heartbeat: `none`, `running`, `draining`, `stale`, `stopped`; stale is older than 90 seconds, the beat every 30. Not "12 hours".
    - Standing (Life safety): the build's are done, due soon, overdue, upcoming, no evidence, date not on record. The screen's "current, none on record, needs input" need a mapping.
    - Library: ready, adjusted, not offered, failing, with a deferred finding. The architectural form is a State form, not Family.
    - Pills for the new words (stalled, replied, assigned, routed, shared, reassigned, waiting on us, held for the board, adopted, declined) need entries in `tones.ts`; today each reads neutral.
22. **Real commands and keys.**
    | The screen shows | The build has |
    |---|---|
    | `jason integrations check gmail` | the keys are `google-workspace`, `postscanmail`; a live check is `--live --by NAME`, at a terminal |
    | `jason cadence --adopt zoom` | `jason cadence --restore SOURCE --by NAME`, `--every`, `--cron`, `--resume SOURCE --by NAME` |
    | vault paths `gmail/oauth`, `postscan/key` | `google-workspace/token/drive`, `google-workspace/oauth-client`, `postscanmail/api-key` |
    | `jason campaigns --outstanding`, `--remind`, `jason responses --unmatched`, `jason campaigns owner-info-2026`, `jason registers owners --enter` | `jason responses --outstanding`, `jason owner-info --email-batch --follow-up reminder`, `jason campaigns --show CODE`, `jason owner-info --apply --payhoa` |
    | `jason vendors --reports bayline-alarm --sync` | `--reports` takes no value; the vendor is `--key`; `--sync` is the portal sign-in |
    | `jason profile --set life_safety.sprinkler.gauges` | the answer goes to intake: `POST /api/write/intake/<id>`, then `jason onboard --apply` |
    | `jason placer-history` for every association | the county command comes from the profile |
23. **Cadences are the registry's.** Instance shows Gmail "every 4h, floor 1h, stale 1d", PayHOA at 05:00, and PostScan at 07:00 with a 12-hour floor. The registry has Gmail every 10 minutes (07-22, floor 2m, stale 1h), PayHOA at 02:00, and PostScan at 08:00 with a one-hour floor, proposed. Read them from `jason cadence --json`. A "next read" must fit its cron.
24. **Topic and kind words are the models'.** Contracts' topic labels ("Parties", "Term and notice", "Disputes", "Standards", "Schedule") are not `Topic` values; the party filter drops `other` and `unstated`. "Arbitration" and "will endeavor" are informational readings in the reader, not checks. Compare's tint is a computed difference, and its sentences ("One lets the manager change the price alone") are readings that carry a `ReadingLabel`.
25. **Evidence has an address scheme.** `arrival:ID` is not one and `arrival` is not an `EvidenceKind`; the server answers "jason cannot open this address". Use `file:responses/…` or add the scheme.
26. **Leads are leads.** Title history draws a reading edge and a lien-to-parcel edge as firm. Both are leads in the graph code. Edge rules are `index.parcel`, `chain.step`, `lifecycle.*`, `process.*`, `reading.<relation>`, and the stores "land chain", "parcel history", and `reading:<file>`; the ids are `inst:<county>:<number>`, with no profile in the name.
27. **Numbers must add up.** Requests' funnel (188 sent, 101 answered, "41 outstanding"), Facts (nine facts undocumented against six assumed and nine reported), Title history (nine loans and "six folded" against four in the data; two notices of default against one), and Service (September and the year to date scaled from Q3) do not reconcile. Counts and arithmetic move to the server.

## The screens

| Screen | Built | What it assumes that is not | Adopt as it stands |
|---|---|---|---|
| **Conversations** | Nothing. The Inbox still shows the "Email awaiting us" tab. | `gmail_catalog`; `Community.policies()`, `handoff_rules()`, `conversation_policy()`, `gmail_mailboxes()`; `/api/conversations`, `/api/handoffs`; per-message Gmail links | Automatic replies folded away; sides as words; the ledger as "NAME, DATE"; "jason's reading: X. Is that right?" until a person sets the intent; "latest word wins"; confidential rows read as "open the private view"; join leads marked "A lead, not a finding" |
| **Policies** | Nothing. | `jason.community.policies`; a `policies` loader | Proposals never in force until a vote is recorded; version-in-force; the fallback line per standing; "jason's proposal" labels. A statutory miss is not an accusation (decisions 6 and 9): no red bar, no `octagon-alert` in the bad tone |
| **Service** | Counting only (`jason respond`): on time and late by kind | `tasks/response_metrics.measure`; `ResponseRule` adoption and pause fields; the overdue read | Statute and policy tables kept apart with the clock and its source; "proposed, not adopted"; the under-five count rule; "never published to members"; "forward is not an answer". The headline merges both clocks and must be split |
| **Requests** | The inbox, outstanding, campaigns, follow-ups, library, and `--outstanding` in the CLI and MCP | Web loaders for `new_responses`, `response`, `campaign_status`, `followups`, the form library; the `followups/*` and `forms/campaigns.json` path rules; the unbuilt components (`CheckedStrip`, `CampaignFunnel`, `FollowUpRow`/`Band`, `BasisChip`, `OutstandingList`) | Four tabs on one page; "Outstanding does not depend on the door"; the unreachable card kept apart; "Nothing on this page sends"; "a reading is evidence… only when a person confirms" |
| **Contracts, Compare** | `contract_terms.load`; no route | `/api/contracts`, `/api/contracts/<key>`, `/api/licenses`; confidential, not-read, empty, and model states; Vendors | The leads wording; the unsigned banner; "as read" with the dotted underline and the word; the licence register copy ("never says active/valid"); Confirm before draft |
| **Community facts** | `/api/facts`, `/api/loss-packet`, `/api/community` | An owner loader (neither facts loader is an owner source); search, filters, and the documents repository | The loss-packet layout with the differing row tinted; "jason does not decide coverage" |
| **My unit manual** | `/api/unit-record`, `unit_records_write` | An identified owner (the owner view is "a view, not a sign-in", and the loader never passes `owner=True`); a board and manager tab; `kind` and an integer `cost_cents` in the form; a `ComponentStatus` for "addition"; stop sharing | Copy and caveats; "(your figure)"; "may be an association record"; private by default; "Only you see this note". Waits on the board's decision on owner sign-in |
| **Paint** | `/api/paint`, `/api/paint/color`, the MCP paint tools | Per-building cycle, implied dates, built year and first sale ("needs input" until the parcel-to-building bridge); `maker` on every colour; `ColorDetail` from the catalog | `PaletteMatrix`, `SourcedDate`, `Caveats`; implied dates in the warning style; "jason does not approve" |
| **Title history** | `/api/instrument-graph` and its reveal | `/api/parcel-processes`, `/parcel-search`, `/formation-ties`, `/association-footprint`, `/survey-coverage`; `ParcelLookup`, `TitleStrand`, `DeedCard`, `FormationTies`, `FilingFootprint`; a route that does not collide with "Title watch" | Masked by role by default; the gap wording ("not found under these names, ask the title company"); the table beside the swimlane |
| **Life safety** | The five inspection loaders | A `life-safety` loader composing them; a `deficiencies` writer; a "not ours" store and mail row; the deficiency row as a component | System cards; deficiency ordering; "cleared only by a linked record"; "none on record… not seen"; TesterCheck masking; the notice-clock day counts; "jason does not contact the insurer" |
| **Governing documents** | `OnboardingView`, `AssociationRecordsView`, `/api/records` | A name that does not collide with `#/documents` (the cite-box screen); `DocumentLocator`; the real reread (`ReadAllFromDrive`) | The key-document counts; the three tabs as the onboarding trio |
| **Reference shelf** | `ReferenceShelf`, `CitationGaps`, `CitedSections`; `IngestCitations` on `#/ingestion` | Records > Reference shelf with the gaps card first; `WorkReader` | The gaps card first; the two built tabs. "Cited in our files" and "Often cited" are not in the spec |
| **Instance** | `serve.status`, `integrations list --json`, `cadence --json` | `/api/instance/{service,integrations,schedules}`, administrator only | No secret shown or taken; no connect or start flow; the tabs; the vault table of names only; "only after a person adopts it, never faster than its floor, never for a write" |

## Settled

- **Nothing here commits the templates.** The package stays outside the repo. What the build takes from it is the structure and the copy above, rewritten from loaders.
- **Components first.** Where a built component exists (`Tabs`, `ScreenHeader`, `DataTable`, `Findings`, `Doc`, `RemoteView`, `Recitation`, `ReadingLabel`), the screen uses it. Where the spec proposes one that is not built, the screen draws it from the same parts and says so; it does not fork the built one.
- **A route is named for what it holds,** and writes are `POST /api/write/<store>/<key>` with `by`, registered in `EXTRA_WRITERS`. The spec's `/api/handoffs/<id>/outcome` becomes `/api/write/handoffs/<key>`.
- **The server computes standings, counts, "awaiting", and "today".** A template shows `asOf`.

## The build's, from this cut

1. **Loaders and routes** for each screen in the table, in the order of the work already planned: Requests (the loaders exist in the CLI and MCP), Service (`response_metrics`), Life safety (compose the five loaders), Contracts, Instance, then Conversations and Policies (their stores are new).
2. **Writes,** each with `by`, append-only where a hold applies: `handoffs`, `policies`, `deficiencies`, followups, responses, a board-item create, and the unit-record add with a `kind` and integer cents.
3. **`tones.ts`** gains the words in item 21. `DueDate` is shown only for open states; today it reads "Nd overdue" for a satisfied one.
4. **Corrections in our own docs.** [policy-catalog-design.md](../policy-catalog-design.md) cites Civil Code 5610 for spending authority. Correct it, and add a lesson (`statute-cited-for-a-subject-it-does-not-speak-to`) with the check: a citation in a spec is read against the stored section.
5. **Gates:** P3 rows redacted server-side and refused to the owner view; P2 and P1 content behind the private view and the treasurer or director; a director counts-only variant of Requests and Service.
6. **Owner identity** for the unit manual stays behind the board's decision on owner sign-in. Until then the manual is the Drive-folder fallback.
7. **Open and not decided here:** where a person's "pin" is stored; where the portfolio view reads from; whether a Gmail draft may ever be created from the console.
