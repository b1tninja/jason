"""The controls' record: what is adopted is a private fact, and what happens to a control is an append-only log.

- The association's controls start as private facts: ``data/spec/<profile>/controls.json`` (``{"controls": [...]}``),
  read through ``jason.community.private.facts``, never checked in. A profile may also return rows from
  ``Community.controls()``; ``load(community=...)`` adds them.
- Every act on a control (suggest, propose, adopt, decline, defer, retire) is one line of ``controls/acts.jsonl`` in the
  profile's data folder: who, when, why, and what the act carried. A line is appended under the store lock (a read, a
  check, one atomic write), and each carries the hash of the line before it, so an edit anywhere is found (``verify``).
- The current controls are the facts' controls with the acts folded over them (``fold``). A control that would go
  below a floor is refused at the act, and again when loaded.

Nothing here approves anything: an act names a person (``by``) and says why. jason records what the secretary
recorded; it never adopts a control on its own.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from jason.controls.types import (MOVES, Control, ControlAct, ControlRefused, ControlState, HistoryEntry, from_dict,
                                  parameters_from_dict, parameters_to_dict, to_dict)

LOCK_KEY = "controls"
TOPIC = "controls"


def controls_dir(data_dir: Path | None = None) -> Path:
    """``controls/`` in ``data_dir``, else in the active profile's data folder, resolved when called."""
    if data_dir is None:
        from jason.config import data_dir as profile_data_dir

        data_dir = profile_data_dir()
    return Path(data_dir) / "controls"


def acts_path(data_dir: Path | None = None) -> Path:
    return controls_dir(data_dir) / "acts.jsonl"


def facts_path(profile: str = "") -> Path:
    from jason.community import private

    return private.path_of(TOPIC, profile)


def configured(data_dir: Path | None = None, profile: str = "") -> bool:
    """Whether any source of controls exists: an act log, or the profile's controls facts. Reads nothing else."""
    if acts_path(data_dir).is_file():
        return True
    try:
        return facts_path(profile).is_file()
    except Exception as exc:  # noqa: BLE001
        from jason.community.profile import CommunityNotChosen

        if isinstance(exc, CommunityNotChosen):
            return False
        raise


# --- the facts ------------------------------------------------------------------------------------------------------------

def seed(profile: str = "") -> list[Control]:
    """The controls in the profile's private facts (empty when there are none), checked as they are loaded."""
    from jason.community import private

    raw = private.facts(TOPIC, profile=profile)
    rows = raw.get("controls", []) if isinstance(raw, Mapping) else raw
    return [_checked(from_dict(r)) for r in rows or ()]


def _checked(control: Control) -> Control:
    from jason.controls.effective import ensure_valid

    return ensure_valid(control)


# --- the log --------------------------------------------------------------------------------------------------------------

def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _digest(row: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canon({k: v for k, v in row.items() if k != "hash"}).encode("utf-8")).hexdigest()


