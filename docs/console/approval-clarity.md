# What "approve" means: making a plan's stages plain, and opt-in ways to apply

**The problem (reported 2026-10-11).** A board member reviewed a plan of owner notice-delivery changes, pressed **Approve**, and believed the changes were made. They were not. The plan has five stages, three of them wear the word "approve", and nothing on the page says that **nothing has been written yet**. The board is glad the flow gives a chance to review, so that one accidental click cannot make an undoable change. The flow stays. What changes is how plainly the page says where you are, what each button does, and what happens next.

This page specifies the wording, a progress strip, a standing "nothing written yet" line, a "waiting to be applied" state that does not get forgotten, and opt-in preferences for how a board wants plans applied. The engine's rules (two people, fingerprints, re-plan before apply, terminal-only kinds) do not change.

## 1. What actually happens (the stages)

| # | Stage | Who | What it does | What is written |
|---|---|---|---|---|
| 1 | **Review** | any board member or the manager | marks each change *approved*, *rejected*, or *held* (a note says why) | only the decision, in jason's own plan record |
| 2 | **Sign** | the person who reviewed | signs the plan on its fingerprint: "I stand behind these decisions" | the signature |
| 3 | **Second signature** | a different person, where the kind or a control requires two | confirms the same fingerprint | the second signature |
| 4 | **Apply** | a named person, at a terminal or (where the board allows) with a console button | jason reads the live system again and, if nothing moved, makes the approved changes | **the changes, for the first time** |
| 5 | **Done** | jason | reads back and records what was applied, what failed, what was refused | the result |

Today the buttons read "Approve 5 selected" (stage 1), "Approve all 12 changes as NAME" (stage 2), and "Apply 12 changes now" (stage 4). The first two are both "Approve".

## 2. Words

- **Stage 1** is **mark**, not approve. Buttons: "Mark 5 as approved", "Mark as rejected", "Mark as held". Confirm text: "Marked approved. Nothing is written. You still need to sign the plan."
- **Stage 2** is **sign**: "Sign this plan as NAME" with the line beneath: "Signing does not make the changes. It says these decisions are yours. A second person may still need to sign, and someone must apply."
- **Stage 4** is **apply**: "Apply 12 changes to PayHOA now" (or the terminal command). The confirm dialog says what is about to change, in counts, and that apply checks the live system first and writes nothing if it moved.
- **Never** use "Approve" for stage 2. "Approved" remains a word for an item's mark and for a fully signed plan: "Signed by A and B, ready to apply."
- A plan's state is one of six sentences, always shown (the engine's status words stay in the JSON):
  - "Needs review: 3 of 12 marked."
  - "Marked, needs your signature."
  - "Waiting for a second signature (the treasurer or another director)."
  - "Signed, **not applied yet**. Nothing has been written."
  - "Applied: 12 changes made, 0 failed."
  - "Withdrawn", "Replaced by a newer plan", or "Failed: 2 changes were not made".

## 3. The progress strip (`PlanProgress`)

Above every plan, one line of five steps with the current one marked and the next action named. It reads from the plan, never from the viewer's guess.

```
 Review ──── Sign ──── Second signature ──── Apply ──── Done
   ✓           ✓            ● you are here      ○         ○
 Signed by A. Waiting for a second person (not A). Nothing has been written to PayHOA.
```

- Each step shows who did it and when (a name and a time) once done.
- A step the plan does not need is omitted (no second signature on a one-person kind).
- **Where apply happens** is stated on the Apply step: "A person applies this at a terminal: `jason approvals apply ID`" (with Copy), or "Apply from here" where the board has allowed console apply (section 5). A terminal-only kind says so and why ("mailing is applied only at the terminal").
- The strip never hides a refusal: a control that requires a particular signer shows its reason on the step it blocks.

## 4. "Nothing has been written" and "waiting to be applied"

- **A standing line** on the plan, in the same place until stage 4 finishes: "**Nothing has been written to PayHOA yet.**" It names how many changes are marked and what applying will do: "Applying will change 12 tags on 9 owner records. Counts only here; the list is below." After apply, the line becomes the result.
- **Waiting to be applied** is a state of its own in the Approvals list, the Today band, and the Work list: "Signed, waiting to be applied" with how long it has waited. A plan signed and left sits in front of the people who may apply it, so it is not forgotten, and the plan's age is judged against its kind's limit (a plan older than its limit is planned again before apply, and the strip says so).
- **A plan the board abandoned** is withdrawn on purpose (a reason, in words), never left to age.

