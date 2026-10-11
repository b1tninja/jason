"""The rules-and-documents screens' reads (docs/console/design-brief-rules-and-documents.md): five read-only loaders over
the same functions the jason-mcp tools run (``jason.api``). Disk and the profile only; nothing reaches the county, Drive,
PayHOA, or lawlibrary, and nothing is written.

- ``cite(args)``, ``GET /api/cite?expression=&as_of=&citing=&citing_day=&text=0``
  (``cite_document``): one provision named the way a person or a document writes it ("Declaration 6.2(a)", "CIV 4920(a)",
  "minutes 2099-01-01"), recited: its stored words whole, the citation, the version in force (``inForce``), the
  instruments that changed it (``history``, one not in force flagged, never merged). A span, an article, or siblings is an
  outline, never joined words. A miss is an answer with its ``reason``.
- ``living(args)``, ``GET /api/living?key=&section=&as_of=`` (``living_document``): with no ``key`` the documents kept as
  amended; with one, the instruments applied and **not in effect** (apart, never merged), the findings, and, with
  ``section``, that section's words, who set them, and its history.
- ``conflicts(args)``, ``GET /api/conflicts?area=&resolved=1&leads=1&document=&since=`` (``document_conflicts``): the
  ``Conflict`` rows, each with what still governs, the part that yields, and the board item. jason notes a conflict and
  never resolves one; a lead is to read beside the statute, not a conflict.
- ``law_in_force(args)``, ``GET /api/law-in-force?citation=&as_of=`` (``law_in_force``): the version of a statute's section
  in force on a day, where the disk shows it; where it does not, nothing is picked and ``reason`` says what would bring
  the words.
- ``write(key, body)``, ``POST /api/write/check-quotes/run`` with ``{"text": ..., "as_of": ...}`` (``verify_quotes``): each
  quotation and citation in the pasted text checked against the stored words. The text travels in the body and never in a
  web address (a URL is logged and kept in a browser's history), so ``GET /api/check-quotes`` answers 400 to a ``text`` and
  says to POST. It is a POST only for that reason: it reads disk and writes nothing, under data/ or elsewhere, and the
  text is not kept (``served.jsonl`` logs files served, never a body). This is the convention of the other read-only POSTs
  (``drive``, ``library``): an ``EXTRA_WRITERS`` entry whose writer gates itself. The results only: the check names no
  confidential file and shows none of its words (``include_confidential`` is never passed, and ``sources`` is not taken).
  A quotation whose words exist only in a confidential record has the verdict ``withheld``, with no name, path, section,
  or words, and never ``found``. ``found`` says the words are the stored words, never that they were read rightly or were
  in force on a day. The text is at most 20,000 characters.

**Words, then a reading.** Every answer carries the stored words as the tool found them, byte for byte; a loader here
paraphrases nothing and adds no reading. ``caveats`` says so, and the consolidated text is not an official restatement.

**Who.** The signed-in roster for ``cite``, ``living``, ``conflicts``, and ``law-in-force`` (the association's documents and
the law: P0, ``jason.web.gates``); the offices that open P2 for ``check-quotes``, since the passage index it checks against
also holds the insurance pages (P2 by ``jason.web.access.PATH_RULES``) and a verdict shows the stored passage. The owner view
answers none of them (``OWNER_SOURCES`` does not list them). ``cite`` never opens the restricted books (executive-session
minutes, the membership list, election materials: CIV 5215, 5200(c)); a record that is confidential is named without its
place on disk.

**The shelf.** A missing shelf, base text, or index is a miss with its reason (``found`` false, ``note``), never a crash: a
statute the shelf lacks stays a miss (the read-through to lawlibrary is held off for the call,
``jason.tasks.statute_fetch.disabled``, so a read writes nothing).
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

Args = dict[str, str]

CAVEATS = (
    "The words are jason's stored words, whole. Any reading of them is a reading, labeled with whose it is, and is not shown here.",
    "jason's consolidated text is not an official restatement: the recorded instruments, the adopted rules, and the Legislature's "
    "text control.",
)
CONFLICT_CAVEAT = "jason notes a conflict; only the board, counsel, or an amendment resolves one."
QUOTE_CAVEATS = (
    "This checks words, not meaning: found does not say the answer reads the words rightly, that they answer the question, or "
    "that they were in force on a given day.",
    "A paraphrase, a figure, or a date outside quotation marks is not checked.",
)
MAX_EXPRESSION = 300
MAX_QUOTE_TEXT = 20_000
HELD = "held"
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _root() -> Path:
    from jason.mcp.county import _data_dir

    return Path(_data_dir(None))


def _flag(args: Args, key: str, default: bool = False) -> bool:
    raw = str(args.get(key, "") or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _day(args: Args, key: str) -> str:
    """A day as YYYY-MM-DD, or empty. A malformed or impossible day is a 400, not a guess."""
    raw = str(args.get(key, "") or "").strip()
    if not raw:
        return ""
    if not _DAY.match(raw):
        raise ValueError(f"{key} is a day as YYYY-MM-DD")
    try:
        date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{key} is a day as YYYY-MM-DD") from exc
    return raw


def _read_only():
    """The disk only for the call: the shelf's read-through to lawlibrary writes a page to data/authorities."""
    from jason.tasks.statute_fetch import disabled

    return disabled()


