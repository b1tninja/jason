"""The property family: the general workflow definitions of docs/workflows/property-safety-vendors.md, built as data.

Nine definitions, keyed as the page keys them: ``life-safety-period`` (the page's section 2.1: one system's inspection, test,
or maintenance for one period), ``deficiency`` (2.2), ``backflow-annual`` (2.3), ``elevated-elements`` (2.4),
``contract-notice-window`` (2.5), ``improvement-request`` (2.6), ``paint-cycle`` (2.7), ``loss-claim`` (2.8), and
``maintenance-program`` (2.9). A step's id is ``<key>.<n>`` with n its place in the page's table (``ORDER`` below names the
page's own step ids in that order, so a step is found by the page's word and numbered by its place). A step is never renumbered.

This module is pure data. It imports the engine's types, ``named_check``, and the helpers of ``definitions_general`` (none
needed here), and nothing of the approvals, tasks, controls, community, or web packages. It adds nothing to
``readers.CHECKS`` or ``readers.JOBS``. So:

- **A plan step** exists only for a registered approvals kind. One does here: ``ask`` of ``life-safety-period`` (the
  ``gmail-drafts`` kind, case ``proposal-request``). Every other write the page calls a plan (a filing plan, an insurer's
  notice, a letter, a vendor's question) has no registered kind, so it is a ``person`` step whose ``why`` says what it
  becomes.
- **A job or a check step** needs a name in ``JOBS`` or ``CHECKS``. None of the property reads is registered there (that
  belongs to the engine's owner), so each read the page gives to jason is a ``person`` step (the manager reads the command's
  output and attests the result). ``WANTED`` lists, as strings, the checks, jobs, plan kinds, templates, and commands the
  page wants that do not exist, so each step can be made what the page says when they do.
- **A law clock** is on a step only where the statute is on the authorities shelf (Civil Code, Health and Safety Code 116800).
  The State Fire Marshal's regulations (19 CCR 904.2) are not on the shelf, so their clocks have the basis ``documents`` with the
  regulation named in ``cite`` (never ``law``). A contract's notice windows are ``documents`` with both edges. A supplier's or
  vendor's stated day is ``counterparty``. A number that is neither the law's nor the documents' is ``proposed policy``.
  A computed date is labeled as the earliest day (or the latest, for an edge that closes).
- **A step with a law clock has no skip rule** (the engine refuses one). Where the page lets a person skip a step the law
  also names, the statute is cited in the ``why`` and the clock is the documents' or none.
- **Roles.** The page's ``reviewer`` (the committee role proposed in console/security-and-privacy.md) is not a ``Role`` yet,
  so a reviewer's step is the manager's. A board vote is a ``decision`` recorded by the secretary. Where the page says
  "president or manager" the manager acts.

**Privacy.** A ``loss-claim`` and an ``improvement-request`` touch a unit and its owner. A run of either has an opaque
subject (the incident's or the request's own id, never an address or a name) and a label that carries no unit or name; a step
asks for a record by its address or id, never by what it says. ``deficiency`` is keyed by a register row's hash id. The
elevated-element inspector's name, licence, and report name are private facts (data/spec) and are never in a step. Executive
session (CIV 4935) is not composed in the Work screens; none of these definitions marks a step executive, and the one place
the law permits a closed session (the engagement of an engineer or architect, a contract's formation) is a ``decision``
whose record is the board's decision, not its deliberation.

No definition here names an association, a street, a vendor, a person, or a fixed amount.
"""

from __future__ import annotations

from typing import Any, Callable

from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, DateSlot, Phase, Repeat, Role, SkipRule, StepDef, StepKind, Workflow,
)

FAMILY = "property"

LSP, DEF, BACK, ELEV, CNW, IMP, PAINT, LOSS, PROG = (
    "life-safety-period", "deficiency", "backflow-annual", "elevated-elements", "contract-notice-window",
    "improvement-request", "paint-cycle", "loss-claim", "maintenance-program")

# The page's own step ids, in the order of its tables; a step's number is its place here, counted from 1.
ORDER: dict[str, tuple[str, ...]] = {
    LSP: ("read", "applies", "ask", "send", "wait-reply", "proposal", "entry", "visit", "file", "read-report", "place",
          "authority", "deficiencies", "keep"),
    DEF: ("propose", "confirm", "impairs", "route", "tell-insurer", "estimate", "repair-decision", "repair", "clear", "lift",
          "board-item"),
    BACK: ("notice-in", "assemblies", "ask-program", "tester", "hire", "test", "receipt", "failed", "repair-retest", "file",
           "record", "next"),
    ELEV: ("reach", "facts", "due", "engage", "list", "inspect", "read", "threat", "preventive", "reserve", "keep", "next"),
    CNW: ("read", "confirm-term", "window", "owed", "licence", "statement", "review", "choice", "draft", "approve", "send",
          "ack", "renew", "transition"),
    IMP: ("receive", "track", "need", "ack", "complete", "missing", "wait-owner", "review", "agenda", "vote", "letter",
          "reconsider", "conditions", "work", "verify", "manual", "findings"),
    PAINT: ("refresh", "watch", "substitute", "dates", "scope", "bids", "award", "notice", "record", "doc", "request"),
    LOSS: ("record", "history", "mitigate", "policy", "notify", "packet", "confirm-step", "guideline", "ask-owner", "outcome",
           "members", "close"),
    PROG: ("standing", "adopt", "sync", "read", "ask", "licence", "vacate", "vacate-notice", "complaint", "renewal", "review"),
}

