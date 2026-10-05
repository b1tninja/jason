# The profile's rows for paint, facts, and unit records

What this profile supplies to the methods in [docs/unit-records-backend.md](../../docs/unit-records-backend.md). None of it is built.
Each row is a profile fact: it goes in `mystique/` as a class attribute or module constant, never in a task.

## `paint_schedules()`

Built: `mystique/paint.py` (the exterior palette, six rows, three schemes). The painting dates come from the reserve study's painting
components ([paint-findings.md](paint-findings.md)): seven-year life, due 2027 to 2030 by building group.

## `unit_coverage()`

- **Declaration list** (Declaration 8.1(a)(i)(B)): interior walls and doors; ceiling, floor, and wall surface materials; utility
  fixtures; cabinets; built-in appliances; heating and air-conditioning; water heaters; each "as originally installed by Declarant
  and any equivalent replacements."
- **Policy list** (endorsement N CP 12301): fixtures (built-in cabinets, built-in appliances, electrical and plumbing fixtures) and
  appliances, "originally installed or replaced in accordance with your condominium's original plans and specifications."
- **Differs on:** wall and ceiling finishes, flooring, doors, heating and cooling, and water heaters (declaration lists, policy does
  not name them). Open question key: `unit-finishes-and-equipment` (with the agent).
- Citations: `decl#8.1(a)(i)(B)`, `decl#8.4`; the policy's endorsement as a library address once its declarations are on file.

## `loss_ladder()`

| Step | Question | Citations |
|---|---|---|
| 1 | What is the item? | `decl#8.1(a)(i)(B)`, `decl#8.4` |
| 2 | Where did the cause originate? | `decl#7.3`, `decl#7.11`, `decl#7.9` |
| 3 | Is it an insured casualty above the deductible? | `decl#Article 11` (11.1), `decl#8.1(a)(iv)`, `decl#8.1(a)(vi)`, the policy's valuation |
| 4 | Whose negligence, and of what degree? | `decl#7.3`, `decl#7.9`, `decl#7.11` ("gross negligence") |
| 5 | Who pays the deductible? | `decl#8.1(a)(vii)` |

## `open_questions()`

1. `unit-finishes-and-equipment`: are unit finishes, heating and cooling, and water heaters covered under the master policy? With the
   agent; the draft is `data/drafts/insurance-agent-unit-coverage.md`, not sent.
2. `builder-options`: does a developer option installed at closing count as original? With the agent.
3. `consequential-damage-7-11`: is 7.11 lawful and fair as applied to a roof leak? With counsel; sent by the board on March 19, 2026.
4. `deductible-guidelines`: the board has not adopted the guidelines 8.1(a)(vii) calls for; the April 30, 2026 write-up is a draft
   to adopt with three additions ([unit-records-findings.md](unit-records-findings.md)).

## `deductible_policy()`

`None` until the board adopts it. The screens show the missing guideline as a held note.

## `original_specs()`

Empty. The developer's finish and appliance schedules by plan are not in the library. First sources: the developer's turnover
papers, the public report for each plan, and the plan set. Plans are those the assessor characteristics already match
(`FLOOR_PLANS`).

## `facts()` to start

The questions owners already ask: touch-up paint (documented, from the Owner's Manual), interior paint colors (assumed: owner's
discretion under Declaration 7.5, no color on file), original flooring and appliances by plan (assumed), who repairs interior water
damage (7.11, recited, with its open question), and what the association's policy covers (8.1(a)(i)(B) and the policy's endorsement,
both recited, with their difference as an open question).
