"""Standard operating procedures: a task's steps in order, each with the command that does it, what to check, and where
to read more. A procedure is an index into the reference material (docs, reports, lessons) for one job, so whoever
runs it next year, a person or an agent, starts from the last time's knowledge rather than from memory.

``jason sop`` lists them; ``jason sop KEY`` prints one, its steps, and the lessons still open in its areas
(``jason.community.lessons``); ``{REPORT:sop key=KEY}`` carries one into a document. A step that a lesson changed names
that lesson, so the reason travels with the step. General procedures are here; a community's own (its dates, its
board's habits) are its specification's (``Community.procedures()``).
"""

from __future__ import annotations

from dataclasses import dataclass

from jason.community.lessons import Area


@dataclass(frozen=True)
class Step:
    do: str                              # what to do, in a sentence
    command: str = ""                    # the command that does it, if any
    check: str = ""                      # what to look at before going on
    refs: tuple[str, ...] = ()           # docs, reports ({REPORT:...}), or other procedures to read
    lessons: tuple[str, ...] = ()        # lesson keys that shaped this step
    person: bool = False                 # a person's step: jason does not do it


@dataclass(frozen=True)
class Procedure:
    key: str
    title: str
    when: str                            # when it is run
    areas: tuple[Area, ...]
    purpose: str
    steps: tuple[Step, ...]
    refs: tuple[str, ...] = ()           # the main reading for the whole procedure


PROCEDURES: tuple[Procedure, ...] = (
    Procedure(
        "owner-info-cycle", "The annual owner information request (Civil Code 4041)",
        "Each year: open in mid-September; answers by late October; entered in PayHOA by November 1.",
        (Area.OWNER_INFO, Area.FORMS, Area.EMAIL, Area.MAILROOM),
        "Ask every owner how to deliver notices, a second address, any representative, and occupancy; record the "
        "answers in PayHOA at least 30 days before the annual reports.",
        (
            Step("Set the cycle's dates, leaving room for one correction before the answer-by date.",
                 refs=("OWNER_INFO_CYCLE in the specification's forms.py", "docs/owner-information.md"),
                 lessons=("leave-room-to-correct",)),
            Step("Settle the board's decisions the cycle depends on: rental approvals, what to ask likely "
                 "non-owner-occupied units, co-owner envelopes.", command="jason board --packet",
                 refs=("{REPORT:occupancy-signals}", "jason lessons --open --area owner-info"), person=True),
            Step("Update the PayHOA form in place (never replace a linked form), and confirm it is live and locked.",
                 command="jason forms --payhoa owner-info --update", check="questions kept their ids; help under 255 "
                 "characters", refs=("docs/forms.md",), lessons=("paper-cannot-require",)),
            Step("Round-trip made-up answers as the test owner.", command="jason forms --payhoa-test owner-info --yes",
                 check="every answer reads back"),
            Step("Open the form's link as an owner, in a private window, signed out and signed in.",
                 check="it lands on the form for the unit, not the dashboard", lessons=("form-link-needs-unit",
                 "test-as-an-owner"), person=True),
            Step("Build the letter and the fillable form from the template Docs.",
                 command="jason packet owner-information --year YEAR --make-templates --yes; then --build --yes",
                 check="four pages (a fifth billed page adds $2.25); the form prints the way online, not a link",
                 refs=("docs/packets.md",)),
            Step("Plan who gets what: email, letter, or both; and the occupancy signals.",
                 command="jason owner-info --send-plan", refs=("data/owner-info/send-plan-DATE.md",)),
            Step("Write the email in Markdown and keep its Doc on the letterhead.",
                 command="jason broadcast data/drafts/NAME.md --to-doc --yes",
                 refs=("docs/drafts-and-forms.md (one Markdown source)",), lessons=("one-source-per-document",
                 "name-the-unit")),
            Step("Preview one owner's email, then send yourself a test.",
                 command="jason owner-info --email-batch --message NAME.md --only me --preview OUT.html; then --yes",
                 check="the subject names the unit; every form link carries ;unitId=; the pictures show"),
            Step("Send the email batch.", command="jason owner-info --email-batch --message NAME.md --yes "
                 "--confirmed-by NAME", refs=("docs/batches.md",)),
            Step("Check for bounced or failed emails, and mail those owners.", lessons=("bounces-are-silent",)),
            Step("The next day, test the emailed link as an owner again; only then mail the letters.",
                 command="jason owner-info --mail-batch --yes --confirmed-by NAME",
                 check="the Mailroom preview's recipients and price", refs=("jason mailroom --prices",),
                 lessons=("letters-cannot-be-recalled", "letter-link-per-unit")),
            Step("Record the answers as they come in: dry run, then write.",
                 command="jason owner-info --apply --payhoa; then --yes",
                 check="each write's reason; a request left open says why", lessons=("returns-by-the-same-rules",
                 "same-as-unit-needs-no-person")),
            Step("Remind the owners who have not answered, a week before the answer-by date.",
                 command="jason owner-info --email-batch --follow-up reminder --message REMINDER.md"),
            Step("On the entry date, close the cycle: remove the unconfirmed addresses, and note what is still open.",
                 refs=("docs/owner-information.md",), person=True),
            Step("Write what went wrong or could be better as lessons, and update this procedure.",
                 command="jason lessons --area owner-info", refs=("AGENTS.md (Lessons and procedures)",)),
        ),
        refs=("docs/owner-information.md", "docs/forms.md", "docs/batches.md", "docs/payhoa-reports.md"),
    ),
    Procedure(
        "board-packet", "The board packet for a meeting",
        "Before each board meeting (the third Tuesday): a week ahead, and again the day before.",
        (Area.DOCUMENTS,),
        "Give the directors each open-session item researched, the standing reports, and the evidence, as of the "
        "meeting.",
        (
            Step("Bring the action items up to date: status, owner, meeting, notes.",
                 command="jason board --set ITEM --status 'on agenda' --meeting DATE",
                 refs=("docs/board-agenda.md",)),
            Step("Name reports in an item's notes rather than copying facts into them.",
                 command="jason board --set ITEM --notes \"commentary {REPORT:KEY} commentary\"",
                 refs=("jason report --list",)),
            Step("The day before, refresh the reports the items name, and catalogue PayHOA's packet runs.",
                 command="jason report --all --doc --yes; jason report treasurers-report period=previous-month --doc --yes",
                 check="no report is stale or failed; last month's Treasurer's Report has been run in PayHOA"),
            Step("Build the packet, and its private Doc on the letterhead.", command="jason board --packet --doc --yes",
                 check="executive session items are listed by title only"),
            Step("Draft the agenda from the last agenda Doc.", command="jason board --agenda DOC_ID --doc --yes",
                 refs=("docs/board-agenda.md",)),
            Step("Share the packet with the directors from Drive.", person=True),
        ),
        refs=("docs/board-agenda.md", "docs/payhoa-reports.md"),
    ),
    Procedure(
        "mailroom-letter", "A letter through PayHOA's Mailroom",
        "Whenever the association mails owners on paper.",
        (Area.MAILROOM,),
        "Print and mail a letter through PayHOA (Lob), charged to the association, without a letter that cannot be "
        "recalled going out wrong.",
        (
            Step("Keep the PDF to four pages (PayHOA's address page is billed; a sixth billed page adds $2.25).",
                 command="jason mailroom --prices", refs=("payhoa.pricing", "AGENTS.md (Boundaries)")),
            Step("Preview the recipients and the cost.", command="jason mailroom --pdf FILE --units UNITS",
                 check="each recipient and the price per letter"),
            Step("Test every link and QR code in the letter as its reader would.", person=True,
                 lessons=("test-as-an-owner", "form-link-needs-unit")),
            Step("Mail it, only on a person's word.", command="jason mailroom --pdf FILE --units UNITS --send --yes",
                 check="the batch's letters read back as processing", lessons=("letters-cannot-be-recalled",)),
            Step("If something is wrong, cancel at once: the window is minutes.",
                 command="jason mailroom --cancel LETTER_ID --yes"),
        ),
        refs=("AGENTS.md (Boundaries)",),
    ),
    Procedure(
        "owner-document", "An owner-facing document: email, guide, or notice",
        "Whenever the association writes to owners.",
        (Area.DOCUMENTS, Area.EMAIL),
        "Write it once and make the email, the Doc on the letterhead, and the PDF from the same file.",
        (
            Step("Write it in Markdown under data/drafts (pictures as ![alt](file){width=560}).",
                 refs=("docs/drafts-and-forms.md (one Markdown source)",), lessons=("one-source-per-document",)),
            Step("Keep its Doc on the letterhead for review.", command="jason broadcast FILE.md --to-doc --yes"),
            Step("For a page to post or attach, export the PDF.",
                 command="jason letter --markdown FILE.md --pdf OUT.pdf --yes", refs=("docs/letters.md",)),
            Step("Preview it as one recipient receives it before sending.", refs=("docs/batches.md",)),
        ),
    ),
    Procedure(
        "check-in", "Checking work into the public repositories",
        "Before any commit to jason or payhoa.",
        (Area.REPOSITORY,),
        "Keep the association's records and people's details out of public history.",
        (
            Step("Keep the community's facts in the private specification (mystique/), never in jason."),
            Step("Use made-up values in fixtures; the operator's own ids go in .env.",
                 refs=(".env.example",), lessons=("no-real-data-in-fixtures",)),
            Step("Scan what will be committed for names, personal emails, phone numbers, and ids.",
                 check="no owner or deed party, no personal mailbox, no signed link or token"),
            Step("Commit, and push only when the person says so.", person=True),
        ),
    ),
)