WANTED: tuple[str, ...] = (
    # reads the page gives to jason, as checks (readers.CHECKS) once they are written
    "check:life-safety-standing -- the standing of each obligation for the period, from the life-safety loader (life-safety-period read)",
    "check:life-safety-reports-read -- reports placed and read for the period (life-safety-period read-report, keep)",
    "check:deficiency-fold -- the register row's state, read from the register's own fold (deficiency, every step)",
    "check:backflow-assemblies -- assemblies from the notice, the water account, and last year's reports, side by side (backflow-annual assemblies)",
    "check:backflow-tester -- the tester against the published lists (backflow-annual tester)",
    "check:elevated-due -- each building's due day from the elevated-inspection records (elevated-elements due)",
    "check:contract-window -- both edges of each notice window, with delivery (contract-notice-window window)",
    "check:contract-owed -- what the counterparty owes and whether it is on file (contract-notice-window owed)",
    "check:contract-statement -- the managing agent's written statement, present or missing (contract-notice-window statement)",
    "check:improvement-findings -- the five findings of the unit's manual (improvement-request findings)",
    "check:paint-catalog -- each scheduled color against the maker's catalog (paint-cycle watch)",
    "check:loss-packet -- the five-question loss packet (loss-claim packet)",
    "check:program-standing -- a maintenance program's document, adoption, and implementation (maintenance-program standing)",
    # jobs (readers.JOBS)
    "job:life-safety-read-report -- jason models --filed, after the local-ai preflight (life-safety-period read-report)",
    "job:life-safety-propose -- jason life-safety --propose (deficiency propose)",
    "job:contract-terms -- jason contract-terms FILE, by a model a person chose (contract-notice-window read)",
    "job:paint-refresh -- jason paint --refresh, a person's ask (paint-cycle refresh)",
    "job:vendor-portal-sync -- jason vendors --sync (maintenance-program sync)",
    "job:gmail-sync -- jason gmail --sync, the arrival of a servicer's, supplier's, or counterparty's mail (every wait)",
    # plan kinds (the approvals registry)
    "plan:gmail-drafts/insurer-notice -- a draft notice to the insurer or agent (deficiency tell-insurer)",
    "plan:gmail-drafts/vendor-question -- a draft question to a vendor (maintenance-program ask, backflow-annual ask-program)",
    "plan:gmail-drafts/owner-request -- a draft to an owner for the items a request lacks (improvement-request missing, loss-claim ask-owner)",
    "plan:drive-filing -- the filing plan for a report and what a portal holds (life-safety-period, backflow-annual file)",
    "plan:payhoa-comment -- a request comment posted by a person (improvement-request ack)",
    "plan:doc-write -- the palette Doc and page refresh (paint-cycle doc)",
    # base templates
    "template:contract-notice -- a non-renewal or termination notice in the clause's own words, address, and delivery",
    "template:entry-notice -- the notice to occupants when an inspection needs entry",
    "template:decision-letter -- an improvement request's written decision, with the elements CIV 4765(a)(4) requires",
    "template:incomplete-items-letter -- the list of what an application lacks",
    "template:vacate-notice -- the notice to occupants and owners that treatment needs them out (CIV 4785(b))",
    # commands
    "command:jason contract-terms --window KEY -- both edges of a notice window",
    "command:jason improvements --determine / --board-item -- an improvement request's determination and agenda item",
    "command:jason incidents --record -- a person-entered incident record",
    "command:jason programs -- a maintenance program's lifecycle",
    "command:jason workflow children -- a child run for each open deficiency, started from a reading",
    # a role
    "role:reviewer -- the committee role proposed in docs/console/security-and-privacy.md (improvement-request review)",
)
"""What the page wants and the engine or the stores do not yet have, as strings ``kind:name -- what it is for``. Each step
that waits on one says so in its ``why``."""

LEFT_OUT: tuple[str, ...] = ()
"""Definitions built but left out of ``BUILDERS`` because the Work screens cannot hold them safely. None: the two that touch a
unit and an owner (``loss-claim``, ``improvement-request``) are held by an opaque subject and a label with no unit or name, at
level P2 for the offices that open it, and no step needs a closed session."""


# --- small helpers --------------------------------------------------------------------------------------------------

P, C, J, PL, D, W, B = (StepKind.PERSON, StepKind.CHECK, StepKind.JOB, StepKind.PLAN, StepKind.DECISION, StepKind.WAIT,
                        StepKind.BRANCH)
M, S, PRES = Role.MANAGER, Role.SECRETARY, Role.PRESIDENT
BY_MANAGER = SkipRule((M,))
BY_SECRETARY = SkipRule((S,))
ONCE, ITEM, PERIOD = Repeat.ONCE, Repeat.PER_ITEM, Repeat.PER_PERIOD


class _Ids:
    """The ids of one definition: a step is named by the page's word and numbered by its place in ``ORDER``."""

    def __init__(self, key: str):
        self.key = key
        self.names = ORDER[key]

    def sid(self, name: str) -> str:
        return f"{self.key}.{self.names.index(name) + 1}"

    def step(self, name: str, title: str, kind: StepKind, role: Role, needs: tuple[str, ...] = (), **more: Any) -> StepDef:
        return StepDef(self.sid(name), title, kind, role=role, needs=tuple(self.sid(n) for n in needs), **more)

    def choice(self, key: str, *names: str) -> Choice:
        return Choice(key, tuple(self.sid(n) for n in names))

    def phase(self, key: str, title: str, *names: str) -> Phase:
        return Phase(key, title, tuple(self.sid(n) for n in names))

    def finish(self, steps: tuple[StepDef, ...], phases: tuple[Phase, ...]) -> None:
        """The steps are exactly the page's, in its order, and each phase names only steps of this definition."""
        assert tuple(s.id for s in steps) == tuple(self.sid(n) for n in self.names), self.key
        ids = {s.id for s in steps}
        assert all(x in ids for p in phases for x in p.steps), self.key


def _clock(basis: ClockBasis, label: str, slot: str = "", days: int = 0, cite: str = "") -> ClockDef:
    return ClockDef(basis, slot, days, cite=cite, label=label)


def _law(cite: str, label: str, slot: str = "", days: int = 0) -> ClockDef:
    return _clock(ClockBasis.LAW, label, slot, days, cite)


def _docs(label: str, cite: str = "", slot: str = "", days: int = 0) -> ClockDef:
    return _clock(ClockBasis.DOCUMENTS, label, slot, days, cite)


def _proposed(label: str, slot: str = "", days: int = 0) -> ClockDef:
    return _clock(ClockBasis.PROPOSED_POLICY, label, slot, days)


def _person_day(label: str, slot: str = "", days: int = 0) -> ClockDef:
    return _clock(ClockBasis.PERSON, label, slot, days)


def _counterparty(label: str, slot: str = "", days: int = 0) -> ClockDef:
    return _clock(ClockBasis.COUNTERPARTY, label, slot, days)


def _opt(name: str, label: str, after: str = "") -> DateSlot:
    """A date a run may be started with, and that is often not known until a record is read: never required."""
    return DateSlot(name, label, required=False, after=after)


# --- 2.1 life-safety-period -----------------------------------------------------------------------------------------

