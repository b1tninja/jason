"""The board family's general workflow definitions (docs/workflows/board-governance.md, sections 2.1 to 2.7).

``BUILDERS`` lists the definitions the Work backend can hold today: ``board-meeting``, ``rule-change``, ``election``,
``law-review``, ``duty-schedule``, ``document-duties``, and ``owners-manual``. ``hearing`` (a member's discipline, CIV
5855) is built by ``hearing()`` and **left out of ``BUILDERS``**: ``jason.web.extra.work`` says executive-session handling
(CIV 4935(e)) is "not composed" (no step can be marked executive, so a run shows in full and no opening is logged), and a
hearing's matter, member, and unit are exactly what must not show in a run list. Add it to ``BUILDERS`` when a step can be
marked held. Even then its run id is opaque and its subject is a handle, never an address (docs/workflows/board-
governance.md, section 5).

Pure data, like ``definitions_general``: it imports only the engine's types, and no store, client, or profile. Nothing here
names an association: a run's dates are slots asked at start, a statute is cited by key and checked against the
authorities shelf, and whoever holds a role acts.

How the page's table became steps (the reasons are in each step's ``why``):

- **Step ids** are ``<key>.<n>`` with n the page's number (``rule-change.0`` is r0). A page row that holds two kinds is
  its number and a dotted one (``duty-schedule.5``, ``duty-schedule.5.1``).
- **A step the page gives to jason** (a check or a job) is a ``person`` step, because no read or job of that name is
  registered (``readers.CHECKS`` and ``JOBS`` are not touched here). Its ``why`` says what it becomes, and ``WANTED``
  lists them. A ``plan`` is used only for a registered approvals kind: ``gmail-drafts`` (cases ``meeting-notice``,
  ``hearing``, ``proposal-request``) and ``payhoa-mailroom-send``.
- **A decision step** is recorded by the secretary at the board's meeting; the run never takes the vote.
- **A law clock** is cited only where the statute is on the shelf. A computed date is the plain day-count of the
  statute's words, with no holiday or weekend rule applied, and a person confirms it. Corporations Code 7341 is not on the
  shelf, so the hearing's suspension notice is a labeled constant of the code, never a law clock.
- **A legal step cannot have a skip rule**, so where the page says a step with a law clock is skipped in some case, the
  case is a branch's path (the engine skips the other paths' steps itself) and the step carries no skip rule.
"""

from __future__ import annotations

from typing import Any, Callable

from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, DateSlot, Elapsed, Phase, Repeat, Role, SkipRule, StepDef, StepKind, Workflow,
)

P, PL, D, W, B = StepKind.PERSON, StepKind.PLAN, StepKind.DECISION, StepKind.WAIT, StepKind.BRANCH
M, S, T, A = Role.MANAGER, Role.SECRETARY, Role.TREASURER, Role.ADMINISTRATOR
JASON, ANYONE = Role.JASON, Role.ANYONE
EACH = Repeat.PER_ITEM

WANTED: tuple[str, ...] = (
    # reads that would be `check` steps (names to add to readers.CHECKS)
    "check:meeting-clocks", "check:notice-delivery-read", "check:executive-note-open", "check:minutes-checks",
    "check:run-complete", "check:rule-in-force", "check:rule-authority", "check:notice-text", "check:rule-stages",
    "check:election-rules-window", "check:hearing-dates", "check:hearing-delivery-read", "check:hearing-requirements-met",
    "check:hearing-minutes-note", "check:readings-stale", "check:shelf-cites", "check:retire-reasons",
    "check:schedule-due", "check:schedule-coverage", "check:manual-headings", "check:manual-concordance",
    "check:manual-template-equal",
    # jobs (names to add to readers.JOBS)
    "job:meetings-sync", "job:board-reports-refresh", "job:board-packet-build", "job:board-notice-draw",
    "job:minutes-draft", "job:rule-change-timeline", "job:law-export", "job:law-versions", "job:outlines-fetch",
    "job:conflict-leads", "job:law-sweep", "job:cite-survey", "job:section-refs-scan", "job:schedule-read-google",
    "job:schedule-evidence", "job:duties-read", "job:duties-fill-bearers", "job:duties-score", "job:manual-classify",
    "job:manual-render", "job:revisions-fetch",
    # approvals kinds and cases (to register)
    "kind:google.doc", "kind:google.calendar+google.tasks", "kind:zoom.hearing.create", "kind:local.section-refs.apply",
    "case:gmail-drafts/rule-change-proposed", "case:gmail-drafts/rule-change-adopted",
    "case:gmail-drafts/election-notice", "case:gmail-drafts/decision-notice",
)
"""What the definitions want that does not exist: ``check:`` and ``job:`` names for ``readers`` (a step that would use one is a
``person`` step until it is registered), ``kind:`` approvals kinds, and ``case:`` cases of the ``gmail-drafts`` kind."""

NO_DAY_RULE = "computed by the statute's plain day-count, no holiday or weekend rule applied; a person confirms the day"


def _law(cite: str, label: str, slot: str = "", days: int = 0) -> ClockDef:
    """A law clock: ``cite`` is on the authorities shelf, and a date, when computed, is labeled as the plain count."""
    return ClockDef(ClockBasis.LAW, slot, days, cite=cite, label=f"{label} ({NO_DAY_RULE})" if slot else label)


def _policy(label: str, slot: str = "", days: int = 0) -> ClockDef:
    return ClockDef(ClockBasis.PROPOSED_POLICY, slot, days, label=f"{label} (proposed policy: the board adopts or changes it)")


def _person_day(label: str, slot: str, days: int = 0) -> ClockDef:
    return ClockDef(ClockBasis.PERSON, slot, days, label=label)


def _ids(key: str) -> tuple[Callable[[str], str], Callable[..., StepDef]]:
    def sid(n: str) -> str:
        return f"{key}.{n}"

    def step(n: str, title: str, kind: StepKind, role: Role, needs: tuple[str, ...] = (), **more: Any) -> StepDef:
        return StepDef(sid(n), title, kind, role=role, needs=tuple(sid(x) for x in needs), **more)

    return sid, step


def _phases(sid: Callable[[str], str], *rows: tuple[str, str, tuple[str, ...]]) -> tuple[Phase, ...]:
    return tuple(Phase(k, t, tuple(sid(n) for n in ns)) for k, t, ns in rows)


def _become(what: str) -> str:
    return f" Becomes {what} when it is registered."


# --- board-meeting (2.1) ---------------------------------------------------------------------------------------------

BM = "board-meeting"


