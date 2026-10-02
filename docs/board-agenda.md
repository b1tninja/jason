# Board action items, agendas, and minutes

## Action items

jason keeps a running list of matters that need a board decision in `data/board/items.json` (`jason board`, MCP `board_items`). Each item has:
- a stable id;
- what the records show, and what the board is asked to do;
- the authority, and the evidence, with the jason command that reproduces it;
- a priority (urgent, high, normal);
- the board's own fields: status (open, proposed, on agenda, in progress, deferred, closed), owner, meeting, and notes.

When a review finds the same matter again, it updates jason's fields and never the board's.

**Commands:**
- `jason board`: lists the open items.
- `jason board --set <id> --status proposed --owner Treasurer`: changes the board's fields and records the change in the item's history.
- `jason board --sheet`: syncs the board's action-items Google Sheet (created September 29, 2026; its id is `BOARD_ITEMS_SHEET` in `mystique/banking.py`, and `--sheet <id>` names another). The board edits status, owner, meeting, and notes there; each sync reads those back first, then writes every column. It is a private file in the association's Drive; share it with the directors from Drive. `--create-sheet` creates a new one.
- `jason board --tasks`: keeps the same items as a Google Tasks list of the same name in the signed-in account, on a token of its own (`secrets/google-tasks-token.json`; the first run needs `--interactive` to consent). Each open item is a task with the ask, status, owner, meeting, and a link to the Sheet in its notes, and the item's due date. Checking a task off closes its item, noted in the item's history; a closed item's task is completed. A Tasks list belongs to one account and is not shared, so the Sheet stays the directors' shared record. jason finds its tasks by a `jason:<id>` line in the notes, deletes none, and reports a task whose item it no longer has. With `--sheet --tasks` the Sheet is read first, then Tasks, then the Sheet is written again.

## Meetings

**The schedule is recorded in the specification** (`MEETING_SCHEDULE`, in `mystique/banking.py`): the resolution that fixes the meetings, their time and place, the regular months, and the annual meeting's day. A month the board meets in practice but the resolution does not make regular is labeled as such. This association's findings are in its private notes (mystique/notes/board-agenda.md).

**Drafting an agenda.** `jason board --agenda <last agenda Doc id>` drafts the next meeting's agenda the way the secretary does: from last month's Google Doc, read-only, including its smart chips (linked files, dates). It writes Markdown to `data/board/agenda-<date>.md`, and the draft:
- carries the header, the Zoom details, the standing items, and the decorum rules forward, and marks last month's business "carried over; keep or drop";
- points "approval of minutes" at the previous meeting and the treasurer's report at the previous month;
- adds what an all-Zoom meeting's notice must carry (CIV 4926(a)(1)): technical instructions, the telephone and email of a person who can help before and during the meeting (`--tech-contact`), and the reminder that members may ask for individual delivery;
- states that every vote of the directors is by roll call (4926(a)(3));
- gives the notice deadline, four days before the meeting (4920), and the rule against acting on items not on the agenda (4930);
- adds the board's proposed action items before the open forum, labeled action or report, with their authority and any notice of their own (5515(b) for a reserve loan, 4360 for a rule change);
- sends litigation and collections items to executive session (4935), and adds a report of the last executive session (4935(e));
- in November, notes that a meeting where ballots are counted cannot be held entirely on Zoom (4926(b)), and flags a meeting outside the resolution's regular months.

**The minutes template.** The minutes are sections (`jason.community.minutes_template.SECTIONS`). Each is a heading and a `{prompt}`: the instructions for what the section must record, the authority, and the minutes questions it answers. The template and the check are one list, and a question no section answers is a gap in the template (`uncovered`). The sections:
- **meeting:** type, date, and teleconference (4920, 4926);
- **call to order:** the time it happened, not the scheduled time;
- **attendance and quorum:** a roll call of each director, late arrivals and early departures, others by role, and whether a quorum was present (Bylaws 7.10);
- **prior minutes:** each set considered, the corrections, and the vote (4950);
- **business**, once per agenda item: the discussion; each motion's words, mover, second, and each director's roll-call vote (4926(a)(3)); every dollar amount and what it is for; a reserve transfer's written finding (5515(c)); and no action on an unlisted matter (4930);
- **open forum:** whether members spoke and on what, or that none came forward (4925(b));
- **executive session:** only the general nature of the matters (4935(e));
- **next meeting**, **adjournment**, and **recorded by** (Bylaws 10.10);
- **the 30-day availability note** (4950(a)).

