"""A preliminary analysis of what kind of document a file is, before ingest decides how to read it.

The library's chain classifies by the first rule that matches: a person's answer, then the name and folder rules, then
the phrase rules, then a model. A first match is fast and usually right, but it never weighs the alternatives. A file
named "... Agreement.pdf" is a contract by its name even when its words are a lender's assignment between strangers.
This analysis weighs them, so the readers that follow fit the document:

1. **Every phrase rule votes.** All of ``content.CONTENT_RULES`` are tried, not just the first that matches: a title
   rule counts more than a body rule, and more phrases count more.
2. **Shape.** ``SIGNALS`` rows read the document's structure: a parties clause, a signature block, an e-signature
   certificate, a recorder's stamp, a meeting's motions, a letter's salutation, a form's blanks, many amounts, numbered
   sections. Each row supports the kinds that look like that. A new signal is a new row.
3. **The kind's own reader.** ``document_models`` reads the text as each leading candidate. A model that recognizes the
   text and finds its required fields is evidence for that kind; one that finds none of them is evidence against it.
4. **Parties.** For an agreement, whether the association is a party at all (its name, or "Association" defined as a
   party). A contract between others is a third party's instrument, filed with the matter it concerns, not an
   association contract.

The verdict never changes a kind on its own: a person's answer stands; a kind the chain gave and the analysis agrees with
is **confirmed**; one it disagrees with is a **question** for a person, with the evidence; a file with no kind gets a
**proposal** for the CLASSIFY question, not a kind. A miss stays a miss until a person answers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from jason.community.content import CONTENT_RULES, TITLE, _hits, body_of
from jason.community.symbols import DocumentKind as K


class Verdict(Enum):
    CONFIRMED = "confirmed"          # the chain's kind, and the evidence agrees
    PERSON = "person"                # a person chose it; not weighed again
    DISAGREES = "disagrees"          # the evidence favors another kind: a question for a person
    WEAK = "weak"                    # the chain's kind, but little in the text supports it: a question for a person
    PROPOSED = "proposed"            # no kind from the chain; the evidence suggests one
    UNKNOWN = "unknown"              # no kind, and no kind stands out


@dataclass(frozen=True)
class Signal:
    key: str
    about: str
    pattern: str
    kinds: tuple[K, ...]
    min_hits: int = 1
    weight: float = 1.0


_AGREEMENTS = (K.CONTRACT, K.PROPOSAL, K.SETTLEMENT, K.LEASE, K.SECURITY_AGREEMENT, K.SUBSIDY_AGREEMENT)
_GOVERNING = (K.DECLARATION, K.AMENDMENT, K.ANNEXATION, K.BYLAWS, K.ARTICLES, K.POLICY, K.OPERATING_RULES,
              K.ELECTION_RULES, K.RESOLUTION)

# Rows, read over the document's own words. Order does not matter: every row that holds adds its weight.
SIGNALS: tuple[Signal, ...] = (
    Signal("parties-clause", "names its parties (\"by and between\", \"hereinafter\")",
           r"by\s+and\s+between|\bhereinafter\b|is\s+made\s+and\s+entered\s+into|\(the\s+[\"“][A-Z]", _AGREEMENTS, weight=1.5),
    Signal("signature-block", "ends in signature lines",
           r"in\s+witness\s+whereof|accepted\s+and\s+agreed|\bBy:\s*_{3,}|signature:\s*_{0,}\s*\n|authorized\s+signature",
           _AGREEMENTS + (K.FORM, K.RESOLUTION)),
    Signal("e-signature", "carries an e-signature envelope or audit report",
           r"docusign\s+envelope|final\s+audit\s+report|certificate\s+of\s+completion|adobe\s+(?:acrobat\s+)?sign|pandadoc",
           _AGREEMENTS),
    Signal("term-and-termination", "speaks of its own term, renewal, or termination",
           r"term\s+of\s+this\s+agreement|automatically\s+renew|terminat\w*\s+this\s+agreement|this\s+agreement\s+may\s+be\s+terminated",
           (K.CONTRACT, K.LEASE, K.SECURITY_AGREEMENT, K.SUBSIDY_AGREEMENT), weight=1.5),
    Signal("offer", "offers a price for acceptance",
           r"valid\s+for\s+\d+\s+days|this\s+(?:proposal|quote|estimate)\s+(?:is|expires)|scope\s+of\s+work|"
           r"we\s+propose|price\s+includes", (K.PROPOSAL,)),
    Signal("recorder-stamp", "opens with a county recorder's stamp",
           r"recording\s+requested\s+by|when\s+recorded\s+(?:mail|return)|recorded\s+in\s+official\s+records",
           (K.DECLARATION, K.AMENDMENT, K.ANNEXATION, K.GRANT_DEED, K.RECORDED_LIEN), weight=1.5),
    Signal("meeting-acts", "records motions and votes",
           r"\bmotion\b|\bseconded\b|\bcarried\b|called\s+to\s+order|\badjourned\b", (K.MINUTES, K.EXECUTIVE_SESSION),
           min_hits=3, weight=1.5),
    Signal("letter", "is a letter (a salutation and a closing)",
           r"(?m)^\s*dear\b|\bsincerely,|very\s+truly\s+yours|\bRe:\s", (K.CORRESPONDENCE, K.LEGAL_CORRESPONDENCE, K.NOTICE,
                                                                       K.VIOLATION_NOTICE, K.DELINQUENCY_NOTICE),
           min_hits=2),
    Signal("form-blanks", "has many blanks to fill", r"_{5,}", (K.FORM, K.BALLOT), min_hits=6),
    Signal("amounts", "lists many dollar amounts", r"\$\s?\d", (K.INVOICE, K.PROPOSAL, K.BUDGET, K.FINANCIAL_STATEMENT,
                                                               K.BANK_STATEMENT, K.TREASURER_REPORT, K.OWNER_STATEMENT),
           min_hits=8),
    Signal("numbered-sections", "is organized in numbered sections",
           r"(?m)^\s*(?:\d{1,2}\.\d{1,2}|ARTICLE\s+[IVXLC\d]+|Section\s+\d+)\b", _AGREEMENTS + _GOVERNING, min_hits=6, weight=0.5),
    Signal("covenants", "binds owners and the land (\"Owner shall\", \"runs with the land\")",
           r"runs?\s+with\s+the\s+land|each\s+owner\s+shall|no\s+owner\s+shall|\bdeclarant\b|binding\s+upon\s+all\s+owners",
           _GOVERNING, min_hits=2),
)
_SIGNAL_RE = [(s, re.compile(s.pattern, re.I)) for s in SIGNALS]
WEAK_SCORE = 2.5                     # below this, the chain's kind is a question, not a confirmation

# What an agreement between others most likely is, by its words: rows, in order, each with where it belongs. An
# owner's rental papers (a property manager hired to lease the unit, a lease) go with the unit's owner and leasing
# records; a lender's papers with the same owner's file.
THIRD_PARTY: tuple[tuple[str, str, str], ...] = (
    ("lease", r"\blandlord\b.{0,400}\btenant\b|\btenant\b.{0,400}\blandlord\b|residential\s+lease|rental\s+agreement",
     "a lease of a unit: an owner's rental record (the unit's leasing record)"),
    ("property-management", r"(?:rent|lease),?\s+(?:lease|rent),?\s+(?:operate|and\s+manage)|property\s+management\s+agreement|"
                            r"\bbroker\b.{0,200}\bmanage",
     "an owner's property-management papers for a rental: the unit's owner file and leasing record"),
    ("loan", r"\bborrower\b|\blender\b|loan\s+agreement|deed\s+of\s+trust|\bmortgag(?:e|or|ee)\b",
     "a lender's or a loan's papers: the owner's file, if it concerns a unit here"),
)
_THIRD_PARTY = [(key, re.compile(p, re.I | re.S), where) for key, p, where in THIRD_PARTY]


def third_party_kind(text: str) -> list[tuple[str, str]]:
    """The kinds of third-party paper the words suggest, in the rows' order, with where each belongs."""
    return [(key, where) for key, rx, where in _THIRD_PARTY if rx.search(text or "")]


