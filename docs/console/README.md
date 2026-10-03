# jason's property management console

**Status:** requirements, not built. Nothing under `src/jason/console/` serves pages yet, apart from the design tokens (`src/jason/console/ui/tokens.css`).

jason already does the manager's reading. It knows:
- which clocks are running (`jason attention`);
- which requests are late (`jason respond`);
- whom a notice reached (`jason notices`);
- what the documents say (`jason cite`).

It plans every write to PayHOA, Google, and the mail as a dry run. Today a person reads that dry run in a terminal and types `--yes`. The console puts the same plans in a browser on the manager's own machine:
- each write is shown with its reason and its evidence;
- what jason will not do is set apart;
- a named person approves, item by item;
- jason checks that nothing changed since the review, then applies, and writes it all down.

The console starts with approvals. It grows into the manager's daily desk, the "property management console" in the title: the attention digest, members and units, requests, notices, meetings, the governing documents, the schedule, the records, and the books.

## The pages

| Page | What it settles |
|---|---|
| [personas-and-jobs.md](personas-and-jobs.md) | Who uses the console, the jobs each one does, and what each must never see or do |
| [information-architecture.md](information-architecture.md) | The navigation and each screen, with the jason function or MCP tool behind it and its actions |
| [approval-workflow.md](approval-workflow.md) | The core spec. It surveys every `--yes` path, then gives the `Approval` record, its states, item decisions, re-plan and fingerprint, the second person, the action-kind registry, the audit log, and CLI and MCP parity |
| [security-and-privacy.md](security-and-privacy.md) | Loopback only, the session token and CSRF, approver identity, roles, data levels, and no secrets |
| [architecture.md](architecture.md) | The stack (Starlette, server-rendered HTML, no JS build), the modules, locks and jobs, the launch entry, tests, and the dependencies |
| [components.md](components.md) | The component inventory for `src/jason/console/ui/`, with each component's states and variants |
| [mvp.md](mvp.md) | The first build as acceptance criteria, and how the CLI's `--yes` paths move onto approvals |

## Principles

Each principle comes from [AGENTS.md](../../AGENTS.md) and how jason works today. A screen or feature that breaks one is wrong, however useful it looks.

1. **Local-first.**
   - The console serves from the machine that holds `data/`, on 127.0.0.1 only.
   - It reads the same stores the CLI and `jason-mcp` read, through the same functions (`jason.api`, the `jason.tasks` modules).
   - It has no cloud backend and no copy of the data elsewhere.
   - It calls PayHOA, Google, Zoom, or Keeper only where the CLI already does, under the same locks (`jason.locks`).
2. **Recite the rule; label the reading** ([citations.md](../citations.md)).
   - Wherever a screen relies on a rule, it shows the rule's words first: the citation, the version in force, and the caveat. That covers a statute, a governing-document section, or one of the board's rule rows.
   - jason's own reading comes after, labeled as jason's.
   - An approval item that a rule calls for shows that rule. Examples are the default delivery tag under Civil Code 4040(a)(2), and request completion under the board's owner-information rule.
