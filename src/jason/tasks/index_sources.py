"""The passage index's sources for the classified library, the mail, jason's reports, and jason's own documentation.

``passage_index.build`` takes sources that give ``IndexFile`` entries. Each source here decides, file by file, whether a
file is searched at all and whether it is held back unless asked (``confidential``). The decisions are rule rows, read
in order, and where no row answers, the file is confidential:

- **The library** (``LibrarySource``, catalog ``library``, standing ``record``): one entry per distinct document, its
  copies folded by their bytes (``tasks.library.distinct_key``). It is confidential when any copy is: the stored flag,
  a confidential kind, a confidential folder, or a kind in ``HELD_KINDS``. A document no copy of which is classified is
  left out, and so are the kinds in ``NOT_RECORDS`` and a document with no text file on disk.
- **The mail** (``MailSource``, catalog ``mail``, standing ``record``): ``MAIL_RULES``. A letter that carries a
  credential is never indexed; nor is another association's mail or an owner's own account. A letter the sort left
  unknown, a confidential kind, and a letter that names a member are confidential.
- **The reports** (``ReportsSource``, catalog ``reports``, standing ``page``, generated): ``REPORT_RULES`` by the page's
  place under ``reports/``. A page no row places is confidential, and so is an open page that names a member.
- **The documentation** (``DocsSource``, catalog ``docs``, standing ``page``, generated): the project checkout's
  ``AGENTS.md``, ``SKILLS.md``, ``README.md``, and ``docs/*.md``. They sit outside the data directory, so the index
  holds them by their absolute paths. Without a checkout there are none.

Every source only reads. ``plan`` gives a source's entries with a count of what it left out and why, so a person can
read the plan before a build (``jason index --plan``). A member's name is one PayHOA lists
(``minutes_privacy.member_names``); without that list the name rows find nothing and the other rows still hold.

``library_holds`` is the test a build asks of every file of every source: a file the library holds as confidential,
by its bytes, is confidential wherever else it is found.

Confidential here is the index's one flag: held back unless asked, for directors and counsel. The console's data
levels (``jason.web.access``) are a separate check, made when a screen opens a file.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community.passage_index import IndexFile, Standing
from jason.community.symbols import DocumentKind

LIBRARY, MAIL, REPORTS, DOCS = "library", "mail", "reports", "docs"


@dataclass
class Plan:
    """What one source gives a build: its entries, and what it left out, by reason."""

    catalog: str
    entries: list[IndexFile] = field(default_factory=list)
    left_out: dict[str, int] = field(default_factory=dict)
    held: dict[str, int] = field(default_factory=dict)          # the confidential entries, by the row that held each

    def leave(self, reason: str) -> None:
        self.left_out[reason] = self.left_out.get(reason, 0) + 1

    def take(self, entry: IndexFile, why: str = "") -> None:
        """Add an entry; ``why`` is the row that made it confidential."""
        self.entries.append(entry)
        if entry.confidential:
            self.held[why or "confidential"] = self.held.get(why or "confidential", 0) + 1

    def summary(self) -> dict[str, Any]:
        return {"catalog": self.catalog, "files": len(self.entries),
                "confidential": sum(1 for e in self.entries if e.confidential),
                "confidentialBy": dict(sorted(self.held.items())), "leftOut": dict(sorted(self.left_out.items()))}


# --- members' names -----------------------------------------------------------------------------------------------------


def member_pattern(data_dir: Path) -> re.Pattern[str] | None:
    """A pattern for the members PayHOA lists by full name (directors left out: they are named in their office), or
    None when there is no list to read."""
    try:
        from jason.tasks.minutes_privacy import member_names

        names = member_names(Path(data_dir))
    except Exception:  # noqa: BLE001 - a list that cannot be read is no list; the rule rows still hold
        return None
    if not names:
        return None
    return re.compile("|".join(r"\b" + r"\s+".join(re.escape(word) for word in name.split()) + r"\b" for name in names),
                      re.IGNORECASE)


def _names_member(text: str, members: re.Pattern[str] | None) -> bool:
    return bool(members is not None and members.search(text))


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _title(text: str) -> str:
    """A page's first heading, without its mark."""
    for line in text.splitlines()[:20]:
        if line.startswith("# "):
            return " ".join(line[2:].split())
    return ""


