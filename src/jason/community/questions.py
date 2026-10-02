"""Questions a local model answers about a document, grounded in its words and set beside the rule reader's record.

A document model (``jason.community.models``) reads a kind with rules: a typed record and findings. A ``QuestionSet``
asks a local model the same things in words, plus what only a reader of the words can answer. Each ``Question`` names
what it asks, the answer's type, the law or rule it serves, and the field of the rule reader's record it is compared
with. The model answers every question as JSON (``schema``): whether the document states it, the answer, and a short
verbatim quote. Nothing counts unless the quote is found in the document's own text (``grounded``).

Each answer is then set beside the rule reader's field (``judge``):

- **agrees**: both state it and it is the same;
- **differs**: both state it and it is not; a person looks;
- **model only**: the model found what the rules did not; a lead for a new rule;
- **rules only**: the rules found what the model did not;
- **gap**: neither finds it; for a question that serves the law, the document may lack it;
- **ungrounded**: the model answered but its quote is not in the text; the answer does not count.

An answer is evidence, never the record. Agreement between two readers that work differently is the confidence.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from jason.community.symbols import DocumentKind


class AnswerType(Enum):
    YES_NO = "yes or no"
    DATE = "date"
    NUMBER = "number"
    TEXT = "text"
    LIST = "list"
    AMOUNT = "dollar amount"        # the model writes "$1,234.56"; the judge reads it as integer cents


class Verdict(Enum):
    AGREES = "agrees"
    DIFFERS = "differs"
    MODEL_ONLY = "model only"
    RULES_ONLY = "rules only"
    GAP = "gap"
    UNGROUNDED = "ungrounded"


@dataclass(frozen=True)
class Question:
    key: str
    ask: str
    answer: AnswerType
    why: str = ""                   # the statute or rule the answer serves
    # The rule reader's field it is set beside ("" for a question only a reader answers). A kind read by several
    # readers names each one's field: "building_limit|limit:flood_zone" is ``building_limit``, else ``limit`` on a
    # record that has a ``flood_zone`` field (the flood reader's record); the first one stated is the rules' answer.
    field: str = ""
    count: bool = False             # compare the number of entries in the field (a list of actions) with a NUMBER answer
    topics: bool = False            # compare the distinct topics of two lists (a decision told twice is one topic)
    gap: str = ""                   # the lead when neither reader finds it
    minimum: int | None = None      # AMOUNT: cents the law asks at least; a stated amount under it is marked short


@dataclass(frozen=True)
class QuestionSet:
    kind: DocumentKind
    about: str                      # what the document is, in a sentence the prompt begins with
    questions: tuple[Question, ...]


_TYPES = {AnswerType.YES_NO: {"type": ["boolean", "null"]}, AnswerType.DATE: {"type": ["string", "null"]},
          AnswerType.NUMBER: {"type": ["number", "null"]}, AnswerType.TEXT: {"type": ["string", "null"]},
          AnswerType.LIST: {"type": "array", "items": {"type": "string"}}, AnswerType.AMOUNT: {"type": ["string", "null"]}}


def schema(qs: QuestionSet) -> dict[str, Any]:
    """The JSON schema Ollama's ``format`` holds the answer to: per question, stated, value, and quote."""
    props = {q.key: {"type": "object", "properties": {"stated": {"type": "boolean"}, "value": _TYPES[q.answer],
                                                        "quote": {"type": "string"}},
                     "required": ["stated", "value", "quote"]} for q in qs.questions}
    return {"type": "object", "properties": props, "required": [q.key for q in qs.questions]}


