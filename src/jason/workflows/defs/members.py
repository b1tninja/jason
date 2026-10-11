"""The members' family of general workflow definitions (docs/workflows/members-cycles.md, sections 2.2 to 2.6).

``owner-info-cycle`` (section 2.1) is built in ``jason.workflows.definitions_general``; this module builds the rest:
``notice-delivery``, ``mailroom-letter``, ``respond-sweep``, ``respond-request``, ``respond-policy``, ``owner-document``,
``form-campaign``, and ``form-library-review``. ``BUILDERS`` is what ``defs.all_builders`` collects.

Pure data. It imports only the engine's types, ``named_check``, and the standard library, and it adds nothing to
``readers.CHECKS`` or ``readers.JOBS``. A step is the kind the page's table gives it only when its read, job, or approvals
kind already exists (the reads written so far, among them ``clock-authority-recited``, ``references-fill``, ``notice-elements``,
``kept-text-unchanged`` and ``form-stale``, are in ``jason.workflows.checks.members``):

- a ``plan`` step names a registered approvals kind (``owner-info-tags``, ``payhoa-mailroom-send``);
- a ``job`` step names a registered job, and a ``check`` step a registered read (``outstanding-read``, or one of the members'
  reads in ``jason.workflows.checks.members``, which ``definitions_general.register_general`` loads);
- anything else is a ``person`` step that shows the command, and its ``why`` says what it will become. ``BECOMES`` maps such a
  step to the read, job, or kind it waits for; ``WANTED`` lists them once, for the report.

Step ids are ``<key>.<n>`` with n the table's number (RQ-10 is ``respond-request.10``; there is no RQ-09). The response-intake
group (IN) is not expanded step by step, as in ``owner-info-cycle``: ``form-campaign.6`` stands for IN-01 to IN-05, IN-08, and
IN-09, ``form-campaign.6.6`` is IN-06, and ``form-campaign.6.7`` is IN-07.

Law clocks are only on statutes the authorities shelf holds. A clock whose basis depends on the request or the notice (the
requirement's own row, a records request's kind) carries the section it cites, or the word ``documents`` with a label, and no
date the engine could compute wrongly. The membership-list clock (CIV 5210(b)(6) with Corp. Code 8330) stays out until counsel
reads it: ``respond-request.13`` says so.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Mapping

from jason.workflows.readers import named_check
from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, DateSlot, Phase, Repeat, Role, SkipRule, StepDef, StepKind, Workflow,
)

FAMILY = "members"

P, C, PL, D, W, B = (StepKind.PERSON, StepKind.CHECK, StepKind.PLAN, StepKind.DECISION, StepKind.WAIT, StepKind.BRANCH)
M, S, A, JASON, ANY = Role.MANAGER, Role.SECRETARY, Role.ADMINISTRATOR, Role.JASON, Role.ANYONE

_ARTICLE = {"check": "a check", "job": "a job", "kind": "a plan under the approvals kind", "case": "a case"}
_BECOMES = re.compile(r"This becomes (?P<article>a check|a job|a plan under the approvals kind|a case) (?P<name>\S+) once built\.")


def _maker(key: str) -> Callable[..., StepDef]:
    """``step(n, title, kind, role, needs, ...)`` for definition ``key``; ``becomes="check NAME"`` adds the sentence to a person
    step's ``why`` that says what it waits to be (``BECOMES`` reads it back; nothing is kept at module level)."""

    def step(n: str, title: str, kind: StepKind, role: Role, needs: tuple[str, ...] = (), *, becomes: str = "",
             why: str = "", **more: Any) -> StepDef:
        sid = f"{key}.{n}"
        if becomes:
            word, _, name = becomes.partition(" ")
            why = (why + " " if why else "") + f"This becomes {_ARTICLE[word]} {name} once built."
        return StepDef(sid, title, kind, role=role, needs=tuple(f"{key}.{x}" for x in needs), why=why, **more)

    return step


def _phases(key: str, *groups: tuple[str, str, tuple[str, ...]]) -> tuple[Phase, ...]:
    return tuple(Phase(k, t, tuple(f"{key}.{n}" for n in ns)) for k, t, ns in groups)


by_manager = SkipRule((M,))


# --- notice-delivery (section 2.2) ----------------------------------------------------------------------------------