def life_safety_period() -> Workflow:
    """One system's inspection, test, or maintenance for one period (page 2.1). The subject is the system, the obligation, and the
    period. ``ask`` is the one plan step; ``deficiencies`` starts a ``deficiency`` run for each open row."""
    i = _Ids(LSP)
    s = i.step
    after_applies = ("ask", "send", "wait-reply", "proposal", "entry", "visit", "file", "read-report", "place", "authority",
                     "deficiencies", "keep")
    steps = (
        s("read", "Read the record for the period: each obligation's standing, the periods covered, the reports unplaced or not read",
          P, M, command="jason inspections; jason deadlines", repeat=PERIOD,
          clock=_docs("the obligation row's cadence (19 CCR 904 for a sprinkler system; the specification's row)", "19 CCR 904(a)(1)"),
          record="each obligation's standing, in words (current, done late, upcoming, due soon, overdue, needs input, none on record)",
          why="The page gives this read to jason (check life-safety-standing, wanted); until it exists the manager reads the command's "
              "output and attests it. 'None on record' is not 'not done'; no skip."),
        s("applies", "Settle which obligations reach the system", B, M, ("read",), command="jason applies; jason applies --file-questions",
          repeat=ITEM, choices=(i.choice("applies", *after_applies), i.choice("does-not-apply")),
          why="Answered by fact (jason applies), by the manager when the fact is missing. An undetermined obligation is left open "
              "as a question (jason intake --answer ID TEXT --by NAME): it never reads as 'not required'."),
        s("ask", "Ask the servicer for the reports it holds and a proposal", PL, M, ("read", "applies"), plan_kind="gmail-drafts",
          command="jason draft --proposal-request SYSTEM --to ADDRESS --yes; or jason approvals plan gmail-drafts --scope ...",
          sop="duty-schedule#5", clock=_proposed("items due within the horizon ride along (proposed: 120 days, the program's)"),
          skip=BY_MANAGER, repeat=ITEM,
          why="The approvals kind gmail-drafts, case proposal-request, keyed by the system; it saves a draft and never sends. "
              "Skipped, with the reason, when a report already answers the item. The servicer's waiting mail and the agreement on file ride as reminders."),
        s("send", "Read the draft in Gmail and send it", P, M, ("ask",), record="the day sent and the draft's reference",
          why="jason has no send method; a person sends. The run ends at the record, not at the act."),
        s("wait-reply", "Wait for the servicer's report or proposal", W, M, ("send",), command="jason gmail --sync; jason followups --add",
          clock=_person_day("a person's own date; the law sets no number", "reply_by"), skip=BY_MANAGER,
          why="Passing the date opens a follow-up and offers `ask` to another recipient; jason picks no recipient. Skipped when a "
              "report arrives by another route."),
        s("proposal", "Accept, decline, re-bid, or defer the proposal", D, S, ("wait-reply",), command="jason board",
          record="the board's decision record (motion and outcome)",
          why="A board item in the safety category and a recorded decision. Accepting starts a contract-notice-window run for the "
              "agreement. Any spending authority the documents state is not read here. jason accepts nothing."),
        s("entry", "Tell occupants when the inspection needs entry", P, M, ("proposal",), skip=BY_MANAGER, repeat=ITEM,
          clock=_docs("the governing documents' entry clause (not read here)"),
          record="the notice's reference, per building",
          why="A draft from the entry-notice base template (wanted) that a person sends. Skipped, with the reason, when no unit is entered."),
        s("visit", "Wait for the booked inspection", W, M, ("entry",), clock=_person_day("the booked day", "visit_on"),
          why="Ended by a person's note that the inspection took place."),
        s("file", "File the report and what the portal holds", P, M, ("visit",), repeat=ITEM,
          command="jason gmail --file-vendor VENDOR --life-safety --yes; jason vendors --reports --drive --yes",
          record="the filing plan's counts and the library address of the report",
          why="The page makes this a filing plan; no approvals kind covers Drive filing (plan:drive-filing, wanted), so a person reads "
              "the plan first and applies it. A protected portal is a person's step: jason enters no password or code."),
        s("read-report", "Read the filed report into the record", P, M, ("file",), command="jason models --filed", repeat=ITEM,
          record="the reading: inspection date, interval, result, deficiencies, buildings",
          why="The page makes this a job (job:life-safety-read-report, wanted; GPU lane after the local-ai preflight). A State form's "
              "marks are read by a person, and no period is assigned from a file name."),
        s("place", "Place what the reading could not, and record the occurrence", P, S, ("read-report",),
          command="jason inspections; jason schedule-evidence --record KEY DUE --by NAME", sop="duty-schedule#4", repeat=ITEM,
          record="the occurrence and its evidence (the report's library address)",
          why="The manager reads what is unplaced; the secretary records the occurrence. Two obligations sharing one report stay "
              "'not assigned' until a person says which."),
        s("authority", "Confirm the report reached the fire authority having jurisdiction", P, M, ("read-report",), skip=BY_MANAGER,
          clock=_docs("the servicer's duty 'at the completion' of the testing (no number)", "19 CCR 904.2(j)"),
          record="the confirmation, or the servicer's record that it sent the report",
          why="19 CCR 904.2(j) is not on the authorities shelf, so the clock is the documents', not the law's. Skipped, with the "
              "reason, when the authority takes none."),
        s("deficiencies", "Open a child run for each deficiency the report lists", P, M, ("read-report",), spawns=DEF,
          command="jason life-safety --propose", skip=BY_MANAGER, repeat=ITEM,
          record="the child run ids, one for each open row",
          why="One deficiency run for each row; none when the report passed with nothing open (skip, with that reason)."),
        s("keep", "Keep the record on file", P, M, ("place",), command="jason inspections",
          clock=_docs("kept five years after the next required test or maintenance (not a law clock here: the regulation is not on the shelf)",
                      "19 CCR 904.2(c)"),
          record="the report's library address and the day its retention ends",
          why="Closes the run. The retention end is read from the record-keeping rule, recited; the page gives the read to jason."),
    )
    phases = (
        i.phase("read", "Read the record", "read", "applies"),
        i.phase("ask", "Ask the servicer", "ask", "send", "wait-reply", "proposal", "entry", "visit"),
        i.phase("file", "File and read the report", "file", "read-report", "place", "authority", "deficiencies"),
        i.phase("keep", "Keep the record", "keep"),
    )
    i.finish(steps, phases)
    return Workflow(key=LSP, title="A life-safety inspection period", family=FAMILY, subject="period", steps=steps,
                    dates=(_opt("visit_on", "The booked inspection day"), _opt("reply_by", "Hear back from the servicer by")),
                    phases=phases, procedure="")


# --- 2.2 deficiency -------------------------------------------------------------------------------------------------

def deficiency() -> Workflow:
    """One deficiency a report found (page 2.2). The register is the event log; the run links to it and copies nothing. The
    subject is the register row's hash id. Every confirmed deficiency becomes a board item (decided 2026-10-11)."""
    i = _Ids(DEF)
    s = i.step
    steps = (
        s("propose", "Propose a row from a reading that lists an open deficiency", P, M, command="jason life-safety --propose",
          record="the proposed row's id",
          why="The page makes this a job (job:life-safety-propose, wanted). The row id is a hash of report, location, device, and "
              "comment, so a second run adds none."),
        s("confirm", "Confirm the row against the report", P, M, ("propose",), command="jason life-safety --confirm ID --by NAME",
          record="the act 'confirmed': who and when",
          why="No 'not a deficiency' act exists yet (a gap the page records)."),
        s("impairs", "Say whether it impairs a scheduled safeguard", P, M, ("confirm",),
          command="jason life-safety --impairs ID --value yes|no --by NAME", record="the act 'impairs' or 'does not impair'",
          why="A person's reading, never inferred; a later act corrects it. P2: never shown while an admin views as someone else."),
        s("route", "Follow the recorded answer", B, M, ("impairs",), choices=(i.choice("impairs", "tell-insurer", "lift"),
                                                                                  i.choice("does-not-impair")),
          why="If it impairs, telling the insurer becomes required; otherwise it does not apply. The answer is the one recorded at `impairs`."),
        s("tell-insurer", "Tell the insurer or agent; keep what was sent", P, M, ("route",),
          command="jason life-safety --insurer-told ID --record REF --on DATE --by NAME",
          clock=_docs("the policy's protective-safeguards words; any number of days is the policy's (not read here)"),
          record="the day, and the library reference of what was sent",
          why="The act 'insurer told'. A draft of the notice is the gmail-drafts case insurer-notice (wanted); the loader raises a banner "
              "while no record shows the insurer was told."),
        s("estimate", "Wait for the written repair estimate", W, M, ("confirm",), command="jason gmail --sync", skip=BY_MANAGER,
          clock=_docs("a written estimate 'before performing any repairs' (the licensee's duty; no number)", "19 CCR 904.2(k)"),
          why="19 CCR 904.2(k) is not on the shelf. Skipped, with the reason, when no repair is needed."),
        s("repair-decision", "Approve the repair", D, S, ("estimate",), command="jason board",
          record="the board's decision record, or the manager's authority where the documents state one",
          why="The limit of the manager's authority is not read (jason has no spending-authority row); until it exists the board decides."),
        s("repair", "Wait for the repair", W, M, ("repair-decision",),
          clock=_docs("'immediate correction' (no number); a target is the board's to adopt, never stamped", "19 CCR 904.2(d)"),
          why="Passing a target a person recorded opens a follow-up. The invoice (line items) and the report arrive in the library."),
        s("clear", "Link the record that cleared it", P, M, ("repair",),
          command="jason life-safety --cleared ID --record REF --kind KIND --on DATE --by NAME",
          record="the clearing record's library reference, its kind (invoice lines, AES 10, a later passing report), and its day",
          why="An invoice's subject line and free text are refused; a clearing record dated on or before the finding is refused."),
        s("lift", "Tell the insurer the impairment ended, if the policy says to", P, M, ("clear", "tell-insurer"), skip=BY_MANAGER,
          clock=_docs("the policy's words decide (not read here)"),
          why="Whether the insurer is told is a question for the board and the policy. Skipped, with the reason, when the policy does not ask."),
        s("board-item", "Bring the deficiency to the board's attention as a board item", P, M, ("confirm",),
          command="jason life-safety --severity ID --value urgent|high|normal --by NAME; jason life-safety --deadline ID --date D --basis B --by NAME",
          clock=_person_day("a deadline a person records, with who set it (insurer, authority, documents, vendor, person); jason computes none",
                            "deadline_on"),
          record="the board item's id and the severity a person set (or jason's labeled proposal)",
          why="Decided 2026-10-11: every confirmed deficiency becomes a board item, proposed for the next agenda and prioritized by a "
              "person's severity and any deadline. Until a severity is set, jason's proposal is labeled as one. The board closes the item, never a clear. No skip."),
    )
    phases = (
        i.phase("find", "Find and confirm", "propose", "confirm", "impairs", "route", "tell-insurer"),
        i.phase("fix", "Estimate, decide, repair", "estimate", "repair-decision", "repair"),
        i.phase("clear", "Clear it", "clear", "lift"),
        i.phase("board", "The board's attention", "board-item"),
    )
    i.finish(steps, phases)
    return Workflow(key=DEF, title="A life-safety deficiency", family=FAMILY, subject="deficiency", steps=steps,
                    dates=(_opt("deadline_on", "A deadline a person records"),), phases=phases, procedure="")


