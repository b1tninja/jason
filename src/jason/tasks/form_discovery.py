"""The discovery pass for standard forms (docs/standard-forms.md, "How to find them: from the law, the documents, and the
reference works").

Five steps, each stopping short of making anything:

1. **Seed from the statutes.** Each section on the authorities shelf (``data/authorities/<CODE>/*.md``) is searched for the
   general language that creates a request: "written request", "upon request", "shall approve or deny", "deemed approved".
   A hit is a span (the paragraphs around it, never a whole page) with the section's canonical citation. No model.
2. **Seed from the documents.** The same search over the section outlines of the governing documents, rules, and policies
   the community keeps (``data/outlines``). Each span names its document key and section. No model, no embedder, no GPU.
3. **Join.** A statute and the document sections that carry it out are grouped when they share a citation, a kind of
   request, or the words that carry their subject. Each join keeps its reason. ``known_as`` says which existing request
   kind (``ResponseKind``) or notice-catalog row a span matches.
4. **Read** (``--read`` only). The local model reads a span into one record (who submits, to whom, what, the clocks, the
   decision). A reading whose quote is not found in the span word for word is dropped with its candidate. A reading is a
   lead for a person, never the rule.
5. **A person decides.** Confirm, hold, or drop each candidate, each act logged with who and why. Confirming writes the
   candidate's status and the log, and nothing else: no form, no procedure, no known-form row.

The patterns are general legal language: nothing here names an association, a street, a vendor, or a section of one
association's documents. The store is ``data/forms/candidates.json`` and the log ``data/forms/candidate-acts.jsonl``.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Protocol

from jason.community.form_candidates import (
    CandidateReading, CandidateSource, CandidateStatus, CandidateStore, Clock, Decision, FormCandidate, Join, JoinBasis,
)
from jason.community.references import CODES, STATUTE_IN_TEXT, StatuteCitation, statute_citation
from jason.community.responses import ClockSource, ResponseKind

QUOTE_NOT_FOUND = "quote not found"
MAX_SPAN = 1600                                  # characters kept of one span: a cluster of paragraphs, cut at a sentence
NOT_A_FORM_KIND = frozenset({ResponseKind.OTHER, ResponseKind.QUESTION, ResponseKind.COMPLAINT, ResponseKind.MAINTENANCE})


class DiscoveryError(RuntimeError):
    """A refusal the command prints as ``jason discover-forms: <reason>``."""


# ---------------------------------------------------------------------------------------------------------------------
# The seed patterns: general legal language only


@dataclass(frozen=True)
class SeedPattern:
    """One phrase pattern. A span is kept when one ``strong`` pattern matches, or two of any kind do."""

    name: str
    regex: str
    note: str
    strong: bool = True

    def search(self, text: str) -> bool:
        return _compiled(self.regex).search(text) is not None


@lru_cache(maxsize=None)
def _compiled(regex: str) -> re.Pattern[str]:
    return re.compile(regex, re.I)


SEED_PATTERNS: tuple[SeedPattern, ...] = (
    SeedPattern("written-request",
                r"\bwritten\s+(?:request|application|demand)s?\b|\brequests?\s+in\s+writing\b|\brequest\w*\b[^.;]{0,30}\bin\s+writing\b",
                "a request that has to be made in writing"),
    SeedPattern("upon-request",
                r"\bupon\s+(?:the\s+)?(?:written\s+|timely\s+)?request\b|\bon\s+(?:the\s+)?request\s+of\b|\bat\s+the\s+request\s+of\b",
                "something the body must do or allow when asked"),
    SeedPattern("may-request",
                r"\b(?:may|shall\s+have\s+the\s+right\s+to|has\s+the\s+right\s+to|is\s+entitled\s+to|are\s+entitled\s+to)\s+"
                r"(?:also\s+|first\s+)?(?:make\s+a\s+|submit\s+a\s+)?request\b",
                "a right to ask"),
    SeedPattern("someone-requests",
                r"\b(?:members?|owners?|residents?|persons?|parties|party|applicants?|requesters?|requestors?)\s+"
                r"(?:properly\s+|timely\s+|first\s+)?(?:requests?|asks?\s+for|applies\s+for|petitions?\s+for)\b",
                "a member, owner, or applicant who asks"),
    SeedPattern("shall-submit",
                r"\b(?:shall|must|may|is\s+required\s+to|are\s+required\s+to)\s+(?:first\s+|also\s+)?submit\b",
                "something the member hands in"),
    SeedPattern("application",
                r"\bapplications?\s+(?:for|to|shall|must|may)\b|\b(?:submit|file|complete|receipt\s+of|receive|review)\w*\s+"
                r"(?:an?\s+|the\s+|each\s+|any\s+)?(?:written\s+|completed\s+)?applications?\b",
                "an application the member makes"),
    SeedPattern("prior-written-approval",
                r"\b(?:prior|advance)\s+(?:written\s+)?(?:approval|consent|permission|authorization)\b|"
                r"\bwritten\s+(?:approval|permission|authorization)\b|\bwithout\s+(?:first\s+)?(?:obtaining\s+)?(?:the\s+)?"
                r"(?:prior\s+)?(?:written\s+)?(?:approval|permission)\b",
                "something the member may not do without approval first"),
    SeedPattern("approve-or-deny",
                r"\b(?:approve|grant)\w*\s+(?:or|and/or)\s+(?:deny|disapprove|reject|refuse)\w*|\b(?:approv\w+|den(?:y|ied|ial))\b"
                r"[^.;]{0,60}\bin\s+writing\b",
                "a decision the body must make, and in writing"),
    SeedPattern("deemed-approved",
                r"\bdeemed\s+(?:to\s+be\s+)?(?:approved|granted|denied|accepted)\b",
                "what happens when the clock passes in silence"),
    SeedPattern("shall-not-refuse",
                r"\bshall\s+not\s+(?:unreasonably\s+)?(?:refuse|deny|withhold)\b|\bmay\s+not\s+(?:refuse|deny)\s+(?:a|any|the)\s+request\b",
                "a request the body may not turn away"),
    SeedPattern("shall-register",
                r"\b(?:shall|must|is\s+required\s+to|are\s+required\s+to)\s+(?:first\s+|annually\s+)?register\b",
                "a registration the member must make"),
    SeedPattern("reservation",
                r"\breservations?\s+(?:shall|must|may|of\s+the)\b|\b(?:clubhouse|pool|facility|facilities|room|hall|amenity)\s+reservations?\b|"
                r"\b(?:shall|must)\s+(?:first\s+)?reserve\b",
                "a booking of a shared facility"),
    SeedPattern("hearing-on-request",
                r"\b(?:request\w*|ask\w*)\b[^.;]{0,40}\b(?:hearing|appeal|reconsideration|variance)\b|"
                r"\b(?:hearing|appeal|reconsideration)\b[^.;]{0,30}\b(?:upon|on)\s+(?:the\s+)?request\b|"
                r"\bright\s+to\s+(?:a\s+|an\s+)?(?:hearing|appeal)\b",
                "a hearing, appeal, or reconsideration the member can ask for"),
    SeedPattern("within-days-of",
                r"\bwithin\s+(?:(?:[a-z-]+\s+)?\(?\d+\)?|[a-z-]+)\s+(?:business\s+|calendar\s+)?days?\s+(?:of|after|from|following)\b",
                "a clock that runs from an event", strong=False),
    SeedPattern("a-request",
                r"\b(?:the|a|any|such|that|each)\s+(?:written\s+)?request\b",
                "the word request, which alone proves little", strong=False),
    SeedPattern("permit",
                r"\b(?:parking|guest|building|use|special\s+use|temporary|vehicle)\s+permits?\b|\bobtain\w*\s+(?:an?\s+)?permits?\b|"
                r"\bpermits?\s+(?:is\s+|are\s+|shall\s+be\s+)?required\b",
                "a permit", strong=False),
    SeedPattern("move-in-out",
                r"\bmove[\s-]?(?:in|out)\b",
                "a move-in or move-out request", strong=False),
    SeedPattern("lease-approval",
                r"\b(?:lease|leasing|rental|renting|rent)\b[^.;]{0,50}\b(?:approval|application|prior\s+written|registration)\b",
                "an approval or registration for renting a unit", strong=False),
    SeedPattern("variance-or-exception",
                r"\bvariances?\b|\bexceptions?\s+to\s+(?:the\s+|this\s+)?(?:rule|policy|restriction|requirement)s?\b",
                "an exception the member may seek", strong=False),
)


# ---------------------------------------------------------------------------------------------------------------------
# Spans


def _normal(text: str) -> str:
    return " ".join(text.split())


def candidate_id(source: CandidateSource, citation: str, quote: str) -> str:
    """A stable id: the same words under the same citation are the same candidate on every seed."""
    import hashlib

    body = _normal(quote).lower()[:240]
    return "fc-" + hashlib.sha1(f"{source.value}|{citation}|{body}".encode("utf-8")).hexdigest()[:10]


def _cut(text: str) -> str:
    """``text`` cut to ``MAX_SPAN`` characters at a sentence end (or a space): still the source's own words."""
    if len(text) <= MAX_SPAN:
        return text
    head = text[:MAX_SPAN]
    end = max(head.rfind(". "), head.rfind(".\n"))
    if end > MAX_SPAN // 2:
        return head[:end + 1]
    return head[:head.rfind(" ")] if " " in head else head


