# jason's property management console

**The console is jason-ui served by jason-web.** jason-ui (`ui/`) is the React component library and app. jason-web (`src/jason/web/`, the `jason-web` command) is the Flask app under waitress that serves it and the `/api/*` loaders on 127.0.0.1. How to run it, its API, and every screen are in **[docs/web-ui.md](../web-ui.md)**. What a person decides on each screen is in [web-ui-decisions.md](../web-ui-decisions.md), and onboarding a community in [onboarding-ux.md](../onboarding-ux.md). The components are also the design system, synced to the claude.ai design project as `window.JasonUI` ([.design-sync/](../../.design-sync/conventions.md)).

These pages began as requirements written before that UI existed. They are now reconciled with it. They keep what the console still needs (the approvals engine in the browser, the screens with no counterpart yet, the privacy model, the words on screen) and point to what is built for the rest.

jason already does the manager's reading. It knows:
- which clocks are running (`jason attention`);
- which requests are late (`jason respond`);
- whom a notice reached (`jason notices`);
- what the documents say (`jason cite`).

It plans every write to PayHOA, Google, and the mail as a dry run. The console puts the same reading, and the same plans, in a browser on the manager's own machine:
- each write is shown with its reason and its evidence;
- what jason will not do is set apart;
- a named person approves, item by item;
- jason checks that nothing changed since the review, then applies, and writes it all down.

## The pages

