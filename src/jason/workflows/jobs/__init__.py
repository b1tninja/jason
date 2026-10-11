"""The jobs a definition's ``job`` step may name: each is a *descriptor* of an existing jason command, nothing more.

A job step does not run anything. The engine never queues, starts, or runs a command: a person runs the command (or queues it,
``jason jobs add -- ARGS``), and the engine *recognizes* the queued job by its arguments (``readers.JobSpec.matches``) and reads
how it ended. So a job is registered by what its command line looks like: the first word (the jason command), the words it must
carry, and the words that make it a different act (``--yes`` is a write a person confirms by name; a job that carries it is not
this job). A command that writes outside jason (Drive, Google, PayHOA, a letter) is never described here; it is a ``plan`` step's
approvals kind, which is the board's call (``wanted.py`` lists them).

``DESCRIPTORS`` is every descriptor written. ``READY`` names the families whose descriptors are *registered*, that is, added to
``readers.JOBS``. A family joins ``READY`` in the same change that turns its person steps into job steps and updates its own
tests (each family's definition test pins its wanted names as *not yet* in ``JOBS``). ``wanted.py`` reports the rest as
"descriptor written, not yet registered". This module imports nothing; ``readers`` builds the ``JobSpec`` rows from it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobDescriptor:
    """``name`` is the job name a step carries. ``first`` is the jason command (the queue's first argument) and ``require`` the
    further words the command line must carry; ``forbid`` are words that make it another act. ``command`` is what a person runs,
    with placeholders in capitals. ``family`` is the family whose step wants it."""

    name: str
    family: str
    first: str
    require: tuple[str, ...] = ()
    forbid: tuple[str, ...] = ()
    command: str = ""

    @property
    def words(self) -> tuple[str, ...]:
        """The words the queue's arguments must carry: the command, then ``require``."""
        return (self.first, *self.require)


def _d(name: str, family: str, command: str, require: tuple[str, ...] = (), forbid: tuple[str, ...] = ()) -> JobDescriptor:
    return JobDescriptor(name, family, command.split()[1], require, forbid, command)


NO_WRITE = ("--yes",)
"""A command line with ``--yes`` is a write a named person confirmed: not the read these descriptors recognize."""

DESCRIPTORS: tuple[JobDescriptor, ...] = (
    # --- property -----------------------------------------------------------------------------------------------------
    _d("life-safety-read-report", "property", "jason models --filed", ("--filed",), NO_WRITE),
    _d("life-safety-propose", "property", "jason life-safety --propose", ("--propose",)),
    _d("contract-terms", "property", "jason contract-terms FILE", (), ("--list",)),
    _d("paint-refresh", "property", "jason paint --refresh", ("--refresh",), NO_WRITE),
    _d("vendor-portal-sync", "property", "jason vendors --sync", ("--sync",), ("--yes", "--drive", "--reports")),
    # --- members ------------------------------------------------------------------------------------------------------
    _d("notice-recipients-plan", "members", "jason delivery --notice RULE --ids FILE", ("--notice", "--ids"), NO_WRITE),
    _d("notices-sync-any-key", "members", "jason notices KEY --sync", ("--sync",)),
    _d("mailroom-preview", "members", "jason mailroom --pdf FILE --units UNITS", ("--pdf", "--units"),
       ("--send", "--cancel", "--yes")),
    _d("catalog-sync", "members", "jason sync-catalog", (), NO_WRITE),
    _d("respond-sources", "members", "jason respond --sources", ("--sources",), NO_WRITE),
    _d("form-library-check", "members", "jason form-library --check", ("--check",), NO_WRITE),
    _d("form-discover", "members", "jason discover-forms --read", ("--read",), ("--confirm",)),
    # --- board --------------------------------------------------------------------------------------------------------
    _d("meetings-sync", "board", "jason meetings --sync", ("--sync",)),
    _d("board-reports-refresh", "board", "jason report --all", ("--all",), NO_WRITE),
    _d("board-packet-build", "board", "jason board --packet", ("--packet",), NO_WRITE),
    _d("board-notice-draw", "board", "jason board --notice --date DATE", ("--notice", "--date"), NO_WRITE),
    _d("minutes-draft", "board", "jason board --minutes DATE", ("--minutes",), NO_WRITE),
    _d("rule-change-timeline", "board", "jason rule-change KEY --notice-date DATE", ("--notice-date",), NO_WRITE),
    _d("law-export", "board", "jason export-authorities"),
    _d("law-versions", "board", "jason law-history --versions --since YEAR --shelf", ("--versions",)),
    _d("outlines-fetch", "board", "jason outlines --fetch", ("--fetch",)),
    _d("conflict-leads", "board", "jason conflicts --leads", ("--leads",)),
    _d("law-sweep", "board", "jason law-history --sweep --since YEAR", ("--sweep",)),
    _d("cite-survey", "board", "jason cite --survey", ("--survey",)),
    _d("section-refs-scan", "board", "jason section-refs --scan", ("--scan",), NO_WRITE),
    _d("schedule-read-google", "board", "jason schedule --read-google", ("--read-google",), NO_WRITE),
    _d("schedule-evidence", "board", "jason schedule-evidence --all", ("--all",), ("--record",)),
    _d("duties-read", "board", "jason duties --documents --read", ("--documents", "--read"), NO_WRITE),
    _d("duties-fill-bearers", "board", "jason duties --documents --fill-bearers", ("--documents", "--fill-bearers"), NO_WRITE),
    _d("manual-classify", "board", "jason manual --classify", ("--classify",)),
    _d("manual-render", "board", "jason manual --render", ("--render",)),
    _d("revisions-fetch", "board", "jason revisions KEY --fetch --versions", ("--fetch",)),
    # --- money --------------------------------------------------------------------------------------------------------
    _d("bill-snapshot-fetch", "money", "jason invoices --fetch", ("--fetch",)),
    _d("bill-dry-run", "money", "jason sync-bills --dry-run", ("--dry-run",), NO_WRITE),
    _d("invoice-review-read", "money", "jason invoices", (), ("--fetch",)),
    _d("packet-plan", "money", "jason packet annual-disclosures --year YEAR", ("annual-disclosures",),
       ("--build", "--make-templates", "--yes")),
    _d("tax-catalog-sync", "money", "jason sync-tax"),
    # --- records ------------------------------------------------------------------------------------------------------
    _d("chronology", "records", "jason chronology --catalog NAME", ("--catalog",), NO_WRITE),
    _d("county-lookup", "records", "jason onboard --lookup", ("--lookup",), NO_WRITE),
    _d("documents-locate", "records", "jason onboard --locate", ("--locate",), NO_WRITE),
    _d("index-build", "records", "jason index --build", ("--build",)),
    _d("ingest-dry-run", "records", "jason ingest SOURCE", (), ("--apply", "--park", "--model")),
    _d("ingest-model", "records", "jason ingest SOURCE --model", ("--model",), ("--apply",)),
    _d("ingest-park", "records", "jason ingest SOURCE --park", ("--park",), ("--apply",)),
    _d("intake-scan", "records", "jason intake --scan", ("--scan",), ("--apply",)),
    _d("inspections-read", "records", "jason inspections"),
    _d("library-ocr-suggestions", "records", "jason intake --library-ocr", ("--library-ocr",), ("--apply",)),
    _d("living-build", "records", "jason living KEY --fetch --working", ("--fetch", "--working"), NO_WRITE),
    _d("models-as-of", "records", "jason models --as-of DATE", ("--as-of",), NO_WRITE),
    _d("parcel-history", "records", "jason instrument-graph --parcel APN", ("--parcel",)),
    _d("preflight", "records", "jason preflight FILE"),
    _d("provisions-recite", "records", "jason readings --recite CITATION", ("--recite",), NO_WRITE),
    _d("review-run", "records", "jason review TASK --collection KEY --ask QUESTION --run", ("--run",)),
    _d("revisions-history", "records", "jason revisions KEY", (), ("--fetch",)),
    _d("rules-find", "records", "jason rules --find --model", ("--find",)),
    _d("segments", "records", "jason segments FILE", (), NO_WRITE),
    _d("split-suggest", "records", "jason split ID --suggest", ("--suggest",), ("--apply", "--yes")),
    _d("sync-catalog", "records", "jason sync-catalog", (), NO_WRITE),
    _d("vendor-reports", "records", "jason vendors --reports", ("--reports",), ("--drive", "--yes")),
    # --- platform -----------------------------------------------------------------------------------------------------
    _d("mail-sync", "platform", "jason mail"),
    _d("gmail-sync", "platform", "jason gmail --sync", ("--sync",), NO_WRITE),
    _d("responses-check", "platform", "jason responses --check", ("--check",)),
    _d("responses-read", "platform", "jason responses --read ID --by NAME", ("--read",)),
)

READY: frozenset[str] = frozenset({"property"})
"""The families whose descriptors are registered in ``readers.JOBS``. A family is added here when its own definition and tests
move from "wanted" to "registered" (see the module docstring)."""

# A name two families want (the same command) is described once, under the family that wanted it first: ``conflict-leads`` is
# the board's (the records family lists it too) and ``gmail-sync`` is the platform's (the property family lists it too). The
# other family finds it registered when the first family's is. ``catalog-sync`` (members) and ``sync-catalog`` (records) are two
# names for one command, kept apart because each family's tests pin its own name.


def registered(ready: frozenset[str] = READY) -> tuple[JobDescriptor, ...]:
    """The descriptors added to ``readers.JOBS``: those of a ready family."""
    return tuple(d for d in DESCRIPTORS if d.family in ready)


UNDESCRIBED: dict[str, str] = {
    "respond-standards": "its command is not built (`jason respond --standards`)",
    "letter-pdf-export": "it writes (`--yes`): a plan step's act, not a job a worker runs",
    "duties-score": "a script (`scripts/eval_duties.py`), not a jason command",
    "bill-sources-read": "three commands (`fetch-bills`, `sync-tax`, `vendors --sync`): a job names one command",
    "tax-documents-keep": "a signed append (`--by NAME`): a person's act, not a queued read",
    "books-sync": "four commands (`books`, `budget`, `reconcile`, `ledger`): a job names one command",
    "packet-build": "it writes Docs (`--yes`): a plan step's act, not a job a worker runs",
    "citations-scan": "three commands (`segments`, `cite --scan`, `cite EXPR`): a job names one command",
    "library-drive-sync": "two commands (`library`, `drive`): a job names one command",
    "parcel-gap-lookup": "no command yet",
    "parcel-report": "the same command as `parcel-history` (`instrument-graph --parcel`); no word tells the two apart in the queue",
    "recorder-reading": "an MCP tool (`recorder_search`, `recorder_detail`), not a jason command",
    "record-read": "it writes (`--yes --by NAME`): a plan step's act, not a job a worker runs",
    "split-read-back": "it writes (`--yes --by NAME`): a plan step's act, not a job a worker runs",
}
"""Wanted job names that cannot be a descriptor of one existing command, and why. ``wanted.py`` reports them; a name here is
never silently dropped, and a test keeps this table and ``DESCRIPTORS`` from naming the same job."""

__all__ = ["DESCRIPTORS", "JobDescriptor", "READY", "UNDESCRIBED", "registered"]