def _lead_in(paragraphs: list[str], at: int) -> int:
    """A list item takes the paragraph that introduces it ("... all of the following:" before "(1) ...")."""
    if at > 0 and re.match(r"^\(\w{1,3}\)", paragraphs[at]) and paragraphs[at - 1].rstrip().endswith(":"):
        return at - 1
    return at


def spans_in(paragraphs: list[str], patterns: Iterable[SeedPattern]) -> list[tuple[str, tuple[str, ...]]]:
    """The spans of ``paragraphs`` worth a look: each cluster of paragraphs with a pattern hit (hits within one paragraph
    of each other are one span), with its list lead-in, as ``(text, names of the patterns that matched)``. A span stands
    when a strong pattern matched, or two patterns of any kind did."""
    patterns = tuple(patterns)
    hit = [k for k, par in enumerate(paragraphs) if any(p.search(par) for p in patterns)]
    out: list[tuple[str, tuple[str, ...]]] = []
    k = 0
    while k < len(hit):
        lo = hi = hit[k]
        while k + 1 < len(hit) and hit[k + 1] - hi <= 1:
            k += 1
            hi = hit[k]
        k += 1
        text = _cut("\n".join(paragraphs[_lead_in(paragraphs, lo):hi + 1]))
        matched = [p for p in patterns if p.search(text)]
        if matched and (any(p.strong for p in matched) or len(matched) >= 2):
            out.append((text, tuple(p.name for p in matched)))
    return out


