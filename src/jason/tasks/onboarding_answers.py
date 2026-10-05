"""Answers that become records: the appliers for ``FACT`` and ``MAP`` intake questions.

``jason intake --apply`` and ``jason onboard --apply`` call ``apply_answer`` through ``jason.tasks.intake.apply`` for
each answered question of these kinds (a high-stakes one only once a second person confirmed it). Where an answer goes
is the question's ``record`` (``jason.community.onboarding.FactRecord``):

- **Private facts** (people, account numbers, the tax ID) merge into ``data/spec/<profile>.json`` under ``facts``,
  keyed by the checklist item. The file is copied to ``data/spec/backups/`` first, the change is shown as a diff, and
  a fact already there with another answer is never overwritten silently: apply refuses unless ``replace`` is given.
  A question with a ``topic`` (a change of office, a term) appends its rows to that topic instead
  (``data/spec/<profile>/<topic>.json``, in the form ``jason.community.roster`` reads), with a backup and a diff; a row
  already there is not added twice, and nothing there is changed.
- **Secrets** become a record that the secret is kept in Keeper, under the record the person named, with no value. (An
  answer that looks like a secret was refused when it was given: ``intake.secret_reason``.)
- **Profile facts** (a book mapping, a pinned folder, a board seat count) become a proposed change: a patch under
  ``data/onboarding/proposals/`` for a person to review and apply (``git apply``). Where jason can write the row (a
  ``BookEntry``, a record pinned on an existing library folder) the proposal is a ``.patch`` with a hunk against the
  profile's own file; otherwise a ``.md`` with the answer and the ``Community`` method it fills, for a person to write.
  jason never edits the profile itself.

Every record names who answered and when, and who confirmed.
"""

from __future__ import annotations

import difflib
import inspect
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.intake import Ask, AskKind
from jason.community.onboarding import FACTS, FactRecord

PROPOSALS = Path("onboarding") / "proposals"


@dataclass(frozen=True)
class Outcome:
    applied: bool
    record: str = ""          # what the answer became (the ask's ``applied_to``)
    shown: str = ""           # a diff or a proposal, for the person to read
    reason: str = ""          # why it was not applied


def _signature(a: Ask) -> dict[str, str]:
    out = {"answered_by": a.answered_by, "answered_at": a.answered_at, "question": a.id}
    if a.confirmed_by:
        out.update(confirmed_by=a.confirmed_by, confirmed_at=a.confirmed_at)
    return out


# --- Private facts ----------------------------------------------------------------------------------------------------

def _value(entry: Any) -> str:
    if isinstance(entry, dict):
        return str(entry.get("answer") or entry.get("record") or "")
    return str(entry or "")


def merge_private(profile: str, key: str, entry: dict[str, Any], *, spec_dir: Path | None = None,
                  replace: bool = False) -> Outcome:
    """Merge one fact into ``<spec dir>/<profile>.json`` under ``facts``: a backup first, a diff shown, and a different
    answer already there refused unless ``replace``."""
    from jason.community.private import spec_dir as default_spec_dir
    from jason.locks import Resource, hold

    if not profile:
        return Outcome(False, reason="no profile named: the private facts file is data/spec/<profile>.json")
    folder = Path(spec_dir) if spec_dir is not None else default_spec_dir()
    path = folder / f"{profile}.json"
    with hold(Resource.STORE, f"spec-{profile}", timeout=120, purpose=f"private facts: {key}"):
        before = path.read_text(encoding="utf-8") if path.is_file() else ""
        data = json.loads(before) if before.strip() else {}
        if not isinstance(data, dict):
            return Outcome(False, reason=f"{path.name} is not a JSON object; fix it by hand")
        facts = data.setdefault(FACTS, {})
        old = facts.get(key)
        if old and _value(old) == _value(entry):
            return Outcome(True, f"already in private facts {path.name}: {key}")
        if old and not replace:
            return Outcome(False, reason=f"the private facts already hold {key} with another answer (answered by "
                                         f"{old.get('answered_by', '?') if isinstance(old, dict) else '?'}); jason never "
                                         f"overwrites a fact silently: apply again with --replace to replace it")
        facts[key] = entry
        after = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
        backup = None
        if before:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = folder / "backups" / f"{profile}-{stamp}.json"
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(before, encoding="utf-8")
        folder.mkdir(parents=True, exist_ok=True)
        path.write_text(after, encoding="utf-8")
    shown = before if not before or before.endswith("\n") else before + "\n"
    diff = "".join(difflib.unified_diff(shown.splitlines(keepends=True), after.splitlines(keepends=True),
                                        fromfile=f"{path.name} (before)", tofile=path.name))
    return Outcome(True, f"private facts {path.name}: {key}" + (f" (backup {backup.name})" if backup else ""), diff)


def _same(row: dict[str, Any], old: Any) -> bool:
    return isinstance(old, dict) and all(old.get(k) == v for k, v in row.items())


