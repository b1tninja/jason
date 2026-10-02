"""Cross-checks between what an agenda item linked and what the minutes of that meeting recorded.

``build`` reads what jason already has on disk and calls nothing:

- the agenda items and the documents each linked or named (``data/meetings/agenda-items.json``, `jason agenda-items`);
- the kinds decided for agenda files (``data/meetings/agenda-kinds.json``) and the text of the files fetched for it
  (``data/meetings/agenda-files``), a PayHOA library copy, or a Gmail attachment with the same bytes;
- the minutes readings (``data/documents/readings.json``: each action's words, outcome, and amount in cents), the
  minutes' own items and attachments, and the local model's grounded answers (``questions-minutes.json``);
- the meeting catalog (``data/meetings/catalog.json``: which meetings have minutes, wherever they are held);
- the Drive listing and the PayHOA library, for insurance policies of a new term.

Four checks, per meeting with an agenda:

1. **Amounts.** Each proposal, estimate, contract, or invoice an item linked, beside the decisions the minutes record for
   it. The document's amount is a total line of its own text ("Grand Total", "Amount Due", "Total"); the decision is
   matched to the document by the minutes item that attaches it, the same dollar amount, or the vendor's and the item's
   words. It **matches**, **differs** (both amounts shown), was **decided** with no amount to set beside it, or the
   document was **linked, but no decision is recorded**. An approval with an amount that no linked document matches is
   **approved without a linked document**.
2. **Prior minutes.** The agenda's "Minutes of M/D/YY": whether the link opens those minutes (not the agenda of that
   day), whether minutes of that meeting are held, whether an earlier agenda already listed them, and whether this
   meeting's minutes record the approval. A meeting whose minutes are held but no agenda listed is a lead too.
3. **Insurance renewals.** A renewal the agenda brought, whether the minutes record a decision on it, and whether a
   policy or certificate for the new term is on file afterward (Drive, the PayHOA library, or a policy reading).
4. **Stale items.** An item or document carried on three or more consecutive agendas with no decision in those
   meetings' minutes.

Every result carries its evidence (file names, ids, quotes). Each is a lead for a person, never a finding: a reading can
miss a decision the minutes state, a name can match the wrong item, and minutes not read are not minutes not written.
The result is ``data/meetings/cross-checks.json``.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from jason.community.questions import distinct_topics, grounded

OUT = Path("meetings") / "cross-checks.json"
DOC_KINDS = frozenset({"proposal", "invoice", "contract", "claim_estimate"})
DOC_WORDS = re.compile(r"proposal|estimate|quote|bid\b|contract|invoice|agreement|engagement|renewal", re.I)
NOT_A_DOCUMENT = re.compile(r"\.(mov|mp4|jpe?g|png|heic)$|^[^\w]*$", re.I)
STALE_DAYS = 3                       # consecutive agendas
POLICY_KINDS = ("insurance_policy", "evidence_of_insurance")
POLICY_WINDOW = 150                  # days after the meeting a policy for the new term is looked for, when no term is named
CAVEATS = (
    "Each result is a lead for a person, never a finding of fact.",
    "Minutes not read are not minutes not written; a meeting whose minutes were not read has no decision checks.",
    "A document is matched to a decision by attachment, amount, or shared words; a match can be wrong, and a miss can be "
    "a decision worded differently.",
    "A document's amount is a total line of its own text; a scan without a text layer has no amount here.",
    "Amounts are integer cents.",
)


class AmountOutcome(Enum):
    MATCHES = "matches"
    DIFFERS = "differs"
    DECIDED = "decided, no amounts to compare"
    TABLED = "tabled or denied"
    NO_DECISION = "linked, but no decision recorded"
    WITHOUT_DOC = "approved without a linked document"


class MinutesIssue(Enum):
    LINKS_AGENDA = "the link opens an agenda, not minutes"
    NOT_LINKED = "named, not linked"
    NAMES_NONE = "names no minutes"
    NOT_HELD = "no minutes of that meeting are held"
    RELISTED = "listed again after an earlier agenda"
    NOT_RECORDED = "this meeting's minutes record no approval"
    NOT_READ = "this meeting's minutes were not read"
    NEVER_LISTED = "minutes held, but no agenda listed them for approval"


# --- amounts ----------------------------------------------------------------------------------------------------------

_MONEY = re.compile(r"\$\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{2})?")
# A total line, best first: a grand total, the amount due, a named total (cost, price, premium), a bare total.
_TOTALS = (
    (0, re.compile(r"\bgrand\s+total\b", re.I)),
    (1, re.compile(r"\b(?:amount|balance|total)\s+due\b", re.I)),
    (2, re.compile(r"\btotal\s+(?:estimated\s+)?(?:cost|price|contract\s+price|premium|investment|amount|for\b)", re.I)),
    (3, re.compile(r"\btotal\b(?!\s*#)(?!ing|ed)", re.I)),
)
_NOT_TOTAL = re.compile(r"\bsub\s*-?\s*total|\btotal(?:ing|ed|s)\b|\btotal\s*#|\blosses\s+totaling", re.I)


def cents(text: str) -> list[int]:
    """Every dollar amount written in the text, in cents."""
    out = []
    for whole, frac in _MONEY.findall(text or ""):
        out.append(int(whole.replace(",", "")) * 100 + (int(frac[1:]) if frac else 0))
    return out


def document_totals(text: str) -> list[dict[str, Any]]:
    """The document's total lines with their amounts, best first. A total line's amount is on it or on one of the two
    lines after it (a table prints "TOTAL" above "$9,968.00")."""
    lines = [ln.strip() for ln in (text or "").splitlines()]
    found: list[tuple[int, int, int, str]] = []
    for n, line in enumerate(lines):
        if not line or _NOT_TOTAL.search(line):
            continue
        rank = next((r for r, rx in _TOTALS if rx.search(line)), None)
        if rank is None:
            continue
        amounts = cents(line[next(rx for r, rx in _TOTALS if r == rank).search(line).start():])
        shown = line
        if not amounts:
            for nxt in lines[n + 1:n + 3]:
                if nxt and cents(nxt):
                    amounts, shown = cents(nxt)[:1], f"{line} {nxt}"
                    break
        amounts = [a for a in amounts if a > 0]
        if amounts:
            found.append((rank, -n, amounts[-1], shown[:160]))
    found.sort()
    seen: set[int] = set()
    out = []
    for rank, neg, amount, line in found:
        if amount in seen:
            continue
        seen.add(amount)
        out.append({"amount": amount, "line": line, "rank": rank})
    return out


def dollars(c: int | None) -> str:
    return "" if c is None else f"${c / 100:,.2f}"


# --- decisions in the minutes -----------------------------------------------------------------------------------------

_APPROVED = re.compile(r"\bapprov|\bgranted\b|\bagreed\b|\bauthori[sz]|\bvoted\b|\bpassed\b|\bdecided to (?!table|defer)|\bproceed", re.I)
_TABLED = re.compile(r"\btabled?\b|\bdefer|\bpostpone", re.I)
_DENIED = re.compile(r"\bdenied\b|\brejected\b|\bdecided against\b|\bdeclined\b", re.I)
# Approvals that are not spending on a vendor's document: fines, prizes, dues, the budget, investing reserves, minutes.
NOT_SPENDING = re.compile(r"\bfines?\b|violation|prize|gift card|per month|\bminutes\b|\bbudget of\b|annual budget|"
                          r"\binvest|\bCD\b|delinquen|foreclos|borrow|credit", re.I)


@dataclass
class Decision:
    source: str                      # "minutes action", "minutes item", "model answer"
    text: str
    outcome: str
    amounts: list[int] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)
    reading: str = ""                # the minutes reading's library id

    def as_dict(self) -> dict[str, Any]:
        out = {"source": self.source, "quote": self.text[:300], "outcome": self.outcome, "minutesId": self.reading}
        if self.amounts:
            out["amounts"] = self.amounts
        if self.attachments:
            out["attachments"] = self.attachments
        return out


def _outcome(text: str) -> str:
    if _DENIED.search(text):
        return "denied"
    if _TABLED.search(text):
        return "tabled"
    if _APPROVED.search(text):
        return "approved"
    return ""


def _walk(items: list[dict[str, Any]], parent: str = "") -> list[tuple[str, dict[str, Any]]]:
    out = []
    for it in items or []:
        title = " / ".join(p for p in (parent, it.get("title", "")) if p)
        out.append((title, it))
        out += _walk(it.get("subitems") or [], title)
    return out


def decisions_of(reading: dict[str, Any], answers: dict[str, dict[str, Any]] | None = None) -> list[Decision]:
    """The decisions one minutes reading records: its actions, its items whose notes state an outcome, and the model's
    grounded amounts (a model amount the actions already carry is not repeated)."""
    f = reading.get("fields") or {}
    rid = str(reading.get("id", ""))
    out: list[Decision] = []
    for a in f.get("actions") or []:
        text = str(a.get("text") or "")
        amounts = [int(a["amount"])] if a.get("amount") else cents(text)
        out.append(Decision("minutes action", text, str(a.get("outcome") or _outcome(text)), amounts, [], rid))
    for title, it in _walk(f.get("items") or []):
        notes = str(it.get("notes") or "")
        outcome = _outcome(notes)
        if outcome:
            out.append(Decision("minutes item", f"{title}: {notes}", outcome, cents(notes), list(it.get("attachments") or []), rid))
    known = {c for d in out for c in d.amounts}
    ans = (answers or {}).get("amounts_approved") or {}
    if ans.get("verdict") not in (None, "ungrounded", "gap") and isinstance(ans.get("model"), list):
        for value in ans["model"]:
            amounts = [c for c in cents(str(value)) if c not in known]
            if amounts:
                out.append(Decision("model answer", str(value), "approved", amounts, [], rid))
    return out


def prior_minutes_approved(reading: dict[str, Any], answers: dict[str, dict[str, Any]] | None = None) -> tuple[bool, str]:
    """Whether the minutes record approving earlier minutes, and the words that say so."""
    f = reading.get("fields") or {}
    for a in f.get("actions") or []:
        text = str(a.get("text") or "")
        if re.search(r"minutes", text, re.I) and _APPROVED.search(text):
            return True, text
    for title, it in _walk(f.get("items") or []):
        if re.search(r"minutes", title, re.I) and _APPROVED.search(str(it.get("notes") or "")):
            return True, f"{title}: {it.get('notes')}"
    if f.get("prior_minutes_approved"):
        return True, "the reading's prior_minutes_approved"
    ans = (answers or {}).get("prior_minutes_approved") or {}
    if ans.get("model") is True and ans.get("verdict") != "ungrounded":
        return True, str(ans.get("quote") or "the model's grounded answer")
    return False, ""


# --- matching a document to a decision --------------------------------------------------------------------------------

_SUFFIX = re.compile(r"(?:ations?|ing|ed|es|s)$")
SINGLE_WORD_DF = 3                  # a single shared word matches only when it is this rare among the decisions


def _word(w: str) -> str:
    s = _SUFFIX.sub("", w).rstrip("e")
    return s if len(s) >= 3 else w


# Words that name no matter: the documents' own vocabulary, the minutes' verbs, and the association's street names (a
# unit's address is on many documents).
COMMON = frozenset(_word(w) for w in (
    "proposal proposed propose estimate quote mystique community association invoice contract service report review "
    "update signed pdf inc llc company square drawing google docs see mail only panel white long non photo photos "
    "attach letter repair repairs maintenance board work cost approve approved build building unit owner request "
    "annual discuss agreed decided need issue also with their they that this from will would have been were about "
    "into while which other include including application hearing plan new year month item open all team group "
    "present member total amount fee charge price bid walk lane macon enchanted magical mesmerizing whimsical "
    "street prevent necessary further proceed executive session affect affected various").split())


def _stem(name: str) -> str:
    return re.sub(r"\.(pdf|docx?|xlsx?)$", "", name or "", flags=re.I).strip()


def _words(text: str) -> set[str]:
    """The text's words, lightly stemmed ("landscaping" and "landscape" are one), without the common ones."""
    return {_word(w) for w in re.findall(r"[a-z][a-z&]{3,}", (text or "").lower())} - COMMON