_HISTORY = re.compile(r"^\d[\d.]*[a-z]?\.\s*\((?:Enacted|Added|Amended|Repealed|Renumbered|Part|Division|Operative|Reserved)\b.*\)\.?$")


def _statute_paragraphs(body: str) -> list[str]:
    out = []
    for raw in re.split(r"\n\s*\n", body):
        par = _normal(raw)
        if not par or par.startswith("- ") or (len(par) < 400 and _HISTORY.match(par)):
            continue                                       # a metadata bullet, the section's history line
        out.append(par)
    return out


def seed_statutes(authorities_dir: Path, patterns: Iterable[SeedPattern] = SEED_PATTERNS) -> list[FormCandidate]:
    """The spans of the authorities shelf with request language. Each page is split at its "## CIV NNNN" headings; a
    section yields a span around each hit (its paragraph or paragraphs, never the page), with the section's canonical
    citation ("CIV 5210")."""
    patterns = tuple(patterns)
    out: list[FormCandidate] = []
    root = Path(authorities_dir)
    if not root.is_dir():
        return out
    for path in sorted(root.rglob("*.md")):
        parts = re.split(r"(?m)^## (.+?)\s*$", path.read_text(encoding="utf-8", errors="replace"))
        for heading, body in zip(parts[1::2], parts[2::2]):
            cited = statute_citation(heading)
            if cited is None:
                continue
            citation = cited.base
            for text, names in spans_in(_statute_paragraphs(body), patterns):
                out.append(FormCandidate(candidate_id(CandidateSource.STATUTE, citation, text), CandidateSource.STATUTE,
                                         citation, text, names))
    return out


def seed_documents(data_dir: Path, patterns: Iterable[SeedPattern] = SEED_PATTERNS, *, outlines: Iterable[Any] | None = None
                   ) -> list[FormCandidate]:
    """The spans of the community's governing documents, rules, and policies with request language, found over their
    section outlines (``data/outlines``; keyword patterns only, no embedder and no model). Each span names the document
    key and the section ("rules 4.2"); a part before the first section is "(no section)". An annexation is left out."""
    from jason.community.reference_model import passages

    patterns = tuple(patterns)
    if outlines is None:
        from jason.tasks.outlines import load

        outlines = load(Path(data_dir))
    out: list[FormCandidate] = []
    for outline in outlines:
        if getattr(outline, "kind", "") == "annexation":
            continue
        for passage in passages(outline, max_chars=200_000, min_chars=40):
            paragraphs = [_normal(line) for line in re.split(r"\n+", passage.text) if line.strip()]
            citation = f"{outline.key} {passage.section}" if passage.section else f"{outline.key} (no section)"
            for text, names in spans_in(paragraphs, patterns):
                out.append(FormCandidate(candidate_id(CandidateSource.DOCUMENT, citation, text), CandidateSource.DOCUMENT,
                                         citation, text, names))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# What a span is known as


def _same_section(a: Any, b: Any) -> bool:
    """Two statute citations name one section, or one a dotted section of the other ("CIV 4745" and "CIV 4745.1")."""
    if a is None or b is None or a.code != b.code:
        return False
    return a.number == b.number or a.number.startswith(b.number + ".") or b.number.startswith(a.number + ".")


def known_as(candidate: FormCandidate, community: Any = None) -> tuple[str, str]:
    """The request kind or notice-catalog row an existing part of jason already has for ``candidate``, with why; ("", "")
    when none.

    In order: a response rule (the general ones and the profile's) whose authority is the candidate's section; a notice
    catalog row whose statute is; then the first kind rule (the profile's, then the general ones) whose words match the
    span, for a kind a member's request can be (not a question, a complaint, or maintenance). A miss stays a miss."""
    from jason.community.notice_catalog import REQUIREMENTS
    from jason.community.responses import classify, rules_for

    kind_rules, by_kind = rules_for(community)
    if candidate.source is CandidateSource.STATUTE:
        mine = statute_citation(candidate.citation)
        for kind, rule in by_kind.items():
            if rule.authority and _same_section(mine, statute_citation(rule.authority)):
                return kind.value, f'a response rule for "{kind.value}" has authority {rule.authority}'
        for row in REQUIREMENTS:
            if _same_section(mine, statute_citation(row.statute)):
                return row.key, f"the notice catalog row {row.key} cites {row.statute}"
    kind, why = classify("", candidate.quote, kind_rules)
    if kind not in NOT_A_FORM_KIND:
        return kind.value, f'the span reads as "{kind.value}": {why}'
    return "", ""


# ---------------------------------------------------------------------------------------------------------------------
# Joining a statute with the documents that carry it out


_STOP = frozenset("""about above after again against also another because before being between board both cannot could
 document documents each either every first following from have having however include includes including interest
 member members must notice other owner owners person persons pursuant provided request requests requested section
 sections shall should subdivision such that their them then there these they this those through under unless upon
 which while whose will within without would written writing association associations common development days year
 years time where when what who whom association's""".split())