def notice_delivery() -> Workflow:
    key = "notice-delivery"
    step = _maker(key)
    last_day = ClockDef(ClockBasis.DOCUMENTS, "last_day_to_send", 0,
                        label="the last day to send: the law's, or the documents' stricter period, from the catalog row")
    steps = (
        step("1", "Read the notice's requirement before it goes: recipients, method, the clock with the documents' stricter period, content, evidence",
             C, JASON, check=named_check("notice-requirement-read"), command="jason notices REQUIREMENT --catalog", sop=f"{key}#1",
             clock=ClockDef(ClockBasis.DOCUMENTS, label="law and the documents, from the catalog row"),
             why="Name every batch with the requirement's key and the date (lesson notice-key-names-requirement)."),
        step("2", "Plan the recipients", P, M, ("1",), command="jason delivery --notice RULE --ids data/notices/KEY/recipients.json",
             becomes="job notice-recipients-plan", record="the recipients plan written: ids and counts, no names",
             why="The plan names ids and counts, never names."),
        step("3", "Wait for the send", W, M, ("1",), clock=last_day,
             why="Ends when a batch or a mailing is made under the key and the text as sent is kept; a person notes the arrival."),
        step("4", "Read the delivery", P, M, ("3",), command='jason notices KEY --sync, or --sync --subject "SUBJECT" --since DATE',
             sop=f"{key}#2", becomes="job notices-sync-any-key", record="the ledger read: how many attempts, and their outcomes",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, "sent_on", 1, label="the day after the send (proposed policy)"),
             why="A bounced message is silent until synced (lesson bounces-are-silent). The registered job reads only keys that begin "
                 "with the owner-information prefix, so a general notice is read by a person's command."),
        step("5", "A general notice: say where it was also posted, if the annual policy statement designates a place; or record that "
                  "it was individual delivery", P, S, ("4",),
             command='jason notices KEY --mark-general --posted "WHERE, 2099-10-02" --by NAME', sop=f"{key}#3",
             record='where and which day it was posted, or "none: individual delivery" (a posting with no day meets no clock)',
             clock=ClockDef(ClockBasis.LAW, cite="CIV 4045(a)(3)", label="a general notice posted where the annual policy statement designates"),
             why="Only then is a failed message information and not a resend (CIV 4045(b) makes individual delivery the member's choice)."),
        step("6", "Wait 24 hours, then read the delivery again", W, M, ("4",), command="jason notices KEY --sync", sop=f"{key}#2",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="24 hours (the vendor fails a message with no delivery event; not a clock of the law)"),
             why="A message with no delivery event after 24 hours reads as unknown; a person notes the arrival after the second sync."),
        step("7", "For each member owed a follow-up, send it", P, M, ("6",), repeat=Repeat.PER_ITEM, skip=by_manager, sop=f"{key}#4",
             command="jason owner-info --mail-batch --only UNIT --resend --yes --confirmed-by NAME, or jason mailroom",
             becomes="kind payhoa-owner-info-mail-batch", record="the resend's batch key, and the second person who confirmed it",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, cite="CIV 4041(e)",
                            label="the law requires the resend, not a number of days (proposed: 3 days after the outcome was read)"),
             why="Skipped, with the reason, when another delivery reached the member or the notice was posted where designated "
                 "(a failed message is then information, unless the member asked for individual delivery, CIV 4045(b)). The resend "
                 "key starts with the notice's key, so the next sync reads it; a test batch is never part of the notice. A letter "
                 "sent by the Mailroom is its own mailroom-letter run."),
        step("8", "Ask each member whose address failed for a working one; record it", P, M, ("7",), repeat=Repeat.PER_ITEM, sop=f"{key}#5",
             record="the answer recorded, or that none came",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="7 days after the outcome was read (proposed policy)"),
             why="No message kind exists to ask for an address; a person asks and enters the answer."),
        step("9", "A week on, read the letters' tracking: never mailed, returned, forwarded", W, M, ("7",), command="jason notices KEY --sync",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="a week (proposed policy)"),
             why="A person notes the arrival after the sync."),
        step("10", "Sync until nothing is owed", C, JASON, ("9",), check=named_check("notice-owed-zero"), command="jason notices KEY",
             sop=f"{key}#6", why="The ledger is the record of each delivery."),
        step("11", "Put the proof of notice together", C, JASON, ("10",), check=named_check("notice-proof"), sop=f"{key}#7",
             command="jason notices KEY --proof --event DATE [--general --posted DATE] [--have text_as_sent,...]",
             clock=ClockDef(ClockBasis.DOCUMENTS, label="law and the documents, from the requirement's row (its windows)"),
             why="Counsel reads whether the proof is sufficient; the evidence items are the requirement's."),
        step("12", "Members reached only after the last day, or not at all", D, S, ("11",), skip=SkipRule((S,)),
             record="the decision record (a new date and a new notice is the usual cure)",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="the Act is silent beyond delivery; the practice in the notices guide is a policy for the board to consider"),
             why="Only on a finding: skipped, with the reason, when every member was reached in time. Counsel reads sufficiency; "
                 "the board adopts nothing here that is not written."),
        step("13", "Keep the text and read the record", C, JASON, ("11",), check=named_check("notice-kept-text"),
             command="jason cite jason://notice/KEY", sop=f"{key}#8", why="A file alone is never proof: the strength reads from the ledger."),
    )
    phases = _phases(key, ("before", "Before it goes", ("1", "2", "3")), ("read", "Read the delivery", ("4", "5", "6")),
                     ("follow", "Follow up", ("7", "8", "9", "10")), ("prove", "Prove it", ("11", "12", "13")))
    return Workflow(key=key, title="Notice delivery: know each member was reached", family=FAMILY, subject="notice", steps=steps,
                    dates=(DateSlot("sent_on", "The notice is sent", required=False),
                           DateSlot("last_day_to_send", "The last day to send", required=False),
                           DateSlot("event_on", "The event the notice is for", required=False)),
                    phases=phases, procedure=key)


