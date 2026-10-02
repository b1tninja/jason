"""What each email asks of the association, and where the answer is likely written.

A first pass over the threads (``jason gmail --sync``), from their subjects:

- **intent** (``Mystique.intent_rules()``): a complaint, a maintenance request, a request for information or records, a
  billing matter, a question, or the association's own enforcement notice. A subject can carry several; one that names
  none takes "maintenance request" from a maintenance, landscaping, or pests topic, and is otherwise unclear.
- **topic** (``Mystique.topic_rules()``): parking, bins, neighbors, insurance, and so on.
- **where the answer is** (``Mystique.topic_sources()``): for each topic, the governing documents' passages that match
  its query and the subject's words (BM25 over the extracts, the same search as ``passage_search``); the library's
  documents of the kinds that speak to it; and the PayHOA violations that are its precedents, with the notice text
  each carried (the restriction it cited, and the hearing language), which is what a courtesy notice or a hearing
  notice for a new complaint would follow.

``case_file`` gathers one matter across the stores by its words (a name, an address, a case number): the threads, the
PayHOA violations and requests, the letters, the Drive files, and the library's documents, in date order.

It reads disk only and answers nothing: a passage is to read, not a ruling, and a precedent is a pattern, not a decision.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from jason.community.topics import Intent, Topic, intents_of

REPORT = "intents.json"
_MAINTENANCE_TOPICS = {Topic.MAINTENANCE.value, Topic.LANDSCAPING.value, Topic.PESTS.value}
_STOP = {"with", "from", "that", "this", "have", "your", "about", "question", "questions", "subject", "please", "thanks", "hello",
         "mystique", "community", "association", "regarding", "follow", "update", "request"}


def _violations(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / "payhoa.db"
    if not path.is_file():
        return []
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute("SELECT id, title, status, reported_at, raw_json FROM violations").fetchall()
    finally:
        conn.close()
    found = []
    for vid, title, status, reported, raw in rows:
        data = json.loads(raw or "{}")
        found.append({"id": int(vid), "title": title, "status": status, "reported": str(reported or "")[:10],
                      "unit": ((data.get("unit") or {}).get("title") or "").upper(),
                      "message": str(data.get("message") or "")[:300], "cites": str(data.get("header") or "")[:500],
                      "hearingLanguage": str(data.get("footer") or "")[:300], "resolution": str(data.get("resolutionTime") or "")[:10]})
    return sorted(found, key=lambda v: v["reported"], reverse=True)


def _library(data_dir: Path) -> list[dict[str, Any]]:
    try:
        from jason.tasks.library import load

        return [dict(r) for r in load(Path(data_dir))]
    except Exception:
        return []


def _passages(query: str, data_dir: Path, k: int = 2) -> list[dict[str, Any]]:
    from jason.community.passages import search

    root = Path(data_dir)
    docs = root / "artifacts" / "site-docs"
    folders = [docs / "governing_documents", docs / "governing_documents_Annexations", docs / "governing_documents_Policies",
               docs / "governing_documents_Resolutions", root / "governing"]
    try:
        hits = search(query, *[f for f in folders if f.is_dir()], k=k)
    except Exception:
        return []
    return [{"file": h.passage.title, "passage": h.passage.index, "score": round(h.score, 1), "text": h.passage.text[:420]} for h in hits]


def answer_sources(topic: str, subject: str, data_dir: Path, community: Any, *, cache: dict | None = None,
                   violations: list | None = None, library: list | None = None) -> dict[str, Any]:
    """The passages, library documents, and precedent violations for one topic, shaped by the subject's words."""
    source = next((s for s in community.topic_sources() if s.topic.value == topic), None)
    if source is None:
        return {}
    words = " ".join(w for w in re.findall(r"[a-z]{4,}", subject.lower()) if w not in _STOP)
    key = (topic, words)
    if cache is not None and key in cache:
        return cache[key]
    found: dict[str, Any] = {"passages": _passages(f"{source.query} {words}", data_dir)}
    lib = library if library is not None else _library(data_dir)
    # A document of a core governing kind (declaration, rules) always speaks to its topic; any other must share a word
    # with the topic's query or the subject ("ALPR Policy" for cameras, not the collection policy). Each name once.
    core = {"declaration", "operating_rules", "bylaws"}
    topic_words = set(re.findall(r"[a-z]{4,}", source.query.lower())) | set(words.split())
    seen: set[str] = set()
    docs = []
    for r in lib:
        name = str(r.get("name") or "")
        if r.get("kind") not in source.kinds or r.get("confidential") or name.casefold() in seen:
            continue
        overlap = len(topic_words & set(re.findall(r"[a-z]{4,}", name.lower())))
        if r.get("kind") not in core and not overlap:
            continue
        seen.add(name.casefold())
        docs.append((source.kinds.index(r["kind"]), -overlap, name, r))
    docs.sort(key=lambda d: d[:3])
    found["documents"] = [{"kind": r["kind"], "name": r["name"], "path": r["path"], "period": r.get("period")} for *_k, r in docs[:4]]
    if source.violation_words:
        pool = violations if violations is not None else _violations(data_dir)
        found["precedents"] = [v for v in pool if any(w in v["title"].lower() for w in source.violation_words)][:4]
    if cache is not None:
        cache[key] = found
    return found


