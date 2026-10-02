"""A local model reading one section at a time for its duties, prohibitions, permissions, rights, and conditions.

Two ways to ask, measured against the phrase grammar (``jason.community.deontic``) in docs/document-duties.md:

- **Free reading** (``DutyModel.read``): the section's words, the lead-in of the list it belongs to, and the kinds and
  traps; the model lists every norm with a verbatim quote.
- **Hybrid** (``DutyModel.review``): the grammar's candidates, each with its marker bracketed in its sentence; the
  model says whether each is a norm, of what kind, and who bears it, and lists any norm the candidates missed.

The prompt names kinds and questions, never a section number or a figure (``jason.community.prompts``). Nothing the
model says is kept on its word: ``to_duties`` keeps a proposal only when its quote is in the section (compared without
regard to case, spacing, or the style of quotation marks and dashes, ``reference_model.find_quote``) and only with the
kinds and bearers ``deontic`` defines. A kept reading is marked ``method="model"`` or ``"hybrid"``: a lead a person
reviews, never a rule row. The model is asked only through an Ollama on this machine, under the GPU lock, after
``jason.local_ai.preflight``.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from typing import Any
from urllib.parse import urlparse

from jason.community.deontic import (
    Bearer, Deadline, DeadlineRelation, DocumentDuty, DutyKind, NORMS, find_deadline, find_recurrence, _markers,
)
from jason.community.reference_model import LOCAL_HOSTS, find_quote

KIND_WORDS = [k.value for k in NORMS]
BEARER_WORDS = [b.value for b in Bearer]

_NORM_ITEM: dict[str, Any] = {
    "type": "object",
    "properties": {
        "quote": {"type": "string"},
        "kind": {"type": "string", "enum": KIND_WORDS},
        "bearer": {"type": "string", "enum": BEARER_WORDS},
        "action": {"type": "string"},
        "trigger": {"type": "string"},
        "deadline": {"type": "string"},
        "recurrence": {"type": "string"},
        "conditions": {"type": "array", "items": {"type": "string"}},
        "notice": {"type": "boolean"},
    },
    "required": ["quote", "kind", "bearer", "action", "trigger", "deadline", "recurrence", "notice"],
}
READ_SCHEMA: dict[str, Any] = {"type": "object", "properties": {"norms": {"type": "array", "items": _NORM_ITEM}},
                               "required": ["norms"]}
REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "norm": {"type": "boolean"},
                    "kind": {"type": "string", "enum": KIND_WORDS + ["none"]},
                    "bearer": {"type": "string", "enum": BEARER_WORDS},
                    "trigger": {"type": "string"},
                    "deadline": {"type": "string"},
                    "recurrence": {"type": "string"},
                    "notice": {"type": "boolean"},
                },
                "required": ["n", "norm", "kind", "bearer", "deadline", "recurrence", "notice"],
            },
        },
        "missed": {"type": "array", "items": _NORM_ITEM},
    },
    "required": ["candidates", "missed"],
}

METHOD = """You read one section of a California common interest development's governing document (a declaration of \
covenants, conditions and restrictions, bylaws, election rules, operating rules, or a board policy or resolution) and \
find the norms it states: what someone must do, must not do, may do, or is entitled to, and the conditions on them.

Kinds:
- duty: someone must act ("shall", "must", "is required to", "is responsible for", "agrees to"), including a duty \
stated in the passive ("notice shall be given", "the minutes shall be made available").
- prohibition: someone must not act ("shall not", "may not", "No Owner shall", "nor shall", "is prohibited").
- permission: someone may act but need not: a power, a discretion, or a privilege ("may", "shall have the power to", \
"in its sole discretion", "is permitted").
- right: someone holds a right others must respect ("shall have the right to", "is entitled to", "shall not be denied").
- condition: an effect that turns on an event or a requirement without a duty of its own ("shall be subject to", "is \
delinquent if", "shall be effective only when"), and a list item that is a condition of something else.
These are not norms; leave them out: a definition ("shall mean", "shall be deemed", "shall be treated as"); a \
statement of status ("shall be a Member", "shall be appurtenant to", "shall pass with title", "shall have one vote"); a \
"may" or "shall" inside a relative or conditional clause ("as the Board may determine", "which may become a \
nuisance", "Unless the Board shall designate otherwise"); words a notice or a form must say, quoted; a recital \
("WHEREAS"); a recommendation ("should", "it is recommended"); a possibility ("may occur", "may be exposed"); and a \
disclaimer ("the Association is not responsible for").

