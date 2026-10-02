"""The copies of forms jason sent, by reference number: which form and cycle, which owner and unit, when, and the
fingerprints of what was filled in (``owner_prefill.fingerprints``), so a reply, a returned PDF, or a scan that names its
reference is compared with exactly what that owner was sent.

The record is ``data/forms/references.json``. It holds ids and hashes, never an address or an email.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STORE = Path("forms") / "references.json"


def load(data_dir: Path) -> dict[str, dict[str, Any]]:
    path = Path(data_dir) / STORE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def record(data_dir: Path, reference: str, **info: Any) -> dict[str, Any]:
    """Keep one sent copy under its reference (a resend of the same copy updates it, keeping when it was first sent)."""
    from jason.locks import Resource, hold

    path = Path(data_dir) / STORE
    with hold(Resource.STORE, "form-references", purpose="record a sent form's reference"):
        refs = load(data_dir)
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        entry = {**refs.get(reference, {}), **info, "lastSent": now}
        entry.setdefault("firstSent", now)
        refs[reference] = entry
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(refs, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    return entry


def lookup(data_dir: Path, text: str) -> list[tuple[str, dict[str, Any]]]:
    """Each marker named in ``text`` (an email's subject and body, a scan's OCR) with the copy it stands for. A marker
    that failed its check is taken to the one sent marker a single character away, when there is exactly one
    (``form_refs.closest``). A hint either way: nothing is read differently for it."""
    from jason.community.form_refs import closest, parse

    refs = load(data_dir)
    found = [(m.text, refs[m.text]) for m in parse(text) if m.text in refs]
    if not found and refs:
        sent = [m for key in refs for m in parse(key)]
        near = closest(text, sent)
        if near is not None and near.text in refs:
            found = [(near.text, refs[near.text])]
    return found


__all__ = ["STORE", "load", "lookup", "record"]