def board_meeting() -> Workflow:
    """One board meeting: notice, agenda, packet, the meeting, the minutes, and their approval (SOP ``board-packet``). The
    run's subject is the meeting's day (ISO date), nothing else: a matter held in executive session is named in the
    packet by its CIV 4935 subject only, and the run holds no matter."""
    sid, step = _ids(BM)
    skip = SkipRule()
    notice_by = _law("CIV 4920(a)", "notice of the meeting given by", "meeting_on", -4)
    steps = (
        step("1", "Rebuild the meeting catalog", P, M, sop="board-packet#1", command="jason meetings --sync",
             record="the catalog rebuilt, and when",
             why="A notice already sent must be on record before the clocks are read (SOP board-packet); cadences already run it."
                 + _become("the job `meetings-sync`")),
        step("2", "Read the clocks forward: the last day to notice the meeting, and the minutes owed from the last one", P, S, ("1",),
             sop="board-packet#1", command="jason schedule-evidence --watch", clock=notice_by,
             record="the notice-by day and the minutes still owed",
             why="Notice is 'at least four days before the meeting' (CIV 4920(a)), or the longer period in the governing documents "
                 "(4920(b)(3)); the last meeting's minutes are due within 30 days (4950(a))." + _become("the check `meeting-clocks`")),
        step("3", "Say the kind and format of the meeting", B, S, ("2",), sop="board-packet#2",
             command="jason notices --catalog --fact board_meeting=ordinary --fact meeting_format=in_person",
             choices=(Choice("ordinary", tuple(sid(n) for n in ("9", "10", "11", "12", "13", "20"))),
                      Choice("executive_only", tuple(sid(n) for n in ("9", "10", "11", "12", "13"))),
                      Choice("emergency", (sid("20"),))),
             why="An executive-session-only meeting needs notice two days before (CIV 4920(b)(2)); an emergency meeting follows 4923 "
                 "(record its reason) and skips the notice steps; a meeting held only in executive session has no minutes to make "
                 "available (4950(a))."),
        step("4", "Bring the action items up to date for the meeting", P, M, ("3",), sop="board-packet#5", repeat=EACH,
             command="jason board --set ITEM --status 'on agenda' --meeting DATE", record="the items on the agenda (ids)",
             why="Items from other runs arrive by link; an executive item is listed by its 4935 subject only."),
        step("5", "Refresh the reports the items name", P, M, ("4",), sop="board-packet#7", repeat=EACH,
             command="jason report --all", clock=_policy("the day before the meeting", "meeting_on", -1),
             record="the reports refreshed, none stale or failed",
             why="A live report is read at the packet, not copied into an item." + _become("the job `board-reports-refresh`")),
        step("6", "Run last month's Treasurer's Report in PayHOA", P, T, ("5",), sop="board-packet#7", skip=skip,
             command="jason report treasurers-report period=previous-month",
             clock=_policy("the day before the meeting", "meeting_on", -1), record="the report-run catalog entry for the month",
             why="Skipped, with the reason, when no report is due."),
        step("7", "Build the packet", P, M, ("4", "5", "6"), sop="board-packet#8", command="jason board --packet",
             record="the packet file built",
             why="Executive items are listed by their 4935 subject only; run it again when an item changes."
                 + _become("the job `board-packet-build`")),
        step("8", "Make the private packet Doc and the members' copy", P, M, ("7",), sop="board-packet#8", skip=SkipRule((M,)),
             command="jason board --packet --doc --yes; jason board --packet --audience members --by NAME",
             record="the Doc in the private folder, and the members' copy in the letters store",
             why="The members' copy is skipped, with the reason, when the profile names no approver." + _become("a plan of kind `google.doc`")),
        step("9", "Draft the agenda", P, S, ("3", "4"), sop="board-packet#9", command="#/agenda; jason board --agenda DOC_ID --doc --yes",
             clock=_law("CIV 4920(d)", "the notice shall contain the agenda (a content rule, not a day)"),
             record="the agenda Doc, its format line naming the meeting's format",
             why="Notice of a board meeting shall contain the agenda (CIV 4920(d)); no item outside it is acted on at a nonemergency "
                 "meeting (4930(a))." + _become("a plan of kind `google.doc`")),
        step("10", "Draw the notice and check its elements", P, S, ("9",), command="jason board --notice --date DATE; jason notice-check FILE --requirement board-meeting",
             record="the notice file, statutes recited from disk, nothing missing",
             why="The last day to give it is step 2's notice-by." + _become("the job `board-notice-draw`")),
        step("11", "Save the notice as a Gmail draft", PL, S, ("10",), plan_kind="gmail-drafts",
             command="jason approvals plan gmail-drafts --scope '{\"case\":\"meeting-notice\",\"key\":\"DATE\"}' --by NAME",
             clock=notice_by, why="A draft with no recipient until a person chooses; the case is `meeting-notice`. jason never sends."),
        step("12", "Post and send the notice, and record the posting", P, S, ("11",), clock=notice_by,
             command="jason notices board-meeting-DATE --mark-general --posted \"WHERE, DATE\" --by NAME",
             record="where and when it was posted and sent",
             why="Delivery is 'by general delivery pursuant to Section 4045' (CIV 4920(c)); none on record is not none given, so the "
                 "posting is recorded. Read and link: the posting is recorded on `#/meetings` and the step reads done when it appears."),
        step("13", "Read delivery until nothing is owed", W, S, ("12",), clock=notice_by,
             command="jason notices board-meeting-DATE --sync",
             why="A file never meets the notice clock; only a delivery, or a send with follow-ups listed, does. Past the notice-by "
                 "day with no delivery on record the run says so in the law's words (4920(a)). Ends when a person notes the delivery."
                 + _become("the check `notice-delivery-read` with jason as the role")),
        step("14", "Share the packet with the directors", P, S, ("8",), sop="board-packet#10", command="Drive (outside the console)",
             clock=_policy("before the meeting", "meeting_on", 0), record="that the packet was shared, and when",
             why="The directors read the same packet at the same level of access."),
        step("15", "Hold the meeting", P, S, ("13",), command="#/room", clock=_person_day("the meeting day", "meeting_on", 0),
             record="the room record, open (the executive record is kept apart)",
             why="The chair presides and the secretary keeps the room record; a step has one role, so the secretary records it "
                 "(the family page names the president as chair)."),
        step("16", "Each motion decided", D, S, ("15",), repeat=EACH, command="#/room; #/decisions", record="the decision id",
             why="Recorded by the secretary with the roll call by name; a vote taken in executive session is read in the private "
                 "view only. The run never takes the vote."),
        step("17", "Note any executive session generally in the minutes", P, S, ("15",), skip=skip,
             record="the open record holds only the 4935 subject and the times",
             command="jason board --minutes DATE",
             why="A matter discussed in executive session is generally noted in the minutes of the next open meeting (CIV 4935(e)); "
                 "skipped, with the reason, if none was held." + _become("the check `executive-note-open`")),
        step("18", "Bring in the Zoom record and draft the minutes", P, S, ("15",), sop="board-packet#3",
             command="jason meetings --sync; jason board --minutes DATE", record="the minutes draft, marked DRAFT",
             why="Start soon: the minutes are due within 30 days (step 20). A local model runs only after the GPU preflight; if it "
                 "fails, the secretary writes them by hand." + _become("the job `minutes-draft`")),
        step("19", "Read jason's checks on the draft", P, S, ("18",), sop="board-packet#3",
             command="jason board --minutes DATE --recheck; jason minutes-privacy",
             record="the quorum counted and the blanks listed, clean",
             why="A draft that claims a quorum the count does not support blocks the next step." + _become("the check `minutes-checks`")),
        step("20", "Fill the blanks, make the minutes available, and record it", P, S, ("19",), sop="board-packet#4",
             command="#/minutes-review; jason schedule --done KEY DUE --by NAME --evidence TEXT",
             clock=_law("CIV 4950(a)", "minutes available to members within 30 days of the meeting", "meeting_on", 30),
             record="the filled copy and the availability record",
             why="Minutes, proposed minutes marked as draft, or a summary 'shall be available to members within 30 days of the "
                 "meeting' (CIV 4950(a)); skipped by the path for a meeting held only in executive session. Read and link: step 12's "
                 "kind of record on `#/meetings`."),
        step("21", "The board approves the minutes at its next meeting", D, S, ("20",), sop="board-packet#4",
             command="jason record-stages --meeting DATE", clock=_person_day("the next meeting", "next_meeting_on", 0),
             record="the decision id on that meeting's approval item",
             why="The next minutes state the approval in words ('approved: stated'); 'listed, not stated' keeps it open."),
        step("22", "Close the run", P, S, tuple(str(i) for i in range(1, 22)), record="that every step is done or skipped",
             why="A late-found fact reopens the run." + _become("the check `run-complete`")),
    )
    phases = _phases(sid, ("prepare", "Prepare", ("1", "2", "3", "4", "5", "6", "7", "8")),
                     ("notice", "Notice", ("9", "10", "11", "12", "13", "14")),
                     ("meeting", "The meeting", ("15", "16", "17")),
                     ("minutes", "Minutes", ("18", "19", "20", "21", "22")))
    return Workflow(key=BM, title="A board meeting", family="board", subject="meeting", steps=steps,
                    dates=(DateSlot("meeting_on", "The meeting day"),
                           DateSlot("next_meeting_on", "The next meeting, which approves the minutes", required=False, after="meeting_on")),
                    phases=phases, procedure="board-packet")