# --- 2.3 backflow-annual --------------------------------------------------------------------------------------------

def backflow_annual() -> Workflow:
    """The water supplier's annual assembly test (page 2.3). The supplier's cycle, tester, tag, report, and deadline are the
    supplier's: a day is the counterparty's, shown from every date it could run from, and none is picked."""
    i = _Ids(BACK)
    s = i.step
    steps = (
        s("notice-in", "Record each notice with every date its days could run from", P, M, command="jason backflow", repeat=ITEM,
          clock=_docs("the notice's own words (its days); jason picks no date"),
          record="the notice's library address and each date its days could run from (dated, postmarked, scanned, failed test)"),
        s("assemblies", "Set the letter's assemblies beside the water account and last year's reports", P, M, command="jason backflow",
          repeat=PERIOD, record="each source in its own column; the differences, none picked",
          why="The page gives this read to jason (check:backflow-assemblies, wanted)."),
        s("ask-program", "Ask which date counts, or about a discrepancy", P, M, ("assemblies",), skip=BY_MANAGER,
          record="the message's reference and the answer recorded",
          why="A message sent by a person (a gmail-drafts case, wanted). Skipped, with the reason, when the notice settles it."),
        s("tester", "Check the tester against the published lists", P, M, command="jason backflow --fetch-testers", repeat=PERIOD,
          clock=_proposed("a list older than a year is flagged (proposed)"),
          record="the check: listed on the list dated D, under another business, not listed, or not fetched",
          why="The page makes this a check and a dated fetch (check:backflow-tester, wanted). Matching is on the tester's name; "
              "'listed' is never said as 'certified'."),
        s("hire", "Hire the tester and hand over the letter whole", P, M, ("tester",), record="the tester engaged and the assembly list given",
          why="The letter goes whole to the tester (lesson backflow-letter-goes-whole-to-the-tester)."),
        s("test", "Wait for the test and the filed report", W, M, ("hire",),
          clock=_counterparty("the supplier's stated day for the test, from the notice; each date it could run from is shown, none picked", "test_due"),
          why="Ended by a person's note that each assembly's report has arrived (tag number, final result, portal receipt)."),
        s("receipt", "Check each report", P, M, ("test",), repeat=ITEM, record="per assembly: the tag, the result, and the portal receipt"),
        s("failed", "Did any assembly fail?", B, M, ("receipt",), choices=(i.choice("failed", "repair-retest"), i.choice("passed")),
          why="Answered by the reading of the reports; a failed assembly makes the repair and retest required."),
        s("repair-retest", "Repair or replace, retest, and file again", W, M, ("failed",),
          clock=_docs("the notice's days to repair, counted from each candidate date and shown side by side"),
          why="Ended by the retest report's arrival. The water supplier's duty as the handbook states it is not on the shelf."),
        s("file", "File the reports", P, M, ("receipt",), repeat=ITEM,
          command="jason gmail --file-vendor VENDOR --life-safety --yes; jason vendors --reports --drive --yes",
          record="the filing plan's counts and the library address of each report",
          why="A filing plan as in life-safety-period (plan:drive-filing, wanted); a person reads it before applying it."),
        s("record", "Record the occurrence and the tag numbers", P, S, ("file",),
          command="jason schedule-evidence --record KEY DUE --by NAME", sop="duty-schedule#4", repeat=PERIOD,
          clock=_law("HSC 116800", "water users comply with the health officer's orders on testing and maintenance of backflow devices (no number)"),
          record="the occurrence and its evidence, with the tag numbers",
          why="The yearly cycle is the supplier's; the statute has no number. No skip."),
        s("next", "Wait for next year", W, M, ("record",), command="jason deadlines",
          clock=_docs("the next due day from the obligation row"), why="Opens next year's run."),
    )
    phases = (
        i.phase("notice", "The notice and the assemblies", "notice-in", "assemblies", "ask-program"),
        i.phase("test", "The tester and the test", "tester", "hire", "test", "receipt", "failed", "repair-retest"),
        i.phase("record", "File and record", "file", "record", "next"),
    )
    i.finish(steps, phases)
    return Workflow(key=BACK, title="The annual backflow test", family=FAMILY, subject="program", steps=steps,
                    dates=(_opt("test_due", "The supplier's stated day for the test"),), phases=phases, procedure="")


# --- 2.4 elevated-elements ------------------------------------------------------------------------------------------

