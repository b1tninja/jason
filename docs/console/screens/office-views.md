# Office views

The landing page of each office, and a lens that lets any board member read another office's · `#/digest` with `?as=OFFICE` · phase 2 · no CLI (the same bands are `jason attention` and `jason workflow --list`)

## In the console

Today (`#/digest`, [today.md](today.md)) is one landing page for everyone. The security page proposes screens by role ([../security-and-privacy.md](../security-and-privacy.md), "Proposed"): the secretary Overview, Governance, and Records; the treasurer Overview and Money; a director all but connections. That table narrows what a person may open. This page replaces the narrowing with a lens.

**The board's principle (2026-10-11).** Directors and officers have the same access to information. Every board member can open every office's landing page; the pages are tailored reports, not permissions. What differs is the **actions** only an officer can take. This spec is the whole screen, as proposed: a landing page per office, a switch to read another's, and the rule for which controls are live.

## Purpose and personas

A landing page answers "what is mine to do, and what is coming for my office?" The president, the vice president, the secretary, the treasurer, a director, and the manager each need a different first screen. A board member also needs to read the others': the secretary reading what the treasurer is waiting on, a director reading what the president will bring to the next meeting, the president reading the secretary's postings and minutes.

- **President, vice president, secretary, treasurer, director:** open their own landing page by default and any other office's by the lens.
- **Manager:** opens the manager's landing page by default. Every director and officer may read it too (decided 2026-10-11): directors have visibility into the manager's page and operations.
- **Administrator (no office):** the owner of the instance; reads the status and setup pages, not an office's page, unless they also hold the office. The dev-only "view as someone" (`POST /auth/act-as`) stays a separate tool for building and checking views, and is not this lens.
- **Reviewer, counsel, a roster person with no office:** no office view.
- **Owner:** never.

## Data

| Part | Source | Loader |
|---|---|---|
| An office's bands | The Today bands cut to the office, from what exists: the letters requested of an approver the office stands for (`Officer.approves`, "the <office>", and "the board" for the two offices that record its vote), by kind and count; the board items the board gave the office (or the board) to act on, matched on the item's owner text (matched, never shown); for the secretary, the board's open votes to record; the schedule's occurrences for the duties the profile's assignments give the office, the board, or name it as backup (overdue and due soon, then the next 45 days); a count of the dock's open tasks the office owns; and the runs whose current step's `role` is the office (`jason.workflows`) | `GET /api/office-view?office=ROLE` (built, `jason.web.extra.office_view`; `ROLE` is an `OfficerRole` word, never a name; empty reads the viewer's own offices as a union) |
| Which offices the viewer holds | `GET /api/session` (`roleClass`, offices); `office-view` answers `mine[]` as words | built |
| The offices a viewer may read | Every `OfficerRole` the profile names, to any signed-in board member or the manager | `office-view` answers `offices[]` (`office`, `vacant`, `holders` as a count) |

**Not composed, and said so in the answer (`notComposed`).** The engine's plans (`jason.approvals`) wait on a named person or a second signature, and no office is attached to a plan unless a control names the offices that may sign; they stay in Approvals. The governance digest's requests, intake, notices, living documents, conflicts, and people's-tasks lines carry no office (only the schedule's duties carry a role); they stay on the Board digest. Next questions (onboarding) are the board's, not an office's. A band whose store cannot be read is named in `bandErrors` and in `notComposed`, and the others stand. The answer adds a fourth band, `comingUp` (the next weeks of the schedule), to the three above, as the layout's "Coming up" row.
| The actions an office has | A step's `role` (the definition), an approval's signers (`Officer.approves`), a decision's recorder (the secretary) | the same rows as Work and Approvals |

**Reading another office's page never changes who the viewer is.** The data levels are the viewer's own (`SEE_RULES`: every office opens P2 and, in the private view, P3), a write goes on the record under the viewer's own name, and the page says "Reading as the treasurer" so no one mistakes it for that person's session.

## Layout

```
+------------------------------------------------------------------------------------------+
| Board digest                                          Reading as: [ My offices v ]       |
| (Secretary)                                                       President  Vice president |
| 1 on a legal clock · 3 overdue · 4 due soon · 6 waiting on a person                       |
|                                                                   Secretary  Treasurer     |
|                                                                   Director   Manager       |
+------------------------------------------------------------------------------------------+
| READING AS THE TREASURER  ·  you are the secretary; actions only the treasurer can take   |
| are shown but not live  [Back to my offices]                                              |
+------------------------------------------------------------------------------------------+
| WAITING ON THE TREASURER                                                                  |
|  Bills with no document: 12             Bill attach, Oct   Step 4: approve   [Open]       |
|  Monthly review, Sep                    Waiting: the treasurer's review      [Open]       |
+------------------------------------------------------------------------------------------+
| COMING UP FOR THE TREASURER                                                               |
|  Budget packet: collect figures   due Nov 3 [DOCUMENTS]     Reserve transfer notice ...   |
+------------------------------------------------------------------------------------------+
| Second signature on money plans  [Only the treasurer can sign this]   (disabled, with why)|
+------------------------------------------------------------------------------------------+
```