def top_terms(text: str, n: int = 8) -> dict[str, str]:
    """The ``n`` commonest meaningful words of ``text`` as stem (first five letters) -> a word that has it."""
    words = [w for w in re.findall(r"[a-z]{5,}", text.lower()) if w not in _STOP]
    stems: dict[str, str] = {}
    counts: Counter[str] = Counter()
    for w in words:
        stems.setdefault(w[:5], w)
        counts[w[:5]] += 1
    ranked = sorted(counts, key=lambda s: (-counts[s], s))[:n]
    return {s: stems[s] for s in ranked}


_NAMED = tuple((re.compile(rf"\b(?:{pattern})\s*(?:[Ss]ections?|§§?|[Ss]ecs?\.)?\s*(\d{{3,5}}(?:\.\d+)*)", re.I), code)
               for pattern, code in CODES)
_AFTER = tuple((re.compile(rf"\b[Ss]ections?\s+(\d{{3,5}}(?:\.\d+)*)\b[^.;]{{0,40}}?\bof\s+the\s+(?:{pattern})", re.I), code)
               for pattern, code in CODES)


def cited_sections(text: str) -> list[StatuteCitation]:
    """The statute sections ``text`` cites, as ``StatuteCitation``s: "CIV 5210", "Civil Code section 5210", "Section 5210
    of the Civil Code"."""
    found: dict[str, StatuteCitation] = {}
    for m in STATUTE_IN_TEXT.finditer(text):
        found.setdefault(f"{m.group('code')} {m.group('number')}", StatuteCitation(m.group("code"), m.group("number")))
    for rx, code in _NAMED:
        for m in rx.finditer(text):
            found.setdefault(f"{code} {m.group(1)}", StatuteCitation(code, m.group(1)))
    for rx, code in _AFTER:
        for m in rx.finditer(text):
            found.setdefault(f"{code} {m.group(1)}", StatuteCitation(code, m.group(1)))
    return list(found.values())


def _join(statute: FormCandidate, document: FormCandidate) -> Join | None:
    mine = statute_citation(statute.citation)
    for cite in cited_sections(document.quote):
        if _same_section(mine, cite):
            return Join(statute.id, document.id, JoinBasis.CITATION,
                        f"{document.citation} cites {cite.base}, the section {statute.citation} is on", 3.0)
    if statute.known_as and statute.known_as == document.known_as:
        return Join(statute.id, document.id, JoinBasis.KIND, f'both read as "{statute.known_as}"', 2.0)
    shared = sorted(set(top_terms(statute.quote)) & set(top_terms(document.quote)))
    if len(shared) >= 3:
        words = top_terms(statute.quote)
        return Join(statute.id, document.id, JoinBasis.TERMS,
                    "both turn on " + ", ".join(words[s] for s in shared), 1.0 + len(shared) / 100)
    return None


def group(candidates: list[FormCandidate]) -> tuple[list[FormCandidate], list[Join]]:
    """Group each document span with the one statute span it best goes with: a citation first, then the same kind of
    request, then shared subject words (three of each span's eight commonest). Returns the candidates with ``group`` set
    (``g-`` and the statute's id) and each join with its reason. A span with no join keeps no group. Modest on purpose:
    a join is a lead a person reads, never a finding."""
    statutes = [c for c in candidates if c.source is CandidateSource.STATUTE]
    joins: list[Join] = []
    for doc in (c for c in candidates if c.source is CandidateSource.DOCUMENT):
        best: Join | None = None
        for statute in statutes:
            found = _join(statute, doc)
            if found is not None and (best is None or found.strength > best.strength):
                best = found
        if best is not None:
            joins.append(best)
    gid = {j.document: "g-" + j.statute[3:] for j in joins}
    gid.update({j.statute: "g-" + j.statute[3:] for j in joins})
    return [c.with_(group=gid.get(c.id, "")) for c in candidates], joins


def annotate(candidates: list[FormCandidate], community: Any = None) -> tuple[list[FormCandidate], list[Join]]:
    """``known_as`` and then the groups, derived afresh from each candidate's words."""
    named = []
    for c in candidates:
        kind, why = known_as(c, community)
        named.append(c.with_(known_as=kind, known_why=why))
    return group(named)


# ---------------------------------------------------------------------------------------------------------------------
# Reading a span


class Reader(Protocol):
    """What reads a span: ``read(span_text, citation)`` gives a dict of the reading's fields (``READING_SCHEMA``)."""

    def read(self, span_text: str, citation: str) -> dict[str, Any]: ...


READING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "request": {"type": "boolean"},
        "who_submits": {"type": "string"},
        "to_whom": {"type": "string"},
        "what": {"type": "string"},
        "required_content": {"type": "array", "items": {"type": "string"}},
        "clocks": {"type": "array", "items": {"type": "object", "properties": {
            "for_whom": {"type": "string"}, "how_long": {"type": "string"}, "if_passes": {"type": "string"}},
            "required": ["for_whom", "how_long", "if_passes"]}},
        "decision": {"type": "object", "properties": {
            "who": {"type": "string"}, "in_writing": {"type": "boolean"}, "reasons": {"type": "boolean"},
            "reconsideration": {"type": "string"}}, "required": ["who", "in_writing", "reasons", "reconsideration"]},
        "authority": {"type": "string"},
        "quote": {"type": "string"},
    },
    "required": ["request", "who_submits", "to_whom", "what", "required_content", "clocks", "decision", "authority", "quote"],
}