# --- rule-change (2.2) -----------------------------------------------------------------------------------------------

RC = "rule-change"


def rule_change() -> Workflow:
    """Adopt, amend, or repeal an operating rule (SOP ``rule-change``, then ``owners-manual``). The subject is a
    ``RuleChange`` key. The notice day and the decision meeting are asked at start; an emergency change (CIV 4360(d))
    has no notice day."""
    sid, step = _ids(RC)
    skip = SkipRule()
    noticed = _law("CIV 4360(a)", "general notice given by", "decision_on", -28)
    steps = (
        step("0", "Read the rule as a record: the version in force, and any change with no adoption", P, M, skip=SkipRule((M,)),
             command="jason revisions KEY --fetch --versions; jason rule-records --show ID --as-of DAY", record="the version read, and the day",
             why="Skipped, with the reason, only if the rule is new." + _become("the check `rule-in-force`")),
        step("1", "Say the change's facts and read the reach of CIV 4355", B, ANYONE, ("0",), sop="rule-change#1",
             command="jason notices --catalog --fact rule_scope=listed_subject --fact rule_change=noticed",
             choices=(Choice("listed", tuple(sid(n) for n in ("6", "7", "8", "9", "10", "17", "18"))),
                      Choice("not_reached", (sid("17"), sid("18"))), Choice("emergency", ())),
             why="listed: noticed under 4360. not_reached: a one-off board action needs no rule (4355(b)). emergency: 'If the board "
                 "determines that an immediate rule change is required' (4360(d)); it skips the member notice and the reversal window "
                 "(4365(h)). Where two readings remain, the board asks counsel, and the lawful course under either is the notice."),
        step("2", "Check authority and conflicts", P, M, ("0",), command="jason rules --subjects; jason conflicts",
             record="the grant of authority, the conflicts, any duplicate of the declaration",
             why="A flag is acknowledged by a person and does not block." + _become("the check `rule-authority`")),
        step("3", "Draft the proposed words, the reason, and the purpose and effect", P, ANYONE, ("1",), sop="rule-change#2",
             command="a RuleChange row in the profile; #/rules", record="the RuleChange key, with the words and the bracketed choices",
             why="jason never fills a bracket; the board's choices stay in brackets."),
        step("4", "Compute the timeline: notice day, decision meeting, comment deadline", P, M, ("3",), sop="rule-change#2",
             command="jason rule-change KEY --notice-date DATE", clock=_policy("comment deadline: the day before the decision", "decision_on", -1),
             record="the dates computed",
             why="The decision meeting is the first meeting at least 28 days after the notice (CIV 4360(a)); the run's dates were set "
                 "from it." + _become("the job `rule-change-timeline`")),
        step("5", "Put it before the board", P, M, ("3", "4"), command="jason board --set ITEM ...; #/actions", record="the board item (id)",
             why="One item, with the text, the clock, and the readings."),
        step("6", "Check the notice text for its required elements", P, S, ("3",), sop="rule-change#4",
             command="jason notice-check FILE --requirement rule-change-proposed --event rule_scope=listed_subject",
             record="the elements present, none missing",
             why="The notice 'shall include the text of the proposed rule change and a description of the purpose and effect' (CIV 4360(a)); "
                 "text first." + _become("the check `notice-text`")),
        step("7", "Save the member notice as a Gmail draft", P, S, ("6",), sop="rule-change#3", clock=noticed,
             command="jason rule-change KEY --draft-email --yes --by NAME", record="the draft, with no recipients, and its text kept",
             why="At least 28 days before the decision (CIV 4360(a)). The `rule-change` case of `gmail-drafts` is not built, so this is "
                 "a person's step." + _become("a plan of kind `gmail-drafts`, case `rule-change-proposed`")),
        step("8", "Address, send, and post the notice", P, S, ("7",), sop="rule-change#5", clock=noticed,
             command="jason notices rule-change-proposed-KEY --mark-general --posted ... --by NAME", record="the notice sent, and the posting",
             why="General notice pursuant to Section 4045 (CIV 4360(a)); a posting is recorded, not assumed."),
        step("9", "Read delivery of the notice", W, S, ("8",), sop="rule-change#5", clock=noticed,
             command="jason notices rule-change-proposed-KEY --sync",
             why="A file never meets the 28-day clock; only a delivery, or a send with follow-ups listed, does. If late, the decision "
                 "meeting moves. Ends when a person notes the delivery."),
        step("10", "Collect the members' comments", P, S, ("8",), repeat=EACH,
             clock=_law("CIV 4360(b)", "consider the comments before deciding", "decision_on", 0),
             record="each comment received, dated",
             why="'A decision on a proposed rule change shall be made at a board meeting, after consideration of any comments made by "
                 "association members' (CIV 4360(b)). No store records a comment yet."),
        step("11", "Agenda item for the decision meeting", W, S, ("5", "9"), command="#/agenda",
             clock=_law("CIV 4920(a)", "agenda notice given by", "decision_on", -4),
             why="Linked to the agenda item of a `board-meeting` run. Blocked if the meeting is under 28 days after the notice."),
        step("12", "Wait for the decision meeting", W, JASON, ("11",), elapsed=Elapsed.ENDS,
             clock=_person_day("the decision meeting", "decision_on", 0),
             why="The meeting day ends the wait; a decision that is continued returns here."),
        step("13", "The board decides", D, S, ("9", "10", "12"), command="#/room; #/decisions", record="the decision id",
             clock=_person_day("the decision meeting", "decision_on", 0),
             why="Made at a board meeting after notice and comments (CIV 4360(a), (b)); the secretary records it, the run takes no vote. If "
                 "the words change at the meeting, whether a new notice is needed is a reading for counsel."),
        step("14", "Record the adoption from the minutes and read the stages", P, S, ("13",), sop="rule-change#6",
             command="jason record-stages --change KEY", record="the adoption, with the minutes reference",
             why="The adopted words are entered from the minutes, not typed." + _become("the check `rule-stages`")),
        step("15", "Notice the adopted change", P, S, ("14",),
             clock=_law("CIV 4360(c)", "adoption notice delivered by", "decision_on", 15),
             command="jason rule-change KEY (section c)", record="the adoption notice, and its delivery day",
             why="'Not more than 15 days after making the rule change' (CIV 4360(c)); an emergency change carries its text, purpose and "
                 "effect, and expiry date." + _become("a plan of kind `gmail-drafts`, case `rule-change-adopted`")),
        step("16", "Read delivery of the adoption notice", W, S, ("15",), command="jason notices rule-change-adopted-KEY --sync",
             clock=_law("CIV 4360(c)", "adoption notice delivered by", "decision_on", 15),
             why="Ends when a person notes the delivery."),
        step("17", "Hold the reversal window", W, S, ("16",), command="jason record-stages --change KEY",
             clock=_law("CIV 4365(b)", "a written request may not be delivered more than 30 days after the association gives general "
                                      "notice of the rule change (counted from the adoption notice's day)"),
             why="Not applicable to an emergency change (CIV 4365(h)). No date is computed here: it runs from the day the adoption notice "
                 "was given, and a person notes the window's end."),
        step("18", "A reversal request arrives, or none by the window's end", B, S, ("17",),
             choices=(Choice("request", ()), Choice("none", ())),
             why="A written request from members owning 5 percent of the separate interests (CIV 4365(a)). If yes, open an `election` run "
                 "(a member vote); a reversed change cannot be readopted for a year (4365(f)). The engine's spawn would not hold "
                 "step 19 for the child, so the secretary records the choice only when the vote is over."),
        step("19", "Carry out the effects: the manual, the next policy statement, citations, new-member packets", P, M, ("14", "18"),
             sop="rule-change#7", spawns="owners-manual", command="jason manual --render; jason document-template",
             record="each effect carried out (a link or a note)", why="Opens an `owners-manual` run; each effect is its own note."),
        step("20", "Record the lesson", P, M, ("19",), skip=skip, command="jason lessons --area governing", record="the lesson row, or none",
             why="Skipped, with the reason, when nothing was learned."),
    )
    phases = _phases(sid, ("read", "Read and draft", ("0", "1", "2", "3", "4", "5")),
                     ("notice", "Notice and comment", ("6", "7", "8", "9", "10", "11", "12")),
                     ("decide", "The board decides", ("13", "14")),
                     ("after", "After adoption", ("15", "16", "17", "18", "19", "20")))
    return Workflow(key=RC, title="A rule change", family="board", subject="rule-change", steps=steps,
                    dates=(DateSlot("notice_on", "The day the member notice is given", required=False),
                           DateSlot("decision_on", "The decision meeting", after="notice_on")),
                    phases=phases, procedure="rule-change")


