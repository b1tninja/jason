"""Plan a meeting: the next meeting's candidate items with computed readiness checks, the saved plan, and the notice's
required contents.

``agenda_plan(args)`` merges the ``meeting`` loader (``jason.web.sources.meeting``: the date, notice deadlines, the
items proposed or on the agenda, the packet draft, the commands) with the plan a person saved
(``jason.tasks.agenda_plan``). Each candidate carries its readiness checks, which are computed facts, never a
judgment: a motion is drafted, documents support it, an executive matter is marked executive (CIV 4935), notice can
still be given (CIV 4920), and, when the item names an interested director, a disclosure is recorded. ``suggestion`` is
one line of plain words from the failing checks. ``notice.required`` lists what the notice must carry under CIV 4920 and
4926, each line ready or not from the basics the person entered. ``write(date, body)`` saves a person's changes to the
plan and returns the merged view. Reads disk only; calls neither Google nor Zoom, and jason has no command that
creates a board meeting on Zoom (``jason hearing --create --yes`` schedules a hearing only), so the Zoom fields are
typed in by a person.
"""

from __future__ import annotations

import re
from typing import Any

Args = dict[str, str]

STEPS = ("Meeting", "Ready to act", "Order and motions", "Notice")
EXECUTIVE_WORD = "executive session"
CAVEATS = (
    "jason checks what is on file and says which items look ready. The board decides what goes on the agenda, and the board sets the agenda.",
    "Notice timing follows Civil Code 4920 (four days; two for a meeting held solely in executive session) unless the bylaws ask for more.",
    "The notice itself is a letter a person drafts, approves, and sends; nothing here sends it.",
)
FORMAT_RULES: dict[str, tuple[str, ...]] = {
    "": (),
    "in person": ("The notice names the place of the meeting (CIV 4920).",),
    "hybrid": ("The notice names a physical location where members may attend (CIV 4090(b)).",
               "A director or a board designee is present at that location (CIV 4090(b)).",
               "Directors can hear one another and the members who speak (CIV 4090(b))."),
    "teleconference": ("Clear instructions for joining the meeting (CIV 4926(a)(1)).",
                       "The telephone number and email of a person who can help before and during the meeting (CIV 4926(a)(1)).",
                       "A reminder that members may ask for individual delivery of notices (CIV 4926(a)(1)).",
                       "A telephone option for everyone entitled to take part (CIV 4926(a)(4)).",
                       "Every director vote by roll call (CIV 4926(a)(3)).",
                       "Not for a meeting where election ballots are counted (CIV 4926(b))."),
}
BASE_RULES = ("Notice and the agenda to members four days ahead (CIV 4920).",
              "Open forum for members, with a time limit the board sets (CIV 4925).",
              "Only items on the posted agenda, except as CIV 4930 allows.")


def _data_dir():
    from jason.mcp.county import _data_dir

    return _data_dir(None)