READING_PROMPT = """You read one span of words from a statute, or from a governing document of a California common \
interest development (a declaration, bylaws, operating rules, or a board policy), and decide whether it creates a \
request that a member, owner, resident, or applicant makes of the association, its board, a committee, or its \
managing agent: an application, a written request, a registration, a reservation, a permit, an approval asked for \
first, or a hearing, appeal, or reconsideration asked for. A right the member holds and the body must honor on \
request counts. A duty the body performs without being asked, a definition, a penalty, or a general statement does not.

If the span creates no such request, answer request: false and leave every other field empty.

If it does, fill:
- who_submits: who makes the request, as the span names them.
- to_whom: the body or person who receives and decides it.
- what: the request, in the span's own words, briefly.
- required_content: what the span says the request or the form must carry (each item a phrase), or an empty list.
- clocks: each time limit the span states, as {for_whom, how_long, if_passes}: whose clock it is (the member's or the \
body's), how long as written, and what the span says happens if it passes ("deemed approved"), or "" if it says \
nothing. An empty list when the span states none.
- decision: who decides; whether the span says in writing, and whether with reasons; and, in the span's words, any \
reconsideration, appeal, or hearing after a denial, or "".
- authority: the citation given for the span below.
- quote: the operative words that create the request, copied exactly, character for character, from the span, four to \
thirty words. Never paraphrase a quote. An answer whose quote is not in the span is thrown away.

Use only what the span says. Where it is silent on a field, leave the field empty; never fill it from what such \
rules usually say."""


def reading_prompt(span_text: str, citation: str) -> str:
    return f"{READING_PROMPT}\n\nThe span, from {citation}:\n{span_text}"


class LocalModelReader:
    """Reads a span with the local model, through the duties reader's path (``jason.community.duty_model.DutyModel``): an
    Ollama on this machine, its preflight (``jason.local_ai``), and the GPU lock around each request. Built and run only
    by ``jason discover-forms --read``; a test passes a fake ``Reader`` instead. ``duty_model`` replaces the model's
    client (tests, and nothing else)."""

    def __init__(self, model: str = "", *, duty_model: Any = None) -> None:
        if duty_model is None:
            from jason.community.duty_model import DutyModel

            duty_model = DutyModel(model=model)
        self._model = duty_model

    @property
    def model(self) -> str:
        return str(self._model.model)

    def read(self, span_text: str, citation: str) -> dict[str, Any]:
        raw = self._model._ask(reading_prompt(span_text, citation), READING_SCHEMA)
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"_problem": "the model's answer is not JSON"}
        return data if isinstance(data, dict) else {"_problem": "the model's answer is not an object"}


def contains_quote(span_text: str, quote: str) -> bool:
    """Whether ``quote`` is in ``span_text`` word for word (whitespace is not compared)."""
    q = _normal(quote).strip()
    return bool(q) and q in _normal(span_text)


def _text(value: Any) -> str:
    return _normal(value) if isinstance(value, str) else ""


def parse_reading(raw: Any, span_text: str, source: CandidateSource, *, model: str = "", at: str = ""
                  ) -> tuple[CandidateReading | None, str]:
    """A reader's dict as a ``CandidateReading``, with the problem: ("", reading) when it stands. A reading whose quote
    is not in the span gives ``QUOTE_NOT_FOUND`` (the caller drops the candidate); anything else unusable gives its
    reason."""
    if not isinstance(raw, dict):
        return None, "the reader's answer is not an object"
    if raw.get("_problem"):
        return None, str(raw["_problem"])
    clock_source = ClockSource.STATUTE if source is CandidateSource.STATUTE else ClockSource.DOCUMENTS
    if raw.get("request") is False:
        return CandidateReading(False, model=model, read_at=at), ""
    quote = _text(raw.get("quote"))
    if not quote:
        return None, "the reading has no quote"
    if not contains_quote(span_text, quote):
        return None, QUOTE_NOT_FOUND
    content, clocks, decision = raw.get("required_content", []), raw.get("clocks", []), raw.get("decision")
    if not isinstance(content, list) or not isinstance(clocks, list) or not (decision is None or isinstance(decision, dict)):
        return None, "the reading's lists or decision are malformed"
    made = []
    for c in clocks:
        if not isinstance(c, dict):
            return None, "a clock is not an object"
        if _text(c.get("how_long")) or _text(c.get("for_whom")):
            made.append(Clock(_text(c.get("for_whom")), _text(c.get("how_long")), _text(c.get("if_passes")), clock_source))
    decided = (Decision(_text(decision.get("who")), bool(decision.get("in_writing")), bool(decision.get("reasons")),
                        _text(decision.get("reconsideration"))) if decision else None)
    return CandidateReading(True, _text(raw.get("who_submits")), _text(raw.get("to_whom")), _text(raw.get("what")),
                            tuple(t for t in (_text(x) for x in content) if t), tuple(made), decided,
                            _text(raw.get("authority")), quote, model, at), ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _noted(old: str, new: str) -> str:
    return new if not old else old if new in old else f"{old}; {new}"


