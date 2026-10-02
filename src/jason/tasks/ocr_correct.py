"""OCR post-correction in document intake: the language model's corpus, second readers, and the library's sidecars.

``jason.community.ocr_correct`` proposes; this module gathers what it needs from ``data/`` and puts the proposals
where a person sees them:

- ``lexicon_for`` builds the language model from clean text on disk: the statutes jason exported
  (``data/authorities``) and the governing documents a person keeps as Docs (``data/outlines``), never the OCR being
  corrected and never the document's own working copy, which is a second reader of the same page and would otherwise
  agree with itself.
- ``model_readings`` asks the local text model about the tokens the lexicon doubts (the marked-suspects prompt, the
  best of the prompts measured), and ``vision_readings`` asks the vision model to read the page's crop of a guarded
  suggestion (a number, an operative word). Each returns suggestions with its own method, for
  ``ocr_correct.combine``; ``tasks.intake.ocr_reading_asks`` turns the agreement into the queue's ``likely`` tier.
- ``library_suggestions`` writes ``data/library/text/<id>.ocr-suggestions.json`` beside a library file's OCR text,
  with the passage's English share as a signal of the OCR's quality. The raw text is never rewritten: a reading is
  evidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from jason.community.lexicon import Lexicon, document_terms, language_of
from jason.community.ocr_correct import Method, Suggestion, suggest


def corpus_texts(data_dir: Path, *, exclude: Iterable[str] = ()) -> list[str]:
    """Clean text for the language model: the exported statutes and the outlines of the Docs a person keeps, less
    the outlines named in ``exclude`` (keys: the document being read, so its own copy is not its judge)."""
    skip = set(exclude)
    out = []
    for path in sorted((Path(data_dir) / "authorities").rglob("*.md")):
        out.append(path.read_text(encoding="utf-8", errors="replace"))
    for path in sorted((Path(data_dir) / "outlines").glob("*.json")):
        if path.stem == "references" or path.stem in skip:
            continue
        try:
            out.append(str(json.loads(path.read_text(encoding="utf-8")).get("text") or ""))
        except ValueError:
            continue
    return out


def lexicon_for(data_dir: Path, text: str = "", *, exclude: Iterable[str] = ()) -> Lexicon:
    """The language model for reading ``text``: the corpus, with the document's own defined terms and names."""
    lexicon = Lexicon.from_texts(corpus_texts(data_dir, exclude=exclude))
    return lexicon.with_terms(document_terms(text, lexicon)) if text else lexicon


def suspects(tokens: Sequence[str], lexicon: Lexicon) -> list[int]:
    """The tokens the English prior doubts, and the ones carrying a mark no text has."""
    return [i for i, t in enumerate(tokens) if lexicon.suspect(t) or any(c in t for c in "|{}~�")]


def model_readings(passages: dict[str, Sequence[str]], lexicon: Lexicon, corrector: Any) -> dict[str, list[Suggestion]]:
    """The local text model's readings of each passage's suspect tokens (``OllamaTextCorrector.marked``), kept only
    where the edit is minimal (``ocr_models.minimal``). ``passages``: {section: tokens}."""
    from jason.community.ocr_models import minimal

    out: dict[str, list[Suggestion]] = {}
    for section, tokens in passages.items():
        marks = suspects(tokens, lexicon)
        if marks:
            out[section] = [s for s in corrector.marked(list(tokens), marks) if minimal(s)]
    return out


# The page's own words, for the vision model's crops.

def page_words(pdf: Path, cache: Path | None = None, *, dpi: int = 300) -> list[dict]:
    """Every OCR word on the scan with its page and box (PDF points), as PyMuPDF's OCR reads it (the reading a cached
    base text came from), cached as JSON beside the scan."""
    if cache is not None and cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    import pymupdf

    from jason.community.ocr import PyMuPdfTesseract

    out = []
    with pymupdf.open(str(pdf)) as doc:
        for n in range(doc.page_count):
            page = doc[n]
            textpage = page.get_textpage_ocr(dpi=dpi, language="eng", full=True, tessdata=PyMuPdfTesseract.tessdata())
            for x0, y0, x1, y1, word, block, line, _ in page.get_text("words", textpage=textpage):
                out.append({"page": n, "box": [x0, y0, x1, y1], "text": word, "block": block, "line": line})
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out), encoding="utf-8")
    return out


def locate(words: Sequence[dict], tokens: Sequence[str], i: int) -> int | None:
    """The page word that is token ``i`` of a passage: its text and a neighbor's must match, and only once."""
    tok = tokens[i]
    prev = tokens[i - 1] if i else ""
    nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
    texts = [w["text"] for w in words]
    both = [k for k, t in enumerate(texts) if t == tok and 0 < k < len(texts) - 1
            and texts[k - 1] == prev and texts[k + 1] == nxt]
    if len(both) == 1:
        return both[0]
    either = [k for k, t in enumerate(texts) if t == tok and ((k and texts[k - 1] == prev)
                                                              or (k + 1 < len(texts) and texts[k + 1] == nxt))]
    return either[0] if len(either) == 1 else None


