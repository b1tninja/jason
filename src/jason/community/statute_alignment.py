"""Which provision of one version of a statute continues which provision of another: a structure-aware aligner.

The question it answers is the one a reader of an old citation asks: is this current provision the same rule
renumbered or reworded, or a changed rule, or something new? It answers in three layers.

**Units.** A section is split into its top-level subdivisions ("(a)", "(b)", with everything nested inside them), the
words before "(a)" as ``(intro)``, and a section with no subdivisions as one unit (``subdivisions``).

**Candidates.** A former unit is compared only with the current units the structure places near it: the headings
(article or chapter) its own heading corresponds to, read from the official disposition rows of *other* sections
(leave-one-section-out, so the gold never answers for itself) and from the headings' own words, plus the top few
current units by lexical (and, when an embedder is given, embedding) similarity anywhere in the act (``candidates``).

**Judgment.** The local model reads one former unit beside its section's candidates and names, for each candidate
that carries its rule forward, how: without substantive change, with changes (and which change, in a phrase), a
generalization, or superseded. Every answer carries a verbatim quote from each side; a match counts only when both
quotes are found in the texts (``verify``). A miss stays a miss: a former unit with no verified match is
``not_continued``, and a current unit nothing continues is ``new``. A model reading is evidence, never a pin.

Lexical and embedding baselines answer the same question by similarity alone, so ``evaluate`` can score every
variant on the same pairs against the Law Revision Commission's disposition table and Comments.
"""

from __future__ import annotations

import json
import math
import re
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Sequence


class Relation(Enum):
    CONTINUED_WITHOUT_SUBSTANTIVE_CHANGE = "continued_without_substantive_change"   # same effect: renumbered, reworded
    CONTINUED_WITH_CHANGES = "continued_with_changes"                               # a deadline, amount, right, or condition changed
    GENERALIZED = "generalized"                                                     # the rule now reaches more cases
    SUPERSEDED = "superseded"                                                       # replaced by a different rule on the same matter
    NOT_CONTINUED = "not_continued"                                                 # a former unit nothing continues
    NEW = "new"                                                                     # a current unit nothing continues


# What the model may answer for a match (the last two are conclusions over all matches, not answers).
MATCH_RELATIONS = (Relation.CONTINUED_WITHOUT_SUBSTANTIVE_CHANGE, Relation.CONTINUED_WITH_CHANGES, Relation.GENERALIZED,
                   Relation.SUPERSEDED)


class Shape(Enum):
    ONE_TO_ONE = "one_to_one"
    SPLIT = "split"                         # one former unit continued in several current sections
    COMBINED = "combined"                   # several former units continued in one current section
    SPLIT_AND_COMBINED = "split_and_combined"


class Variant(Enum):
    STRUCTURE = "structure"                 # every candidate the structure offers (the candidate set's own precision and recall)
    LEXICAL = "lexical"                     # the best TF-IDF candidate above a fixed floor
    EMBEDDING = "embedding"                 # the best embedding candidate above a fixed floor
    LLM = "llm"                             # the model's verified matches


# ---------------------------------------------------------------- units


@dataclass(frozen=True)
class Unit:
    section: str            # "1363"
    label: str              # "(g)", "(intro)", or "" for a section with no subdivisions
    text: str
    group: str = ""         # the finest heading the section sits under (article, else chapter)
    session: str = ""

    @property
    def id(self) -> str:
        return f"{self.section}{self.label}"


_LABEL = re.compile(r"^\(([a-z]{1,2})\)\s*")
_ROMAN = {"i", "v", "x", "ii", "iv", "vi", "ix", "xi"}


def _next_letter(letter: str) -> str:
    if letter == "z":
        return "aa"
    if len(letter) == 2 and letter[0] == letter[1]:
        return chr(ord(letter[0]) + 1) * 2
    return chr(ord(letter) + 1)


