# Handoff: held material, setup, the roster, and the notice

For a design pass on the components that pair with what was built on 2026-10-04:
- executive items held back outside the private view (the meeting page, the plan, board items, decisions);
- setup over onboarding (the gates, the questions, answers waiting to be applied, a second person's confirmation);
- People and offices, with terms and recorded changes of office;
- the board meeting notice by format, with statutes recited from disk;
- the meeting room as a bottom sheet on a phone;
- tab rows that scroll.

Each of these was built with whatever components were at hand, so the same idea is drawn three ways on three screens. This page names the components that would make each idea one thing. It gives their jobs, states, data shapes with made-up samples, and the rules they must keep. The components are proposed names; the build takes them from the design's results. Read [handoff-reconciliation.md](handoff-reconciliation.md) and [handoff-reconciliation-3.md](handoff-reconciliation-3.md) first: their corrections still stand.

## The idea in five sentences

Some things are on a screen only as a placeholder: an executive item outside the private view, a statute not on disk, an answer not yet applied, an office no one holds. Each placeholder says plainly what is missing, why, and the one step that would fill it, and never guesses what it hides. jason's acts are seals and a person's decisions are stamps; a placeholder is neither, it is a held line. Every change that matters takes two people or a terminal command a person runs, and the design shows whose step is next. Nothing here sends, applies, or decides on its own.

## The components

| Component | Pairs with | Job |
|---|---|---|
| `HeldRow` | the meeting page, the agenda plan, board items, Decisions | One drawing of an item held back outside the private view |
| `PrivateGate` | `PrivateSwitch`, `PrivateAsk`, `PrivateBand` | Where held material would be: why it is held, and opening the private view for a stated reason |
| `GateRail` | `StageSteps`, setup | The five onboarding gates with computed status, never clickable to "done" |
| `ChecklistItem` | setup, `Seal` | One onboarding item: its computed status, what jason checked, and its next step |
| `PendingAnswer` | `QuestionCard`, `SecondConfirm`, `Command` | An answer given and waiting: for a second person, then for a person to apply it |
| `PersonSteps` | `Command` | The ordered steps only a person takes (a terminal command, a send in PayHOA), with who takes each |
| `OfficeCard` | People, `RoutingTag` | One office: who holds it, what it approves, sign-in, its duties, or its vacancy with the provision |
| `TermRow` | People | One term with its election record and provision; ended only from a recorded end |
| `RecitalBlock` | `Recitation`, the notice | A statute recited from disk inside a document, or its visible miss |
| `FormatLines` | the notice, the agenda plan | What a meeting's format requires, and only that |
| `BottomSheet` | `HostPanel`, the dock drawers | The phone layout: a handle, a row that stays, a body that scrolls |
| `ScrollRow` | `Tabs` | A row that scrolls sideways and shows that it does |

### `HeldRow`

Today a held item is drawn three ways: `HeldBoardItemCard` on Board items, a disabled row on Plan a meeting, and a held line on Decisions. One component replaces them.

- **Shape** (as the loaders send it):

  ```json
  {"id": "executive-1", "held": true, "subject": "assessment_payment",
   "general": "a member's payment of assessments", "status": "on agenda",
   "priority": "high", "meeting": "2099-03-17", "due": "2099-03-10"}
  ```

  A list carries `executiveHeld: 2` and `executiveHeldNote`.
- **States:**
  - with a subject: "An executive-session matter: a member's payment of assessments";
  - with none: "An executive-session matter", and a blank the Secretary fills;
  - in a table row, in a kanban card, in a list.
- **Keeps:** where the item stands (status, priority, meeting, due).
- **Never shows:** a title, an ask, notes, evidence, an id, or a count that would identify one member.
- **Offers:** only the `PrivateGate`. No details, no edit form, no decision.
- **Does not look like an error or a lock icon on a person.** It is the law's general note (CIV 4935(e)), drawn calmly: the `executive` glyph, the subject in the statute's words, no red.

### `PrivateGate`

Where held material would be. It says what is held and why, and offers to open the private view.

- **Variants:**
  - inline, under a `HeldRow`;
  - a band over a held section;
  - a card for a whole held screen.
- **States:**
  - "Held: open the private view to see it" with the reason field;
  - "Your offices do not open this" (the server's reason, quoted);
  - "Sign in to open the private view";
  - open: the material shows, and the `PrivateBand` runs under the header.
- **Rules:**
  - The reason is a short phrase the person types, never a choice from jason's list.
  - Opening reloads the screen's read, which is logged.
  - The owner view never shows a `PrivateGate`.

### `GateRail` and `ChecklistItem`

Setup is a view over onboarding: five gates (START to ADOPT) and 108 items in 15 groups, each with a status jason computes.

- **`GateRail`**: the five gates in order, each with its state (passed, current, ahead) and its count ("12 of 18 present").
  - The `read` seal sits at its head with the date jason last read the checklist.
  - A gate is never clicked to pass it.
- **`ChecklistItem`**:
  - its title;
  - its computed status (present, partial, missing) as words and a glyph, never colour alone;
  - what jason checked ("the profile's board rule names its source"), as a `read` or `could-not-confirm` seal;
  - its next step: a question, a command, or "nothing to do".
- **A connect item** (a credential, a Keeper record) shows only its terminal command, never an input.
- **A standing question** is always open, because its item can change: a change of office, a term. It is labelled "standing" and sorts after the questions an item is missing.
- **Shape** (one item, made up):

  ```json
  {"key": "board-rule", "title": "The board's rules", "status": "partial",
   "checked": ["quorum: Bylaws 7.1 recited", "recusal: not on file"],
   "ask": {"id": "a1b2c3", "question": "Does an interested director count toward a quorum, and on what source?",
           "stakes": true, "state": "open"}}
  ```

### `PendingAnswer`

An answer to an onboarding question moves through three hands: the person who answers, a second person when the answer is high-stakes, and a person who applies it at the terminal.

- **States:**
  - answered by NAME on DATE, waiting for a second person (the `waiting-on` seal);
  - confirmed by NAME, waiting to be applied (the command);
  - applied (gone from the queue; the item's status moves);
  - refused: "That looks like a secret: keep it in Keeper" (the field clears; the value is never shown again).
- **Rules:**
  - The answerer cannot confirm their own answer. The button says "Confirm as NAME" and is absent for the answerer.
  - The value is never echoed back once sent.
  - No stamp: an answer waiting to be applied is not a decision.

### `PersonSteps`

Wherever jason prepares something a person finishes: the notice ("next, each a person's step"), applying answers, sending a letter, recording a change of office.

- An ordered list. Each step has:
  - who takes it (an office or "you");
  - the `Command` or the place (PayHOA, the minutes);
  - whether it is done, from a record, never from a click here.
- **States:** none done; some done (each with its record); all done.
- jason's own finished steps sit above as seals ("jason drafted the notice").

### `OfficeCard` and `TermRow`

People and offices is read-only.

- **`OfficeCard`**:
  - the office, as a `RoutingTag`;
  - each holder (one person may hold two offices, so the same name can appear on two cards), what they approve, and whether they can sign in;
  - its duties, each with its adoption ("proposed" until the board adopts it).
- **A vacant office:** "No one holds the office of treasurer." The vacancy provision is recited when the profile has one; otherwise "The provision is not on file." Its duties read "unassigned". Nothing routes to another office.
- **The administrators** are drawn apart: "Not an office; approves nothing."
- **`TermRow`**: the person, the seat (director, or the office), the start, the end, the election record (the minutes or the inspector's report), and the provision.
  - With no end recorded: "at the pleasure of the board" for an officer, or "no end date on record" for a director.
  - "Term ended; election due" only from a recorded end in the past.
- **A change of office:** a `PersonSteps` list, with no edit control.
  1. The board acts; the minutes record it.
  2. A person answers the board-roster question.
  3. A second person confirms.
  4. A person applies it.
- **Shape** (made up):

  ```json
  {"offices": [{"role": "treasurer", "holders": [{"name": "Sam Example", "approves": ["the treasurer"], "canSignIn": true}],
                "duties": [{"title": "Budget report to members", "owners": [{"role": "treasurer", "adoption": "proposed"}]}]},
               {"role": "vice_president", "vacant": true, "vacancy": "No one holds the office of vice president.",
                "provisionNote": "The provision is not on file."}],
   "terms": {"onFile": true, "rows": [{"person": "Sam Example", "seat": "director", "start": "2098-11-17",
             "end": "2100-11-16", "source": "Minutes of 2098-11-17", "provision": "Bylaws 5.2"}]}}
  ```

### `RecitalBlock`

A statute recited inside a document: the meeting notice's delivery section, the agenda's reminder, a letter.

- **The words:** in the document's serif, set as a quotation, with the citation as its heading ("Civil Code Section 4045(b) reads:") and the edition in small print.
- **An omission** is an ellipsis inside the quotation, never a paraphrase around it.
- **The miss:** "Civil Code Section 4045 is not on disk (not in the library). Its words are not paraphrased here: export the authorities, then draw it again." It is highlighted to be fixed before printing, and the document cannot be marked ready while one shows.
- **In print:** the quotation keeps its rule; the miss prints as a blank box, never as words.

### `FormatLines`

A meeting's format decides what its notice and agenda must carry.

| Format | Lines |
|---|---|
| In person | the place |
| Hybrid | the physical location members may attend, and a director or the board's designee present there (CIV 4090(b)) |
| Held entirely by teleconference | how to join; the telephone option; the help contact; the individual-delivery reminder; every vote by roll call (4926(a)(1)-(4)) |

- The format is chosen first, and the lines follow; a line that does not apply is not shown greyed, it is absent.
- **Refused:** teleconference for a meeting where ballots are counted (4926(b)), with the words "A meeting at which ballots are counted cannot be held entirely by teleconference."
- **A blank** (no help contact named, no place) is a highlighted field to fill, never a sample value.
- **The open-forum line** appears only when the board has adopted a limit.

### `BottomSheet`

The meeting room's host panel is a bottom sheet under 720px. The dock's drawers want the same on a phone.

- **Parts:** a 44px handle ("Host panel" / "Hide the panel", `aria-expanded`), a row that stays (the tabs), and a body that scrolls.
- **States:** collapsed (the handle and the row); open (up to 78% of the screen); open on a tab.
- **Content survives collapse:** a drafted motion is still there when it opens.
- **What the design decides:** whether it starts open or collapsed, and whether it slides.
- Serving the console to a phone is a deployment decision; the layout is ready for it.

### `ScrollRow`

The tab row now scrolls sideways instead of widening the page.

- **Show that it scrolls:** a fade at the edge that has more, and the selected tab scrolled into view without moving the page.
- **Keyboard:** Left and Right (wrapping), Home and End, focus inside the row.
- Use it for any row of chips or filters, not only tabs.

## What must not change

- **A held item is never drawn as missing, broken, or forbidden to a person.** It is the statute's general note.
- **Status is computed.** No component offers "mark done", "approve" for jason, or a toggle that passes a gate.
- **Two people for a high-stakes answer.** The answerer never sees a confirm button on their own answer.
- **Nothing sends.** Sending, applying, and recording are a person's steps, shown as `PersonSteps`.
- **Recite, never paraphrase.** A statute missing from disk is a visible miss.
- **Seals for jason, stamps for a person, neither for a placeholder.**
- **Samples.** The design project is private and may use the association's real details where they help. What comes back into the repo is general: no association's facts in code or general docs, and made-up fixtures ("Sam Example", "123 Main St", `example.org`).

## Decisions that are the design's

1. Whether `HeldRow` shows the held count once per list or a line per held item.
2. The `PrivateGate`'s three variants: one component with a `variant` prop, or three.
3. How a standing question sits in setup: its own group, or at the end of its item.
4. `BottomSheet`'s starting state, and whether it slides.
5. `ScrollRow`'s edge treatment: a fade, an arrow button, or both.
6. Whether `PersonSteps` numbers its steps or uses the office glyphs as markers.

## Where each is used first

| Component | First screen | Then |
|---|---|---|
| `HeldRow`, `PrivateGate` | Board items | the meeting page, Plan a meeting, Decisions |
| `GateRail`, `ChecklistItem`, `PendingAnswer` | Onboarding → Setup | a new community's first run |
| `PersonSteps` | the notice (`jason board --notice`) | applying answers, a change of office, a letter's send |
| `OfficeCard`, `TermRow` | People and offices | the owner page's officers line, the board digest |
| `RecitalBlock`, `FormatLines` | the meeting notice | the agenda, letters, rule-change notices |
| `BottomSheet`, `ScrollRow` | the meeting room, onboarding | the dock on a phone |
