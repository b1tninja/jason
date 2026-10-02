"""Which email the association answers, learned from its own replies, and which open threads likely need one.

A thread is a question put to the association when its first message came in. It was **answered** when a message went
out after an inbound one; the reply time is from the first inbound message to the first reply after it. The history is
the threads that came in more than ``settle_days`` ago, so a thread still inside the usual reply time is not counted as
unanswered.

Reply rates are kept at three levels, from the most to the least specific, and a thread takes the first level with at
least ``min_threads`` of history:

1. the same sender: a named sender (``Sender.domains``), or a business domain;
2. the same kind of party asking the same kind of thing: owner, buyer, former owner, board member, personal, a
   sender's kind (vendor, insurer, government agency, ...), or an unnamed business, with the thread's first intent;
3. the same kind of party.

An open thread (its last message came in) with a rate of one half or more, or one the association already answered once,
**likely needs a response**; it is **past the usual time** when it is older than three replies in four took at its
level, and at least two days old. The rate says what the association has done,
not what it must do: a thread the history rarely answered may still need an answer.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any

from jason.community.topics import Intent, intents_of

LIKELY = 0.5
REPORT = "replies.json"


def _at(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
    except ValueError:
        return None


def party_class(row: dict[str, Any]) -> str:
    """The kind of party a thread is with: owner, buyer, former owner, board member, a sender's kind, business, or personal."""
    parties = row.get("parties") or []
    for p in parties:
        if p.startswith("former owner of"):
            return "former owner"
    for p in parties:
        if p.startswith("buyer of"):
            return "buyer"
    for p in parties:
        if p.startswith("owner of"):
            return "owner"
    if "board member" in parties:
        return "board member"
    if row.get("senderKind"):
        return row["senderKind"]
    if row.get("domains"):
        return "business"
    return "personal" if "personal" in parties else "other"


def _answered(messages: list[dict[str, Any]]) -> tuple[bool, float | None]:
    """(whether a message went out after the first inbound one, days from that inbound message to the first such reply)."""
    first_in = next((m for m in messages if m["direction"] == "in"), None)
    if first_in is None:
        return False, None
    start = _at(first_in["at"])
    reply = next((m for m in messages if m["direction"] == "out" and m["at"] > first_in["at"]), None)
    if reply is None or start is None:
        return False, None
    return True, round((_at(reply["at"]) - start).total_seconds() / 86400, 2)


