"""PayHOA requests beside the email about them, and drafts for the emailed requests PayHOA does not have.

Every stored request (``data/payhoa.db``) is read with its title, message, comments, and dates, and given its topics.
Two kinds of email are then joined to it:

- **PayHOA's own notices** ("Maintenance Request Submission", "New Comment", "Request Status Change"): the request
  created, commented on, or updated within 15 minutes of the notice (the form's name in the subject decides a tie);
- **an owner's thread** about the same unit: a thread active from 30 days before the request to 45 days after its last
  change, scored by shared topics (2), shared subject words (1 each, up to 3), and being within three days of the
  request (1); a score of 2 or more links them, and each link keeps its reasons.

An owner's thread that raises a request topic (maintenance, landscaping, pests, architecture, parking, bins, neighbors,
security, utilities) and links to no request is an emailed request PayHOA does not have. For each, a **draft** names the
form (``Mystique.request_forms()``), the unit, a title from the subject, and a message pointing at the thread. The email
is read by its headers, so the message says what the thread is about, not what the owner wrote; a person completes it.

Nothing is created: ``create`` submits one draft only when a person names it, and never approves, denies, or assigns.
"""

from __future__ import annotations

import html
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jason.community.request_forms import form_for
from jason.community.topics import Topic, topics_of

REPORT = "request-links.json"
NOTICE = re.compile(r"(?i)(maintenance|general|architectural)?\s*request\s*(submission|status change)|new comment")
_STOP = {"with", "from", "that", "this", "have", "your", "about", "request", "requests", "question", "questions", "subject",
         "please", "thank", "thanks", "hello", "mystique", "community", "association", "regarding", "follow", "update"}


def _at(value: str) -> datetime | None:
    """A timestamp as UTC; PayHOA's stored ones carry no zone and are UTC (its API's "Z")."""
    try:
        found = datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
    except ValueError:
        return None
    return found.replace(tzinfo=timezone.utc) if found and found.tzinfo is None else found


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in _STOP}


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def load_requests(data_dir: Path, community: Any) -> list[dict[str, Any]]:
    path = Path(data_dir) / "payhoa.db"
    if not path.is_file():
        return []
    rules = tuple(community.topic_rules())
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        units = {int(i): label.upper() for i, label in conn.execute("SELECT id, label FROM units")}
        rows = conn.execute("SELECT id, form_name, unit_id, status, created_at, raw_json FROM requests").fetchall()
    finally:
        conn.close()
    found = []
    for rid, form, unit_id, status, created, raw in rows:
        data = json.loads(raw or "{}")
        answers = {str((a.get("question") or {}).get("label") or ""): _text(a.get("answer")) for a in data.get("answers") or []}
        title, message = answers.get("Title", ""), answers.get("Message", "")
        comments = [{"at": c.get("createdAt"), "admin": bool(c.get("isAdmin"))} for c in data.get("comments") or [] if not c.get("deletedAt")]
        found.append({"id": int(rid), "form": form, "unitId": int(unit_id or 0), "unit": units.get(int(unit_id or 0), ""), "status": status,
                      "created": created or data.get("createdAt"), "updated": data.get("updatedAt"), "completed": data.get("completionDate"),
                      "title": title, "message": message[:400], "comments": comments,
                      "topics": [t.value for t in topics_of(f"{title} {message} {form}", rules)]})
    return found


