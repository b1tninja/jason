"""Segmentation on disk: read a PDF's pages, run the readers, keep the reading in ``data/library/segments/<id>.json``.

``jason.community.document_segments`` is the pure part (the cue table, the records, the parts). This module:

- reads each page of a PDF into ``PageInfo`` (its text layer's lines with their place and type size; an image-only page
  is measured for ink, and OCR'd only when asked: ``ocr=True``);
- runs the second readers, each behind an option and neither on by default: the local vision model shown a page's
  thumbnail ("is this the first page of a new document?", scored from its ``top_logprobs`` as
  ``OllamaTextCorrector.choose`` does, run after ``local_ai.preflight`` and holding the GPU lock) and the embedder
  (``qwen3-embedding``: the cosine between adjacent pages);
- classifies each segment's kind with the profile's name rules and jason's phrase rules (``classify_document``,
  ``content.classify_text``), the same chain the library uses; a miss stays a miss;
- keeps the reading beside the library's text, keyed by the file's SHA-256, under the store lock. The source file is
  never split or rewritten, and a reading of other bytes is stale (``stale``).

Everything here reads the file as it is. Preparing the scan first (removing blank pages, cleaning, deskewing) is the
preflight's work, not this module's: a blank page is read as a page with no words and is transparent to the rules.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jason.community.document_segments import (
    BLANK_CHARS, MODEL_THRESHOLD, THRESHOLD, VERSION, Boundary, Line, MoveKind, PageInfo, Reader, Segment, Segmentation, Tier,
    build_page, decide, find_parts, score_pages, walk_segments)

DEFAULT_MODEL = "qwen3.5:9b"


def default_data_dir() -> Path:
    from jason.config import Settings

    return Settings.load().ownership_db.parent


def store_dir(data_dir: Path) -> Path:
    return Path(data_dir) / "library" / "segments"


def store_path(data_dir: Path, doc_id: str) -> Path:
    return store_dir(data_dir) / f"{doc_id}.json"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def file_id(path: Path, sha: str = "") -> str:
    """The store id of a file the library does not hold: ``sha-`` and the first sixteen hex digits of its SHA-256."""
    return "sha-" + (sha or sha256_of(path))[:16]


def load(data_dir: Path, doc_id: str) -> Segmentation | None:
    path = store_path(data_dir, doc_id)
    if not path.is_file():
        return None
    try:
        return Segmentation.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, KeyError):
        return None


def save(data_dir: Path, seg: Segmentation) -> Path:
    """Write the reading under the store lock. It is a new file or a replaced reading; the source PDF is not touched."""
    from jason.locks import Resource, hold

    path = store_path(data_dir, seg.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with hold(Resource.STORE, f"segments-{seg.id}", timeout=60, purpose=f"segments {seg.id}"):
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(seg.to_dict(), ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    return path


def stored(data_dir: Path) -> list[Segmentation]:
    """Every stored reading."""
    folder = store_dir(data_dir)
    found = [load(data_dir, p.stem) for p in sorted(folder.glob("*.json"))] if folder.is_dir() else []
    return [s for s in found if s is not None]


def parts_in_store(data_dir: Path, *, book: str = "", kind: str = "") -> list[tuple[Segmentation, Any]]:
    """The parts of a book ("rules") or a kind ("form") across every stored reading, each with the reading it is in:
    what a citation to "the Rules" scopes to. Each part is a page range of a file, so the words in it are the words of
    those pages (``text_of_pages``) or of any other text of the same document found by its anchors (``part_span``)."""
    return [(seg, part) for seg in stored(data_dir) for part in seg.parts_of(kind=kind, book=book)]


def text_of_pages(pdf: Path, start: int, end: int) -> str:
    """The text layer of pages ``start`` to ``end`` (1-based, inclusive), page by page, blank line between."""
    import pymupdf

    with pymupdf.open(str(pdf)) as doc:
        return "\n\n".join(doc[n - 1].get_text() for n in range(max(1, start), min(doc.page_count, end) + 1))


def stale(seg: Segmentation, pdf: Path) -> bool:
    """Whether the reading is of other bytes than the file now holds."""
    return bool(seg.sha256) and seg.sha256 != sha256_of(pdf)


# ---------------------------------------------------------------------------------------------------------------------
# Reading the pages


def _lines_of(raw: dict[str, Any], width: float, height: float) -> tuple[list[Line], str]:
    lines: list[Line] = []
    fonts: Counter[str] = Counter()
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for ln in block.get("lines", []):
            spans = ln.get("spans") or []
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            x0, y0, x1, y1 = ln["bbox"]
            size = max((s.get("size", 0.0) for s in spans), default=0.0)
            bold = any((s.get("flags", 0) & 16) or "bold" in str(s.get("font", "")).lower() for s in spans)
            for s in spans:
                fonts[str(s.get("font", ""))] += len(s.get("text", ""))
            lines.append(Line(text, y0 / height, y1 / height, x0 / width, x1 / width, size, bold))
    lines.sort(key=lambda x: (round(x.top * 200), x.x0))
    return lines, (fonts.most_common(1)[0][0] if fonts else "")


def _ink(page: Any) -> float:
    """The share of dark pixels at 24 dpi: how much is printed on a page that has no words."""
    import pymupdf

    pix = page.get_pixmap(dpi=24, colorspace=pymupdf.csGRAY)
    data = pix.samples
    return round(sum(1 for b in data if b < 128) / max(1, len(data)), 4)


def read_pages(pdf: Path, *, ocr: bool = False, progress: Callable[[int, int], None] | None = None
               ) -> tuple[list[PageInfo], list[list[Any]]]:
    """Each page's features from the file's text layer, and the file's bookmarks ([level, title, page]). A page with no
    words is measured for ink; with ``ocr`` it is read by Tesseract through PyMuPDF (slow: not the default)."""
    import pymupdf

    out: list[PageInfo] = []
    with pymupdf.open(str(pdf)) as doc:
        toc = [list(t[:3]) for t in doc.get_toc()]
        for i in range(doc.page_count):
            page = doc[i]
            w, h = float(page.rect.width), float(page.rect.height)
            lines, font = _lines_of(page.get_text("dict"), w, h)
            source = "text"
            if sum(c.isalnum() for ln in lines for c in ln.text) < BLANK_CHARS and ocr:
                from jason.community.ocr import PyMuPdfTesseract

                if PyMuPdfTesseract.available():
                    textpage = page.get_textpage_ocr(dpi=200, language="eng", full=True, tessdata=PyMuPdfTesseract.tessdata())
                    lines, font = _lines_of(page.get_text("dict", textpage=textpage), w, h)
                    source = "ocr"
            info = build_page(i + 1, w, h, lines, source=source, font=font)
            if info.blank:
                info.ink = _ink(page)
            out.append(info)
            if progress:
                progress(i + 1, doc.page_count)
    return out, toc


def page_png(pdf: Path, n: int, *, dpi: int = 72) -> str:
    """Page ``n`` (1-based) as a base64 PNG."""
    import pymupdf

    with pymupdf.open(str(pdf)) as doc:
        return base64.b64encode(doc[n - 1].get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")


def page_texts(pdf: Path) -> list[str]:
    import pymupdf

    with pymupdf.open(str(pdf)) as doc:
        return [doc[i].get_text() for i in range(doc.page_count)]


# ---------------------------------------------------------------------------------------------------------------------
# The vision model as a second reader

SINGLE_PROMPT = (
    "This image is one page of a scanned file that may hold several separate documents stacked together (letters, "
    "agreements, invoices, reports, minutes, recorded instruments). Is this page the FIRST page of a new, separate "
    "document, rather than a continuation of the page before it? A first page usually has a title, a letterhead, a "
    "recording stamp, a date and addressee, or a page number 1. A continuation starts in the middle of the text or "
    "carries the next page number. Answer Y for a first page or N for a continuation.")
PAIR_PROMPT = (
    "The first image is a page of a scanned file that may hold several separate documents stacked together. The second "
    "image is the very next page. Is the second page the FIRST page of a new, separate document (a different title, "
    "letterhead, sender, subject, or numbering), rather than a continuation of the first page's document? Answer Y if "
    "the second page starts a new document or N if it continues the first.")


@dataclass
class OllamaPageReader:
    """The vision model scoring "does this page start a document?" from the probabilities of Y and N (Ollama's
    ``top_logprobs``), so its answer is a number and not a verdict. ``pair`` shows the page before as well."""

    model: str = DEFAULT_MODEL
    base_url: str = "http://localhost:11434"
    dpi: int = 72
    context: int = 4096
    timeout: int = 300
    pair: bool = False
    fetch: Callable[[str, dict], dict] | None = None

    def p_new(self, page_png_b64: str, before_png_b64: str = "") -> float | None:
        """The probability that the page starts a new document, or None when the model gave no Y or N."""
        from jason.community.ollama_extractor import _post

        images = [before_png_b64, page_png_b64] if (self.pair and before_png_b64) else [page_png_b64]
        prompt = PAIR_PROMPT if len(images) == 2 else SINGLE_PROMPT
        payload = {"model": self.model, "stream": False, "think": False, "logprobs": True, "top_logprobs": 10,
                   "keep_alive": "10m", "options": {"temperature": 0, "num_ctx": self.context, "num_predict": 1},
                   "messages": [{"role": "user", "content": prompt, "images": images}]}
        poster = self.fetch or (lambda url, body: _post(url, body, self.timeout))
        answer = poster(f"{self.base_url}/api/chat", payload)
        weights = {"Y": 0.0, "N": 0.0}
        for row in (answer.get("logprobs") or [{}])[0].get("top_logprobs") or []:
            token = str(row.get("token") or "").strip().upper()[:1]
            if token in weights:
                weights[token] += math.exp(float(row.get("logprob") or -100))
        total = weights["Y"] + weights["N"]
        return None if total <= 0 else weights["Y"] / total


    def move_probs(self, page_png_b64: str, before_png_b64: str, choices: dict[str, str]) -> dict[str, float] | None:
        """The model's probability for each lettered move against the stack (``document_segments.move_choices``), from the
        probabilities of the letters in its ``top_logprobs``; None when it named none of them. It is shown the page before
        and the page, and the open documents by title."""
        from jason.community.ollama_extractor import _post

        lines = "\n".join(f"{k}) {v}" for k, v in choices.items())
        prompt = ("The first image is a page of a scanned file that holds several documents, some inside others (an exhibit "
                  "inside an agreement, a report inside a packet). The second image is the very next page. The documents "
                  f"open at the first page, innermost last, are named below. Which is true of the second page?\n{lines}\n"
                  "Answer with one letter.")
        payload = {"model": self.model, "stream": False, "think": False, "logprobs": True, "top_logprobs": 12,
                   "keep_alive": "10m", "options": {"temperature": 0, "num_ctx": self.context, "num_predict": 1},
                   "messages": [{"role": "user", "content": prompt, "images": [before_png_b64, page_png_b64]}]}
        poster = self.fetch or (lambda url, body: _post(url, body, self.timeout))
        answer = poster(f"{self.base_url}/api/chat", payload)
        weights = {k: 0.0 for k in choices}
        for row in (answer.get("logprobs") or [{}])[0].get("top_logprobs") or []:
            token = str(row.get("token") or "").strip().upper()[:1]
            if token in weights:
                weights[token] += math.exp(float(row.get("logprob") or -100))
        total = sum(weights.values())
        return None if total <= 0 else {k: v / total for k, v in weights.items()}


def read_model(pdf: Path, pages: Sequence[PageInfo], reader: Any, *, progress: Callable[[int, int], None] | None = None
               ) -> dict[int, float]:
    """The model's probability for each page with words (the first is not asked): {page: p(new document)}."""
    import pymupdf

    out: dict[int, float] = {}
    todo = [p for p in pages if not p.blank]
    before: PageInfo | None = None
    dpi = getattr(reader, "dpi", 72)
    with pymupdf.open(str(pdf)) as doc:
        def render(n: int) -> str:
            return base64.b64encode(doc[n - 1].get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")

        for k, page in enumerate(todo):
            if before is not None:
                p = reader.p_new(render(page.n), render(before.n) if getattr(reader, "pair", False) else "")
                if p is not None:
                    out[page.n] = p
            before = page
            if progress:
                progress(k + 1, len(todo))
    return out


def read_moves(pdf: Path, pages: Sequence[PageInfo], segments: Sequence[Segment], moves: Sequence[Any], reader: Any
               ) -> dict[int, dict[str, float]]:
    """Ask the vision model each move the rule pass made but a continue, as a closed choice against the stack at that page
    (continue, new inside, back to an outer document, new top-level), and return {page: {letter: probability}}. The
    letters are ``document_segments.move_choices``'s; ``move_letter`` says which the rule pass's move is."""
    import pymupdf

    from jason.community.document_segments import move_choices, open_chain

    live = [p for p in pages if not p.blank]
    before = {b.n: a.n for a, b in zip(live, live[1:])}
    out: dict[int, dict[str, float]] = {}
    dpi = getattr(reader, "dpi", 72)
    with pymupdf.open(str(pdf)) as doc:
        def render(n: int) -> str:
            return base64.b64encode(doc[n - 1].get_pixmap(dpi=dpi).tobytes("png")).decode("ascii")

        for move in moves:
            prev = before.get(move.page)
            if move.kind is MoveKind.FIRST or prev is None:
                continue
            chain = open_chain(segments, prev)
            if not chain:
                continue
            got = reader.move_probs(render(move.page), render(prev), move_choices(chain))
            if got is not None:
                out[move.page] = got
    return out


def attach_moves(seg: Segmentation, probs: dict[int, dict[str, float]]) -> Segmentation:
    """Put the model's reading of each move on the move, and make the move ``LIKELY`` where the model's most probable
    letter is the rule pass's move, ``SUGGESTED`` where it is not (the readers disagree: a person looks). The segments
    keep their own tier, which is the boundary's."""
    from dataclasses import replace

    from jason.community.document_segments import move_letter, open_chain

    live = [p for p in seg.pages if not p.blank]
    before = {b.n: a.n for a, b in zip(live, live[1:])}
    out = []
    for move in seg.moves:
        got = probs.get(move.page)
        if got is None:
            out.append(move)
            continue
        prev = before.get(move.page)
        chain = open_chain(seg.segments, prev) if prev else []
        top = max(got, key=got.get)
        agree = top == move_letter(move, chain) and got[top] >= 0.5
        out.append(replace(move, model=got, tier=Tier.LIKELY if agree else Tier.SUGGESTED,
                           readers=(*move.readers, Reader.MODEL) if Reader.MODEL not in move.readers else move.readers))
    seg.moves = out
    return seg


# ---------------------------------------------------------------------------------------------------------------------
# The embedder as a third


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def read_embeddings(pages: Sequence[PageInfo], embedder: Any) -> dict[int, float]:
    """The cosine between each page with words and the one before it ({page: cosine}); lower is a bigger change."""
    todo = [p for p in pages if not p.blank and p.lead.strip()]
    if len(todo) < 2:
        return {}
    vectors = embedder.embed_passages([p.lead for p in todo])
    return {b.n: _cosine(va, vb) for (a, b), (va, vb) in zip(zip(todo, todo[1:]), zip(vectors, vectors[1:]))}


# ---------------------------------------------------------------------------------------------------------------------
# The kind of each segment


def kind_chain(community: Any = None) -> Callable[[str, str], tuple[str, str]]:
    """``classify(title, opening text) -> (DocumentKind value, basis)``: the profile's name rules over the title, then
    jason's phrase rules over the opening words, as the library does; a miss is ("", "")."""
    from jason.community.content import classify_text

    def classify(title: str, text: str) -> tuple[str, str]:
        if community is not None and title:
            try:
                kind = community.classify_document(f"{title}.pdf")
            except Exception:  # noqa: BLE001 - a profile without kind rules is a miss
                kind = None
            if kind is not None:
                return kind.value, "name rule over the title"
        kind, why = classify_text(text or "")
        return (kind.value, f"phrase rule: {why}") if kind is not None else ("", "")

    return classify


# ---------------------------------------------------------------------------------------------------------------------
# Putting it together


def segment_pages(pages: Sequence[PageInfo], *, toc: Sequence[Sequence[Any]] = (), model: dict[int, float] | None = None,
                  embeddings: dict[int, float] | None = None, community: Any = None, threshold: float = THRESHOLD,
                  model_threshold: float = MODEL_THRESHOLD, accept: str = "any", weights: dict[str, float] | None = None,
                  text_of: Callable[[int], list[str]] | None = None, doc_id: str = "", name: str = "",
                  sha: str = "", readers: dict[str, str] | None = None) -> Segmentation:
    """Run the rule pass (and the model's and embedder's readings when given) over stored pages and return the reading."""
    scores = score_pages(pages, embeddings=embeddings, weights=weights)
    boundaries = decide(pages, rule_scores=scores, model=model, embeddings=embeddings, threshold=threshold,
                        model_threshold=model_threshold, accept=accept)
    segments, moves = walk_segments(pages, boundaries, classify=kind_chain(community))
    parts = find_parts(pages, segments, toc=toc, text_of=text_of)
    return Segmentation(
        doc_id, sha, name, len(pages), {"rules": VERSION, **(readers or {})},
        {"threshold": threshold, "modelThreshold": model_threshold, "accept": accept, "weights": weights or {}},
        boundaries, segments, parts, list(pages), datetime.now(timezone.utc).isoformat(timespec="seconds"), moves)


def segment_file(pdf: Path, *, doc_id: str = "", data_dir: Path | None = None, model: Any = None, embedder: Any = None,
                 ocr: bool = False, community: Any = None, accept: str = "any", write: bool = True, force: bool = False,
                 progress: Callable[[str, int, int], None] | None = None) -> Segmentation:
    """Read ``pdf`` and keep its segments and parts. A reading of the same bytes is reused unless ``force``; a model or an
    embedder (both off by default) adds its reading to the stored one. The PDF is never changed."""
    pdf = Path(pdf)
    sha = sha256_of(pdf)
    doc_id = doc_id or file_id(pdf, sha)
    root = Path(data_dir) if data_dir else None
    cached = load(root, doc_id) if (root is not None and not force) else None
    if cached is not None and cached.sha256 == sha and cached.pages:
        pages = cached.pages
        import pymupdf

        with pymupdf.open(str(pdf)) as doc:
            toc = [list(t[:3]) for t in doc.get_toc()]
    else:
        pages, toc = read_pages(pdf, ocr=ocr, progress=(lambda a, b: progress("pages", a, b)) if progress else None)
    readers: dict[str, str] = {}
    model_p = embeds = None
    if model is not None:
        from jason.local_ai import preflight

        preflight(getattr(model, "model", DEFAULT_MODEL))
        started = time.monotonic()
        model_p = read_model(pdf, pages, model, progress=(lambda a, b: progress("model", a, b)) if progress else None)
        readers["model"] = f"{model.model} {'pair' if model.pair else 'single'} {model.dpi}dpi"
        readers["modelSeconds"] = f"{time.monotonic() - started:.1f}"
    elif cached is not None and cached.sha256 == sha:
        model_p = {b.page: b.model for b in cached.candidates if b.model is not None} or None
    if embedder is not None:
        embeds = read_embeddings(pages, embedder)
        readers["embedding"] = getattr(embedder, "model", "embedder")
    texts = page_texts(pdf)
    seg = segment_pages(pages, toc=toc, model=model_p, embeddings=embeds, community=community, accept=accept,
                        text_of=lambda n: [ln for ln in texts[n - 1].splitlines() if ln.strip()] if 0 < n <= len(texts) else [],
                        doc_id=doc_id, name=pdf.name, sha=sha, readers=readers)
    if model is not None and hasattr(model, "move_probs"):
        # The second reader on each move the rules made: the closed choice against the stack at that page.
        probs = read_moves(pdf, pages, seg.segments, seg.moves, model)
        attach_moves(seg, probs)
        seg.readers["moves"] = f"{model.model} closed choice, {len(probs)} moves"
    if write and root is not None:
        save(root, seg)
    return seg


# ---------------------------------------------------------------------------------------------------------------------
# Measuring against labeled files


def _near(pred: Sequence[int], gold: Sequence[int], rank: dict[int, int], within: int) -> tuple[int, set[int]]:
    """Gold boundaries matched once each to the nearest unmatched prediction, within ``within`` content pages (blank
    pages are not counted: a blank back between two pages is no distance). Returns the hits and the matched predictions."""
    used: set[int] = set()
    hits = 0
    for g in sorted(gold):
        near = [p for p in pred if p not in used and abs(rank.get(p, p) - rank.get(g, g)) <= within]
        if near:
            used.add(min(near, key=lambda p: abs(rank.get(p, p) - rank.get(g, g))))
            hits += 1
    return hits, used


def prf(predicted: Sequence[int], gold: Sequence[int], *, within: int = 0, maybe: Sequence[int] = (),
        rank: dict[int, int] | None = None) -> dict[str, float]:
    """Precision, recall, and F1 of boundary pages, exact (``within`` 0) or within some content pages. Each gold boundary
    is matched once, to the nearest unmatched prediction inside the window. A prediction on a ``maybe`` page (a boundary
    the labeler could not decide) is dropped first: it counts neither way."""
    skip = set(maybe) - set(gold)
    pred = sorted(set(predicted) - skip)
    want = sorted(set(gold))
    hits, _ = _near(pred, want, rank or {}, within)
    precision = hits / len(pred) if pred else 0.0
    recall = hits / len(want) if want else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": hits, "predicted": len(pred), "gold": len(want), "precision": precision, "recall": recall, "f1": f1}


def pooled(rows: Sequence[dict[str, float]]) -> dict[str, float]:
    """Micro-averaged precision, recall, and F1 over files."""
    tp = sum(r["tp"] for r in rows)
    pred = sum(r["predicted"] for r in rows)
    gold = sum(r["gold"] for r in rows)
    p = tp / pred if pred else 0.0
    r = tp / gold if gold else 0.0
    return {"tp": tp, "predicted": pred, "gold": gold, "precision": p, "recall": r,
            "f1": 2 * p * r / (p + r) if p + r else 0.0}


def part_accuracy(parts: Sequence[Any], gold: Sequence[dict[str, Any]], *, within: int = 0) -> dict[str, Any]:
    """How the found parts meet the labeled ones. A gold part ``{title, start, end}`` is *found* when a found part starts
    within ``within`` pages of its start (the anchor), and *exact* when it also ends within ``within`` pages of its end.
    ``extra`` counts found parts that match no gold part."""
    found = exact = 0
    used: set[int] = set()
    for g in gold:
        cands = [(i, p) for i, p in enumerate(parts) if i not in used and abs(p.start - g["start"]) <= within]
        if cands:
            i, p = min(cands, key=lambda ip: abs(ip[1].start - g["start"]))
            used.add(i)
            found += 1
            if abs(p.end - g["end"]) <= within:
                exact += 1
    extra = len(parts) - len(used)
    return {"gold": len(gold), "found": found, "exact": exact, "extra": extra,
            "anchor": found / len(gold) if gold else 0.0, "span": exact / len(gold) if gold else 0.0,
            "precision": len(used) / len(parts) if parts else 0.0}


VARIANTS = ("rules", "model", "agree", "union", "rules-alone", "model-alone", "embed", "rules+embed", "all3")


def variant_breaks(pages: Sequence[PageInfo], variant: str, *, model: dict[int, float] | None = None,
                   embeddings: dict[int, float] | None = None, threshold: float = THRESHOLD,
                   model_threshold: float = MODEL_THRESHOLD, weights: dict[str, float] | None = None) -> list[int]:
    """The pages a reader (or readers) say break: ``rules`` (the cue pass), ``model`` (the vision model's probability),
    ``agree`` (both), ``union`` (either), ``rules-alone`` and ``model-alone`` (one and not the other), ``embed`` (the
    embedder's change points), ``rules+embed`` (the cues with the embedder's), ``all3`` (any two of the three). What a
    break is, a new document or an outer one returning, is the walk's to say (``variant_tree``)."""
    from jason.community.document_segments import embedding_break

    rules = {n for n, (score, _) in score_pages(pages, weights=weights).items() if score >= threshold}
    with_embedding = {n for n, (score, _) in score_pages(pages, embeddings=embeddings, weights=weights).items()
                      if score >= threshold}
    said = {n for n, p in (model or {}).items() if p >= model_threshold}
    broke = {n for n, c in (embeddings or {}).items() if embedding_break(c)}
    return sorted({"rules": rules, "model": said, "agree": rules & said, "union": rules | said, "rules-alone": rules - said,
                   "model-alone": said - rules, "embed": broke, "rules+embed": with_embedding,
                   "all3": {n for n in rules | said | broke if sum([n in rules, n in said, n in broke]) >= 2}}[variant])


def variant_tree(pages: Sequence[PageInfo], variant: str, **kw: Any) -> tuple[list[Segment], list[Any]]:
    """The tree and the moves the walk makes from a variant's breaks."""
    breaks = [Boundary(n, Tier.SUGGESTED, (Reader.RULES,)) for n in variant_breaks(pages, variant, **kw)]
    return walk_segments(pages, breaks)


def variant_starts(pages: Sequence[PageInfo], variant: str, **kw: Any) -> list[int]:
    """The first pages of the documents a variant finds (an exhibit is nested, and counted there; a page where an outer
    document returns is not a start). The first page with words is one in every variant, and is left out of the figures."""
    return sorted(s.start for s in variant_tree(pages, variant, **kw)[0] if s.role == "document")


def nesting_accuracy(segments: Sequence[Segment], moves: Sequence[Any], gold_nested: Sequence[dict[str, Any]],
                     gold_resumes: Sequence[dict[str, Any]], rank: dict[int, int], *, maybe: Sequence[int] = ()) -> dict[str, Any]:
    """How the tree meets the labeled nesting, within one content page. A labeled item {start, parent, end}: *found* when a
    segment starts there, *parent* when that segment's parent starts at the labeled page, *end* when it ends there. A
    segment that is nested and matches no labeled item is *extra*. A labeled resume {page, to}: *popped* when the walk pops
    at that page back to the document that started at ``to``."""
    def near(a: int, b: int) -> bool:
        return abs(rank.get(a, a) - rank.get(b, b)) <= 1

    by_key = {s.key: s for s in segments}
    found = parent_ok = end_ok = 0
    used: set[str] = set()
    for g in gold_nested:
        cand = [s for s in segments if s.key not in used and near(s.start, g["start"])]
        if not cand:
            continue
        s = min(cand, key=lambda x: abs(rank.get(x.start, x.start) - rank.get(g["start"], g["start"])))
        used.add(s.key)
        found += 1
        parent = by_key.get(s.parent)
        if parent is not None and (near(parent.start, g["parent"]) or (parent.start in maybe and parent.start >= g["parent"])):
            parent_ok += 1                 # a maybe page that split the parent leaves the child in a fragment of it
        if near(s.end - s.blank_after, g["end"]):
            end_ok += 1
    extra = sum(1 for s in segments if s.parent and s.key not in used and not any(near(s.start, m) for m in maybe))
    popped = pops = 0
    pop_moves = [m for m in moves if m.kind is MoveKind.POP]
    taken: set[int] = set()
    for g in gold_resumes:
        pops += 1
        hit = next((m for i, m in enumerate(pop_moves) if i not in taken and near(m.page, g["page"])
                    and by_key.get(m.segment) is not None and near(by_key[m.segment].start, g["to"])), None)
        if hit is not None:
            taken.add(pop_moves.index(hit))
            popped += 1
    return {"gold": len(gold_nested), "found": found, "parent": parent_ok, "end": end_ok, "extra": extra,
            "resumes": pops, "popped": popped, "pops_extra": len(pop_moves) - len(taken)}


def evaluate(files: Sequence[dict[str, Any]], pages_for: Callable[[dict[str, Any]], tuple[Sequence[PageInfo], Sequence[Any]]], *,
             variants: Sequence[str] = ("rules",), model_for: Callable[[dict[str, Any]], dict[int, float] | None] | None = None,
             embeddings_for: Callable[[dict[str, Any]], dict[int, float] | None] | None = None, split: str = "all",
             threshold: float = THRESHOLD, model_threshold: float = MODEL_THRESHOLD, weights: dict[str, float] | None = None,
             community: Any = None) -> dict[str, Any]:
    """Score the readers against labeled files. A labeled file is ``{path, split, boundaries, maybe, window, parts, nested,
    resumes}``; ``boundaries`` null leaves the file out of the boundary figures and ``parts`` null out of the part figures.
    The first page with words of each file is not counted (it is a start by definition); a prediction on a ``maybe`` page
    counts neither way; ``window`` limits the pages scored. Boundary figures are the first pages of documents (nested
    ones too, exhibits not), exact and within one content page; the nesting figures are ``nesting_accuracy``; part figures
    are the anchor (a found part starts at the labeled page, or within one) and the span (it also ends there)."""
    out: dict[str, Any] = {"variants": {}, "parts": {}, "nesting": {}, "files": []}
    chosen = [f for f in files if split == "all" or f.get("split") == split]
    rows: dict[str, list[tuple[dict, dict]]] = {v: [] for v in variants}
    nest_rows: dict[str, list[dict[str, Any]]] = {v: [] for v in variants}
    part_rows: list[dict[str, Any]] = []
    for f in chosen:
        pages, toc = pages_for(f)
        content = [p.n for p in pages if not p.blank]
        rank = {n: i for i, n in enumerate(content)}
        first = content[0] if content else 1
        lo, hi = (f.get("window") or [1, len(pages)])
        model = model_for(f) if model_for else None
        embeds = embeddings_for(f) if embeddings_for else None
        gold = [n for n in (f.get("boundaries") or []) if lo <= n <= hi and n != first]
        maybe = [n for n in (f.get("maybe") or []) if lo <= n <= hi]
        kw = {"model": model, "embeddings": embeds, "threshold": threshold, "model_threshold": model_threshold, "weights": weights}
        for v in variants:
            if f.get("boundaries") is None:
                continue
            if v in ("model", "agree", "union", "all3", "rules-alone", "model-alone") and not model:
                continue
            if v in ("embed", "rules+embed", "all3") and not embeds:
                continue
            segs, moves = variant_tree(pages, v, **kw)
            starts = [s.start for s in segs if s.role == "document" and lo <= s.start <= hi and s.start != first]
            exact = prf(starts, gold, maybe=maybe, rank=rank)
            near = prf(starts, gold, within=1, maybe=maybe, rank=rank)
            rows[v].append((exact, near))
            if f.get("nested") or f.get("resumes") or any(s.parent for s in segs):
                window = [s for s in segs if lo <= s.start <= hi]
                nest_rows[v].append(nesting_accuracy(window, [m for m in moves if lo <= m.page <= hi], f.get("nested") or [],
                                                     f.get("resumes") or [], rank, maybe=maybe))
            out["files"].append({"path": f["path"], "split": f.get("split"), "variant": v, "exact": exact, "near": near,
                                 "missed": sorted(set(gold) - set(starts)), "extra": sorted(set(starts) - set(gold) - set(maybe))})
        if f.get("parts") is not None:
            boundaries = decide(pages, rule_scores=score_pages(pages, weights=weights), threshold=threshold, accept="rules")
            if f.get("boundaries") is None:
                boundaries = [Boundary(first, Tier.LIKELY, (Reader.RULES,))]
            segs, _ = walk_segments(pages, boundaries)
            found = find_parts(pages, segs, toc=toc)
            span = part_accuracy(found, f["parts"], within=0)
            nearby = part_accuracy(found, f["parts"], within=1)
            part_rows.append({"path": f["path"], "exact": span, "near": nearby,
                              "found": [(p.title, p.start, p.end, p.basis) for p in found]})
    for v, pairs in rows.items():
        out["variants"][v] = {"exact": pooled([e for e, _ in pairs]), "near": pooled([n for _, n in pairs]), "files": len(pairs)}
    for v, rs in nest_rows.items():
        if rs:
            keys = ("gold", "found", "parent", "end", "extra", "resumes", "popped", "pops_extra")
            out["nesting"][v] = {k: sum(r[k] for r in rs) for k in keys} | {"files": len(rs)}
    if part_rows:
        g = sum(r["exact"]["gold"] for r in part_rows)
        n_found = sum(r["exact"]["found"] for r in part_rows)
        near_found = sum(r["near"]["found"] for r in part_rows)
        near_span = sum(r["near"]["exact"] for r in part_rows)
        extra = sum(r["near"]["extra"] for r in part_rows)
        out["parts"] = {"gold": g, "anchor_exact": n_found / g if g else 0.0, "anchor_near": near_found / g if g else 0.0,
                        "span_near": near_span / g if g else 0.0, "extra": extra, "files": len(part_rows), "rows": part_rows}
    return out


def gold_moves(f: dict[str, Any], first: int) -> dict[int, str]:
    """The labeled move at each page of a gold file: B (a document inside another: every nested start, exhibits too), C
    (a new top-level document: a boundary that is not nested), E/D (an outer document resumes: a labeled resume; the letter
    is D, the nearest outer, unless the label says more levels, which it does not today)."""
    nested = {g["start"] for g in f.get("nested") or []}
    out = {n: "C" for n in (f.get("boundaries") or []) if n != first}
    out.update({n: "B" for n in nested})
    out.update({g["page"]: "D" for g in f.get("resumes") or []})
    return out


def evaluate_moves(f: dict[str, Any], pages: Sequence[PageInfo], probs: dict[int, dict[str, float]]) -> dict[str, int]:
    """How the rule pass's moves and the model's closed-choice reading meet a gold file's labeled moves (the letters of
    ``gold_moves``). Counted over the rule pass's moves that are at a labeled page: the rules right, the model's most
    probable letter right, both the same letter (``LIKELY``), and how many of those same-letter moves are right."""
    from jason.community.document_segments import move_letter, open_chain

    live = [p for p in pages if not p.blank]
    if not live:
        return {}
    first = live[0].n
    gold = gold_moves(f, first)
    segs, moves = variant_tree(pages, "rules")
    before = {b.n: a.n for a, b in zip(live, live[1:])}
    row = {"moves": 0, "labeled": 0, "rules_right": 0, "model_right": 0, "agree": 0, "agree_right": 0, "asked": 0}
    maybe = set(f.get("maybe") or [])
    for m in moves:
        if m.kind is MoveKind.FIRST or m.page in maybe:
            continue
        row["moves"] += 1
        want = gold.get(m.page)
        if want is None:
            continue
        row["labeled"] += 1
        chain = open_chain(segs, before.get(m.page, m.page))
        mine = move_letter(m, chain)
        row["rules_right"] += mine == want or (want == "D" and mine in "DEF" and m.kind is MoveKind.POP)
        got = probs.get(m.page)
        if got is None:
            continue
        row["asked"] += 1
        top = max(got, key=got.get)
        row["model_right"] += top == want or (want == "D" and top in "DEF")
        if top == mine:
            row["agree"] += 1
            row["agree_right"] += mine == want or (want == "D" and mine in "DEF")
    return row


def gold_pages(path: Path) -> list[dict[str, Any]]:
    """The labeled files of a gold JSON (``{"files": [{"path", "boundaries", "parts", "split"}]}``)."""
    return list(json.loads(Path(path).read_text(encoding="utf-8")).get("files") or [])


__all__ = ["DEFAULT_MODEL", "OllamaPageReader", "default_data_dir", "evaluate", "file_id", "gold_pages", "kind_chain", "load",
           "page_png", "part_accuracy", "parts_in_store", "pooled", "prf", "read_embeddings", "read_model", "read_moves", "attach_moves", "read_pages",
           "save", "segment_file", "segment_pages", "sha256_of", "stale", "store_dir", "store_path", "stored",
           "text_of_pages", "variant_breaks", "variant_starts", "variant_tree", "nesting_accuracy", "gold_moves", "evaluate_moves"]