def _miss(note: str, **rest: Any) -> dict[str, Any]:
    return {"found": False, "note": note, **rest}


def _hold_confidential(value: Any) -> Any:
    """A confidential record is named without where it sits on disk or in Drive (its kind and its flag stay)."""
    if isinstance(value, list):
        return [_hold_confidential(v) for v in value]
    if not isinstance(value, dict):
        return value
    held = bool(value.get("confidential"))
    return {k: (HELD if held and k in ("where", "location", "path", "file", "library") and v else _hold_confidential(v))
            for k, v in value.items()}


def _with_caveats(out: dict[str, Any], *extra: str) -> dict[str, Any]:
    return {**out, "caveats": [*CAVEATS, *extra]}


def cite(args: Args) -> dict[str, Any]:
    """GET /api/cite: one provision recited from the shelf (``jason.mcp.governance.cite_document``), restricted books
    refused, the words verbatim."""
    from jason.mcp.governance import cite_document

    expression = str(args.get("expression", args.get("q", "")) or "").strip()
    if len(expression) > MAX_EXPRESSION:
        raise ValueError(f"expression is a citation of at most {MAX_EXPRESSION} characters")
    as_of, citing_day = _day(args, "as_of"), _day(args, "citing_day")
    with _read_only():
        out = cite_document(expression, as_of=as_of, text=_flag(args, "text", True), citing=str(args.get("citing", "") or "").strip(),
                            citing_day=citing_day, data_dir=_root())
    out = _hold_confidential(out)
    out.setdefault("found", False)
    if as_of:
        out.setdefault("asOf", as_of)
    return _with_caveats(out)


def living(args: Args) -> dict[str, Any]:
    """GET /api/living: the documents kept as amended, or one as amended with its applied and not-in-effect instruments."""
    from jason.mcp.governance import living_document

    key = str(args.get("key", "") or "").strip()
    section = str(args.get("section", "") or "").strip()
    as_of = _day(args, "as_of")
    if section and not key:
        raise ValueError("section needs key: name the document")
    try:
        with _read_only():
            out = living_document(key, section=section, as_of=as_of, data_dir=_root())
    except (OSError, KeyError) as exc:
        return _with_caveats(_miss(f"{key or 'the living documents'} cannot be read from disk: {exc}"))
    if "error" in out:
        rest = {k: v for k, v in out.items() if k != "error"}
        return _with_caveats(_miss(str(out["error"]), **rest))
    out = {"found": True, **out}
    if as_of:
        out["asOf"] = as_of
    return _with_caveats(out)


def conflicts(args: Args) -> dict[str, Any]:
    """GET /api/conflicts: the ``Conflict`` rows, and with ``leads=1`` the candidates; noted, never resolved."""
    from jason.mcp.governance import document_conflicts

    since = _day(args, "since")
    with _read_only():
        out = document_conflicts(area=str(args.get("area", "") or "").strip(), include_resolved=_flag(args, "resolved"),
                                 leads=_flag(args, "leads"), document=str(args.get("document", "") or "").strip(), since=since,
                                 data_dir=_root())
    if "error" in out:
        raise ValueError(str(out["error"]))
    return {"found": bool(out.get("conflicts")), **out, "caveats": [CONFLICT_CAVEAT, *CAVEATS[1:]]}