# --- the library --------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class HeldKind:
    """A kind the library does not flag, held as confidential in the index, with why."""

    kind: DocumentKind
    why: str


# Kinds outside ``library.CONFIDENTIAL_KINDS`` that the index holds back all the same. The first three wait for a
# person's decision (docs/rag-roadmap.md, item 1); until it is made they are confidential. The rest name owners.
HELD_KINDS: tuple[HeldKind, ...] = (
    HeldKind(DocumentKind.TREASURER_REPORT, "its aging section can list units and balances; a person decides how it is shared"),
    HeldKind(DocumentKind.LEGAL_CORRESPONDENCE, "counsel's letters; a person decides how they are shared"),
    HeldKind(DocumentKind.SETTLEMENT, "a settlement's terms and figures are private facts; a person decides"),
    HeldKind(DocumentKind.LEASE, "which unit an owner rents, and the tenant, are private facts"),
    HeldKind(DocumentKind.GRANT_DEED, "an owner's deed: who held a unit, as the property-history pages are held"),
    HeldKind(DocumentKind.RECORDED_LIEN, "names an owner and a debt"),
)
# Kinds classified so they can be set aside: a blank template and a photo are not the association's record.
NOT_RECORDS = frozenset({DocumentKind.TEMPLATE, DocumentKind.IMAGE})

UNCLASSIFIED = "unclassified: no copy of the document has a kind"
NOT_A_RECORD = "a template or an image: not a record"
NO_TEXT = "no text file on disk"


