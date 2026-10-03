# Interaction patterns

The patterns the console uses for the things it does most: show a plan, take approvals, catch a stale plan, handle what cannot be undone, tell a person what changed, show dense tables, work from the keyboard, and meet WCAG 2.2 AA. Each pattern gives the recommendation first, then the sources behind it, each with one short quote.

The quotes were checked against the pages on Oct 3, 2026. Each is under 15 words.

## Showing a plan as a diff

**Recommendation**
- **One row per write, as before → after.** `WriteRow` shows the change's sign as a word with a mark: "+ add", "− remove", "~ change", the old value struck (`<del>`) and the new one inserted (`<ins>`). The sign is never color alone.
- **Group by target.** One owner's or one unit's changes read together, with a group header and group-level approve and reject. A dependent item (a request completion) sits at the end of its group as "Then: …", naming what it waits on.
- **The reason sits on the row.** The planner's `why`, then the rule with **recite**, then the evidence chips. A person should never leave the row to learn why a write exists.
- **What will not happen is in the plan.** Held for the board, for a person, confirm with the owner, and test accounts left out each have their own section under the approvable writes, with counts in the header. A plan that hides what it will not do misleads by omission.
- **The whole plan before the decision.** Like a "check your answers" page, the approval page is the summary a person signs. Nothing approvable is on another page or behind pagination: a long plan uses grouping and the "Show: undecided" filter, not pages.
- **Mark what a person has already looked at, and unmark it when it changes.** A row decided, then changed by a re-plan, shows "changed since review" and loses its decision.

**Sources**
- Terraform's plan is a preview that "does not actually carry out the proposed changes" ([Command: plan](https://developer.hashicorp.com/terraform/cli/commands/plan)). Its `+`, `-`, `~` marks are the model for the write row's signs.
- GitHub resets a file's viewed mark when it changes: "If the file changes after you view the file, it will be unmarked as viewed" ([Reviewing proposed changes](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/reviewing-proposed-changes-in-a-pull-request)).
- GOV.UK's check-answers pattern lets people "check their answers before submitting information to a service" ([Check answers](https://design-system.service.gov.uk/patterns/check-answers/)).

## Bulk and per-item approval

**Recommendation**
- **Per item is the record; bulk is a shortcut.** "Approve all approvable" and "Approve group" set each item's decision, and the log records each one ([approval-workflow.md](../approval-workflow.md#5-approval-by-item)).
- **Nothing is pre-checked.** The default is undecided.
- **Say exactly what is selected,** in a live count: "5 of 8 approved · 1 rejected · 2 undecided". "All" means every approvable item in this plan, including rows filtered out of view, and the count says so.
- **Bulk never reaches a held item.** Held, for-a-person, and confirm items have no checkbox at all, so no bulk action can select them.
- **The bar acts on what is decided, and names it:** "Approve 8 of 10 changes as Jane Example".
- **A rejection needs a reason, even in bulk.** "Reject group" asks one reason for the group, logged on each item.