@dataclass(frozen=True)
class Candidate:
    kind: str
    score: float
    reasons: tuple[str, ...]


@dataclass
class KindAnalysis:
    classified: str                  # the chain's kind ("" for none)
    method: str                      # how the chain got it (``library.Method`` name)
    verdict: Verdict
    kind: str                        # what the readers should read it as ("" when unknown)
    candidates: list[Candidate]
    signals: list[str]
    notes: list[str] = field(default_factory=list)

    @property
    def suggestion(self) -> str:
        """The leading candidate, unless the one thing the analysis knows is that the file is not what it looks like
        (an agreement the association is not a party to): then no suggestion."""
        if any("not named as a party" in n for n in self.notes):
            return ""
        if self.verdict is Verdict.WEAK:
            # The chain's own weak kind is not a suggestion; another kind is, if one leads.
            return next((c.kind for c in self.candidates if c.kind != self.classified and c.score >= 3.0), "")
        return self.candidates[0].kind if self.candidates else ""

    def as_dict(self) -> dict[str, Any]:
        return {"classified": self.classified, "method": self.method, "verdict": self.verdict.value, "kind": self.kind,
                "suggestion": self.suggestion,
                "candidates": [{"kind": c.kind, "score": round(c.score, 2), "reasons": list(c.reasons)}
                               for c in self.candidates[:5]],
                "signals": list(self.signals), "notes": list(self.notes)}


