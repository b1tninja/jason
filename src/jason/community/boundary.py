"""Keep one association's facts out of jason's general documentation.

The general docs (``docs/``, ``AGENTS.md``, ``README.md``, ``SKILLS.md``) describe jason for any
association. The instance's own facts belong in its profile (``mystique/docs/``) or its private
notes (``mystique/notes/``). The terms checked come from the profile itself: its names, streets,
vendors, developers, banks, case numbers, group addresses, Drive ids, and PayHOA org id. Adding
a fact to the profile extends the check.

The baseline of what each document names today is ``tests/fixtures/docs_boundary.json``. It
only shrinks: a new term fails the test, and so does a cleared one the baseline still lists
(``python -m jason.community.boundary --update`` rewrites it).

General code (``src/jason``) is held to the same terms where a fact hides in code: a regular
expression it matches text with, a word list it filters by, and a default argument. Such a fact
belongs in the profile behind a ``Community`` method with an empty default. Its baseline is
``tests/fixtures/code_boundary.json`` and only shrinks the same way. General code never imports
the profile package by name at all (`profile_imports`).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from jason.community.base import Community

# The general docs, and jason's base templates, which a profile renders (docs/base-templates.md).
GENERAL_DOCS = ("AGENTS.md", "README.md", "SKILLS.md", "docs", "src/jason/templates")
_DOC_SUFFIXES = (".md", ".html")
# A code span that points into the profile package (`mystique/meetings.py`, `Mystique.senders()`) names the
# profile on purpose; the association's name in prose does not.
_POINTER = re.compile(
    r"`[^`\n]*`"                        # a code span
    r"|\[[\w./-]+\]\([^)\s]*\)"         # a link whose text is a folder or file name: [mystique](mystique/README.md)
    r"|\]\([^)\s]*\)"                   # a link target
    r"|(?<![\w/.-])[\w-]+/[\w./#-]+"    # a bare path: mystique/notes/meetings.md
)
_STREET_SUFFIX = re.compile(r"\s+(DR|LN|WALK|WAY|CT|ST|AVE|RD|BLVD|CIR|PL)$", re.I)


@dataclass(frozen=True)
class Term:
    """One instance fact and what it is."""

    text: str
    kind: str

    def pattern(self) -> re.Pattern[str]:
        return re.compile(r"(?<![\w-])" + re.escape(self.text) + r"(?![\w-])", re.I)


def instance_terms(community: Community) -> tuple[Term, ...]:
    """The profile's facts that a general document should not name."""
    found: dict[str, Term] = {}

    def add(text: object, kind: str, *, minimum: int = 4) -> None:
        word = str(text or "").strip()
        if len(word) >= minimum and word.casefold() not in found:
            found[word.casefold()] = Term(word, kind)

    add(community.name, "name")
    add(community.corporate_name, "name")
    add(community.name.split()[0], "name")
    add(community.org_id, "payhoa org id")
    from jason.community.symbols import Street

    for street in Street:
        add(_STREET_SUFFIX.sub("", street.value).title(), "street")
    for portal in _rows(community, "vendor_portals"):
        add(getattr(portal, "vendor", ""), "vendor")
    # A management company the association has had: its name and the words that recognize it. A reader finds it
    # through the sender directory (``sources.manager_in``), never by a name in a pattern.
    for sender in _rows(community, "senders"):
        if getattr(getattr(sender, "kind", None), "name", "") == "MANAGER":
            add(getattr(sender, "name", ""), "manager")
            for word in getattr(sender, "words", ()):
                if not any(ch.isdigit() for ch in word):
                    add(str(word).title(), "manager", minimum=5)
    for developer in _rows(community, "developers"):
        add(getattr(developer, "name", ""), "developer")
    for account in _rows(community, "bank_accounts"):
        add(getattr(account, "bank", ""), "bank")
    for case in _rows(community, "legal_cases"):
        add(getattr(case, "case_number", ""), "case number")
    for group in _rows(community, "google_groups"):
        address = str(getattr(group, "address", ""))
        add(address, "group address")
        add(address.partition("@")[2], "domain")
    for root in _rows(community, "drive_roots"):
        add(getattr(getattr(root, "drive", None), "value", ""), "drive id", minimum=20)
    for anchor in _rows(community, "known_files"):
        add(getattr(anchor, "drive_id", ""), "drive id", minimum=20)
    for folder in _rows(community, "library_folders"):
        add(getattr(getattr(folder, "drive", None), "value", ""), "drive id", minimum=20)
    return tuple(found.values())


def _rows(community: Community, name: str) -> tuple:
    method = getattr(community, name, None)
    if method is None:
        return ()
    rows = method() if callable(method) else method
    if isinstance(rows, dict):
        rows = rows.values()
    return tuple(rows or ())


# Kinds of term a document may carry inside a code pointer (a reader named after the vendor whose layout it reads).
PROSE_KINDS = ("name", "manager")


def general_documents(root: Path) -> tuple[Path, ...]:
    """Every general document under the repository root."""
    files: list[Path] = []
    for entry in GENERAL_DOCS:
        path = root / entry
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(sorted(p for p in path.rglob("*") if p.suffix in _DOC_SUFFIXES))
    return tuple(files)


