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
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from jason.workflows import definitions
from jason.workflows.readers import JOBS, named_check
from jason.workflows.types import (
    ClockBasis, ClockDef, DateSlot, Elapsed, Phase, Role, SkipRule, StepDef, StepKind, Workflow,
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


GENERAL: tuple[Callable[[], Workflow], ...] = (owner_info_cycle,)


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
    resolver = resolve_law if resolve_law is not None else shelf_resolver(data_dir)
    return tuple(definitions.register(build(), plan_kinds=plan_kinds, jobs=jobs if jobs is not None else set(JOBS),
                                      resolve_law=resolver) for build in GENERAL)


__all__ = ["GENERAL", "OI", "owner_info_cycle", "register_general", "shelf_resolver"]
