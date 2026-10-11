# Design index: where the design agent starts

Every design brief and screen spec for the console, in the order to read them. A brief is one page of orientation for a design agent (the idea, the rules, the screens, the components, a made-up community to draw against). A spec is the whole screen, with its data, layout, states, privacy, and acceptance criteria. The model underneath all of them is [../workflows-design.md](../workflows-design.md); the engine is [../workflows-engine.md](../workflows-engine.md).

**The rules that run through every one** (each brief repeats the ones that bite):
- Directors and officers have the same access to information; they differ in duties. There is no director-only view. A step or a field shows what the viewer's level allows (P0 to P3, `access.py`), and an owner never sees these screens.
- The secretary is the board's official record keeper and records the board's decisions. jason decides nothing, sends nothing, mails nothing on its own: a person runs the command or approves the plan.
- A statute is recited from the stored text, then jason's reading follows, labeled as a reading. Every date has a basis word (law, documents, counterparty, proposed policy, person); a proposed number is never drawn as a stamp.
- Use only made-up data ("Oakview", "123 Main St", "A. Owner", 2099 dates). Nothing in the repository names a real association.
- Each brief says what is built and what has no view yet. Draw the unbuilt parts from the sample and say so.

## 1. Read first

| Order | Brief | What it covers |
|---|---|---|
| 1 | [screens/office-views.md](screens/office-views.md) with [screens/today.md](screens/today.md) | The landing page per office, and the lens that lets any board member read another's. Draw it first: it frames who sees what. |
| 2 | [design-brief-work.md](design-brief-work.md) with [screens/work.md](screens/work.md) | The Work list, the run page, the seven step kinds, starting a run, the definitions catalog, and the rule for where a step's work happens (the run embeds reads and links writes). Every family's long task is a run drawn here. |
| 3 | [design-brief-fonts-and-theme.md](design-brief-fonts-and-theme.md), [design-brief-limits.md](design-brief-limits.md) | The theme and type decision, and the instance limits page (a worked example of a small brief). |

## 2. The families

| Family | Brief | Specs it rests on |
|---|---|---|
| The members: forms, campaigns, arrivals, follow-ups | [design-brief-forms.md](design-brief-forms.md) | [handoff-forms-and-arrivals.md](handoff-forms-and-arrivals.md), [handoff-responses.md](handoff-responses.md), [handoff-followups.md](handoff-followups.md), [handoff-form-library.md](handoff-form-library.md) |
| Requests and onboarding | [design-brief-requests-and-onboarding.md](design-brief-requests-and-onboarding.md) | [screens/requests.md](screens/requests.md), [screens/onboarding.md](screens/onboarding.md) |
| Notices and the Mailroom | [design-brief-notices-and-mailroom.md](design-brief-notices-and-mailroom.md) | [screens/notices.md](screens/notices.md), [screens/mailroom.md](screens/mailroom.md) |
| Money: bills, payments, mail | [design-brief-mail-and-payments.md](design-brief-mail-and-payments.md) | [handoff-mail-and-payment-attachments.md](handoff-mail-and-payment-attachments.md), [screens/finance.md](screens/finance.md) |
| Money: reviews and collections | [design-brief-money-reviews.md](design-brief-money-reviews.md) | [screens/monthly-review.md](screens/monthly-review.md), [screens/delinquency-process.md](screens/delinquency-process.md) |
| The annual disclosures | [design-brief-annual-disclosures.md](design-brief-annual-disclosures.md) | [handoff-annual-disclosures.md](handoff-annual-disclosures.md), [screens/collect-items.md](screens/collect-items.md) |
| The board: meetings and the calendar | [design-brief-governance-calendar.md](design-brief-governance-calendar.md) | [screens/meetings-and-minutes.md](screens/meetings-and-minutes.md), [screens/schedule-and-duties.md](screens/schedule-and-duties.md), [screens/today.md](screens/today.md) |
| Controls: the safeguards jason suggests and the board adopts | [design-brief-controls.md](design-brief-controls.md) | [screens/controls.md](screens/controls.md), [../controls.md](../controls.md) |
| The board: records, elections, hearings, the law | [design-brief-board-records.md](design-brief-board-records.md) | [screens/elections.md](screens/elections.md), [screens/incidents.md](screens/incidents.md), [screens/hearing-process.md](screens/hearing-process.md), [screens/law-review.md](screens/law-review.md), [screens/board-items.md](screens/board-items.md) |
| Property, safety, vendors | [design-brief-life-safety.md](design-brief-life-safety.md), [design-brief-property-and-units.md](design-brief-property-and-units.md) | [screens/life-safety.md](screens/life-safety.md), [screens/paint.md](screens/paint.md), [screens/unit-record.md](screens/unit-record.md), [screens/members-and-units.md](screens/members-and-units.md), [handoff-contracts.md](handoff-contracts.md) |
| The platform: integrations and the instance | [design-brief-platform.md](design-brief-platform.md) | [screens/integration-disconnect.md](screens/integration-disconnect.md), [handoff-instance-and-integrations.md](handoff-instance-and-integrations.md), [screens/limits.md](screens/limits.md), [screens/status.md](screens/status.md) |

All the other pages in [screens/](screens/README.md) are one screen each.

## 3. What to check before drawing

- [design-gaps.md](design-gaps.md): the audit of what has no spec yet, with what is built and what has no view. It is dated; a brief's own "checked against the code" paragraph is newer for its subject.
- [../workflows/README.md](../workflows/README.md): the six family pages, the decisions already taken, and the decisions still waiting on the board.
- Components: [components.md](components.md) maps each to what is built, being added, or proposed. A name a brief uses that is not in `ui/src/components` is specified, not built: draw it from the built parts.

## 4. Open decisions that change a drawing

- Decided 2026-10-11 (no longer open): the treasurer opens the private view (P3), like the manager, president, vice president, director, and secretary; the board decided that directors and officers have the same access to information. Draw one private-view switch for every office that opens P3.
- Whether a notice letter defaults to first class (it now does) and whether earlier standard mailings need a board look (a board item is proposed).
- Which store "record a posting" writes (the notice ledger or the schedule's done log), and whether meeting steps m12 and m20 are read-and-link.
- Whether the Work screen's definitions catalog and the Today "Your work" band ship in the first phase.
