"""Copies of a governing document's sections embedded in other documents, found by their words.

The owner's manual restates a declaration section, a policy binds in a statutory notice, a notice quotes the leasing
cap. Each such copy goes stale when an amendment changes the section. This module finds them: every version of every
section (the current words, the words an amendment replaced, and a draft's proposed words) is read as one stream of
its letters and digits, with the spaces and punctuation dropped, and cut into overlapping runs of ``RUN`` characters.
A host document's runs are looked up against them, and a cluster of shared runs is a copy. How much of the section it
covers and how faithfully it reads say whether it is verbatim, near-verbatim, or an excerpt; which version shares the
most runs with it says whether it is current or stale.

The stream is what makes OCR noise on both sides tolerable: a scan read as "Notmore than" or "re- quired" has the same
letters as the Doc, and a misread letter breaks only the runs across it, so the copy reads as near-verbatim rather
than verbatim. A run shared by more than ``COMMON`` sections is boilerplate ("oftheassociationshall") and is not
counted. A paraphrase shares few runs; ``paraphrases`` finds those by a paragraph's rare words instead, and a
paraphrase is a lead to read, never a finding by itself.

Nothing here decides what to do about a copy: ``jason.tasks.section_refs`` says who owns the host and what may be
done (a token in jason's own sources, a finding for an adopted rule's next revision, nothing for a recorded instrument).
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

RUN = 30                    # characters (letters and digits) in a run: about six words
STRIDE = 3                  # a host is looked up every STRIDE characters; any shared stretch of RUN + STRIDE is seen
COMMON = 3                  # a run in more sections than this is boilerplate
GAP = 200                   # characters between shared runs before a cluster ends
MIN_SHARED = 60             # characters a cluster must share (about twelve words)
MIN_CHARS = 60              # a section version shorter than this is not looked for (a caption, a lead-in)
EXCERPT_CHARS = 120         # characters shared that make a partial copy an excerpt (about twenty-five words)
EXCERPT_COVERAGE = 0.1      # an excerpt holds at least this share of its section: less is a phrase in common (a
                            # notary's acknowledgment that a base read by OCR runs into its last section)


class Version(Enum):
    CURRENT = "current"              # the words in force now
    SUPERSEDED = "superseded"        # words an amendment in effect has replaced (or removed)
    PENDING = "pending"              # a draft's proposed words, not in effect


class CopyKind(Enum):
    VERBATIM = "verbatim"            # the whole section, word for word
    NEAR_VERBATIM = "near-verbatim"  # the whole section, a few words differ (OCR, a typo, an edit)
    EXCERPT = "excerpt"              # part of the section, word for word or nearly
    PARAPHRASE = "paraphrase"        # the section's rare words in a paragraph of other words: a lead


class Currency(Enum):
    CURRENT = "current"              # reads as the words in force
    STALE = "stale"                  # reads as words an amendment replaced or removed
    DRAFT = "draft"                  # reads as a draft amendment's proposed words
    UNAMENDED = "unamended"          # the section has never been amended: nothing to be stale against
    UNDECIDED = "undecided"          # the copy does not reach the words the amendment changed


@dataclass(frozen=True)
class SectionVersion:
    key: str                         # the document ("ccrs")
    number: str                      # "4.2(b)"
    caption: str
    words: str                       # the section's own words (not its subsections')
    version: Version
    label: str = ""                  # who set these words: "base", an instrument key, "<key> (draft)"
    removed: bool = False            # the current version: an amendment removed the section


_NOT_ALNUM = re.compile(r"[^a-z0-9]+")
_WORD = re.compile(r"[A-Za-z0-9]+(?:-[ \t]*\r?\n[ \t]*[a-z]+)?")


def stream(text: str) -> str:
    """The letters and digits of ``text``, lowercased, nothing else."""
    return _NOT_ALNUM.sub("", (text or "").lower())


def offsets(text: str) -> list[int]:
    """Each stream character's offset in ``text``."""
    lower = (text or "").lower()
    return [m.start() for m in re.finditer(r"[a-z0-9]", lower)]


def words_of(text: str) -> list[tuple[str, int, int]]:
    """The words of ``text``, lowercased, with their offsets; a word broken across a line ("re-\\nquired") is one."""
    return [(re.sub(r"-\s*", "", m.group(0)).lower(), m.start(), m.end()) for m in _WORD.finditer(text or "")]


