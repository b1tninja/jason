"""Each profile's data is its own: a second association never reads the first one's stores or private facts.

A second profile is scaffolded into a temp folder and made active, with the data root (``JASON_DATA_DIR``) a temp folder
that holds a first profile's stores and private fact files. The read-only tasks a new association runs first (the
onboarding session, the library, the private facts, the bank and utility accounts) are watched through Python's audit
events: nothing they open, connect to, or list may be the first profile's, and nothing may be created. The default
profile's topic files at the old place are still read for it, and only for it, and ``jason spec --migrate`` copies them
into its own folder with a backup. A static check keeps ``Path("data")`` out of the code.
"""

import ast
import io
import json
import sqlite3
import sys
import tokenize
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from jason.cli import build_parser
from jason.community import community, private
from jason.community import profile as profiles
from jason.tasks import profile_scaffold as scaffold
from jason.tasks import spec_layout as layout

KEY = "second_village"
NAME = "Second Village HOA"
FIRST = "mystique"                    # the default profile, whose stores sit at the data root

# --- Audit events: what a task opens, connects to, or lists ------------------------------------------------------------

_WATCH: list[tuple[str, str]] | None = None


def _audit(event: str, args: tuple) -> None:
    if _WATCH is None or event not in ("open", "sqlite3.connect", "os.listdir", "os.scandir"):
        return
    target = args[0] if args else None
    if isinstance(target, int) or target is None:
        return
    if isinstance(target, bytes):
        target = target.decode("utf-8", "replace")
    text = str(target)
    if text.startswith("file:"):
        text = text[5:].split("?", 1)[0]
    _WATCH.append((event, text))


sys.addaudithook(_audit)


class _Watched:
    def __enter__(self):
        global _WATCH
        _WATCH = []
        return _WATCH

    def __exit__(self, *exc):
        global _WATCH
        _WATCH = None


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def _tree(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*")}


def _forget(key: str) -> None:
    for module in [m for m in sys.modules if m == f"jason_{key}" or m.startswith(f"jason_{key}.")]:
        del sys.modules[module]
    profiles._LOADED.pop(key, None)


def _sqlite(path: Path, table: str = "t") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE {table} (x)")
    conn.execute(f"INSERT INTO {table} VALUES (1)")
    conn.commit()
    conn.close()


def _first_profiles_data(root: Path) -> None:
    """A first association's stores at the data root and its private facts, in both the old and the new layout."""
    _sqlite(root / "library" / "library.db", "library")
    _sqlite(root / "utilities.db", "bills")
    _sqlite(root / "ownership.db")
    _sqlite(root / "index-cache.db")
    (root / "payhoa").mkdir(parents=True)
    (root / "payhoa" / "finance-2099.json").write_text(json.dumps({"syncedAt": "2099-01-01", "bankAccounts": [
        {"friendlyName": "A first association's account", "plaidBalance": 100}]}), encoding="utf-8")
    (root / "intake").mkdir()
    (root / "intake" / "asks.json").write_text("[]", encoding="utf-8")
    spec = root / "spec"
    (spec / FIRST).mkdir(parents=True)
    rows = {"bank_accounts": [{"suffix": "0001", "purpose": "operating"}],
            "utility_accounts": [{"utility": "smud", "account": "0000000001"}],
            "cases": {"a-case": {"gross_cents": 1}}, "holds": {"a-hold": {"terms": ["x"]}}}
    for topic, value in rows.items():
        (spec / f"{topic}.json").write_text(json.dumps(value), encoding="utf-8")            # the old layout
    (spec / FIRST / "senders.json").write_text(json.dumps({"roles": {"x": "y"}}), encoding="utf-8")
    (spec / f"{FIRST}.json").write_text(json.dumps({"facts": {"signers": {"answer": "x"}}}), encoding="utf-8")


@pytest.fixture
def second(tmp_path, monkeypatch):
    """The scaffold of a second profile, active, over a data root that holds the first profile's data."""
    root = tmp_path / "data"
    _first_profiles_data(root)
    monkeypatch.delenv("JASON_SPEC_DIR", raising=False)
    monkeypatch.delenv("PAYHOA_CATALOG", raising=False)
    monkeypatch.setenv("JASON_DATA_DIR", str(root))
    monkeypatch.setenv("JASON_ENV", str(tmp_path / "no.env"))                 # no .env: nothing names another folder
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path / "locks"))
    made = scaffold.write(KEY, NAME, county="Sacramento", directory=tmp_path / "pkg" / KEY, today=date(2099, 1, 1))
    assert made.spec == root / "spec" / f"{KEY}.json"                         # the spec folder follows the data root
    monkeypatch.setenv("JASON_PROFILE", KEY)
    monkeypatch.setenv("JASON_PROFILE_DIR", str(made.package))
    yield root
    _forget(KEY)