def append_topic(profile: str, topic: str, a: Ask, *, spec_dir: Path | None = None) -> Outcome:
    """Append an answer's rows (``jason.community.roster.rows_for``) to the private fact topic ``topic``, each signed
    with who answered and confirmed: the file ``facts(topic)`` reads, copied to ``backups/`` first, the change shown as
    a diff. A row already there is not added again; nothing already there is changed."""
    from jason.community.private import path_of
    from jason.community.private import spec_dir as default_spec_dir
    from jason.community.roster import FormError, rows_for
    from jason.locks import Resource, hold

    if not profile:
        return Outcome(False, reason="no profile named: the topic is data/spec/<profile>/<topic>.json")
    try:
        rows = rows_for(topic, a.answer)
    except FormError as exc:
        return Outcome(False, reason=f"not in the question's form: {exc}; answer again")
    folder = Path(spec_dir) if spec_dir is not None else default_spec_dir()
    path = path_of(topic, profile, folder=folder)
    with hold(Resource.STORE, f"spec-{profile}-{topic}", timeout=120, purpose=f"private facts: {topic}"):
        before = path.read_text(encoding="utf-8") if path.is_file() else ""
        data = json.loads(before) if before.strip() else []
        if not isinstance(data, list):
            return Outcome(False, reason=f"{path.name} is not a JSON list; fix it by hand")
        fresh = [r for r in rows if not any(_same(r, old) for old in data)]
        if not fresh:
            return Outcome(True, f"already in private facts {topic}")
        data += [{**r, **_signature(a)} for r in fresh]
        after = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
        backup = None
        if before:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = folder / "backups" / f"{profile}-{topic}-{stamp}.json"
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(before, encoding="utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(after, encoding="utf-8")
    shown = before if not before or before.endswith("\n") else before + "\n"
    diff = "".join(difflib.unified_diff(shown.splitlines(keepends=True), after.splitlines(keepends=True),
                                        fromfile=f"{path.name} (before)", tofile=path.name))
    return Outcome(True, f"private facts {topic}: {len(fresh)} row{'' if len(fresh) == 1 else 's'} added"
                   + (f" (backup {backup.name})" if backup else ""), diff)


def apply_fact(a: Ask, *, profile: str, data_dir: Path, community: Any = None, spec_dir: Path | None = None,
               replace: bool = False) -> Outcome:
    try:
        record = FactRecord(a.detail.get("record") or FactRecord.PRIVATE.value)
    except ValueError:
        return Outcome(False, reason=f"unknown record {a.detail.get('record')!r}")
    key = str(a.detail.get("item") or a.serves or a.subject.removeprefix("fact:"))
    if record is FactRecord.PROFILE:
        return propose(a, data_dir=data_dir, community=community)
    topic = str(a.detail.get("topic") or "")
    if record is FactRecord.PRIVATE and topic:
        return append_topic(profile, topic, a, spec_dir=spec_dir)
    if record is FactRecord.KEEPER:
        entry = {"kept_in": "Keeper", "record": a.answer.strip(), **_signature(a)}
    else:
        entry = {"answer": a.answer.strip(), **_signature(a)}
    return merge_private(profile, key, entry, spec_dir=spec_dir, replace=replace)


# --- Proposed profile changes -----------------------------------------------------------------------------------------

def _package(community: Any) -> Path | None:
    try:
        return Path(inspect.getfile(type(community))).resolve().parent
    except (TypeError, OSError):
        return None


_OPENS = re.compile(r"^[A-Z][A-Z0-9_]*\s*(?::[^=]+)?=\s*\(\s*$")


def insert_row(package: Path, type_name: str, rows: list[str]) -> tuple[Path, str, str] | None:
    """The profile file whose top-level tuple holds ``type_name(...)`` rows, its text, and its text with ``rows`` added
    before the tuple's closing line; None when no such tuple is found."""
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if f"{type_name}(" not in text:
            continue
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if not _OPENS.match(line.rstrip("\n")):
                continue
            end = next((j for j in range(i + 1, len(lines)) if lines[j].rstrip() == ")"), None)
            if end is None or not any(f"{type_name}(" in x for x in lines[i + 1:end]):
                continue
            new = lines[:end] + [f"    {row},\n" for row in rows] + lines[end:]
            return path, text, "".join(new)
    return None


def pin_record(package: Path, folder: str, record: str) -> tuple[Path, str, str] | None:
    """The profile file with the ``LibraryFolder`` row for ``folder`` (its path, on one line) changed to also hold the
    5200 ``record``; None when no such row is found."""
    member = f"AssociationRecord.{record.upper()}"
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "LibraryFolder(" not in text or f'"{folder}"' not in text:
            continue
        lines = text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if "LibraryFolder(" not in line or f'"{folder}"' not in line:
                continue
            if member in line:
                return None
            body = line.rstrip("\n")
            if "records=(" in body:
                body = body.replace("records=(", f"records=({member}, ", 1)
            elif "(AssociationRecord." in body:
                body = body.replace("(AssociationRecord.", f"({member}, AssociationRecord.", 1)
            elif body.rstrip().endswith("),"):
                stripped = body.rstrip()
                body = stripped[:-2] + f", records=({member},)),"
            else:
                return None
            lines[i] = body + "\n"
            return path, text, "".join(lines)
    return None


def _slug(text: str) -> str:
    stem = Path(text.removeprefix("library:")).stem
    return re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")[:60] or "document"


def change_for(a: Ask, community: Any) -> tuple[tuple[Path, str, str] | None, str, str]:
    """The edit a MAP answer makes (file, before, after) when jason can write it, the row in words, and the
    ``Community`` method it fills."""
    package = _package(community)
    d = a.detail
    answer = a.answer.strip()
    # The row goes in the checked-in profile, so it names the question and the day, never the person (who is in the
    # proposal's header and the queue, both under data/).
    note = f"mapped from intake question {a.id} ({a.answered_at[:10]})"
    if d.get("map") == "book":
        book = str(d.get("book") or "")
        member = f"Book.{book.upper()}"
        outlines = list(d.get("outlines") or ())
        if answer.lower().startswith("all ") and outlines:
            keys = outlines
        elif answer in outlines:
            keys = [answer]
        elif answer.startswith("library:") or answer in (d.get("files") or ()):
            keys = [_slug(answer)]
            note += f"; outline {answer.removeprefix('library:')} first (jason outlines --fetch)"
        else:
            return None, f"book {book}: {answer}", "book_entries"
        rows = [f'BookEntry("{k}", {member}, note="{note}")' for k in keys]
        edit = insert_row(package, "BookEntry", rows) if package is not None else None
        return edit, "; ".join(rows), "book_entries"
    if d.get("map") == "record":
        record = str(d.get("record") or "")
        folder = answer if answer.endswith("/") else answer + "/"
        edit = pin_record(package, folder, record) if package is not None else None
        return edit, f"pin AssociationRecord.{record.upper()} on the library folder {folder}", "library_folders"
    return None, answer, str(d.get("method") or "")


def propose(a: Ask, *, data_dir: Path, community: Any = None) -> Outcome:
    """Write the proposed change under ``data/onboarding/proposals/``: a ``.patch`` when jason can write the hunk, else a
    ``.md`` for a person to write. Nothing in the profile changes."""
    if community is None:
        from jason.community import community as active

        community = active()
    edit, row, method = change_for(a, community) if a.kind is AskKind.MAP else (None, a.answer.strip(),
                                                                                  str(a.detail.get("method") or ""))
    folder = Path(data_dir) / PROPOSALS
    folder.mkdir(parents=True, exist_ok=True)
    head = [f"Proposed by jason from intake question {a.id} ({a.kind.value} {a.subject}).",
            f"Question: {a.question}",
            f"Answer: {a.answer} (by {a.answered_by}, {a.answered_at})"
            + (f"; confirmed by {a.confirmed_by}, {a.confirmed_at}" if a.confirmed_by else ""),
            f"Fills: Community.{method}()" if method else "Fills: the profile",
            "jason never edits the profile: a person reviews this, then applies it (git apply) or writes it by hand."]
    if edit is not None:
        path, before, after = edit
        package = path.parent
        rel = f"{package.name}/{path.name}"
        diff = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                            fromfile=f"a/{rel}", tofile=f"b/{rel}"))
        out = folder / f"{a.id}.patch"
        text = "".join(f"# {h}\n" for h in head) + f"diff --git a/{rel} b/{rel}\n" + diff
        out.write_text(text, encoding="utf-8")
        return Outcome(True, f"proposal {PROPOSALS.as_posix()}/{out.name}", text)
    out = folder / f"{a.id}.md"
    where = _package(community)
    text = "\n".join([f"# Proposed profile change ({a.id})", "", *(f"- {h}" for h in head), "",
                      "No hunk: jason cannot write this change from the answer. Write it in the profile"
                      + (f" ({where.name}/), " if where is not None else ", ")
                      + (f"in the method or rows behind Community.{method}()" if method else "where it belongs") + ":", "",
                      f"    {row}", ""])
    out.write_text(text, encoding="utf-8")
    return Outcome(True, f"proposal {PROPOSALS.as_posix()}/{out.name} (to write by hand)", text)


def apply_answer(a: Ask, *, data_dir: Path, community: Any = None, profile: str = "", spec_dir: Path | None = None,
                 replace: bool = False) -> Outcome:
    """Apply one answered FACT or MAP question."""
    if a.kind is AskKind.FACT:
        if not profile:
            from jason.community.profile import profile_name

            profile = profile_name()
        return apply_fact(a, profile=profile, data_dir=data_dir, community=community, spec_dir=spec_dir, replace=replace)
    if a.kind is AskKind.MAP:
        return propose(a, data_dir=data_dir, community=community)
    return Outcome(False, reason=f"no applier for {a.kind.value}")


__all__ = ["Outcome", "PROPOSALS", "append_topic", "apply_answer", "apply_fact", "change_for", "insert_row", "merge_private",
           "pin_record", "propose"]