def read_candidate(candidate: FormCandidate, reader: Reader, *, at: str = "") -> FormCandidate:
    """``candidate`` read by ``reader``. A reading that stands is kept. One whose quote is not in the span is dropped, and
    the candidate with it (status dropped, note "quote not found"); one that is unusable for another reason leaves the
    candidate as it was, with the reason in its note. A reader that finds no request in the span says so in the note and
    leaves the decision to a person."""
    at = at or _now()
    reading, problem = parse_reading(reader.read(candidate.quote, candidate.citation), candidate.quote, candidate.source,
                                     model=str(getattr(reader, "model", "")), at=at)
    if problem == QUOTE_NOT_FOUND:
        return candidate.with_(reading=None, status=CandidateStatus.DROPPED, note=_noted(candidate.note, QUOTE_NOT_FOUND))
    if reading is None:
        return candidate.with_(note=_noted(candidate.note, f"reading not usable: {problem}"))
    if not reading.is_request:
        return candidate.with_(reading=reading, note=_noted(candidate.note, "the reader found no request in this span"))
    return candidate.with_(reading=reading)


# ---------------------------------------------------------------------------------------------------------------------
# The store: data/forms/candidates.json and the log


def forms_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "forms"


def store_path(data_dir: Path) -> Path:
    return forms_dir(data_dir) / "candidates.json"


def acts_path(data_dir: Path) -> Path:
    return forms_dir(data_dir) / "candidate-acts.jsonl"


def _lock(profile: str = ""):
    from jason.locks import Resource, account, hold

    return hold(Resource.STORE, f"form-candidates-{profile or account()}", timeout=60, purpose="jason discover-forms")


def load(data_dir: Path) -> CandidateStore:
    path = store_path(data_dir)
    if not path.is_file():
        return CandidateStore()
    return CandidateStore.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _save(data_dir: Path, store: CandidateStore) -> None:
    path = store_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(store.to_dict(), indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def log_act(data_dir: Path, *, by: str, act: str, candidate: str = "", why: str = "", detail: str = "") -> dict[str, Any]:
    """Append one act: who, when, what, why (and the candidate it was about)."""
    entry = {"at": _now(), "by": by, "act": act, "candidate": candidate, "why": why, "detail": detail}
    path = acts_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def acts(data_dir: Path, candidate: str = "") -> list[dict[str, Any]]:
    path = acts_path(data_dir)
    if not path.is_file():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if not candidate or r.get("candidate") == candidate]


def merge_seed(old: list[FormCandidate], seeded: list[FormCandidate], scope: set[CandidateSource]) -> list[FormCandidate]:
    """The kept candidates after a seed. A seeded candidate already kept keeps its status, note, reading, and (a person's
    word) everything but its seeds; if its words changed the reading goes and the note says so. A kept candidate in
    ``scope`` the seed no longer finds is removed when nobody has looked at it (new, unread: the seed makes it again) and
    otherwise kept, noted. Candidates outside ``scope`` are not touched."""
    by_id = {c.id: c for c in old}
    seen: set[str] = set()
    out: list[FormCandidate] = []
    for c in seeded:
        if c.id in seen:
            continue
        seen.add(c.id)
        prior = by_id.get(c.id)
        if prior is None:
            out.append(c)
        elif prior.quote != c.quote:
            out.append(prior.with_(seeds=c.seeds, quote=c.quote, reading=None,
                                   note=_noted(prior.note, "the words changed since it was read")))
        else:
            out.append(prior.with_(seeds=c.seeds))
    for prior in old:
        if prior.id in seen:
            continue
        if prior.source in scope and prior.status is CandidateStatus.NEW and prior.reading is None:
            continue
        out.append(prior if prior.source not in scope else prior.with_(note=_noted(prior.note, "no longer in the latest seed")))
    return out


@dataclass(frozen=True)
class SeedResult:
    found: int
    added: int
    removed: int
    by_pattern: dict[str, int]
    total: int
    joins: int


def seed(data_dir: Path, *, source: str = "all", authorities_dir: Path | None = None, community: Any = None,
         patterns: Iterable[SeedPattern] = SEED_PATTERNS, outlines: Iterable[Any] | None = None, by: str = "jason"
         ) -> SeedResult:
    """Run the seeds (no model, no GPU), keep the candidates, and log it. ``source`` is "statutes", "documents", or "all"."""
    if source not in ("statutes", "documents", "all"):
        raise DiscoveryError("--source is statutes, documents, or all")
    patterns = tuple(patterns)
    scope = {CandidateSource.STATUTE: source in ("statutes", "all"), CandidateSource.DOCUMENT: source in ("documents", "all")}
    seeded: list[FormCandidate] = []
    if scope[CandidateSource.STATUTE]:
        seeded += seed_statutes(authorities_dir if authorities_dir is not None else Path(data_dir) / "authorities", patterns)
    if scope[CandidateSource.DOCUMENT]:
        seeded += seed_documents(data_dir, patterns, outlines=outlines)
    chosen = {s for s, on in scope.items() if on}
    with _lock():
        store = load(data_dir)
        before = {c.id for c in store.candidates}
        merged = merge_seed(store.candidates, seeded, chosen)
        store.candidates, store.joins = annotate(merged, community)
        store.seeded_at = _now()
        _save(data_dir, store)
        after = {c.id for c in store.candidates}
        found = len({c.id for c in seeded})
        log_act(data_dir, by=by, act="seed", why=f"source {source}",
                detail=f"{found} found, {len(after - before)} new, {len(before - after)} removed")
    counts: Counter[str] = Counter(name for c in seeded for name in c.seeds)
    return SeedResult(found, len(after - before), len(before - after), dict(counts), len(store.candidates), len(store.joins))