def elevated_elements() -> Workflow:
    """The Civil Code 5551 inspection of exterior elevated elements (page 2.4): the nine-year cycle, a row for each building. The
    inspector's name, licence, and report name are private facts and never in a step."""
    i = _Ids(ELEV)
    s = i.step
    downstream = tuple(n for n in ORDER[ELEV] if n != "reach")
    steps = (
        s("reach", "Settle which buildings the section reaches", B, M, command="jason applies", repeat=ITEM,
          choices=(i.choice("reaches", *downstream), i.choice("does-not-reach")),
          clock=_law("CIV 5551(l)", "the section applies only to buildings containing three or more attached multifamily dwelling units"),
          why="A building whose facts are missing is a question, not an answer: leave it open."),
        s("facts", "Enter each building's facts from the record that states them", P, M, ("reach",), repeat=ITEM,
          record="the record that states each fact (attached units, responsibility, elements count, permit and certificate dates, inspection date and its report)",
          why="No date is entered without its report; a fact not stated stays unknown."),
        s("due", "Count the next due day", P, M, ("facts",), command="jason deadlines; jason applies", repeat=ITEM,
          clock=_law("CIV 5551(b)(1)", "at least every nine years; six years from the certificate of occupancy for a building whose permit application was on or after the (k) date; "
                                       "the earliest day the record shows, never earlier", "due_on"),
          record="the due day and what it comes under, or the question for a building with no date on record",
          why="The page gives this to jason (check:elevated-due, wanted). An unknown day is a question, never a guess."),
        s("engage", "Engage a licensed engineer or architect", D, S, ("due",), command="jason board",
          clock=_law("CIV 5551(b)(1)", "by a licensed structural or civil engineer or architect"),
          record="the board's decision record and the contract's library address",
          why="Starts a contract-notice-window run for the contract. CIV 4935(a) permits executive session for matters relating to "
              "the formation of contracts with third parties; the Work screens do not compose that handling, so only the decision is recorded here."),
        s("list", "Receive the random list of locations (before the first inspection)", W, M, ("engage",), skip=BY_MANAGER,
          why="CIV 5551(c): before the first visual inspection the inspector generates the list, kept for future use. Skipped, with the reason, after the first cycle."),
        s("inspect", "Wait for the inspection and the written report", W, M, ("engage",),
          clock=_person_day("the booked day", "inspect_on"), why="CIV 5551(i) sets the cycle; the booked day is a person's."),
        s("read", "Enter the date of inspection from page one of the report", P, M, ("inspect",), repeat=ITEM,
          clock=_law("CIV 5551(e)(5)(A)", "the report states the date of the inspection on its first page"),
          record="the date and the report named by its library address"),
        s("threat", "Does any element pose an immediate threat to occupants?", B, M, ("read",),
          choices=(i.choice("threat", "preventive"), i.choice("none")),
          clock=_law("CIV 5551(e)(5)(F)", "the report's first page states whether an element is an immediate threat"),
          why="Answered from the first-page count by a person; a threat makes `preventive` required."),
        s("preventive", "Prevent occupant access until repairs are inspected and approved", P, M, ("threat",),
          clock=_law("CIV 5551(g)(1)", "preventive measures 'immediately' (no number)"),
          record="the day access was prevented and how",
          why="The president or the manager acts; the manager records it. It cannot be skipped or paused."),
        s("reserve", "Incorporate the report into the reserve study", P, M, ("read",),
          clock=_law("CIV 5551(f)", "the report is incorporated into the reserve study"),
          record="the reserve study's library address showing it",
          why="The board and the study's preparer; `jason reserves` only reads."),
        s("keep", "Keep the reports for two cycles", P, M, ("read",), command="jason inspections",
          clock=_law("CIV 5551(i)", "all written reports are maintained for two inspection cycles as records of the association"),
          record="the report's library address"),
        s("next", "Wait for the next cycle", W, M, ("keep",), command="jason deadlines",
          clock=_law("CIV 5551(b)(1)", "the earliest next due day: nine years on, from the record", "next_due_on"),
          why="Opens the next run."),
    )
    phases = (
        i.phase("reach", "Which buildings", "reach", "facts", "due"),
        i.phase("inspect", "Engage and inspect", "engage", "list", "inspect", "read", "threat", "preventive"),
        i.phase("keep", "Reserve, keep, next", "reserve", "keep", "next"),
    )
    i.finish(steps, phases)
    return Workflow(key=ELEV, title="Exterior elevated elements inspection", family=FAMILY, subject="cycle", steps=steps,
                    dates=(_opt("due_on", "The next due day, from the building's record"),
                           _opt("inspect_on", "The booked inspection day"),
                           _opt("next_due_on", "The next cycle's earliest due day", after="due_on")),
                    phases=phases, procedure="")


# --- 2.5 contract-notice-window -------------------------------------------------------------------------------------

def contract_notice_window() -> Workflow:
    """A vendor or management agreement: terms read, both edges of each notice window, the renewal decision, the notice
    (page 2.5). Both edges are the contract's (basis documents); the delivery the clause names is part of the window."""
    i = _Ids(CNW)
    s = i.step
    end_path = ("draft", "approve", "send", "ack", "transition")
    steps = (
        s("read", "Read the terms of the contract", P, M, command="jason contract-terms FILE; jason contract-terms --library", sop="ingest#2",
          record="the terms reading's address (term, renewal, each notice's window, delivery, deliverables, findings)",
          why="The page makes this a job (job:contract-terms, wanted). A model is a person's choice, per document; Bedrock sends the words "
              "to AWS and refuses a confidential file unless allowed for the run. A clause the model proposes that is not in the text is dropped, with its reason."),
        s("confirm-term", "Check the term's start and end on the page", P, M, ("read",),
          clock=_docs("the term's end, as the contract's words give it", slot="term_ends"),
          record="the term's end and its source (recorded, implied, or needs input)", sop="onboard#18",
          why="Not skippable when the start is blank."),
        s("window", "Count each window back from the term's end, both edges, with the delivery", P, M, ("confirm-term",), repeat=ITEM,
          command="to add: jason contract-terms --window KEY", sop="onboard#18",
          clock=_docs("the window opens (the contract's words); the earliest day a notice counts", slot="window_opens"),
          record="per clause (non-renewal, termination without cause, breach and cure): opens, closes, delivery",
          why="The page gives this to jason (check:contract-window, wanted). A window has two edges; a notice outside either 'may not count'."),
        s("owed", "Read what the counterparty owes and whether it is on file", P, M, ("read",), command="jason contract-terms --list",
          record="the list: on file, not on file, not yet due",
          why="A deliverable worth tracking becomes a board item or a register row, a person's choice (check:contract-owed, wanted)."),
        s("licence", "Check the licence numbers against the board's page", P, M, ("read",), command="jason licenses", repeat=ITEM,
          clock=_person_day("each contract and each renewal"), record="the check's date; the paper's number is not 'valid'"),
        s("statement", "A management agreement: is the managing agent's written statement on file", P, M, ("read",),
          clock=_law("CIV 5375", "the statement is given 'in no event more than 90 days' before entering into the agreement; the earliest day it may be dated",
                     "agreement_on", -90),
          record="the statement's library address, or why none is needed (a renewal, or an agreement that is not a management agreement)",
          why="The page gives this to jason (check:contract-statement, wanted). No skip: a run for a renewal records that no statement is needed."),
        s("review", "Renew, renegotiate, re-bid, or end", D, S, ("window",), command="jason board",
          clock=_docs("before the window closes (the contract's words); a board meeting's notice is at least four days (CIV 4920(a))", slot="window_closes"),
          record="the board's decision record; no decision before the window closes is recorded as 'no action', not as a renewal",
          why="The lead time to reach an agenda is the board's. No skip."),
        s("choice", "Which path", B, M, ("review",), choices=(i.choice("end", *end_path), i.choice("renew", "renew")),
          why="End leads to the notice; renew or re-bid leads to the new agreement."),
        s("draft", "Draft the notice in the words, address, and delivery the clause names", P, M, ("choice",), repeat=ITEM,
          command="jason letter (fills a template Doc); #/approvals",
          record="the letter's address in the letter stages (draft, saved, requested, approved, sent)",
          why="From the contract-notice base template (wanted); a plan step when an approvals kind for a letter is registered."),
        s("approve", "Approve the letter's words", P, PRES, ("draft",), command="#/approvals", record="the letter's log entry",
          why="The officer the letter names; the president until a letter can name another."),
        s("send", "Send by the delivery the clause names; keep proof", P, M, ("approve",),
          clock=_docs("inside both edges of the window (the contract's words)", slot="window_closes"),
          record="the day, the method, and the proof of delivery's library reference",
          why="jason sends nothing. Not skippable."),
        s("ack", "Wait for the counterparty's acknowledgment", W, M, ("send",), command="jason gmail --sync",
          why="A follow-up when it does not come."),
        s("renew", "Record the renewal or the new agreement", P, S, ("choice",), record="the new contract's library address",
          why="Starts a new run for the new term."),
        s("transition", "For a change of manager: records, access, and vendors", P, PRES, ("choice",), sop="onboard#19", skip=BY_MANAGER,
          command="jason sop onboard", record="what was requested and from whom",
          why="The onboard procedure's last two steps (records under CIV 5205 as that procedure names it). Skipped, with the reason, when it is not a management agreement."),
    )
    phases = (
        i.phase("terms", "The terms", "read", "confirm-term", "window", "owed", "licence", "statement"),
        i.phase("decide", "Decide", "review", "choice"),
        i.phase("notice", "Give notice", "draft", "approve", "send", "ack", "transition"),
        i.phase("renew", "Renew", "renew"),
    )
    i.finish(steps, phases)
    return Workflow(key=CNW, title="A contract's notice window", family=FAMILY, subject="contract", steps=steps,
                    dates=(_opt("term_ends", "The term's end"),
                           _opt("window_opens", "The notice window opens"),
                           _opt("window_closes", "The notice window closes", after="window_opens"),
                           _opt("agreement_on", "The day the management agreement is entered")),
                    phases=phases, procedure="")