def reply_needed(data_dir: Path, community: Any, *, today: date | None = None, settle_days: int = 14, min_threads: int = 5,
                 open_days: int = 120) -> dict[str, Any]:
    from jason.tasks.request_links import _messages_by_thread
    from jason.tasks.threads import threads

    day = today or date.today()
    rules = tuple(community.intent_rules())
    rows = [r for r in threads(data_dir, community)["rows"] if r["status"] not in ("notice", "internal")]
    by_thread = _messages_by_thread(data_dir)
    settle = (day - timedelta(days=settle_days)).isoformat()
    stats: dict[tuple, dict[str, Any]] = {}

    def keys(r: dict[str, Any]) -> list[tuple]:
        cls = party_class(r)
        intent = next(iter(intents_of(r["subject"], rules)), None)
        sender = r["sender"] or (r["domains"][0] if r["domains"] else "")
        found: list[tuple] = []
        if sender:
            found.append(("sender", sender))
        found.append(("class+intent", cls, intent.value if intent else "unclear"))
        found.append(("class", cls))
        return found

    history = []
    for r in rows:
        messages = sorted(by_thread.get(r["threadId"], []), key=lambda m: m["at"])
        if not messages or messages[0]["direction"] != "in" or r["first"] > settle:
            continue
        answered, days = _answered(messages)
        history.append((r, answered, days))
        for k in keys(r):
            e = stats.setdefault(k, {"threads": 0, "answered": 0, "days": []})
            e["threads"] += 1
            e["answered"] += int(answered)
            if days is not None:
                e["days"].append(days)

    def rate(k: tuple) -> dict[str, Any] | None:
        e = stats.get(k)
        if not e or e["threads"] < min_threads:
            return None
        days = sorted(e["days"])
        return {"level": k[0], "key": " / ".join(str(x) for x in k[1:]), "threads": e["threads"],
                "replyRate": round(e["answered"] / e["threads"], 2), "medianDays": round(median(days), 1) if days else None,
                # Three replies in four came within this many days.
                "usualDays": round(days[min(len(days) - 1, int(0.75 * len(days)))], 1) if days else None}

    since = (day - timedelta(days=open_days)).isoformat()
    open_rows = []
    for r in rows:
        if r["status"] != "awaiting us" or r["last"] < since:
            continue
        basis = next((x for x in (rate(k) for k in keys(r)) if x), None)
        if basis is None:
            continue
        messages = sorted(by_thread.get(r["threadId"], []), key=lambda m: m["at"])
        replied_before = any(m["direction"] == "out" for m in messages)
        likely = basis["replyRate"] >= LIKELY or replied_before
        # Past the usual time: older than three replies in four took at this level, and at least two days.
        overdue = bool(basis["usualDays"] is not None and r["ageDays"] > max(2.0, basis["usualDays"]))
        open_rows.append({"threadId": r["threadId"], "last": r["last"], "ageDays": r["ageDays"], "subject": r["subject"][:100],
                          "who": r["sender"] or ", ".join(r["parties"][:2]), "partyClass": party_class(r), "topics": r.get("topics") or [],
                          "repliedBefore": replied_before, "likelyNeedsResponse": likely, "pastUsualTime": overdue,
                          "basis": basis, "link": r["link"]})
    open_rows.sort(key=lambda o: (not o["likelyNeedsResponse"], not o["pastUsualTime"], -o["basis"]["replyRate"], -o["ageDays"]))
    classes = sorted((rate(k) for k in stats if k[0] == "class"), key=lambda x: -(x or {}).get("threads", 0))
    pairs = sorted((x for x in (rate(k) for k in stats if k[0] == "class+intent") if x), key=lambda x: -x["threads"])
    senders = sorted((x for x in (rate(k) for k in stats if k[0] == "sender") if x), key=lambda x: -x["threads"])
    result = {
        "found": bool(history),
        "asOf": day.isoformat(),
        "history": len(history),
        "answered": sum(1 for _r, a, _d in history if a),
        "byPartyClass": [c for c in classes if c],
        "byPartyClassAndIntent": pairs[:30],
        "bySender": senders[:30],
        "open": open_rows,
        "likelyNeedsResponse": sum(1 for o in open_rows if o["likelyNeedsResponse"]),
        "pastUsualTime": sum(1 for o in open_rows if o["likelyNeedsResponse"] and o["pastUsualTime"]),
        "caveats": [
            "A reply is a message sent from this mailbox after an inbound one; an answer by phone, in person, from another "
            "mailbox, or through PayHOA is not seen, so the rates understate what was answered.",
            "The rate says what the association has done with threads like this, not what it must do.",
            f"History is the threads that came in more than {settle_days} days ago; a level needs {min_threads} threads to count.",
        ],
    }
    out = Path(data_dir) / "reports" / REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def reply_lines(result: dict[str, Any], *, limit: int = 30) -> list[str]:
    out = [f"History: {result['history']} threads that came in, {result['answered']} answered from this mailbox", "",
           "Reply rate by party"]
    for c in result["byPartyClass"]:
        days = f", median {c['medianDays']} days" if c["medianDays"] is not None else ""
        out.append(f"  {c['key']}: {c['replyRate']:.0%} of {c['threads']}{days}")
    out.append("")
    out.append("By party and what it asks")
    for c in result["byPartyClassAndIntent"][:14]:
        days = f", median {c['medianDays']} days" if c["medianDays"] is not None else ""
        out.append(f"  {c['key']}: {c['replyRate']:.0%} of {c['threads']}{days}")
    out.append("")
    out.append(f"Open threads likely needing a response: {result['likelyNeedsResponse']} ({result['pastUsualTime']} past the usual time)")
    shown = 0
    for o in result["open"]:
        if not o["likelyNeedsResponse"]:
            continue
        flag = "PAST USUAL" if o["pastUsualTime"] else "          "
        before = " (replied before)" if o["repliedBefore"] else ""
        out.append(f"  {flag} {o['ageDays']:>3}d {o['who'][:32]:32} {o['subject'][:58]}{before}  [{o['basis']['key'][:28]} {o['basis']['replyRate']:.0%}]")
        shown += 1
        if shown >= limit:
            break
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["reply_needed", "reply_lines", "party_class"]
