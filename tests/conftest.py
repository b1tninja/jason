import os
from pathlib import Path

import pytest

# The tests read made-up private facts (tests/fixtures/spec), never the association's real ones (data/spec): the same
# results on any checkout. Set before the specification is first imported, since it reads them when it loads.
os.environ["JASON_SPEC_DIR"] = str(Path(__file__).parent / "fixtures" / "spec")
# The tests are written against the mystique profile, whatever profile this machine's .env chooses.
os.environ["JASON_PROFILE"] = "mystique"
os.environ.pop("JASON_PROFILE_DIR", None)


@pytest.fixture(autouse=True)
def _no_ollama_ocr(monkeypatch):
    """A test never reaches the machine's Ollama for OCR; a loaded model also exhausts commit and crashes numpy."""
    monkeypatch.setenv("JASON_OCR_OLLAMA", "0")


@pytest.fixture(autouse=True)
def _own_lock_dir(monkeypatch, tmp_path_factory):
    """Each test takes jason's locks in its own folder, never the machine's (a real run may hold the GPU lock)."""
    monkeypatch.setenv("JASON_LOCK_DIR", str(tmp_path_factory.mktemp("locks")))