# --- mailroom-letter (section 2.3) ----------------------------------------------------------------------------------

def mailroom_letter() -> Workflow:
    key = "mailroom-letter"
    step = _maker(key)
    steps = (
        step("1", "Keep the PDF within the page limit", C, JASON, check=named_check("mailroom-pages"), command="jason mailroom --prices",
             sop=f"{key}#1", why="Four pages at most unless a person chooses otherwise; a sixth billed page adds 225 cents a letter. "
                 "The vendor's pricing, not the law."),
        step("2", "Preview the recipients and the cost", P, M, ("1",), command="jason mailroom --pdf FILE --units UNITS", sop=f"{key}#3",
             becomes="job mailroom-preview", record="the recipients (by unit), the price a letter, the total in cents, and the preview's fingerprint",
             why="Choose the mail class first: first class or better for an individual notice (CIV 4040(a)(2)). The preview saves a "
                 "record with no names or addresses; again if the PDF changes."),
        step("3", "Test every link and QR code as its reader would", P, M, ("2",), repeat=Repeat.PER_ITEM, sop=f"{key}#4",
             record="each link opened, with the date", why="Lessons test-as-an-owner, form-link-needs-unit, letter-link-per-unit."),
        step("4", "Mail it, only on a person's word", PL, M, ("2", "3"), plan_kind="payhoa-mailroom-send", sop=f"{key}#6",
             command="jason mailroom --pdf FILE --units UNITS --send --yes [--notice KEY --by NAME]",
             clock=ClockDef(ClockBasis.DOCUMENTS, "last_day_to_send", 0,
                            label="the notice's last day to send, if there is a notice (law or documents, from the requirement's row)"),
             why="This mails N letters and a letter cannot be recalled. Two distinct people sign the saved preview's fingerprint, "
                 "and it is applied only by the command, at a terminal. jason never starts this step."),
        step("5", "If something is wrong, cancel at once", W, M, ("4",), command="jason mailroom --cancel LETTER_ID --yes", sop=f"{key}#7",
             becomes="kind payhoa-mailroom-cancel",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="the cancel window is minutes (lesson letters-cannot-be-recalled)"),
             why="Ends when a person notes the letter cancelled or the window passed; after that the correction is a new notice."),
        step("6", "Read the batch back", C, JASON, ("4",), check=named_check("mailroom-batch-read"), command="jason mailroom --batch ID",
             why="A letter that is not processing is a finding, not a retry."),
        step("7", "A week on, read the tracking: never mailed, returned, forwarded", W, M, ("6",), sop=f"{key}#8",
             command="jason notices KEY --sync, else jason mailroom --letters KIND and --events COMMUNICATION",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="a week (proposed policy)"),
             why="With a notice key the findings go to its delivery run; ends when a person notes the arrival."),
    )
    phases = _phases(key, ("prepare", "Prepare", ("1", "2", "3")), ("mail", "Mail", ("4", "5", "6")), ("track", "Track", ("7",)))
    return Workflow(key=key, title="Mail a letter through the Mailroom", family=FAMILY, subject="letter", steps=steps,
                    dates=(DateSlot("last_day_to_send", "The notice's last day to send", required=False),),
                    phases=phases, procedure=key)


# --- the respond family (section 2.4) -------------------------------------------------------------------------------

