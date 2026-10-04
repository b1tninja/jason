"""The saved agenda plan for one board meeting: what a person entered while planning it.

``data/meetings/plan-<date>.json`` holds, for one meeting date, the basics a person typed (start time, format under
Civil Code 4926, location, join instructions, dial-in, help contact), each candidate board item's place on the agenda
(whether it is included, its kind, the proposed motion, the minutes allotted, its order, the Drive files in its
packet, and for an executive matter its Civil Code 4935 subject), the decision brief a person wrote for it (the question, the criteria, the options, and the facts on file),
and the Zoom details entered by hand. None of it comes from the profile and none of it is jason's judgment: the
readiness checks are computed by the loader (``jason.web.extra.agenda_plan``) from this plan and the meeting, and a
brief never carries a recommendation. ``update`` refuses a body that tries to add one. jason decides nothing here; it
keeps what the person planned.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

STORE = Path("meetings")
FORMATS = ("in person", "hybrid", "teleconference")          # CIV 4090(b), 4926
KINDS = ("consent", "discussion", "action", "executive")
BASICS = ("start", "format", "location", "join", "dialIn", "help")
ITEM_FIELDS = ("include", "kind", "motion", "allot", "order", "packet", "brief", "subject")
BRIEF_FIELDS = ("question", "criteria", "options", "facts")
PACKET_FIELDS = ("id", "name", "kind", "url")
ZOOM_FIELDS = ("topic", "joinUrl", "dialIn")
TOP_LEVEL = ("basics", "items", "brief", "zoom")
FORBIDDEN = re.compile(r"recommend", re.IGNORECASE)   # a brief has no recommended option; the board chooses


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _day(value: str) -> str:
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        raise ValueError("the meeting date is YYYY-MM-DD") from None


def path(data_dir: Path, day: str) -> Path:
    return Path(data_dir) / STORE / f"plan-{_day(day)}.json"


def empty(day: str) -> dict[str, Any]:
    return {"date": _day(day), "basics": {"date": _day(day), "start": "", "format": "", "location": "", "join": "", "dialIn": "", "help": ""},
            "items": {}, "zoom": {"topic": "", "joinUrl": "", "dialIn": ""}, "updated": "", "history": []}


def load(data_dir: Path, day: str) -> dict[str, Any]:
    """The plan for ``day``, or an empty one when nothing has been saved yet."""
    p = path(data_dir, day)
    plan = empty(day)
    if p.is_file():
        raw = json.loads(p.read_text(encoding="utf-8"))
        plan["basics"].update({k: v for k, v in (raw.get("basics") or {}).items() if k in BASICS})
        plan["items"] = dict(raw.get("items") or {})
        plan["zoom"].update({k: v for k, v in (raw.get("zoom") or {}).items() if k in ZOOM_FIELDS})
        plan["updated"] = raw.get("updated", "")
        plan["history"] = list(raw.get("history") or [])
    return plan


def save(data_dir: Path, plan: dict[str, Any]) -> Path:
    p = path(data_dir, plan["date"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plan, indent=1), encoding="utf-8")
    return p


def _store_lock(fn):
    import functools

    from jason.locks import Resource, hold

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with hold(Resource.STORE, "agenda-plan", timeout=60, purpose=f"agenda plan: {fn.__name__}"):
            return fn(*args, **kwargs)
    return wrapper


def _scan_forbidden(value: Any, where: str = "body") -> None:
    """Refuse any key that names a recommendation, anywhere in the body: a brief lays out options and the board chooses."""
    if isinstance(value, dict):
        for k, v in value.items():
            if FORBIDDEN.search(str(k)):
                raise ValueError(f"{where}.{k}: a brief has no recommended option; jason lays out the options and the board chooses")
            _scan_forbidden(v, f"{where}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            _scan_forbidden(v, f"{where}[{i}]")


def _strings(value: Any, name: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError(f"{name} is a list of strings")
    return [x.strip() for x in value if x.strip()]


def _brief(raw: Any, name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{name} is an object with question, criteria, options, facts")
    unknown = sorted(set(raw) - set(BRIEF_FIELDS))
    if unknown:
        raise ValueError(f"{name}.{unknown[0]}: not a brief field; a brief has {', '.join(BRIEF_FIELDS)}")
    out: dict[str, Any] = {"question": str(raw.get("question", "")).strip(), "criteria": _strings(raw.get("criteria", []), f"{name}.criteria"),
                           "options": [], "facts": _strings(raw.get("facts", []), f"{name}.facts")}
    options = raw.get("options", [])
    if not isinstance(options, list):
        raise ValueError(f"{name}.options is a list of {{label, values}}")
    for i, o in enumerate(options):
        if not isinstance(o, dict) or set(o) - {"label", "values"}:
            raise ValueError(f"{name}.options[{i}] is {{label, values}} and nothing else")
        label = str(o.get("label", "")).strip()
        if not label:
            raise ValueError(f"{name}.options[{i}]: an option needs a label")
        values = o.get("values", [])
        if not isinstance(values, list):
            raise ValueError(f"{name}.options[{i}].values is a list of strings, one per criterion")
        out["options"].append({"label": label, "values": [str(v) for v in values]})
    return out


def _packet(raw: Any, name: str) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise ValueError(f"{name} is a list of {{id, name, kind, url}}")
    out = []
    for i, f in enumerate(raw):
        if not isinstance(f, dict) or not str(f.get("id", "")).strip():
            raise ValueError(f"{name}[{i}]: a packet file needs its Drive id")
        out.append({k: str(f.get(k, "") or "") for k in PACKET_FIELDS})
    return out


def _item(raw: Any, name: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{name} is an object")
    unknown = sorted(set(raw) - set(ITEM_FIELDS))
    if unknown:
        raise ValueError(f"{name}.{unknown[0]}: not an agenda field; an item has {', '.join(ITEM_FIELDS)}")
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if k == "include":
            if not isinstance(v, bool):
                raise ValueError(f"{name}.include is true or false")
            out[k] = v
        elif k == "kind":
            if v not in KINDS:
                raise ValueError(f"{name}.kind is one of {', '.join(KINDS)}")
            out[k] = v
        elif k == "motion":
            out[k] = str(v)
        elif k in ("allot", "order"):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v or int(v) < 0:
                raise ValueError(f"{name}.{k} is a whole number of {'minutes' if k == 'allot' else 'places'}")
            out[k] = int(v)
        elif k == "packet":
            out[k] = _packet(v, f"{name}.packet")
        elif k == "brief":
            out[k] = _brief(v, f"{name}.brief")
        elif k == "subject":
            # An executive matter's Civil Code 4935 subject (``ExecutiveSubject``): the open minutes note the matter by
            # it, never by the item's title ("generally noted in the minutes", 4935(e)). Empty clears it.
            from jason.community.models.meetings import ExecutiveSubject

            word = str(v or "").strip()
            choices = [s.value for s in ExecutiveSubject]
            if word and word not in choices:
                raise ValueError(f"{name}.subject is one of {', '.join(choices)} (CIV 4935(a)-(d))")
            out[k] = word
    return out


def _basics(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("basics is an object")
    unknown = sorted(set(raw) - set(BASICS) - {"date"})
    if unknown:
        raise ValueError(f"basics.{unknown[0]}: not a basics field; the basics are {', '.join(BASICS)}")
    out = {k: str(v or "").strip() for k, v in raw.items() if k in BASICS}
    if "format" in out and out["format"] not in ("", *FORMATS):
        raise ValueError(f"basics.format is one of {', '.join(FORMATS)} (CIV 4926)")
    if "start" in out and out["start"] and not re.fullmatch(r"\d{2}:\d{2}", out["start"]):
        raise ValueError("basics.start is HH:MM")
    return out


@_store_lock
def update(data_dir: Path, day: str, body: dict[str, Any], by: str) -> dict[str, Any]:
    """Merge a person's changes into the plan for ``day`` and note them in its history. ``body`` carries any of
    ``basics``, ``items`` (by board item id; each item any of its fields), ``brief`` (by item id), and ``zoom``. A
    different date in ``basics`` is refused: the date is the plan's key. A key that names a recommendation is refused."""
    by = str(by or "").strip()
    if not by:
        raise ValueError("a change to the plan names who made it (by)")
    if not isinstance(body, dict):
        raise ValueError("the body is an object")
    unknown = sorted(set(body) - set(TOP_LEVEL))
    if unknown:
        raise ValueError(f"{unknown[0]}: not part of the plan; the plan has {', '.join(TOP_LEVEL)}")
    _scan_forbidden(body)
    plan = load(data_dir, day)
    changed: list[str] = []
    if "basics" in body:
        new = _basics(body["basics"])
        given = str((body["basics"] or {}).get("date", "") or "").strip()
        if given and _day(given) != plan["date"]:
            raise ValueError(f"the plan's date ({plan['date']}) is its key; plan another date as its own plan")
        for k, v in new.items():
            if plan["basics"].get(k, "") != v:
                plan["basics"][k] = v
                changed.append(f"basics.{k}")
    items = dict(body.get("items") or {})
    if not isinstance(body.get("items", {}), dict):
        raise ValueError("items is an object by board item id")
    briefs = body.get("brief") or {}
    if not isinstance(briefs, dict):
        raise ValueError("brief is an object by board item id")
    for item_id, brief in briefs.items():
        items[item_id] = {**(items.get(item_id) or {}), "brief": brief}
    for item_id, raw in items.items():
        key = str(item_id).strip()
        if not key:
            raise ValueError("an item needs its board item id")
        new = _item(raw, f"items.{key}")
        current = dict(plan["items"].get(key) or {})
        for k, v in new.items():
            if current.get(k) != v:
                current[k] = v
                changed.append(f"items.{key}.{k}")
        plan["items"][key] = current
    if "zoom" in body:
        raw = body["zoom"]
        if not isinstance(raw, dict) or set(raw) - set(ZOOM_FIELDS):
            raise ValueError(f"zoom has {', '.join(ZOOM_FIELDS)}, entered by hand")
        for k, v in raw.items():
            v = str(v or "").strip()
            if plan["zoom"].get(k, "") != v:
                plan["zoom"][k] = v
                changed.append(f"zoom.{k}")
    if not changed:
        raise ValueError("nothing to change")
    now = _now()
    plan["updated"] = now
    plan["history"].append(f"{now[:10]}: {by} changed {', '.join(changed)}")
    save(data_dir, plan)
    return plan


__all__ = ["STORE", "FORMATS", "KINDS", "BASICS", "ITEM_FIELDS", "BRIEF_FIELDS", "ZOOM_FIELDS", "path", "empty", "load", "save", "update"]