def paragraphs(text: str) -> list[str]:
    """The text's paragraphs (split at blank lines), each with its spacing made one space."""
    return [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n[ \t\r\f\v]*\n", text or "") if p.strip()]


def subdivisions(section: str, text: str, *, group: str = "", session: str = "") -> tuple[Unit, ...]:
    """The section's top-level subdivisions in order. A lowercase label opens a new one only when it is the next
    letter (one or two may be skipped where a subdivision was repealed, but never to a roman numeral), so "(i)" under
    "(A)" stays inside its subdivision. The words before "(a)" are ``(intro)``; a section without "(a)" is one unit."""
    units: list[Unit] = []
    label, buf, expected = "", [], "a"

    def flush() -> None:
        body = "\n\n".join(buf).strip()
        if body and (label or len(body) >= 20):
            units.append(Unit(section, f"({label})" if label else "(intro)", body, group, session))

    for p in paragraphs(text):
        m = _LABEL.match(p)
        if m:
            got = m.group(1)
            skip = [expected, _next_letter(expected), _next_letter(_next_letter(expected))] if label else ["a"]
            if got in skip and (got == expected or got not in _ROMAN):
                flush()
                label, buf, expected = got, [], _next_letter(got)
        buf.append(p)
    if not label:
        body = "\n\n".join(paragraphs(text))
        return (Unit(section, "", body, group, session),) if body else ()
    flush()
    return tuple(units)


def strip_label(text: str) -> str:
    return _LABEL.sub("", text, count=1).strip()


# ---------------------------------------------------------------- lexical similarity

_STOP = set("""a an the of to in on for by with from as at or and be is are was were been being that this these those
which who whom whose any all each such shall may must not no if than then there their its it his her he she they them
under upon into within without other provided pursuant section sections subdivision subdivisions paragraph title
chapter article code civil part division""".split())


def tokens(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z]+", (text or "").lower()):
        if len(w) < 3 or w in _STOP:
            continue
        for suffix in ("ing", "ed", "es", "s"):
            if len(w) > len(suffix) + 3 and w.endswith(suffix):
                w = w[: -len(suffix)]
                break
        out.append(w)
    return out


class Tfidf:
    """TF-IDF vectors over a corpus of unit texts (section numbers and cross-reference digits left out)."""

    def __init__(self, texts: Iterable[str]) -> None:
        docs = [set(tokens(t)) for t in texts]
        n = max(1, len(docs))
        df = Counter(w for d in docs for w in d)
        self.idf = {w: math.log((1 + n) / (1 + c)) + 1 for w, c in df.items()}

    def vector(self, text: str) -> dict[str, float]:
        tf = Counter(tokens(text))
        v = {w: (1 + math.log(c)) * self.idf.get(w, 1.0) for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / norm for w, x in v.items()}


def cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(w, 0.0) for w, x in a.items())


def dense_cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    return sum(x * y for x, y in zip(a, b))


# ---------------------------------------------------------------- structure


def _heading_words(heading: str) -> set[str]:
    heading = re.sub(r"\[[^\]]*\]", " ", heading)
    heading = re.sub(r"^\s*(?:ARTICLE|CHAPTER|PART|TITLE|DIVISION)\s+[\dA-Z.]+\s*", " ", heading, flags=re.I)
    return set(tokens(heading))


@dataclass
class StructureMap:
    """Former heading -> current headings, each with how it was found ("gold" counts from other sections' official
    rows, "outline" from the headings' words and the groups' text)."""

    groups: dict[str, list[tuple[str, float, str]]] = field(default_factory=dict)

    def targets(self, group: str) -> list[str]:
        return [g for g, _, _ in self.groups.get(group, [])]


def structure_map(former: Sequence[Unit], current: Sequence[Unit], tfidf: Tfidf, *,
                  gold_pairs: Iterable[tuple[str, str]] = (), exclude_section: str = "",
                  gold_top: int = 4, outline_top: int = 3) -> StructureMap:
    """The heading correspondence. ``gold_pairs`` are (former section, current section) rows; those of
    ``exclude_section`` are left out, so a section's own rows never shape its candidates."""
    former_group = {u.section: u.group for u in former}
    current_group = {u.section: u.group for u in current}
    counts: dict[str, Counter] = defaultdict(Counter)
    for f, c in gold_pairs:
        if f == exclude_section or f not in former_group or c not in current_group:
            continue
        counts[former_group[f]][current_group[c]] += 1
    text_f: dict[str, list[str]] = defaultdict(list)
    text_c: dict[str, list[str]] = defaultdict(list)
    for u in former:
        text_f[u.group].append(u.text)
    for u in current:
        text_c[u.group].append(u.text)
    vec_c = {g: tfidf.vector(g + " " + " ".join(t)) for g, t in text_c.items()}
    out = StructureMap()
    for g, texts in text_f.items():
        rows: dict[str, tuple[float, str]] = {}
        for cg, n in counts[g].most_common(gold_top):
            rows[cg] = (float(n), "gold")
        vf = tfidf.vector(g + " " + " ".join(texts))
        words = _heading_words(g)
        scored = []
        for cg, vc in vec_c.items():
            hw = _heading_words(cg)
            jac = len(words & hw) / len(words | hw) if words | hw else 0.0
            scored.append((cosine(vf, vc) + 0.5 * jac, cg))
        for s, cg in sorted(scored, reverse=True)[:outline_top]:
            rows.setdefault(cg, (round(s, 4), "outline"))
        out.groups[g] = [(cg, s, how) for cg, (s, how) in rows.items()]
    return out