**Sources**
- Helios (HashiCorp) advises: "Display the selected count to communicate how many rows or results have been selected" ([Table multi-select](https://helios.hashicorp.design/patterns/table-multi-select)).
- Carbon puts batch actions in context: "the batch action bar appears at the top of the table" ([Data table](https://carbondesignsystem.com/components/data-table/usage/)). The console keeps its bar at the foot, sticky, because the decision closes the review; see [focus not obscured](#accessibility-wcag-22-aa).
- NN/g's bulk-action guidance asks for clear feedback and undo ([Bulk actions](https://www.nngroup.com/videos/bulk-actions-design-guidelines/)). Here, undo before submit is simple: a decision can be changed until the person submits.

## Stale-plan detection

**Recommendation**
- **Bind every signature to a fingerprint.** A stored approval's items never change: a re-plan is a new approval. So a decision or a signature names the approval by id, and the engine refuses one on an approval that is superseded or withdrawn. Apply goes further: it echoes the fingerprint the person reviewed, and the server refuses a mismatch (409) and changes nothing: "This plan changed since you opened it. Reload to see the new plan." This is optimistic concurrency, as HTTP's `If-Match` and 412 do.
- **Re-plan at apply, always.** A stored plan's live state is never trusted. If an approved item's basis differs, refuse the whole apply, supersede the approval, and open a new one with the changed items marked and earlier decisions shown as hints.
- **Show the age of the read** in the header ("live read Oct 3, 08:40"), and refuse apply past the kind's `max_age_hours` with a re-plan button.
- **Changed-since-review is a banner first in the content,** with what changed and one action, the new plan to review (`ChangedBanner`). `ApproveBar` is blocked while it shows.
- **New items do not block.** Writes new since review are noted ("3 writes new since review, not included") and wait for the next plan.

**Sources**
- Terraform refuses a stale saved plan: "The given plan file can no longer be applied because the state was changed" ([hashicorp/terraform#21785](https://github.com/hashicorp/terraform/issues/21785); an issue thread, not the official docs).
- GitHub can "dismiss stale pull request approvals when commits are pushed that affect the diff" ([About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)).
- With `If-Match`, a 412 response lets "you prevent conflicts or mid-air collisions" ([MDN: 412 Precondition Failed](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/412)).

## Undo and no undo

Most of jason's PayHOA writes can be reversed by another write: a tag added can be removed. A send cannot: an email delivered, a letter mailed, a comment PayHOA emailed to an owner. The console treats the two differently, and says which is which before anyone approves.

**Recommendation**
- **State reversibility on the plan,** from the kind's `reversible` column: "Reversible: yes, a tag is removed". For a mixed kind, split it: "Status yes; the owner's email no."
- **Before submit, everything is undoable.** A decision can be changed until the person submits, so the console asks for no confirmation on deciding.
- **Reversible writes: no extra confirmation.** The submit button already names the action, the count, and the signer. A dialog on top of that would train people to click through.
- **Irreversible writes: type to confirm.** Apply asks the person to type the count of letters or messages, after a sentence that says what happens, what it costs, and what cannot be recalled. This is the one place the console uses a confirmation step.
- **No "undo" button for a write outside `data/`.** Reversing a PayHOA write is a new plan, reviewed and approved like the first. An "undo" that silently wrote to PayHOA would bypass the approval.
- **Cancelling a send in flight** (a Mailroom letter still processing) is its own kind, `payhoa.mailroom.cancel`, and says what it saves and what it may miss: "Cancelling may miss the notice's deadline."

**Sources**
- NN/g on confirmations: "If you cry wolf too many times, people will stop paying attention" ([Confirmation dialogs](https://www.nngroup.com/articles/confirmation-dialog/)). The same article urges offering undo wherever possible.
- GitHub asks a person to "type the name of the repository you want to delete" before an irreversible delete ([Deleting a repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/deleting-a-repository)).

## Notifications

**Recommendation**
- **Inline first.** A result appears where the action was taken: `ApplyResult` replaces `ApproveBar`; a refused field shows its error beside it.
- **No toasts.** jason-ui has none. The result itself (applied, failed, refused) stays inline on the page, where the person can read it again.
- **Status messages are announced without moving focus** (`role="status"`); a failure that stops the work uses `role="alert"`.
- **The navigation's counts are the console's notification center.** "Approvals 2", "Requests 3", with words for a screen reader. Nothing pops up.
- **The digest decides what is urgent,** not the console. LEGAL first, then overdue, due soon, open, noted. The console adds no urgency of its own.
- **No email or push notifications in phases 1 to 4.** jason's only send path to people is a Gmail draft a person sends.

**Sources**
- NN/g: an indicator or validation "should be shown in close proximity to that element" ([Indicators, validations, and notifications](https://www.nngroup.com/articles/indicators-validations-notifications/)).
- Carbon: notifications "are disruptive and should be used sparingly" ([Notification usage](https://carbondesignsystem.com/components/notification/usage/)). The same page warns that a toast dismisses itself, so its content needs another route.

## Dense tables

**Recommendation**
- **Built for the four jobs:** find a row, compare rows, read one row, act on rows. Sorting in the column headers and a filter box (`DataTable`), and a search where names are involved that never puts the words in the route.
- **Sticky header row; first column fixed** when the table scrolls sideways inside its own frame. The page itself never scrolls sideways.
- **Two densities:** comfortable (40 px rows) by default, compact (32 px) as a stored preference. Never below the 24 px target size for a row's controls.
- **Numbers right-aligned, in tabular figures.** Dates in one format. Status as a word badge.
- **One action per row, at most two.** More go on the row's own page.
- **A caption that says what the table is and how it is sorted,** for a screen reader: "Open requests, most urgent first."
- **Counts above the table, never only at the foot:** "14 open: 2 overdue · 3 due soon · 9 open".

**Sources**
- NN/g: "Freeze header rows and header columns (if the table is larger than the screen)" ([Data tables: four major user tasks](https://www.nngroup.com/articles/data-tables/)).
- Carbon: "Sorting controls are located in the column headers" ([Data table usage](https://carbondesignsystem.com/components/data-table/usage/)).

## Keyboard use

**Recommendation**
- **Everything works with Tab, Shift+Tab, Enter, and Space.** Every control is a real `<button>`, `<a>`, or form field, in reading order.
- **The skip link** goes to `<main>`. `ConsoleShell` has none yet; it should come first in the header.
- **Approval rows are a list of form controls, not an ARIA grid.** A grid's arrow-key model suits a spreadsheet; an approval needs each decision reachable by Tab, read in order. Groups are `<fieldset>`s with legends naming the owner.
- **Shortcuts on the approval page, with a modifier or only while a row has focus:** `j`/`k` move between rows, `a` approves and `r` rejects the focused row, `?` lists the shortcuts. Single-key shortcuts can be turned off (a preference kept in the browser), and are off by default for a speech-input user who asks.
- **Focus moves with the work:** after a group is decided, to the next undecided group; after apply, to `ApplyResult`'s heading; after a refusal, to the error.
- **Returning from a recitation** (opened from an item's **recite**) puts focus back on that item.

**Sources**
- The ARIA grid pattern: "Only one of the focusable elements contained by the grid is included in the page tab sequence" ([APG: Grid](https://www.w3.org/WAI/ARIA/apg/patterns/grid/)). That is right for a spreadsheet and wrong for a list of decisions, which is why the console does not use it here.
- GitHub notes "You can disable character key shortcuts, while still allowing shortcuts that use modifier keys" ([Keyboard shortcuts](https://docs.github.com/en/get-started/accessibility/keyboard-shortcuts)).
- WCAG 2.1.4 requires that "A mechanism is available to turn the shortcut off" ([Understanding 2.1.4](https://www.w3.org/WAI/WCAG22/Understanding/character-key-shortcuts.html)).

## Accessibility: WCAG 2.2 AA

The console meets WCAG 2.2 AA. These criteria matter most in a dense approval console.

| Criterion | What the console does |
|---|---|
| **2.4.7 Focus visible** | A 2 px focus ring in the focus token, with a 3:1 contrast against both the background and the control, on every focusable element, including rows reached by shortcut |
| **2.4.11 Focus not obscured (minimum)** | The sticky approve bar and the sticky page header reserve their height (`scroll-padding-top`, `scroll-padding-bottom`), so a focused row scrolls clear of them. A non-modal panel never covers the field that opened it |
| **2.5.8 Target size (minimum)** | Every checkbox, decision button, chip, and copy button is at least 24 by 24 CSS pixels, or spaced so a 24 px circle around it touches no other target. The row checkbox's label is the whole first cell |
| **4.1.3 Status messages** | The selected count, "Approved 8 of 10 changes", "Applied 3 of 5", "Reading the store…", and a re-check's result are in `role="status"` regions. A refusal that stops the work uses `role="alert"`. Focus does not move to announce them |
| **3.3.7 Redundant entry** | The approver's name is pre-filled with the acting person. A rejection reason given for a group is not asked again per item. The second person's name starts empty, under the exception for security |
| **3.3.8 Accessible authentication (minimum)** | There is no sign-in today: "Signed in as" is a pick from a list. Sign-in, when it comes, uses passkeys, with nothing to remember or transcribe |
| **1.4.3 Contrast (minimum)** | 4.5:1 for text, including badge text and muted metadata; 3:1 for icons and borders that carry meaning |
| **1.4.1 Use of color** | Every status, sign, and urgency is a word; color and mark only repeat it |
| **1.3.1 Info and relationships** | Tables have captions and header cells; groups are fieldsets with legends; a recitation is a `<figure>` with `<blockquote>` and `<figcaption>` |
| **2.5.7 Dragging movements** | No drag anywhere. Reordering, where it exists, has buttons |

**Sources**
- 2.4.11: a focused component "is not entirely hidden due to author-created content" ([Understanding 2.4.11](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html)).
- 2.5.8: a target is "at least 24 by 24 CSS pixels", or spaced to pass ([Understanding 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)).
- 4.1.3: status messages are "presented to the user by assistive technologies without receiving focus" ([Understanding 4.1.3](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html)).
- 2.4.7: there must be "a mode of operation where the keyboard focus indicator is visible" ([Understanding 2.4.7](https://www.w3.org/WAI/WCAG22/Understanding/focus-visible.html)).
- 3.3.7: information entered before is "either: auto-populated, or available for the user to select" ([Understanding 3.3.7](https://www.w3.org/WAI/WCAG22/Understanding/redundant-entry.html)).
- 3.3.8: the guidance lists "Support for password entry by password managers to reduce memory need" ([Understanding 3.3.8](https://www.w3.org/WAI/WCAG22/Understanding/accessible-authentication-minimum.html)).