# --- election (2.3) --------------------------------------------------------------------------------------------------

EL = "election"
KIND_PATHS = ("directors", "recall", "assessment", "amendment", "exclusive_use", "other")


def election() -> Workflow:
    """An election of directors, a recall, or a member vote (CIV 5100 to 5145; SOP ``election``). No ballot, no candidate,
    no voter appears in a label or a step: the inspector of elections holds them outside jason. The dates are asked at
    start; none is shortened (a passed notice day moves the election)."""
    sid, step = _ids(EL)
    skip = SkipRule()
    directed = ("2.1", "2.2", "7", "8", "9", "10", "10.1", "11")          # the steps that only an election of directors or a recall has
    only_directors = tuple(sid(n) for n in directed)
    choices = tuple(Choice(k, only_directors if k in ("directors", "recall") else ()) for k in KIND_PATHS)
    steps = (
        step("1", "Say the kind of election", B, S, sop="election#1", command="jason notices --catalog --fact election=directors",
             choices=choices,
             why="The kind decides which notices apply (directors, a recall, or a member vote such as an assessment, an amendment, or a "
                 "reversal of a rule change). A row left undetermined is never read as 'not required'. A member vote skips the "
                 "nomination, acclamation, and pre-ballot notice steps (7 to 11, 2.1, and 2.2)."),
        step("2", "Answer the standing facts with the record that states each", P, ANYONE, ("1",), sop="election#2",
             command="jason applies --questions; jason intake --answer ID TEXT --by NAME", record="each answer, with the record that settles it",
             why="Electronic ballots and opt-out in the election rules; the quorum in the documents. 'Undetermined' is never 'not required'."),
        step("2.1", "The board decides whether acclamation is available", D, S, ("1",), command="#/decisions", record="the decision id",
             why="A standing fact the board writes down once (where the law is silent, a written policy). Acclamation is 'may, but is not "
                 "required' (CIV 5103)."),
        step("2.2", "Say whether acclamation is available", B, S, ("2.1",),
             choices=(Choice("available", (sid("8"),)), Choice("not_available", ())),
             why="Skips the acclamation notices when it is not. This branch is added because the notice step has a law clock, and a step "
                 "with a law clock cannot be skipped by a person."),
        step("3", "Check the election rules in force, and that none is amended inside the window", P, S, ("2",),
             command="jason rule-records; jason record-stages --rules",
             clock=_law("CIV 5105(h)(4)(B)(iii)", "election operating rules not amended less than 90 days prior to the election",
                        "count_on", -90),
             record="the rules' record, and any rule-change run that amends them",
             why="Blocks the dates (step 5) if a change falls inside the window." + _become("the check `election-rules-window`")),
        step("4", "Select the inspector or inspectors", P, S, ("2",), record="the rules' method and who selected, with the record",
             clock=_law("CIV 5110(a)", "one or three independent third parties (a number, not a day)"),
             why="'The number of inspectors of elections shall be one or three' (CIV 5110(a)); none a director, candidate, or contractor "
                 "(5110(b)). If the election rules are silent on who selects, that is a question for the board, not a default. When the "
                 "rules give the choice to the board, its decision is recorded at a meeting and its id is the record."),
        step("5", "Set the dates, and the notice day each forces", P, S, ("3", "4"),
             clock=_policy("room for one correction before each notice day"),
             record="nomination deadline, ballots out, voting deadline, count meeting, opt-out deadline",
             command="the catalog anchors NOMINATION_DEADLINE, BALLOTS_DISTRIBUTED, VOTING_DEADLINE, OPT_OUT_DEADLINE",
             why="A passed notice day moves the election; no clock is shortened. The dates were asked at start; this confirms them."),
        step("6", "Candidate list and voter list", P, S, ("5",), repeat=EACH,
             clock=_law("CIV 5105(a)(7)", "voter list verified at least 30 days before the ballots are distributed", "ballots_out", -30),
             record="both lists retained by the inspector; each correction",
             why="The inspector keeps them; members verify their entries and corrections are made within two business days "
                 "(CIV 5105(a)(7)). The secretary records what the inspector reports."),
        step("7", "Notice of the nomination procedure", P, S, ("5",), sop="election#4",
             command="jason notice-check FILE --requirement nomination-procedure --event election=directors",
             clock=_law("CIV 5115(a)", "nomination-procedure notice at least 30 days before any nomination deadline", "nomination_deadline", -30),
             record="the notice sent, its text checked",
             why="Directors and a recall only. A gmail-drafts case and a PayHOA broadcast kind for it are not built."
                 + _become("a plan of kind `gmail-drafts`, case `election-notice`")),
        step("8", "Acclamation notices: the initial notice and the reminder", P, S, ("2", "2.2", "7"),
             command="jason notices acclamation-initial-DATE; jason notices acclamation-reminder-DATE",
             clock=_law("CIV 5103(b)(1)", "initial notice at least 90 days before the nomination deadline", "nomination_deadline", -90),
             record="both notices sent, the reminder naming the candidates",
             why="The reminder is 'between 7 and 30 days before' the deadline (CIV 5103(b)(2)); skipped by the 'not available' path."),
        step("9", "Receive and acknowledge each nomination", P, S, ("7",), repeat=EACH,
             clock=_law("CIV 5103(c)", "acknowledge within seven business days of receiving a nomination (counted from each receipt)"),
             command="the candidate-nomination form", record="each nomination acknowledged, and each nominee qualified or disqualified with the basis and the appeal route",
             why="A disqualification only on the grounds CIV 5105(b) to (e) allow."),
        step("10", "At the nomination deadline: acclaim, or go to ballot", B, S, ("9", "2.2"), command="#/agenda",
             clock=_person_day("the nomination deadline", "nomination_deadline", 0),
             choices=(Choice("acclaim", (sid("10.1"),)), Choice("ballot", tuple(sid(n) for n in ("11", "12", "12.1", "13", "14", "15", "15.1")))),
             why="Qualified candidates are counted against the vacancies. An acclamation seats them with no ballot, so the ballot steps "
                 "are skipped; to ballot, step 11 follows."),
        step("10.1", "The board votes to consider the qualified candidates elected by acclamation", D, S, ("10",), command="#/agenda; #/decisions",
             record="the decision id, the agenda item naming each qualified candidate",
             why="'The association board votes to consider the qualified candidates elected by acclamation at a meeting ... for which the "
                 "agenda item reflects the name of each qualified candidate' (CIV 5103(e)); the run's label names no candidate."),
        step("11", "Notice before the ballots go out", P, S, ("5", "6", "9"), sop="election#4",
             command="jason notices pre-ballot-notice-DATE; jason notice-check FILE --requirement KEY",
             clock=_law("CIV 5115(b)", "notice at least 30 days before the ballots are distributed", "ballots_out", -30),
             record="the notice sent: return place and time, electronic instructions, count meeting, candidate list, quorum statement",
             why="Directors and a recall only." + _become("a plan of kind `gmail-drafts`, case `election-notice`")),
        step("12", "Ballots, two envelopes, and the election rules delivered by mail", PL, M, ("11",), plan_kind="payhoa-mailroom-send",
             repeat=EACH, command="jason mailroom --pdf FILE --units UNITS; then --send --yes --approval ID (a person, at a terminal)",
             clock=_law("CIV 5115(c)", "ballots delivered not less than 30 days prior to the deadline for voting", "voting_deadline", -30),
             why="A mailed letter cannot be recalled, so two distinct people sign the plan; the inspector delivers and the manager plans. "
                 "One per channel."),
        step("12.1", "Deliver the electronic-ballot and opt-out notices", P, M, ("11",), skip=skip, repeat=EACH,
             command="jason notices election-electronic-DATE", record="each notice sent, and its day",
             why="Only when the election rules allow electronic ballots (the answer to step 2): the electronic notice 30 days before the "
                 "election (CIV 5105(i)(3)(A)) and the opt-out notice 30 days before its deadline (5105(i)(4)). Skipped, with the reason, "
                 "when they do not."),
        step("13", "Voting period", W, JASON, ("12", "12.1"), elapsed=Elapsed.ENDS,
             clock=_person_day("the voting deadline", "voting_deadline", 0), why="The voting deadline ends the wait."),
        step("14", "Count in public", P, S, ("13",), command="#/agenda; #/room",
             clock=_law("CIV 5120(a)", "counted at a properly noticed open meeting (the count meeting)", "count_on", 0),
             record="the tabulation, or that a quorum was not present",
             why="The inspector counts; the secretary hosts the meeting. Not conducted entirely by teleconference (CIV 4926(b)). With no "
                 "quorum the materials stay in the inspector's custody."),
        step("15", "Say whether a quorum was present", B, S, ("14",), choices=(Choice("quorum", (sid("15.1"),)), Choice("no_quorum", ())),
             why="No quorum: reconvene at least 20 days later (CIV 5115(d)(2))."),
        step("15.1", "Notice the reconvened meeting", P, S, ("15",), command="jason notices reconvened-election-meeting-DATE",
             clock=_law("CIV 5115(d)(3)", "notice no less than 15 days prior to the adjourned meeting (counted from its day)"),
             record="the notice sent, and the adjourned meeting's day", why="Skipped by the 'quorum' path."),
        step("16", "Give the results to the board and the members", P, S, ("14", "15.1"), command="jason notices election-results-DATE",
             clock=_law("CIV 5120(b)", "general notice of the tabulated results within 15 days of the election", "count_on", 15),
             record="the inspector's report in the next minutes, and the general notice",
             why="'Within 15 days of the election, the board shall give general notice pursuant to Section 4045 of the tabulated results' "
                 "(CIV 5120(b))."),
        step("17", "Record the seats and terms", P, S, ("16",), sop="election#6",
             command="jason onboard --questions --group elections; jason onboard --answer ID TEXT --by NAME; --confirm; --apply",
             record="seat holders and terms, with the inspector's report as the record",
             why="A second person confirms; a seat is never recorded from a name alone. Closes the 'term ended' flag on People."),
        step("18", "Custody and the challenge period", W, S, ("16",),
             clock=_law("CIV 5145(a)", "an action within one year of the inspector's notice of the results, or when the cause accrues"),
             why="The inspector holds the election materials until the time for challenging the election has expired (CIV 5125), then "
                 "transfers them. Ends when a person notes the transfer; no date is computed here."),
    )
    phases = _phases(sid, ("set-up", "Set up", ("1", "2", "2.1", "2.2", "3", "4", "5", "6")),
                     ("nominations", "Notices and nominations", ("7", "8", "9", "10", "10.1")),
                     ("ballots", "Ballots and voting", ("11", "12", "12.1", "13")),
                     ("count", "Count and results", ("14", "15", "15.1", "16", "17", "18")))
    return Workflow(key=EL, title="An election or a member vote", family="board", subject="election", steps=steps,
                    dates=(DateSlot("nomination_deadline", "The deadline for submitting nominations", required=False),
                           DateSlot("ballots_out", "Ballots distributed"),
                           DateSlot("voting_deadline", "The deadline for voting", after="ballots_out"),
                           DateSlot("count_on", "The count meeting and election day", after="voting_deadline"),
                           DateSlot("opt_out_deadline", "The deadline to opt out of electronic ballots", required=False)),
                    phases=phases, procedure="election")