- **The lens** (`OfficeLens`) is a select in the header: "My offices" (the default; a person who holds two offices sees the union) and each office the profile names. It stays on a page across reloads (the URL's `?as=secretary`), and the page names it in a banner whenever it is not the viewer's own.
- **Bands** are cut to the office: `Waiting on you` (or "Waiting on the treasurer"), `Needs attention`, `Coming up`, `Your work` (retitled "Work for the treasurer"). Each band's heading names the office when the lens is not the viewer's. Built as `OfficeToday` (`ui/src/components/OfficeLens.tsx`) above the Board digest on `#/digest`; `Next questions` is not composed per office (above).
- **A control the viewer's offices do not hold is shown, disabled, with the reason** ("Only the treasurer can sign this. You are the secretary."). It is never hidden, so a board member sees what the office does. The server refuses the act whatever the page shows (the check is on the server, as every write).
- **No impersonation:** the page never says "you", "your" for the other office, never fills the other office's name into a record, and never shows a "Switch to" that signs in as them.

## Components

Built: `Card`, `DataTable`, `Pill`, `Stat`, `Confirm`, `Command`, `DueDate`, `Caveats`, `ScreenHeader`, and, in `OfficeLens.tsx`, `OfficeLens` (the select), `OfficeBanner`, `OfficeBand` and `OfficeBands` (a band with the office named in its heading), `OfficeToday` (the loader's page), `DisabledForOffice` (a control with the reason it is not live; no screen uses it yet, because no officer-only control is on Today), and `useOfficeLens` (the URL's `?as=`). The `Your work` band of [today.md](today.md) is the same band with the run rows; the Work screen is not built, so a run row has no link yet. Styles: `ui/src/styles/office-views.css`.

## Actions

- **Switch the lens:** a read; nothing is written; it is remembered in the URL, not on the server.
- **Open a row** goes to the owning screen (Approvals, Work, Decisions, Notices), where the viewer's own offices decide which controls are live.
- **Every act on the page belongs to the viewer's own offices.** An act that needs an office the viewer does not hold is `DisabledForOffice`. What counts as an officer's alone comes from the association's bylaws (a profile's reading of its Article on officers; the example profile's is `mystique/docs/officer-duties.md`): presiding at a meeting (the president, or the vice president while the president is absent or disabled); recording the board's decisions, the minutes, and that a notice was given (the secretary); and answering for the books, deposits, and disbursements (the treasurer). Everything else is the board's act and open to any director, including a second signature on a payment (the bylaws let any two directors, or an officer and a director, sign). Also live only for their holder: the manager's one-person kinds, and a step of a run whose `role` the viewer does not hold.

## States

- **A profile that names no one for an office** (a vacancy): the office is in the lens with "Vacant", and its bands show what waits with no one to do it. This is a finding for the board, not an error.
- **One person holds two offices:** "My offices" is the union; the lens can still read each separately.
- **No officers named by the profile:** the lens lists no office and the page is Today as it is.
- **The loader fails for one band:** that band says so with its reason; the others stand.

## Privacy

- The lens changes no data level. Directors and officers have the same access to information; a board member reading the treasurer's page reads what the treasurer's page reads, at the viewer's own level, and the private view (P3) opens only in the viewer's own logged window.
- The page lists counts and kinds on the bands, and the owning screens decide what a name or a unit shows.
- A roster person with no office, a reviewer, counsel, and an owner are refused: 403 with the sentence `access.may_see` gives.
- `office-view` is not an owner source (`OWNER_SOURCES` does not list it).

## Acceptance criteria

1. `GET /api/office-view?office=treasurer` signed out is a 401; for a viewer who holds no board office it is a 403; for any board member it is 200.
2. The response names the office asked for, never the viewer's, and carries no `by`, no name from that office's holder, and no session of theirs.
3. Reading as another office changes no data level: a test shows the same viewer gets the same P2 and private-view results with and without the lens.
4. A control for an act the viewer's offices do not hold renders disabled with the reason, and the server refuses the same act with a 403 naming the office that holds it.
5. The banner "Reading as the treasurer" shows whenever the lens is not the viewer's own and offers "Back to my offices".
6. A person who holds two offices sees the union by default, and the lens still reads each alone.
7. A vacant office is in the lens as "Vacant" and its bands show what waits.
8. The page uses the made-up office words only (`OfficerRole`); no person's name appears in a URL.

## Decisions for the user

**Settled 2026-10-11:**
1. A board member may read the manager's landing page and operations.
2. The lens lives in the URL and the browser, not on the server.
3. The secretary and the treasurer may read each other's pages, as every board member reads every office's.
4. Nothing narrows the "Screens" column: every board member opens every screen their data levels allow, and the security page keeps only "Can sign".

**Still to confirm:**
5. **Which controls are officer-only** (answered from the bylaws, 2026-10-11, pending the board's confirmation of the reading in the profile's officer-duties page; not signing, which the bylaws open to any two directors): the definitions' `role` per step and each approvals kind's signers decide, and the board confirms the list once.
