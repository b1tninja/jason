"""The splitter's cheap suggestion pass (docs/pdf-splitter.md, section 4): where a document probably starts, from what the pages show.

Deterministic, and no model, network, or file: it takes the per-page facts (``split_session.PageFact``) and, when the text layer was
read, the segmentation's ``PageInfo`` rows. The text cues are the segmentation's own cue table (``document_segments.CUES``: the page
numbering restarting, a title or a letterhead opening the page, a running header or footer that changes, a blank before, a change of
size or orientation); this module adds three signals from the scan itself that the cue table does not read (a change of scan
resolution, a change of colour mode, and a blank separator on a page with no text layer), each with a low weight, because a change of
scan setting alone is common inside one document and matters only in company.

A suggestion carries every signal with its weight and a reason in words built from them, a confidence (a logistic of the summed
weights; **not yet calibrated**, which ``scripts/split_fuzz.py`` measures), and a band. It is never applied: the session keeps
suggestions apart from the person's boundaries, and only a person's ``accept`` merges one.

The model pass (docs/pdf-splitter.md, 4.4), the within-session learning (4.6), and nested levels are later phases: every suggestion
here is ``reader="rules"`` at level 0.
"""

from __future__ import annotations

import math
from typing import Sequence

from jason.community import document_segments as ds
from jason.community.split_session import PageFact, Signal, Suggestion

FLOOR = 0.55                 # the least summed weight listed at all (a Low suggestion); the screen shows High and Medium by default
MIDPOINT = 0.6               # the summed weight at which a page is as likely a start as not (the rule pass starts a document at 0.8)
STEEPNESS = 3.0
DPI_TOLERANCE = 0.2          # a scan resolution this far from the page before's (a share) is a change

# The signals this pass adds to the segmentation's cue table, with the weight and the words of each.
SPLIT_SIGNALS: dict[str, tuple[float, str]] = {
    "dpi-change": (0.35, "the scan resolution changes"),
    "colour-change": (0.35, "the page's colour mode changes"),
    "blank-before": (0.9, "a blank page comes before, and blank pages are rare in this scan, so it reads as a separator"),
    "size-change": (0.9, "the page is not the size or orientation of the page before"),
}


def confidence(score: float) -> float:
    """The logistic of a summed weight: 0.5 at ``MIDPOINT``, 0.65 at the rule pass's own threshold (0.8), 0.94 at 1.5."""
    return 1.0 / (1.0 + math.exp(-STEEPNESS * (score - MIDPOINT)))


def _sentence(says: str, evidence: str = "") -> str:
    text = says.strip()
    text = text[:1].upper() + text[1:]
    if evidence:
        text += f" ({evidence.strip()[:50]})"
    return text.rstrip(".") + "."


def _resized(a: PageFact, b: PageFact) -> bool:
    if not (a.width and a.height and b.width and b.height):
        return False
    if (a.width > a.height) != (b.width > b.height):
        return True
    return abs(a.width - b.width) / max(a.width, 1) > 0.05 or abs(a.height - b.height) / max(a.height, 1) > 0.05


def _live(fact: PageFact) -> bool:
    return fact.blank != "blank"


def _fact_signals(facts: Sequence[PageFact], text_scored: set[int], text_keys: dict[int, set[str]]) -> dict[int, list[tuple[str, float, str]]]:
    """The signals the scan itself shows, for each page after the first."""
    out: dict[int, list[tuple[str, float, str]]] = {}
    blanks = sum(1 for f in facts if f.blank == "blank")
    rare = bool(facts) and blanks / len(facts) <= ds.DUPLEX
    live = [f for f in facts if _live(f)]
    for i, f in enumerate(live):
        if i == 0:
            continue
        prev, nxt = live[i - 1], (live[i + 1] if i + 1 < len(live) else None)
        found: list[tuple[str, float, str]] = []
        had = text_keys.get(f.n, set())
        if rare and f.n - prev.n > 1:
            found.append(("blank-before", SPLIT_SIGNALS["blank-before"][0], f"{f.n - prev.n - 1} blank"))
        if f.n not in text_scored and "size-change" not in had and _resized(prev, f) and (nxt is None or _resized(prev, nxt)):
            found.append(("size-change", SPLIT_SIGNALS["size-change"][0], f"{prev.width:.0f}x{prev.height:.0f} then {f.width:.0f}x{f.height:.0f}"))
        if prev.dpi and f.dpi and abs(f.dpi - prev.dpi) / max(prev.dpi, 1) > DPI_TOLERANCE:
            found.append(("dpi-change", SPLIT_SIGNALS["dpi-change"][0], f"{prev.dpi} then {f.dpi} dpi"))
        if prev.colour and f.colour and prev.colour != f.colour:
            found.append(("colour-change", SPLIT_SIGNALS["colour-change"][0], f"{prev.colour} then {f.colour}"))
        if found:
            out[f.n] = found
    return out