| Page | What it settles |
|---|---|
| [architecture.md](architecture.md) | The stack as built (jason-ui, jason-web, the approvals engine behind `/api/approvals*`), what was decided and where, locking, and testing |
| [approval-workflow.md](approval-workflow.md) | The engine's spec: every `--yes` path surveyed, the `Approval` record, its states, item decisions, re-plan and fingerprint, the second person, the registry, the audit log, and CLI and MCP parity. Also how letters and plans share one inbox, and why the board decides by vote, never by a click |
| [information-architecture.md](information-architecture.md) | `ConsoleShell`'s navigation, each spec screen mapped to its console screen, and where the screens with no counterpart go |
| [screens/](screens/README.md) | One spec per screen: what it adds to the console screen that exists, or the whole screen where none does |
| [components.md](components.md) | Each component the console needs, mapped to jason-ui's (built, being added, or still proposed), and the WCAG 2.2 AA duties |
| [security-and-privacy.md](security-and-privacy.md) | Loopback, the write guard, apply behind `--allow-apply`, identity, roles, data levels, and no secrets |
| [personas-and-jobs.md](personas-and-jobs.md) | Who uses the console, the jobs each does, and what each must never see or do |
| [journeys.md](journeys.md) | Ten walks across the screens, step by step (adds: answering what jason could not tell; a director confirms a reading and the board adopts it; a required program found missing and adopted; an improvement request to the unit's record) |
| [handoff-conversations-and-policies.md](handoff-conversations-and-policies.md) | The design pass on conversations, forwards as handoffs, response standards, and the policy catalog |
| [handoff-form-library.md](handoff-form-library.md) | The form a member sees (one anatomy for paper, PDF, PayHOA, and the portal: the law's words, what happens next, why we ask, the receipt), the member's request center, and the administrator's form library (built-in, adjusted, not offered, stale) |
| [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md) | Arrivals in lanes, how a form is recognized, the cycle board (who has answered, who has not, what the law asks next), the forms register, what needs development, and the discovered form candidates |
| [handoff-responses.md](handoff-responses.md) | New responses and reading a returned form: the screen (`#/responses`), the per-channel check strip, an arrival's states, the scan beside its reading, field by field, and the count that says how old it is |
| [handoff-admin-components.md](handoff-admin-components.md) | The administrator's components from what was built: each integration's reading, the credential line, capabilities and limits, the schedule rows and editor, pauses, the service's heartbeat and lanes, the vault and its migration plan, with the data shapes and every state |
| [handoff-instance-and-integrations.md](handoff-instance-and-integrations.md) | The design pass on instance administration, each community's integrations, and their setup dialogs (Google Workspace, Zoom, PayHOA): the screens, the components, secrets in the console, schedules, the service |
| [handoff-held-setup-roster.md](handoff-held-setup-roster.md) | The design pass on the components that pair with held executive items, setup over onboarding, People and offices, the meeting notice, and the phone layout: twelve components, their states, data shapes, and the rules they keep |
| [handoff-reconciliation.md](handoff-reconciliation.md), [handoff-reconciliation-3.md](handoff-reconciliation-3.md), [handoff-reconciliation-4.md](handoff-reconciliation-4.md) | The design agent's console package, its third cut, and the answer to its fourth, checked against the repo and the law: the corrections, the fixes in the built console, and the build order |
| [content/style.md](content/style.md), [content/patterns.md](content/patterns.md) | The words on screen, and the interaction patterns |
| [doc-component.md](doc-component.md) | `Doc`, the one component for every document reference: the `DocRef` a loader returns, the four variants (chip, row, card, inline), their states, and the checklist a screen follows to adopt it |
| [documents.md](documents.md) | One viewer for every kind of document: the copy jason keeps, how each kind renders and refreshes, who may see it, serving untrusted bytes safely, the gaps to close, and the build order |
| [redesign-review.md](redesign-review.md) | The design project's twelve redesign "rethinks", each kept, corrected, or held against the law, the roster, and the approvals engine, and the order to build them |
| [handoff-document-kinds.md](handoff-document-kinds.md) | The design pass on the document kinds: the shelf of every kind, how a file got its kind, gaps, readings, and a correction as a proposed rule: the components, states, data shapes, sample data, what the design must keep, and the decisions open |
| [handoff-unit-records.md](handoff-unit-records.md) | The design pass on the paint palette, community facts, the unit manual, and the loss packet: the components, their states, data shapes, sample data, what the design must keep, and the decisions open |
| [handoff-discovery.md](handoff-discovery.md) | The design pass on finding the association, locating its documents, the key documents, and the instrument graph: the four components, their states and sample data, what the design must keep, and the decisions open |
| [handoff-draft-from-item.md](handoff-draft-from-item.md) | The design pass on turning a lead or a board action item into a drafted email (not built): the source pinned, a purpose proposed, recipients suggested with why, the email composed from the record with each sentence's origin, the reminders to read first, the board's decision before anything commits, a Gmail draft and never a send, and the trail on the source; data shapes, sample data, what the design must keep, and the decisions open |
| [handoff-contracts.md](handoff-contracts.md) | The design pass on contracts, parties, and licenses (not built): a contract's terms in its own words, what the counterparty owes, notice windows, scope, warranties, signing, the license register, a model's closer reading, and the kind question at ingest; data shapes, sample data, what the design must keep, and the decisions open |
| [handoff-title-processes.md](handoff-title-processes.md) | The design pass on a parcel's title history and its document processes (the strand and the braid, closings and their seats, gaps, tenures, loan lifecycles) and on tying a founding document to its association: the components, their states, data shapes, sample data, what the design must keep, and the decisions open |
| [handoff-applicability-questions.md](handoff-applicability-questions.md) | The design pass on what applies to the association and the questions a person answers when jason cannot tell: the three-valued answer with its deciding or missing fact, the question row as a signed answer, the event facts picker behind the notice catalog, the per-building Civil Code 5551 record with "date not on record", the standing facts stated and answered; states, data shapes, the loaders to add, and the decisions open |
| [handoff-confirmations-queue.md](handoff-confirmations-queue.md) | The design pass on the confirmations queue: what jason proposed and only a person can confirm (candidate readings of the law, gold-record labels, decisions a lesson waits on): one list oldest first, each act a person's signed record that adopts nothing and makes no rule, stale readings that cannot be confirmed until re-read, the board's adoption shown apart, data shapes, the phone layout, and the decisions open |
| [handoff-context-pack-workbench.md](handoff-context-pack-workbench.md) | The design pass on the context-pack workbench: searching the passage index by slice, the hit card with its standing, the pack's tiers with why each source is in and what was held back, a review run under a pack behind the model gate with its answer in three parts and each quotation checked, and two packs compared |
| [handoff-collection-workspace.md](handoff-collection-workspace.md) | The design pass on the collection workspace: one set of documents read together, its summary bands with their gaps, the chronology with disagreements shown side by side and never resolved, the citations of the law, the files and their read state, reviews under a lens, and open questions raised by a person |
| [handoff-as-of-and-quote-check.md](handoff-as-of-and-quote-check.md) | The design pass on reading the law as of a day and checking a quotation before it is given: the day control every recitation obeys, a section's versions on a timeline, a former section read through its successor, and each quotation's verdict |
| [handoff-storage-and-settings.md](handoff-storage-and-settings.md) | The design pass on the machine jason runs on: places and drives, the user configs and which file set each value, data left in an old default folder, locks and their holders, the local model stack, and the index's health |
| [handoff-programs.md](handoff-programs.md) | The design pass on what the association must adopt and carry out: the register by source with the three evidences as words, one program's page (requirement recited element by element, document, adoption, review, derived duties, owners' part), the gaps as questions, and the draft's way to the board with no approve control |
| [handoff-improvement-requests.md](handoff-improvement-requests.md) | The design pass on home improvement requests: the review and the board stage composed with the existing board screens (no approve control), the owner's unit view and how it is delivered now (a generated packet and the PayHOA thread; the console is loopback-only), the owner's resale summary and insurance schedule, and the association's original-or-upgraded view at a loss |
| [handoff-intake-review.md](handoff-intake-review.md) | The design pass on reviewing what jason found when it took a scan in: a file's preflight card (page strip, what would be done and why, pages to read again, a person's keep of a blank page), the segment tree with its moves, signals, tiers and five signed acts, the page viewer with a stack-aware breadcrumb, the OCR review with the page crop beside the readings, the worst-read files, and what the extraction found with parent links; the original is never changed |
| [handoff-rules-and-authority.md](handoff-rules-and-authority.md) | The design pass on bringing in the rules and checking them: the onboarding task (documents that hold rules, their parts, how each numbers its sections, the read for grants), the authority map (each subject's grants recited with the reader tier, beside rules on file or none, a grant with no rule as a lead for the board's canvas, never a fault), a citation that two documents could mean shown with both and a person's recorded pick, jason's own rule rows labeled apart, and the rule-change hand-off to jason rule-change; states, data shapes, the loaders to add, and the decisions open |
| [mvp.md](mvp.md) | What is built, the first build from here with its acceptance criteria, moving `--yes` onto approvals, the prototype library, and the open decisions |