def prompt(qs: QuestionSet, text: str) -> str:
    lines = [f"{qs.about} Answer each question from this document's own words only. Do not infer, assume, or use "
             "outside knowledge. For each question give: stated (true only if the document says it), value (null when "
             "not stated; dates as YYYY-MM-DD; yes or no as true or false; a dollar amount as written, like \"$1,234.56\"; "
             "a list as short strings), and quote (the "
             "document's exact words that support the answer, at most 200 characters, copied character for character; "
             "empty when not stated).", "", "Questions:"]
    for q in qs.questions:
        lines.append(f"- {q.key} ({q.answer.value}): {q.ask}")
    lines += ["", "Document:", "<<<", text, ">>>"]
    return "\n".join(lines)


def _norm(s: str) -> str:
    s = re.sub(r"[​­•○●]", " ", s or "")
    return re.sub(r"\s+", " ", re.sub(r"[‘’]", "'", re.sub(r"[“”]", '"', s))).strip().lower()


def grounded(quote: str, text: str, *, threshold: float = 0.9) -> bool:
    """The quote is in the text: exactly, after folding space and quote marks, or nearly (OCR'd text differs by a letter).

    A model joins passages with an ellipsis ("approved X... approved Y"); each passage must then be in the text."""
    pieces = [p for p in re.split(r"\s*(?:\.\.\.|…)\s*", quote or "") if len(_norm(p)) >= 6]
    if len(pieces) > 1:
        return all(_grounded_piece(p, text, threshold) for p in pieces)
    return _grounded_piece(quote, text, threshold)


_TOKEN = re.compile(r"[a-z0-9]+")


def _scattered(q: str, t: str, slack: int = 120) -> bool:
    """Every word of the quote in the text close together: a form's label and its value that the PDF's text layer set
    on separate lines, or in another order ("PHILADELPHIA INDEMNITY ..." above "Policy issued by:"), which a model
    quotes as one line. The words are looked for around each place the quote's longest word is."""
    words = set(_TOKEN.findall(q))
    if len(words) < 2:
        return False
    anchor = max(words, key=len)
    span = len(q) + slack
    others = [re.compile(r"\b" + re.escape(w) + r"\b") for w in words - {anchor}]
    for hit in re.finditer(r"\b" + re.escape(anchor) + r"\b", t):
        lo, hi = max(0, hit.start() - span), hit.end() + span
        if all(p.search(t, lo, hi) for p in others):
            return True
    return False


def _grounded_piece(quote: str, text: str, threshold: float) -> bool:
    q, t = _norm(quote), _norm(text)
    if not q:
        return False
    if q in t or _scattered(q, t):
        return True
    if len(q) < 12:
        return False
    matcher = difflib.SequenceMatcher(None, t, q, autojunk=False)
    block = matcher.find_longest_match(0, len(t), 0, len(q))
    start = max(0, block.a - block.b)
    window = t[start:start + len(q) + 10]
    return difflib.SequenceMatcher(None, window, q).ratio() >= threshold


def _value(v: Any) -> Any:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    if isinstance(v, (list, tuple)):
        return [x for x in (_value(i) for i in v) if x is not None] or None
    return v


_DOLLARS = re.compile(r"-?\$?\s?(\d{1,3}(?:,\d{3})+|\d+)(\.\d{1,2})?")