def respond_sweep() -> Workflow:
    key = "respond-sweep"
    step = _maker(key)
    steps = (
        step("1", "Refresh the requests", P, M, command="jason sync-catalog", sop="respond#1", becomes="job catalog-sync",
             repeat=Repeat.PER_PERIOD, record="the catalog refreshed, with its age",
             why="Weekly, and the day before each board meeting."),
        step("2", "Read the open requests with their clocks; open one respond-request for each, by request id", C, JASON, ("1",),
             check=named_check("requests-read"), command="jason respond", sop="respond#1", repeat=Repeat.PER_PERIOD,
             why="Anything overdue or due soon is named; a request read as other has its kind decided in its own run."),
        step("3", "Join the emailed requests PayHOA lacks", P, M, ("2",), command="jason request-links, then --create THREAD --yes",
             sop="respond#4", becomes="kind payhoa-request-create", repeat=Repeat.PER_ITEM, skip=by_manager,
             record="the request created and linked",
             why="The owner sees the new request, so a draft is entered only on a person's word. Skipped, with the reason, when no emailed request lacks one."),
        step("4", "Put on the agenda what the board decides", P, M, ("2",), command="jason board", skip=by_manager,
             record="the board items made (architectural, solar, EV charger, rental, and variance requests)",
             why="Before each meeting; skipped, with the reason, when nothing is the board's this week."),
        step("5", "Monthly, read the answers on time, by kind, for the board", C, JASON, ("1",), check=named_check("answers-on-time"),
             command="jason respond --all", sop="respond#6", repeat=Repeat.PER_PERIOD, skip=by_manager,
             why="Monthly, so a weekly sweep skips it with the reason in the other weeks."),
        step("6", "Label new requests' kinds in the gold set; measure before changing a kind rule", P, A, ("2",),
             command="jason respond --measure", sop="respond#7", skip=SkipRule((A, M)),
             record="no kind's precision or recall falls", why="Per rule change; skipped, with the reason, when no kind rule changed."),
    )
    phases = _phases(key, ("read", "Read the requests", ("1", "2")), ("act", "Act", ("3", "4")), ("measure", "Measure", ("5", "6")))
    return Workflow(key=key, title="The weekly sweep of member requests", family=FAMILY, subject="period", steps=steps,
                    phases=phases, procedure="respond")


