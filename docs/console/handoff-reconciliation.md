# The console handoff of 2026-10-04, reconciled with what is built

The design agent's package (`design_handoff_community_console`: HANDOFF.md, CLAUDE-CODE-BRIEF.md, UPSTREAM-SPEC.md, REDESIGN-SPEC.md, 17 screen templates, the glyph, stamp, and seal sets) was checked line by line against the repo and the domain rules. This page is for both readers:
- **the design agent:** what to change, and why;
- **the build:** what is already built, what is new, and what in the built console must be fixed regardless.

It extends [redesign-review.md](redesign-review.md), which the design agent had not seen when it wrote the package.

## In one paragraph

Much of the brief is built:
- the clerk's-desk tokens;
- sign-in, the admin view (`--dev`), and writes off while acting;
- Approvals grouped by whose turn, with the board's own group;
- the dock, and screen states (loading, error with Retry, empty, missing);
- the meeting room's motion, second, and roll call;
- records requests with their 5210 clock;
- the owner view's screen filter.

New are:
- the Glyph, Stamp, and Seal components and the routing tags;
- the Matters screen;
- role landing and the role strip;
- the Documents screen's promote flow;
- an owner's account page.

Seven kinds of conflict recur: the design treats as fixed what is the law's, the governing documents', the board's, or the roster's to say; or it gives the browser a power only a person at the terminal has.

## Corrections for the design agent

### Architecture

1. **The routes are jason-web's, not jason-mcp's.** jason-mcp is read-only stdio. `sample-api.js` is replaced by the routes jason-web already serves: `/api/session`, `/auth/act-as`, `/api/approvals`, `/api/write/approvals/<key>`, `/api/dock`, `/api/write/dock/<id>`, `/api/drive-files`, and the rest in [web-ui.md](../web-ui.md).
2. **Adopt the server's shapes; don't ask it for the stores'.**
   - **Session:** `signedIn{name, role, email, admin}`, `acting{name, role}`, `actAsPeople`, `actAsRoles`, `private{…}`. The people who may approve come from `/api/approvals`.
   - **Letters:** approval is a transition with `by` (`save`, `request`, `withdraw`, `send_back`, `approve`, `record_sent`), never a stage the client sets.
   - **Dock:** deadlines `{date, days, authority, standing}`, tasks `{text, doneAt, history}`.
3. **No `/api/screens/:id`.** Each loader is the screen's read. It gains `asOf`. "Empty" (read, nothing waiting) and "missing" (`found:false`, with the command that fills the store) stay two different states.
4. **No caching of Approvals or evidence.** A plan is read again before it is applied, and the CLI writes the same stores.
5. **Telemetry is the existing audit logs:**
   - the approvals chain;
   - the letter trail;
   - `sign-ins.jsonl`;
   - `access/served.jsonl`;
   - `access/private.jsonl`.

   They record structured acts, never a Confirm's prose, which can carry P2 or executive-session words.

### Roles

6. **The roles are the roster's offices,** not four classes:
   - **Admin:** holds no office, approves nothing, and lands on Status and setup (sign-in, sources, sync health), seeing what waits on anyone, read-only. The admin view exists only under `--dev` and refuses writes. Viewing as an office applies that office's `approves`.
   - **Manager:** sees Decisions (they prepare briefs and agendas) but never records the board's vote.
   - **Screen access** is checked on the server, never by filtering the nav.
7. **The role strip and the dock's counts come from the server** (`moves` in `/api/session`; role-aware dock counts). They count what this person may act on.

### Approvals and sending

8. **"For the board" waits on a meeting:** "Waiting on the board's meeting of DATE", or "Not on an agenda yet". Recorded only by the president or the secretary, with the meeting's date.
9. **There is no Send button that mails.** "Approved, to send" shows the terminal command (`jason mailroom --send --yes`), run by a person, then records `sentRef`. The stamp `sent` follows the record. Add `sent` to stamps.js's header.
10. **ApproveBar is never blank:** "Your move" for a person who may act, read-only with whom it waits on for everyone else.

### Matters, meetings, decisions

11. **Matters are the board items with a planning layer,** not a new store. A `matters` loader merges the board items, the meeting plan, and the calendar clocks. The tier and `latest` are computed on each read, and the tier is labeled jason's suggestion: the board sets the agenda. "Report only" is a new plan kind.
12. **Fixed numbers are the profile's or the board's:**
    - **The meeting's length:** `board_meeting_policy().duration_minutes`, not 90.
    - **The open-forum limit:** the board establishes it (CIV 4925(b)). Until a policy is adopted, the screen says "no limit on record; the board sets it", never "3 minutes".
    - **The task due date:** "Ask the manager" is due from the notice date (which honors a longer period in the governing documents) less a lead time the board sets, routed by the duty's owner, not by keyword.