def test_a_second_profile_reads_none_of_the_first_profiles_data_and_creates_nothing(second):
    from jason import api
    from jason.config import Settings, data_dir
    from jason.mcp import county
    from jason.tasks import ingest, onboarding, onboarding_session

    root = second
    mine = root / KEY
    allowed = (mine, root / "spec" / KEY, root / "spec" / f"{KEY}.json")
    real = Path(private.__file__).resolve().parents[3] / "data"
    settings = Settings.load()
    assert data_dir() == settings.payhoa_catalog.parent == mine
    assert settings.smud_db.parent == mine and settings.idoxs_db.parent == mine     # never the first one's utility store
    assert private.spec_dir() == root / "spec"
    before = _tree(root)

    the = community()
    with _Watched() as seen:
        assert type(the).__name__ == "SecondVillage"
        # the private facts: the second profile's own topics, none of them the first one's old or new files
        for topic in ("bank_accounts", "utility_accounts", "cases", "holds", "senders"):
            assert private.facts(topic) == {}
            assert private.facts(topic, []) == []
            assert private.path_of(topic) == root / "spec" / KEY / f"{topic}.json"
        assert private.facts(FIRST) == {}                                       # another profile's name is a topic
        assert private.facts(KEY) == {"facts": {}}                              # its own facts file
        assert the.bank_accounts() == () and the.utility_accounts() == ()
        # the onboarding session and the checklist's context
        session = onboarding_session.build(the, mine, settings=settings)
        assert session.gates and all(not g.open for g in session.gates)
        status = api.onboarding_status()
        assert "error" not in status
        ctx = onboarding.load_context(the, mine, settings=settings)
        assert ctx.library == () and ctx.private("bank_accounts") == {} and ctx.private("utility_accounts") == {}
        now, _ = ingest.contexts(the, mine, rows=[], asks=())
        assert now.library == () and now.private("cases") == {}
        # the library, the bank accounts, and the utility accounts as the MCP tools read them
        assert county.library_status()["found"] is False
        assert county.bank_accounts()["found"] is False
        assert county.utility_accounts()["found"] is False

    assert any(_under(Path(p), root / "spec" / f"{KEY}.json") for _, p in seen)   # the watch sees what is opened
    leaked = sorted({f"{event} {path}" for event, path in seen
                     if (_under(Path(path), root) or _under(Path(path), real))
                     and not any(_under(Path(path), ok) for ok in allowed)})
    assert not leaked, leaked
    assert _tree(root) == before                                                # nothing created, here or the first's
    assert not mine.exists()


def test_the_checklist_reports_the_second_profiles_bank_and_utility_accounts_as_its_own(second):
    from jason.community.onboarding import Private
    from jason.tasks import onboarding

    ctx = onboarding.load_context(community(), second / KEY)
    for topic in ("bank_accounts", "utility_accounts", "cases", "holds"):
        finding = Private(topic).run(ctx)
        assert finding.passed is False and finding.evidence.endswith(": 0"), finding  # not the first one's rows


def test_the_default_profile_reads_its_old_topic_files_until_they_are_copied(tmp_path, monkeypatch):
    spec = tmp_path / "spec"
    spec.mkdir()
    monkeypatch.setenv("JASON_SPEC_DIR", str(spec))
    (spec / "bank_accounts.json").write_text('[{"suffix": "0001"}]', encoding="utf-8")
    assert private.facts("bank_accounts", [], profile=FIRST) == [{"suffix": "0001"}]
    assert private.path_of("bank_accounts", FIRST) == spec / "bank_accounts.json"
    assert private.facts("bank_accounts", [], profile=KEY) == []                # another profile: never the old file
    (spec / FIRST).mkdir()
    (spec / FIRST / "bank_accounts.json").write_text('[{"suffix": "0002"}]', encoding="utf-8")
    assert private.facts("bank_accounts", [], profile=FIRST) == [{"suffix": "0002"}]     # its own folder first
    written = private.write("utility_accounts", [], profile=KEY)
    assert written == spec / KEY / "utility_accounts.json"