# --- 2.6 improvement-request ----------------------------------------------------------------------------------------

def improvement_request() -> Workflow:
    """An owner's improvement request from application to the unit's manual (page 2.6). The request touches a unit and an owner,
    so the run's subject is the request's own id (``imp-...``) and its label carries no unit and no name. A statute's day is
    set as a date by a person from the received day, and is the earliest-day count; jason never applies a deeming."""
    i = _Ids(IMP)
    s = i.step
    after_vote = ("conditions", "work", "verify", "manual", "findings")
    steps = (
        s("receive", "Enter the request and its received day", P, M, command="jason sync-catalog; jason respond; jason request-links --create THREAD --yes",
          record="the request's id (never an address or a name) and the received day",
          why="All clocks count from the received day. The channel and address are in the request record, not here."),
        s("track", "Set the track", B, M, ("receive",),
          choices=tuple(i.choice(k) for k in ("ordinary", "accessibility", "solar", "charger", "rebuild")), command="jason respond",
          why="By the kind rule; the manager sets it when the words do not say, and the run records who did. A request classified "
              "'other' leaves this open: the general clock and a question stand."),
        s("need", "Do the governing documents require approval for this change?", P, M, ("track",), command="jason applies",
          clock=_law("CIV 4765(a)", "applies 'if the governing documents require association approval'"),
          record="applies, does not apply, or undetermined with the missing fact",
          why="An undetermined answer is a question for the board or counsel."),
        s("ack", "Acknowledge the request", P, M, ("receive",), command="jason request-comment ID \"...\"",
          clock=_proposed("an acknowledgment time (proposed; never shown to an owner as a date)"),
          record="the day the owner was told",
          why="A comment posted by a person (plan:payhoa-comment, wanted); the command writes without --yes."),
        s("complete", "Record complete, or list what is missing", P, M, ("need",),
          clock=_law("CIV 4766(b)(1)", "rebuild: written notice of complete or incomplete no later than 30 calendar days after receipt; the latest day",
                     "rebuild_complete_by"),
          record="the determination (complete, or the items missing) and the day",
          why="Solar and charger: the deemed approval is excepted where the delay results from a reasonable request for additional "
              "information. Ordinary: the governing documents' time, else a proposed one. A rebuild's missed day deems it complete (the law's, not jason's)."),
        s("missing", "Send the list of missing items", P, M, ("complete",), skip=BY_MANAGER, command="#/approvals",
          record="the letter's address in the letter stages",
          why="From the incomplete-items-letter base template (wanted), posted by a person. Skipped, with the reason, when the request is complete as received."),
        s("wait-owner", "Wait for the owner's items", W, M, ("missing",), command="jason sync-request-files --requests N", skip=BY_MANAGER,
          why="Ended by a person's note of the arrival. Only a policy clock pauses, and a person records the pause."),
        s("review", "Read against the standards and earlier decisions", P, M, ("complete",), command="jason respond --sources",
          record="the review's address, with the reviewer's name and role",
          why="The reviewer role is proposed, not built (role:reviewer, wanted), so the manager records it; the recommendation stays the reviewer's."),
        s("agenda", "Place it on a noticed agenda", P, M, ("review",), command="jason board",
          clock=_law("CIV 4920(a)", "notice of the time and place of a board meeting at least four days before the meeting"),
          record="the board item's id and the meeting that meets the clock, computed and labeled as the earliest"),
        s("vote", "Approve, approve with conditions, or deny", D, S, ("agenda",), command="#/room, #/decisions",
          clock=_docs("ordinary: the governing documents' maximum time for a response (CIV 4765(a)(1)); solar and charger have their own statutory days (the run's clocks)",
                      "CIV 4765(a)(1)"),
          record="the decision record: motion, roll call by name, recusals",
          why="jason never sets approved or denied. No skip."),
        s("letter", "Draft, approve, and deliver the decision letter", P, M, ("vote",), command="#/approvals",
          clock=_law("CIV 4765(a)(4)", "a decision is in writing; a disapproval carries the reason and the reconsideration procedure"),
          record="the letter's address and the day it was delivered",
          why="From the decision-letter base template (wanted); the recording officer approves. Not skippable."),
        s("reconsider", "A denial: was reconsideration requested?", B, M, ("letter",), command="#/room",
          choices=(i.choice("asked"), i.choice("not-asked")),
          clock=_law("CIV 4765(a)(5)", "a disapproved change has a procedure for reconsideration by the board (the time is the documents', else proposed)"),
          why="A second decision is linked to the first."),
        s("conditions", "Record the conditions with due days", P, S, ("vote",), repeat=ITEM, skip=BY_SECRETARY,
          clock=_docs("the decision's own words; a charger in a common area: a certificate of insurance within 14 days of approval (CIV 4745(f)(1)(C))",
                      "CIV 4745(f)(1)(C)"),
          record="each condition and the proof it needs",
          why="Skipped, with the reason, for a denial or an approval with no conditions."),
        s("work", "Wait for the owner's start and finish", W, M, ("conditions",), skip=BY_MANAGER,
          clock=_proposed("an approval's lifetime (proposed)"), why="Entered 'as reported by the owner'."),
        s("verify", "Check the work against the approval", P, M, ("work",), skip=BY_MANAGER,
          record="the verification and its evidence; a difference is shown side by side, never as a violation",
          why="jason never inspects."),
        s("manual", "Link the entry in the unit's manual", P, M, ("verify",), skip=BY_MANAGER,
          record="the entry's reference (the entry's approval is the request's address)",
          why="Skipped, with the reason, when the owner declines or the request was denied."),
        s("findings", "Compute the five findings", P, M, ("manual",), skip=BY_MANAGER,
          why="The page gives this to jason (check:improvement-findings, wanted): approval without an entry, and the others, in their fixed words."),
    )
    phases = (
        i.phase("receive", "Receive and classify", "receive", "track", "need", "ack"),
        i.phase("complete", "Completeness", "complete", "missing", "wait-owner"),
        i.phase("decide", "Review and decide", "review", "agenda", "vote", "letter", "reconsider"),
        i.phase("after", "After the decision", *after_vote),
    )
    i.finish(steps, phases)
    return Workflow(
        key=IMP, title="An owner's improvement request", family=FAMILY, subject="request", steps=steps,
        dates=(DateSlot("received_on", "The day the request was received"),
               _opt("solar_by", "A solar request: the earliest statutory day, 45 days from receipt", after="received_on"),
               _opt("charger_by", "A charger request: the earliest statutory day, 60 days from receipt", after="received_on"),
               _opt("rebuild_complete_by", "A rebuild: the latest day to determine completeness, 30 calendar days from receipt",
                    after="received_on")),
        phases=phases, procedure="",
        clocks=(_law("CIV 714(e)(2)(B)", "solar: an application not denied in writing within 45 days of receipt is deemed approved, unless the delay is the result of a reasonable request for additional information",
                     "solar_by"),
                _law("CIV 4745(e)", "charger: an application not denied in writing within 60 days of receipt is deemed approved, unless the delay is willful or the result of a reasonable request for additional information",
                     "charger_by")))