## 5. Opt-in preferences for applying (a board's choice)

Some boards want a console button for apply; some want the terminal only; some want a pause before anything is written. These are **apply preferences**, adopted like a control: jason suggests, the board adopts at a meeting (recorded by the secretary), with an effective date and a history ([../controls.md](../controls.md), the control-adoption run). They never loosen a signature requirement, a control, or a terminal-only kind.

| Preference | Choices | Default | Notes |
|---|---|---|---|
| **Where apply happens** | terminal only; console button after every signature (the server also allows apply) | terminal only | the server's `--allow-apply` still gates the console button; the Mailroom send stays terminal-only whatever is chosen |
| **Who may apply** | any signer; any board member or the manager; not either signer | any board member or the manager | "not either signer" is a separation of duties: the person who signed does not also apply |
| **A pause before apply** | none; N minutes; until the next day | none | after the last signature the plan shows a countdown and a Withdraw button; apply is offered only after it |
| **A typed count over N changes** | off; N | off | above N changes, the apply dialog asks the person to type the count |
| **A reminder for a signed plan** | none; after N hours | after 24 hours | surfaces in Today and Work and in the Approvals list; sends nothing |
| **Apply after the pause, automatically** | never; for named kinds that move no money and send nothing | never | a board's explicit opt-in, per kind, with an effective date; refused for any kind with a cost, any kind that mails or emails, and any terminal-only kind; the plan must be fully signed, the live re-plan must match, and a person can withdraw during the pause. **Not built: the engine has no such flag, and none is offered.** |

Each preference is a control-like row: the provision or the decision it rests on, the board's reading, the decision that adopted it, the date it takes effect, and a history. Until the board adopts one, the defaults hold.

### 5.1 What is built (the first four rows and the reminder)

The five preferences are rows in the control catalog (`jason.controls.catalog.PREFERENCES`: `where-apply`, `who-may-apply`, `pause-before-apply`, `typed-count-over`, `reminder-hours`; family "Applying plans"), adopted through the same record and act log as any control ([../controls.md](../controls.md)). They are preferences and not safeguards, so they sit beside the catalog and not in it: `effective_approver` never reads them, and they cannot change who signs or how many. `jason.controls.apply_prefs` holds the enforcement.

