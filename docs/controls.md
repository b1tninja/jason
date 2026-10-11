# Controls: the safeguards a board opts into, and jason suggests

A **control** is a safeguard the board chooses to add to how the association works: two signers on a payment, a second person confirming a high-stakes answer, an approval before the manager spends past an amount, a written resolution before an officer signs a contract. jason reads the governing documents when it takes an association on, finds the duties and limits they set, and **suggests** the controls that follow. The board **adopts** the ones it wants. jason enforces only what the board adopted, and never turns one on by itself.

This began as a design and is now built in part (section 7 says what): the catalog and record, the effective-approver lookup, the suggestion reader, `jason controls`, the loaders, the Controls screen, the notice on plans and workflow steps, signer enforcement, the `control-adoption` run, and the onboarding step.

## 1. The principles

- **jason proposes; the board adopts.** A control is a rule the association makes for itself. jason never makes a rule ([AGENTS.md](../AGENTS.md), "Where the law is silent, write it down"). A suggestion carries the provision it comes from, quoted whole, and jason's reasoning labeled as a reading.
- **A control only adds.** It can require more (a second signer, a lower threshold, a written resolution first). It cannot remove a rail the code or the law already sets: a built-in two-person kind stays two-person, and a control that would let one person do what the law or the governing documents require two to do is refused with the provision named.
- **Opt in, with a record.** An adopted control has a decision (recorded by the secretary, with the meeting and the vote as taken), an effective date, and a history. Declining or deferring is recorded too, so the same suggestion is not asked again without a reason.
- **Enforced where the work happens.** The approvals engine reads the adopted signers for a kind; a workflow step reads the adopted gate; the Mailroom reads the adopted class. Hiding a button is not enforcement: the server refuses the act.
- **Plain failure.** If a control asks for more people than the roster has (two directors where one is seated), the act is refused and says why. A control never silently falls back to fewer.

## 2. The record

A catalog of **control types** is written once, in jason, for any association. A community's **adopted controls** are its own facts, kept as private profile data (`data/spec/<profile>/controls.json`, never checked in), merged through `jason.community.private.facts`.

```
ControlType  key, title, family, what it governs (an approvals kind, a workflow step, a send, a spend)
             parameters (who may count as a signer, how many, an amount, a class)
             floor (what the law or a built-in rail already requires; a control may not go below it)
             sources (the kinds of provision that suggest it)
Control      type, parameters as adopted, scope (all, one account, one kind, one family)
             basis (the provision quoted whole, with its citation), jason's reading (labeled)
             state: suggested | proposed to the board | adopted | declined | deferred | retired
             adopted by (the decision id, the meeting, the vote as taken), effective date
             history (append only: who, when, why)
```

## 3. Where suggestions come from