def email_intents(data_dir: Path, community: Any, *, days: int = 365, today: date | None = None, with_sources: bool = True) -> dict[str, Any]:
    from jason.tasks.party import _unit_of
    from jason.tasks.threads import threads

    day = today or date.today()
    since = (day - timedelta(days=days)).isoformat()
    rules = tuple(community.intent_rules())
    rows = [r for r in threads(data_dir, community)["rows"] if r["status"] not in ("notice", "internal") and r["last"] >= since]
    violations = _violations(data_dir)
    library = _library(data_dir)
    cache: dict = {}
    out = []
    counts: dict[str, int] = {}
    for r in rows:
        intents = [i.value for i in intents_of(r["subject"], rules)]
        if not intents and set(r.get("topics") or []) & _MAINTENANCE_TOPICS:
            intents = [Intent.MAINTENANCE.value]
        for i in intents or ["unclear"]:
            counts[i] = counts.get(i, 0) + 1
        entry = {"threadId": r["threadId"], "first": r["first"], "last": r["last"], "status": r["status"], "subject": r["subject"][:100],
                 "who": r["sender"] or ", ".join(r["parties"][:2]), "units": _unit_of(r["parties"]), "intents": intents or ["unclear"],
                 "topics": r.get("topics") or [], "link": r["link"]}
        if with_sources and set(intents) & {Intent.COMPLAINT.value, Intent.QUESTION.value, Intent.INFORMATION.value}:
            entry["sources"] = {t: answer_sources(t, r["subject"], data_dir, community, cache=cache, violations=violations, library=library)
                                for t in entry["topics"][:2]}
        out.append(entry)
    result = {"found": bool(out), "asOf": day.isoformat(), "days": days, "threads": len(out), "byIntent": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
              "rows": out, "violations": violations,
              "caveats": ["Intent and topic are read from the subject alone; the message may ask something else.",
                          "A passage is text to read beside the question, ranked by word overlap; it is not a ruling.",
                          "A precedent violation shows how the association handled that conduct before, and the restriction it cited; "
                          "a new complaint still needs its own facts, notice, and hearing."]}
    path = Path(data_dir) / "reports" / REPORT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result


