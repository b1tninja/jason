# The console handoff's fourth cut, answered

The design agent's fourth cut (2026-10-04, evening) answers [handoff-reconciliation.md](handoff-reconciliation.md) and [handoff-reconciliation-3.md](handoff-reconciliation-3.md) in its `RECONCILIATION-RESPONSE.md`. Each of the 28 corrections is now applied in the templates or adopted for the build, and the third cut's pieces are corrected. This page answers what it holds for discussion, notes what is new, and lists what is the build's.

## Settled

- **Real details.** The package is scrubbed to the sample association. Either way is fine: the design project is private and may use the association's real details where they help. What comes back into the repo stays general ([handoff-reconciliation-3.md](handoff-reconciliation-3.md#the-package-itself)).
- **Tokens.** `--stamp-tilt` already carries `/* @kind other */`. `--dv-frame`'s open-grid value now does too (commit ffe6ce2). Both reach the project at the next design sync.
- **Phone widths.** `.fields` now gives its tracks `minmax(0, 1fr)` and its inputs `min-width: 0` (commit cb9d361), so `BoardFields` fits a 360px column. `console-local.css`'s stopgap can go after the sync.

## The three held items

1. **The Community tweak and `community.js`.** Keep it as a design-time preview of two themes, labelled as such. It is not a product setting: one installation serves one profile, fixed when jason-web starts (`JASON_PROFILE`). The record's shape is now built as `GET /api/community`: each fact as `{value, source, onFile, note}`, a missing fact "not on file", a rule with no source "ask counsel" ([web-ui.md](../web-ui.md)). Read `community.js`'s fields against it.
2. **Setup as a faithful view.** The read and the write are built:
   - `GET /api/onboarding-session` (`?limit=`, `?group=`, `?stage=`, `?kinds=`): `status_dict` (the five gates, progress, groups, stage), `items` (each with its computed status, what was checked, its `ask`, and `connect` for a credential item), `next` (the ranked questions, fact and map by default), `answered` (who and when, never the value), `otherOpen`, `apply`, `asOf`;
   - `POST /api/write/intake/<id>` with `{answer, by}` or `{confirm: true, by}`: the answer queues; applying stays `jason onboard --apply`.

   The template's `GET /api/onboarding` and `POST /api/intake` are these two routes. Connecting integrations in the console (Google Workspace's OAuth web application, Keeper, PayHOA, Zoom) is still to be built and is an administrator's flow ([onboarding.md](../onboarding.md#connecting-integrations-todo)); until then a connect item shows its terminal command.
3. **Table, continue, refer.** Agreed: each is a motion on the floor (mover, second, roll call), its stamp the motion's word; withdraw stays a logged act. Rewiring the room's dispose actions is the build's (below), not the template's.

## New in this cut

- **Status** (`ConsoleStatus`), the administrator's landing. `GET /api/status` is now built (below, item 2): each source's last read and standing (current, stale, failed, not signed in) from the stores' own `syncedAt` and the job queue, the fix as a `Command`, the sign-ins (`sign-ins.jsonl`), the five gates (from `/api/onboarding-session`), and recent failures. Administrator only.
- **The members' copy of the packet.** Agreed as designed: it drops draft motions, option briefs, and privileged files, and goes to the secretary through Approvals before posting. A member's copy is reviewed, never filtered silently.
- **`docref.js`.** Fine as a stand-in; the loaders already return `DocRef`s (`refs_from_strings`), so it goes when the templates read the routes.
- **Light and dark.** Keep the seven scheme tokens together, as `scheme.css` does.

## The build's, from this cut

1. **Subsidiary motions in the meeting room:** table, continue, and refer as motions with a roll call; withdraw as a logged act.
2. **`GET /api/status`** for the administrator's landing. Done: `jason.web.extra.status` and `#/status`, where the administrator lands ([screens/status.md](screens/status.md)). No source declares a freshness threshold yet, so none says current or stale.
3. **The members' copy of the packet** through Approvals. Done: `jason board --packet --audience members [--by NAME]` ([board-agenda.md](../board-agenda.md#the-board-packet)); the approver is the specification's (`Community.document_approvers`).
4. **Setup's screen** read against the template's grouping, now that the routes exist. *Done* ([onboarding-ux.md](../onboarding-ux.md#setting-up-in-the-console-the-setup-tab)): the gates with what holds the current one, the checklist by group, each item's status, seals, and next step, standing questions, first-run empty states; the loader adds each ask's `standing` and `clock`. Where the build differs from `ConsoleSetup`:
   - **Groups and gates are the server's:** 15 groups, not the template's 28, and the gates START, INGEST, ESTABLISH, OPERATE, ADOPT, each over its own items, not over groups.
   - **Every item behind a gate holds it,** not only the high-stakes missing ones: high-stakes items are listed first and marked.
   - **No board questions to Matters:** no ask's answer goes to the board (`FactRecord` is the private facts, a profile change, or Keeper), and Matters is not built.
   - **The answer's value is never shown,** and there is no Withdraw: an answer shows who gave it and when; dismissing is an answer.
   - **The clock is the profile's words,** shown only where a `FactAsk` names one, never a date.

Still behind a board decision: owner sign-in, and with it My account, the public facts page, and the owner unit manual.