# --- 2.7 paint-cycle ------------------------------------------------------------------------------------------------

def paint_cycle() -> Workflow:
    """The paint schedule against the maker's catalog and the repaint of a building group (page 2.7). The maker's catalog is
    one reader; another maker is 'not checked', never guessed."""
    i = _Ids(PAINT)
    s = i.step
    steps = (
        s("refresh", "Refresh the catalog copy", P, M, command="jason paint --refresh", clock=_proposed("the copy is kept a week"),
          record="the copy's age after the refresh",
          why="A job on a person's ask (job:paint-refresh, wanted); it reads the network."),
        s("watch", "Check each scheduled color against the catalog", P, M, command="jason paint --check", repeat=ITEM,
          clock=_proposed("quarterly, and with the January law review (proposed)"),
          record="per color: ok, renamed, discontinued, not found, or not checked",
          why="The page gives this to jason (check:paint-catalog, wanted); the command exits 1 on a difference. A rename after an award reads 'changed since' and opens `substitute`."),
        s("substitute", "Choose what substitutes for a renamed or discontinued color", D, S, ("watch",), repeat=ITEM, skip=BY_SECRETARY,
          command="jason paint --match \"CODE\" --exterior", record="the board's decision record",
          why="The law and the documents are silent, so a written policy is proposed; a rule on a CIV 4355(a) subject needs notice (CIV 4360(a), "
              "at least 28 days). The closest current colors are listed as options, none recommended. Skipped, with the reason, when `watch` found nothing."),
        s("dates", "Read next due and cost from the reserve study", P, M, command="jason paint --json", repeat=PERIOD,
          clock=_docs("the reserve study"), record="the study's address; last painted is 'needs input' unless a recorded event is attached"),
        s("scope", "Prepare the per-building sheet for the vendor", P, M, ("substitute",), repeat=ITEM,
          record="the sheet's library address (surface, code, name, sheen)"),
        s("bids", "Collect proposals and read their terms", W, M, ("scope",), command="jason contract-terms --library",
          why="Ended by a person's note that the proposals are in the library."),
        s("award", "Award the work", D, S, ("bids",), command="jason board", record="the board's decision record",
          why="Starts a contract-notice-window run for the contract. No skip."),
        s("notice", "Tell owners what to expect", P, M, ("award",), repeat=ITEM, clock=_docs("the governing documents (not read here)"),
          record="the notice's reference, per building",
          why="A draft a person sends; `jason notices` then reads its delivery."),
        s("record", "Record last painted by building, with the invoice", P, M, ("notice",), repeat=ITEM,
          command="jason incidents --work improvement", record="the event's address and the invoice's library reference",
          why="An improvement event on a building; a person confirms it before it is cited."),
        s("doc", "Refresh the palette Doc and page", P, M, ("record",), command="jason paint --to-doc --yes; jason paint --page",
          record="the Doc's address", why="Replaces edits made in the Doc (plan:doc-write, wanted)."),
        s("request", "Side path: an owner's color request", B, M, spawns=IMP, repeat=ITEM,
          choices=(i.choice("request"), i.choice("none")), command="to add: jason paint --request CODE --surface S --building B",
          why="Opens an improvement-request run; the check says whether the color is on the schedule for this surface, for another, near, or not on it."),
    )
    phases = (
        i.phase("watch", "Watch the catalog", "refresh", "watch", "substitute", "dates"),
        i.phase("repaint", "The repaint", "scope", "bids", "award", "notice", "record", "doc"),
        i.phase("request", "A color request", "request"),
    )
    i.finish(steps, phases)
    return Workflow(key=PAINT, title="The paint cycle", family=FAMILY, subject="schedule", steps=steps, dates=(), phases=phases,
                    procedure="")


# --- 2.8 loss-claim -------------------------------------------------------------------------------------------------