def scan(root: Path, terms: tuple[Term, ...]) -> dict[str, list[str]]:
    """For each general document, the instance terms it names (sorted); documents naming none are left out."""
    patterns = [(term, term.pattern()) for term in terms]
    found: dict[str, list[str]] = {}
    for path in general_documents(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        prose = _POINTER.sub("", text)
        hits = sorted({term.text for term, pattern in patterns
                       if pattern.search(prose if term.kind in PROSE_KINDS else text)}, key=str.casefold)
        if hits:
            found[path.relative_to(root).as_posix()] = hits
    return found


@dataclass(frozen=True)
class Drift:
    """New leaks (a term a document did not name before) and cleared ones the baseline still lists."""

    new: dict[str, list[str]]
    cleared: dict[str, list[str]]

    @property
    def ok(self) -> bool:
        return not self.new and not self.cleared


def compare(current: dict[str, list[str]], baseline: dict[str, list[str]]) -> Drift:
    new: dict[str, list[str]] = {}
    cleared: dict[str, list[str]] = {}
    for path in sorted(set(current) | set(baseline)):
        now = {t.casefold(): t for t in current.get(path, [])}
        before = {t.casefold(): t for t in baseline.get(path, [])}
        added = sorted((now[k] for k in now.keys() - before.keys()), key=str.casefold)
        gone = sorted((before[k] for k in before.keys() - now.keys()), key=str.casefold)
        if added:
            new[path] = added
        if gone:
            cleared[path] = gone
    return Drift(new, cleared)


# --- general code -----------------------------------------------------------------------------------------------------

GENERAL_CODE = "src/jason"
# The ``re`` functions whose first argument is the pattern.
_RE_CALLS = frozenset({"compile", "search", "match", "fullmatch", "findall", "finditer", "sub", "subn", "split"})
# A pattern's escapes (\b, \s): "\bMain" names Main as plainly as "Main" does.
_ESCAPE = re.compile(r"\\[A-Za-z]")


def _strings(node: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def code_sites(tree: ast.AST) -> list[str]:
    """The strings in ``tree`` where a fact hides in code: the pattern given to ``re``, a word list
    (``"a b c".split()``), and a parameter's default. A docstring, a comment, or a message is not one."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            func = node.func
            if func.attr in _RE_CALLS and isinstance(func.value, ast.Name) and func.value.id == "re" and node.args:
                found += _strings(node.args[0])
            elif func.attr == "split" and isinstance(func.value, ast.Constant) and isinstance(func.value.value, str):
                found.append(func.value.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            found += [s for d in (*node.args.defaults, *node.args.kw_defaults) if d is not None for s in _strings(d)]
    return [_ESCAPE.sub(" ", s) for s in found]


def _code_files(root: Path) -> list[Path]:
    return sorted((root / GENERAL_CODE).rglob("*.py"))


def scan_code(root: Path, terms: tuple[Term, ...]) -> dict[str, list[str]]:
    """For each general module, the instance terms its patterns, word lists, and defaults name (sorted)."""
    patterns = [(term, term.pattern()) for term in terms]
    found: dict[str, list[str]] = {}
    for path in _code_files(root):
        strings = code_sites(ast.parse(path.read_text(encoding="utf-8")))
        hits = sorted({term.text for term, pattern in patterns if any(pattern.search(s) for s in strings)}, key=str.casefold)
        if hits:
            found[path.relative_to(root).as_posix()] = hits
    return found


def _imported(node: ast.AST) -> list[str]:
    """The module names an import statement or an ``import_module("…")`` call names."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if isinstance(node, ast.ImportFrom):
        return [node.module] if node.module and not node.level else []
    if isinstance(node, ast.Call) and node.args:
        func = node.func
        called = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
        if called in ("import_module", "__import__"):
            first = node.args[0]
            if isinstance(first, ast.JoinedStr) and first.values:
                first = first.values[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                return [first.value]
    return []


def profile_imports(root: Path, slug: str) -> list[str]:
    """``path:line`` wherever general code imports the profile package by name (``slug`` or ``jason_<slug>``). It
    reaches the profile through ``jason.community.community()`` instead."""
    names = {slug, f"jason_{slug}"}
    found: list[str] = []
    for path in _code_files(root):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if any(module.split(".")[0] in names for module in _imported(node)):
                found.append(f"{path.relative_to(root).as_posix()}:{node.lineno}")
    return found


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def baseline_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "tests" / "fixtures" / "docs_boundary.json"


def code_baseline_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "tests" / "fixtures" / "code_boundary.json"


def main(argv: list[str] | None = None) -> int:
    from jason.community import community

    args = list(sys.argv[1:] if argv is None else argv)
    root = repo_root()
    terms = instance_terms(community())
    ok = True
    for what, current, path in (("general documents", scan(root, terms), baseline_path(root)),
                                ("general modules", scan_code(root, terms), code_baseline_path(root))):
        if "--update" in args:
            path.write_text(json.dumps(current, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"{sum(len(v) for v in current.values())} terms in {len(current)} {what} -> {path}")
            continue
        baseline = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        drift = compare(current, baseline)
        for doc, found in drift.new.items():
            print(f"new   {doc}: {', '.join(found)}")
        for doc, found in drift.cleared.items():
            print(f"clear {doc}: {', '.join(found)}")
        print(f"{sum(len(v) for v in current.values())} instance terms in {len(current)} {what}")
        ok = ok and drift.ok
    for site in profile_imports(root, community().slug):
        print(f"import {site}: general code imports the profile package")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