bearer: who must, must not, or may act; for a right, who holds it. One of: association; board (the board or a \
director); officer (president, secretary, treasurer); committee; inspector (of elections); manager (the managing agent); \
owner; member; occupant (resident, tenant, guest); candidate; declarant; mortgagee; person (any person); other (a court \
or public agency); unstated. In a passive sentence the subject is not the bearer: "Members shall be given notice" is a \
duty to give the Members notice, borne by whoever gives it. When the words leave the bearer out but the section makes \
clear who acts (the board holds its own meetings and hearings; the association keeps its records; owners pay \
assessments), name that bearer; otherwise say unstated.

For each norm: trigger is what sets it off as written ("upon receipt of an application"), or ""; deadline is a time \
limit or period as written ("within 30 days after the hearing", "at least ten days before the meeting", "for one year \
after the election"), or ""; recurrence is how often as written ("annually", "at least quarterly", "each month"), or \
""; conditions are exceptions and conditions as written ("unless ...", "except ...", "provided that ..."); notice is true \
when the act is to give notice to, mail, deliver, post, or distribute something to people, or the norm sets what a \
notice or ballot must contain."""

EXAMPLES = """Examples (invented text):
Text: "\\"Common Area\\" shall mean all real property owned by the Association. Each Owner shall be a Member."
Answer: {"norms": []}
Text: "Within fifteen (15) days after the hearing, the Board shall mail its written decision to the Owner. The Board \
may, in its sole discretion, extend the time to cure."
Answer: {"norms": [{"quote": "the Board shall mail its written decision to the Owner", "kind": "duty", "bearer": "board", \
"action": "mail its written decision to the Owner", "trigger": "", "deadline": "Within fifteen (15) days after the \
hearing", "recurrence": "", "conditions": [], "notice": true}, {"quote": "The Board may, in its sole discretion, extend \
the time to cure", "kind": "permission", "bearer": "board", "action": "extend the time to cure", "trigger": "", \
"deadline": "", "recurrence": "", "conditions": [], "notice": false}]}
Text: "No Owner shall keep more than two pets in a Unit, except as permitted by the Rules. Notice of each meeting of the \
Board shall be posted in the Common Area at least four days before the meeting."
Answer: {"norms": [{"quote": "No Owner shall keep more than two pets in a Unit", "kind": "prohibition", "bearer": \
"owner", "action": "keep more than two pets in a Unit", "trigger": "", "deadline": "", "recurrence": "", "conditions": \
["except as permitted by the Rules"], "notice": false}, {"quote": "Notice of each meeting of the Board shall be posted in \
the Common Area", "kind": "duty", "bearer": "board", "action": "post notice of each meeting in the Common Area", \
"trigger": "", "deadline": "at least four days before the meeting", "recurrence": "", "conditions": [], "notice": true}]}
Text (a list item; the lead-in is "The Treasurer shall:"): "Present a statement of income and expenses to the Board \
each quarter."
Answer: {"norms": [{"quote": "Present a statement of income and expenses to the Board each quarter", "kind": "duty", \
"bearer": "officer", "action": "present a statement of income and expenses to the Board", "trigger": "", "deadline": "", \
"recurrence": "each quarter", "conditions": [], "notice": false}]}"""


def _where(source: str, title: str, section: str, caption: str, lead: str) -> str:
    where = f"The document: {title or source}"
    where += f", section {section}" if section else ", a part with no section number"
    if caption and caption != section:
        where += f" ({caption[:90]})"
    where += "."
    if lead:
        where += f"\nThis section is an item of a list introduced by: \"{lead}\""
    return where


def read_prompt(text: str, *, source: str = "", title: str = "", section: str = "", caption: str = "", lead: str = "") -> str:
    """The free reading: the method, worked examples, where the section sits, and its words."""
    return (METHOD + "\n\nquote: words copied exactly, character for character, from the section below, four to \
twenty-five words, including the words that make it a norm. Never paraphrase a quote, and never list a norm whose words \
are not in the text. An empty list is a good answer when the section states no norm.\n\n" + EXAMPLES + "\n\n"
            + _where(source, title, section, caption, lead) + f"\nText:\n{text}")


def mark(sentence: str, start: int, end: int) -> str:
    return sentence[:start] + "[[" + sentence[start:end] + "]]" + sentence[end:]


def review_prompt(text: str, candidates: list[DocumentDuty], *, source: str = "", title: str = "", section: str = "",
                  caption: str = "", lead: str = "") -> str:
    """The hybrid: the method, the section, and the grammar's candidates (each sentence with its marker in [[ ]])."""
    lines = []
    for n, c in enumerate(candidates, 1):
        at = c.marker_at - c.start
        width = len(c.marker) if c.marker not in ("lead-in",) and not c.marker.startswith("no ...") else 0
        if c.marker.startswith("no ..."):
            width = len(c.marker.split()[-1])
        sentence = mark(c.quote, at, at + width) if width else "[[list item]] " + c.quote
        lines.append(f"{n}. {' '.join(sentence.split())[:700]}")
    return (METHOD + "\n\nA phrase reader found the candidates below in this section; in each, the words that made it a "
            "candidate are in [[ ]]. For each candidate n, say whether it is a norm (norm: false, kind \"none\" for a "
            "definition, a status, a modal inside a relative or conditional clause, a quoted form, or a possibility), "
            "its kind, its bearer, and its trigger, deadline, recurrence, and notice as defined above. Then list in "
            "missed any norm in the section that no candidate covers, with a quote copied exactly from the text (four "
            "to twenty-five words); an empty list when there is none.\n\n"
            + _where(source, title, section, caption, lead) + f"\nText:\n{text}\n\nCandidates:\n" + "\n".join(lines))