def crops(pdf: Path, words: Sequence[dict], k: int, *, dpi: int = 300) -> tuple[str, str]:
    """The word's crop and its line's, as base64 PNG."""
    import base64

    import pymupdf

    w = words[k]
    line = [x for x in words if x["page"] == w["page"] and x["block"] == w["block"] and x["line"] == w["line"]]
    with pymupdf.open(str(pdf)) as doc:
        page = doc[w["page"]]
        x0, y0, x1, y1 = w["box"]
        word_png = page.get_pixmap(dpi=dpi, clip=pymupdf.Rect(x0 - 1.5, y0 - 1.5, x1 + 1.5, y1 + 1.5)).tobytes("png")
        lx0, ly0 = min(x["box"][0] for x in line), min(x["box"][1] for x in line)
        lx1, ly1 = max(x["box"][2] for x in line), max(x["box"][3] for x in line)
        line_png = page.get_pixmap(dpi=200, clip=pymupdf.Rect(lx0 - 2, ly0 - 2, lx1 + 2, ly1 + 2)).tobytes("png")
    return base64.b64encode(word_png).decode("ascii"), base64.b64encode(line_png).decode("ascii")


def vision_readings(pdf: Path, words: Sequence[dict], passages: dict[str, Sequence[str]],
                    wanted: dict[str, list[Suggestion]], reader: Any) -> dict[str, list[Suggestion]]:
    """The vision model's reading of each wanted suggestion's word, cropped from the page, as a suggestion of its
    own (the same span; its reading, whatever it is). ``wanted``: {section: suggestions to check}; one-token spans."""
    out: dict[str, list[Suggestion]] = {}
    for section, items in wanted.items():
        tokens = passages.get(section) or ()
        for s in items:
            if s.end - s.start != 1:
                continue
            k = locate(words, tokens, s.start)
            if k is None:
                continue
            word_png, line_png = crops(pdf, words, k)
            read = reader.read(word_png, line_png)
            if not read or read == s.wrong or "?" in read:
                continue                              # the page reads as the OCR did, or is unreadable
            out.setdefault(section, []).append(Suggestion(s.start, s.end, s.wrong, read, s.fix, (Method.VISION,), 0.8,
                                                          (f"vision: read the page's crop as \"{read}\"",)))
    return out


# The library: a sidecar of suggestions beside each OCR text, never an edit of it.

def _ocr_engine(text: str) -> str:
    m = re.search(r"- ocr: `([^`]+)`", text[:400])
    return m.group(1) if m else ""


def library_suggestions(data_dir: Path, *, kinds: Iterable[str] = (), limit: int | None = None,
                        lexicon: Lexicon | None = None, log: Callable[[str], None] | None = None) -> list[dict]:
    """For each library file whose text an OCR engine read (or a vision model re-read), the text rules' suggestions
    and the English prior's quality signal, in ``data/library/text/<id>.ocr-suggestions.json``. Returns the rows of
    the quality report, worst first."""
    import sqlite3

    db = Path(data_dir) / "library" / "library.db"
    if not db.is_file():
        return []
    with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
        rows = conn.execute("SELECT id, path, kind FROM documents").fetchall()
    wanted = set(kinds)
    base = lexicon or lexicon_for(data_dir)
    report = []
    for doc_id, path, kind in rows:
        if wanted and kind not in wanted:
            continue
        folder = Path(data_dir) / "library" / "text"
        for source in (folder / f"{doc_id}.txt", folder / f"{doc_id}.vision.txt"):
            if not source.is_file():
                continue
            text = source.read_text(encoding="utf-8", errors="replace")
            vision = source.name.endswith(".vision.txt")
            engine = "ollama-vision" if vision else _ocr_engine(text)
            if not engine:
                continue                                    # a text layer or an extract: no OCR to correct
            if text.startswith("# ") and "\n" in text:
                text = text.split("\n", 1)[1]               # jason's header line ("# name - ocr: `engine`")
            lex = base.with_terms(document_terms(text, base))
            tokens = text.split()
            lang = language_of(" ".join(tokens[:600]), lex)
            found = [] if lang.language not in ("en", "") else suggest(tokens, lex, language_check=False, tables=vision)
            before = sum(lex.suspect(t) for t in tokens)
            row = {"id": doc_id, "path": path, "kind": kind, "source": source.name, "engine": engine,
                   "language": lang.language, "english_share": round(lang.english_share, 3), "tokens": len(tokens),
                   "suspects": before, "suggestions": len(found),
                   "guarded": sum(bool(s.guard) for s in found)}
            sidecar = source.with_name(source.name.replace(".txt", "") + ".ocr-suggestions.json")
            sidecar.write_text(json.dumps({**row, "written": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                           "note": "suggestions are evidence for a person, never applied to the text; "
                                                   "start and end count whitespace tokens after the header line",
                                           "items": [_row(s) for s in found]}, indent=1), encoding="utf-8")
            report.append(row)
            if log:
                log(f"{path}: {len(found)} suggestions, {before} suspects of {len(tokens)} tokens ({engine})")
        if limit is not None and len(report) >= limit:
            break
    return sorted(report, key=lambda r: (r["suspects"] / max(1, r["tokens"])), reverse=True)


def _row(s: Suggestion) -> dict:
    row = asdict(s)
    row["fix"] = s.fix.value
    row["methods"] = [m.value for m in s.methods]
    row["guard"] = s.guard
    return row


__all__ = ["corpus_texts", "crops", "lexicon_for", "library_suggestions", "locate", "model_readings", "page_words",
           "suspects", "vision_readings"]