def procedures(community: object | None = None) -> tuple[Procedure, ...]:
    own = getattr(community, "procedures", lambda: ())() if community is not None else ()
    return PROCEDURES + tuple(own)


def find(key: str, community: object | None = None) -> Procedure | None:
    return next((p for p in procedures(community) if p.key == key), None)


def lines(proc: Procedure, community: object | None = None) -> list[str]:
    """A procedure as Markdown: its purpose, its steps with their commands, checks, and references, then the lessons
    still open in its areas."""
    from jason.community.lessons import Status, lessons

    out = [f"**{proc.title}.** {proc.purpose} _When:_ {proc.when}", ""]
    for n, s in enumerate(proc.steps, 1):
        text = f"{n}. {s.do}" + (" _(a person's step)_" if s.person else "")
        extra = []
        if s.command:
            extra.append(f"`{s.command}`")
        if s.check:
            extra.append(f"check: {s.check}")
        if s.refs:
            extra.append("see: " + "; ".join(s.refs))
        if s.lessons:
            extra.append("lessons: " + ", ".join(s.lessons))
        out.append(text + (" " + ". ".join(x[0].upper() + x[1:] if not x.startswith("`") else x for x in extra) + "."
                           if extra else ""))
    if proc.refs:
        out += ["", "Reading: " + "; ".join(proc.refs) + "."]
    open_ = [l for l in lessons(community) if l.status is not Status.FIXED and any(l.applies_to(a) for a in proc.areas)]
    if open_:
        out += ["", "Open lessons in its areas:"] + [f"- **{l.key}** ({l.status.value}): {l.change}" for l in open_]
    return out


__all__ = ["PROCEDURES", "Procedure", "Step", "find", "lines", "procedures"]