- **Adopting one.** `jason controls --offer TYPE [--scope all|kind:KEY|family:SYSTEM] --by NAME` records it as a suggestion; `--propose KEY --by NAME` puts it before the board; the secretary records the board's decision with `--adopt KEY --meeting DATE --decision ID --effective DATE --param NAME=VALUE --yes`. The values: `where` (`console` or `terminal`), `who` (`board_or_manager`, `any_signer`, `not_signer`), `minutes` and `until_next_day`, `over` (a typed count above this many changes; 0 asks on every plan), `hours` or `off` (no reminder). A preference binds from its effective date. Where several cover a kind (one for all, one for a family, one for the kind), the stricter governs in each respect: a terminal over a console, the longer pause, the lower number for a typed count, the sooner reminder; two `who` choices that leave no one refuse every apply.
- **The floors, which no choice passes.** The console never applies a kind that is terminal-only, that has a cost, or that sends something to people (`ActionKind.sends`). A console choice scoped to such a kind is refused when it is adopted, with the reason; a console choice for all, or for a family, is floored back to a terminal for such a kind when it is read, and the plan says why. A hand-edited facts file cannot pass the floors either (the same check runs when it is loaded and when it is read). The Mailroom send stays at the terminal whatever is chosen. The kind that completes owner-information requests declares that it sends (PayHOA emails the board's completion comment to the owner), so it is applied at the terminal until its registry row says otherwise.
- **Where each is enforced.**
  - *Where apply happens:* the web apply route refuses (403, in words, with the terminal command) unless the board adopted a console button for the kind; the server's `--allow-apply` is still required besides. The plan view shows "Apply is at a terminal" instead of a button.
  - *Who may apply:* `engine.apply` refuses a person the choice excludes ("only a person who signed this plan", or "does not let a person who signed this plan also apply it"), and, once a `who` preference is adopted, a name that holds no office on the roster. The default (any board member or the manager) is kept by the console's sign-in and by the person at the terminal, and is not checked against the roster where no preference is adopted.
  - *A pause:* from the last signature, `engine.problems` (so a check, a dry run, and an apply) refuses until it ends. The plan shows a countdown and a Withdraw button, no Apply button, and no terminal command until it is over. "Until the next day" ends at the next midnight on the machine's clock.
  - *A typed count:* above N approved changes the apply dialog asks the person to type the number; the terminal takes `--count N` (`jason approvals apply`, `jason mailroom --approval`); a missing or wrong number is refused by the engine before any live read.
  - *A reminder:* a plan signed and waiting for the hours set (24 by default) is marked "reminder due" in the Approvals list, the Today band, and the attention digest. It sends nothing.
- **Directors and officers read the same.** The effective preferences and the countdown are the same for every viewer; they name offices and counts, never a private fact.

## 6. What a reviewer sees about the changes

For plans like the owner notice delivery preferences (the owner-information tags), the plan says in words what each change is: "Set Owner A's notice delivery preference to email" with the before and after, the answer it comes from, and the reason it is in the plan. The list is the plan's items; the heading gives counts. A reviewer can open an item to see its evidence and the exceptions and holds recorded under the same finding ([../held-items.md](../held-items.md)). A change jason cannot make from a form answer is held, not hidden.

## 7. Undo, withdraw, and what cannot be undone

- **Before apply:** any mark can be changed and the plan can be withdrawn with a reason; a re-plan replaces the plan when the live system moved.
- **After apply:** the result lists what was made. Whether a change can be reversed is stated per kind on the plan ("a tag can be changed back by a new plan"; "a mailed letter cannot be recalled"). jason never reverses a change by itself.
- **A mistaken signature** is not edited. The plan is withdrawn and planned again; the withdrawal and the reason stay in the log.

## 8. Build order

1. **Wording and the strip** (UI only): the stage words in section 2, `PlanProgress`, the standing "nothing written" line, the six state sentences in the Approvals list and Today's band.
2. **Waiting to be applied** in the Today band, the Work list, and the Approvals list. Built for the Today office bands (`signedWaiting`), the Approvals list ("Signed, waiting to be applied · 3 days"; a plan older than its kind's limit reads "Signed 5 days ago; it will be planned again before it is applied"), and the governance digest's `approvals` section; the server's `engine.waiting_to_apply` decides which plans wait (fully signed, not applied, withdrawn, or superseded; the clock runs from the last signature). The Work list is not built.
3. **The preferences** (section 5) as adopted rows: where apply happens, who may apply, a pause, a typed count, a reminder. **Built** (section 5.1), with the floors. **Auto-apply is not built**, not even as a flag; it stays last, and only if the board asks for it.

## 9. Acceptance criteria

1. No plan screen uses "Approve" for signing. Stage 1 says "Mark", stage 2 says "Sign", stage 4 says "Apply".
2. Every open plan shows the strip with the current stage, the next action, and who does it; a plan applied shows "Done" with the result.
3. Until stage 4 finishes, the plan says "Nothing has been written" and how many changes applying will make, in counts.
4. A signed, unapplied plan is a named state in the Approvals list and in Today, with its waiting time.
5. A terminal-only kind says it is applied at the terminal and never shows an Apply button.
6. A preference never lowers a signature count, removes a control, or enables apply for a kind that is terminal-only, costs money, or sends mail. (Guarded by `apply_prefs.console_floor` and `tests/test_apply_preferences.py`.)
7. Directors and officers read the same plan the same way; the strip names offices, not private facts.

## 10. Decisions for the board

- The words (section 2): "Mark", "Sign", "Apply" (recommended), or other.
- Whether console apply is offered at all (recommended: only if the board adopts it; the terminal stays the default).
- Whether a signer may also apply (recommended: yes by default; the board may adopt separation of duties).
- Whether an automatic apply is ever wanted (recommended: no; offered only on request, for kinds that move no money and send nothing).
- Whether the kind that completes owner-information requests may ever be applied from the console. It declares that it sends (the completion comment is emailed to the owner), so the floors close it; opening it is a change to its registry row and the board's decision, not a preference.
- Whether the default "any board member or the manager" should be checked against the roster everywhere (recommended: only where the board adopts a `who` preference, so a terminal apply by a name not on the roster is not refused unasked).