`minutes-template-<date>.md`, written beside the agenda, is this template: each prompt in braces, a business block per agenda item, and roll-call tables for attendance and motions.

Minutes made this way close the gaps the minutes questions find in minutes that are the agenda with Zoom's AI recap appended: no roll call or vote, no directors listed, no call-to-order or adjournment time, no open forum note, and no recorder.

**Drafting the minutes from the Zoom record.** `jason board --minutes DATE` has the local model write each section by its prompt into `data/board/minutes-draft-<date>.md`, marked DRAFT; nothing is posted.

- **What the model gets:** only the open meeting. That is the transcript up to the executive session's break, with clock times; who was on the call and for how long; and the agenda's items.
- **What it doesn't get:** Zoom's AI summary, which can retell the executive session.
- **The executive session note:** only the general subjects, from the agenda's headings or the chair's words when adjourning.
- **Blanks, never guesses:** what the record does not show is a blank ("___ (not in the record)"). A person is a director only when the roster or the record says so.
- **The roster:** `jason board --members` reads the members PayHOA tags "Board Member" into `data/payhoa/board-members.json`, current and archived (a former director). The drafter uses that roster.
  - The tags are on each row of PayHOA's people list (`tags`, one entry per tag applied). `/tags/member` lists only the tag names, with one holder each.
  - The tag is what the board keeps in PayHOA; the minutes and the election results are the record of who serves.
- **Checks:** each section's supporting words are checked against the transcript. The draft is then asked the minutes questions, and what it still lacks is listed for the Secretary.

Set beside approved minutes that are a Zoom AI summary and asked the same minutes questions, a draft adds what the summary leaves out (the call to order, the adjournment to executive session, the quorum, the directors present, the open forum). Where the two differ on whether something was decided, the transcript settles it: an AI summary can record a discussion as a decision.

This association's findings are in its private notes (mystique/notes/board-agenda.md).

**Minutes that name a member.** `jason minutes-privacy` reads every minutes text for a member's name (PayHOA's people, matched in either order and without initials) within 120 characters of a delinquency, balance, payment plan, fine, violation, hearing, lien, collections, or foreclosure.
- A director named in the board's role is not a hit (the roster; "motion made by …, Board President").
- `--correct` writes a copy with each passage replaced by the general note CIV 4935(e) allows (`data/board/minutes-corrected-<date>.md`). The original is not changed.
- The minutes template's business section forbids naming a member in that way.
- This association's findings are in its private notes (mystique/notes/board-agenda.md).

**The agenda as a Google Doc.** `jason board --agenda <last agenda Doc id> --doc --yes` fills the **Board Meeting Agenda** template (My Drive/Templates, on the letterhead) into `My Drive/Meetings/<year>/DRAFT Agenda for M/D/YY`; `--preview` puts it in My Drive/Templates as "Preview - Agenda for M/D/YY" instead. A re-run rewrites the same Doc (its id is kept in `data/board/docs.json`). The Doc:
- has the meeting's name under the letterhead and a ruled box with the date, time, Zoom link, meeting ID, and telephone number, taken from the schedule and the last agenda's header;
- carries the 4926(a) statements in small print under the box; `{TECH_CONTACT}` stays visible until the secretary names the person who can help (`--tech-contact`);
- numbers the business I, II, III with sub-items A, B, C, as the secretary's agendas do, and sets "See:" lines in the item's indent without a number;
- highlights what the secretary must act on: last month's business "carried over: keep or drop", and each file to link ("[Minutes of 9/15/26]");
- groups the board's action items under **New Business**, each with its title, "(action)" or "(report)", the action proposed with its authority, and any notice the law requires. The background stays in the board packet;
- lists the executive session by the general nature of its business only (CIV 4935): the last agenda's headings, plus a general heading for an item they do not cover. An item's own title and ask stay in the packet;
- ends with the decorum rules, and repeats the meeting's name and date at the top of each later page.