def respond_request() -> Workflow:
    key = "respond-request"
    step = _maker(key)
    ack = ClockDef(ClockBasis.PROPOSED_POLICY,
                   label="acknowledge in the days the policy gives (proposed until adopted); no statute read here sets one")
    def paths(*ns: str) -> tuple[str, ...]:
        return tuple(f"{key}.{n}" for n in ns)

    records, resale, board, staff = paths("10", "11", "12", "13"), paths("14"), paths("15", "16", "17", "18", "19"), paths("20")
    steps = (
        step("1", "Classify: kind, clock row, owner, due day", C, JASON, check=named_check("request-classified"), command="jason respond",
             sop="respond#1", clock=ClockDef(ClockBasis.DOCUMENTS, label="per the clock row: the statute's, the documents', or a policy's"),
             why="A made-up due day is never shown."),
        step("2", "A kind read as other: decide its kind", P, M, ("1",), skip=by_manager, record="the kind, with a reason",
             why="Skipped unless the kind was read as other; a kind read wrongly is reopened here and the clock is recomputed."),
        step("3", "Read the clock's authority: the words first, then any reading, labeled", C, JASON, ("1",),
             check=named_check("clock-authority-recited"), command="jason cite AUTHORITY",
             why="The read finds the authority's words on disk (a statute on the shelf, a clause in the document as kept). Recite the "
                 "operative words with their citation before any reading, and label whose reading it is."),
        step("4", "No rule sets a clock for this kind", D, S, ("3",), skip=SkipRule((S, M)), record="the board item that holds the question",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, cite="CIV 4350",
                            label="the law and the documents are silent: a written policy is proposed for the board"),
             why="Skipped, with the reason, unless the authority read found none. jason proposes a policy; the board adopts it."),
        step("5", "Read where the answer is written: passages, library files, precedents", P, M, ("1",),
             command="jason respond --sources", sop="respond#2", becomes="job respond-sources", record="the leads read",
             why="Each line is a lead to read, not a ruling."),
        step("6", "Draft the acknowledgment", P, M, ("1",), command="jason respond --draft ID; jason respond --draft email:ID --gmail --yes",
             sop="respond#3", becomes="case gmail-drafts/acknowledgment", spawns="owner-document", skip=by_manager, clock=ack,
             record="the draft made (a comment for a PayHOA request, a draft in the thread for an emailed one)",
             why="A date only where the law or the documents set one. Skipped, with the reason, when the first admin comment is already there."),
        step("7", "Send it", P, M, ("6",), command='jason request-comment ID "TEXT"', sop="respond#3", clock=ack,
             record="where it was sent (a comment, or the outgoing message)",
             why="A comment until jason request-comment has a dry run and a gate; a Gmail draft is sent from Gmail by a person."),
        step("8", "Branch by kind", B, M, ("2",),
             choices=(Choice("records", records), Choice("resale", resale), Choice("board", board), Choice("staff", staff),
                      Choice("executive-session", ())),
             why="A person chooses until jason can read the kind. Executive-session kinds (payment plan, hearing request, internal "
                 "dispute, ADR) link to their own families and are counted without names."),
        step("10", "Records: open the request in the records store", P, M, ("8",),
             command="the records-requests form (POST /api/write/records-requests/new); no command verified",
             record="the request id in the store: day received, unit, how, record kinds, the member's purpose in their words, years",
             clock=ClockDef(ClockBasis.LAW, cite="CIV 5210(b)", label="inspection or copies of the association's records"),
             why="The stages are computed from the day received."),
        step("11", "Records: decide the purpose (membership list only) and what is withheld or redacted, with the legal basis", P, M, ("10",),
             command="POST /api/write/records-requests/<id>", repeat=Repeat.PER_ITEM,
             record="withheld or redacted records with the legal basis, or 'nothing withheld'",
             clock=ClockDef(ClockBasis.LAW, cite="CIV 5215(d)", label="a written explanation of the legal basis, if the member asks"),
             why="Counsel where needed; jason never decides what is withheld and does not score a purpose (CIV 5225)."),
        step("12", "Records: tell the member the copying cost and wait for agreement before copying", W, M, ("10",),
             clock=ClockDef(ClockBasis.LAW, cite="CIV 5205(f)", label="the member agrees to the cost before copies are made"),
             why="Ends when a person notes the agreement, or that it is an inspection with no copies. Whether the wait stops the "
                 "records clock is not in the words read, so the clock runs and both dates show (a question for counsel)."),
        step("13", "Records: make them available; record the day and how", P, M, ("11", "12"),
             command="the records store write", record="the day produced, and whether inspected or copied",
             clock=ClockDef(ClockBasis.LAW, cite="CIV 5210(b)(1)",
                            label="current year within 10 business days; the two prior years within 30 calendar days (5210(b)(2)); computed in RQ-01"),
             why="The membership list (CIV 5210(b)(6) with Corp. Code 8330) is out of this clock until counsel reads it: its figure in "
                 "the code does not match the words, and this step does not date it."),
        step("14", "Resale documents: the documents and the form, fee estimate first", P, M, ("8",),
             record="the day delivered, with the day the request was mailed or delivered as the anchor",
             clock=ClockDef(ClockBasis.LAW, "received_on", 10, cite="CIV 4530(a)(1)",
                            label="within 10 days of the mailing or delivery of the request"),
             why="The received day is the request's mailed or delivered day."),
        step("15", "Board kinds: put it on the next agenda", P, M, ("8",), command="jason board",
             record="the board item: the question, the recited provisions, the options, no recommendation",
             clock=ClockDef(ClockBasis.DOCUMENTS, label="the documents' or the statute's time, from RQ-01"),
             why="jason never approves, denies, or assigns a request."),
        step("16", "The board decides", D, S, ("15",), command="#/room, #/decisions",
             record="the decision: the date, the meeting, the vote as taken, the motion's words, any conditions",
             why="The secretary records the board's vote; opening the run gives no standing to record it."),
        step("17", "Write the decision letter", P, M, ("16",), command="jason letter", spawns="owner-document",
             record="the letter at stage approved, with its elements checked",
             clock=ClockDef(ClockBasis.LAW, cite="CIV 4765(a)(4)", label="a decision on a proposed change is in writing"),
             why="The officer who recorded the vote signs. A decision the Act makes a noticed act opens a notice-delivery run."),
        step("18", "Post the decision in the thread; record where", P, M, ("17",), record="where it was sent",
             why="As the acknowledgment's send."),
        step("19", "Reconsideration asked", B, S, ("18",),
             choices=(Choice("asked", ()), Choice("not-asked", ())),
             clock=ClockDef(ClockBasis.DOCUMENTS, cite="CIV 4765(a)(5)",
                            label="the documents' time for a request for reconsideration, or a proposed policy"),
             why="If asked, a new respond-request opens for a reconsideration at an open meeting; if not, nothing follows. "
                 "A person answers until jason can read the arrival."),
        step("20", "Staff kinds: answer; maintenance is answered when the plan is told and closed when the work is done", P, M, ("8",),
             command="jason request-comment ID TEXT, or a Gmail reply", record="the first answer, where it was sent",
             why="The clock is the kind's row, read in RQ-01."),
        step("21", "Waiting on the member", W, M, ("6",), skip=by_manager,
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="only a policy clock pauses; a statute or documents clock does not"),
             why="A pause is a person's record with a reason, ended when the member writes back. Not built: a response rule has no "
                 "pause field. Skipped, with the reason, when the member is not being waited on."),
        step("22", "Close the request", P, M, ("13", "14", "18", "20"), sop="respond#5",
             record="closed in the request thread, and the day",
             why="The next sync shows it closed; a done step that a store contradicts reads 'changed since'."),
    )
    phases = _phases(key, ("intake", "Intake", ("1", "2", "3", "4", "5")), ("acknowledge", "Acknowledge", ("6", "7", "21")),
                     ("route", "Route by kind", ("8",)), ("records", "Records", ("10", "11", "12", "13")),
                     ("resale", "Resale", ("14",)), ("board", "The board", ("15", "16", "17", "18", "19")),
                     ("staff", "Staff", ("20",)), ("close", "Close", ("22",)))
    return Workflow(key=key, title="Answer a member's request on its clock", family=FAMILY, subject="request", steps=steps,
                    dates=(DateSlot("received_on", "The day the request was received"),), phases=phases, procedure="respond")


