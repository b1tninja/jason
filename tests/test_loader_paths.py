"""The guard on what jason-web's loaders answer (docs/console/doc-component.md, "The reference"): a loader returns
document references, never an absolute path. Each ``/api/<name>`` loader is called on a made-up data folder, and no
string in its JSON may start with a drive letter or a root folder.

``ALLOWED`` lists the answers that carry one today, each with the group that removes it; a fixed loader comes off the
list (the test fails on an entry that no longer carries one, so the list only shrinks)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|/(?:Users|home|tmp|var|mnt|private|data|srv|opt)/)")

# loader name -> (the JSON path that carries an absolute path today, any index, the group that removes it)
ALLOWED: dict[str, tuple[str, str]] = {
    "communities": (".communities[].where", "associations picker (not a screen group): the profile's folder, not data/"),
    "minutes-review": (".drafts[].file", "Meetings: Minutes review's relative paths"),
}


def _shape(where: str) -> str:
    return re.sub(r"\[\d+\]", "[]", where)


def _strings(value, where=""):
    if isinstance(value, str):
        yield where, value
    elif isinstance(value, dict):
        for key, inner in value.items():
            yield from _strings(inner, f"{where}.{key}")
    elif isinstance(value, list):
        for i, inner in enumerate(value):
            yield from _strings(inner, f"{where}[{i}]")


@pytest.fixture
def data(tmp_path, monkeypatch):
    """A made-up data folder with a few documents where the screens look for them."""
    monkeypatch.setenv("JASON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "payhoa.db"))
    (tmp_path / "governing").mkdir()
    (tmp_path / "governing" / "Example Declaration.pdf").write_bytes(b"%PDF-1.4 example")
    (tmp_path / "mail" / "100").mkdir(parents=True)
    (tmp_path / "mail" / "100" / "contents.pdf").write_bytes(b"%PDF-1.4 letter")
    (tmp_path / "board").mkdir()
    (tmp_path / "board" / "minutes-draft-2099-01-01.md").write_text("# DRAFT Minutes\n", encoding="utf-8")
    (tmp_path / "board" / "items.json").write_text(json.dumps([]), encoding="utf-8")
    return tmp_path


def test_no_loader_answers_an_absolute_path(data):
    from jason.web.sources import default_loaders

    found: dict[str, list[tuple[str, str]]] = {}
    ran = 0
    roots = {str(data), data.as_posix(), str(Path(__file__).resolve().parents[1]),
             Path(__file__).resolve().parents[1].as_posix()}
    for name, load in sorted(default_loaders().items()):
        try:
            out = load({})
        except Exception:  # noqa: BLE001 - a loader that cannot answer an empty folder has nothing to leak
            continue
        ran += 1
        hits = [(w, s) for w, s in _strings(json.loads(json.dumps(out, default=str)))
                if ABSOLUTE.match(s.strip()) or any(s.strip().startswith(r) for r in roots)]
        if hits:
            found[name] = hits
    assert ran >= 30, f"only {ran} loaders answered a made-up folder"
    new = {n: [w for w, _ in h] for n, h in found.items()
           if n not in ALLOWED or any(_shape(w) != ALLOWED[n][0] for w, _ in h)}
    assert not new, f"loaders answer absolute paths (return a DocRef or a path under data/ instead): {new}"
    gone = sorted(set(ALLOWED) - set(found))
    assert not gone, f"no longer carries an absolute path; take it off ALLOWED: {gone}"