The Markdown draft (`agenda-<date>.md`) keeps the secretary's notes that do not belong on the agenda: the notice deadline and the special-meeting and annual-meeting cautions.

**Nothing is posted automatically.** jason writes drafts in the association's private Drive folders; the secretary edits, renames, and posts the agenda.

## Suggested edits in the agenda Doc

The Docs API can write suggestions. A `documents.batchUpdate` with `writeControl.writeMode = SUGGEST` applies every request in it as a suggestion the Doc's editors accept or reject. jason's Docs client takes `write_mode="SUGGEST"`.

`meeting_agenda.insertion_requests` builds the requests that add the board's items before the "Open Forum" heading:
- It inserts one block at the start of that paragraph, so each title keeps the heading style and list numbering.
- Each note line becomes plain text.
- With `highlight=True`, for normal edits, the inserted text is shaded.

**Limits (September 2026):**
- `SUGGEST` is a Google Workspace **Developer Preview** feature, and the Cloud project must be enrolled. A few request types fail in that mode, such as named ranges, headers and footers, and tab changes. Inserting text and setting paragraph styles are not among them.
- Anchored comments come through the Docs API's `InsertCommentRequest`, also in Developer Preview. Comments made through the Drive API show in Docs as unanchored ("Original content deleted").
- Suggestions and comments are attributed to the signed-in account. A dedicated jason account would set its suggestions apart from the treasurer's.

**Fallbacks that work today:**
- Edit a copy of last month's Doc with the inserted text highlighted.
- Use Docs' Tools › Compare documents on the old and new agendas, which produces a suggestions-style redline.

Nothing is written to Drive without the board's approval.

## The board packet

`jason board --packet` (for the next meeting, or `--date`) writes `data/board/packet-<date>.md`. For each open-session item on the agenda it gives:
- the background and the question for the board;
- **the law**: the sections the item cites, quoted from `data/authorities` and trimmed to the cited subdivisions;
- **what the records show now**: facts re-read from the review that found the item (`RESEARCHERS`: cost centers, reserve transfers, fire and insurance deadlines, developer securities);
- **the board's notes**, with each `{REPORT:key}` in them shown as that report's last run (`jason.tasks.live_reports`), like documentation that says "run this command" and comments on the output: the report's command, what it reads, when it ran, and a link to its own Doc, then its rows, then the board's words around it. Set one with `jason board --set ITEM --notes "Commentary {REPORT:occupancy-signals} more commentary"`;
- the evidence;
- **options** and a **draft motion** (`OPTIONS`, or a generic frame);
- any notice the item needs of its own, and its deadline.

Executive session items are listed by title only. The packet is research, not advice: the board weighs the options, and counsel's reading of the law governs.

**Reports: documents of their own.** A report a note names is run on its own and kept, so refreshing its facts never means rebuilding the packet:

```bash
jason report --list                                # each report, when it last ran, stale or failed, and its Doc
jason report occupancy-signals                     # run one now: data/reports/live/occupancy-signals.md
jason report occupancy-signals --doc --yes         # and rewrite its own Doc (My Drive/Meetings/Reports, private)
jason report --all --doc --yes                     # every report the board's items name
jason board --packet                               # shows each named report's last run (seconds; reads nothing live)
jason board --packet --refresh-reports             # runs the named reports first
```

- A run is saved with when it ran, its command, and what it read. A report never run is run once by the first document that names it; after that a document shows the saved run and says when it was made.
- A run older than a week is flagged in the document, with the command that refreshes it. A refresh that fails (no network, a login needed) keeps the last good rows and says it could not refresh.
- Reports: `occupancy-signals` (units the evidence reads as not owner-occupied but untagged, and occupancy tags that may describe a former owner, from PayHOA live, the county roll, and the deeds). Reports never print names, addresses, or emails. A new report is one `Report` row: its command, what it reads, and its function.