def _plain(text: str) -> list[str]:
    return [w for w, _, _ in words_of(text)]


@dataclass
class Index:
    """Every version's runs, and which versions share each run."""

    versions: list[SectionVersion] = field(default_factory=list)
    runs: dict[str, list[tuple[int, int]]] = field(default_factory=dict)
    sets: list[set[str]] = field(default_factory=list)      # each version's runs
    streams: list[str] = field(default_factory=list)        # each version's stream
    total: list[int] = field(default_factory=list)          # runs per version

    @classmethod
    def build(cls, versions: Iterable[SectionVersion]) -> Index:
        out = cls()
        owners: dict[str, set[tuple[str, str]]] = defaultdict(set)
        raw: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for v in versions:
            s = stream(v.words)
            if len(s) < MIN_CHARS:
                continue
            vid = len(out.versions)
            out.versions.append(v)
            runs = [s[i:i + RUN] for i in range(len(s) - RUN + 1)]
            out.sets.append(set(runs))
            out.streams.append(s)
            out.total.append(max(1, len(runs)))
            for i, run in enumerate(runs):
                owners[run].add((v.key, v.number))
                raw[run].append((vid, i))
        out.runs = {run: hits for run, hits in raw.items() if len(owners[run]) <= COMMON}
        return out


@dataclass
class Copy:
    """One section's words found in a host, at ``start``..``end`` of the host's text."""

    host: str
    start: int
    end: int
    key: str
    number: str
    caption: str
    kind: CopyKind
    currency: Currency
    coverage: float                  # how much of the section the copy holds (0 to 1)
    fidelity: float                  # how much of the copy is the section's words (0 to 1)
    matched: str                     # the version it reads as: "current", or the label of what set the old words
    excerpt: str = ""                # the copy's first words
    words: int = 0                   # the copy's length in words
    versions: dict[str, int] = field(default_factory=dict)    # runs shared with each version, by label
    also: list[str] = field(default_factory=list)              # other sections with the same words here

    @property
    def target(self) -> str:
        return f"{self.key}#{self.number}"

    @property
    def similarity(self) -> float:
        return round((self.coverage + self.fidelity) / 2, 3)

    def as_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["kind"], raw["currency"] = self.kind.value, self.currency.value
        raw["target"], raw["similarity"] = self.target, self.similarity
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Copy:
        fields = {k: v for k, v in raw.items() if k not in ("target", "similarity")}
        fields["kind"], fields["currency"] = CopyKind(fields["kind"]), Currency(fields["currency"])
        return cls(**fields)