def read_new(data_dir: Path, reader: Reader, *, limit: int = 0, source: str = "all", by: str = "jason",
             progress=lambda line: None) -> list[tuple[str, str]]:
    """Read the new candidates that have no reading yet with ``reader``, up to ``limit`` (0: all). Each is saved as soon as it
    is read, and the store is held only while it is changed, never while the model works. Returns ``(id, outcome)`` per
    candidate: "read", "no request", "dropped (quote not found)", or "unusable: why"."""
    wanted = {"statutes": {CandidateSource.STATUTE}, "documents": {CandidateSource.DOCUMENT}}.get(
        source, {CandidateSource.STATUTE, CandidateSource.DOCUMENT})
    todo = [c.id for c in load(data_dir).candidates if c.status is CandidateStatus.NEW and c.reading is None and c.source in wanted]
    if limit:
        todo = todo[:limit]
    results: list[tuple[str, str]] = []
    for cid in todo:
        current = load(data_dir).get(cid)
        if current is None:
            continue
        read = read_candidate(current, reader)                       # the model works here, holding the GPU lock and no store
        with _lock():
            store = load(data_dir)
            if store.get(cid) is None:
                continue
            store.candidates = [read if c.id == cid else c for c in store.candidates]
            _save(data_dir, store)
            if read.status is CandidateStatus.DROPPED:
                outcome = f"dropped ({QUOTE_NOT_FOUND})"
            elif read.reading is None:
                outcome = "unusable: " + read.note.split("reading not usable: ")[-1]
            elif not read.reading.is_request:
                outcome = "no request"
            else:
                outcome = "read"
            log_act(data_dir, by=by, act="read", candidate=cid, detail=f"{outcome}; model {getattr(reader, 'model', '') or 'unknown'}")
        results.append((cid, outcome))
        progress(f"{cid} {outcome}")
    return results


_ACTS = {"confirm": CandidateStatus.CONFIRMED, "hold": CandidateStatus.HELD, "drop": CandidateStatus.DROPPED}


def decide(data_dir: Path, candidate_id: str, act: str, *, by: str, why: str = "") -> FormCandidate:
    """A person's act on one candidate: ``confirm``, ``hold`` (the law is silent on a clock the form needs, or the reading
    is open: for the board), or ``drop``. It names who (``by``), and why for hold and drop. It writes the candidate's
    status and the log and nothing else: no form, no procedure, no known-form row."""
    if act not in _ACTS:
        raise DiscoveryError(f"no act {act}")
    by, why = (by or "").strip(), (why or "").strip()
    if not by:
        raise DiscoveryError(f"--{act} needs --by NAME: a person's act is logged under a name")
    if act != "confirm" and not why:
        raise DiscoveryError(f"--{act} needs --why TEXT: the reason is kept with the act")
    with _lock():
        store = load(data_dir)
        found = store.get(candidate_id)
        if found is None:
            raise DiscoveryError(f"no candidate {candidate_id} (jason discover-forms --list)")
        status = _ACTS[act]
        if found.status is status:
            raise DiscoveryError(f"{candidate_id} is already {status.value}")
        changed = found.with_(status=status)
        store.candidates = [changed if c.id == candidate_id else c for c in store.candidates]
        _save(data_dir, store)
        log_act(data_dir, by=by, act=act, candidate=candidate_id, why=why, detail=f"{found.status.value} -> {status.value}")
    return changed


# ---------------------------------------------------------------------------------------------------------------------
# Looking


def select(candidates: Iterable[FormCandidate], *, status: str = "", source: str = "", known: bool | None = None
           ) -> list[FormCandidate]:
    want_source = {"statutes": CandidateSource.STATUTE, "documents": CandidateSource.DOCUMENT}.get(source)
    out = []
    for c in candidates:
        if status and c.status.value != status:
            continue
        if want_source is not None and c.source is not want_source:
            continue
        if known is not None and bool(c.known_as) != known:
            continue
        out.append(c)
    return out


def summary(store: CandidateStore) -> dict[str, Any]:
    cands = store.candidates
    return {"candidates": len(cands),
            "byStatus": {s.value: sum(1 for c in cands if c.status is s) for s in CandidateStatus},
            "bySource": {s.value: sum(1 for c in cands if c.source is s) for s in CandidateSource},
            "known": sum(1 for c in cands if c.known_as), "unknown": sum(1 for c in cands if not c.known_as),
            "read": sum(1 for c in cands if c.reading is not None), "unread": sum(1 for c in cands if c.reading is None),
            "groups": len({c.group for c in cands if c.group}), "seededAt": store.seeded_at}


def brief(c: FormCandidate, width: int = 90) -> str:
    """One line: id, status, source, citation, what it is known as, its group, and the start of its words."""
    first = _normal(c.quote)
    first = first if len(first) <= width else first[:width].rsplit(" ", 1)[0] + " ..."
    tail = (f"  known as: {c.known_as}" if c.known_as else "") + (f"  group {c.group}" if c.group else "")
    return f'{c.id}  {c.status.value:9} {c.source.value:8} {c.citation}{tail}  "{first}"'