@dataclass
class CandidateSet:
    """A former section's candidates (shared by its units, so one prompt prefix serves them all), with each unit's
    own lexical and embedding scores against every candidate and where each candidate came from."""

    former: tuple[Unit, ...]
    candidates: tuple[Unit, ...]
    lexical: dict[str, dict[str, float]]           # former unit id -> candidate id -> cosine
    dense: dict[str, dict[str, float]]
    origin: dict[str, str]                          # candidate id -> "structure" | "lexical" | "embedding"


def candidates(former: Sequence[Unit], current: Sequence[Unit], tfidf: Tfidf, smap: StructureMap, *,
               vectors: dict[str, list[float]] | None = None, top_k: int = 5, cap: int = 80) -> CandidateSet:
    """The current units a former section's units are judged against: every unit in the headings the structure maps
    its headings to, plus each unit's top ``top_k`` anywhere by lexical (and embedding) similarity; at most ``cap``,
    the ones least like any former unit dropped first."""
    vf = {u.id: tfidf.vector(u.text) for u in former}
    vc = {u.id: tfidf.vector(u.text) for u in current}
    lexical = {f: {c: cosine(v, vc[c]) for c in vc} for f, v in vf.items()}
    dense: dict[str, dict[str, float]] = {}
    if vectors:
        dense = {f.id: {c.id: dense_cosine(vectors.get(f.id, []), vectors.get(c.id, [])) for c in current} for f in former}
    origin: dict[str, str] = {}
    groups = {g for u in former for g in smap.targets(u.group)}
    for c in current:
        if c.group in groups:
            origin[c.id] = "structure"
    for f in former:
        for c, _ in sorted(lexical[f.id].items(), key=lambda kv: -kv[1])[:top_k]:
            origin.setdefault(c, "lexical")
        if dense:
            for c, _ in sorted(dense[f.id].items(), key=lambda kv: -kv[1])[:top_k]:
                origin.setdefault(c, "embedding")
    best = {c: max(lexical[f][c] for f in lexical) if lexical else 0.0 for c in origin}
    kept = sorted(origin, key=lambda c: -best[c])[:cap]
    by_id = {c.id: c for c in current}
    ordered = tuple(sorted((by_id[c] for c in kept), key=lambda u: (_num(u.section), u.label)))
    keep = {u.id for u in ordered}
    return CandidateSet(tuple(former), ordered,
                        {f: {c: s for c, s in row.items() if c in keep} for f, row in lexical.items()},
                        {f: {c: s for c, s in row.items() if c in keep} for f, row in dense.items()},
                        {c: origin[c] for c in keep})


def _num(section: str) -> tuple[float, ...]:
    try:
        return tuple(float(p) for p in section.split("."))
    except ValueError:
        return (0.0,)


# ---------------------------------------------------------------- matches


@dataclass
class Match:
    former: str                         # former unit id, "1363(g)"
    current: str                        # current unit id, "5855(a)"
    relation: str                       # a Relation value
    method: str                         # "llm", "lexical", "embedding", "identical"
    score: float = 0.0
    former_quote: str = ""
    current_quote: str = ""
    change: str = ""                    # the substantive change in a phrase, kept only when its quotes are found
    change_former: str = ""
    change_current: str = ""
    change_verified: bool = False
    confidence: str = ""                # "high", "medium", "low"
    source: str = "model"               # a model's or a rule's reading: a lead, never a pin

    @property
    def former_section(self) -> str:
        return _section_of(self.former)

    @property
    def current_section(self) -> str:
        return _section_of(self.current)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _section_of(unit_id: str) -> str:
    return re.sub(r"\(.*$", "", unit_id).strip()


def _label_of(unit_id: str) -> str:
    m = re.search(r"\(([^)]*)\)", unit_id)
    return m.group(1) if m else ""