def _rule_votes(body: str) -> dict[str, list[tuple[float, str]]]:
    votes: dict[str, list[tuple[float, str]]] = {}
    for rule in CONTENT_RULES:
        window = body[: rule.window]
        if rule.requires and len(_hits(window, rule.requires)) < len(rule.requires):
            continue
        found = _hits(window, rule.phrases)
        if len(found) < rule.min_hits:
            continue
        title = rule.window <= TITLE
        weight = (3.0 if title else 1.0) + 0.5 * (len(found) - rule.min_hits)
        where = "title" if title else "text"
        votes.setdefault(rule.kind.value, []).append(
            (weight, f"{where} phrase{'s' if len(found) > 1 else ''} " + ", ".join(f'"{p.strip()}"' for p in found[:3])))
    # A kind counts its best rule, plus a little for each other rule that also holds.
    return votes


def signals_of(text: str) -> list[tuple[Signal, int]]:
    out = []
    for sig, rx in _SIGNAL_RE:
        n = len(rx.findall(text))
        if n >= sig.min_hits:
            out.append((sig, n))
    return out


def association_is_party(text: str, community: Any = None) -> bool | None:
    """Whether the association is named as a party in the agreement's opening pages: its name, its corporate name, or
    "Association", "HOA", "Client" defined as a party. None when the text is too short to say."""
    from jason.community.contract_terms import prepare

    prepared = prepare(text)                     # the same unwrap and parties the contract reader uses, made once
    head = prepared.body[:20_000]
    if len(head) < 400:
        return None
    folded = head.casefold()
    for name in (getattr(community, "name", "") or "", getattr(community, "corporate_name", "") or ""):
        words = [w for w in re.findall(r"[a-z0-9]+", name.casefold()) if w not in ("the", "inc", "a")]
        if words and " ".join(words[:2]) in " ".join(re.findall(r"[a-z0-9]+", folded)):
            return True
    parties = prepared.parties
    if any(re.search(r"association|hoa|client|customer", term, re.I) for term in parties.names):
        return True
    return bool(re.search(r"\b(?:homeowners|owners|community)\s+association\b|\bthe\s+association\b", head, re.I))