def test_migrate_is_a_dry_run_then_copies_with_a_backup_and_never_changes_a_source(tmp_path, monkeypatch, capsys):
    spec = tmp_path / "spec"
    spec.mkdir()
    monkeypatch.setenv("JASON_SPEC_DIR", str(spec))
    for topic in ("bank_accounts", "cases", "utility_accounts"):
        (spec / f"{topic}.json").write_text(json.dumps({topic: "a value"}), encoding="utf-8")
    (spec / f"{FIRST}.json").write_text('{"facts": {}}', encoding="utf-8")
    (spec / "oakview.json").write_text('{"facts": {}, "leads": []}', encoding="utf-8")     # another profile's own file
    sources = {p.name: p.read_bytes() for p in spec.glob("*.json")}

    args = build_parser().parse_args(["spec", "--migrate"])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert "Dry run: 3 to copy" in out and "a value" not in out
    assert f"copy spec/bank_accounts.json -> spec/{FIRST}/bank_accounts.json" in out
    assert f"skip spec/{FIRST}.json" in out and "skip spec/oakview.json" in out
    assert sorted(p.name for p in spec.iterdir()) == sorted(sources)            # the dry run wrote nothing

    steps = layout.plan(spec)
    backup = layout.apply(steps, spec, now=datetime(2099, 1, 1, tzinfo=timezone.utc))
    assert backup == spec / "backups" / "migrate-20990101T000000Z"
    assert sorted(p.name for p in backup.iterdir()) == ["bank_accounts.json", "cases.json", "utility_accounts.json"]
    assert sorted(p.name for p in (spec / FIRST).iterdir()) == ["bank_accounts.json", "cases.json", "utility_accounts.json"]
    assert {p.name: p.read_bytes() for p in spec.glob("*.json")} == sources      # every source as it was
    assert private.path_of("cases", FIRST) == spec / FIRST / "cases.json"

    (spec / FIRST / "cases.json").write_text('{"changed": true}', encoding="utf-8")
    again = {s.source.name: s.action for s in layout.plan(spec)}
    assert again["bank_accounts.json"] is layout.Action.SAME and again["cases.json"] is layout.Action.HOLD
    assert layout.apply(layout.plan(spec), spec) is None                        # nothing to copy; a held copy is kept
    assert json.loads((spec / FIRST / "cases.json").read_text(encoding="utf-8")) == {"changed": True}

    args = build_parser().parse_args(["spec"])
    assert args.func(args) == 0
    shown = capsys.readouterr().out
    assert f"cases: {FIRST}/cases.json" in shown and "a value" not in shown


# --- No hard-coded data folder ------------------------------------------------------------------------------------------

_SRC = Path(__file__).resolve().parents[1] / "src" / "jason"
# config.py names the data root once (``data_root``). The others are owned by another piece of work and are listed here
# until it routes them through ``jason.config.data_dir()``; a fixed one fails this test until it is removed.
_ALLOWED = {"config.py"}
_PENDING: dict[str, int] = {}


def _data_literals(text: str) -> int:
    """The code (not the prose: a string is one token) that names the data folder: ``Path("data...")``, ``= "data"``,
    ``/ "data"``, or an argument's ``default="data/..."``."""
    tokens = [t for t in tokenize.generate_tokens(io.StringIO(text).readline)
              if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT)]
    hits = 0
    for i, token in enumerate(tokens):
        if token.type != tokenize.STRING or i < 2:
            continue
        try:
            value = ast.literal_eval(token.string)
        except (ValueError, SyntaxError):
            continue
        if not isinstance(value, str) or not (value == "data" or value.startswith(("data/", "data\\"))):
            continue
        before, op = tokens[i - 2].string, tokens[i - 1].string
        if (op == "(" and before == "Path") or (op in ("=", "/") and value == "data") or (op == "=" and before == "default"):
            hits += 1
    return hits


def test_no_code_names_the_data_folder_except_the_settings():
    found: dict[str, int] = {}
    for path in sorted(_SRC.rglob("*.py")):
        rel = path.relative_to(_SRC).as_posix()
        if rel in _ALLOWED:
            continue
        hits = _data_literals(path.read_text(encoding="utf-8"))
        if hits:
            found[rel] = hits
    assert found == _PENDING, ("use jason.config.data_dir() or the settings, resolved when called, not a hard-coded "
                               f"data folder: {found}")


def test_the_scan_finds_each_form_and_not_the_prose():
    code = "\n".join(['a = Path("data")', 'b = Path("data/x.db")', 'def f(data_dir="data"): pass', 'c = root / "data"',
                      'p.add_argument("--out", default="data/x.jsonl")', ""])
    assert _data_literals(code) == 5
    prose = "\n".join(["note = 'use Path(\"data\") never'", 'label = f"data/{x}"', 'refs = ("data/reports/a.md",)', ""])
    assert _data_literals(prose) == 0