def similarity_matches(cs: CandidateSet, *, method: str, floor: float, near: float = 0.85) -> list[Match]:
    """The baseline: each former unit's best candidate when it clears ``floor``, and any other nearly as close (a
    split): within ``near`` of the best's margin over the floor, since embedding similarities crowd near the top. Similarity says nothing about substance, so the relation is a guess from closeness alone."""
    table = cs.lexical if method == "lexical" else cs.dense
    out: list[Match] = []
    for f in cs.former:
        row = sorted(table.get(f.id, {}).items(), key=lambda kv: -kv[1])
        if not row or row[0][1] < floor:
            continue
        top = row[0][1]
        for c, s in row:
            if s < floor + near * (top - floor):          # within ``near`` of the best, measured above the floor
                break
            rel = Relation.CONTINUED_WITHOUT_SUBSTANTIVE_CHANGE if s >= 0.85 else Relation.CONTINUED_WITH_CHANGES
            out.append(Match(f.id, c, rel.value, method, round(s, 4), source=method))
    return out


def structure_matches(cs: CandidateSet) -> list[Match]:
    """Every structure candidate, as if each continued every former unit: the candidate set's ceiling and floor."""
    return [Match(f.id, c.id, Relation.CONTINUED_WITH_CHANGES.value, "structure", source="structure")
            for f in cs.former for c in cs.candidates if cs.origin.get(c.id) == "structure"]


# ---------------------------------------------------------------- the model judge

PROMPT = """You compare two versions of a California statute to find where each provision of the earlier version went.

The candidates below are provisions of the {current_edition}. After them is one provision of the {former_edition}.
Name every candidate that carries forward all or part of the earlier provision's rule (the same duty, right,
definition, deadline, or condition, even if renumbered or reworded). Do not name a candidate that only concerns a
related topic. If none carries it forward, answer with an empty list.

For each candidate you name, give:
- "candidate": its id exactly as shown.
- "relation": "continued_without_substantive_change" when it has the same legal effect (renumbered, reworded,
  reorganized; new section numbers in cross-references, defined terms used in place of longer phrases, a
  provision moved to another section, and changes of style or grammar are not substantive);
  "continued_with_changes" when the rule continues but something of substance changed (a deadline,
  an amount, who must act, a right or duty added or removed, a condition added or removed); "generalized" when the
  rule now reaches more cases than before; "superseded" when a different rule now governs the same matter.
- "former_quote" and "current_quote": 5 to 25 words copied exactly from each text showing the same rule.
- For "continued_with_changes" only: "change", a short phrase naming the substantive change (for example
  "notice period 15 days -> 14 days"), with "change_former" and "change_current" the exact words that differ on
  each side (leave one empty when words were only added or only removed). Otherwise leave these three empty.

Copy quotes character for character; do not paraphrase inside a quote.

CANDIDATES ({current_edition}):
{candidates}

EARLIER PROVISION ({former_edition}) {former_id}:
<<<
{former_text}
>>>"""


def answer_schema(ids: Sequence[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"matches": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "candidate": {"type": "string", "enum": list(ids)},
                "relation": {"type": "string", "enum": [r.value for r in MATCH_RELATIONS]},
                "former_quote": {"type": "string"},
                "current_quote": {"type": "string"},
                "change": {"type": "string"},
                "change_former": {"type": "string"},
                "change_current": {"type": "string"},
            },
            "required": ["candidate", "relation", "former_quote", "current_quote", "change", "change_former", "change_current"],
        }}},
        "required": ["matches"],
    }


def build_prompt(unit: Unit, cands: Sequence[Unit], *, former_edition: str, current_edition: str,
                 max_candidate_chars: int = 900, max_former_chars: int = 6000) -> str:
    """Candidates first, the former unit last, so consecutive prompts for one section share their prefix."""
    lines = []
    for c in cands:
        body = c.text if len(c.text) <= max_candidate_chars else c.text[:max_candidate_chars].rsplit(" ", 1)[0] + " ..."
        lines.append(f"[{c.id}] {body}")
    return PROMPT.format(current_edition=current_edition, former_edition=former_edition, candidates="\n\n".join(lines),
                         former_id=unit.id, former_text=unit.text[:max_former_chars])


def _fold(text: str) -> str:
    text = (text or "").translate(str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " ",
                                                "�": "'"}))
    return re.sub(r"\s+", " ", text).strip().casefold()