def _reading_lines(r: CandidateReading, indent: str = "") -> list[str]:
    if not r.is_request:
        return [f"{indent}The reader found no request in this span (model {r.model or 'unknown'})."]
    out = [f"{indent}Who submits: {r.who_submits or '-'}; to whom: {r.to_whom or '-'}",
           f"{indent}What: {r.what or '-'}"]
    if r.required_content:
        out.append(f"{indent}Required content: " + "; ".join(r.required_content))
    for c in r.clocks:
        out.append(f"{indent}Clock ({c.source.value}), for {c.for_whom or 'unstated'}: {c.how_long or '-'}"
                   + (f"; if it passes: {c.if_passes}" if c.if_passes else ""))
    if r.decision:
        d = r.decision
        bits = [f"decided by {d.who or 'unstated'}", "in writing" if d.in_writing else "writing not stated",
                "with reasons" if d.reasons else "reasons not stated"]
        out.append(f"{indent}Decision: " + ", ".join(bits) + (f"; reconsideration: {d.reconsideration}" if d.reconsideration else ""))
    if r.authority:
        out.append(f"{indent}Authority the reader named: {r.authority}")
    out.append(f'{indent}Quote the reader chose (found in the span): "{r.quote}"')
    return out


def candidate_lines(c: FormCandidate, joins: Iterable[Join] = ()) -> list[str]:
    """One candidate for a person: the quote first, then the reading (labeled), then what is known about it."""
    out = [f"{c.citation} [{c.source.value}] {c.id}  status: {c.status.value}"]
    out += ["> " + line for line in c.quote.splitlines()]
    out.append(f"Seeds: {', '.join(c.seeds)}")
    if c.known_as:
        out.append(f"Known as: {c.known_as} ({c.known_why})")
    for j in joins:
        if c.id in (j.statute, j.document):
            other = j.document if c.id == j.statute else j.statute
            out.append(f"Joined with {other} ({j.basis.value}): {j.reason}")
    if c.reading is not None:
        out.append(f"A reading for a person (model {c.reading.model or 'unknown'}, {c.reading.read_at or 'unknown time'}); "
                   "it is a lead, never the rule:")
        out += _reading_lines(c.reading, "  ")
    if c.note:
        out.append(f"Note: {c.note}")
    return out


def report(candidates: Iterable[FormCandidate], joins: Iterable[Join] = ()) -> str:
    """Markdown for a person: each group (a statute and the document sections that carry it out), then the statutes and
    the documents with no group. Each candidate shows its quote first, then the reading under the label "A reading for a
    person", then its status."""
    cands, joins = list(candidates), list(joins)
    groups: dict[str, list[FormCandidate]] = {}
    for c in cands:
        if c.group:
            groups.setdefault(c.group, []).append(c)

    def block(c: FormCandidate) -> list[str]:
        lines = [f"### {c.citation}: {c.status.value}" + (f" (known as {c.known_as})" if c.known_as else ""), "",
                 f"`{c.id}`, {c.source.value}; seeded by {', '.join(c.seeds)}.", ""]
        lines += ["> " + line for line in c.quote.splitlines()]
        lines.append("")
        for j in joins:
            if j.document == c.id:
                lines += [f"Joined with the statute `{j.statute}` ({j.basis.value}): {j.reason}.", ""]
        if c.known_as:
            lines += [f"Known as {c.known_as}: {c.known_why}.", ""]
        if c.reading is not None:
            lines += [f"**A reading for a person** (model {c.reading.model or 'unknown'}): a lead to check against the quote, never "
                      "the rule.", ""]
            lines += ["- " + line.strip() for line in _reading_lines(c.reading)]
            lines.append("")
        if c.note:
            lines += [f"Note: {c.note}", ""]
        lines.append(f"**Status: {c.status.value}.**")
        lines.append("")
        return lines

    out = ["# Form candidates", "",
           f"{len(cands)} candidate(s). A candidate is a span of the law or the documents that may create a request a "
           "standard form could take. Each shows the words first; a reading is labeled and is a lead. Confirming one makes "
           "no form: that is a person's next step.", ""]
    if groups:
        out += ["## Groups: a statute and the document sections that carry it out", ""]
        for gid, members in sorted(groups.items()):
            members.sort(key=lambda c: (c.source is not CandidateSource.STATUTE, c.citation))
            out += [f"## Group `{gid}`", ""]
            for c in members:
                out += block(c)
    for title, source in (("## Statutes with no group", CandidateSource.STATUTE),
                          ("## Documents with no group", CandidateSource.DOCUMENT)):
        rest = [c for c in cands if not c.group and c.source is source]
        if rest:
            out += [title, ""]
            for c in rest:
                out += block(c)
    if not cands:
        out.append("None kept: `jason discover-forms --seed` runs the seeds.")
    return "\n".join(out).rstrip() + "\n"


__all__ = ["DiscoveryError", "LocalModelReader", "MAX_SPAN", "QUOTE_NOT_FOUND", "READING_SCHEMA", "Reader", "SEED_PATTERNS",
           "SeedPattern", "SeedResult", "acts", "annotate", "brief", "candidate_id", "candidate_lines", "cited_sections",
           "contains_quote", "decide", "group", "known_as", "load", "log_act", "merge_seed", "parse_reading", "read_candidate",
           "read_new", "report", "reading_prompt", "seed", "seed_documents", "seed_statutes", "select", "spans_in",
           "store_path", "summary", "top_terms"]