def respond_policy() -> Workflow:
    key = "respond-policy"
    step = _maker(key)
    steps = (
        step("1", "Print the proposal: each kind's clock with its source, statutes recited, policy clocks marked proposed", P, M,
             command="jason respond --standards (not built); today jason respond --all and the rule rows", becomes="job respond-standards",
             record="the proposal printed", why="A policy clock is shown labeled proposed."),
        step("2", "Put it on the board's agenda with the options: adopt, adopt with changes, keep internal", P, M, ("1",),
             command="jason board", record="the board item",
             why="The options are the board's: jason proposes and takes no side."),
        step("3", "Is it a rule on a subject listed in CIV 4355(a)?", B, S, ("2",),
             choices=(Choice("rule-change", ()), Choice("policy", ())), command="jason rule-change",
             clock=ClockDef(ClockBasis.LAW, "decide_on", -28, cite="CIV 4360(a)",
                            label="notice of a proposed rule change at least 28 days before the change"),
             why="A reading for counsel. Yes: jason rule-change, notice first. No: a policy adopted at an open meeting. "
                 "A person answers until jason can read it."),
        step("4", "Adopt, change, or decline", D, S, ("3",), command="#/room, #/decisions",
             record="the vote and the motion's words",
             clock=ClockDef(ClockBasis.PROPOSED_POLICY, cite="CIV 4350",
                            label="the board's decision; an operating rule is valid only if written, within authority, and reasonable"),
             why="jason proposes; the board adopts. Where the law is silent a written policy applied the same way each time is the board's evidence of good faith."),
        step("5", "Write the rows into the profile from the decision", P, A, ("4",), skip=SkipRule((A, M)),
             record="the patch applied: adoption and adopted on each row (the fields are not built)",
             why="A patch a person applies. Skipped, with the reason, when the board declined or kept the standard internal."),
        step("6", "Publish only the adopted rows", P, M, ("5",), spawns="owner-document", skip=by_manager,
             becomes="kind google-doc",
             record="the response-standards template rendered from the adopted rows",
             why="Skipped, with the reason, when nothing was adopted. The rendered page is an owner-document run."),
    )
    return Workflow(key=key, title="Adopt a written response standard", family=FAMILY, subject="standard", steps=steps,
                    dates=(DateSlot("decide_on", "The day the board decides", required=False),),
                    phases=_phases(key, ("propose", "Propose", ("1", "2")), ("decide", "The board decides", ("3", "4")),
                                   ("publish", "Publish", ("5", "6"))), procedure="respond")


# --- owner-document (section 2.5) -----------------------------------------------------------------------------------