**PayHOA's packets, included as built.** PayHOA keeps every report packet run (Treasurer's Report, Annual Financial Package, Pro Forma Budget) with its own PDF. `jason report treasurers-report` reads that list into a catalog (`tasks/report_runs.py`, `data/payhoa/report-runs.json`; one read-only call), and a reference with a period includes the run already made:

```bash
jason report --catalog                                          # every run: packet, month, when, pages, where its PDF is
jason report treasurers-report period=previous-month            # re-read the catalog; show last month's run
jason report treasurers-report period=2026-08 --doc --yes       # file that run's PDF in My Drive/Meetings/Reports
```

- `period=` is `YYYY-MM`, `previous-month` or `this-month` (counted from the document's date: the meeting's, for the packet), or `latest`.
- In a document the reference resolves from the catalog on disk each time it is built: no PayHOA call, and no packet is ever built. A month not run yet says so and names the newest run; running the packet is the treasurer's, in PayHOA (Reports, Report Packets).
- Each run carries the month it reports, notes when its dates do not fit a monthly report, and the library copy that is the same file by its SHA-256. With `--doc --yes` PayHOA's PDF, unchanged, is filed in Drive and the packet links to it.
- **Every packet carries** the reports `packet_reports()` names in the specification (for example, last month's Treasurer's Report), under "Reports" before the items.

**The packet as a Google Doc.** `jason board --packet --doc --yes` also writes it to `My Drive/Meetings/<year>/Board Packet for M/D/YY (confidential)` on the letterhead, in the house style (headings with a rule under each item, the quoted law set in, numbered options). The Doc is not shared: the folder is private to the association's account. It opens with a confidentiality line and repeats "Confidential: for the directors and counsel" at the top of each later page, because parts draw on privileged advice and on figures shared for mediation only (Evidence Code 1119). A re-run rewrites the same Doc (`data/board/docs.json`); share it with the directors from Drive.

## Rule changes under Civil Code 4360

A proposed change to an operating rule is a `RuleChange` row in `mystique/rule_changes.py`: the rule it amends (an outline key), the proposed words section by section (a whole section, or a `strike` of a few words), the purpose and effect, and what the board and counsel must decide. A `[bracket]` in the proposed text is the board's choice; jason never fills in a fee or a date. The current words are read from `data/outlines/<document>.json`, not copied into the row.

`jason rule-change <key>` writes `data/board/rule-change-<slug>.md`:
- **the timeline**: the decision meeting is the first meeting on `meeting_schedule()` at least 28 days after the notice date (`--notice-date`, default today; `--decision` to name one, refused if under 28 days; `--regular-months-only` to count only the resolution's months), the last day to send the notice, the comment deadline (default the day before), the agenda notice (4920, 4 days), the notice of adoption (4360(c), 15 days), the last day for a reversal request (4365(b), 30 days after), and the annual policy statement window (5310);
- **(a) the member notice** (4360(a)): the text of the change, its purpose and effect, how and by when to comment, and the decision meeting, with a checklist of the required elements; it goes by general notice (4045);
- **(b) the agenda item** for the decision meeting, with a draft motion;
- **(c) the notice of adoption** template, with the members' right to call a reversal vote (4365);
- **the law**, quoted from `data/authorities`; a citation not exported is marked unverified.

`--draft-email` previews the member notice as a Gmail draft with no recipients; `--draft-email --yes` saves it. jason never sends: a person addresses the draft to the members whose preferred delivery method is email (4041) and mails the rest.

Note 4355(a): 4360 and 4365 apply only to rules on the subjects it lists. For a change not plainly among them, the board may follow 4360 anyway, and counsel says whether it must. This association's findings are in its private notes (mystique/notes/board-agenda.md).
