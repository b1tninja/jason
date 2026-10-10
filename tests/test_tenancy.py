"""docs/tenancy.md, phase 1: one community per process is explicit, and a second community on the same disk crosses nothing.

Two throwaway communities (``alpha``, ``beta``; tests/tenancy_support.py) hold a sentinel in every store jason reads.
The same public reads run for each, in one interpreter alternating the active community and then as separate processes
(the cell shape). A read that returns the other community's sentinel is a module holding state across communities; it
is named in the failure. Those that cross today are listed in ``tests/fixtures/tenancy_state.json`` (``crosses``): the
work of phase 2. A new one fails, and so does one that no longer crosses (the list only shrinks). A second check reads
the syntax of ``src/jason`` for module-level state a community could leave behind (``jason.community.tenancy_state``).
"""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from pathlib import Path

import pytest

import tenancy_support as ts
from jason.community import profile as profiles
from jason.community import tenancy_state

SRC_TESTS = Path(__file__).resolve().parent


@pytest.fixture
def world(tmp_path, monkeypatch):
    """Two communities on one disk; this process serves whichever ``serve(key)`` names, through the profile search seam
    (one explicit profile folder per name) and the settings that name the folders."""
    w = ts.build_world(tmp_path)
    monkeypatch.setattr(profiles, "profile_root", lambda name=None: w.packages[name or profiles.profile_name()])
    for name in ("JASON_PROFILE_DIR", "PAYHOA_CATALOG", "JASON_COMMUNITY_VIA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("JASON_DATA_DIR", str(w.data_root))
    monkeypatch.setenv("JASON_SPEC_DIR", str(w.spec_dir))
    monkeypatch.setenv("JASON_LOCK_DIR", str(w.lock_dir))
    yield w
    for key in ts.KEYS:
        for module in [m for m in sys.modules if m == f"jason_{key}" or m.startswith(f"jason_{key}.")]:
            del sys.modules[module]
        profiles._LOADED.pop(key, None)


def serve(monkeypatch, key: str) -> None:
    monkeypatch.setenv("JASON_COMMUNITY", key)


def _other(key: str) -> str:
    return next(k for k in ts.KEYS if k != key)


def _crossings(texts: dict[str, dict[str, str]]) -> dict[str, str]:
    """probe -> what crossed, for each read (by community) that holds the other's sentinel or lacks its own."""
    found: dict[str, str] = {}
    for key, probes in texts.items():
        for name, text in probes.items():
            if f"SENT-{_other(key)}" in text:
                found[name] = f"the read for {key} returned SENT-{_other(key)}"
            elif f"SENT-{key}" not in text and name not in ("lock_names",) and not text.startswith("ERROR"):
                found.setdefault(name, f"the read for {key} lacks its own sentinel")
            elif text.startswith("ERROR"):
                found.setdefault(name, f"the read for {key} failed: {text[:140]}")
    return found


def _judge(found: dict[str, str]) -> None:
    """Fail on a crossing the baseline does not list, and on a listed one that no longer crosses."""
    listed = tenancy_state.load_crosses()
    new = {name: why for name, why in found.items() if name not in listed}
    cleared = sorted(name for name in listed if name not in found)
    where = {name: ts.PROBES[name][0] for name in new}
    assert not new, ("a read crosses communities; the state is held in: "
                     + "; ".join(f"{where[n]} ({n}: {new[n]})" for n in sorted(new)))
    assert not cleared, f"these no longer cross; remove them from tests/fixtures/tenancy_state.json: {cleared}"


def test_alternating_communities_in_one_interpreter_crosses_nothing_new(world, monkeypatch):
    texts: dict[str, dict[str, str]] = {}
    for key in (*ts.KEYS, ts.KEYS[0]):                     # alpha, beta, alpha again: a cache that remembers shows
        serve(monkeypatch, key)
        now = ts.read_all()
        if key in texts:
            assert now == texts[key], f"the second read for {key} differs from the first"
        texts[key] = now
    _judge(_crossings(texts))


_WATCH: list[tuple[str, ...]] = []      # path prefixes a read must not open (the audit hook below reads it)
_OPENED: list[str] = []


def _audit(event: str, args: tuple) -> None:
    if _WATCH and event in ("open", "sqlite3.connect", "os.listdir", "os.scandir") and args:
        text = str(args[0]).replace("\\", "/").lower()
        if any(text.startswith(prefix) for watched in _WATCH for prefix in watched):
            _OPENED.append(f"{event} {args[0]}")


sys.addaudithook(_audit)


def test_a_read_for_one_community_opens_no_file_of_the_other(world, monkeypatch):
    """Python's audit events: while alpha is served, nothing under beta's data or private-facts folders is opened or
    listed, and the other way round."""
    for key in (*ts.KEYS, ts.KEYS[0]):
        other = _other(key)
        _WATCH[:] = [tuple(str(p).replace("\\", "/").lower() for p in (world.data(other), world.spec_dir / other,
                                                                       world.spec_dir / f"{other}.json"))]
        _OPENED.clear()
        serve(monkeypatch, key)
        try:
            ts.read_all()
        finally:
            _WATCH.clear()
        assert _OPENED == [], f"serving {key} touched {other}'s files: {_OPENED[:5]}"


def test_the_harness_finds_a_leak(world, monkeypatch):
    """A probe that remembers the first community it was asked about is found, and the module that holds it is named."""
    remembered: dict[str, str] = {}

    def leaky() -> str:
        return remembered.setdefault("first", f"SENT-{ts._active()}")

    monkeypatch.setitem(ts.PROBES, "leaky", ("jason.example.leaky", leaky))
    texts = {}
    for key in ts.KEYS:
        serve(monkeypatch, key)
        texts[key] = ts.read_all()
    found = _crossings(texts)
    assert "leaky" in found and "SENT-alpha" in found["leaky"]
    with pytest.raises(AssertionError, match="jason.example.leaky"):
        _judge({"leaky": found["leaky"]})


def test_separate_processes_cross_nothing(world):
    """The cell shape: one process per community, its settings the only difference. The answers are the same as the
    one interpreter's, and none holds the other's sentinel."""
    import os

    texts: dict[str, dict[str, str]] = {}
    for key in ts.KEYS:
        env = {k: v for k, v in os.environ.items() if not k.startswith("JASON_")}
        env.update(world.env(key))
        env["PYTHONPATH"] = str(SRC_TESTS.parent / "src")
        done = subprocess.run([sys.executable, str(SRC_TESTS / "tenancy_support.py")], capture_output=True, text=True,
                              env=env, timeout=300)
        assert done.returncode == 0, done.stderr[-800:]
        texts[key] = json.loads(done.stdout.strip().splitlines()[-1])
    assert _crossings(texts) == {}, "a separate process returned the other community's data"


def test_a_lock_of_one_community_does_not_block_the_other(world, monkeypatch):
    from jason.locks import Resource, ResourceBusy, account, hold

    import threading

    def attempt(key: str) -> str:
        """Another thread asks for ``key``'s PayHOA lock (a thread already holding one is let through again)."""
        result: list[str] = []

        def run() -> None:
            try:
                with hold(Resource.PAYHOA, account(key), timeout=0.3):
                    result.append("held")
            except ResourceBusy:
                result.append("busy")

        t = threading.Thread(target=run)
        t.start()
        t.join()
        return result[0]

    serve(monkeypatch, "alpha")
    with hold(Resource.PAYHOA, account()):
        assert attempt("beta") == "held"                  # beta's account is another lock
        assert attempt("alpha") == "busy"                 # alpha's own is held


def test_no_new_module_level_community_state():
    found = tenancy_state.scan()
    baseline = tenancy_state.load_baseline()
    new, cleared = tenancy_state.compare(found, baseline)
    assert not new, ("module-level state a community could leave behind; if it is keyed by the community or a path, "
                     "shared public content, or set once at start, add it to tests/fixtures/tenancy_state.json with "
                     "its status and a one-line reason, else keep it out of the module: " + ", ".join(new))
    assert not cleared, f"cleared; run python -m jason.community.tenancy_state --update: {cleared}"
    assert not tenancy_state.problems(baseline)


def test_the_process_global_list_names_things_that_exist():
    """What stays process-wide by design (the work of phase 7) is listed with its reason, and each entry is real."""
    import importlib

    listed = json.loads(tenancy_state.baseline_path().read_text(encoding="utf-8"))["process_global"]
    assert listed
    for key, reason in listed.items():
        module, _, attr = key.partition(":")
        target = importlib.import_module(module)
        for part in attr.split("."):
            target = getattr(target, part)                # a renamed function must be renamed here too
        assert reason.strip()


def test_the_lint_finds_each_kind_of_state():
    src = inspect.cleandoc('''
        import os, tempfile
        from functools import lru_cache
        from pathlib import Path
        _seen = {}
        STAMP = None
        @lru_cache(maxsize=None)
        def read(): return 1
        @lru_cache(maxsize=None)
        def keyed(path): return 2
        def set_it():
            global STAMP
            STAMP = 1
            os.environ["JASON_PROFILE"] = "x"
            tempfile.tempdir = "y"
            return Path("data")
        def default(root=community()): return root
    ''')
    found = tenancy_state.scan_source(src, "m")
    assert set(found) == {"m:container:_seen", "m:cache:read", "m:global:STAMP", "m:environ:JASON_PROFILE",
                          "m:environ:tempfile.tempdir", "m:data-path:Path('data')", "m:default-call:default"}


def test_no_mcp_tool_takes_a_community():
    """A tool that took one would let a model, or a prompt hidden in a document, ask for the other community by naming it."""
    from jason.mcp.server import ALL_TOOLS

    named = {tool.__name__: [p for p in inspect.signature(tool).parameters if "communit" in p.lower() or p.lower() == "profile"]
             for tool in ALL_TOOLS}
    assert {name: params for name, params in named.items() if params} == {}