13. **The notice checklist, corrected** (each line recites the statute from disk):
    - 4920(a): four days, or longer where the governing documents require it (4920(b)(3)); two days for a meeting held solely in executive session.
    - 4930: the agenda lists every item. It is not the forum limit (4925(b)), which is not a notice line.
    - 4926: the join instructions, help contact, and telephone option apply only to a meeting held entirely by teleconference. A hybrid meeting is 4090(b).
    - 4935: no notice line. 4935(e) is the minutes' general note.
    - Readiness ("action items ready") is jason's check, kept apart from the statutory lines.
14. **Quorum and recusal come from the bylaws or counsel, labeled.**
    - The quorum rule is the bylaws' provision, quoted, or counsel's reading, labeled.
    - Civil Code 5350(b) lists the matters an interested director "shall not vote" on; a contract is 5350(a), through Corporations Code 7233–7234.
    - Recusal is a director's disclosure the secretary records, never applied automatically.
    - With no rule on file, the screen says "not on file; ask counsel", and never silently counts the director.
15. **Table, continue, and refer are motions the board votes on** by roll call, and their stamp shows the motion's word. Only "withdrawn" (by the mover, before the vote) is a logged act without a vote.
16. **Executive session:**
    - The badge names its 4935 subject (`ExecutiveSubject`). An item that matches none cannot be executive.
    - A hearing is executive on the member's request (4935(b)).
    - The open log and minutes get only the subject's general words, never the item's title.
17. **Speakers.**
    - An unmatched caller is "unidentified caller" with the last four digits of the number (the caller may be a director and change the quorum), never "A member".
    - Open-forum speakers are never named in the minutes.
18. **Retention follows the `meeting-records` policy** and the association's adopted rule. The 30 days is the 4950(a) clock for the minutes, not retention.
19. **Polls are member input that the host runs.** jason records them, and never launches one.

### Documents, records, owners

20. **Promote is two approvals, not one Drive path:**
    - **The words:** the letter goes saved → requested → approved, by the officer whose `Officer.approves` names the kind.
    - **The write:** a `google.doc` plan into the profile's Drive folder, as a Google Doc (not a .docx), applied by a person.
    - Until that kind exists, the screen shows "Run in the terminal".
21. **Folder states:**
    - "Not found", with the *not confirmed* seal, never a red "missing": a gap is a place to look.
    - "Restricted" (P3: counted outside the private view, listed inside, never in the owner view). "Withheld" is only what a person withheld on a request, with its 5215 basis.
    - The reserve study is due under 5550's own conditions and its annual review, dated from the study's inspection.
    - The ledger view belongs to the private view.
22. **My account is a future screen.** Owners have no sign-in. PayHOA is the owners' portal until the board decides otherwise. When it comes:
    - it shows PayHOA's balance, and flags a mismatch rather than recomputing one;
    - it offers "Ask to meet about a payment plan" to an owner sent a 5660 notice, never on a balance threshold;
    - it recites 5665, with the 45-day clock only when its 15-day condition holds;
    - it quotes 5650–5660, never paraphrases them.
23. **The request picker:**
    - Each kind links to its PayHOA form or the official address.
    - Clocks come only from `ResponseRule` rows: statute rows cited, policy rows labeled "proposed" until adopted, and no clock otherwise.
    - It carries no *filed* seal.
    - Payment plans and appeals go to the board.
    - A public page cannot write to the console, which listens only on this machine.
24. **"Keep my name out"** becomes "Ask to keep my name out", on complaints only. It shows when the board's complaints policy is adopted, with "the board's complaints policy says when a name is shared".
25. **The owner view** shows open-session minutes, the annual disclosures, and the records request form with what was produced (once owners have accounts). It shows no delinquency, no liens, no discipline, and no other owner's facts. It never shows the library, and never the board's digest.

### The visual system

26. **Glyph, Stamp, Seal, and routing tags** are ported as components with props. glyph-layer.js is not shipped.
    - Seals mark what jason did; stamps mark what a person decided. They never share a word.
    - Drop `draft` and `confidential` as stamps. A draft is the *drafted* seal; confidential is the P3 chip, which is a level, not a decision.
    - A county filing is the *read* seal with its instrument number, never `recorded`.
    - glyph-layer.js maps `filed`, a seal word, to the stamp glyph: fix the mapping.
    - Routing tags resolve from the roster, not keywords.