def _clusters(points: list[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    points.sort()
    out: list[list[tuple[int, int]]] = []
    for p in points:
        if out and p[0] - out[-1][-1][0] <= GAP:
            out[-1].append(p)
        else:
            out.append([p])
    return out


def _aligned(cluster: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """The points of a cluster that lie on stretches of shared text: neighbours that advance together in the host and
    the section (a run of copied words). A lone shared run at a cluster's edge ("shall be parked, kept or permitted")
    is dropped, so a copy starts and ends where the copied words do."""
    keep: list[tuple[int, int]] = []
    segment: list[tuple[int, int]] = []
    for p in cluster:
        if segment and p[0] - segment[-1][0] <= RUN and abs((p[0] - segment[-1][0]) - (p[1] - segment[-1][1])) <= RUN:
            segment.append(p)
            continue
        if len(segment) >= 2:
            keep += segment
        segment = [p]
    if len(segment) >= 2:
        keep += segment
    return keep


def _label(v: SectionVersion) -> str:
    return "current" if v.version is Version.CURRENT else (v.label or v.version.value)


def shared_runs(text: str, index: Index) -> set[str]:
    """The indexed runs ``text`` holds (looked up every ``STRIDE`` characters): for counting how many documents carry
    a run, since a run in many unrelated documents is boilerplate (a notary's acknowledgment the base text carries)."""
    s = stream(text)
    runs = index.runs
    return {s[i:i + RUN] for i in range(0, len(s) - RUN + 1, STRIDE) if s[i:i + RUN] in runs}


def without(index: Index, runs: Iterable[str]) -> Index:
    """The index less ``runs`` (a copy: the versions and their run sets are shared)."""
    drop = set(runs)
    return Index(versions=index.versions, runs={r: h for r, h in index.runs.items() if r not in drop},
                 sets=index.sets, streams=index.streams, total=index.total)


def find(host: str, text: str, index: Index) -> list[Copy]:
    """The copies of indexed sections in ``text``: one per section and place."""
    s = stream(text)
    runs = index.runs
    hits: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for i in range(0, len(s) - RUN + 1, STRIDE):
        found = runs.get(s[i:i + RUN])
        if found:
            for vid, pos in found:
                hits[vid].append((i, pos))
    if not hits:
        return []
    spans: dict[tuple[str, str], list[tuple[int, int, int, list[tuple[int, int]]]]] = defaultdict(list)
    for vid, points in hits.items():
        for cluster in _clusters(points):
            cluster = _aligned(cluster)
            if len({i for i, _ in cluster}) * STRIDE < MIN_SHARED:
                continue
            v = index.versions[vid]
            spans[(v.key, v.number)].append((cluster[0][0], cluster[-1][0] + RUN, vid, cluster))
    if not spans:
        return []
    where = offsets(text)
    out: list[Copy] = []
    for found in spans.values():
        found.sort()
        groups: list[list[tuple[int, int, int, list[tuple[int, int]]]]] = []
        for item in found:
            if groups and item[0] < max(g[1] for g in groups[-1]):
                groups[-1].append(item)
            else:
                groups.append([item])
        for group in groups:
            copy = _copy(host, text, s, where, index, group)
            if copy is not None:
                out.append(copy)
    return _merge(sorted(out, key=lambda c: (c.start, c.key, c.number)))


def _merge(copies: list[Copy]) -> list[Copy]:
    """One copy for one place: sections of the same document whose words are the same there (a document that
    repeats a paragraph under two numbers) are one copy, the others named in ``also``."""
    out: list[Copy] = []
    for c in copies:
        twin = next((o for o in out if o.key == c.key and abs(o.start - c.start) <= 40 and abs(o.end - c.end) <= 40
                     and o.kind is c.kind and abs(o.coverage - c.coverage) <= 0.02), None)
        if twin is not None:
            twin.also.append(c.number)
        else:
            out.append(c)
    return out


def _copy(host: str, text: str, s: str, where: list[int], index: Index,
          group: list[tuple[int, int, int, list[tuple[int, int]]]]) -> Copy | None:
    start = min(g[0] for g in group)
    end = min(len(s), max(g[1] for g in group))
    # The looked-up runs fall every STRIDE characters: extend each end while the host and the section still agree.
    first = min(group, key=lambda g: g[0])
    i, pos = first[3][0]
    vs = index.streams[first[2]]
    while i > 0 and pos > 0 and s[i - 1] == vs[pos - 1]:
        i, pos = i - 1, pos - 1
    start = min(start, i)
    last = max(group, key=lambda g: g[1])
    i, pos = last[3][-1][0] + RUN, last[3][-1][1] + RUN
    vs = index.streams[last[2]]
    while i < len(s) and pos < len(vs) and s[i] == vs[pos]:
        i, pos = i + 1, pos + 1
    end = max(end, i)
    span_runs = [s[i:i + RUN] for i in range(start, end - RUN + 1)]
    v0 = index.versions[group[0][2]]
    # Every version of the section is weighed, even one with no cluster here: a copy of old words shares most of the new.
    shared: dict[int, int] = {}
    for vid, v in enumerate(index.versions):
        if v.key == v0.key and v.number == v0.number:
            mine = index.sets[vid]
            shared[vid] = sum(1 for r in span_runs if r in mine)
    best = max(shared, key=lambda vid: (shared[vid], index.versions[vid].version is Version.CURRENT))
    v = index.versions[best]
    cov = min(1.0, shared[best] / index.total[best])
    fidelity = min(1.0, shared[best] / max(1, len(span_runs)))
    chars = shared[best] + RUN - 1
    if cov >= 0.9 and fidelity >= 0.97 and cov >= 0.97:
        kind = CopyKind.VERBATIM
    elif cov >= 0.6 and fidelity >= 0.6:
        kind = CopyKind.NEAR_VERBATIM
    elif chars >= EXCERPT_CHARS and fidelity >= 0.5 and cov >= EXCERPT_COVERAGE:
        kind = CopyKind.EXCERPT
    else:
        return None
    a, b = where[start], where[end - 1] + 1
    while a > 0 and text[a - 1].isalnum():          # the copy starts and ends on whole words
        a -= 1
    while b < len(text) and text[b].isalnum():
        b += 1
    body = _plain(text[a:b])
    return Copy(host, a, b, v.key, v.number, v.caption, kind, _currency(index, shared, best), round(cov, 3),
                round(fidelity, 3), _label(v), " ".join(body[:16]), len(body),
                {_label(index.versions[vid]): n for vid, n in sorted(shared.items())})


def _currency(index: Index, shared: dict[int, int], best: int) -> Currency:
    kinds = {index.versions[vid].version for vid in shared}
    if kinds == {Version.CURRENT}:
        return Currency.UNAMENDED
    top = shared[best]
    current = [vid for vid in shared if index.versions[vid].version is Version.CURRENT
               and not index.versions[vid].removed]
    if current and shared[current[0]] >= top:
        others = [vid for vid in shared if vid not in current and shared[vid] >= top]
        return Currency.UNDECIDED if others else Currency.CURRENT
    winner = index.versions[best].version
    if winner is Version.PENDING:
        return Currency.DRAFT
    if winner is Version.SUPERSEDED:
        return Currency.STALE
    return Currency.CURRENT


# Paraphrases: a paragraph that shares a section's rare words without its runs. -----------------------------------

_STOP = frozenset("""a an and any are as at be been by for from has have if in into is it its no not of on or other
shall such than that the their them then there these this those to under unless upon was were which who will with
within without may must each all association owner owners unit units board""".split())


def _content(text: str) -> set[str]:
    return {w for w in _plain(text) if len(w) > 2 and w not in _STOP and not w.isdigit()}


def paragraphs(text: str) -> list[tuple[int, int]]:
    """The offsets of each paragraph (blank-line separated) of ``text``."""
    out, at = [], 0
    for m in re.finditer(r"\n[ \t>]*\n", text + "\n\n"):
        if text[at:m.start()].strip():
            out.append((at, min(m.start(), len(text))))
        at = m.end()
    return out


def paraphrases(host: str, text: str, versions: Iterable[SectionVersion], *, taken: Sequence[tuple[int, int]] = (),
                least: float = 0.7, rare: int = 6, min_words: int = 12, widest: float = 3.0) -> list[Copy]:
    """Paragraphs of ``text`` holding ``least`` of a section's content words, ``rare`` of them words few sections use,
    outside the spans already ``taken`` by a copy, in a paragraph no more than ``widest`` times the section's content
    words (a long paragraph shares many words with anything). Current versions only: a paraphrase is a lead to read."""
    current = [v for v in versions if v.version is Version.CURRENT and not v.removed]
    sets = [_content(v.words) for v in current]
    df: dict[str, int] = defaultdict(int)
    for c in sets:
        for w in c:
            df[w] += 1
    postings: dict[str, list[int]] = defaultdict(list)
    for k, c in enumerate(sets):
        for w in c:
            if df[w] <= 3:
                postings[w].append(k)
    out: list[Copy] = []
    for a, b in paragraphs(text):
        if any(a < e and s < b for s, e in taken):
            continue
        para = _content(text[a:b])
        if len(para) < min_words:
            continue
        counts: dict[int, int] = defaultdict(int)
        for w in para:
            for k in postings.get(w, ()):
                counts[k] += 1
        for k, n in counts.items():
            if n < rare or len(sets[k]) < min_words or len(para) > widest * len(sets[k]):
                continue
            share = len(sets[k] & para) / len(sets[k])
            if share < least:
                continue
            v = current[k]
            body = _plain(text[a:b])
            out.append(Copy(host, a, b, v.key, v.number, v.caption, CopyKind.PARAPHRASE, Currency.UNDECIDED,
                            round(share, 3), round(len(sets[k] & para) / len(para), 3), "current",
                            " ".join(body[:16]), len(body)))
    return out


__all__ = ["COMMON", "Copy", "CopyKind", "Currency", "GAP", "Index", "RUN", "STRIDE", "SectionVersion", "Version",
           "find", "offsets", "paragraphs", "paraphrases", "stream", "words_of"]