def quote_found(quote: str, text: str, *, min_words: int = 3) -> bool:
    """The quote occurs in the text, compared without regard to case, spacing, or quotation-mark and dash style; a
    quote joined with an ellipsis must have each piece in the text. Shorter than ``min_words`` words never counts."""
    q = _fold(quote).strip(" \"'")
    if len(q.split()) < min_words:
        return False
    body = _fold(text)
    pieces = [p.strip(" \"'") for p in re.split(r"\s*(?:\.\.\.|…)\s*", q) if p.strip(" \"'")]
    return bool(pieces) and all(p in body for p in pieces)


def _side_found(quote: str, text: str) -> bool:
    return not quote.strip() or quote_found(quote, text, min_words=1)


def parse_answer(raw: str) -> tuple[list[dict[str, str]], str]:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return [], "the model did not answer in JSON"
    items = data.get("matches") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return [], "the answer has no list of matches"
    keys = ("candidate", "relation", "former_quote", "current_quote", "change", "change_former", "change_current")
    return [{k: str(i.get(k) or "").strip() for k in keys} for i in items if isinstance(i, dict)], ""


def verify(unit: Unit, proposals: Sequence[dict[str, str]], by_id: dict[str, Unit], cs: CandidateSet | None = None) \
        -> tuple[list[Match], list[dict[str, Any]]]:
    """The proposals whose quotes are found on both sides, as matches; the rest, with why they were set aside."""
    kept: list[Match] = []
    dropped: list[dict[str, Any]] = []
    seen: set[str] = set()
    valid = {r.value for r in MATCH_RELATIONS}
    lex = sorted((cs.lexical.get(unit.id) or {}).items(), key=lambda kv: -kv[1]) if cs else []
    top3 = {c for c, _ in lex[:3]}
    for p in proposals:
        cand = by_id.get(p["candidate"])
        why = ""
        if cand is None:
            why = "not a candidate"
        elif p["candidate"] in seen:
            why = "named twice"
        elif p["relation"] not in valid:
            why = "unknown relation"
        elif not quote_found(p["former_quote"], unit.text):
            why = "former quote not found"
        elif not quote_found(p["current_quote"], cand.text):
            why = "current quote not found"
        if why:
            dropped.append({**p, "former": unit.id, "why": why})
            continue
        seen.add(cand.id)
        m = Match(unit.id, cand.id, p["relation"], "llm", former_quote=p["former_quote"], current_quote=p["current_quote"])
        if p["relation"] == Relation.CONTINUED_WITH_CHANGES.value and p["change"]:
            ok = (p["change_former"] or p["change_current"]) and _side_found(p["change_former"], unit.text) \
                and _side_found(p["change_current"], cand.text)
            m.change_verified = bool(ok)
            if ok:
                m.change, m.change_former, m.change_current = p["change"], p["change_former"], p["change_current"]
        if cs is not None:
            m.score = round((cs.lexical.get(unit.id) or {}).get(cand.id, 0.0), 4)
            placed = cs.origin.get(cand.id) == "structure" or cand.id in top3
            m.confidence = "high" if placed else "medium"
        else:
            m.confidence = "medium"
        if p["relation"] == Relation.CONTINUED_WITH_CHANGES.value and not m.change_verified:
            m.confidence = "low" if m.confidence == "medium" else "medium"
        kept.append(m)
    return kept, dropped