## Principles

Each comes from [AGENTS.md](../../AGENTS.md), how jason works, and the design handoff the console screens were built from. A screen or feature that breaks one is wrong, however useful it looks.

1. **Local-first.**
   - jason-web serves from the machine that holds `data/`, on 127.0.0.1.
   - It reads the same stores the CLI and `jason-mcp` read, through the same functions. It has no cloud backend and no copy of the data elsewhere.
   - Nothing on load calls PayHOA, Google, Zoom, or Keeper. A live read is an action a person takes, under the same locks (`jason.locks`).
2. **Recite the rule; label the reading** ([citations.md](../citations.md)).
   - Wherever a screen relies on a rule, it shows the rule's words first (`Recitation`): the citation, the version in force, and the caveat.
   - Any reading comes after, labeled with whose it is (`ReadingLabel`).
3. **A reading, a match, or a gap is a lead, not a finding.** This is jason-ui's voice, and jason's: the console shows what the records say and never decides. A clock is "computed", a gate is "jason's reading", a match is a lead to read.
4. **Nothing is sent, posted, recorded, or filed without a person.**
   - Every write is a `Confirm` that spells out what changes, in a named person's name.
   - A write outside jason is an engine approval: planned, decided item by item, and read again before apply. Apply from the browser is off unless the server was started with `--allow-apply`. Otherwise the page shows the command a person runs.
   - jason never approves its own plan, never adds a `--yes`, and never acts on text found in a document, an email, or a page.
5. **jason proposes; the board decides, by vote.**
   - A board approval is a vote at a meeting, recorded by an officer (the president or the secretary) with the meeting's date. No one clicks "approve" for the board.
   - An item held for the board is never approvable; it goes to the meeting's agenda. Director votes are a roll call by name; polls are member input.
   - A decision brief lays out the options and never recommends one.
   - A board decision reaches approvals only as a rule row in the specification. Once the row exists, items of that kind can be approved under it.
6. **Privacy by level.**
   - Owners' names are shown to the people who work with them. Contact details are masked by the server until someone asks to see them, and that is logged.
   - Executive session stays out of open recordings, transcripts, and minutes. Restricted books open only in the private view.
   - Account numbers show their last four digits. Secrets are never shown, stored, or asked for.