def word_frequency(decisions: list[Decision]) -> Counter:
    """In how many decisions each word appears: a word most decisions use names no one matter."""
    df: Counter = Counter()
    for d in decisions:
        df.update(_words(d.text))
    return df


def relate(doc_name: str, context: str, totals: list[int], d: Decision, df: Counter | None = None) -> list[str]:
    """Why a decision is about the document: the minutes item attaches it, the same amount (to the dollar), or words.

    Words: two the document's name or its agenda line shares with the decision, one of them from the name; or one word
    of the name that at most ``SINGLE_WORD_DF`` decisions use."""
    why = []
    stem = _stem(doc_name).casefold()
    if stem and any(_stem(a).casefold() == stem for a in d.attachments):
        why.append("the minutes item attaches it")
    same = sorted(t for t in set(totals) if any(abs(t - a) < 100 for a in d.amounts))
    if same:
        why.append(f"the same amount {dollars(same[0])}")
    df = df or Counter()
    name_words = _words(_stem(doc_name))
    decision_words = _words(d.text)
    shared = (name_words | _words(context)) & decision_words
    rare = {w for w in shared & name_words if df[w] <= SINGLE_WORD_DF and len(w) >= 5}
    if (len(shared) >= 2 and shared & name_words) or rare:
        why.append("shared words: " + ", ".join(sorted(shared)[:5]))
    return why