When the governing documents are ingested (the `onboard` run's governing-documents gate, or `jason ingest`), jason reads their duties and limits and matches them to control types. Each match is a **suggestion**, never an adoption.

| What the documents say | The control it suggests |
|---|---|
| Who may sign for the Association, and how many (a bylaws section on checks and drafts) | **Payment signers:** the least the document allows is the floor; the suggestion is the signer rule the board prefers above it (for example, the treasurer and one other director above an amount the board sets) |
| A stricter rule for the reserve (two board members to withdraw) | **Reserve withdrawal signers,** at that floor or above |
| That no officer may bind the Association without a resolution | **Contract authorization:** a board resolution on record before an officer signs; the term and size limits the documents set as checks |
| A limit on the board's powers (a contract term, a capital spend, a sale) | **Limit checks:** a warning, or a refusal, when a plan or a contract passes the limit |
| That the board prescribes the manager's duties | **Manager spending authority:** an amount above which the manager asks, and who is asked |
| A review the documents or the law require of the board (the accounts, monthly under the statute) | **Review cadence:** the schedule, who records the review, ratification at the next meeting |
| That a notice goes by a named method | **Delivery class:** the method a notice letter defaults to |
| Who keeps the records and gives the notices | **Recorder:** who records the board's decisions and that a notice was given |
| High-stakes answers at onboarding (the board's roster, the delivery rules) | **Second-person confirmation** (built for onboarding; offered for other kinds) |

A suggestion shows: the provision's words whole with the citation (quoted from the stored text, never from memory), what the provision sets as the floor, what jason suggests above it and why (a reading), and what turning it on changes (which kinds and steps it touches). A provision jason cannot read cleanly is shown as a question for the board or counsel, not as a suggestion.

## 4. The lifecycle

`suggested` (jason found the provision) → `proposed` (a person puts it before the board; it becomes a board item with the quoted provision as its evidence) → the board decides at a meeting (the secretary records the decision) → `adopted` (with an effective date), `declined`, or `deferred` (with a reason and a date to look again). An adopted control is reviewed each year with the board's other standing decisions (the duty schedule). Retiring a control is a decision too.

The adoption is a `decision` step in a **control-adoption** run, one run per control (a family of the workflows, [workflows/README.md](workflows/README.md)): suggest, put it before the board, decide, record, set the effective date, check the roster can satisfy it, and wait for the effective date, from which it is in force (jason turns nothing on; the date and the check do).

## 5. Enforcement

- **The approvals engine.** An action kind has a fixed approver rule in code (`ONE_PERSON` or `TWO_PERSON`). The *effective* rule is the stricter of the kind's and the adopted control's: more signers, a narrower set of who may sign, a threshold above which a second signature is needed. The plan shows the effective rule and where it came from ("two signers: the board adopted this on DATE").
- **Workflow steps.** A step's `role` and its gates come from the definition; an adopted control can add a gate (a resolution on record before the step, a second person to confirm, a narrower set of offices that may record it). The run page shows the gate and why. A type governs steps by `Governs(WORKFLOW_STEP, pattern)`: the pattern (`fnmatch`) names a step id or a workflow key (every step of it) or is `*`; a control scoped to a kind names the pattern itself, one scoped to a family names a workflow family. The gates bind from the control's effective date, and only add. A *resolution* is on record when the act (its record or reason), the run's subject or label, or the record of a step already done cites the id of a decision recorded in Decisions with the outcome approved. A *second* person is a different person who also holds the step's role (the engine asks the role of each person who acts): the first person's act is recorded as a note (`first_of_two`) and the step stays open; a different person's act completes it, naming the first. The roster that cannot supply a second person refuses the act, as it does for a plan. The engine takes the gates as an injected `gates` callable (`jason.workflows.api.attest` and `skip`); its default, `jason.controls.effective.workflow_gate`, is looked up when an act is made and reads nothing when no controls source is configured.
- **Sends.** The Mailroom's class and tracking defaults, and whether a send needs a second person, read the adopted controls.
- **Spend.** A plan that moves money, over an adopted threshold, needs the extra approval. No registered kind moves money yet (attaching a bill to a PayHOA transaction pays nothing), so a control binds a kind only when scoped to it by name or family until the first money kind is registered. jason computes nothing about the law here: the threshold is the board's number.
- **The roster check.** Before the effective date, jason checks the roster can satisfy the control (enough directors, an officer for each named role) and warns the board if it cannot: the control is `adopted`, not yet in force. From the effective date the control binds. If the roster then cannot satisfy it (a seat falls vacant), the act is refused and the reason is given; jason never falls back to the kind's own weaker rule. The board answers by filling the seat, or by deciding to modify or retire the control.

## 6. The screens

- **Controls** (Governance, beside Documents): the suggestions, grouped by family; each card shows the quoted provision, the floor, jason's suggestion labeled as such, what it would change, and its state. "Propose to the board" creates the board item; nothing else is a button. Adoption is recorded in Decisions, by the secretary.
- **Onboarding:** after the governing documents are ingested and their duties read, the session offers "Controls jason suggests from your documents" as one step, with the same cards, and the board can take them to a meeting or leave them.
- **Wherever a control bites:** a plan, a step, or a send shows "Required by a control the board adopted on DATE" with a link to the control, so a person is never blocked without a reason.
- Directors and officers have the same access to information; the secretary records the decisions; a control is not a permission and never narrows what a board member may read.

## 7. What exists now, and what to build

| Piece | State |
|---|---|
| Approver rules on action kinds (`ONE_PERSON`, `TWO_PERSON`) and the second-person rule | built (`jason.approvals.registry`) |
| Second-person confirmation of high-stakes onboarding answers | built (`POST /api/write/intake/<id>`) |
| The roster and each person's `approves` (drafts jason writes) | built (`Community.officers()`); it is not a signer list for payments |
| The documents' duties, read and checked | built in part (`document_duties`, `careful-reading`, the key documents); no extraction of signers or limits |
| Board items and the board's decisions, recorded by the secretary | built (`jason board`, `decisions.json`) |
| Rule rows with an `adoption` board item (the response rules) | built; the model for "a row the board has adopted" |
| The `Control` and `ControlType` records, the catalog of nine control types with floors, the append-only act log (`data/controls/acts.jsonl`), the effective-approver lookup (stricter-of, binding from the effective date, refusing an act the roster cannot satisfy) and its hook in the approvals engine (`jason.controls`) | built (step 1, 2026-10-11) |
| Who may sign: `roles` (the offices that may sign) and `must_include` (offices among the signers) are checked against the roster (`Community.officers()`, a signer matched by name; a name not on the roster holds no office) when a person submits and when a person confirms, and again before apply (`jason.controls.effective.signer_refusals`, `engine.signer_refusals`). `roles` binds every signer. `must_include` binds the signers as a whole: a first signer need not hold the required office when a second follows, and the approval is refused at the last signature, and at apply, unless the set holds it. Each control is asked on its own, so two controls with no office in common leave no one who may sign. A control that asks only above an amount is not asked of a plan at or below it. A roster that cannot be read leaves the offices unchecked (the second signer is still required). | built (2026-10-11) |
| The suggestion reader (`jason.controls.suggest`: general phrase evidence on each catalog type, the provision whole, a floor only where one count is certain, a question where the match is weak; it runs only after the duties are confirmed read, `Community.duties_read()`), `jason controls` (list, show, suggest and record, roster check, propose), the loaders `controls`, `control`, `control-notices` and the writer `POST /api/write/controls/<key>` (`{act: "propose"}` only) | built (steps 2 and 3, 2026-10-11) |
| Categories on approval kinds (`ActionKind.categories`, default empty: `"payment"` for a kind that pays or commits the association's money, `"reserve"` for one that moves reserve funds) | field built; none set. The three registered kinds (owner-information tags, bill attachment, Gmail drafts) move no money: attaching a bill to a transaction pays nothing and approves nothing. So a control scoped to all (payment or reserve signers) binds nothing until the first money kind is registered with its category; scope it to a kind or a family meanwhile. `touches` says so. |
| Controls on workflow steps: `Governs(WORKFLOW_STEP, pattern)`, `effective.step_gates` (a resolution first, a second person, the offices that may record), `step_unmet`, the engine's `gates` and `workflow_gate` (attest and skip refused with the control's sentence, a second person's confirmation), `step_controls` on the work-run loader (`controls` on a step, only when controls are configured), `ControlStepNotice` on the run step | built (2026-10-11) |
| The Controls screen, the `control-adoption` run (eight steps), the onboarding step (one board item per suggestion, proposed one at a time) | built (2026-10-11) |
| A command that records the board's outcome on a control (`jason controls --adopt/--decline/--defer` with `--decision`, `--effective`, `--by`) | not built; the secretary records it in Decisions and the act log by `jason.controls.store.record` |

**Build order:** (1) the catalog and the record, with the effective-approver lookup in the approvals engine (a control may only tighten), tested on made-up controls; (2) the suggestion reader for the first three families (payment and reserve signers, contract authorization, review cadence), quoting from the stored governing documents; (3) the `control-adoption` run and the board item; (4) the Controls screen and the onboarding step.

## 8. Decisions for the board

- Which control families to offer first (recommended: payment and reserve signers, then contract authorization, then review cadence).
- Whether a control can apply to one account, one kind, or all (recommended: all three; every control that applies binds, and in each respect the stricter one governs).
- Whether an adopted control takes effect on the meeting date or a later date the board names (recommended: the board names it).
- Whether a declined suggestion may be asked again (recommended: only after the date the board set, or when the provision changes).
