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

from jason.community.lexicon import Lexicon, document_term_forms, document_terms, language_of
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
    if not text:
        return lexicon
    terms = document_terms(text, lexicon)
    return lexicon.with_terms(terms, document_term_forms(text, terms))


OPTION_NAMES = ("search", "case", "terms", "real-words")


def options_for(names: Iterable[str] = (), channel: Any = None) -> Any:
    """The text rules' ``Options`` for the names a person gave (``jason intake --ocr-options search,case``): ``search``
    looks the vocabulary over for words within three edits, ``case`` sets a corrected word's capitals from its sentence and
    the document's terms, ``terms`` ranks a defined term up, ``real-words`` reads a real word as another where the context
    and the channel make the other far likelier. No names is today's behavior. ``channel`` is a learned
    ``ocr_channel.Channel`` (``learn_channel``), merged with the hand list."""
    import math

    from jason.community.ocr_correct import HAND_CHANNEL, Options
    from jason.community.ocr_vocab import available

    wanted = set(names)
    unknown = wanted - set(OPTION_NAMES)
    if unknown:
        raise ValueError(f"no OCR option {', '.join(sorted(unknown))}: {', '.join(OPTION_NAMES)}")
    return Options(channel=HAND_CHANNEL.merged(channel, "hand+learned") if channel is not None else None,
                   case_by_context="case" in wanted, term_bonus=2.0 if "terms" in wanted else 0.0,
                   search="search" in wanted and available(), real_words=0.95 if "real-words" in wanted else 0.0,
                   route_real=0.2 if "real-words" in wanted else 0.0, real_ratio=5.0, real_keep=math.log(0.995))


def channel_path(data_dir: Path) -> Path:
    return Path(data_dir) / "ocr" / "channel.json"


def load_channel(data_dir: Path) -> Any:
    """The channel ``learn_channel`` saved, or None."""
    from jason.community.ocr_channel import Channel

    path = channel_path(data_dir)
    return Channel.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.is_file() else None


def learn_channel(pairs: Iterable[tuple[str, str]], printed: Iterable[str], data_dir: Path | None = None, *,
                  min_count: int = 2) -> Any:
    """The channel counted from (as read, as printed) pairs (``ocr_channel.aligned_pairs`` of a reading and its working
    copy, or of rendered clean text read back), saved to ``data/ocr/channel.json`` when ``data_dir`` is given. Only letters
    are counted: the file holds no word of any document."""
    from jason.community.ocr_channel import learn

    channel = learn(pairs, printed, min_count=min_count)
    if data_dir is not None:
        path = channel_path(data_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(channel.to_dict(), indent=1), encoding="utf-8")
    return channel


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


def line_words(words: Sequence[dict], k: int) -> list[int]:
    """The indexes of the page words on the same line as word ``k``, in order."""
    w = words[k]
    return [n for n, x in enumerate(words) if x["page"] == w["page"] and x["block"] == w["block"] and x["line"] == w["line"]]


def line_crop(pdf: Path, words: Sequence[dict], members: Sequence[int], *, dpi: int = 300) -> str:
    """The crop of one line (the page words ``members``), as base64 PNG."""
    import base64

    import pymupdf

    line = [words[n] for n in members]
    with pymupdf.open(str(pdf)) as doc:
        page = doc[line[0]["page"]]
        x0, y0 = min(x["box"][0] for x in line), min(x["box"][1] for x in line)
        x1, y1 = max(x["box"][2] for x in line), max(x["box"][3] for x in line)
        png = page.get_pixmap(dpi=dpi, clip=pymupdf.Rect(x0 - 3, y0 - 2, x1 + 3, y1 + 2)).tobytes("png")
    return base64.b64encode(png).decode("ascii")


ROUTES = ("guarded", "doubts", "suspects")


def routed(passages: dict[str, Sequence[str]], lexicon: Lexicon, route: str = "doubts", opts: Any = None
           ) -> dict[str, list[Suggestion]]:
    """The tokens to send to the page's crop, as one-token placeholder suggestions (``vision_readings`` fills in what the
    page says): ``"doubts"`` are the suspects the text rules cannot settle (no candidate, or none the context settles) and,
    with ``opts.route_real``, real words the noisy channel doubts; ``"suspects"`` is every token the English prior doubts
    (and those real words).
    The guarded suggestions (``"guarded"``, today's) are the caller's: they are the text rules' own."""
    from jason.community.ocr_correct import DEFAULT, Fix, doubts

    if route not in ROUTES or route == "guarded":
        return {}
    opts = opts or DEFAULT
    out: dict[str, list[Suggestion]] = {}
    for section, tokens in passages.items():
        tokens = list(tokens)
        found = doubts(tokens, lexicon, opts)
        if route == "suspects":
            marks = sorted({i for i in suspects(tokens, lexicon) if re.search(r"[A-Za-z]{2,}", tokens[i])}
                           | {d.index for d in found if d.why == "real word"})
        else:
            marks = [d.index for d in found]
        if marks:
            out[section] = [Suggestion(i, i + 1, tokens[i], tokens[i], Fix.OTHER, (Method.VISION,)) for i in marks]
    return out


def usable_reading(wrong: str, read: str, lexicon: Lexicon | None) -> bool:
    """Whether the page's crop reading may stand as a suggestion for ``wrong``: a reading that holds a "?", that spans
    lines, or that is several words when the OCR read one (a crop that took in a neighbour: "reoccupy his" for
    "reoccupy") is the model wandering; and, given the lexicon, the reading must not be a suspect itself (a model that
    copies a misreading back, or invents a non-word, has read nothing a person should be asked about)."""
    if not read or read == wrong or "?" in read or "\n" in read:
        return False
    if len(read.split()) > 1 and read.replace(" ", "") != wrong:
        return False
    return not (lexicon is not None and any(lexicon.suspect(piece) for piece in read.split()))


def vision_readings(pdf: Path, words: Sequence[dict], passages: dict[str, Sequence[str]],
                    wanted: dict[str, list[Suggestion]], reader: Any, *, lexicon: Lexicon | None = None
                    ) -> dict[str, list[Suggestion]]:
    """The vision model's reading of each wanted suggestion's word, cropped from the page, as a suggestion of its
    own (the same span; its reading, whatever it is). ``wanted``: {section: suggestions to check}; one-token spans.
    With ``lexicon`` a reading must pass ``usable_reading`` (the token routed from the suspects, ``routed``, is read
    without the text rules' guess, and the crop is held to what a crop can say)."""
    from jason.community.ocr_correct import Fix

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
            if lexicon is not None:
                if not usable_reading(s.wrong, read, lexicon):
                    continue
            elif not read or read == s.wrong or "?" in read:
                continue                              # the page reads as the OCR did, or is unreadable
            fix = s.fix if s.right != s.wrong else (Fix.SPLIT if read.replace(" ", "") == s.wrong else Fix.CHARACTER)
            out.setdefault(section, []).append(Suggestion(s.start, s.end, s.wrong, read, fix, (Method.VISION,), 0.8,
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
            terms = document_terms(text, base)
            lex = base.with_terms(terms, document_term_forms(text, terms))
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


__all__ = ["OPTION_NAMES", "ROUTES", "channel_path", "corpus_texts", "crops", "learn_channel", "lexicon_for",
           "library_suggestions", "line_crop", "line_words", "load_channel", "locate", "model_readings", "options_for",
           "page_words", "routed", "suspects", "usable_reading", "vision_readings"]
