import os
from pathlib import Path

import pytest

# The tests read made-up private facts (tests/fixtures/spec), never the association's real ones (data/spec): the same
# results on any checkout. Set before the specification is first imported, since it reads them when it loads.
os.environ["JASON_SPEC_DIR"] = str(Path(__file__).parent / "fixtures" / "spec")
# The tests are written against the mystique profile, whatever profile this machine's .env chooses.
os.environ["JASON_PROFILE"] = "mystique"
os.environ.pop("JASON_PROFILE_DIR", None)

# JASON_TEMP_DIR (environment or .env) puts scratch, and pytest's tmp_path (PYTEST_DEBUG_TEMPROOT, which pytest-xdist's
# workers inherit), on that drive. Unset, nothing changes. pytest prunes only the pytest-of-<user> folders it made.
try:
    from jason.config import apply_temp_dir

    apply_temp_dir()
except Exception as exc:  # noqa: BLE001 - a JASON_TEMP_DIR that cannot be used stops the run, never falls back to C:
    pytest.exit(f"JASON_TEMP_DIR: {exc}", returncode=2)

# Past this point a test reads no one's user config (~/.jason/.env): the machine's settings, such as where scratch goes,
# were applied above, and the tests set what they need themselves. A file that does not exist, so no test finds one.
os.environ["JASON_CONFIG"] = str(Path(__file__).parent / "fixtures" / "no-user-config.env")


@pytest.fixture(autouse=True)
def _no_keeper_login(monkeypatch):
    """A test never signs in to Keeper: a session it opens wants a sign-in (``KeeperAuthRequired``), as a machine with
    no Keeper login would. A test that fakes Keeper sets its own ``login_to_vault``."""
    import jason.secrets as secrets

    def refuse(**kwargs):
        raise secrets.KeeperAuthRequired("the tests never sign in to Keeper")

    monkeypatch.setattr(secrets, "login_to_vault", refuse)


@pytest.fixture
def memory_vault():
    """An empty in-memory credential vault (``jason.vault.MemoryStore``): a test never reaches Keeper."""
    from jason.vault import MemoryStore

    return MemoryStore()


@pytest.fixture(autouse=True)
def _no_ollama_ocr(monkeypatch):
    """A test never reaches the machine's Ollama for OCR; a loaded model also exhausts commit and crashes numpy."""
    monkeypatch.setenv("JASON_OCR_OLLAMA", "0")


@pytest.fixture(autouse=True)
def _no_statute_fetch(monkeypatch):
    """A statute missing from a test's shelf stays a miss: no test spawns the lawlibrary worker (tests/test_statute_fetch.py
    turns the read-through on with a fake worker)."""
    monkeypatch.setenv("JASON_AUTHORITIES_FETCH", "0")


@pytest.fixture(autouse=True)
def _own_lock_dir(monkeypatch, tmp_path_factory):
    """Each test takes jason's locks in its own folder, never the machine's (a real run may hold the GPU lock)."""
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path_factory.mktemp("locks")))