def suggest(facts: Sequence[PageFact], pages: Sequence[ds.PageInfo] | None = None, *, floor: float = FLOOR,
            without: Sequence[str] = ()) -> list[Suggestion]:
    """Suggested first pages, in page order, each with its signals and reason. Page 1 is never suggested: it always starts a segment.
    ``pages`` is the text layer's ``PageInfo`` rows (``jason.tasks.segments.read_pages``); without it only the scan's own signals
    speak. ``without`` leaves named signals out (the fuzz harness's ablation)."""
    text_scores: dict[int, tuple[float, list[tuple[str, float, str]]]] = {}
    if pages:
        text_scores = ds.score_pages(list(pages))
    text_keys = {n: {k for k, _, _ in fired} for n, (_, fired) in text_scores.items()}
    extra = _fact_signals(facts, set(text_scores), text_keys)
    out: list[Suggestion] = []
    for f in facts:
        if f.n == 1 or f.blank == "blank":
            continue
        score_text, fired = text_scores.get(f.n, (0.0, []))
        sigs = [(k, w, e) for k, w, e in fired if k != "after-blank"] + extra.get(f.n, [])      # a blank before is read once, below
        sigs = [x for x in sigs if x[0] not in without]
        if not sigs:
            continue
        score = sum(w for _, w, _ in sigs)
        if score < floor:
            continue
        signals = []
        for key, weight, evidence in sorted(sigs, key=lambda s: -abs(s[1])):
            says = ds.CUES[key].says if key in ds.CUES else SPLIT_SIGNALS[key][1]
            signals.append(Signal(key, weight, _sentence(says, evidence)))
        pos = [s for s in signals if s.weight > 0][:3]
        neg = [s for s in signals if s.weight <= -0.8][:1]
        why = f"Page {f.n}. " + " ".join(s.said for s in pos)
        if neg:
            why += " Against: " + neg[0].said[:1].lower() + neg[0].said[1:]
        out.append(Suggestion(f"g{f.n}", f.n, 0, round(confidence(score), 3), "suggested", signals, why.strip(), "rules", "open"))
    return out


def facts_from_pages(pages: Sequence[ds.PageInfo], *, ink_blank: float = 0.004, ink_marked: float = 0.02) -> list[PageFact]:
    """Per-page facts from the segmentation's page rows alone (a text layer): size, words, the running lines, the printed page number,
    the title and a date. A page with no words is blank when it has almost no ink, marked when it has a little, else content with no
    text layer. Image facts (dpi, colour, codec) come from the scan: ``jason.tasks.split_session.page_facts``."""
    out = []
    for p in pages:
        label = ds.label_of(p)
        if not p.blank:
            blank, has_text = "content", True
        else:
            has_text = False
            ink = p.ink if p.ink is not None else 1.0
            blank = "blank" if ink < ink_blank else "marked" if ink < ink_marked else "content"
        title = ds.read_title(p) if has_text else ""
        out.append(PageFact(p.n, p.width, p.height, 0, blank, has_text, p.words, p.chars, 0, "", "", p.header[:80], p.footer[:80],
                            (label.n, label.total) if label and not label.roman else None, title[:90],
                            ds.read_date(p.lead) if has_text else "", ""))
    return out


def reasons(suggestion: Suggestion) -> str:
    """A suggestion's reason with its band and confidence, for a terminal."""
    return f"page {suggestion.page}  {suggestion.band} ({suggestion.confidence:.2f})  {suggestion.why}"