# --- inputs -----------------------------------------------------------------------------------------------------------

def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _agendas(data_dir: Path) -> list[dict[str, Any]]:
    """The agendas by meeting date, oldest first; two agenda Docs for one date are one agenda (items and documents
    merged)."""
    raw = _json(Path(data_dir) / "meetings" / "agenda-items.json") or {}
    by_date: dict[str, dict[str, Any]] = {}
    for m in raw.get("meetings", []):
        a = by_date.setdefault(m["date"], {"date": m["date"], "titles": [], "items": []})
        a["titles"].append(m.get("agenda") or "")
        a["items"] += [{**i, "_agenda": m.get("agenda") or ""} for i in m.get("items") or []]
    return [by_date[k] for k in sorted(by_date)]


def _label(item: dict[str, Any]) -> str:
    return " / ".join(p for p in (item.get("item"), item.get("subitem")) if p)


def _minutes_readings(data_dir: Path) -> dict[str, list[dict[str, Any]]]:
    raw = _json(Path(data_dir) / "documents" / "readings.json") or {}
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in raw.get("readings", []):
        if r.get("kind") != "minutes":
            continue
        day = str((r.get("fields") or {}).get("meeting_date") or r.get("period") or "")[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
            out[day].append(r)
    return out


def _model_answers(data_dir: Path) -> dict[str, dict[str, dict[str, Any]]]:
    raw = _json(Path(data_dir) / "documents" / "questions-minutes.json") or {}
    return {str(f["id"]): {a["key"]: a for a in f.get("answers") or []} for f in raw.get("files", [])}


def _catalog(data_dir: Path) -> dict[str, dict[str, Any]]:
    raw = _json(Path(data_dir) / "meetings" / "catalog.json") or {}
    return {m["date"]: m for m in raw.get("meetings", [])}


def _held_minutes(meeting: dict[str, Any] | None) -> list[dict[str, Any]]:
    return [r for r in (meeting or {}).get("records", []) if r.get("kind") == "minutes"]


class Texts:
    """A linked document's words: the agenda file fetched for it, the library's text, or a copy with the same bytes."""

    def __init__(self, data_dir: Path, *, local_copies: bool = True) -> None:
        self.data_dir = Path(data_dir)
        listing = _json(self.data_dir / "drive" / "files.json") or []
        rows = listing if isinstance(listing, list) else listing.get("files", [])
        self.md5 = {r["id"]: r["md5"] for r in rows if r.get("md5")}
        self._copies: dict[str, Path] | None = None if local_copies else {}
        self._cache: dict[tuple[str, str], tuple[str, str]] = {}

    def __call__(self, doc: dict[str, Any]) -> tuple[str, str]:
        if not doc.get("ref"):
            return "", ""
        key = (doc["where"], doc["ref"])
        if key not in self._cache:
            from jason.tasks.agenda_kinds import _local_copies, _text

            if self._copies is None:
                try:
                    self._copies = _local_copies(self.data_dir)
                except Exception:  # the digests are a convenience; without them only fetched and library text is read
                    self._copies = {}
            try:
                self._cache[key] = _text(self.data_dir, doc, self.md5, self._copies)
            except Exception:
                self._cache[key] = ("", "")
        return self._cache[key]


def _decided_kinds(data_dir: Path) -> dict[tuple[str, str], str]:
    raw = _json(Path(data_dir) / "meetings" / "agenda-kinds.json") or {}
    return {(d["where"], d["ref"]): d["kind"] for d in raw.get("decided", [])}


def _is_document(r: dict[str, Any], item: dict[str, Any], kinds: dict[tuple[str, str], str], has_total: bool = False) -> bool:
    """A proposal, estimate, contract, or invoice by its kind; an unclassified file under an item that brings those
    kinds when its name says so or its text carries a total."""
    if r.get("relation") == "received" or NOT_A_DOCUMENT.search(r.get("name") or ""):
        return False
    kind = r.get("nameKind") or kinds.get((r.get("where"), r.get("ref") or ""))
    if kind:
        return kind in DOC_KINDS
    return bool(set(item.get("expects") or []) & DOC_KINDS) and (bool(DOC_WORDS.search(r.get("name") or "")) or has_total)


def _context(item: dict[str, Any], name: str) -> str:
    """The item's words about one document: its label and the note line that names the document."""
    stem = _stem(name).casefold()[:24]
    notes = [n for n in item.get("notes") or [] if stem and stem in n.casefold()]
    return " ".join([_label(item)] + [re.sub(r"\[[^\]]*\]", " ", n) for n in notes])


# --- check 1: amounts -------------------------------------------------------------------------------------------------

def check_amounts(agenda: dict[str, Any], decisions: list[Decision], texts: Callable[[dict[str, Any]], tuple[str, str]],
                  kinds: dict[tuple[str, str], str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    used: set[int] = set()
    df = word_frequency(decisions)
    for item in agenda["items"]:
        for r in item.get("related") or []:
            if r.get("relation") == "received" or NOT_A_DOCUMENT.search(r.get("name") or ""):
                continue
            key = f"{r.get('where')}:{r.get('ref') or r.get('name')}"
            if key in seen:
                continue
            seen.add(key)
            text, source = texts(r)
            totals = document_totals(text)
            amounts = [t["amount"] for t in totals]
            context = _context(item, r["name"])
            matched = []
            for n, d in enumerate(decisions):
                why = relate(r["name"], context, amounts, d, df)
                if why:
                    matched.append((n, d, why))
            for n, _, _ in matched:
                used.add(n)                        # a decision about any linked file is not "without a linked document"
            if not _is_document(r, item, kinds, bool(totals)):
                continue
            decided = [(d, why) for _, d, why in matched if d.outcome in ("approved", "denied", "tabled")]
            row = {"date": agenda["date"], "item": _label(item), "outcome": "",
                   "document": {"name": r["name"], "where": r.get("where"), "ref": r.get("ref"), "relation": r.get("relation"),
                                "kind": r.get("nameKind") or kinds.get((r.get("where"), r.get("ref") or ""))},
                   "documentAmount": totals[0]["amount"] if totals else None, "documentTotals": totals[:4],
                   "textFrom": source or "no text on disk",
                   "decisions": [{**d.as_dict(), "because": why} for d, why in decided[:4]]}
            _judge_amounts(row, amounts, decided)
            rows.append(row)
    # A copy of the same document ("Proposal 750977-1 (2) - signed.pdf") shares its copies' decisions: an original whose
    # total the approval does not carry is then a revised document, and differs.
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_variant[_variant(row["document"]["name"])].append(row)
    for group in by_variant.values():
        shared = [d for row in group for d in row["decisions"]]
        for row in group:
            if row["decisions"] or not shared:
                continue
            copies = sorted({x["document"]["name"] for x in group if x["decisions"]})
            row["decisions"] = [{**d, "because": [f"a copy of the same document ({', '.join(copies)})"]} for d in shared[:4]]
            decided = [(Decision(d["source"], d["quote"], d["outcome"], d.get("amounts") or []), d["because"]) for d in row["decisions"]]
            _judge_amounts(row, [t["amount"] for t in row["documentTotals"]], decided)
    unmatched = [d for n, d in enumerate(decisions)
                 if n not in used and d.outcome == "approved" and d.amounts and not NOT_SPENDING.search(d.text)]
    # A decision told twice (the action and the model's amount, the same dollars) is one lead.
    kept = set(distinct_topics([d.text for d in unmatched]))
    for d in unmatched:
        if d.text not in kept:
            continue
        kept.discard(d.text)
        rows.append({"date": agenda["date"], "item": "", "outcome": AmountOutcome.WITHOUT_DOC.value, "document": None,
                     "documentAmount": None, "approvedAmounts": d.amounts, "decisions": [d.as_dict()],
                     "lead": f"the minutes approve {', '.join(dollars(a) for a in d.amounts)}; no document the agenda linked "
                             "matches it by attachment, amount, or words"})
    return rows


def _judge_amounts(row: dict[str, Any], amounts: list[int], decided: list[tuple[Decision, list[str]]]) -> None:
    doc_amount = row["documentAmount"]
    approved = sorted({a for d, _ in decided if d.outcome == "approved" for a in d.amounts})
    if not decided:
        outcome = AmountOutcome.NO_DECISION
    elif not any(d.outcome == "approved" for d, _ in decided):
        outcome = AmountOutcome.TABLED
    elif doc_amount is not None and any(abs(t - a) < 100 for t in amounts for a in approved):
        outcome = AmountOutcome.MATCHES
    elif doc_amount is not None and approved:
        outcome = AmountOutcome.DIFFERS
    else:
        outcome = AmountOutcome.DECIDED
    row["outcome"] = outcome.value
    if approved:
        row["approvedAmounts"] = approved
    if outcome is AmountOutcome.DIFFERS:
        row["lead"] = (f"the document's total is {dollars(doc_amount)}; the minutes approved "
                       f"{', '.join(dollars(a) for a in approved)}")


# --- check 2: approval of prior minutes -------------------------------------------------------------------------------

_MINUTES_OF = re.compile(r"minutes\b[^\]\n/]{0,40}?(\d{1,2})/(\d{1,2})/(\d{2,4})", re.I)


def _named_minutes(texts: list[str]) -> list[str]:
    """The meeting dates "Minutes of M/D/YY" (or "Minutes of Regular Meeting Held M/D/YY") name, in order."""
    out: list[str] = []
    for t in texts:
        out += [d for d in (_day(m) for m in _MINUTES_OF.finditer(t or "")) if d]
    return list(dict.fromkeys(out))


def _day(m: re.Match) -> str | None:
    month, day, year = (int(x) for x in m.groups())
    year = year + 2000 if year < 100 else year
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _approval_items(agenda: dict[str, Any]) -> list[dict[str, Any]]:
    return [i for i in agenda["items"] if re.search(r"approv\w*\s+(?:of\s+)?(?:the\s+)?minutes", _label(i), re.I)]


def check_prior_minutes(agendas: list[dict[str, Any]], readings: dict[str, list[dict[str, Any]]],
                        answers: dict[str, dict[str, dict[str, Any]]], catalog: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    listed: dict[str, list[str]] = defaultdict(list)          # minutes date -> agenda dates that listed it
    for agenda in agendas:
        # Two agenda Docs for one meeting may list the same minutes (one row) or different ones (a row each).
        groups: dict[tuple[str, ...], dict[str, Any]] = {}
        for item in _approval_items(agenda):
            linked = [r for r in item.get("related") or [] if r.get("relation") == "linked"]
            named = _named_minutes(list(item.get("notes") or []) + [r.get("name") or "" for r in linked])
            g = groups.setdefault(tuple(named), {"item": _label(item), "named": named, "linked": {}, "notes": [],
                                                 "agendas": []})
            g["linked"].update({(r.get("ref") or r.get("name")): r for r in linked})
            g["notes"] += [n for n in item.get("notes") or [] if n not in g["notes"]]
            if item.get("_agenda") and item["_agenda"] not in g["agendas"]:
                g["agendas"].append(item["_agenda"])
        reads = readings.get(agenda["date"], [])
        recorded, quote = False, ""
        for rd in reads:
            ok, q = prior_minutes_approved(rd, answers.get(str(rd.get("id")), {}))
            if ok:
                recorded, quote = True, q
                break
        for g in groups.values():
            named, linked = g["named"], list(g["linked"].values())
            issues: list[dict[str, Any]] = []
            for r in linked:
                if (r.get("nameKind") == "agenda") or re.match(r"\s*(?:copy of\s+)?agenda\b", r.get("name") or "", re.I):
                    issues.append({"issue": MinutesIssue.LINKS_AGENDA.value, "file": r.get("name"), "ref": r.get("ref"),
                                   "lead": f"the item names minutes, but its link opens {r.get('name')!r}"})
            if not named:
                issues.append({"issue": MinutesIssue.NAMES_NONE.value, "notes": g["notes"][:2]})
            opens_agenda = any(i["issue"] == MinutesIssue.LINKS_AGENDA.value for i in issues)
            for day in named:
                opens = [r for r in linked if r.get("nameKind") != "agenda" and day in _named_minutes([r.get("name") or ""])]
                if not opens and not opens_agenda:
                    issues.append({"issue": MinutesIssue.NOT_LINKED.value, "minutesOf": day})
                if not _held_minutes(catalog.get(day)):
                    issues.append({"issue": MinutesIssue.NOT_HELD.value, "minutesOf": day, "meetingInCatalog": day in catalog})
                earlier = [d for d in listed[day] if d < agenda["date"]]
                if earlier:
                    issues.append({"issue": MinutesIssue.RELISTED.value, "minutesOf": day, "earlierAgendas": earlier,
                                   "lead": f"minutes of {day} were already listed on the agenda of {earlier[-1]}"})
                if agenda["date"] not in listed[day]:
                    listed[day].append(agenda["date"])
            if not reads:
                issues.append({"issue": MinutesIssue.NOT_READ.value,
                               "minutesHeld": len(_held_minutes(catalog.get(agenda["date"])))})
            elif not recorded:
                issues.append({"issue": MinutesIssue.NOT_RECORDED.value, "minutesIds": [str(r.get("id")) for r in reads]})
            rows.append({"date": agenda["date"], "item": g["item"], "agendaDocs": g["agendas"], "names": named,
                         "links": [{"name": r.get("name"), "ref": r.get("ref"), "kind": r.get("nameKind")} for r in linked],
                         "approvalRecorded": recorded if reads else None, "quote": quote[:300], "issues": issues})
    # Minutes of a board meeting that no agenda listed for approval.
    # Only from the first agenda whose items name an approval of minutes: an older agenda read as one block names none.
    board_days = {a["date"] for a in agendas if not any(re.search(r"annual", t, re.I) for t in a["titles"])}
    with_items = [a["date"] for a in agendas if _approval_items(a)]
    if with_items:
        first, last = with_items[0], agendas[-1]["date"]
        for day, meeting in sorted(catalog.items()):
            if day in board_days and first <= day < last and _held_minutes(meeting) and day not in listed:
                rows.append({"date": day, "item": "", "names": [], "links": [], "approvalRecorded": None, "quote": "",
                             "issues": [{"issue": MinutesIssue.NEVER_LISTED.value, "minutesOf": day,
                                         "held": [f"{r['where']}: {r['name']}" for r in _held_minutes(meeting)[:3]]}]})
    return rows


# --- check 3: insurance renewals --------------------------------------------------------------------------------------

_RENEWAL = re.compile(r"insurance\s+renewals?|renewal\s+(?:letter|ltr|proposal|propsal)|\brenewal\b.*\b(?:policy|insurance|flood|umbrella|crime)|"
                      r"(?:flood|umbrella|crime|fidelity|d&o|liability)\b.*\brenewal", re.I)
_INSURANCE_DOC = re.compile(r"insurance|renewal|policy|flood|umbrella|crime|fidelity|\bpkg\b|tria|\bd&o\b|premium|carrier", re.I)
_INSURANCE_DECISION = re.compile(r"insurance|premium|\bpolic(?:y|ies)\b|renewal|flood|umbrella|crime|fidelity|\bd&o\b", re.I)
# A policy or its evidence, not the paperwork around a renewal.
_POLICY_NAME = re.compile(r"\bpolicy\b|declaration|\bdec\b|certificate|evidence|binder", re.I)
_NOT_POLICY = re.compile(r"renewal|proposal|propsal|\bltr\b|letter|invoice|envelope|quote|disclosure|guide|checklist|rules", re.I)
_TERM = re.compile(r"(?<!\d)(?:20)?(\d{2})\s*[-–/]\s*(?:20)?(\d{2})(?!\d)")
_YEAR = re.compile(r"(?<!\d)20(\d{2})(?!\d)")
# The words that name a line of coverage in a file's name; the specification's policies add their numbers and programs.
LINE_WORDS: dict[str, str] = {
    "flood": r"\bflood\b",
    "umbrella": r"\bumbrella\b|\bumb\b",
    "fidelity": r"\bcrime\b|\bfidelity\b|\bcr\b",
    "directors_and_officers": r"\bd\s*&\s*o\b|directors",
    "workers_comp": r"workers'?\s*comp",
    "master": r"\bpkg\b|\bpackage\b|\bmaster\b|\bproperty\b|\bliability\b|\btria\b",
}
_GENERIC_NAME = {"insurance", "company", "national", "federal", "indemnity", "services", "program", "administrators",
                 "association", "associates", "alliance", "casualty", "surety", "llc", "inc", "nfip", "the"}


def _terms(text: str) -> set[str]:
    return {f"{a}-{b}" for a, b in _TERM.findall(text or "") if int(b) == int(a) + 1}


def _years(text: str) -> set[str]:
    out = set(_YEAR.findall(_TERM.sub(" ", text or "")))
    for t in _terms(text):
        out.update(t.split("-"))
    return out


def line_patterns(community: Any = None) -> dict[str, tuple[re.Pattern, re.Pattern | None, re.Pattern | None]]:
    """Per line of coverage: the coverage words, the specification's policy numbers, and its program or carrier names."""
    numbers: dict[str, list[str]] = defaultdict(list)
    names: dict[str, list[str]] = defaultdict(list)
    try:
        policies = community.insurance().policies if community is not None else ()
    except Exception:
        policies = ()
    for p in policies:
        numbers[p.kind.value] += [re.escape(n) for n in p.numbers]
        for name in (p.program, p.carrier if not p.program else ""):
            words = [w for w in re.findall(r"[A-Za-z]{4,}", name or "") if w.lower() not in _GENERIC_NAME]
            if words:
                names[p.kind.value].append(rf"\b{re.escape(words[0])}\b")

    def rx(parts: list[str]) -> re.Pattern | None:
        return re.compile("|".join(parts), re.I) if parts else None

    return {line: (re.compile(words, re.I), rx(numbers.get(line, [])), rx(names.get(line, [])))
            for line, words in LINE_WORDS.items()}


def lines_of(text: str, patterns: dict[str, tuple[re.Pattern, re.Pattern | None, re.Pattern | None]]) -> set[str]:
    """The lines of coverage a name speaks of: its coverage words; failing those, a policy number; then a program."""
    for n in range(3):
        found = {line for line, rxs in patterns.items() if rxs[n] is not None and rxs[n].search(text or "")}
        if found:
            return found
    return set()


def _policy_files(data_dir: Path, community: Any) -> list[dict[str, Any]]:
    """Policies and certificates on file: Drive files the specification's rules name so or that sit in an insurance folder
    under a policy's name, the PayHOA library's, and the policy readings with their terms."""
    out: list[dict[str, Any]] = []
    listing = _json(Path(data_dir) / "drive" / "files.json") or []
    for r in listing if isinstance(listing, list) else listing.get("files", []):
        if r.get("mimeType", "").endswith(".folder") or _NOT_POLICY.search(r["name"]):
            continue
        kind = community.classify_document(r["name"], path=r.get("path") or "") if community is not None else None
        in_folder = "insurance" in (r.get("path") or "").lower() and bool(_POLICY_NAME.search(r["name"]))
        if (kind is not None and kind.value in POLICY_KINDS) or in_folder:
            out.append({"where": "Drive", "ref": r["id"], "name": r["name"], "kind": kind.value if kind else "insurance file",
                        "date": (r.get("created") or r.get("modified") or "")[:10]})
    db = Path(data_dir) / "library" / "library.db"
    if db.is_file():
        with sqlite3.connect(db) as con:
            for doc_id, name, kind, period in con.execute(
                    "select id, name, kind, period from documents where kind in (?, ?)", POLICY_KINDS):
                if not _NOT_POLICY.search(name or ""):
                    out.append({"where": "PayHOA library", "ref": str(doc_id), "name": name, "kind": kind, "date": ""})
    raw = _json(Path(data_dir) / "documents" / "readings.json") or {}
    for r in raw.get("readings", []):
        f = r.get("fields") or {}
        if r.get("kind") == "insurance_policy" and f.get("term_start"):
            out.append({"where": "PayHOA library", "ref": str(r["id"]), "name": r.get("name"), "kind": "insurance_policy",
                        "date": "", "termStart": str(f.get("term_start"))[:10], "termEnd": str(f.get("term_end") or "")[:10],
                        "coverage": f.get("coverage"), "number": f.get("policy_number"), "reading": True})
    return out


def _for_term(p: dict[str, Any], meeting: date, terms: set[str], years: set[str]) -> bool:
    """A policy on file for the renewal's new term: its reading's term starts near the meeting, its name carries the
    term (or, when the renewal names only a year, that year), or its name carries no year and it was filed near the
    meeting."""
    if p.get("termStart"):
        return (meeting - timedelta(days=60)).isoformat() <= p["termStart"] <= (meeting + timedelta(days=400)).isoformat()
    names_terms, names_years = _terms(p["name"]), _years(p["name"])
    if terms:
        if names_terms:
            return bool(names_terms & terms)
        if names_years:
            return bool(names_years & {y for t in terms for y in t.split("-")})
    elif years and names_years:
        return bool(names_years & years)
    day = p.get("date") or ""
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", day)) and \
        (meeting - timedelta(days=60)).isoformat() <= day <= (meeting + timedelta(days=POLICY_WINDOW)).isoformat()


_BLDG = re.compile(r"\bbldg\.?\s*(\d)\b|\bbuilding\s+(\d)\b", re.I)


def check_insurance(agenda: dict[str, Any], decisions: list[Decision] | None, policies: list[dict[str, Any]],
                    patterns: dict[str, tuple[re.Pattern, re.Pattern | None, re.Pattern | None]]) -> list[dict[str, Any]]:
    rows = []
    meeting = date.fromisoformat(agenda["date"])
    for item in agenda["items"]:
        label = _label(item)
        hits = [ln for ln in [label] + list(item.get("notes") or []) if _RENEWAL.search(ln) and not re.search(r"claim", ln, re.I)]
        if not hits:
            continue
        docs = [r for r in item.get("related") or [] if r.get("relation") != "received" and _INSURANCE_DOC.search(r.get("name") or "")]
        words = " ".join(hits + [r["name"] for r in docs])
        terms, years = _terms(words), _years(words)
        lines = set()
        for text in hits + [r["name"] for r in docs]:
            lines |= lines_of(text, patterns)
        buildings = {a or b for a, b in _BLDG.findall(words)}
        found = [d for d in decisions or [] if d.outcome and _INSURANCE_DECISION.search(d.text)]
        on_file = [p for p in policies if _for_term(p, meeting, terms, years)]
        by_line: dict[str, list[dict[str, Any]]] = {}
        for line in sorted(lines) or ["any"]:
            match = []
            for p in on_file:
                plines = lines_of(f"{p['name']} {p.get('coverage') or ''} {p.get('number') or ''}", patterns)
                if line != "any" and line not in plines:
                    continue
                if line == "flood" and buildings and not ({a or b for a, b in _BLDG.findall(p["name"])} & buildings):
                    continue
                match.append(p)
            by_line[line] = list({(p["where"], p["name"]): p for p in match}.values())[:8]
        missing = [line for line, ps in by_line.items() if not ps]
        rows.append({"date": agenda["date"], "item": label, "renewal": hits[:3], "terms": sorted(terms), "lines": sorted(lines),
                     "buildings": sorted(buildings),
                     "documents": [{"name": r["name"], "where": r.get("where"), "ref": r.get("ref")} for r in docs[:8]],
                     "minutesRead": decisions is not None,
                     "decisionRecorded": (bool(found) if decisions is not None else None),
                     "decisions": [d.as_dict() for d in found[:4]],
                     "policiesForNewTerm": by_line, "missingLines": missing, "policyOnFile": not missing,
                     "lead": _insurance_lead(decisions is not None, bool(found), missing, terms)})
    return rows


def _insurance_lead(read: bool, decided: bool, missing: list[str], terms: set[str]) -> str:
    parts = []
    if not read:
        parts.append("the minutes of this meeting were not read")
    elif not decided:
        parts.append("the minutes record no decision on the renewal")
    if missing:
        parts.append("no policy or certificate on file for the new term" + (f" ({', '.join(sorted(terms))})" if terms else "")
                     + (f": {', '.join(missing)}" if missing != ["any"] else ""))
    return "; ".join(parts)


# --- check 4: stale items ---------------------------------------------------------------------------------------------

STANDING = re.compile(r"approv\w*\s+(?:of\s+)?(?:the\s+)?minutes|treasurer|architectural review|^maintenance|maintenance\s*&|"
                      r"open maintenance|open forum|decorum|executive session|^(?:review\s+)?proposals?$|^discussion$|call to order|"
                      r"adjourn|bylaws|§|standing committees|member discipline|delinquencies|legal matters|formation of contracts|"
                      r"^agenda$|time and place|^review (?:any|all)\b|^see:?$|^reports?$|^elections?$|call for candidates|hoa election", re.I)
STANDING_KINDS = frozenset({"form", "minutes", "agenda", "treasurer_report", "financial_statement", "bank_statement", "policy",
                            "operating_rules", "image", "notice", "election_results", "correspondence"})


def _norm(text: str) -> str:
    text = re.sub(r"\[[^\]]*\]|https?://\S+|[^\w\s&/-]", " ", text or "")
    return re.sub(r"\s+", " ", text).strip(" -/").casefold()


def _keys(agenda: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """What an agenda carries: its non-standing item titles, short note headings, and the documents it linked."""
    out: dict[str, dict[str, Any]] = {}
    for item in agenda["items"]:
        for part in (item.get("item"), item.get("subitem")):
            k = _norm(part or "")
            if k and len(k) >= 4 and not STANDING.search(k) and len(k.split()) <= 10:
                out.setdefault(f"item:{k}", {"kind": "item", "label": part.strip(), "context": _label(item)})
        for n in item.get("notes") or []:
            head = _norm(n.split("[")[0])
            if head and 4 <= len(head) and len(head.split()) <= 5 and not STANDING.search(head):
                out.setdefault(f"item:{head}", {"kind": "item", "label": n.split("[")[0].strip(), "context": _label(item)})
        for r in item.get("related") or []:
            if r.get("relation") == "received" or NOT_A_DOCUMENT.search(r.get("name") or "") or r.get("where") == "not in Drive":
                continue
            if (r.get("nameKind") or "") in STANDING_KINDS:
                continue
            out.setdefault(f"doc:{_variant(r['name'])}",
                           {"kind": "document", "label": r["name"], "context": _label(item), "ref": r.get("ref"), "where": r.get("where")})
    return out


def _about(v: dict[str, Any], d: Decision, df: Counter) -> bool:
    """A decision about a carried item or document: the minutes item attaches the document, or the words match."""
    if v["kind"] == "document" and any(_variant(x) == _variant(v["label"]) for x in d.attachments):
        return True
    label = _stem(v["label"])
    shared = _words(label) & _words(d.text)
    return len(shared) >= 2 or any(df[w] <= SINGLE_WORD_DF and len(w) >= 5 for w in shared) or \
        (len(_words(label)) == 1 and bool(shared))


def _variant(name: str) -> str:
    """A file's name without its copy marks: "Proposal 750977-1 (2) - signed.pdf" is "proposal 750977-1"."""
    return _norm(re.sub(r"\s*\(\d+\)|\s*-?\s*signed\b", "", _stem(name), flags=re.I))


def check_stale(agendas: list[dict[str, Any]], decisions: dict[str, list[Decision]],
                decided_docs: frozenset[tuple[str, str]] | set[tuple[str, str]] = frozenset()) -> list[dict[str, Any]]:
    """Items and documents carried on ``STALE_DAYS`` or more consecutive agendas with no decision in those meetings'
    minutes. ``decided_docs`` are (meeting date, document) pairs the amounts check found decided."""
    board = [a for a in agendas if a["items"] and not any(re.search(r"annual", t, re.I) for t in a["titles"])]
    carried: dict[str, list[int]] = defaultdict(list)
    info: dict[str, dict[str, Any]] = {}
    for n, a in enumerate(board):
        for k, v in _keys(a).items():
            carried[k].append(n)
            info.setdefault(k, v)
    df = word_frequency([d for ds in decisions.values() for d in ds])
    rows = []
    for k, idx in carried.items():
        runs, run = [], [idx[0]]
        for i in idx[1:]:
            if i == run[-1] + 1:
                run.append(i)
            else:
                runs.append(run)
                run = [i]
        runs.append(run)
        for run in runs:
            if len(run) < STALE_DAYS:
                continue
            days = [board[i]["date"] for i in run]
            v = info[k]
            found, tabled, unread = [], [], []
            for day in days:
                if day not in decisions:
                    unread.append(day)
                    continue
                for d in decisions[day]:
                    if _about(v, d, df):
                        (tabled if d.outcome == "tabled" else found).append({"date": day, **d.as_dict()})
            if any(f["outcome"] in ("approved", "denied") for f in found):
                continue
            if v["kind"] == "document" and any((day, k[4:]) in decided_docs for day in days):
                continue
            read = [d for d in days if d not in unread]
            rows.append({"key": k, "kind": v["kind"], "label": v["label"], "item": v["context"], "ref": v.get("ref"),
                         "agendas": days, "count": len(days), "minutesRead": read, "minutesNotRead": unread,
                         "tabled": tabled[:3],
                         "lead": f"on {len(days)} consecutive agendas ({days[0]} to {days[-1]}); "
                                 + (f"no decision in the minutes of {', '.join(read)}" if read else "no minutes of those meetings were read")
                                 + (f"; minutes of {', '.join(unread)} not read" if read and unread else "")})
    rows.sort(key=lambda r: (not r["minutesRead"], -r["count"], r["agendas"][0]))
    return rows


# --- the optional model question --------------------------------------------------------------------------------------

def ask_decision(doc_name: str, context: str, minutes_text: str, ask: Callable[[str, dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """One grounded question to the local model: do these minutes record a decision about this document?"""
    from jason.community.questions import AnswerType, Question, QuestionSet, prompt, schema
    from jason.community.symbols import DocumentKind

    about = f"{_stem(doc_name)} ({context})"
    qs = QuestionSet(DocumentKind.MINUTES, "These are the minutes of a condominium association's board meeting.", (
        Question("decision", f"What did the board decide about {about}: approved, denied, tabled, or nothing?", AnswerType.TEXT),
        Question("amount", f"What dollar amount did the board approve for {about}?", AnswerType.NUMBER),
    ))
    answers = ask(prompt(qs, minutes_text[:60_000]), schema(qs))
    out = {}
    for q in qs.questions:
        a = answers.get(q.key) or {}
        ok = bool(a.get("stated")) and a.get("value") is not None and grounded(str(a.get("quote") or ""), minutes_text)
        out[q.key] = {"value": a.get("value") if ok else None, "quote": str(a.get("quote") or "")[:200], "grounded": ok}
    return out


# --- build ------------------------------------------------------------------------------------------------------------

def build(data_dir: Path, community: Any = None, *, ask: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
          max_questions: int = 3, texts: Callable[[dict[str, Any]], tuple[str, str]] | None = None,
          log: Callable[[str], None] | None = None) -> dict[str, Any]:
    data_dir = Path(data_dir)
    if community is None:
        try:
            from jason.community import load_mystique

            community = load_mystique()
        except Exception:
            community = None
    agendas = _agendas(data_dir)
    readings = _minutes_readings(data_dir)
    answers = _model_answers(data_dir)
    catalog = _catalog(data_dir)
    kinds = _decided_kinds(data_dir)
    texts = texts or Texts(data_dir)
    policies = _policy_files(data_dir, community)
    patterns = line_patterns(community)
    decisions = {day: [d for r in rs for d in decisions_of(r, answers.get(str(r.get("id")), {}))] for day, rs in readings.items()}

    meetings, amounts, insurance = [], [], []
    for a in agendas:
        reads = readings.get(a["date"], [])
        meetings.append({"date": a["date"], "agendas": a["titles"], "minutesRead": [str(r.get("id")) for r in reads],
                         "minutesHeld": len(_held_minutes(catalog.get(a["date"])))})
        if reads:
            amounts += check_amounts(a, decisions[a["date"]], texts, kinds)
        insurance += check_insurance(a, decisions.get(a["date"]) if reads else None, policies, patterns)
    asked = 0
    if ask is not None:
        from jason.tasks.library import text_for

        for row in amounts:
            if asked >= max_questions:
                break
            if row["outcome"] != AmountOutcome.NO_DECISION.value or row["documentAmount"] is None:
                continue
            for rd in readings.get(row["date"], []):
                text = text_for(data_dir, str(rd["id"]))
                if not text.strip():
                    continue
                try:
                    row["model"] = ask_decision(row["document"]["name"], row["item"], text, ask)
                except Exception as exc:  # one question the model cannot answer does not stop the checks
                    row["model"] = {"error": f"{type(exc).__name__}: {exc}"}
                asked += 1
                if log:
                    log(f"asked about {row['document']['name']} ({row['date']}): {row['model']}")
                break
    prior = check_prior_minutes(agendas, readings, answers, catalog)
    decided_docs = {(r["date"], _variant(r["document"]["name"])) for r in amounts
                    if r["document"] and r["outcome"] not in (AmountOutcome.NO_DECISION.value, AmountOutcome.TABLED.value)}
    stale = check_stale(agendas, decisions, decided_docs)
    result = {"builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "caveats": list(CAVEATS),
              "meetings": meetings, "amounts": amounts, "priorMinutes": prior, "insurance": insurance, "stale": stale,
              "modelQuestions": asked, "counts": _counts(amounts, prior, insurance, stale)}
    out = data_dir / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


def _counts(amounts: list[dict[str, Any]], prior: list[dict[str, Any]], insurance: list[dict[str, Any]],
            stale: list[dict[str, Any]]) -> dict[str, Any]:
    return {"amounts": dict(Counter(r["outcome"] for r in amounts)),
            "priorMinutes": dict(Counter(i["issue"] for r in prior for i in r["issues"])),
            "priorMinutesItems": len([r for r in prior if r["item"]]),
            "insurance": {"items": len(insurance), "decisionRecorded": sum(1 for r in insurance if r["decisionRecorded"]),
                          "minutesNotRead": sum(1 for r in insurance if not r["minutesRead"]),
                          "policyOnFile": sum(1 for r in insurance if r["policyOnFile"])},
            "stale": len(stale)}


def summary_lines(result: dict[str, Any], *, limit: int = 8) -> list[str]:
    c = result["counts"]
    read = sum(1 for m in result["meetings"] if m["minutesRead"])
    lines = [f"{len(result['meetings'])} agendas; {read} with minutes read. Every line is a lead for a person, not a finding.", "",
             "Amounts (linked document vs the minutes): " + (", ".join(f"{v} {k}" for k, v in c["amounts"].items()) or "none")]
    for r in [r for r in result["amounts"] if r["outcome"] == AmountOutcome.DIFFERS.value][:limit]:
        lines.append(f"- {r['date']} {r['document']['name'][:60]}: {r['lead']}")
    for r in [r for r in result["amounts"] if r["outcome"] == AmountOutcome.WITHOUT_DOC.value][:limit]:
        lines.append(f"- {r['date']} approved without a linked document: {r['decisions'][0]['quote'][:110]}")
    lines += ["", f"Prior minutes ({c['priorMinutesItems']} approval items): " +
              (", ".join(f"{v} {k}" for k, v in c["priorMinutes"].items()) or "no issues")]
    for r in result["priorMinutes"]:
        for i in r["issues"]:
            if i["issue"] in (MinutesIssue.LINKS_AGENDA.value, MinutesIssue.RELISTED.value, MinutesIssue.NOT_HELD.value,
                              MinutesIssue.NEVER_LISTED.value):
                lines.append(f"- {r['date']}: {i['issue']}" + (f" ({i.get('lead') or i.get('minutesOf')})"))
    ins = c["insurance"]
    lines += ["", f"Insurance renewals: {ins['items']} items; decision recorded {ins['decisionRecorded']}, minutes not read "
                  f"{ins['minutesNotRead']}, a policy on file for every line renewed {ins['policyOnFile']}"]
    for r in result["insurance"][:limit]:
        lines.append(f"- {r['date']} {r['item'][:40]} ({', '.join(r['lines']) or 'no line named'}): "
                     f"{r['lead'] or 'decision recorded; policies on file'}")
    lines += ["", f"Stale items (3+ consecutive agendas, no decision): {c['stale']}"]
    for r in result["stale"][:limit]:
        lines.append(f"- {r['label'][:60]}: {r['lead']}")
    return lines


__all__ = ["AmountOutcome", "Decision", "MinutesIssue", "build", "cents", "check_amounts", "check_insurance",
           "check_prior_minutes", "check_stale", "decisions_of", "document_totals", "summary_lines"]