def case_file(terms: list[str], data_dir: Path, community: Any) -> dict[str, Any]:
    """One matter across the stores: every thread, violation, request, letter, Drive file, and library document whose subject,
    title, name, path, or unit carries one of ``terms`` (a name, an address, a case or claim number), in date order."""
    from jason.tasks.mail import load_items
    from jason.tasks.request_links import load_requests
    from jason.tasks.threads import threads

    words = [t.lower() for t in terms if t.strip()]

    def hit(*values: Any) -> bool:
        text = " ".join(str(v or "") for v in values).lower()
        return any(w in text for w in words)

    events: list[dict[str, Any]] = []
    for r in threads(data_dir, community)["rows"]:
        if hit(r["subject"], " ".join(r["parties"]), " ".join(r.get("attachments") or [])):
            events.append({"date": r["first"], "until": r["last"], "what": "email thread", "title": r["subject"][:100],
                           "who": r["sender"] or ", ".join(r["parties"][:3]), "status": r["status"], "ref": r["link"]})
    for v in _violations(data_dir):
        if hit(v["title"], v["unit"], v["message"]):
            events.append({"date": v["reported"], "what": "PayHOA violation", "title": v["title"], "who": v["unit"], "status": v["status"],
                           "ref": f"violation {v['id']}", "detail": v["message"], "cites": v["cites"][:300],
                           "hearing": v["resolution"]})
    for q in load_requests(data_dir, community):
        if hit(q["title"], q["message"], q["unit"]):
            events.append({"date": str(q["created"])[:10], "what": "PayHOA request", "title": q["title"], "who": q["unit"], "status": q["status"],
                           "ref": f"request {q['id']}"})
    for m in load_items(data_dir).values():
        if hit(m.get("from"), m.get("sender"), " ".join((m.get("facts") or {}).get("addresses") or [])):
            events.append({"date": (m.get("received") or "")[:10], "what": "letter", "title": m.get("kind"), "who": m.get("from"),
                           "status": m.get("urgency"), "ref": f"mail {m['mailId']}"})
    drive = Path(data_dir) / "drive" / "holdings.json"
    if drive.is_file():
        for f in json.loads(drive.read_text(encoding="utf-8")).get("rows", []):
            if hit(f["drivePath"]):
                events.append({"date": f["modified"], "what": "Drive file", "title": f["name"], "who": f["drivePath"].rsplit("/", 1)[0],
                               "status": f["kind"] or "unclassified", "ref": f["id"]})
    for d in _library(data_dir):
        if hit(d.get("path"), d.get("name")):
            events.append({"date": str(d.get("period") or ""), "what": "PayHOA library", "title": d.get("name"), "who": d.get("path"),
                           "status": d.get("kind"), "ref": d.get("id")})
    events.sort(key=lambda e: e["date"] or "")
    counts: dict[str, int] = {}
    for e in events:
        counts[e["what"]] = counts.get(e["what"], 0) + 1
    return {"found": bool(events), "terms": terms, "counts": counts, "events": events,
            "caveats": ["A match is by words in subjects, titles, names, and paths; a document about the matter that never names it "
                        "is not found, and one that names a word for another reason is.",
                        "Email is read by its headers; a thread's content is in Gmail."]}


def intent_lines(result: dict[str, Any], *, intent: str = "", limit: int = 30) -> list[str]:
    out = [f"{result['threads']} threads in {result['days']} days: " + ", ".join(f"{k} {n}" for k, n in result["byIntent"].items()), ""]
    shown = 0
    for r in result["rows"]:
        if intent and intent not in r["intents"]:
            continue
        out.append(f"{r['last']} [{', '.join(r['intents'])}] {r['who'][:34]}: {r['subject'][:70]}  {{{', '.join(r['topics'][:2])}}}")
        for topic, src in (r.get("sources") or {}).items():
            for p in src.get("passages", [])[:1]:
                out.append(f"    {topic}: {p['file']} #{p['passage']}: {p['text'][:110]}...")
            for d in src.get("documents", [])[:2]:
                out.append(f"    {topic}: {d['kind']} {d['name'][:60]}")
            for v in src.get("precedents", [])[:2]:
                out.append(f"    precedent: {v['reported']} {v['title']} ({v['unit'] or '-'}, {v['status']})")
        shown += 1
        if shown >= limit:
            break
    out.append("")
    out.extend(f"* {c}" for c in result["caveats"])
    return out


__all__ = ["email_intents", "answer_sources", "case_file", "intent_lines"]