# --- hearing (2.4): built, not in BUILDERS ---------------------------------------------------------------------------

HR = "hearing"


def hearing() -> Workflow:
    """A hearing on a member's discipline or a damage charge (CIV 5855). **Not in ``BUILDERS``**: the Work backend cannot hold
    such a run (``jason.web.extra.work``: executive-session handling is not composed, so no step can be marked held and every
    run shows in full at P2). Its subject is an opaque handle (a digest), never an address or a name, and no step's words
    carry a unit, a member, or the matter. There is no SOP ``hearing`` yet (the page's gap), so no step has a ``sop``."""
    sid, step = _ids(HR)
    skip = SkipRule()
    notice_by = _law("CIV 5855(a)", "written notice to the member by", "hearing_on", -10)
    decision_by = _law("CIV 5855(f)", "decision notice within 14 days following the action", "action_on", 14)
    steps = (
        step("1", "State the matter and the authority", P, M, command="jason hearing --address ADDRESS --violation TEXT",
             record="the matter in the board's words, the discipline the documents authorize, the penalty schedule in effect on the day",
             why="A monetary penalty may not exceed the lesser of the schedule's amount in effect at the time of the violation and $100 "
                 "per violation, unless CIV 5850(d) is met in an open meeting. No schedule check is built; this is a person's statement."),
        step("2", "Compute the dates", P, M, ("1",), command="jason hearing --address ADDRESS --date DATE [--notice-on DATE]", clock=notice_by,
             record="notice by, the executive-meeting notice by, and the decision notice by",
             why="The notice is 'at least 10 days prior to the meeting' (CIV 5855(a)); an executive-session-only meeting needs two days' "
                 "notice (4920(b)(2)). A suspension notice period of 15 days is a code constant citing Corporations Code 7341, which is "
                 "not on the shelf: it is not recited and is not a clock here." + _become("the check `hearing-dates`")),
        step("3", "Agenda item in executive session", W, S, ("2",), command="#/agenda",
             why="A `board-meeting` run holds it by its 4935 subject only ('member discipline'); if the member asks, the board 'shall meet "
                 "in executive session' (CIV 5855(b), 4935(b))."),
        step("4", "Write the notice", P, M, ("2",), clock=notice_by, command="jason hearing ... --doc --yes; jason notice-check discipline-hearing",
             record="the notice Doc: date, time, place, nature, right to attend and address, executive session, cure",
             why="The words are checked against the elements; the unit and the member appear in the Doc only."
                 + _become("a plan of kind `google.doc`")),
        step("5", "Schedule the Zoom meeting", P, M, ("2",), skip=skip, command="jason hearing ... --create --yes",
             record="the meeting id and link",
             why="Skipped, with the reason, for an in-person hearing. A second person confirms." + _become("a plan of kind `zoom.hearing.create`")),
        step("6", "Save the notice email as a Gmail draft", PL, M, ("4",), plan_kind="gmail-drafts", clock=notice_by,
             command="jason approvals plan gmail-drafts --scope '{\"case\":\"hearing\",\"key\":\"ADDRESS\"}' --by NAME",
             why="Case `hearing`; the body names the unit and goes to the recipient a person chooses. jason never sends."),
        step("7", "Deliver the notice and record the day", P, M, ("6",), clock=notice_by,
             command="jason hearing ... --notice-on DATE", record="the delivery day and the proof",
             why="'By either personal delivery or individual delivery pursuant to Section 4040' (CIV 5855(a)); the day is the person's "
                 "statement, not read from the ledger."),
        step("8", "Read delivery", P, M, ("7",), clock=notice_by, command="jason hearing --list; jason notices discipline-hearing-DATE --sync",
             record="the ledger's strength, or 'no delivery recorded'",
             why="A notice delivered late moves the hearing: a new date and a new notice. Whether a resend cures is a question for the board "
                 "or counsel." + _become("the check `hearing-delivery-read`")),
        step("9", "The cure window", W, S, ("7",), command="none yet",
             clock=_law("CIV 5855(c)", "the board shall not impose discipline if the member cures or commits to cure"),
             why="If the member cures, or commits to cure when the cure takes longer than the notice period, the run is cancelled with the "
                 "reason 'no discipline' and the record. Ends when a person notes the window's end."),
        step("10", "Hold the hearing", P, S, ("8", "3"), command="#/room (the executive record)",
             clock=_person_day("the hearing day", "hearing_on", 0), record="the executive-session room record, and the member's attendance",
             why="The chair presides and the secretary keeps the record; a step has one role, so the secretary records it."),
        step("11", "Record the board's findings", D, S, ("10",), command="#/room; #/decisions; #/hearings", record="the decision id",
             why="Recorded by the secretary; read in the private view only. The hearing row and the decisions store are two stores today "
                 "and are shown as a difference, never reconciled."),
        step("12", "Agreement or no agreement", B, S, ("11",), choices=(Choice("agreement", ()), Choice("no_agreement", ())),
             why="'If the board and the member are in agreement after the meeting, the board shall draft a written resolution' (CIV 5855(e)); "
                 "otherwise internal dispute resolution is offered (5855(d))."),
        step("13", "Write and deliver the decision", P, M, ("11",), clock=decision_by, command="jason letter --template decision-notice --yes",
             record="the decision notice Doc, and the delivery day",
             why="Within 14 days following the action (CIV 5855(f); 15 days before 2025-06-30)."
                 + _become("a plan of kind `google.doc` and a `gmail-drafts` case `decision-notice`")),
        step("14", "Read delivery of the decision", W, S, ("13",), clock=decision_by, command="jason notices discipline-decision-DATE --sync",
             why="Ends when a person notes the delivery."),
        step("15", "State that every requirement was met", P, S, ("8", "9", "13"),
             record="each requirement of CIV 5855 shown met or not, on record",
             why="'A disciplinary action ... shall not be effective against a member unless the board fulfills the requirements of this "
                 "section' (CIV 5855(g)); jason states, and the board and counsel decide." + _become("the check `hearing-requirements-met`")),
        step("16", "Note the matter generally in the next open minutes", P, S, ("10",), command="jason board --minutes DATE",
             record="the 4935 subject noted in the open minutes",
             why="Only by its 4935 subject (CIV 4935(e)). Closes the run." + _become("the check `hearing-minutes-note`")),
    )
    phases = _phases(sid, ("matter", "The matter and the notice", ("1", "2", "3", "4", "5", "6", "7", "8", "9")),
                     ("hearing", "The hearing", ("10", "11", "12")),
                     ("decision", "The decision", ("13", "14", "15", "16")))
    return Workflow(key=HR, title="A hearing", family="board", subject="hearing", steps=steps,
                    dates=(DateSlot("hearing_on", "The hearing day"),
                           DateSlot("action_on", "The day the board acts", required=False, after="hearing_on")),
                    phases=phases, procedure="")