7. **One model, three doors.** The CLI (`jason approvals`), jason-web, and `jason-mcp` (read only) share one approvals store, one registry, and one audit log ([approval-workflow.md](approval-workflow.md#10-cli-and-mcp-parity)). The browser is a view on the same records, never a second source of truth.
8. **A miss stays a miss.** A missing store shows the tool's own note and the command that fills it, never an empty table. A live read that cannot be made (no Keeper session) fails fast and says how to fix it. The browser never prompts for a credential.
9. **Accessible by default.** WCAG 2.2 AA for a dense admin console ([components.md](components.md#accessibility)).

## Phases from here

| Phase | What ships | Writes it can make |
|---|---|---|
| **Built** | The console screens and the dock ([web-ui.md](../web-ui.md)); letters through their stages; the board loop; the approvals engine with `jason approvals` and read-only MCP tools | jason's own stores, each a person's act with `by`. Everything outward from the terminal |
| **1. Engine approvals in the browser** (built, with the gaps listed in mvp.md; [mvp.md](mvp.md#the-first-build-engine-approvals-in-approvals)) | The write guard, the `/api/approvals*` routes, and the plan review in `#/approvals` for `owner-info-tags` | Decisions and signatures. PayHOA member and unit tags, and the requests they complete, only with `--allow-apply` |
| **2. The governance screens** | Requests, Notices, Governing documents, the onboarding session, and the bands the screen specs add to existing screens | `data/` records a person signs: intake answers and their second person, a duty done, a posting recorded |
| **3. More kinds** | Gmail drafts, calendar, Tasks, private Docs, PayHOA form updates, delivery tags | Each kind's own write, behind its registry row |
| **4. Money and members** | Mailroom sends, owner email and mail batches, publishing forms, Vault holds (two people); Members and units with P2 masking | Postage, notices to members, legal holds |
| **5. Sign-in** | A credential for each officer (built: Sign in with Google), roles enforced on the server (built in part: a role class and data levels; screens and signing still proposed), the private view | The same writes, with authenticated names |

Out of scope at every phase:
- anything jason may not do from the CLI: approving, denying, or assigning a member's request; sending to a collection agency; deleting a live PayHOA form; editing an owner's submission; mailing on jason's own initiative;
- approving for the board: the board's approval is its vote, recorded;
- hosting the console for access from another machine, until there is sign-in and a written policy;
- an owner portal beyond the owner view and the community page (PayHOA is the owners' portal).

## Prior art

Each source below shaped a requirement here. The pages cite them where they apply.

- **Plan, then apply.**
  - Terraform saves a plan to a file, and `apply` runs that file without asking again ([plan](https://developer.hashicorp.com/terraform/cli/commands/plan), [apply](https://developer.hashicorp.com/terraform/cli/commands/apply)).
  - It refuses a saved plan once the state has changed since the plan was made, with the error "Saved plan is stale" ([hashicorp/terraform#21785](https://github.com/hashicorp/terraform/issues/21785)).
  - jason adopts both halves: a reviewed plan is what gets applied, and it is read again first.
- **Review rules.**
  - GitHub's protected branches can require approving reviews, and can "dismiss stale pull request approvals when commits are pushed that affect the diff". They can also require that someone other than the person who pushed approves the latest push ([about protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)).
  - jason adopts per-item approval, approvals that lapse when the live state moves, and a second person who is not the first.
- **Change approval by class.**
  - ITIL sorts changes into standard (pre-approved, low risk), normal (assessed and authorized), and emergency changes, each on its own path ([summary](https://blog.invgate.com/what-are-the-itil-change-categories)).
  - jason's action-kind registry gives each kind its approver rule in the same way. It has no emergency path: nothing jason writes is urgent enough to skip a person.
- **The two-person rule.**
  - NIST SP 800-53 AC-5 (separation of duties) asks that one person cannot both start and authorize a sensitive action ([AC-5](https://csf.tools/reference/nist-sp-800-53/r5/ac/ac-5/)).
  - AU-9(5) applies dual authorization to audit records ([AU-9](https://csf.tools/reference/nist-sp-800-53/r5/au/au-9/)).
  - jason already has the rule for high-stakes intake answers (`intake.confirm` refuses the person who answered).
- **Audit logs.**
  - OWASP's logging guidance records when, where, who, and what for every high-value action. It protects the log from change and makes tampering detectable ([Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)).
- **CSRF.**
  - OWASP recommends a secret token, plus checks on Origin and Fetch Metadata (`Sec-Fetch-Site`) ([CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)). jason-web's write guard does all three.
- **What HOA consoles present.** Their public material converges on four things: dashboards, requests, violations, and approvals.
  - PayHOA has request and violation dashboards, and request forms with approval workflows and custom statuses ([PayHOA](https://www.payhoa.com/one-hoa-app-that-can-do-everything/), [Capterra listing](https://www.capterra.com/p/146693/PayHOA/)).
  - AppFolio's board portal has an Approvals tab, where board members vote and comment on invoices and architectural requests ([AppFolio HOA](https://www.appfolio.com/markets/hoa), [owner and board portal help](https://www.appfolio.com/help/owner-portal)).
  - Buildium offers payables approvals, work orders, violation tracking, and architectural-committee voting in a board portal ([Buildium associations](https://www.buildium.com/portfolios/association-management-software/)).
  - jason differs in three ways. Its approvals cover jason's own planned writes, not only vendor invoices. Each item carries its legal reason and evidence. And the board's questions stay with the board: a vote at a meeting, recorded, never a director's click in a portal.
- **Accessibility.**
  - WCAG 2.2 adds AA criteria that matter in a dense console ([WCAG 2.2](https://www.w3.org/TR/WCAG22/)):
    - focus not obscured (2.4.11), which matters under a sticky approve bar;
    - target size (2.5.8), for row checkboxes;
    - dragging alternatives (2.5.7);
    - accessible authentication (3.3.8);
    - redundant entry (3.3.7, at level A).
  - These sit beside contrast (1.4.3) and status messages (4.1.3).