def _packet_motion(packet_md: str, item: dict[str, Any]) -> str:
    """The draft motion the packet carries for ``item``, or "" when it has only the generic frame built from the ask."""
    title = re.escape(str(item.get("title", "")))
    m = re.search(rf"^## \d+\. {title}\s*$(.*?)(?=^## \d+\. |\Z)", packet_md or "", re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    found = re.search(r"\*\*Draft motion\.\*\*\s*(.+)", m.group(1))
    if not found:
        return ""
    motion = found.group(1).strip()
    ask = str(item.get("ask", "")).strip()
    generic = f"Move that the board {ask[0].lower() + ask[1:]}" if ask else ""
    return "" if generic and motion == generic else motion


def _checks(item: dict[str, Any], saved: dict[str, Any], kind: str, packet_md: str, today: str, notice_by: str, executive_by: str) -> list[dict[str, Any]]:
    executive = item.get("agendaSession") == EXECUTIVE_WORD
    motion = str(saved.get("motion", "") or "").strip() or _packet_motion(packet_md, item)
    checks: list[dict[str, Any]] = [{"label": "Motion drafted", "ok": bool(motion)}]
    if not motion:
        checks[-1]["why"] = "no motion drafted yet; the packet's generic frame is not one"
    documents = bool(saved.get("packet")) or bool(item.get("evidence"))
    checks.append({"label": "Supporting documents", "ok": documents, **({} if documents else {"why": "no packet files attached and no evidence on the item"})})
    if executive or kind == "executive":
        ok = executive and kind == "executive"
        why = ("an executive-session matter is not marked executive (CIV 4935)" if executive and not ok
               else "marked executive, but the item is an open-session matter; CIV 4935 lists the executive topics" if not executive else "")
        checks.append({"label": "Executive session marked (CIV 4935)", "ok": ok, **({"why": why} if why else {})})
    deadline = executive_by if executive else notice_by
    can_notice = today <= deadline
    checks.append({"label": f"Notice can still be given by {deadline} (CIV 4920)", "ok": can_notice,
                   **({} if can_notice else {"why": f"notice was due {deadline}; the item waits for the next meeting unless CIV 4930(d) applies"})})
    interested = item.get("interested") or item.get("interestedDirectors")
    if interested:
        disclosed = bool(item.get("disclosed") or item.get("disclosure"))
        checks.append({"label": "Conflict disclosure recorded (Corp. Code 7233; CIV 5350)", "ok": disclosed,
                       **({} if disclosed else {"why": "an interested director is named and no disclosure is recorded"})})
    return checks


def _suggestion(checks: list[dict[str, Any]]) -> str:
    whys = [c["why"] for c in checks if not c["ok"] and c.get("why")]
    return "; ".join(whys[:1] + [w.split(";")[0] for w in whys[1:]]) if whys else ""


def _required(basics: dict[str, Any], zoom: dict[str, Any], included: list[dict[str, Any]], today: str, notice_by: str) -> list[dict[str, Any]]:
    fmt = basics.get("format", "")
    virtual, remote = fmt == "teleconference", fmt in ("hybrid", "teleconference")
    place_ok = bool(basics.get("start")) and (virtual or bool(basics.get("location")))
    rows = [{"label": "Time and place of the meeting (CIV 4920)", "ready": place_ok,
             "detail": "" if place_ok else ("a start time" if not basics.get("start") else "the location") + " is missing from the basics"},
            {"label": "The agenda: every item the board will discuss or act on (CIV 4930)", "ready": bool(included),
             "detail": f"{len(included)} item(s) on the agenda" if included else "no item is marked to include yet"}]
    if fmt == "hybrid":
        rows.append({"label": "A physical location where members may attend, with a director or designee present (CIV 4090(b))",
                     "ready": bool(basics.get("location")), "detail": basics.get("location", "") or "no location entered"})
    if remote:
        join = basics.get("join") or zoom.get("joinUrl")
        dial = basics.get("dialIn") or zoom.get("dialIn")
        rows.append({"label": "Clear instructions for joining (CIV 4926(a)(1))", "ready": bool(join), "detail": "" if join else "no join instructions or link entered"})
        rows.append({"label": "A telephone option for everyone entitled to take part (CIV 4926(a)(4))", "ready": bool(dial), "detail": "" if dial else "no dial-in entered"})
    if virtual:
        rows.append({"label": "Phone and email of a person who can help before and during the meeting (CIV 4926(a)(1))",
                     "ready": bool(basics.get("help")), "detail": "" if basics.get("help") else "no help contact entered"})
        rows.append({"label": "A reminder that members may ask for individual delivery of notices (CIV 4926(a)(1))", "ready": True,
                     "detail": "a fixed line; the notice a person drafts carries it"})
    if any(c.get("session") == EXECUTIVE_WORD for c in included):
        rows.append({"label": "Executive session matters described generally (CIV 4935)", "ready": True,
                     "detail": "listed by title only; noted generally in the next open minutes (4935(e))"})
    rows.append({"label": f"Delivered by {notice_by}, four days ahead (CIV 4920)", "ready": today <= notice_by,
                 "detail": "" if today <= notice_by else f"the notice date has passed (today {today})"})
    return rows


def agenda_plan(args: Args) -> dict[str, Any]:
    """The meeting loader's output merged with the saved plan: ``candidates`` with computed readiness, ``notice`` with
    the required contents, the ``steps``, the ``commands``, and the ``zoom`` fields a person enters by hand."""
    from jason.tasks import agenda_plan as store
    from jason.web.sources import meeting

    m = meeting(args)
    if not m.get("found", True):
        return m
    root = _data_dir()
    day = m["date"]
    plan = store.load(root, day)
    today, notice_by, executive_by = m.get("today", ""), m.get("noticeBy", ""), m.get("executiveNoticeBy", "")
    packet_md = m.get("packetMarkdown", "") or ""
    candidates = []
    for n, item in enumerate(m.get("items", [])):
        saved = dict(plan["items"].get(item["id"]) or {})
        executive = item.get("agendaSession") == EXECUTIVE_WORD
        kind = saved.get("kind") or ("executive" if executive else "action")
        checks = _checks(item, saved, kind, packet_md, today, notice_by, executive_by)
        candidates.append({
            "id": item["id"], "title": item.get("title", ""), "ask": item.get("ask", ""), "session": item.get("agendaSession", ""),
            "authority": item.get("authority", ""), "priority": item.get("priority", ""), "evidence": list(item.get("evidence") or []),
            "kind": kind, "include": bool(saved.get("include", False)),
            "motion": str(saved.get("motion", "") or "") or _packet_motion(packet_md, item),
            "allot": int(saved.get("allot", 10)), "order": int(saved.get("order", n)),
            "packet": list(saved.get("packet") or []), "brief": saved.get("brief"),
            "readiness": {"ready": all(c["ok"] for c in checks), "checks": checks},
            "suggestion": _suggestion(checks),
        })
    candidates.sort(key=lambda c: (c["session"] == EXECUTIVE_WORD, c["order"]))
    included = [c for c in candidates if c["include"]]
    commands = dict(m.get("commands") or {})
    commands["onAgenda"] = [commands.get("notice", "").replace("<item id>", c["id"]) for c in included if commands.get("notice")]
    return {
        "found": True, "date": day, "today": today, "noticeBy": notice_by, "executiveNoticeBy": executive_by,
        "directors": list(m.get("directors") or []), "decisions": list(m.get("decisions") or []),
        "basics": plan["basics"], "zoom": {**plan["zoom"], "command": None,
                                           "note": "jason has no command that creates a board meeting on Zoom (jason hearing --create --yes schedules a hearing only). Create it on the association's account and enter the join link and dial-in here."},
        "candidates": candidates, "kinds": list(store.KINDS), "formats": list(store.FORMATS),
        "rules": list(BASE_RULES) + list(FORMAT_RULES.get(plan["basics"].get("format", ""), ())),
        "notice": {"by": notice_by, "executiveBy": executive_by, "required": _required(plan["basics"], plan["zoom"], included, today, notice_by)},
        "steps": list(STEPS), "commands": commands, "updated": plan["updated"], "history": plan["history"],
        "agendaMarkdown": m.get("agendaMarkdown", ""), "caveats": list(CAVEATS) + list(m.get("caveats") or []),
    }


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """Save a person's changes to the plan for the meeting ``key`` (a date): ``by`` and any of basics, items, brief, zoom.
    jason's own store; nothing is sent, and no board item changes (the terminal commands do that)."""
    from jason.tasks import agenda_plan as store

    clean = {k: v for k, v in body.items() if v is not None}
    by = str(clean.pop("by", "") or "")
    store.update(_data_dir(), key, clean, by)
    return agenda_plan({"date": key})