class OllamaJudge:
    """The shared local model through Ollama, thinking off, temperature 0, answering to a JSON schema.

    ``post(url, payload)`` replaces HTTP in tests. Unset, the first call runs ``jason.local_ai.preflight`` and each
    request goes through ``ollama_extractor._post``, which holds jason's GPU lock for its length (another jason
    process's request is waited for, up to ``timeout``)."""

    def __init__(self, *, model: str = "", base_url: str = "", post: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
                 timeout: int = 1800, keep_alive: str = "5m") -> None:
        from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL

        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")
        self.num_ctx = DEFAULT_CONTEXT
        self._post = post
        self.timeout = timeout
        self.keep_alive = keep_alive
        self._checked = post is not None

    def preflight(self) -> None:
        if self._checked:
            return
        from jason.local_ai import preflight

        preflight(self.model, ollama_url=self.base_url)
        self._checked = True

    def ask(self, prompt: str, schema: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """The raw answer and Ollama's timings for it."""
        self.preflight()
        payload = {"model": self.model, "stream": False, "think": False, "format": schema, "keep_alive": self.keep_alive,
                   "options": {"temperature": 0, "num_ctx": self.num_ctx},
                   "messages": [{"role": "user", "content": prompt}]}
        if self._post is not None:
            data = self._post(f"{self.base_url}/api/chat", payload)
        else:
            from jason.community.ollama_extractor import _post

            data = _post(f"{self.base_url}/api/chat", payload, self.timeout)
        meta = {k: data.get(k) for k in ("prompt_eval_count", "eval_count", "total_duration", "prompt_eval_duration", "eval_duration")
                if isinstance(data, dict) and data.get(k) is not None}
        return str(((data or {}).get("message") or {}).get("content") or ""), meta


def judge_section(cs: CandidateSet, judge: OllamaJudge, *, former_edition: str, current_edition: str,
                  skip: Callable[[Unit], bool] | None = None) -> dict[str, Any]:
    """Ask the model about each former unit of one section against the section's candidates; verified matches only."""
    by_id = {c.id: c for c in cs.candidates}
    ids = [c.id for c in cs.candidates]
    schema = answer_schema(ids)
    matches: list[Match] = []
    dropped: list[dict[str, Any]] = []
    requests: list[dict[str, Any]] = []
    errors: list[str] = []
    for unit in cs.former:
        if skip and skip(unit):
            continue
        prompt = build_prompt(unit, cs.candidates, former_edition=former_edition, current_edition=current_edition)
        started = time.monotonic()
        raw, meta = judge.ask(prompt, schema)
        seconds = round(time.monotonic() - started, 2)
        proposals, error = parse_answer(raw)
        if error:
            errors.append(f"{unit.id}: {error}")
        kept, gone = verify(unit, proposals, by_id, cs)
        matches += kept
        dropped += gone
        requests.append({"unit": unit.id, "seconds": seconds, "candidates": len(ids), "proposed": len(proposals),
                         "kept": len(kept), **meta})
    return {"matches": matches, "dropped": dropped, "requests": requests, "errors": errors}


# ---------------------------------------------------------------- conclusions over matches


def shapes(matches: Sequence[Match]) -> dict[str, str]:
    """Each former unit's shape from all its matches: split when it went to several current sections, combined when
    a current section it went to also continues another former section, both, or one to one."""
    to: dict[str, set[str]] = defaultdict(set)
    into: dict[str, set[str]] = defaultdict(set)
    for m in matches:
        to[m.former].add(m.current_section)
        into[m.current_section].add(m.former_section)
    out: dict[str, str] = {}
    for f, targets in to.items():
        split = len(targets) > 1
        combined = any(len(into[t] - {_section_of(f)}) > 0 for t in targets)
        out[f] = (Shape.SPLIT_AND_COMBINED if split and combined else Shape.SPLIT if split else
                  Shape.COMBINED if combined else Shape.ONE_TO_ONE).value
    return out


def per_former(units: Sequence[Unit], matches: Sequence[Match]) -> list[dict[str, Any]]:
    """Each former unit: where it went, how, and the change; ``not_continued`` when nothing verified continues it."""
    shape = shapes(matches)
    by: dict[str, list[Match]] = defaultdict(list)
    for m in matches:
        by[m.former].append(m)
    rows = []
    for u in units:
        ms = by.get(u.id, [])
        rows.append({"former": u.id, "relation": _overall(ms), "shape": shape.get(u.id, ""),
                     "targets": [m.to_dict() for m in ms]})
    return rows


def per_current(units: Sequence[Unit], matches: Sequence[Match]) -> list[dict[str, Any]]:
    """Each current section: its predecessors with relation and substantive change, or ``new`` when nothing
    verified continues into any of its units (a miss stays a miss: ``new`` means no reading found one)."""
    by: dict[str, list[Match]] = defaultdict(list)
    for m in matches:
        by[m.current_section].append(m)
    out = []
    for section in dict.fromkeys(u.section for u in units):
        ms = by.get(section, [])
        out.append({
            "section": section,
            "relation": _overall(ms, empty=Relation.NEW),
            "predecessors": [{"former": m.former, "current": m.current, "relation": m.relation, "change": m.change,
                              "change_former": m.change_former, "change_current": m.change_current,
                              "confidence": m.confidence, "source": m.source} for m in ms],
            "changes": sorted({m.change for m in ms if m.change}),
        })
    return out


_RANK = {Relation.CONTINUED_WITH_CHANGES.value: 3, Relation.SUPERSEDED.value: 2, Relation.GENERALIZED.value: 1,
         Relation.CONTINUED_WITHOUT_SUBSTANTIVE_CHANGE.value: 0}


def _overall(ms: Sequence[Match], empty: Relation = Relation.NOT_CONTINUED) -> str:
    """The strongest change among the matches: a section with one changed part is a changed section."""
    if not ms:
        return empty.value
    return max((m.relation for m in ms), key=lambda r: _RANK.get(r, 0))


# ---------------------------------------------------------------- the gold


def gold_unit_labels(part: str) -> list[str]:
    """The top-level labels a disposition row's former part names: "(e)(1)-(2)" -> ["(e)"], "(a)-(c)" ->
    ["(a)", "(b)", "(c)"], "(intro. cl.)" -> ["(intro)"], "" -> [""] (the whole section); [] when no label reads."""
    part = (part or "").strip()
    if not part:
        return [""]
    if part.lower().startswith("(intro"):
        return ["(intro)"]
    m = re.match(r"^\(([a-z]{1,2})\)(?:-\(([a-z]{1,2})\))?", part)
    if not m:
        return []
    first, last = m.group(1), m.group(2)
    if not last:
        return [f"({first})"]
    out, at = [], first
    for _ in range(30):
        out.append(f"({at})")
        if at == last:
            break
        at = _next_letter(at)
    return out


@dataclass
class Gold:
    section_pairs: set[tuple[str, str]] = field(default_factory=set)            # (former section, current section)
    unit_pairs: set[tuple[str, str]] = field(default_factory=set)               # (former unit id, current section)
    target_labels: dict[tuple[str, str], set[str]] = field(default_factory=dict)  # (former unit, current section) -> labels
    omitted_units: set[str] = field(default_factory=set)
    omitted_sections: set[str] = field(default_factory=set)
    sections: set[str] = field(default_factory=set)
    unit_sections: set[str] = field(default_factory=set)        # sections whose rows read at the unit level
    relation: dict[tuple[str, str], str] = field(default_factory=dict)          # Comment's class per (former unit, current section)
    unread_parts: list[str] = field(default_factory=list)


COMMENT_CLASS = {"continued_without_change": Relation.CONTINUED_WITHOUT_SUBSTANTIVE_CHANGE.value,
                 "continued_without_substantive_change": Relation.CONTINUED_WITHOUT_SUBSTANTIVE_CHANGE.value,
                 "continued_with_changes": Relation.CONTINUED_WITH_CHANGES.value,
                 "generalized": Relation.GENERALIZED.value}


def read_gold(former_doc: dict[str, Any], units: Sequence[Unit], *, act: str = "davis-stirling") -> Gold:
    """The disposition table's rows (and the Comments' change classes) at section and unit level."""
    have = {u.id for u in units}
    by_section: dict[str, list[Unit]] = defaultdict(list)
    for u in units:
        by_section[u.section].append(u)
    g = Gold()
    targets_of: dict[str, set[str]] = defaultdict(set)
    for sec in former_doc.get("sections") or []:
        for row in sec.get("rows") or []:
            if row.get("act") != act:
                continue
            former = row.get("former") or {}
            number = str(former.get("section") or "")
            source = row.get("source")
            labels = gold_unit_labels(str(former.get("part") or ""))
            if labels == [""] and len(by_section.get(number, [])) == 1 and by_section[number][0].label == "":
                labels = [number]
            else:
                labels = [number + lab for lab in labels if lab]
            targets = [(str(t.get("section") or ""), gold_unit_labels(str(t.get("part") or ""))) for t in row.get("targets") or []]
            if source == "disposition_table":
                g.sections.add(number)
                for t, _ in targets:
                    g.section_pairs.add((number, t))
                    targets_of[number].add(t)
                if former.get("part") and not labels:
                    g.unread_parts.append(str(former.get("citation")))
                for lab in labels:
                    if lab not in have:
                        g.unread_parts.append(f"{former.get('citation')} (no unit {lab})")
                        continue
                    g.unit_sections.add(number)
                    if not targets:
                        g.omitted_units.add(lab)
                    for t, tl in targets:
                        g.unit_pairs.add((lab, t))
                        if tl and tl != [""]:
                            g.target_labels.setdefault((lab, t), set()).update(tl)
            elif source == "commission_comment":
                cls = COMMENT_CLASS.get(str(row.get("succession") or ""))
                if cls:
                    for lab in labels:
                        for t, _ in targets:
                            g.relation.setdefault((lab, t), cls)
    # A section the table places whole in one current section: each of its units went there.
    for number, units_here in by_section.items():
        if number in g.sections and number not in g.unit_sections and len(targets_of.get(number, ())) == 1                 and all(u.label for u in units_here):
            (t,) = targets_of[number]
            g.unit_sections.add(number)
            g.unit_pairs.update((u.id, t) for u in units_here)
    g.omitted_units -= {f for f, _ in g.unit_pairs}
    g.omitted_sections = {s for s in g.sections if not targets_of.get(s)}
    return g


def _prf(predicted: set, gold: set) -> dict[str, Any]:
    tp = len(predicted & gold)
    p = tp / len(predicted) if predicted else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"tp": tp, "predicted": len(predicted), "gold": len(gold), "precision": round(p, 3), "recall": round(r, 3), "f1": round(f, 3)}


