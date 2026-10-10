"""The record checklist, read only (docs/record-intake.md): the slots for the records an association must be able to put its
hands on, and what a person picked or answered for each. Two tools, ``record_slots`` and ``record_slot``. Neither picks,
answers, or unpins: those are a person's act at the terminal (``jason records --pick``) or the console, as the person.
Neither calls Drive, PayHOA, Google, or Keeper. A confidential file is never named here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

CAVEATS = (
    "A slot's state is jason's reading of records on disk. A person's answer (not applicable, none exists, waiting) is "
    "theirs, with their name; jason never makes one.",
    "Empty means nobody has spoken for the slot, not that the record does not exist; missing is not none. The association "
    "may hold the record outside jason.",
    "A file's classification is a suggestion until a person confirms it, and a reading is never verified against the law. "
    "A file that reads as another kind than the slot's is shown as a problem, never silently accepted.",
    "A confidential file is held back: its name is masked and its id shortened. Open the private view in the console to "
    "see it.",
    "This tool reads. A pick, an answer, and an unpin are a person's act (jason records --pick / --answer / --unpin, "
    "each a dry run until --yes); jason proposes and never decides that a record is complete.",
)


def _root(data_dir: Path | None) -> Path:
    from jason.config import Settings

    return Path(data_dir) if data_dir is not None else Settings.load().payhoa_catalog.parent


def _community() -> Any:
    from jason.community import community

    return community()


def record_slots(group: str = "", state: str = "", data_dir: Path | None = None) -> dict[str, Any]:
    """The association's record checklist: each slot (one record the association must hold, by the law or document that
    requires it, cited), its state (empty, picked, classified, read, confirmed, not applicable, does not exist, waiting on
    someone else, or problem), how many files are pinned and held back, and the biggest unknowns first. ``group`` (governing,
    recorded, finance, meetings, ...) and ``state`` narrow the listing; the counts stay whole. Reads disk only. Empty is
    not none: say so. A file's name is never in this listing."""
    from jason.tasks import record_slots as rs

    try:
        return {**rs.view(_community(), _root(data_dir), group=group.strip(), state=state.strip(), private=False),
                "caveats": list(CAVEATS)}
    except Exception as exc:  # a reader that fails is an answer, not a traceback
        return {"found": False, "error": f"{type(exc).__name__}: {exc}", "caveats": list(CAVEATS)}


def record_slot(key: str, data_dir: Path | None = None) -> dict[str, Any]:
    """One slot of the record checklist: the citation that requires it, what is held (each pin with who made it and when,
    what the classified library read it as, and whether that agrees with the kind the slot expects), the specification's own
    pins, any collision (two holders on a slot that holds one: neither wins), the candidates in the library that are not
    pinned, a person's answer and the trail. A confidential file is named by its kind only, and its id is shortened. A
    wrong-slot pick is a problem, with the slots it fits. Reads disk only; a reading is a suggestion until a person
    confirms it."""
    from jason.tasks import record_slots as rs

    try:
        return {**rs.slot_view(key.strip(), _community(), _root(data_dir), private=False), "caveats": list(CAVEATS)}
    except Exception as exc:  # a reader that fails is an answer, not a traceback
        return {"found": False, "key": key, "error": f"{type(exc).__name__}: {exc}", "caveats": list(CAVEATS)}


TOOLS = (record_slots, record_slot)