def owner_document() -> Workflow:
    key = "owner-document"
    step = _maker(key)
    by_author = SkipRule((ANY,))
    steps = (
        step("1", "Write it once in Markdown under data/drafts, pictures as ![alt](file){width=560}", P, ANY, sop=f"{key}#1",
             record="the source file and its hash", why="Lesson one-source-per-document: the Doc, the PDF, and the email all come from this file."),
        step("2", "Check the references: every {QUOTE:key#n} and {CITE:key#n} fills", C, JASON, ("1",),
             check=named_check("references-fill"), command="jason section-refs --check FILE", sop=f"{key}#2", repeat=Repeat.PER_PERIOD,
             why="A quote noted 'check before sending' is read against the recorded copy. Again after each edit."),
        step("3", "Where it states what a provision requires, read the provision as cited", P, ANY, ("2",),
             command="jason cite EXPRESSION --cited-by --md", sop=f"{key}#3", skip=by_author,
             record="the citation, with the words in force and any reading labeled and whose",
             clock=ClockDef(ClockBasis.DOCUMENTS, label="the law or the documents the text cites"),
             why="Skipped, with the reason, when it states no requirement."),
        step("4", "Is it a notice the Act requires? If so, check its elements", C, JASON, ("2",),
             check=named_check("notice-elements"), command="jason notices REQUIREMENT --catalog", skip=by_author,
             why="Each element is present, supplied by a token, enclosed, missing, or not checkable by words. Skipped, with the reason, "
                 "when it is not a required notice. A required notice is handed to a notice-delivery run in step 9."),
        step("5", "Make its Doc on the letterhead", P, ANY, ("3",), command="jason broadcast FILE.md --to-doc --yes", sop=f"{key}#4",
             becomes="kind google-doc", repeat=Repeat.PER_PERIOD, record="the Doc id; the Markdown's hash matches the hash the Doc was made from",
             why="Again after each edit; a Doc edited after approval returns the letter to saved."),
        step("6", "Approve the words", P, S, ("5",), command="#/approvals (letters); no command verified",
             record="the letter at stage approved with its log; a board approval recorded with the meeting's date",
             why="The letter's named approver approves; where the board must, its vote is recorded by the secretary or the president. "
                 "The secretary records that the stage is approved."),
        step("7", "For a page to post or attach, export the PDF", P, ANY, ("6",), command="jason letter --markdown FILE.md --pdf OUT.pdf --yes",
             sop=f"{key}#5", becomes="job letter-pdf-export", skip=by_author, record="the PDF made",
             why="Skipped, with the reason, when no page is needed."),
        step("8", "Preview it as one recipient receives it", P, ANY, ("5",), command="jason owner-info --email-batch ... --preview OUT.html",
             sop=f"{key}#6", repeat=Repeat.PER_ITEM, record="the subject names the unit; form links carry the unit",
             why="Per channel; the command shown is for the owner-information email."),
        step("9", "Hand it to a delivery: an email batch, a broadcast, the Mailroom, or a posting", B, ANY, ("8", "6"),
             choices=(Choice("email-batch", ()), Choice("broadcast", ()), Choice("mailroom", ()), Choice("posting", ())),
             spawns="notice-delivery",
             why="The text is kept under data/notices/KEY with its hash. The delivery is its own run (notice-delivery, with a "
                 "mailroom-letter run for a mailing)."),
        step("10", "Read the kept text against the file", C, JASON, ("9",), check=named_check("kept-text-unchanged"),
             command="jason cite jason://notice/KEY",
             why="An edit since the text was kept means the words above are not the words sent."),
    )
    phases = _phases(key, ("write", "Write", ("1", "2", "3", "4")), ("make", "Make", ("5", "6", "7", "8")), ("send", "Send", ("9", "10")))
    return Workflow(key=key, title="Write an owner document once", family=FAMILY, subject="document", steps=steps, phases=phases,
                    procedure=key)


# --- form-campaign and form-library-review (section 2.6) -----------------------------------------------------------

def form_campaign() -> Workflow:
    key = "form-campaign"
    step = _maker(key)
    steps = (
        step("1", "Is the form offered? Tier, status, recitals, handler, marker", C, JASON, check=named_check("form-offered"),
             command="jason form-library --check [--tier T]", why="On open."),
        step("2", "Stale against an amendment?", C, JASON, ("1",), check=named_check("form-stale"),
             command="jason form-library --check; jason law-history", spawns="form-library-review",
             why="A stale form opens a form-library-review run; the statute's text on the shelf is the authority."),
        step("3", "Choose the handler", B, M, ("1",),
             choices=(Choice("owner-information", (f"{key}.6.6", f"{key}.6.7")), Choice("response-clock", ())),
             command="jason campaigns --open FORM ... --handler KEY",
             why="A form with an authority takes the process handler its citations name. A custom form takes a general handler, "
                 "none of which is built: leave this step open and the run is blocked. A person answers until jason can read it."),
        step("4", "Open the campaign", P, M, ("3",), sop="owner-info-cycle#10",
             command="jason campaigns --open FORM --channel C --cycle-year Y --by NAME [--option NAME=VALUE] [--return-by DATE]",
             record="the campaign code opened",
             why="Every generator refuses a form with no open campaign; a row the profile already runs is adopted with --adopt."),
        step("5", "Offer the form in its channel: a PayHOA form, the request center, or a PDF; the link carries the unit", P, M, ("4",),
             command="jason forms --payhoa KEY --yes", becomes="kind payhoa-form-update",
             record="where it is offered; the copies kept in the references store",
             why="A linked form is changed in place and never deleted."),
        step("6", "Collect and process the arrivals (group IN: check, read, confirm, key a paper return, triage, enter what only a person can)",
             P, M, ("5",), command="jason responses --check", sop="owner-info-cycle#14",
             record="the arrivals read and confirmed (a count or ids)",
             why="Handler owner-information goes to the plan below; handler response-clock opens a respond-request for each arrival "
                 "that asks for something. A reading is evidence for a person."),
        step("6.6", "Decide what only the board decides: a co-owner's answer for the others, an occupancy answer the tag does not show, a blank required answer",
             D, S, ("6",), command="jason board", sop="owner-info-cycle#16", record="the board's decision record or the minutes",
             why="Handler owner-information only. The law is silent, so each is held and never approved by a click."),
        step("6.7", "Record the answers: a plan decided item by item by a named person, applied only if nothing changed", PL, M, ("6", "6.6"),
             plan_kind="owner-info-tags", command="jason approvals plan owner-info-tags --by NAME", sop="owner-info-cycle#17",
             clock=ClockDef(ClockBasis.LAW, "reports_mailed", -30, cite="CIV 4041(b)(1)", label="enter the answers in the books"),
             why="Handler owner-information only. At least 30 days before the 5300 and 5310 disclosures; complete a request only after its writes."),
        step("7", "Read what is due and who is outstanding", C, JASON, ("5",), check=named_check("outstanding-read"),
             command="jason campaigns --show CODE; jason followups --campaign CODE", sop="owner-info-cycle#15",
             why="An owner who answered by any method is not outstanding; an unreachable owner is listed apart. The read finds the "
                 "campaign by the run's return-by date."),
        step("8", "Close the campaign", P, M, ("6", "6.6", "6.7"), command="jason campaigns --close CODE --by NAME", sop="owner-info-cycle#19",
             record="the campaign closed", clock=ClockDef(ClockBasis.PROPOSED_POLICY, "return_by", 7,
                                                           label="close (proposed: 7 days after return-by)"),
             why="A standing form with no return-by has no close date (not verified in the campaigns)."),
    )
    phases = _phases(key, ("check", "Check the form", ("1", "2", "3")), ("offer", "Offer it", ("4", "5")),
                     ("collect", "Collect and record", ("6", "6.6", "6.7", "7")), ("close", "Close", ("8",)))
    return Workflow(key=key, title="Offer a standard form and process what comes back", family=FAMILY, subject="campaign", steps=steps,
                    dates=(DateSlot("return_by", "Answers asked by", required=False),
                           DateSlot("reports_mailed", "The annual reports are mailed", required=False, after="return_by")),
                    phases=phases, procedure="")