def _messages_by_thread(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    from jason.tasks.gmail import CORRESPONDENCE, _load

    by: dict[str, list[dict[str, Any]]] = {}
    for m in _load(data_dir, CORRESPONDENCE).get("messages") or []:
        by.setdefault(m["threadId"], []).append(m)
    return by


def _notice_links(requests: list[dict[str, Any]], by_thread: dict[str, list[dict[str, Any]]]) -> dict[int, list[dict[str, Any]]]:
    """PayHOA's notices joined to the request created, commented on, or updated within 15 minutes of each."""
    window = timedelta(minutes=15)
    links: dict[int, list[dict[str, Any]]] = {}
    for thread_id, messages in by_thread.items():
        for m in messages:
            if "payhoa.com" not in (m.get("domains") or []):
                continue
            hit = NOTICE.search(m.get("subject") or "")
            at = _at(m["at"])
            if not hit or at is None:
                continue
            form_word = (hit.group(1) or "").lower()
            kind = "comment" if "comment" in hit.group(0).lower() else "status" if (hit.group(2) or "").lower() == "status change" else "submission"
            candidates = []
            for r in requests:
                if form_word and form_word not in r["form"].lower():
                    continue
                times = ([_at(r["created"])] if kind == "submission" else
                         [_at(c["at"]) for c in r["comments"]] if kind == "comment" else [_at(r["updated"]), _at(r["completed"])])
                gaps = [abs(at - t) for t in times if t is not None]
                if gaps and min(gaps) <= window:
                    candidates.append((min(gaps), r["id"]))
            if candidates:
                _gap, rid = min(candidates)
                links.setdefault(rid, []).append({"threadId": thread_id, "at": m["at"][:19], "subject": (m.get("subject") or "")[:90],
                                                  "how": f"PayHOA {kind} notice"})
    return links


def _score(thread: dict[str, Any], request: dict[str, Any]) -> tuple[int, list[str]]:
    reasons, score = [], 0
    shared = set(thread.get("topics") or []) & set(request["topics"])
    if shared:
        score += 2
        reasons.append("topic " + ", ".join(sorted(shared)))
    words = _words(thread["subject"]) & _words(f"{request['title']} {request['message']}")
    if words:
        score += min(3, len(words))
        reasons.append("words " + ", ".join(sorted(words)[:4]))
    created = _at(request["created"])
    first = _at(thread["first"] + "T00:00:00+00:00")
    if created and first and abs((created - first).days) <= 3:
        score += 1
        reasons.append("within three days")
    return score, reasons


def request_links(data_dir: Path, community: Any, *, today: datetime | None = None) -> dict[str, Any]:
    from jason.tasks.party import _unit_of
    from jason.tasks.threads import threads

    now = today or datetime.now(timezone.utc)
    requests = load_requests(data_dir, community)
    by_thread = _messages_by_thread(data_dir)
    notices = _notice_links(requests, by_thread)
    rows = threads(data_dir, community)["rows"]
    owner_threads = [r for r in rows if r["status"] not in ("notice", "internal") and _unit_of(r["parties"])]
    linked_threads: set[str] = set()
    owner_links: dict[int, list[dict[str, Any]]] = {}
    for r in requests:
        if not r["unit"]:
            continue
        created = _at(r["created"])
        end = max([t for t in (_at(r["updated"]), _at(r["completed"]), created) if t] or [now])
        if created is None:
            continue
        lo, hi = (created - timedelta(days=30)).date().isoformat(), (end + timedelta(days=45)).date().isoformat()
        for t in owner_threads:
            if r["unit"] not in _unit_of(t["parties"]) or t["last"] < lo or t["first"] > hi:
                continue
            score, reasons = _score(t, r)
            if score >= 2:
                owner_links.setdefault(r["id"], []).append({"threadId": t["threadId"], "first": t["first"], "last": t["last"],
                                                            "subject": t["subject"][:90], "status": t["status"], "score": score,
                                                            "how": "; ".join(reasons), "link": t["link"]})
                linked_threads.add(t["threadId"])
    out_requests = []
    for r in requests:
        own = sorted(owner_links.get(r["id"], []), key=lambda l: -l["score"])
        out_requests.append({**{k: r[k] for k in ("id", "form", "unit", "status", "created", "title", "topics")},
                             "notices": notices.get(r["id"], []), "ownerThreads": own[:6]})
    out_requests.sort(key=lambda r: r["created"] or "", reverse=True)
    wanted = {t.value for t in community.request_topics()}
    forms = tuple(community.request_forms())
    unit_ids = {r["unit"]: r["unitId"] for r in requests if r["unit"]}
    unit_ids.update(_unit_ids(data_dir))
    drafts = []
    for t in owner_threads:
        # Only a thread between the association and owners: a claim with an adjuster or a vendor's pitch that copies an
        # owner is not the owner's request.
        if t["threadId"] in linked_threads or t["domains"]:
            continue
        raised = [x for x in t.get("topics") or [] if x in wanted]
        if not raised:
            continue
        form = form_for([Topic(x) for x in raised], forms)
        unit = _unit_of(t["parties"])[0]
        title = re.sub(r"(?i)^(?:(?:re|fwd?|fw|subject)\s*:\s*)+", "", t["subject"]).strip() or "Request by email"
        drafts.append({"threadId": t["threadId"], "unit": unit, "unitId": unit_ids.get(unit), "first": t["first"], "last": t["last"],
                       "status": t["status"], "topics": raised, "form": form.name if form else None, "formId": form.form_id if form else None,
                       "title": title[:120], "link": t["link"],
                       "message": (f"Raised by email by the owner of {unit}, first on {t['first']} ({t['messages']} messages, last {t['last']}): "
                                   f"\"{title}\". Topics: {', '.join(raised)}. Entered from the email thread so it can be tracked here; "
                                   f"the thread is in the association's Gmail.")})
    drafts.sort(key=lambda d: d["last"], reverse=True)
    result = {
        "found": bool(requests),
        "requests": len(requests),
        "withNotice": sum(1 for r in out_requests if r["notices"]),
        "withOwnerThread": sum(1 for r in out_requests if r["ownerThreads"]),
        "emailedWithoutRequest": len(drafts),
        "rows": out_requests,
        "drafts": drafts,
        "caveats": [
            "A notice is joined by time (15 minutes); an owner's thread by unit, dates, topics, and subject words, with its reasons.",
            "A draft is built from email headers: its message says what the thread is about; a person reads the thread and "
            "completes it before it is entered.",
            "Jason enters a request only when a person names the draft, and never approves, denies, or assigns one.",
        ],
    }
    out = Path(data_dir) / "reports" / REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def with_refs(rows: list[dict[str, Any]], data_dir: Path) -> list[dict[str, Any]]:
    """Each request row with ``doc``, its submission as a document reference (``payhoa:submission:<id>``, named by its
    title), beside the old fields; the console's Request column shows it as a ``Doc`` chip. A light resolve of the
    catalog row and the kept read, so call it on the rows shown, not every request."""
    from jason.approvals.docref import submission_ref

    out = []
    for r in rows:
        try:
            doc = submission_ref(r["id"], name=str(r.get("title") or "") or None, data_dir=Path(data_dir))
        except (TypeError, ValueError):
            doc = None
        out.append({**r, "doc": doc} if doc else dict(r))
    return out


def _unit_ids(data_dir: Path) -> dict[str, int]:
    path = Path(data_dir) / "payhoa.db"
    if not path.is_file():
        return {}
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return {label.upper(): int(i) for i, label in conn.execute("SELECT id, label FROM units")}
    finally:
        conn.close()


def create(client: Any, org_id: int, community: Any, draft: dict[str, Any], *, message: str = "", notify_owner: bool = False) -> list[Any]:
    """Enter one draft as a PayHOA request (title, and ``message`` or the draft's). Returns PayHOA's new submission ids."""
    form = next((f for f in community.request_forms() if f.form_id == draft["formId"]), None)
    if form is None or not draft.get("unitId"):
        raise ValueError("the draft has no form or unit")
    answers = [{"formQuestionId": form.title_question, "answer": draft["title"]},
               {"formQuestionId": form.message_question, "answer": message or draft["message"]}]
    return client.create_form_submission(org_id, form.form_id, [int(draft["unitId"])], answers, send_notification_to_owner=notify_owner)


def link_lines(result: dict[str, Any], *, limit: int = 25) -> list[str]:
    out = [f"{result['requests']} PayHOA requests: {result['withNotice']} joined to PayHOA's notices, {result['withOwnerThread']} to an "
           f"owner's thread; {result['emailedWithoutRequest']} emailed requests with no PayHOA request", ""]
    shown = 0
    for r in result["rows"]:
        if not r["ownerThreads"]:
            continue
        out.append(f"#{r['id']} {r['created'][:10]} {r['unit'] or '-'} {r['form']} ({r['status']}): {r['title'][:60]}")
        for t in r["ownerThreads"][:3]:
            out.append(f"    email {t['first']}..{t['last']} [{t['status']}] {t['subject'][:60]} ({t['how']})")
        shown += 1
        if shown >= limit:
            break
    if result["drafts"]:
        out.append("")
        out.append("Emailed requests with no PayHOA request (drafts; enter one with --create THREAD_ID)")
        for d in result["drafts"][:limit]:
            out.append(f"  {d['last']} {d['unit']}: {d['title'][:60]} -> {d['form']} [{', '.join(d['topics'])}] ({d['threadId']})")
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["request_links", "load_requests", "create", "link_lines", "with_refs"]