def analyze(name: str, text: str, *, classified: str = "", method: str = "", confidence: float | None = None,
            community: Any = None, data_dir: Any = None, today: Any = None, recognize: int = 4) -> KindAnalysis:
    """Weigh the kinds a file could be. ``classified``/``method``/``confidence`` are the chain's answer."""
    from jason.community import document_models as dm

    body = body_of(text or "")
    if method == "PERSON":
        return KindAnalysis(classified, method, Verdict.PERSON, classified, [Candidate(classified, 99.0, ("a person's answer",))],
                            [])
    scores: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}

    def add(kind: str, weight: float, why: str) -> None:
        scores[kind] = scores.get(kind, 0.0) + weight
        reasons.setdefault(kind, []).append(why)

    for kind, votes in _rule_votes(body).items():
        votes.sort(reverse=True)
        add(kind, votes[0][0] + 0.25 * (len(votes) - 1), votes[0][1])
    found = signals_of(text or "")
    for sig, n in found:
        for kind in sig.kinds:
            add(kind.value, sig.weight, sig.about)
    if classified:
        prior = {"NAME": 2.0, "CONTENT": 1.5, "AGENDA": 2.0, "MODEL": 3.0 * float(confidence or 0.5)}.get(method, 1.0)
        add(classified, prior, f"the {method.lower() or 'chain'}'s kind")
    # The kind's own reader, for the leading candidates and the chain's kind.
    ranked = sorted(scores, key=lambda k: -scores[k])
    probe = list(dict.fromkeys(([classified] if classified else []) + ranked[:recognize]))
    context = dm.ModelContext(community=community, data_dir=data_dir, name=name, **({"today": today} if today else {}))
    for kind in probe:
        try:
            dk = K(kind)
            reading = dm.read(dk, text or "", context)
        except Exception:  # noqa: BLE001 - a reader that cannot read this text says nothing about it
            reading = None
        required = max((len(m.required) for m in dm.models_for(dk)), default=0) if kind in K._value2member_map_ else 0
        if reading is None:
            if required:
                add(kind, -0.5, f"its {kind} reader does not recognize the text")
            continue
        missing = len(reading.missing)
        if required and missing >= required:
            add(kind, -1.0, f"its {kind} reader ({reading.model}) finds none of the fields a {kind} carries")
        elif required:
            add(kind, 2.0 * (1 - missing / required), f"its {kind} reader ({reading.model}) finds "
                f"{required - missing} of {required} fields")
    notes: list[str] = []
    top = sorted(scores, key=lambda k: -scores[k])
    agreement_like = (classified in {k.value for k in _AGREEMENTS}) or (top and top[0] in {k.value for k in _AGREEMENTS})
    if agreement_like:
        party = association_is_party(text or "", community)
        if party is False:
            kinds = third_party_kind(text or "")
            what = "; ".join(where for _, where in kinds) if kinds else "file it with the matter it concerns"
            notes.append("the association is not named as a party: an instrument between others, not an association "
                         f"contract. It reads as {what}" if kinds else
                         f"the association is not named as a party: an instrument between others; {what}, not as an "
                         "association contract")
            for k in _AGREEMENTS:
                if k.value in scores:
                    add(k.value, -3.0, "the association is not a party")
    candidates = [Candidate(k, scores[k], tuple(reasons[k])) for k in sorted(scores, key=lambda k: -scores[k])]
    candidates = [c for c in candidates if c.score > 0]
    best = candidates[0] if candidates else None
    if classified:
        mine = next((c for c in candidates if c.kind == classified), None)
        margin = (best.score - (mine.score if mine else 0.0)) if best else 0.0
        # Strong evidence for another kind: its title phrase, or its own reader finding every field it looks for.
        strong = best is not None and any(r.startswith("title phrase") or re.search(r"finds (\d+) of \1 fields", r)
                                           for r in best.reasons)
        if best is None or best.kind == classified or margin < (1.0 if strong else 2.0):
            verdict, kind = Verdict.CONFIRMED, classified
            # Only a phrase rule's or a model's kind can be weak: a name or folder rule is the profile's deliberate
            # choice, and a short text says too little to doubt anything.
            if method in ("CONTENT", "MODEL") and len(body) >= 400 and (mine.score if mine else 0.0) < WEAK_SCORE:
                verdict = Verdict.WEAK
                notes.append(f"little in the text supports {classified} ({mine.score if mine else 0:.1f}): its "
                             f"{classified} reader " + ("does not recognize it" if mine is None or not any(
                                 "finds" in r for r in mine.reasons) else "finds few of its fields"))
        else:
            verdict, kind = Verdict.DISAGREES, classified
            notes.append(f"the text reads more like {best.kind} ({best.score:.1f}) than {classified} "
                         f"({mine.score if mine else 0:.1f})")
        if mine is None and notes and verdict is Verdict.CONFIRMED:
            verdict = Verdict.DISAGREES
    elif best is not None and best.score >= 3.0:
        verdict, kind = Verdict.PROPOSED, best.kind
    else:
        verdict, kind = Verdict.UNKNOWN, ""
    if classified and any("not named as a party" in n for n in notes) and verdict in (Verdict.CONFIRMED, Verdict.WEAK):
        verdict = Verdict.DISAGREES
    return KindAnalysis(classified, method, verdict, kind, candidates, [s.key for s, _ in found], notes)


__all__ = ["Verdict", "Signal", "SIGNALS", "Candidate", "KindAnalysis", "analyze", "signals_of", "association_is_party"]