# --- law-review (2.5) ------------------------------------------------------------------------------------------------

LR = "law-review"


def law_review() -> Workflow:
    """The year's changes in the law against the written provisions (SOP ``law-review``). The subject is a year. A lead
    is read beside the statute before it is a conflict row; jason notes a conflict and never resolves one."""
    sid, step = _ids(LR)
    skip = SkipRule()
    steps = (
        step("1", "Refresh the law and the change history", P, M, sop="law-review#1", command="jason export-authorities; jason law-history --export",
             clock=_policy("each January, and when a law takes effect mid-year"), record="the export date, and the year's chaptered bills",
             why="No statute sets the review; the board adopts it as a duty assignment." + _become("the job `law-export`")),
        step("2", "Set aside the readings whose words changed", P, M, ("1",), sop="law-review#2", command="jason readings --stale",
             record="the stale readings, each redone or confirmed", why="Each is redone or confirmed by the board or counsel before it is used."
             + _become("the check `readings-stale`")),
        step("3", "Keep the earlier versions of the changed sections", P, M, ("1",), sop="law-review#3",
             command="jason law-history --versions --since YEAR --shelf", record="the versions kept, with the range in force; shelf differs: 0",
             why="A miss is a citation to correct." + _become("the job `law-versions`")),
        step("4", "Check the shelf holds the sections the documents cite", P, M, ("1",), sop="law-review#4", repeat=EACH,
             command="jason reference --cites WORK; jason ingest SOURCE", record="each cited-not-exported section added or noted",
             why="A person adds a row for each gap." + _become("the check `shelf-cites`")),
        step("5", "Refresh the documents' outlines", P, M, ("1",), sop="law-review#5", command="jason outlines --fetch",
             record="the outlines current, with the written dates pinned", why="A document added or adopted since is a citable document."
             + _become("the job `outlines-fetch`")),
        step("6", "List the leads", P, M, ("3", "5"), sop="law-review#6", command="jason conflicts --leads --since YEAR-01-01",
             record="the leads: each change since a document was written, with the citing or subject-matching section",
             why="A document with no written date counts every change." + _become("the job `conflict-leads`")),
        step("7", "Read each lead beside the statute", P, M, ("6",), sop="law-review#7", repeat=EACH,
             command="jason law-history --section NNNN", record="no conflict, or a Conflict row: the part that yields, how it is applied meanwhile, plain or for counsel",
             why="'To the extent of any conflict between the governing documents and the law, the law shall prevail' (CIV 4205(a)); the "
                 "statute is recited first and the reading labeled. The row is a profile edit a person commits; where the extent is "
                 "unclear it is recorded as for counsel and the course lawful under either reading is followed."),
        step("8", "Check jason's own rules and pages", P, A, ("1",), sop="law-review#8", command="jason law-history --sweep --since YEAR",
             record="law-sweep.md read", why="A correction is a code change." + _become("the job `law-sweep`")),
        step("9", "Survey the citations and the stale records", P, M, ("5",), sop="law-review#9", repeat=EACH,
             command="jason cite --survey; jason cite --stale; jason cite --renumbered; jason cite --migrate-ids",
             record="the misses by reason, and the stale records re-keyed",
             why="A row where more than one section answers is picked by a person." + _become("the job `cite-survey`")),
        step("10", "Check the people-task rules that retire a duty", P, M, ("1",), sop="law-review#10", repeat=EACH,
             command="jason schedule --people --all", record="each retire reason still true",
             why="A repealed filing or an exemption retires a duty only on its source." + _become("the check `retire-reasons`")),
        step("11", "Find the stale copies of the changed sections", P, M, ("1",), sop="law-review#11",
             command="jason section-refs --refresh --scan --guide; jason section-refs --patch", record="the copies scanned and the patch proposed",
             why="A patch is made on a person's word." + _become("the job `section-refs-scan` and a plan of kind `local.section-refs.apply`")),
        step("12", "Put each new conflict before the board", D, S, ("7",), sop="law-review#12", repeat=EACH,
             command="jason board --set ITEM ...; {REPORT:conflicts}", record="the decision id",
             why="The board amends (a `rule-change` run), asks counsel, or leaves it; jason notes a conflict and never resolves one."),
        step("13", "Correct former cross-references by resolution", D, S, ("7",), skip=skip, command="a board resolution",
             record="the resolution showing the correction",
             why="'The board may amend the governing documents, solely to correct the cross-reference, by adopting a board resolution that "
                 "shows the correction' (CIV 4235(a)); optional, skipped with the reason."),
        step("14", "Lessons and procedure", P, M, tuple(str(i) for i in range(1, 13)), skip=skip, command="jason lessons --area governing",
             record="the lessons added, and the procedure updated", why="Skipped, with the reason, when nothing was learned."),
    )
    phases = _phases(sid, ("refresh", "Refresh", ("1", "2", "3", "4", "5")),
                     ("read", "Read the leads", ("6", "7", "8", "9", "10", "11")),
                     ("board", "The board", ("12", "13", "14")))
    return Workflow(key=LR, title="The year's law review", family="board", subject="year", steps=steps, dates=(), phases=phases,
                    procedure="law-review")