def form_library_review() -> Workflow:
    key = "form-library-review"
    step = _maker(key)
    steps = (
        step("1", "List the Act's changes since each form's as-of", P, A, command="jason conflicts --leads; jason form-library --check",
             sop="law-review#6", becomes="job form-library-check", record="the stale forms and citations listed",
             why="Each January."),
        step("2", "Read each amendment; update the definition; bump the version, with what changed and when it takes effect", P, A, ("1",),
             repeat=Repeat.PER_ITEM, command="a code change", record="the new version, what changed, and when it takes effect",
             why="A campaign keeps the version it used."),
        step("3", "A change in the law in the middle of a campaign", D, S, ("2",), skip=SkipRule((S,)),
             record="the board's decision record", clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="the library's open question: the board decides"),
             why="Only on a finding; skipped, with the reason, when no campaign is open. jason does not decide it."),
        step("4", "Find requests the law or the documents create that have no form", P, A,
             command="jason discover-forms --seed, --read, --confirm ID --by NAME", becomes="job form-discover",
             record="each candidate confirmed, held, or dropped",
             why="Yearly. A candidate whose clock the law leaves silent is held as a proposed policy."),
    )
    return Workflow(key=key, title="Keep the form library current with the law", family=FAMILY, subject="period", steps=steps,
                    phases=_phases(key, ("read", "Read the changes", ("1", "2", "3")), ("find", "Find missing forms", ("4",))),
                    procedure="law-review")


BUILDERS: tuple[Callable[[], Workflow], ...] = (
    notice_delivery, mailroom_letter, respond_sweep, respond_request, respond_policy, owner_document, form_campaign,
    form_library_review,
)


def _becomes() -> Mapping[str, str]:
    """{step id: "check NAME" | "job NAME" | "kind NAME" | "case NAME"} for each step that says what it becomes."""
    words = {v: k for k, v in _ARTICLE.items()}
    out: dict[str, str] = {}
    for build in BUILDERS:
        for s in build().steps:
            m = _BECOMES.search(s.why)
            if m:
                out[s.id] = f"{words[m.group('article')]} {m.group('name')}"
    return out


BECOMES: Mapping[str, str] = _becomes()
"""{step id: the read, job, or approvals kind it waits for}, as "check NAME", "job NAME", "kind NAME", or "case NAME"."""

WANTED: tuple[str, ...] = tuple(dict.fromkeys(BECOMES.values()))
"""The reads, jobs, and approvals kinds these definitions wait for, once each, in the order the steps need them."""


__all__ = ["BECOMES", "BUILDERS", "FAMILY", "WANTED", "form_campaign", "form_library_review", "mailroom_letter", "notice_delivery",
           "owner_document", "respond_policy", "respond_request", "respond_sweep"]
