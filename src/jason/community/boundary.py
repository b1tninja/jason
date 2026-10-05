"""Keep one association's facts out of jason's general documentation.

The general docs (``docs/``, ``AGENTS.md``, ``README.md``, ``SKILLS.md``) describe jason for any
association. The instance's own facts belong in its profile (``mystique/docs/``) or its private
notes (``mystique/notes/``). The terms checked come from the profile itself: its names, streets,
vendors, developers, banks, case numbers, group addresses, Drive ids, PayHOA org id, and the
counterparties in its sender directory (law firms, managers, vendors, insurers, banks, title
companies, accountants). Adding a fact to the profile extends the check.

The baseline of what each document names today is ``tests/fixtures/docs_boundary.json``. It
only shrinks: a new term fails the test, and so does a cleared one the baseline still lists
(``python -m jason.community.boundary --update`` rewrites it).

General code (``src/jason``) is held to the same terms where a fact hides in code: a regular
expression it matches text with, a word list it filters by, and a default argument. The regular
expression is read wherever it is handed over: to ``re``, to a reader helper (``first``,
``date_after``, ``amount_after``), or to a module's own function that passes its parameter on as a
pattern (`pattern_parameters`). Such a fact belongs in the profile behind a ``Community`` method
with an empty default. Its baseline is ``tests/fixtures/code_boundary.json`` and only shrinks the
same way. General code never imports the profile package by name at all (`profile_imports`).

A module's own table (a tuple, list, set, or dict of names, words, or records) is read only by the
wide reading (``scan_code(..., wide=True)``, ``python -m jason.community.boundary --wide``), which
is a report and not yet part of the check: ``docs/adapters.md`` says what it still finds.

A counterparty's name is treated two ways. A general reader that recognizes one by name is the
bug: it finds the counterparty through the sender directory instead (``sources.sender_in``). A
vendor-format adapter, the reader of the layout one vendor prints, carries the vendor's name as
the layout's signature. The two look the same in code, so an adapter is declared as data
(``jason.community.adapters``, listed in ``docs/adapters.md``): the vendor's name is then allowed
in that module and in a code span of a document, and nowhere else. A declaration the code no
longer bears out, or one the document does not list, fails the check (`adapter_problems`).
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
    for text, kind, minimum in sender_terms(_rows(community, "senders")):
        add(text, kind, minimum=minimum)
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


# The sender directory's counterparties: the kinds of sender that are one association's own (its law firms, managers,
# vendors, insurers, banks, title companies, accountants, its owners' property managers, a private utility), and the
# kind each gives its terms. A reader finds one through the directory (``sources.sender_in``), never by a name in a
# pattern. A government agency, a platform jason runs on, and an owner are not here: the State, a county, a federal
# program, and the association's own statement are no association's fact.
COUNTERPARTY_KINDS = {"MANAGER": "manager", "LAW_FIRM": "law firm", "VENDOR": "vendor", "INSURER": "insurer", "BANK": "bank",
                      "TITLE_ESCROW": "title or escrow company", "ACCOUNTANT": "accountant",
                      "PROPERTY_MANAGER": "property manager", "UTILITY": "utility"}


def sender_terms(senders: tuple) -> list[tuple[str, str, int]]:
    """(term, kind, shortest length) for each counterparty in a sender directory: its name and the words that recognize
    it.

    - A sender with a government level (a city's utility department, a public utility district) is a public source,
      like a government agency, and gives no term.
    - A word with a digit in it is an address or a box number, not a name.
    - A word shorter than five characters is too short to tell from an ordinary word.
    - A word the general vocabulary already uses for a sender nobody named (``sources.KIND_WORDS``) is generic.
    - A one-word name is a term only when the directory lists it among the sender's words. The words are chosen to
      recognize the sender in a document's text, so a name that is also an ordinary word ("Belong") is not among them.
    """
    from jason.community.sources import KIND_WORDS, fold

    generic = {fold(word) for _, _, words in KIND_WORDS for word in words}
    found: list[tuple[str, str, int]] = []
    for sender in senders:
        kind = COUNTERPARTY_KINDS.get(getattr(getattr(sender, "kind", None), "name", ""))
        if kind is None or getattr(sender, "level", None) is not None:
            continue
        words = [str(word) for word in getattr(sender, "words", ())
                 if not any(ch.isdigit() for ch in str(word)) and fold(str(word)) not in generic]
        name = str(getattr(sender, "name", "") or "")
        if len(name.split()) > 1 or fold(name) in {fold(word) for word in words}:
            found.append((name, kind, 4))
        found += [(word.title(), kind, 5) for word in words]
    return found


# Kinds of term a document may carry inside a code pointer: the profile's own name (a pointer into its package).
PROSE_KINDS = ("name",)
# Kinds of term a document may carry inside a code pointer only where it points at a declared adapter: a reader of the
# layout that vendor prints (``jason.community.adapters``).
ADAPTER_KINDS = frozenset(COUNTERPARTY_KINDS.values())


def _adapters(adapters: tuple | None) -> tuple:
    if adapters is not None:
        return tuple(adapters)
    from jason.community.adapters import adapters as declared_adapters

    return declared_adapters()


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


def scan(root: Path, terms: tuple[Term, ...], adapters: tuple | None = None) -> dict[str, list[str]]:
    """For each general document, the instance terms it names (sorted); documents naming none are left out.

    The profile's name may stand in a code pointer. A counterparty's name may stand in one only where an adapter is
    declared for that vendor's layout (``adapters``, by default every declared one): the document then points at the
    reader, as it would at a module. In prose it is a fact about the association, and found."""
    patterns = [(term, term.pattern()) for term in terms]
    rows = _adapters(adapters)
    pointed = {term.text: any(row.names(term.text) for row in rows) for term in terms if term.kind in ADAPTER_KINDS}
    found: dict[str, list[str]] = {}
    for path in general_documents(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        prose = _POINTER.sub("", text)
        hits = sorted({term.text for term, pattern in patterns
                       if pattern.search(prose if term.kind in PROSE_KINDS or pointed.get(term.text) else text)}, key=str.casefold)
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


# The readers' helpers that take a pattern (``jason.community.document_models``): the slots, by position and by name,
# where it goes. `pattern_parameters` adds every other function in general code that hands a parameter on as a pattern.
READER_HELPERS: dict[str, frozenset] = {"first": frozenset({0, "pattern"}), "amount_after": frozenset({0, "label"}),
                                        "date_after": frozenset({0, "label"})}
ADAPTERS_MODULE = "src/jason/community/adapters.py"


def _strings(node: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _pattern_arguments(call: ast.Call, helpers: dict[str, frozenset]) -> list[ast.AST]:
    """The arguments of a call that are patterns: the first given to ``re``, and a helper's pattern slots."""
    func = call.func
    if isinstance(func, ast.Attribute) and func.attr in _RE_CALLS:
        # ``re.search(pattern, ...)``. The same name on anything else is a compiled pattern's method, whose argument
        # is the text.
        mine = isinstance(func.value, ast.Name) and func.value.id == "re"
        return [*call.args[:1], *(k.value for k in call.keywords if k.arg == "pattern")] if mine else []
    if isinstance(func, ast.Name):
        slots = helpers.get(func.id)
    elif isinstance(func, ast.Attribute):
        # A method called on its own object is the module's own. On anything else, only a reader helper by its name
        # (``document_models.first(...)``): another object's method of some other name is not known.
        own = isinstance(func.value, ast.Name) and func.value.id in ("self", "cls")
        slots = helpers.get(func.attr) if own else READER_HELPERS.get(func.attr)
    else:
        slots = None
    if not slots:
        return []
    return [arg for at, arg in enumerate(call.args) if at in slots] + [k.value for k in call.keywords if k.arg in slots]


def _module_of(path: str) -> str:
    """``src/jason/community/base.py`` as ``jason.community.base``; a package's ``__init__`` as the package."""
    parts = path.removesuffix(".py").split("/")
    parts = parts[1:] if parts[:1] == ["src"] else parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _imported_names(tree: ast.AST, module: str, package: bool) -> dict[str, tuple[str, str]]:
    """Each name a module imports with ``from M import N [as A]``, as (M, N), a relative M resolved."""
    found: dict[str, tuple[str, str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        base = node.module or ""
        if node.level:
            parent = module.split(".") if package else module.split(".")[:-1]
            parent = parent[: max(len(parent) - (node.level - 1), 0)]
            base = ".".join([*parent, base] if base else parent)
        for alias in node.names:
            found[alias.asname or alias.name] = (base, alias.name)
    return found


def pattern_parameters(trees: dict[str, ast.AST]) -> dict[str, dict[str, frozenset]]:
    """For each module (by path), the functions it can call whose parameter is matched against text, by the name the
    module calls them, each with the slots (position and name) where the pattern goes.

    These are the reader helpers, and every function in ``trees`` that hands a parameter to ``re`` as the pattern or to
    another such function. A reader's own helper (``_after(label, text)``) is found this way, so a fact in the string
    given to it is seen as one given to ``re`` is. A module knows its own functions and the ones it imports by name
    (``from M import N``); a function of the same name in a module it does not import is another function."""
    modules = {path: _module_of(path) for path in trees}
    scope: dict[str, dict[str, tuple[str, str]]] = {}
    functions: list[tuple[str, tuple[str, str], list[str], set[str], list[ast.Call]]] = []
    for path, tree in trees.items():
        own: dict[str, tuple[str, str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                positional = [a.arg for a in (*node.args.posonlyargs, *node.args.args)]
                if positional[:1] in (["self"], ["cls"]):
                    positional = positional[1:]
                named = set(positional) | {a.arg for a in node.args.kwonlyargs}
                own[node.name] = (modules[path], node.name)
                functions.append((path, own[node.name], positional, named, [c for c in ast.walk(node) if isinstance(c, ast.Call)]))
        scope[path] = {**_imported_names(tree, modules[path], path.endswith("__init__.py")), **own}
    slots: dict[tuple[str, str], frozenset] = {}

    def view(path: str) -> dict[str, frozenset]:
        helpers = dict(READER_HELPERS)
        for name, key in scope[path].items():
            if key in slots:
                helpers[name] = slots[key]
            elif not (name in READER_HELPERS and key[0].endswith("document_models")):
                helpers.pop(name, None)       # the module's own function of a helper's name, with no pattern parameter
        return helpers

    changed = True
    while changed:
        changed = False
        views: dict[str, dict[str, frozenset]] = {}
        for path, key, positional, named, calls in functions:
            helpers = views[path] if path in views else views.setdefault(path, view(path))
            handed = {n.id for call in calls for arg in _pattern_arguments(call, helpers)
                      for n in ast.walk(arg) if isinstance(n, ast.Name)} & named
            found = frozenset(handed) | frozenset(positional.index(p) for p in handed if p in positional)
            if not found <= slots.get(key, frozenset()):
                slots[key] = slots.get(key, frozenset()) | found
                changed = True
    return {path: view(path) for path in trees}


def _collections(tree: ast.AST) -> list[str]:
    """The strings in a module's (or a class's) own tuples, lists, sets, and dicts: a table of names or words, or of
    records that carry them. ``__all__`` lists the module's own names and is left out."""
    found: list[str] = []
    bodies = [getattr(tree, "body", [])] + [node.body for node in getattr(tree, "body", []) if isinstance(node, ast.ClassDef)]
    for node in (node for body in bodies for node in body):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(t, ast.Name) and t.id == "__all__" for t in targets):
            continue
        if any(isinstance(n, (ast.Tuple, ast.List, ast.Set, ast.Dict)) for n in ast.walk(node.value)):
            found += _strings(node.value)
    return found


def code_sites(tree: ast.AST, helpers: dict[str, frozenset] | None = None, *, wide: bool = False) -> list[str]:
    """The strings in ``tree`` where a fact hides in code: a pattern given to ``re`` or to a function that matches its
    parameter against text (``helpers``, by default the reader helpers and this tree's own), a word list
    (``"a b c".split()``), and a parameter's default. A docstring, a comment, or a message is not one.

    ``wide`` adds the strings of the module's and its classes' own collections (`_collections`). The committed check
    does not read those: see ``docs/adapters.md``."""
    helpers = pattern_parameters({"module.py": tree})["module.py"] if helpers is None else helpers
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            found += [s for arg in _pattern_arguments(node, helpers) for s in _strings(arg)]
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "split" and isinstance(func.value, ast.Constant) \
                    and isinstance(func.value.value, str):
                found.append(func.value.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            found += [s for d in (*node.args.defaults, *node.args.kw_defaults) if d is not None for s in _strings(d)]
    if wide:
        found += _collections(tree)
    return [_ESCAPE.sub(" ", s) for s in found]


def _code_files(root: Path) -> list[Path]:
    return sorted((root / GENERAL_CODE).rglob("*.py"))


def scan_code(root: Path, terms: tuple[Term, ...], adapters: tuple | None = None, *, wide: bool = False) -> dict[str, list[str]]:
    """For each general module, the instance terms its patterns, word lists, and defaults name (sorted). A pattern is
    one given to ``re``, to a reader helper (``first``, ``date_after``, ``amount_after``), or to any function in general
    code that hands its parameter on as a pattern (`pattern_parameters`). ``wide`` reads the modules' own collections
    too (`code_sites`).

    A counterparty's name is not counted in a module declared as an adapter for that vendor's layout (``adapters``, by
    default every declared one): there the name is the layout's signature. Nor is it counted in the module that holds
    the declarations. It is counted in every other module, and every other kind of term is counted everywhere."""
    patterns = [(term, term.pattern()) for term in terms]
    rows = _adapters(adapters)
    trees = {path.relative_to(root).as_posix(): ast.parse(path.read_text(encoding="utf-8")) for path in _code_files(root)}
    helpers = pattern_parameters(trees)
    found: dict[str, list[str]] = {}
    for module, tree in trees.items():
        strings = code_sites(tree, helpers[module], wide=wide)
        hits = sorted({term.text for term, pattern in patterns if any(pattern.search(s) for s in strings)
                       and not (term.kind in ADAPTER_KINDS and any(row.names(term.text) and module in (row.module, ADAPTERS_MODULE)
                                                                   for row in rows))},
                      key=str.casefold)
        if hits:
            found[module] = hits
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


ADAPTERS_DOC = "docs/adapters.md"


def adapter_problems(root: Path, adapters: tuple | None = None) -> list[str]:
    """What is wrong with the adapter declarations: one the code no longer bears out (its module is gone or no longer
    names the vendor), and one the adapters document does not list. A declaration is data a reader of the repository can
    see, so it is never only in the code."""
    from jason.community.adapters import stale, unlisted

    rows = _adapters(adapters)
    doc = root / ADAPTERS_DOC
    listed = doc.read_text(encoding="utf-8") if doc.is_file() else ""
    return stale(root, rows) + [f"{ADAPTERS_DOC}: does not list {row}" for row in unlisted(listed, rows)]


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
    if "--wide" in args:
        # A report, not part of the check: what the modules' own collections name beyond the committed reading.
        committed, wide = scan_code(root, terms), scan_code(root, terms, wide=True)
        for module, found in wide.items():
            more = [term for term in found if term not in committed.get(module, [])]
            if more:
                print(f"wide  {module}: {', '.join(more)}")
    for site in profile_imports(root, community().slug):
        print(f"import {site}: general code imports the profile package")
        ok = False
    for line in adapter_problems(root):
        print(f"adapter {line}")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