# --- duty-schedule (2.6) ---------------------------------------------------------------------------------------------

DS = "duty-schedule"


def duty_schedule() -> Workflow:
    """Every duty owned, every clock set, each occurrence done (SOP ``duty-schedule``). The subject is a month (YYYY-MM)."""
    sid, step = _ids(DS)
    steps = (
        step("1", "Read what falls due, by role", P, M, sop="duty-schedule#1", repeat=EACH, command="jason schedule --days 45",
             clock=_policy("each month before the board meeting", "board_meeting_on", 0), record="the occurrences read: done, overdue, due soon, upcoming",
             why="Each duty keeps its own clock, the law's or the documents'." + _become("the check `schedule-due`")),
        step("2", "Read people's own tasks and events", P, M, ("1",), sop="duty-schedule#2", command="jason schedule --read-google --people",
             record="the classes: covered, untracked recurring, one-off; stale tasks",
             why="A task proposed to close is closed by its owner in Google." + _become("the job `schedule-read-google`")),
        step("3", "Find the evidence on disk", P, M, ("1",), sop="duty-schedule#3", command="jason schedule-evidence --since DATE --all",
             record="the proposals: proposed, partial, contrary, none",
             why="'Contrary' goes to the board; nothing is recorded done on it." + _become("the job `schedule-evidence`")),
        step("4", "Record each occurrence done", P, ANYONE, ("3",), sop="duty-schedule#4", repeat=EACH,
             command="jason schedule --done KEY DUE --by NAME --evidence TEXT",
             record="who did it, when, and the evidence",
             why="By the assignment's role (any named person; the command refuses without a name and evidence)."),
        step("5", "Is a life-safety inspection overdue?", B, M, ("1",), sop="duty-schedule#5", command="jason inspections",
             choices=(Choice("overdue", ()), Choice("none", (sid("5.1"), sid("5.2")))),
             why="The inspection's own period decides."),
        step("5.1", "Ask the servicer for the reports and a proposal (Gmail draft)", PL, M, ("5",), sop="duty-schedule#5", plan_kind="gmail-drafts",
             repeat=EACH, command="jason approvals plan gmail-drafts --scope '{\"case\":\"proposal-request\",\"key\":\"SYSTEM\"}' --by NAME",
             why="Case `proposal-request`; read the vendor's waiting mail and the agreement first. The recipient is a person's choice."),
        step("5.2", "The board decides on the vendor's proposal", D, S, ("5.1",), sop="duty-schedule#5", repeat=EACH, command="#/decisions",
             record="the decision id", why="Accepting a proposal is the board's decision."),
        step("6", "Publish the schedule", P, M, ("1",), sop="duty-schedule#6", command="jason schedule --tasks --calendar; then --yes",
             record="the dated occurrences on the board calendar, and the open ones on each role's Tasks list",
             why="A check-off in Google is weaker evidence; record the minutes' item too."
                 + _become("a plan of kind `google.calendar` and `google.tasks`")),
        step("7", "Check coverage", P, M, ("1",), sop="duty-schedule#7", command="jason duties --documents KEY; jason schedule --coverage",
             record="duties with no owner, and duties on a clock nothing schedules",
             why="A non-empty list blocks the board's adoption (step 8)." + _become("the check `schedule-coverage`")),
        step("8", "The board adopts the assignments", D, S, ("7",), sop="duty-schedule#8", repeat=EACH, command="{REPORT:schedule}",
             record="each assignment adopted, changed, declined, or not applicable, with the minutes",
             why="Until adopted, an assignment reads 'proposed, not adopted'."),
    )
    phases = _phases(sid, ("read", "Read", ("1", "2", "3")), ("record", "Record", ("4", "5", "5.1", "5.2")),
                     ("publish", "Publish and adopt", ("6", "7", "8")))
    return Workflow(key=DS, title="The duty schedule", family="board", subject="period", steps=steps,
                    dates=(DateSlot("board_meeting_on", "The board meeting the month's read feeds", required=False),),
                    phases=phases, procedure="duty-schedule")