def _kind(value: str) -> DocumentKind | None:
    try:
        return DocumentKind(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class LibrarySource:
    """The classified library's documents (``tasks.library``), each by its cached text file."""

    held: tuple[HeldKind, ...] = HELD_KINDS
    not_records: frozenset[DocumentKind] = NOT_RECORDS

    @property
    def catalogs(self) -> tuple[str, ...]:
        return (LIBRARY,)

    def copy_held(self, row: dict[str, Any]) -> str:
        """Why one copy makes its document confidential, or "": its kind, its folder, its stored flag (which also
        carries what its text showed), or a held kind. A kind the code does not know is confidential."""
        from jason.community.library import CONFIDENTIAL_FOLDERS, CONFIDENTIAL_KINDS

        kind = _kind(row["kind"]) if row.get("kind") else None
        if kind in CONFIDENTIAL_KINDS:
            return "a confidential kind"
        if str(row.get("path") or "").casefold().startswith(CONFIDENTIAL_FOLDERS):
            return "a copy in a confidential folder"
        if row.get("confidential"):
            return "the library's flag (its text)"
        if row.get("kind") and kind is None:
            return "a kind the code does not know"
        if kind in {h.kind for h in self.held}:
            return "a held kind"
        return ""

    def copy_confidential(self, row: dict[str, Any]) -> bool:
        return bool(self.copy_held(row))

    def plan(self, data_dir: Path) -> Plan:
        from jason.tasks.library import distinct_key, load, text_path

        root = Path(data_dir)
        plan = Plan(LIBRARY)
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in load(root):
            groups.setdefault(distinct_key(row), []).append(row)
        for copies in groups.values():
            classified = [row for row in copies if row.get("kind")]
            if not classified:
                plan.leave(UNCLASSIFIED)
                continue
            first = classified[0]
            if all(_kind(row["kind"]) in self.not_records for row in classified):
                plan.leave(NOT_A_RECORD)
                continue
            path = next((found for found in (text_path(root, row["id"]) for row in (*classified, *copies)) if found), None)
            if path is None:
                plan.leave(NO_TEXT)
                continue
            records: list[str] = []
            for row in copies:
                records += [record for record in row.get("records") or [] if record not in records]
            why = next((held for held in (self.copy_held(row) for row in copies) if held), "")
            plan.take(IndexFile(path, LIBRARY, Standing.RECORD, kind=first["kind"], confidential=bool(why),
                                context=library_context(first, records)), why)
        return plan

    def entries(self, data_dir: Path) -> Iterable[IndexFile]:
        return self.plan(data_dir).entries


def library_holds(data_dir: Path, source: LibrarySource | None = None) -> Callable[[Path], bool]:
    """A test a build asks of every file (``passage_index.build``'s ``held``): whether the library holds the same file
    as confidential. The file is matched by its bytes, and so is the file it is the extract of (``name.pdf.md`` beside
    ``name.pdf``). This is what keeps a confidential library document from being searched openly through a copy another
    source gives (a Drive mirror's extract). A library that cannot be read holds nothing here; its own source then
    gives no entries either."""
    import hashlib
    import sqlite3

    from jason.tasks.library import distinct_key, load

    source = source or LibrarySource()
    try:
        rows = load(Path(data_dir))
    except sqlite3.Error:
        rows = ()
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(distinct_key(row), []).append(row)
    held = {row["sha256"] for copies in groups.values() if any(source.copy_confidential(row) for row in copies)
            for row in copies if row.get("sha256")}

    def holds(path: Path) -> bool:
        if not held:
            return False
        original = path.with_name(path.name[:-3]) if path.name.lower().endswith(".md") else path
        for file in {path, original}:
            try:
                if file.is_file() and hashlib.sha256(file.read_bytes()).hexdigest() in held:
                    return True
            except OSError:
                continue
        return False

    return holds


def library_context(row: dict[str, Any], records: list[str]) -> str:
    """Where a library document sits, in a line: its name, its kind, its period, and its Civil Code 5200 records."""
    parts = [f"{row['name']}: {str(row['kind']).replace('_', ' ')}"]
    if row.get("period"):
        parts.append(f"period {row['period']}")
    if records:
        parts.append("Civil Code 5200 record: " + ", ".join(record.replace("_", " ") for record in records))
    return "; ".join(parts)


# --- the mail -----------------------------------------------------------------------------------------------------------


class Call(Enum):
    NEVER = "never indexed"
    CONFIDENTIAL = "confidential"
    OPEN = "open"


@dataclass(frozen=True)
class MailRule:
    """One row of the mail's rule: a test over a letter's stored row (None when it has none), its text, and the
    members' names, and what a letter that passes it is."""

    name: str
    call: Call
    test: Callable[[dict[str, Any] | None, str, "re.Pattern[str] | None"], bool]


def _source(row: dict[str, Any] | None) -> dict[str, Any]:
    source = (row or {}).get("source")
    return source if isinstance(source, dict) else {}


def _mail_kind(row: dict[str, Any] | None) -> Any:
    from jason.postscanmail.models import MailKind

    return next((kind for kind in MailKind if kind.value == (row or {}).get("kind")), None)


def _credential(row: dict[str, Any] | None, text: str, members: Any) -> bool:
    from jason.tasks.mail import carries_credential

    return bool((row or {}).get("credential")) or carries_credential(text)


def _misdirected(row: dict[str, Any] | None, text: str, members: Any) -> bool:
    return bool(_source(row).get("misdirected"))


def _owners_account(row: dict[str, Any] | None, text: str, members: Any) -> bool:
    from jason.community.sources import SourceKind

    return _source(row).get("kind") == SourceKind.OWNER.value


def _sort_unknown(row: dict[str, Any] | None, text: str, members: Any) -> bool:
    """No stored row, no kind the sort knows, the kind the sort gives what it could not place, or a row whose sender
    was never read against the profile (so whose mail it is was never asked)."""
    from jason.postscanmail.models import MailKind

    return row is None or _mail_kind(row) in (None, MailKind.OTHER) or not _source(row)


def _confidential_kind(row: dict[str, Any] | None, text: str, members: Any) -> bool:
    from jason.postscanmail.models import CONFIDENTIAL_KINDS

    return _mail_kind(row) in CONFIDENTIAL_KINDS


def _mail_names_member(row: dict[str, Any] | None, text: str, members: Any) -> bool:
    return _names_member(text, members)


# In order; the first row a letter passes decides it, and a letter that passes none is open. The first three rows are
# the retired catalog sync's "never"; the confidential kinds are its "only when a person asks".
MAIL_RULES: tuple[MailRule, ...] = (
    MailRule("carries a PIN, a passcode, a password, or an access code", Call.NEVER, _credential),
    MailRule("another association's mail: not the association's record", Call.NEVER, _misdirected),
    MailRule("an owner's or resident's own account", Call.NEVER, _owners_account),
    MailRule("the sort is unknown", Call.CONFIDENTIAL, _sort_unknown),
    MailRule("an attorney's letter, a bank statement, a check, or an escrow request", Call.CONFIDENTIAL, _confidential_kind),
    MailRule("names a member", Call.CONFIDENTIAL, _mail_names_member),
)


def mail_call(row: dict[str, Any] | None, text: str, members: "re.Pattern[str] | None" = None,
              rules: tuple[MailRule, ...] = MAIL_RULES) -> tuple[Call, str]:
    """What a letter is by ``rules``, and the row that said so ("" for an open letter)."""
    for rule in rules:
        if rule.test(row, text, members):
            return rule.call, rule.name
    return Call.OPEN, ""


@dataclass(frozen=True)
class MailSource:
    """The scanned letters (``tasks.mail``): a letter's page (``letter.md``) when it is on disk, else its scanned text
    (``text.txt``). Both are read for a credential, whatever the stored row says."""

    rules: tuple[MailRule, ...] = MAIL_RULES

    @property
    def catalogs(self) -> tuple[str, ...]:
        return (MAIL,)

    def plan(self, data_dir: Path) -> Plan:
        from jason.tasks.mail import LETTER, load_items, mail_dir

        root = mail_dir(Path(data_dir))
        plan = Plan(MAIL)
        if not root.is_dir():
            return plan
        try:
            items = load_items(Path(data_dir))
            readable = True
        except (OSError, ValueError, KeyError, AttributeError, TypeError):
            items, readable = {}, False           # a sort that cannot be read: every letter's sort is unknown
        members = member_pattern(Path(data_dir)) if readable else None
        on_disk = {p.name for p in root.iterdir() if p.is_dir() and ((p / LETTER).is_file() or (p / "text.txt").is_file())}
        for mail_id in sorted(on_disk | set(items)):
            row = items.get(mail_id)
            page, scanned = root / mail_id / LETTER, root / mail_id / "text.txt"
            text = "\n".join(part for part in (_read(scanned), _read(page)) if part)
            if not text.strip():
                plan.leave("no text: not scanned, or nothing read")
                continue
            call, why = mail_call(row, text, members, self.rules)
            if call is Call.NEVER:
                plan.leave(why)
                continue
            plan.take(IndexFile(page if page.is_file() else scanned, MAIL, Standing.RECORD, kind="",
                                confidential=call is Call.CONFIDENTIAL, context=mail_context(mail_id, row)), why)
        return plan

    def entries(self, data_dir: Path) -> Iterable[IndexFile]:
        return self.plan(data_dir).entries


def mail_context(mail_id: str, row: dict[str, Any] | None) -> str:
    """Where a letter sits, in a line: when it came, who sent it, and the sort."""
    if row is None:
        return f"A letter the association received (mail {mail_id}); not sorted"
    day = str(row.get("received") or "")[:10]
    who = " ".join(str(row.get("from") or row.get("sender") or "").split())[:70]
    return (f"A letter the association received{' ' + day if day else ''}{' from ' + who if who else ''}"
            f" (mail {mail_id}); sorted as {row.get('kind') or 'nothing'}")


# --- jason's reports ----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportRule:
    """One place under ``reports/`` (an fnmatch pattern on the posix path, lower case) and whether its pages are held
    back, with why."""

    pattern: str
    confidential: bool
    why: str


# In order, first match. A page no row places is confidential: a new report is held back until a row says what it is.
# The open rows are the pages jason writes from the law and the governing documents, which name no person.
REPORT_RULES: tuple[ReportRule, ...] = (
    ReportRule("property-history/*", True, "who held each unit, PayHOA's members, liens and notices, and taxes"),
    ReportRule("live/*", True, "PayHOA's reports as they stand: balances and aging by unit, occupancy"),
    ReportRule("mail.md", True, "names every letter, the held ones among them"),
    ReportRule("revisions-*.md", True, "quotes working drafts, which are not the adopted text"),
    ReportRule("duties.md", False, "the manager's duties, with the statutes' and the governing documents' passages"),
    ReportRule("law-sweep.md", False, "the sections of the law that changed and the files that cite them"),
    ReportRule("notice-templates.md", False, "the base notice templates checked against the law"),
    ReportRule("references.md", False, "the governing documents' sections and what cites what"),
)
UNPLACED = "no rule places the page"
NAMES_A_MEMBER = "names a member"


def report_call(rel: str, rules: tuple[ReportRule, ...] = REPORT_RULES) -> tuple[bool, str]:
    """Whether the page at ``rel`` (under ``reports/``) is held back by ``rules``, and why."""
    lowered = rel.replace("\\", "/").lower()
    for rule in rules:
        if fnmatch.fnmatchcase(lowered, rule.pattern):
            return rule.confidential, rule.why
    return True, UNPLACED


@dataclass(frozen=True)
class ReportsSource:
    """The pages jason generated under ``reports/``. Each is a summary, never quoted as the rule."""

    rules: tuple[ReportRule, ...] = REPORT_RULES
    folder: str = "reports"

    @property
    def catalogs(self) -> tuple[str, ...]:
        return (REPORTS,)

    def plan(self, data_dir: Path) -> Plan:
        root = Path(data_dir) / self.folder
        plan = Plan(REPORTS)
        if not root.is_dir():
            return plan
        members: re.Pattern[str] | None = None
        asked = False
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            text = _read(path)
            if not text.strip():
                plan.leave("an empty page")
                continue
            held, why = report_call(path.relative_to(root).as_posix(), self.rules)
            if not held:
                if not asked:
                    members, asked = member_pattern(Path(data_dir)), True
                held, why = _names_member(text, members), NAMES_A_MEMBER
            title = _title(text)
            plan.take(IndexFile(path, REPORTS, Standing.PAGE, kind="", confidential=held, generated=True,
                                context=f"jason's report{': ' + title if title else ''}"), why)
        return plan

    def entries(self, data_dir: Path) -> Iterable[IndexFile]:
        return self.plan(data_dir).entries


# --- jason's own documentation ------------------------------------------------------------------------------------------

DOC_PATTERNS: tuple[str, ...] = ("AGENTS.md", "SKILLS.md", "README.md", "docs/*.md")


def checkout() -> Path | None:
    """The project checkout this code runs from, or None when jason is installed without one."""
    root = Path(__file__).resolve().parents[3]
    return root if (root / "AGENTS.md").is_file() and (root / "docs").is_dir() else None


@dataclass(frozen=True)
class DocsSource:
    """jason's own instructions and documentation, from the project checkout: how jason works, never the rule and never
    the association's record. The files are outside the data directory; the index holds each by its absolute path."""

    root: Path | None = None              # None: the checkout this code runs from
    patterns: tuple[str, ...] = DOC_PATTERNS

    @property
    def catalogs(self) -> tuple[str, ...]:
        return (DOCS,)

    def plan(self, data_dir: Path) -> Plan:
        plan = Plan(DOCS)
        root = self.root if self.root is not None else checkout()
        if root is None or not Path(root).is_dir():
            return plan
        seen: set[Path] = set()
        for pattern in self.patterns:
            for path in sorted(Path(root).glob(pattern)):
                if not path.is_file() or path in seen:
                    continue
                seen.add(path)
                title = _title(_read(path))
                plan.take(IndexFile(path, DOCS, Standing.PAGE, kind="", generated=True,
                                    context=f"jason's documentation{': ' + title if title else ''}"))
        return plan

    def entries(self, data_dir: Path) -> Iterable[IndexFile]:
        return self.plan(data_dir).entries


def sources() -> tuple[Any, ...]:
    """The four sources, in the order a build takes them."""
    return (LibrarySource(), MailSource(), ReportsSource(), DocsSource())


__all__ = ["Call", "DOC_PATTERNS", "DocsSource", "HELD_KINDS", "HeldKind", "LibrarySource", "MAIL_RULES", "MailRule",
           "MailSource", "NOT_RECORDS", "Plan", "REPORT_RULES", "ReportRule", "ReportsSource", "checkout", "library_context",
           "library_holds", "mail_call", "mail_context", "member_pattern", "report_call", "sources"]