def evaluate(matches: Sequence[Match], gold: Gold, sections: Iterable[str], *, current_scope: Iterable[str] = ()) -> dict[str, Any]:
    """Precision and recall against the disposition table over ``sections`` (former), at section level and at unit
    level (only where the table reads at a unit), the current subdivision where the table names one, the omitted
    units left unmatched, the change class against the Comments, and ``new`` where the scope is the whole act."""
    scope = set(sections)
    pred_sec = {(m.former_section, m.current_section) for m in matches if m.former_section in scope}
    gold_sec = {p for p in gold.section_pairs if p[0] in scope}
    unit_scope = scope & gold.unit_sections
    gold_units = {p for p in gold.unit_pairs if _section_of(p[0]) in unit_scope}
    labelled_units = {f for f, _ in gold_units} | {u for u in gold.omitted_units if _section_of(u) in unit_scope}
    pred_units = {(m.former, m.current_section) for m in matches if m.former in labelled_units}
    out: dict[str, Any] = {"section": _prf(pred_sec, gold_sec), "unit": _prf(pred_units, gold_units)}
    # The current subdivision, where the table names one and the pair was found.
    hit = total = 0
    for (f, t), labels in gold.target_labels.items():
        if _section_of(f) not in unit_scope or (f, t) not in pred_units:
            continue
        total += 1
        got = {"(" + _label_of(m.current) + ")" for m in matches if m.former == f and m.current_section == t}
        hit += bool(got & labels)
    out["current_subdivision"] = {"named_by_table": total, "matched": hit}
    omitted = {u for u in gold.omitted_units if _section_of(u) in unit_scope}
    matched_formers = {m.former for m in matches}
    out["omitted_units"] = {"gold": len(omitted), "left_unmatched": len(omitted - matched_formers)}
    # The change class (without substantive change / with changes / generalized) against the Comments.
    confusion: Counter = Counter()
    for m in matches:
        cls = gold.relation.get((m.former, m.current_section))
        if cls and (m.former, m.current_section) in gold_units:
            confusion[(cls, m.relation)] += 1
    agree = sum(n for (g_, p_), n in confusion.items() if g_ == p_)
    total_c = sum(confusion.values())
    # The class that matters most is the minority one: a change a reader must not mistake for a renumbering.
    changed = Relation.CONTINUED_WITH_CHANGES.value
    tp_c = confusion.get((changed, changed), 0)
    said = sum(n for (_, p_), n in confusion.items() if p_ == changed)
    real = sum(n for (g_, _), n in confusion.items() if g_ == changed)
    out["relation"] = {"compared": total_c, "agree": agree, "accuracy": round(agree / total_c, 3) if total_c else None,
                       "with_changes": {"gold": real, "said": said, "both": tp_c,
                                        "precision": round(tp_c / said, 3) if said else None,
                                        "recall": round(tp_c / real, 3) if real else None},
                       "confusion": {f"{g_} -> {p_}": n for (g_, p_), n in sorted(confusion.items())}}
    cur = set(current_scope)
    if cur:
        gold_new = cur - {t for _, t in gold.section_pairs}
        pred_new = cur - {m.current_section for m in matches}
        out["new"] = _prf(pred_new, gold_new)
    return out


__all__ = ["Relation", "Shape", "Variant", "Unit", "subdivisions", "paragraphs", "strip_label", "Tfidf", "tokens", "cosine",
           "StructureMap", "structure_map", "CandidateSet", "candidates", "Match", "similarity_matches",
           "structure_matches", "answer_schema", "build_prompt", "quote_found", "parse_answer", "verify", "OllamaJudge",
           "judge_section", "shapes", "per_former", "per_current", "gold_unit_labels", "Gold", "read_gold", "evaluate"]
