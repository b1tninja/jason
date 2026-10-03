# Components

The inventory every screen draws from. The library lives in `src/jason/console/ui/`:
- `tokens.css`, the design tokens;
- `base.css`;
- `components/<name>.html`, `<name>.css`, and an optional `<name>.js`.

Each `.html` file is reference markup with its states and variants in a header comment. The templates turn each one into a Jinja macro of the same name ([architecture.md](architecture.md#stack)).

This page holds the names, purposes, states, and variants: the contract between the screens and the library. Per-screen layouts are in [screens/](screens/). The words on screen are in [content/style.md](content/style.md) and [content/patterns.md](content/patterns.md).

**Conventions** (from the library as built):
- **Classes** are `jc-<component>`, with BEM elements and modifiers: `.jc-write__why`, `.jc-badge--held`.
- **Colors are roles, never hues.** `--jc-accent`, `success`, `warning`, `danger`, `info`, `held`, and `neutral`, each with `-soft` and `-border`.
- **Every state is in words.** Color and icon only repeat the word, and an icon is `aria-hidden`.
- **No component needs script to do its job.** A `.js` file enhances; the server enforces.
- **Sample markup uses plainly fake values:** "Example Village HOA", "Jordan Example", "123 Main St".

## Layout

| Component | File | Purpose | States and variants |
|---|---|---|---|
| App shell | `app-shell` | The frame of every page: the skip link, the top bar (jason, the profile's name, the acting person), the nav, and `<main id="main">` | Under 960 px the nav goes above the content. Private view on: the top bar shows a `held`-role strip, "Private view: restricted records shown", with "turn off" |
| Nav | `nav` | The sections in [information-architecture.md](information-architecture.md#navigation) order. Counts have words for a screen reader | `aria-current="page"` on the current section. `.jc-nav__count--attention` when something there is past a clock. Onboarding is shown only while a gate is closed |
| Page header | `page-header` | The page's only `<h1>`. Optional breadcrumb, subtitle, meta line (badges, freshness), and actions | The primary action goes last. The meta line carries "read from disk, synced <time>" or "read live <time>" |

## Status and identity

| Component | File | Purpose | States and variants |
|---|---|---|---|
| Status badge | `status-badge` | The state of an approval, an item, or a record, as a word | **Approval:** `--planned --review --approved --partial --applying --applied --failed --superseded --withdrawn`, matching `ApprovalStatus` one for one. **Item result:** `--applied --failed --changed --blocked --uncertain --not-applied`. **Item class:** `--held` (for the board), `--person`, `--confirm` (with the owner). **Records:** `--open --overdue --due-soon`. Size `--sm` for table cells |
| Clock or deadline badge | `deadline-badge` | Time left or past, with the date in `<time>` | `--soon` (7 days or fewer), `--today`, `--passed`, `--met`. `--legal` adds "Legal", with a title naming the source; the citation is the item's own (`attention.Urgency.LEGAL`). It maps to the digest's urgencies: LEGAL is `--legal --passed`, OVERDUE is `--passed`, due soon is `--soon` |
| Stage-gate stepper | `stage-stepper` | The onboarding stages in order (start, ingest, establish, operate, adopt), from `onboarding_status()["gates"]` | Each stage is closed (its gate passed, with the date) or open, naming what it waits on (`waiting`, `checks`). `aria-current="step"` on the stage being worked |
| Person chip | `person-chip` | Who requested, decided, confirmed, or applied: initials (hidden), the full name, an optional role | `--agent` for jason: a plan or a reading, **never** a decision or a signature. `--board` for the board as a body. `--you` for the acting person. An approval card shows "planned by" jason (`--agent`) and "requested by" a person; they are two chips, never one |
| Held-for-board banner | `held-banner` | Above items the board must decide first: how many, why, and the board item | `role="note"`. `--inline` for one line in a write row or card. It always says that approving the rest never approves a held item |

## Approval

| Component | File | Purpose | States and variants |
|---|---|---|---|
| Approval card | `approval-card` | One approval in a list: kind (the `ActionKind.title`), a summary, planned by and requested by, the counts, the status, and the clock | Counts are writes, targets, held, for a person, and to confirm with the owner. A zero count is left out. A 2P kind shows "needs a second person". It carries a deadline badge when the kind has a clock |
| Write or diff row | `write-row` | One `PlanItem`: select, the change (`+` add, `-` remove, `~` change, with words for a screen reader), before → after (`<del>` and `<ins>`), why, the rule (a short recited citation linking the recitation), the evidence chips, and the state. One `<tbody>` per target group, starting with a header row; `.jc-writes__then` shows what follows the group (a completion waiting on its writes) | `--held` (planner's class): no checkbox and an inline held note. `--person`: no checkbox, with the task for a person. `--confirm`: no checkbox. `--changed`: changed since review, with the old and new basis on request. After a decision: approved, rejected (with the reason), or held by a person (with the reason). After apply: a result badge |
| Evidence chip | `evidence-chip` | A link to what an item rests on. The kind is a word | `--form`, `--document`, `--email`, `--record`, `--ledger`, and **`--rule`** (a statute or rule row: it opens the recitation). `--missing` is a span, not a link. `--confidential` is held back unless asked. A P2 or P3 target asks before revealing |
| Changed-since-review banner | `changed-banner` | The live state moved: both fingerprints (12 hex), what changed, the new approval's link, and a re-plan action that works without script | Static with a heading on load. `role="alert"` when inserted after load. It disables the approve bar's Approve |
| Approve bar | `approve-bar` | A sticky form: the selected count, the name field (pre-filled with the acting name), the cost line, and the actions **Approve selected**, **Reject selected** (with a reason), and **Hold for the board** (with a reason). It posts the fingerprint and the CSRF token | `--blocked` (changed since review). `--submitted`, which swaps in "Apply", "Withdraw", and, for a 2P kind, "Waiting for a second person". No action is enabled with nothing selected. Its height is set as `scroll-padding-bottom` on the page, so a focused row is never under it (WCAG 2.4.11) |
| Second-person confirm | `confirm-panel` | States the two-person rule in words, shows who answered or approved, and asks for the confirmer's full name. The same panel serves an approval's second signature and a high-stakes intake answer (`onboarding_confirm`) | Waiting (the default), `--refused` (same name: the script says so before sending, the server refuses anyway), `--confirmed` (both people shown), and `--declined` (with the reason). The name field starts **empty** |
| Cost summary | `cost-summary` | What the action will charge, line by line, in dollars from integer cents. Whether it is an estimate, who is charged, and the price source (`payhoa.pricing`, PayHOA's preview) | `--none` ("No charge: PayHOA tag changes"), `--over` (over a limit, flagged in words). It shows the billed pages per letter, and the extra postage past the fifth billed page |
| Result panel | `result-panel` | What an apply did: the counts of applied, failed, changed, blocked, and not applied, each list in a `<details>` (failed open by default) | Default (all applied), `--failures`, `--refused` (a re-plan found a change, nothing written: it links the new approval). `role="status"` when it replaces the approve bar |

## Text and data

| Component | File | Purpose | States and variants |
|---|---|---|---|
| Recitation block | `recitation` | The words whole from the stored text, the citation, the version in force, and the caveat (`community.cite.CAVEAT`) | `--not-in-force` (not the version in force on the date asked). `.jc-omission` for a marked omission. `<mark>` for the words that answer. `.jc-term` linking a definition, which is recited too. `.jc-recited` for a short recital in running text. A reading never goes inside it |
| Reading label | `reading-label` | A reading of recited words, labeled with whose it is: jason's, the board's (with its adoption date), or counsel's | `--open`: two readings remain, and the board asks counsel. `.jc-decision` for a person's decision, set apart from both recited words and a reading |
| Data table | `data-table` | Dense rows, a sticky header, sortable columns, inside a scrolling `.jc-table-wrap` with `tabindex="0"`, `role="region"`, and a label | `--zebra`, `--compact`. `data-sort-value` for dates and money. Row selection by checkbox only (no drag, WCAG 2.5.7). A masked P2 cell uses the masked field |
| Filters bar | `filters-bar` | A GET form: search, selects, and toggle chips. `role="search"`. The summary line says "12 of 80 shown" | It works with no script. **Searches for a person by name or email are a POST** with no query string ([security-and-privacy.md](security-and-privacy.md#urls)) |
| Empty, loading, and error states | `states` | Empty: what is not there, and what to do. Loading: `aria-busy` with words. Error: what failed, where it stopped, and the next action | **Unavailable** (a missing store: the reason and the command that fills it, from `attention.Section.error`). **Sign-in needed** (`KeeperAuthRequired` or `GoogleAuthRequired`: "run `jason login` in a terminal"; never a password field). **Busy** (`ResourceBusy`: who holds the lock) |
| Toast | `toast` | A short message after an action, with a link to it | `--success`, `--error` (`role="alert"`), `--held`. No timer: it stays until dismissed (WCAG 2.2.1) |

## Activity

These two are not in the library yet.

| Component | File | Purpose | States and variants |
|---|---|---|---|
| Audit timeline | `audit-timeline` | An approval's (or the whole log's) events, newest last: the time, the person chip, the event in words, the item, and the result. It is an ordered list (`<ol>`), not a table, so it reads in order | Event kinds in the log's own words: planned, decided, submitted, confirmed, declined, apply started, refused (changed), applied, failed, superseded, withdrawn, revealed (the field's kind only), private view on or off. `--compact` inside an approval. A "chain verified" or "chain broken at line N" line from `audit.verify` |
| Queue item | `queue-item` | One ranked question or task in a queue: the rank, what it unblocks (`Unblocks`: a legal clock first), the question, the choices with jason's suggestion (labeled as jason's), the evidence chips, and the answer form | `--likely` (a suggestion strong enough to accept after a look), `--high-stakes` (needs a second person: the confirm panel follows), `--answered` (by whom, and when), `--refused` (a secret: the `SecretRefused` message; nothing kept). Used on Today (the next questions) and Onboarding |

## Also needed

The screens need these, and the library does not have them yet:

| Component | File | Purpose | States and variants |
|---|---|---|---|
| Masked field | `masked-field` | A P2 value as the server masked it (`a••••@example.com`), with "Show". Show is a POST that returns this one field and logs the reveal | Masked, revealed (with "Hide"), and not allowed (the role cannot reveal: no button, and a note). The full value is never in the page until revealed |
| Private-view switch | `private-switch` | Turns the private view on, asking for a reason, and off. It is in the page header | Off (the default) or on (the strip in the app shell). Expiring: 2 minutes before the idle limit it offers to extend (WCAG 2.2.1) |
| Job status | `job-status` | Long work started from the console: what runs, who started it, the last lines of progress, and the result link | Queued, running (`aria-busy`, with progress in `role="status"`), done (a link to the new approval), failed (the error and the fix command). No script: a Refresh link |
| Freshness line | `freshness` | When a section's store was last synced, and the command that refreshes it | Fresh, stale (older than the section's own limit), never synced (unavailable) |

## Accessibility

The console meets WCAG 2.2 AA ([W3C](https://www.w3.org/TR/WCAG22/)). A dense admin console stresses these criteria most, so each component owns them:

- **Keyboard (2.1.1, 2.4.3, 2.4.7).**
  - Every action is a native control in DOM order.
  - The skip link comes first.
  - The focus ring uses `--jc-focus`.
  - No `tabindex` above 0.
  - Table scrolling regions are focusable and labeled.
- **Focus not obscured (2.4.11).** The sticky approve bar and the top bar are offset with `scroll-padding`, so a focused row is never hidden under them.
- **Target size (2.5.8).**
  - Controls are 28 px high (`tokens.css`).
  - Row checkboxes sit in a label that fills the cell, so the target is at least 24 by 24 px.
  - Chips in a filters bar are whole-label targets.
- **Dragging (2.5.7).** Nothing needs a drag: selecting, ordering, and resizing all have buttons.
- **Contrast (1.4.3, 1.4.11).** Role text is at least 4.5:1 on its surface and soft fill, and borders on components at least 3:1, as `tokens.css` states. Dark mode keeps the same ratios.
- **Use of color (1.4.1).** Every state is a word first.
- **Reflow (1.4.10).** At 320 CSS px wide, the page does not scroll sideways. Wide tables scroll inside their own region.
- **Status messages (4.1.3).**
  - Toasts, the job status, the result panel, and the approve bar's live count use `role="status"` or `aria-live="polite"`.
  - Errors that replace content use `role="alert"`.
- **Labels and errors (1.3.1, 3.3.1, 3.3.2, 3.3.3).**
  - Every control has a visible label.
  - An error names the field and says how to fix it: "That is the name that approved it. A second person confirms."
- **Timing (2.2.1).**
  - The idle limits (the session, and the private view) warn first and can be extended.
  - Toasts never time out.
  - A form in progress is never lost to a timeout: decisions are saved as made (`in review`).
- **Redundant entry (3.3.7).** The approver's name is pre-filled. Only the second person's field starts empty, under the criterion's security exception.
- **Accessible authentication (3.3.8).** The sign-in token can be pasted, or carried by the link. It is never typed from memory, and nothing asks for a transcription or a puzzle.
- **Consistent help (3.2.6).** Each page's "how this works" link (to its CLI command and doc) sits in the same place in the page header.