def acts(data_dir: Path | None = None) -> list[dict[str, Any]]:
    """The acts, oldest first."""
    file = acts_path(data_dir)
    if not file.is_file():
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify(data_dir: Path | None = None) -> tuple[bool, int | None, str]:
    """Walk the chain: (whole, the first broken line's number, why)."""
    file = acts_path(data_dir)
    if not file.is_file():
        return True, None, "no acts yet"
    prev = ""
    for n, line in enumerate(file.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            return False, n, "not JSON"
        if row.get("prev", "") != prev:
            return False, n, "its prev is not the hash of the line before"
        if _digest(row) != row.get("hash"):
            return False, n, "its hash does not match its contents"
        prev = row["hash"]
    return True, None, "the chain is whole"


def _reached(day: str, at: str) -> bool:
    return bool(day) and day <= at[:10]


def apply_act(current: Control | None, row: Mapping[str, Any]) -> Control:
    """One act on a control, as the log records it: the control after, or ``ControlRefused``. Pure; the writer and the
    fold both use it, so a line that could not have been written cannot be read."""
    try:
        act = ControlAct(row.get("act"))
    except ValueError:
        raise ControlRefused(f"{row.get('act')!r} is not an act on a control") from None
    by, why, at = str(row.get("by") or "").strip(), str(row.get("why") or "").strip(), str(row.get("at") or "")
    if not by:
        raise ControlRefused("an act on a control names the person (by)")
    if not why:
        raise ControlRefused("an act on a control says why")
    starts, ends = MOVES[act]
    state = current.state if current else None
    if state not in starts:
        raise ControlRefused(f"{row.get('key')}: a control that is {state.value if state else 'new'} cannot "
                             f"{act.value}")
    entry = HistoryEntry(act, by, at, why, str(row.get("decision") or ""), str(row.get("againOn") or ""))
    if act is ControlAct.SUGGEST:
        made = from_dict({**(row.get("control") or {}), "key": row.get("key"), "state": "suggested", "history": []})
        return _checked(replace(made, history=(entry,)))
    assert current is not None
    if act is ControlAct.PROPOSE and state in (ControlState.DECLINED, ControlState.DEFERRED):
        last = next(h for h in reversed(current.history) if h.act in (ControlAct.DECLINE, ControlAct.DEFER))
        if state is ControlState.DECLINED and not last.again_on:
            raise ControlRefused(f"{current.key} was declined with no date to ask again")
        if last.again_on and not _reached(last.again_on, at):
            raise ControlRefused(f"{current.key} may be asked again on {last.again_on}, not before")
    changes: dict[str, Any] = {"state": MOVES[act][1], "history": current.history + (entry,)}
    if act is ControlAct.ADOPT:
        if not entry.decision:
            raise ControlRefused("an adoption names the decision the secretary recorded")
        try:
            effective = date.fromisoformat(str(row.get("effective") or ""))
        except ValueError:
            raise ControlRefused("an adoption names the effective date (YYYY-MM-DD)") from None
        params = (parameters_from_dict(current.type, row["parameters"]) if row.get("parameters") is not None
                  else dict(current.parameters))
        changes.update(parameters=params, decision=entry.decision, effective=effective)
    return _checked(replace(current, **changes))


def fold(start: Iterable[Control], rows: Iterable[Mapping[str, Any]]) -> dict[str, Control]:
    """The controls now: ``start`` (the facts' controls) with every act applied in order."""
    out = {c.key: c for c in start}
    for n, row in enumerate(rows, 1):
        key = str(row.get("key") or "")
        try:
            out[key] = apply_act(out.get(key), row)
        except ControlRefused as exc:
            raise ControlRefused(f"act {row.get('seq', n)} on {key or '?'}: {exc}") from exc
    return out


def load(data_dir: Path | None = None, profile: str = "", community: Any = None) -> list[Control]:
    """Every control now, in a stable order (family, then key): the facts', the community's own, and the acts folded in."""
    start = seed(profile)
    if community is not None:
        mine = [_checked(c) for c in community.controls()]
        dup = {c.key for c in start} & {c.key for c in mine}
        if dup:
            raise ControlRefused("a control is in both the facts and the profile: " + ", ".join(sorted(dup)))
        start += mine
    folded = fold(start, acts(data_dir))
    return sorted(folded.values(), key=lambda c: (c.type.family.value, c.key))


def get(key: str, data_dir: Path | None = None, profile: str = "", community: Any = None) -> Control:
    for c in load(data_dir, profile, community):
        if c.key == key:
            return c
    raise KeyError(f"no control {key}")


def record(act: ControlAct, key: str, *, by: str, why: str, control: Control | None = None,
           parameters: Mapping[str, Any] | None = None, decision: str = "", effective: date | str | None = None,
           again_on: str = "", data_dir: Path | None = None, profile: str = "", community: Any = None,
           now: datetime | None = None) -> Control:
    """Append one act and return the control it leaves. ``control`` carries a suggestion; ``parameters``, ``decision``
    and ``effective`` an adoption (the parameters as the board adopted them); ``again_on`` a decline or a deferral.
    Refused, with nothing written, when the move is not allowed or the control would go below a floor."""
    from jason.locks import Resource, hold

    now = now or datetime.now(timezone.utc)
    row: dict[str, Any] = {"at": now.isoformat(timespec="seconds"), "key": key, "act": act.value, "by": by.strip(),
                           "why": why.strip()}
    if act is ControlAct.SUGGEST:
        if control is None:
            raise ControlRefused("a suggestion carries the control")
        row["control"] = to_dict(replace(control, key=key, history=(), state=ControlState.SUGGESTED))
    if parameters is not None:
        row["parameters"] = parameters_to_dict(_type_of(key, control, data_dir, profile, community), parameters)
    for name, value in (("decision", decision), ("againOn", again_on),
                        ("effective", effective.isoformat() if isinstance(effective, date) else effective or "")):
        if value:
            row[name] = value
    file = acts_path(data_dir)
    file.parent.mkdir(parents=True, exist_ok=True)
    with hold(Resource.STORE, LOCK_KEY, timeout=60, purpose=f"controls: {act.value} {key}"):
        current = {c.key: c for c in load(data_dir, profile, community)}
        after = apply_act(current.get(key), row)          # refused here writes nothing
        log = acts(data_dir)
        row["seq"] = (int(log[-1]["seq"]) + 1) if log else 1
        row["prev"] = log[-1]["hash"] if log else ""
        row["hash"] = _digest(row)
        with file.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(_canon(row) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
    return after


def _type_of(key: str, control: Control | None, data_dir: Path | None, profile: str, community: Any):
    if control is not None:
        return control.type
    return get(key, data_dir, profile, community).type


__all__ = ["LOCK_KEY", "TOPIC", "acts", "acts_path", "apply_act", "configured", "controls_dir", "facts_path", "fold",
           "get", "load", "record", "seed", "verify"]