def cents(value: Any) -> int | None:
    """A dollar amount as the model writes it ("$1,234.56", "1234.5", 1234.56) in integer cents; None when none."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(round(float(value) * 100))
    m = _DOLLARS.search(str(value).replace("$ ", "$"))
    if not m:
        return None
    return int(round(float(m.group(1).replace(",", "") + (m.group(2) or "")) * 100))


def _same(q: Question, model: Any, rules: Any) -> bool:
    if q.answer is AnswerType.YES_NO:
        return bool(model) == bool(rules)
    if q.answer is AnswerType.AMOUNT:
        try:
            return model is not None and abs(int(model) - int(rules)) < 1
        except (TypeError, ValueError):
            return False
    if q.answer is AnswerType.NUMBER:
        try:
            return abs(float(model) - float(rules)) < 0.01
        except (TypeError, ValueError):
            return False
    if q.answer is AnswerType.DATE:
        return str(model)[:10] == str(rules)[:10]
    if q.answer is AnswerType.LIST:
        a = {_norm(str(x)) for x in model or []}
        b = {_norm(str(x)) for x in rules or []}
        return bool(a & b) and len(a & b) >= min(len(a), len(b)) * 0.6
    # Spacing and punctuation are not a difference ("Pro Active Pest Control", "ProActive Pest Control").
    a, b = re.sub(r"[^a-z0-9]", "", _norm(str(model))), re.sub(r"[^a-z0-9]", "", _norm(str(rules)))
    return a == b or (bool(a) and bool(b) and (a in b or b in a))


_STOP = {"the", "a", "an", "and", "of", "to", "for", "on", "in", "with", "board", "approved", "approve", "approval",
         "agreed", "decided", "decision", "motion", "voted", "vote", "they", "team", "group", "was", "were", "be", "at", "by",
         "its", "their", "this", "that", "from", "as", "all", "new", "per"}
_AMOUNT = re.compile(r"\$\s?[\d,]+(?:\.\d+)?")


def _signature(entry: str) -> tuple[set[str], set[str]]:
    words = {w[:6] for w in re.findall(r"[a-z]{3,}", entry.lower()) if w not in _STOP}
    amounts = {str(cents(a)) for a in _AMOUNT.findall(entry)}
    return words, amounts


def _related(a: tuple[set[str], set[str]], b: tuple[set[str], set[str]]) -> bool:
    if a[1] and b[1] and a[1] & b[1] and (not a[0] or not b[0] or {w[:4] for w in a[0]} & {w[:4] for w in b[0]}):
        # The same dollar amount told in a word of the same stem is the same matter ("Stripe", "Striping"); two
        # coverages with the same limit ("Forgery $25,000", "Outside The Premises $25,000") are not.
        return True
    if not a[0] or not b[0]:
        return False
    return len(a[0] & b[0]) / min(len(a[0]), len(b[0])) >= 0.4


def distinct_topics(entries: list[str]) -> list[str]:
    """The entries with the ones that retell an earlier one dropped (the same amount, or most of the same words)."""
    kept: list[tuple[str, tuple[set[str], set[str]]]] = []
    for e in entries:
        sig = _signature(e)
        if not any(_related(sig, k) for _, k in kept):
            kept.append((e, sig))
    return [e for e, _ in kept]


def compare_topics(model: list[str], rules: list[str]) -> dict[str, Any]:
    """The two readers' distinct topics, matched: what both found, and what only one did."""
    m, r = distinct_topics(model), distinct_topics(rules)
    rs = [_signature(x) for x in r]
    both = [x for x in m if any(_related(_signature(x), s) for s in rs)]
    only_model = [x for x in m if x not in both]
    only_rules = [x for x, s in zip(r, rs) if not any(_related(s, _signature(y)) for y in m)]
    return {"modelTopics": len(m), "rulesTopics": len(r), "both": both, "onlyModel": only_model, "onlyRules": only_rules}


def _entry(x: Any) -> str:
    """One entry of a record's list as words: a dict's label with its amount in dollars ("CRACK SEAL $2,100.00")."""
    if not isinstance(x, dict):
        return str(x)
    label = next((str(x[k]) for k in ("text", "description", "name", "named", "title") if x.get(k)), "")
    amount = next((x[k] for k in ("amount", "amount_cents", "limit") if isinstance(x.get(k), int)), None)
    return f"{label} ${amount / 100:,.2f}".strip() if amount is not None else label


def _field(q: Question, fields: dict[str, Any]) -> Any:
    """The first of the question's fields the record states (see ``Question.field``); False when one says no."""
    said_no = False
    for alt in q.field.split("|"):
        name, _, when = alt.strip().partition(":")
        if name not in fields or (when and when not in fields):
            continue
        v = fields[name]
        if v is False:
            said_no = True
        elif v not in (None, "", [], (), {}):
            return v
    return False if said_no else None