def law_in_force(args: Args) -> dict[str, Any]:
    """GET /api/law-in-force: a statute section as it stood on a day, where the disk shows it; otherwise a miss that says
    what would bring the words."""
    from jason.mcp.governance import law_in_force as tool

    citation = str(args.get("citation", args.get("q", "")) or "").strip()
    if len(citation) > MAX_EXPRESSION:
        raise ValueError(f"citation is a code and a section of at most {MAX_EXPRESSION} characters")
    as_of = _day(args, "as_of")
    with _read_only():
        out = tool(citation, as_of=as_of, data_dir=_root())
    if "error" in out:
        raise ValueError(str(out["error"]))
    return _with_caveats(out)


POST_ONLY = ("Pasted text is not put in a web address: POST /api/write/check-quotes/run with {\"text\": ..., \"as_of\": ...}.")
OWNER_REFUSED = "The quote check is the board's."
WITHHELD = "withheld"
WITHHELD_NOTE = "the words exist only in a restricted record; nothing is shown"
ACTS = ("run",)


def _hold_back(report: dict[str, Any]) -> dict[str, Any]:
    """Nothing of a confidential file reaches the web: a place in one is dropped (no name, path, section, or words), the warning
    about it with it, and a quotation whose words are found only there is ``withheld``, not ``found``."""
    quotes = []
    counts = dict(report.get("counts") or {})
    for q in report.get("quotes") or []:
        places = q.get("places") or []
        held = [p for p in places if p.get("withheld") or p.get("confidential")]
        if not held:
            quotes.append(q)
            continue
        kept = [p for p in places if p not in held]
        warnings = [w for w in (q.get("warnings") or []) if "confidential" not in w.lower()]
        out = {k: v for k, v in q.items() if k not in ("places", "warnings")}
        if kept:
            out["places"] = kept
        elif q.get("verdict") == "found":
            out["verdict"] = WITHHELD
            out["note"] = WITHHELD_NOTE
            out.pop("match", None)
            counts["found"] = max(0, int(counts.get("found", 0)) - 1)
            counts[WITHHELD] = int(counts.get(WITHHELD, 0)) + 1
        if warnings:
            out["warnings"] = warnings
        quotes.append(out)
    counts["warnings"] = sum(1 for q in quotes if q.get("warnings"))
    return {**report, "quotes": quotes, "counts": counts}


def _check(text: str, as_of: str) -> dict[str, Any]:
    from jason.mcp.county import verify_quotes

    if len(text) > MAX_QUOTE_TEXT:
        raise ValueError(f"text is at most {MAX_QUOTE_TEXT} characters; check it in parts")
    if not text.strip():
        return {"available": True, "checked": False, "found": False, "note": "paste the text whose quotations and citations are to be checked",
                "post": "/api/write/check-quotes/run", "caveats": list(QUOTE_CAVEATS)}
    with _read_only():
        out = verify_quotes(text, "", False, as_of, data_dir=_root())
    if not out.get("available", True):
        return {"checked": False, "found": False, **out, "caveats": list(QUOTE_CAVEATS)}
    if "error" in out:
        raise ValueError(str(out["error"]))
    out = _hold_back(out)
    return {"checked": True, **out, "caveats": [*QUOTE_CAVEATS, *[c for c in (out.get("caveats") or []) if c not in QUOTE_CAVEATS]]}


def check_quotes(args: Args) -> dict[str, Any]:
    """GET /api/check-quotes: how to ask. A ``text`` is refused (400): it is POSTed, so it never sits in a web address."""
    if str(args.get("text", args.get("answer", "")) or "").strip():
        raise ValueError(POST_ONLY)
    _day(args, "as_of")
    return _check("", "")


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/check-quotes/run`` ``{text, as_of}``: the check. Reads disk only and writes nothing. The board's: the
    owner view is refused, and where console sign-in is set up the offices that open P2 are required (``jason.web.gates``)."""
    from flask import abort, has_request_context, request

    if key not in ACTS:
        raise KeyError(key)
    body = body if isinstance(body, dict) else {}
    if has_request_context():
        from jason.web import access, gates

        if request.args.get("view") == "owner" or str(body.get("view") or "") == "owner":
            abort(access.refusal(403, OWNER_REFUSED))
        gates.check(gates.P2)
    return _check(str(body.get("text", body.get("answer", "")) or ""), _day({k: str(v or "") for k, v in body.items()}, "as_of"))