def loss_claim() -> Workflow:
    """An incident or insurance claim: history, carrier, the five-question packet, outcome (page 2.8). jason decides neither
    coverage nor fault. A loss touches a unit and an owner, so the run's subject is the incident's own id and its label carries
    no unit and no name; a step asks for a record by its address or id."""
    i = _Ids(LOSS)
    s = i.step
    steps = (
        s("record", "Record the incident: what, where, found when", P, M, command="to add: jason incidents --record",
          record="the incident's id (never an address or a name)",
          why="Today incidents are only read from paperwork; a person-entered record is wanted (command:jason incidents --record)."),
        s("history", "Read what the paperwork shows: cause, element, standing", P, M, ("record",),
          command="jason incidents --address \"123 Main\" --all; jason incidents --link",
          record="the event: claimed, claim candidate, under deductible, sudden with cost unknown, or none",
          why="A standing is a lead. The deductible is the policy's. A claim on another's policy is kept apart."),
        s("mitigate", "Stop the loss and secure the area", P, M, ("record",), clock=_person_day("at once while water or fire is active"),
          record="the vendor's papers' library address and the day", why="Not skippable when water or fire is active."),
        s("policy", "Read which policy applies, its deductible, and its notice conditions", P, M, ("record",), command="jason insurance",
          clock=_docs("the policy; its notice-of-loss words are not read unless the pages are on disk"), repeat=PERIOD,
          record="the policy's address and the pages recited"),
        s("notify", "Notify the carrier or agent", P, M, ("policy",), clock=_docs("the policy's words (no statute for this step was found in this family)"),
          record="the claim number and the library reference of what was sent", why="Not skippable."),
        s("packet", "Assemble the five-question loss packet", P, M, ("record",), repeat=ITEM,
          command="GET /api/loss-packet?unit=&incident=",
          record="the packet's reference; each step with its provisions recited and what the record shows",
          why="The page gives this to jason (check:loss-packet, wanted). Held notes read, for example, 'no deductible guideline adopted'."),
        s("confirm-step", "Confirm each of the five steps", P, M, ("packet",), repeat=ITEM,
          command="POST /api/write/loss-packet/confirm", record="the step confirmed, by name and day", why="jason confirms nothing."),
        s("guideline", "The board's deductible guideline: adopted, or a gap", D, S, ("packet",), command="jason rule-change",
          record="the board's decision record, or the policy proposed",
          why="A rule on a CIV 4355(a) subject needs notice before adoption (CIV 4360(a)). No skip."),
        s("ask-owner", "Ask the owner what the item was", P, M, ("packet",), repeat=ITEM, skip=BY_MANAGER,
          record="the draft's reference", why="A draft a person sends (plan:gmail-drafts/owner-request, wanted). Skipped, with the reason, when the packet needs nothing more."),
        s("outcome", "Wait for the carrier's outcome", W, M, ("notify",), command="jason insurance",
          clock=_docs("the policy and the carrier's letters"),
          why="A claim paper: settlement, denial, closed, or primacy. A follow-up when the carrier is silent."),
        s("members", "Did coverage lapse, reduce, or the deductible rise?", B, M, ("outcome",),
          choices=(i.choice("yes"), i.choice("no")), command="jason notices",
          clock=_law("CIV 5810", "individual notice to all members, as soon as reasonably practicable, if a policy described in the annual budget report has lapsed, "
                                 "been canceled, and is not immediately renewed, restored, or replaced"),
          why="Answered from the renewal record. Yes: a member-notice run from the insurance-change-notice base template."),
        s("close", "Record the outcome and what to learn", P, M, ("outcome", "members"), command="jason incidents --link; jason lessons",
          record="the incident's links stored; the lesson added, if one is warranted"),
    )
    phases = (
        i.phase("record", "Record and read", "record", "history", "mitigate", "policy", "notify"),
        i.phase("packet", "The packet", "packet", "confirm-step", "guideline", "ask-owner"),
        i.phase("outcome", "Outcome", "outcome", "members", "close"),
    )
    i.finish(steps, phases)
    return Workflow(key=LOSS, title="A loss or insurance claim", family=FAMILY, subject="incident", steps=steps, dates=(),
                    phases=phases, procedure="")


# --- 2.9 maintenance-program ----------------------------------------------------------------------------------------

def maintenance_program() -> Workflow:
    """A maintenance program the profile declares (page 2.9); pest control is the worked case. The vacating notice has the two
    edges of CIV 4785(b)."""
    i = _Ids(PROG)
    s = i.step
    steps = (
        s("standing", "Is the program adopted?", P, M, command="to add: jason programs",
          record="the document, the adoption, and the implementation, each in its own word",
          why="'No act on record' is not 'not adopted' (check:program-standing, wanted)."),
        s("adopt", "Adopt it, if the governing documents make it optional", D, S, ("standing",), skip=BY_SECRETARY, command="jason board",
          clock=_docs("the declaration"), record="the board's decision record",
          why="A vendor proposal's approval is implementation evidence, not an adoption. Skipped, with the reason, when already adopted."),
        s("sync", "Read the vendor's portal", P, M, ("adopt",), command="jason vendors --sync", repeat=PERIOD,
          clock=_person_day("the cadence a person adopted (jason cadence)"),
          record="the visits, products, and reports on disk, or the sync's failure",
          why="A job when job:vendor-portal-sync is registered. A failed sync shows the last good read and its age; it is never repeated on a timer."),
        s("read", "Read visits, products, activity, and label limits", P, M, ("sync",), command="jason pests; jason pests --fetch", repeat=PERIOD,
          clock=_docs("the label limits as stored"),
          record="the brief's address; a finding is a question (an interval between treatments, a landscape use)"),
        s("ask", "Ask the vendor what the record cannot show", P, M, ("read",), skip=BY_MANAGER,
          record="the draft's reference", why="A draft a person sends (plan:gmail-drafts/vendor-question, wanted). Skipped, with the reason, when no finding stands."),
        s("licence", "Check the vendor's licence and insurance on the board's page", P, M, ("sync",), command="jason licenses", repeat=ITEM,
          clock=_person_day("before each contract and each renewal"), record="the check's date"),
        s("vacate", "Does treatment need occupants out?", B, M, ("read",), choices=(i.choice("yes", "vacate-notice"), i.choice("no")),
          repeat=ITEM,
          clock=_law("CIV 4785(b)", "the earliest day to give notice: 30 days before the date of the temporary relocation", "relocation_on", -30),
          why="Answered by a person from the vendor's plan."),
        s("vacate-notice", "Give notice to occupants and owners", P, M, ("vacate",), repeat=ITEM,
          clock=_law("CIV 4785(b)", "the latest day to give notice: 15 days before the date of the temporary relocation", "relocation_on", -15),
          record="the notice's reference, with the reason, the times, and that occupants bear their own accommodations",
          why="From the vacate-notice base template (wanted), delivered by a person; `jason notices` then reads its delivery. Not skippable."),
        s("complaint", "Route a complaint: common area or owner", P, M, repeat=ITEM, clock=_docs("the declaration decides who handles it"),
          record="who handles it"),
        s("renewal", "Renewal or re-bid", B, M, ("read",), spawns=CNW, choices=(i.choice("renew"), i.choice("none")),
          clock=_docs("each term, as the contract's words give it"),
          why="Renewing opens a contract-notice-window run."),
        s("review", "Review the year", P, S, ("read",), command="jason lessons", clock=_proposed("yearly (proposed)"),
          record="the board item's id and the lessons recorded"),
    )
    phases = (
        i.phase("adopt", "Adopt", "standing", "adopt"),
        i.phase("read", "Read the program", "sync", "read", "ask", "licence"),
        i.phase("treat", "Treatments and complaints", "vacate", "vacate-notice", "complaint"),
        i.phase("renew", "Renew and review", "renewal", "review"),
    )
    i.finish(steps, phases)
    return Workflow(key=PROG, title="A maintenance program", family=FAMILY, subject="program", steps=steps,
                    dates=(_opt("relocation_on", "The date of the temporary relocation"),), phases=phases, procedure="")


BUILDERS: tuple[Callable[[], Workflow], ...] = (
    life_safety_period, deficiency, backflow_annual, elevated_elements, contract_notice_window, improvement_request,
    paint_cycle, loss_claim, maintenance_program,
)

__all__ = ["BUILDERS", "FAMILY", "LEFT_OUT", "ORDER", "WANTED", "backflow_annual", "contract_notice_window", "deficiency",
           "elevated_elements", "improvement_request", "life_safety_period", "loss_claim", "maintenance_program", "paint_cycle"]