def rule_value(q: Question, fields: dict[str, Any]) -> Any:
    """The rule reader's answer: the field, or the count of its entries; an empty field is no answer."""
    if not q.field:
        return None
    v = _field(q, fields)
    if q.count:
        return len(v) if v else None
    if isinstance(v, str) and q.answer is AnswerType.LIST:
        v = [v]
    if isinstance(v, (list, tuple)):
        v = [_entry(x) for x in v]
    if q.topics:
        return v or None
    if isinstance(v, date):
        return v.isoformat()
    if v is False and q.answer is AnswerType.YES_NO:
        return False
    if q.answer is AnswerType.AMOUNT:
        return v if isinstance(v, int) and not isinstance(v, bool) else None
    return _value(v)


def judge(q: Question, answer: dict[str, Any], text: str, fields: dict[str, Any]) -> dict[str, Any]:
    """One question's verdict: the model's answer grounded in the text, set beside the rule reader's."""
    value = _value(answer.get("value"))
    if q.answer is AnswerType.AMOUNT:
        value = cents(value)
    stated = bool(answer.get("stated")) and value is not None
    quote = str(answer.get("quote") or "")
    rules = rule_value(q, fields)
    if q.answer is AnswerType.YES_NO and not stated and rules is False:
        # Neither reader finds it (no draft mark, no executive session): the rules' "no" and the model's silence agree.
        return {"key": q.key, "model": False, "quote": "", "rules": False, "verdict": Verdict.AGREES.value}
    if q.answer is AnswerType.YES_NO and value is False and rules is None:
        # The model's "no" with nothing from the rules is its silence: neither reader finds the thing asked about.
        stated = False
    if q.count and isinstance(value, list):
        value = len(value)                   # a list of the decisions, each quoted, is counted against the rules' actions
    out: dict[str, Any] = {"key": q.key, "model": value if stated else None, "quote": quote[:200], "rules": rules}
    # A list's quote may skip lines between its entries ("i. Member Discipline ii. Delinquencies" over a sub-bullet); the
    # entries are then each looked for in the text (an invoice's "BUILDING PREMIUM: $851.00" lines, each on the page).
    list_found = q.answer is AnswerType.LIST and isinstance(value, list) and not q.count and \
        all(grounded(str(v), text) for v in value if len(str(v)) >= 4)
    if stated and not grounded(quote, text) and not list_found:
        verdict = Verdict.UNGROUNDED
    elif not q.field:
        verdict = Verdict.MODEL_ONLY if stated else Verdict.GAP
    elif stated and rules is not None and q.topics:
        found = compare_topics([str(v) for v in value], list(rules))
        out.update(found)
        out["rules"] = f"{found['rulesTopics']} topics"
        agree = len(found["both"]) >= 0.6 * max(found["modelTopics"], found["rulesTopics"], 1)
        verdict = Verdict.AGREES if agree else Verdict.DIFFERS
    elif stated and rules is not None:
        same = abs(float(value) - float(rules)) < 0.01 if q.count else _same(q, value, rules)
        verdict = Verdict.AGREES if same else Verdict.DIFFERS
    elif stated:
        verdict = Verdict.MODEL_ONLY
    elif rules is not None:
        verdict = Verdict.RULES_ONLY
    else:
        verdict = Verdict.GAP
    out["verdict"] = verdict.value
    if verdict is Verdict.GAP and q.gap:
        out["lead"] = q.gap
        out["authority"] = q.why
    if q.minimum is not None:
        amount = value if stated and verdict is not Verdict.UNGROUNDED else rules
        if isinstance(amount, int) and amount < q.minimum:
            out["short"] = f"${amount / 100:,.2f} is under ${q.minimum / 100:,.2f}"
            out["authority"] = q.why
    return out


__all__ = ["AnswerType", "Question", "QuestionSet", "Verdict", "cents", "grounded", "judge", "prompt", "rule_value", "schema"]