27. **Tokens.** `--serif` carries `/* @kind font */`. The radius is one value, 2px (`--r`). INTEGRATION.md's 8px is superseded.
28. **Fixtures** are the loaders' shapes, with made-up data in `tests/fixtures`, never exported from a browser's storage:
    - "policies (6)" is the insurance policies (5) and is renamed;
    - the record kinds come from `records_inventory` (15).

## The board's open decisions (§5), corrected

| The brief assumed | Where it belongs |
|---|---|
| Quorum 3 of 5, simple majority | `Community.board()` (the bylaws' rule, with its source); the vote basis and the interested-director rule are added to it, with sources |
| Open forum 3 minutes | The board's `meeting-schedule` policy (4925(b)) |
| Transcript retention 30 days | The `meeting-records` policy and the association's adopted rule |
| Owner roster from PayHOA or Drive | PayHOA, jason's source of truth for owners |
| Translations reviewed by the vice president | A roster or profile fact |
| The manager or the secretary sends | The roster (`Officer.approves`) and the `approvals` configuration |

## Fixes in the built console, independent of the design

Found during this reconciliation. Each gets a lesson and a guard (AGENTS.md):

| Fix | What is wrong |
|---|---|
| **The executive session reaches the open minutes** (fixed: lesson `executive-session-in-open-log`) | Log entries made during executive session go into the room's open log, which the draft minutes copy. `decide` records them as "open session", and the general note falls back to the item's title. Now a separate P3 record; the open log carries the 4935 subject's general words only. The minutes draft gives the model each agenda executive item by its 4935 subject only (lesson `agenda-executive-words-to-minutes-model`). |
| **The owner view shows delinquency** (fixed: lesson `owner-view-showed-delinquency`) | The owner Overview renders the board's digest (owners in default, liens), and the owner nav includes Records (CIV 5200), which lists the liens the association placed. Now the server answers `view=owner` reads from the owner loaders alone (`jason.web.extra.owner_view`), and the Overview is `/api/owner-digest`. |
| **Recusal and quorum are hardcoded** (fixed: lesson `recusal-quorum-hardcoded`) | "Recused directors count toward quorum" is cited as if it were statute (`meeting_room.py`, `RollCall`). The vote basis is fixed, and with no rule on file the director is counted silently. The Decisions caveat says "marked absent", and `DecisionCard` does not pass `recused`. Now `BoardRule` carries the vote basis and the recusal rule with their sources; the room recites them (`board_rules`) or says "not on file; ask counsel", works the tally both ways, and holds a vote the readings decide differently. `Decision.recused` records the disclosure. |
| **The notice date ignores the documents** (fixed: lesson `notice-date-ignored-documents`) | `notice_date` always uses four days. The hybrid meeting is cited as 4926. Now `notice_period` takes the governing documents' longer period (`Community.board_notice_period()`, 4920(b)(3)) with its source, and the checklist gives a hybrid meeting 4090(b)'s lines and 4926's only to a meeting held entirely by teleconference. |
| **The open-forum limit is 3 minutes in code** (fixed: lesson `open-forum-default-limit`) | `meeting_room.py` and `AgendaWizard`. Now `Community.open_forum_limit()` or a limit a person enters; with neither, "No limit on record; the board sets it (CIV 4925(b))". |
| **General code imports the profile** | `board_digest` (`mcp/county.py`) imports `mystique` directly instead of `community()` |
| **The audit log masks emails only** | Phones and mailing addresses are masked only on the way out, not when written |
| **Dock counts and Ask routing** (fixed: lesson `dock-counts-everyones`) | Counts are everyone's, not the person's. A routed question becomes a task with no owner. Now the counts are the signed-in person's (deadlines by the duty's owner in `Community.assignments`, tasks by owner, letters by `Officer.approves`), labeled everyone's with nobody signed in; a routed question goes to the office that owns the duty the asker names, else stays unassigned, with no due date until the board sets a lead time |

## The build, in order

1. **The fixes above,** first the executive session and the owner view.
2. **Glyph, Stamp, Seal, routing tags** (components, previews, design sync).
3. **Roles from the roster:**
   - `moves` and `offices` in `/api/session`;
   - landing by role;
   - the role strip;
   - server-side screen access;
   - the admin's Status screen.
4. **Matters:** the `matters` loader and screen; the plan's `when` and "report only"; the warning on moving a statutory item.
5. **The meeting room's beats,** the separate executive log, and the motions' words.
6. **Approvals:** "waiting on the meeting of DATE"; `asOf` on every loader; print CSS without the shell.
7. **Documents:** folder states; promote through the letters' approval and a `google.doc` plan kind.
8. **Later, each by a board decision first:**
   - My account and owner sign-in;
   - the public request picker (with PayHOA forms);
   - "Ask to keep my name out".
