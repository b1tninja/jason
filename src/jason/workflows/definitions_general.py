"""The general workflow definitions, registered when asked (``register_general``), never at import.

Each is a row built from a family page (docs/workflows/) and the procedure it follows (``jason.community.procedures``).
They name no association: a run's dates are slots asked at start, a statute is cited by key (``CIV 4041(b)(1)``) and checked
against the authorities shelf, and a person who acts is whoever holds the role.

``owner-info-cycle`` is the annual owner-information request (docs/workflows/members-cycles.md, section 2.1). Its ids are
``owner-info-cycle.N`` with N the table's OI-NN; the response-intake group (IN) has no place in the table's numbering, so its
board decision and its recording plan are ``owner-info-cycle.17.6`` and ``owner-info-cycle.17.7`` (IN-06 and IN-07), and
``owner-info-cycle.17`` stands for the rest of the group (IN-01 to IN-05, IN-08, IN-09). Where the table names an approvals kind
or a child definition that is not built, the step is a ``person`` step with the command shown (the step's ``why`` says which
kind it becomes); it is never a plan that nothing can make.

``control-adoption`` is one control's way from jason's suggestion to the day it binds (docs/controls.md, section 4). Its ids are
``control-adoption.N`` for N from 1 to 8, the run's subject is ``control:KEY``, and it asks no date at start: the board names the
effective date, and the control's own record holds it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from jason.workflows import definitions
from jason.workflows.readers import JOBS, named_check
from jason.workflows.types import (
    Choice, ClockBasis, ClockDef, DateSlot, Elapsed, Phase, Role, SkipRule, StepDef, StepKind, Workflow,
)

OI = "owner-info-cycle"
ENTRY = ClockDef(ClockBasis.LAW, "reports_mailed", -30, cite="CIV 4041(b)(1)", label="enter the answers in the books")


def sid(n: str) -> str:
    return f"{OI}.{n}"


def _step(n: str, title: str, kind: StepKind, role: Role, needs: tuple[str, ...] = (), **more: Any) -> StepDef:
    return StepDef(sid(n), title, kind, role=role, needs=tuple(sid(x) for x in needs), **more)


def owner_info_cycle() -> Workflow:
    P, C, J, PL, D, W = StepKind.PERSON, StepKind.CHECK, StepKind.JOB, StepKind.PLAN, StepKind.DECISION, StepKind.WAIT
    M, A, S = Role.MANAGER, Role.ADMINISTRATOR, Role.SECRETARY
    by_manager = SkipRule((M,))
    steps = (
        # --- A. Set up
        _step("1", "Set the cycle's dates", P, A, command="jason owner-info", sop=f"{OI}#1", record="the profile's cycle row, with the dates",
              why="The profile's cycle row holds the dates; a person edits it, jason does not (lesson leave-room-to-correct)."),
        _step("2", "Check the dates leave room for one correction before the return-by date", C, Role.JASON, ("1",),
              check=named_check("dates-room"), command="jason owner-info", sop=f"{OI}#1", skip=SkipRule((M, A)),
              why="No minimum is adopted: the follow-ups use 1 day to sync and 3 to resend (proposed policy); a person records why not."),
        _step("3", "Settle the decisions the cycle depends on: rental approvals, what to ask likely non-owner-occupied units, co-owner envelopes",
              D, S, ("1",), command="jason board --packet", sop=f"{OI}#2", record="the board's decision record or the minutes",
              why="The law is silent, so the board decides; undecided questions stay held and never block the send."),
        _step("4", "Open the cycle's campaigns, one a channel, each naming its form, version, and handler", P, M, ("1",),
              command="jason campaigns --open FORM --channel C --cycle-year Y --by NAME", sop=f"{OI}#10",
              record="the campaign codes opened", evidence=("file:forms/campaigns.json",),
              why="Every generator refuses a form with no open campaign (lesson reference-made-before-a-handler-was-chosen)."),
        _step("5", "Update the PayHOA form in place and confirm it is live and locked", P, M, ("4",),
              command="jason forms --payhoa owner-info --update", sop=f"{OI}#3", record="the form's lock entry",
              evidence=("file:payhoa/forms.json",),
              why="A linked form is never replaced (lesson paper-cannot-require); this becomes a plan step when an approvals kind for a form update is registered."),
        _step("6", "Round-trip made-up answers as the test owner", J, M, ("5",), job="payhoa-form-test", sop=f"{OI}#4",
              command="jason forms --payhoa-test owner-info --yes",
              why="Every answer must read back before an owner sees the form."),
        _step("7", "Open each form link and QR target as an owner, signed out and signed in", P, M, ("5",), sop=f"{OI}#5",
              record="the date and each link opened", why="The link must carry the unit and land on the form (lessons form-link-needs-unit, test-as-an-owner)."),
        _step("8", "Build the letter and the fillable form from the template Docs", P, M, ("5",), sop=f"{OI}#6",
              command="jason packet owner-information --year YEAR --make-templates --yes; then --build --yes",
              record="the Docs and PDFs built, with the page count",
              why="Four pages at most: a sixth billed page adds postage; this becomes a plan step when an approvals kind for a Doc is registered."),
        _step("9", "Plan who gets what: email, letter, or both, and the occupancy signals", J, M, ("4",), job="owner-info-send-plan",
              sop=f"{OI}#7", command="jason owner-info --send-plan", evidence=("glob:owner-info/send-plan-*.md",),
              why="The plan names counts and units, never addresses."),
        _step("10", "Write the email, the guide, and the letter once", P, M, ("9",), sop=f"{OI}#8",
              command="jason broadcast data/drafts/NAME.md --to-doc --yes", record="the Doc on the letterhead",
              why="One Markdown source makes the email, the Doc, and the PDF (lessons one-source-per-document, name-the-unit); a child owner-document run follows when that definition exists."),
        _step("11", "Preview one owner's email, then send a test to yourself", J, M, ("10", "4"), job="owner-info-email-test", sop=f"{OI}#9",
              command="jason owner-info --email-batch --message NAME.md --only me --preview OUT.html; then --yes",
              why="The subject names the unit, every form link carries ;unitId=, and the pictures show."),
        # --- B. Send
        _step("12", "Send the email batch", P, M, ("11", "7"), sop=f"{OI}#11",
              command="jason owner-info --email-batch --message NAME.md --yes --confirmed-by NAME",
              record="the batch key, and the second person who confirmed it",
              why="No statutory day to send; mail that cannot be recalled needs a second person; this becomes a plan step when an approvals kind for the email batch is registered."),
        _step("13", "Read the emails' delivery", J, M, ("12",), job="notices-sync", sop=f"{OI}#12",
              command="jason notices owner-info-YEAR --sync", clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="the day after the send"),
              why="A bounced email is silent until synced (lesson bounces-are-silent); a child notice-delivery run follows when that definition exists."),
        _step("14", "Wait for every email's delivery result", W, M, ("12",), check=named_check("delivery-read"), sop=f"{OI}#12",
              clock=ClockDef(ClockBasis.PROPOSED_POLICY, label="PayHOA fails a message with no delivery event after 24 hours"),
              why="Ends when the notice ledger holds an outcome for every emailed copy, or a person notes the arrival."),
        _step("15", "The next day, test the emailed link as an owner again", P, M, ("14",), sop=f"{OI}#13",
              record="the date and the link opened", why="Only then are the letters mailed (lesson letters-cannot-be-recalled)."),
        _step("16", "Mail the letters, one Mailroom send per building", P, M, ("15", "13"), sop=f"{OI}#13",
              command="jason owner-info --mail-batch --yes --confirmed-by NAME",
              record="the batch key, the count and cost in cents, and the second person who confirmed it",
              why="A mailed letter cannot be recalled (lessons letters-cannot-be-recalled, letter-link-per-unit); jason never starts it; this becomes a plan step when an approvals kind for the mail batch is registered."),
        # --- C. Collect and record (group IN)
        _step("17", "Collect, read, and confirm the answers from every channel, and triage them by the response policy", P, M, ("12",),
              command="jason responses --check; jason responses --list --new; jason responses --read ID --by NAME; jason responses --confirm ID --by NAME",
              sop=f"{OI}#14", record="the arrivals read and confirmed (a count or ids)",
              why="A reading is evidence for a person; nothing is an answer until a person confirms it (lesson returns-by-the-same-rules)."),
        _step("17.6", "Decide what only the board decides: a co-owner's answer for the others, an occupancy answer the tag does not show, a blank required answer",
              D, S, ("17",), command="jason board", sop=f"{OI}#16", record="the board's decision record or the minutes",
              why="The law is silent and the answers need a policy (lesson answers-need-a-policy); each is held and never approved by a click."),
        _step("17.7", "Record the answers: a plan decided item by item by a named person, applied only if nothing changed", PL, M, ("17", "17.6"),
              plan_kind="owner-info-tags", command="jason approvals plan owner-info-tags --by NAME", sop=f"{OI}#17",
              clock=ENTRY, why="Enter the answers at least 30 days before the 5300 and 5310 disclosures (CIV 4041(b)(1)); complete a request only after its writes (lesson complete-only-after-writes)."),
        # --- D. Follow up and close
        _step("18", "Read what is due and who is outstanding", C, Role.JASON, ("12",), check=named_check("outstanding-read"),
              command="jason followups; jason campaigns --show CODE", sop=f"{OI}#15",
              why="An owner who answered by any method is not outstanding; an unreachable owner is listed apart, never hidden; nothing is marked done except by a person."),
        _step("19", "Remind the owners who have not answered", P, M, ("18",), sop=f"{OI}#18", skip=by_manager,
              command="jason owner-info --email-batch --follow-up reminder --message REMINDER.md",
              record="the reminder batch key, and the second person who confirmed it",
              clock=ClockDef(ClockBasis.PROPOSED_POLICY, "return_by", -7, label="remind (proposed: 7 days before return-by)"),
              why="Skipped, with the reason, when nobody is outstanding; jason never marks the follow-up done."),
        _step("20", "Resend or ask for what failed", P, M, ("13",), sop=f"{OI}#12",
              command="jason notices owner-info-YEAR; jason owner-info --mail-batch --only UNIT --resend --yes --confirmed-by NAME",
              record="the count of members owed, and what was sent",
              clock=ClockDef(ClockBasis.PROPOSED_POLICY, cite="CIV 4041(e)", label="the law requires the resend, not a number of days (proposed: 3 days after the outcome)"),
              why="A bounced email is resent to a mailing or email address the member identified (CIV 4041(e)); record 0 owed when none is."),
        _step("21", "The return-by date", W, M, ("12",), clock=ClockDef(ClockBasis.PERSON, "return_by", 0, label="answers asked by"),
              elapsed=Elapsed.ENDS, why="The association's date; the date ends the wait."),
        _step("22", "Last day to enter the answers: nothing unread, nothing confirmed and unrecorded, no plan open", C, Role.JASON, ("17.7", "21"),
              check=named_check("entry-day-gap"), command="jason owner-info; jason responses --list", sop=f"{OI}#19", clock=ENTRY,
              why="At least 30 days before the 5300 and 5310 disclosures (CIV 4041(b)(1)); a gap is a finding for the board, not a write."),
        _step("23", "Close the cycle: move out the Unconfirmed Address records no owner confirmed, note what is open, close the campaigns", P, M, ("22",),
              command="jason campaigns --close CODE --by NAME", sop=f"{OI}#19", record="the campaigns closed, and what is left open",
              clock=ClockDef(ClockBasis.PROPOSED_POLICY, "return_by", 7, label="close (proposed: 7 days after return-by)"),
              why="The removal in PayHOA is a person's, or an item of the owner-info-tags plan."),
        _step("24", "The annual reports go out", W, M, ("22",),
              clock=ClockDef(ClockBasis.PERSON, "reports_mailed", 0, cite="CIV 5300", label="reports mailed (the association's date; CIV 5300 and 5310)"),
              why="Ends when a person notes the mailing; the day is the profile's."),
        _step("25", "Write the lessons and update the procedure", P, A, ("23",), command="jason lessons --area owner-info",
              sop=f"{OI}#20", record="the lessons added, with their status",
              why="A fixed lesson names its guard; the procedure step names the lesson."),
    )
    ids = {s.id for s in steps}
    phases = (
        Phase("set-up", "Set up", tuple(sid(n) for n in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"))),
        Phase("send", "Send", tuple(sid(n) for n in ("12", "13", "14", "15", "16"))),
        Phase("collect", "Collect and record", tuple(sid(n) for n in ("17", "17.6", "17.7"))),
        Phase("close", "Follow up and close", tuple(sid(n) for n in ("18", "19", "20", "21", "22", "23", "24", "25"))),
    )
    assert all(x in ids for p in phases for x in p.steps)
    return Workflow(
        key=OI, title="The annual owner information request", family="members", subject="campaign", steps=steps,
        dates=(DateSlot("opens_on", "The cycle opens"), DateSlot("return_by", "Answers asked by", after="opens_on"),
               DateSlot("reports_mailed", "The annual reports are mailed", after="return_by")),
        phases=phases, procedure=OI)


CA = "control-adoption"


def cid(n: str) -> str:
    return f"{CA}.{n}"


def control_adoption() -> Workflow:
    """One control, from jason's suggestion to the day it binds (docs/controls.md, section 4). One run a control: its subject
    is ``control:KEY``. No procedure covers it (``procedure`` is empty), no date is asked at start (the board names the
    effective date, and the control's own record holds it), and no statute sets a clock: the effective date is the board's
    (a ``person`` basis). jason suggests; the board decides at a meeting; the secretary records the decision; the date and
    the checks do the rest. A declined control closes the run: the steps after the outcome belong to the ``adopted`` path."""
    P, C, D, W, B = StepKind.PERSON, StepKind.CHECK, StepKind.DECISION, StepKind.WAIT, StepKind.BRANCH
    J, S, ANY = Role.JASON, Role.SECRETARY, Role.ANYONE
    date_named = ClockDef(ClockBasis.PERSON, label="the effective date the board names")

    def step(n: str, title: str, kind: StepKind, role: Role, needs: tuple[str, ...] = (), **more: Any) -> StepDef:
        return StepDef(cid(n), title, kind, role=role, needs=tuple(cid(x) for x in needs), **more)

    steps = (
        step("1", "Suggest: jason read a provision and recorded the control as suggested", C, J, check=named_check("control-suggested"),
             command="jason controls --show KEY",
             why="A suggestion is jason's reading of a provision, labeled as a reading; it adopts nothing (docs/controls.md, section 1)."),
        step("2", "Put it before the board: a board item with the provision as its evidence", P, ANY, ("1",),
             command="jason controls --propose KEY --by NAME", record="the board item id (control-KEY)",
             why="Any board member may put a suggestion before the board; this is all a person does with it here, and it adopts nothing."),
        step("3", "The board decides at a meeting; the secretary records the decision", D, S, ("2",),
             record="the decision id in the decisions store",
             why="The board adopts, declines, or defers; jason never decides. Tabled or continued is recorded and leaves this step open."),
        step("4", "Record the outcome: the control's act log shows adopted or declined, with the decision id", B, J, ("3",),
             check=named_check("control-outcome"),
             choices=(Choice("adopted", tuple(cid(n) for n in ("5", "6", "7", "8"))), Choice("declined", ())),
             why="The secretary records it with jason controls --adopt, --decline, or --defer (the meeting, the decision id and, "
                 "for an adoption, the effective date; nothing is written without --yes). A declined control ends the run here."),
        step("5", "Set the effective date the board named", P, S, ("4",), record="the effective date, YYYY-MM-DD", clock=date_named,
             why="The board names the date (docs/controls.md, section 8); it is in the adoption act, and the secretary confirms it is the one named."),
        step("6", "Check the roster can satisfy it (a warning; nothing is blocked)", C, J, ("5",), check=named_check("control-roster"),
             command="jason controls --roster-check KEY", skip=SkipRule((S,)),
             why="If the roster lacks an office the control needs, the board is warned before the date; the control still binds from it."),
        step("7", "In force: wait for the effective date", W, J, ("6",), check=named_check("control-in-force"), clock=date_named,
             why="jason turns nothing on; the date and the check do. From the date the control binds, and an act the roster cannot satisfy is refused."),
        step("8", "Review it each year with the board's other standing decisions", W, S, ("7",), check=named_check("control-retired"),
             clock=ClockDef(ClockBasis.PERSON, label="a year after it takes effect, and each year (the duty schedule keeps the cadence)"),
             why="Ends when the secretary notes the first yearly review held, or the board retires the control (a decision of its own)."),
    )
    phases = (
        Phase("suggest", "Suggest and propose", tuple(cid(n) for n in ("1", "2"))),
        Phase("decide", "The board decides", tuple(cid(n) for n in ("3", "4"))),
        Phase("effect", "Take effect", tuple(cid(n) for n in ("5", "6", "7"))),
        Phase("review", "Review", (cid("8"),)),
    )
    return Workflow(key=CA, title="Adopt a control", family="board", subject="control", steps=steps, dates=(), phases=phases,
                    procedure="")


GENERAL: tuple[Callable[[], Workflow], ...] = (owner_info_cycle, control_adoption)


def shelf_resolver(data_dir: Path | str | None) -> Callable[[str], "bool | None"] | None:
    """A ``validate`` resolver for a law clock's citation: true when the section is on the authorities shelf, false when the
    shelf holds its code and not the section, ``None`` (cannot tell) when the shelf is not here. ``None`` with no folder."""
    if data_dir is None:
        return None
    root = Path(data_dir)

    def resolve(cite: str) -> "bool | None":
        code = cite.strip().split(" ", 1)[0]
        if not (root / "authorities" / code).is_dir():
            return None
        try:
            from jason.community import law_text

            return bool(law_text.versions(cite, root))
        except Exception:  # noqa: BLE001 - a shelf that cannot be read cannot tell
            return None
    return resolve


def register_general(data_dir: Path | str | None = None, *, plan_kinds: Any = None, jobs: Any = None,
                     resolve_law: Any = None) -> tuple[Workflow, ...]:
    """Register the general definitions (replacing a row with the same key) and return them. Called by ``jason workflow``
    when it lists or starts a run, never at import. Each is checked: its plan kinds against the approvals registry (or
    ``plan_kinds``), its jobs against ``JOBS`` (or ``jobs``), its statutes against the shelf in ``data_dir`` (or
    ``resolve_law``). A row that fails raises ``InvalidWorkflow`` naming the step."""
    from jason.workflows import checks
    from jason.workflows.defs import all_builders

    checks.load_all()                                  # the reads a step may name register themselves
    resolver = resolve_law if resolve_law is not None else shelf_resolver(data_dir)
    return tuple(definitions.register(build(), plan_kinds=plan_kinds, jobs=jobs if jobs is not None else set(JOBS),
                                      resolve_law=resolver) for build in (*GENERAL, *all_builders()))


__all__ = ["CA", "GENERAL", "OI", "cid", "control_adoption", "owner_info_cycle", "register_general", "shelf_resolver"]