class DutyModel:
    """The shared local model over one section, answering to ``READ_SCHEMA`` or ``REVIEW_SCHEMA``.

    ``fetch(url, payload)`` replaces HTTP in tests. Only an Ollama on this machine is asked.
    """

    def __init__(self, *, model: str = "", base_url: str = "", fetch=None, timeout: int = 600, keep_alive: str = "5m",
                 num_ctx: int = 0) -> None:
        from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL

        self.model = model or DEFAULT_MODEL
        self.num_ctx = num_ctx or DEFAULT_CONTEXT
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")
        if (urlparse(self.base_url).hostname or "") not in LOCAL_HOSTS:
            raise ValueError(f"the duty model reads only through an Ollama on this machine, not {self.base_url}")
        self._fetch = fetch
        self.timeout = timeout
        self.keep_alive = keep_alive
        self._checked = False

    def preflight(self) -> None:
        if self._fetch is not None or self._checked:
            return
        from jason.community.content import ModelUnavailable
        from jason.local_ai import LocalAIUnavailable, preflight

        try:
            preflight(self.model, ollama_url=self.base_url)
        except LocalAIUnavailable as exc:
            raise ModelUnavailable(str(exc)) from exc
        self._checked = True

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._fetch is not None:
            return self._fetch(f"{self.base_url}{path}", payload)
        from urllib.error import URLError
        from urllib.request import Request, urlopen

        from jason.community.content import ModelUnavailable
        from jason.locks import Resource, ResourceBusy, hold

        request = Request(f"{self.base_url}{path}", data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            with hold(Resource.GPU, timeout=self.timeout, purpose=f"{self.model} duties"), \
                    urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except ResourceBusy as exc:
            raise ModelUnavailable(f"the model server is busy with another jason process: {exc}") from exc
        except (URLError, OSError) as exc:
            raise ModelUnavailable(f"Ollama at {self.base_url} did not answer: {exc}") from exc

    def _ask(self, prompt: str, schema: dict[str, Any]) -> str:
        self.preflight()
        data = self._post("/api/chat", {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                                         "format": schema, "stream": False, "think": False, "keep_alive": self.keep_alive,
                                         "options": {"temperature": 0, "num_ctx": self.num_ctx}})
        return str((data.get("message") or {}).get("content") or data.get("response") or "")

    def read(self, text: str, **where: str) -> str:
        return self._ask(read_prompt(text, **where), READ_SCHEMA)

    def review(self, text: str, candidates: list[DocumentDuty], **where: str) -> str:
        return self._ask(review_prompt(text, candidates, **where), REVIEW_SCHEMA)


def _load(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _deadline(words: str) -> Deadline | None:
    words = " ".join((words or "").split())
    if not words:
        return None
    return find_deadline(words) or Deadline(words, DeadlineRelation.WITHIN)


def _recurrence(words: str) -> tuple[str, int]:
    words = " ".join((words or "").split())
    if not words:
        return "", 0
    found, months = find_recurrence(words)
    return (found or words), months


def _first_marker(text: str, start: int, end: int) -> int:
    """The offset of the first marker inside ``text[start:end]`` (where a person would point), else ``start``."""
    found = _markers(text[start:end])
    return start + found[0].start if found else start


def to_duties(raw: str, text: str, *, source: str, section: str, base: int, method: str = "model"
              ) -> tuple[list[DocumentDuty], list[dict[str, Any]]]:
    """The model's norms whose quotes are in ``text``, as readings; and what was dropped, with why."""
    data = _load(raw)
    if data is None or not isinstance(data.get("norms"), list):
        return [], [{"why": "the model's answer is not JSON with a list of norms", "raw": (raw or "")[:300]}]
    kept, dropped = [], []
    for item in data["norms"]:
        made = _norm(item, text, source=source, section=section, base=base, method=method)
        if isinstance(made, DocumentDuty):
            kept.append(made)
        else:
            dropped.append({"why": made, "item": item})
    return kept, dropped


def _norm(item: Any, text: str, *, source: str, section: str, base: int, method: str) -> DocumentDuty | str:
    if not isinstance(item, dict):
        return "not an object"
    quote = str(item.get("quote") or "").strip()
    span = find_quote(text, quote)
    if span is None:
        return "its quote is not in the section"
    try:
        kind = DutyKind(str(item.get("kind") or "").strip().lower())
        bearer = Bearer(str(item.get("bearer") or "unstated").strip().lower())
    except ValueError:
        return "a kind or bearer jason does not define"
    if kind not in NORMS:
        return "not a norm"
    recurrence, months = _recurrence(str(item.get("recurrence") or ""))
    conditions = tuple(str(c).strip() for c in item.get("conditions") or () if str(c).strip())
    s, e = span
    return DocumentDuty(
        source=source, section=section, start=base + s, end=base + e, quote=text[s:e], kind=kind, bearer=bearer,
        marker="model", marker_at=base + _first_marker(text, s, e), action=" ".join(str(item.get("action") or "").split())[:240],
        trigger=" ".join(str(item.get("trigger") or "").split()), deadline=_deadline(str(item.get("deadline") or "")),
        recurrence=recurrence, recurrence_months=months, conditions=conditions,
        notice=bool(item.get("notice")), method=method)


def merge_review(raw: str, candidates: list[DocumentDuty], text: str, *, source: str, section: str, base: int,
                 fill_only: bool = False) -> tuple[list[DocumentDuty], list[dict[str, Any]]]:
    """The hybrid's readings: each grammar candidate with the model's kind, bearer, and timing (``fill_only``: keep the
    grammar's kind and timing and fill only a bearer the grammar left unstated), the candidates the model calls no norm
    dropped, and the model's missed norms whose quotes are in the text."""
    data = _load(raw)
    if data is None or not isinstance(data.get("candidates"), list):
        return list(candidates), [{"why": "the model's answer is not JSON with a list of candidates", "raw": (raw or "")[:300]}]
    verdicts = {}
    for v in data["candidates"]:
        if isinstance(v, dict) and isinstance(v.get("n"), int):
            verdicts[v["n"]] = v
    out, dropped = [], []
    for n, c in enumerate(candidates, 1):
        v = verdicts.get(n)
        if v is None:
            out.append(replace(c, method="hybrid"))
            continue
        try:
            bearer = Bearer(str(v.get("bearer") or "unstated").lower())
        except ValueError:
            bearer = Bearer.UNSTATED
        if fill_only:
            # Only the bearer the grammar left out: its kinds and timing measured better than the model's (the model
            # adds deadlines a sentence's preface sets for another act).
            out.append(replace(c, method="hybrid", bearer=bearer if c.bearer is Bearer.UNSTATED else c.bearer))
            continue
        kind_word = str(v.get("kind") or "").lower()
        if not v.get("norm") or kind_word not in KIND_WORDS:
            dropped.append({"why": "the model calls it no norm", "candidate": c.quote[:200], "marker": c.marker})
            continue
        # The model's kind and notice; its bearer unless it says unstated; its timing, else the grammar's.
        recurrence, months = _recurrence(str(v.get("recurrence") or ""))
        out.append(replace(c, method="hybrid", kind=DutyKind(kind_word),
                           bearer=bearer if bearer is not Bearer.UNSTATED else c.bearer,
                           deadline=_deadline(str(v.get("deadline") or "")) or c.deadline,
                           recurrence=recurrence or c.recurrence, recurrence_months=months or c.recurrence_months,
                           trigger=" ".join(str(v.get("trigger") or "").split()) or c.trigger,
                           notice=bool(v.get("notice"))))
    if not fill_only:
        for item in data.get("missed") or ():
            made = _norm(item, text, source=source, section=section, base=base, method="hybrid")
            if isinstance(made, DocumentDuty):
                if any(abs(made.marker_at - o.marker_at) <= 3 for o in out):
                    continue
                out.append(made)
            else:
                dropped.append({"why": made, "item": item})
    return out, dropped


__all__ = ["DutyModel", "READ_SCHEMA", "REVIEW_SCHEMA", "read_prompt", "review_prompt", "to_duties", "merge_review", "mark"]