DD = "document-duties"


def document_duties() -> Workflow:
    """The duties a document states, read again when it is outlined, amended, or replaced (SOP ``document-duties``). The
    subject is a document key. A 'may' is a power, not a duty; a conflict between a 'shall' and a 'may' is a finding for the
    conflict register."""
    sid, step = _ids(DD)
    steps = (
        step("1", "Read the document with the phrase grammar", P, M, sop="document-duties#1", command="jason duties --documents --read",
             record="the readings kept", why="Reviews are kept." + _become("the job `duties-read`")),
        step("2", "Fill the bearers the words leave out", P, M, ("1",), sop="document-duties#2", command="jason duties --documents --fill-bearers",
             record="the bearers filled", why="A local model runs only after the GPU preflight and holds the GPU lock; a failed preflight "
                                              "stops the step." + _become("the job `duties-fill-bearers`")),
        step("3", "Review the timed untracked duties, the notice duties, and owners' prohibitions", P, M, ("2",), sop="document-duties#3",
             repeat=EACH, command="jason duties --documents --review ID --status confirmed",
             record="each reading confirmed, corrected, or rejected against the sentence"),
        step("4", "Say what tracks each timed duty, or propose the recurring-deadline row", P, M, ("3",), sop="document-duties#4",
             repeat=EACH, command="jason duties --documents --tracked-by WHAT", record="what tracks it, or the row proposed",
             why="Duties to give notice go to the notice catalog."),
        step("5", "Score the grammar and the model again", P, A, ("1",), sop="document-duties#5", skip=SkipRule(),
             command="python scripts/eval_duties.py", record="the trial recorded",
             why="After a change to the grammar or the model; skipped, with the reason, when neither changed."
                 + _become("the job `duties-score`")),
    )
    phases = _phases(sid, ("read", "Read", ("1", "2")), ("review", "Review", ("3", "4", "5")))
    return Workflow(key=DD, title="The duties a document states", family="board", subject="document", steps=steps, dates=(),
                    phases=phases, procedure="document-duties")


# --- owners-manual (2.7) ---------------------------------------------------------------------------------------------

OM = "owners-manual"


def owners_manual() -> Workflow:
    """Keep the owner's manual and the Rules document generated and citable (SOP ``owners-manual``; ``rule-history`` runs
    inside it). The subject is a revision of the manual. Nothing is written to Drive without a recorded approval, and a
    draft rules document is never filed where a folder syncs to a public list."""
    sid, step = _ids(OM)
    steps = (
        step("1", "Refresh the outlines and the copies scan", P, M, sop="owners-manual#1", command="jason outlines --fetch; jason section-refs --scan",
             record="the outlines and copies.json current",
             why="Whenever a rule changes or a copied document is amended." + _become("the jobs `outlines-fetch` and `section-refs-scan`")),
        step("2", "Read the versions and the adoption history of the Doc", P, M, ("1",), sop="rule-history#1",
             command="jason revisions KEY --fetch --versions", record="the revisions kept, and pending suggestions listed",
             why="'No adoption found' is a finding, never proof none happened." + _become("the job `revisions-fetch`")),
        step("3", "Check the headings against the PDF", P, M, ("1",), sop="owners-manual#2", skip=SkipRule((M,)),
             command="python scripts/structure_fuzz.py gold ...", record="every numbered capital line a styled heading, or a person says it is not",
             why="Skipped, with the reason, if no template is built." + _become("the check `manual-headings`")),
        step("4", "Classify each section and answer the questions", P, M, ("1",), sop="owners-manual#3", repeat=EACH,
             command="jason manual --classify --asks; jason intake --answer ID TEXT --by NAME",
             record="classification.json, and the asks answered", why="Each unclear section is a question to a person."
             + _become("the job `manual-classify`")),
        step("5", "Check the concordance", P, M, ("4",), sop="owners-manual#4", command="jason manual --concordance",
             record="zero unresolved citations", why="A citation unresolved blocks the render." + _become("the check `manual-concordance`")),
        step("6", "Check that the template equals the manual", P, M, ("4",), sop="owners-manual#5", command="jason document-template owners-manual",
             record="identical: yes; 0 unlabeled pieces", why="After any base or block change." + _become("the check `manual-template-equal`")),
        step("7", "Render the rules and the manual", P, M, ("5", "6"), sop="owners-manual#6",
             command="jason manual --render; jason manual --render --current",
             record="rules-and-regulations.md, owners-manual.md, owners-manual.diff; 0 unlabeled differences",
             why="The rules print the last adopted words; a render that leaves an unlabeled difference fails and shows the diff."
                 + _become("the job `manual-render`")),
        step("8", "Read the plan for the Docs", P, M, ("7",), sop="owners-manual#7",
             command="jason document-template rules-and-regulations; jason document-template --doc plan; then --doc create --yes",
             record="the plan read: folder, styles, link",
             why="Nothing is written to Drive without a recorded approval; a draft rules document is never filed where a folder syncs to a "
                 "public list." + _become("a plan of kind `google.doc`")),
        step("9", "Does the extraction need the CIV 4360 notice?", D, S, ("7",), sop="owners-manual#9", command="jason board --set ITEM ...",
             record="the decision id, with counsel's reading first if the board prefers the other reading",
             why="Two readings remain, and the lawful course under either is to notice the extraction under 4360(a); the board decides. "
                 "Opens a `rule-change` run; a declined notice is a written finding and the extraction stays unpublished."),
        step("10", "Refetch the Doc's links before publishing", P, M, ("8",), sop="owners-manual#8", command="jason outlines --fetch",
             record="the chips current", why="Once, just before anything is published." + _become("the job `outlines-fetch`")),
        step("11", "After adoption: the citable document, the aliases, and a rerun", P, M, ("9",), sop="owners-manual#10",
             record="the rules document made a citable document and the rules book's source",
             why="A profile edit a person commits; a `reopened` event on steps 1 to 7 runs them again."),
    )
    phases = _phases(sid, ("prepare", "Prepare", ("1", "2", "3", "4")), ("render", "Check and render", ("5", "6", "7", "8")),
                     ("publish", "Decide and publish", ("9", "10", "11")))
    return Workflow(key=OM, title="The owner's manual", family="board", subject="revision", steps=steps, dates=(), phases=phases,
                    procedure="owners-manual")


BUILDERS: tuple[Callable[[], Workflow], ...] = (board_meeting, rule_change, election, law_review, duty_schedule, document_duties,
                                                owners_manual)
"""What ``register_general`` registers for this family. ``hearing`` is built by ``hearing()`` and left out: the Work backend
cannot hold an executive-session run (``jason.web.extra.work``: 'not composed')."""

LEFT_OUT: tuple[Callable[[], Workflow], ...] = (hearing,)

__all__ = ["BUILDERS", "LEFT_OUT", "WANTED", "board_meeting", "document_duties", "duty_schedule", "election", "hearing",
           "law_review", "owners_manual", "rule_change"]