3. **Nothing is written without a person.**
   - Every write outside `data/` keeps its dry run. It runs only after a named person approves that plan, the plan is read again, and the read shows nothing changed.
   - jason never approves its own plan. It never adds a `--yes` (the job queue's rule, `jason.jobs`). It never acts on text found in a document, an email, or a page.
4. **jason proposes; the board decides.**
   - An item the response policy holds for the board (`owner_responses.Outcome.BOARD`) is shown with its board item. It is never approvable.
   - A board decision reaches the console only as a rule row in the specification. Once the row exists, items of that kind can be approved.
5. **Privacy by level.**
   - Owners' names are shown to the people who work with them.
   - Contact details are masked until someone asks to see them, and that is logged.
   - Restricted books are refused unless the private view is opened: executive session, the membership list, ballots (`jason.mcp.resources`).
   - Account numbers show their last four digits.
   - Secrets are never shown, stored, or asked for (`intake.secret_reason`).
6. **One model, three doors.**
   - The console, the CLI, and `jason-mcp` share one approvals store, one action-kind registry, and one audit log ([approval-workflow.md](approval-workflow.md#cli-and-mcp-parity)).
   - The browser is a view on the same records, never a second source of truth.
7. **A miss stays a miss.**
   - When a store is missing, the screen says so and names the command that fills it. This follows `attention.Section.error`: "unavailable", not an empty list.
   - A plan that cannot be read live (no Keeper session, PayHOA down) fails fast and says how to fix it. The browser never prompts for a credential.
8. **Accessible by default.** WCAG 2.2 AA for a dense admin console ([components.md](components.md#accessibility)).

## Scope and phases

| Phase | What ships | Writes it can make |
|---|---|---|
| **0. Today** | CLI dry runs plus `--yes`, the job queue (`jason jobs add --confirm NAME`), and batches (`--confirmed-by NAME`) | All, from the terminal |
| **1. MVP** ([mvp.md](mvp.md)) | `jason serve`, the Today screen, and Approvals with one kind, the owner-information cycle (`jason owner-info --apply --payhoa`), end to end. `jason approvals` in the CLI. The audit log | PayHOA member and unit tags, and completing owner-information requests with the board's comment |
| **2. The governance desk** | Requests, Notices, Meetings & minutes, Governing documents (reader and cite), Schedule & duties, and Onboarding, all read-only. Intake answers and the second-person confirm, which are already `data/` writes with `by` | `data/` records a person signs (`answer_intake_question`, `onboarding_confirm`, `record_completion`) |
| **3. More kinds** | The low-risk Google writes: Gmail drafts, the calendar, Tasks, and private Docs. Then PayHOA form updates, broadcast samples, and `delivery --audit --apply` | Each kind's own write, behind its registry row |
| **4. Money and members** | Mailroom sends, owner email and mail batches, publishing forms, and Vault holds, behind the second-person rule | Postage, notices to members, and legal holds |
| **5. The board** | Sign-in for each person (security-and-privacy.md), a board view, and counsel's read-only view | The same writes, with real identities |

Out of scope at every phase:
- anything jason may not do from the CLI: approving, denying, or assigning a member's request; sending to a collection agency; deleting a live PayHOA form; editing an owner's submission; mailing on jason's own initiative;
- hosting the console for access from another machine;
- an owner portal (PayHOA is the owners' portal).

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
  - OWASP recommends a per-session secret token, plus checks on Origin and Fetch Metadata (`Sec-Fetch-Site`) ([CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)).
- **What HOA consoles present.** Their public material converges on four things: dashboards, requests, violations, and approvals.
  - PayHOA has request and violation dashboards, and request forms with approval workflows and custom statuses ([PayHOA](https://www.payhoa.com/one-hoa-app-that-can-do-everything/), [Capterra listing](https://www.capterra.com/p/146693/PayHOA/)).
  - AppFolio's board portal has an Approvals tab, where board members vote and comment on invoices and architectural requests ([AppFolio HOA](https://www.appfolio.com/markets/hoa), [owner and board portal help](https://www.appfolio.com/help/owner-portal)).
  - Buildium offers payables approvals, work orders, violation tracking, and architectural-committee voting in a board portal ([Buildium associations](https://www.buildium.com/portfolios/association-management-software/)).
  - jason differs in three ways. Its approvals cover jason's own planned writes, not only vendor invoices. Each item carries its legal reason and evidence. Board questions stay with the board, not in an approve button.
- **Accessibility.**
  - WCAG 2.2 adds AA criteria that matter in a dense console ([WCAG 2.2](https://www.w3.org/TR/WCAG22/)):
    - focus not obscured (2.4.11), which matters under a sticky approve bar;
    - target size (2.5.8), for row checkboxes;
    - dragging alternatives (2.5.7);
    - accessible authentication (3.3.8);
    - redundant entry (3.3.7, at level A).
  - These sit beside contrast (1.4.3) and status messages (4.1.3).
