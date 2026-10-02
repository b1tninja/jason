"""A fuzzer for the paper forms and the form reader: made-up answers, filled in the ways owners fill them, printed,
scanned badly, read back, and scored, so the form's design and the reader's hints are judged by what comes back.

Each **case** is drawn from a seed, so any case can be made again (``Case``):

- **answers**, made up in a **style** (plain, long, look-alike letters, punctuation, accents, capitals) from the form's
  own questions and what each holds (``FormQuestion.reads_as``); names and emails are invented (emails at the
  ``example`` domains), so no owner's information is used;
- a **fill**: typed into the PDF's fields; written by hand (a handwriting font on the printed page, each word
  a little off the line and turned, boxes marked with a pen stroke); in cursive; an emailed pre-filled copy sent back
  untouched; or one with an answer changed;
- a **scan profile**: a clean, office, or home scanner, a phone or fax, a page fed upside down, or one drawn at random
  (resolution, turn, scale, shift, blur, speckle, a faint or dark copy, JPEG);

and it is read by ``form_reader.read_scan``, then again with the reading hints (``form_hints``). Each answer is scored
the way jason compares answers (``owner_prefill.normalize``); a pre-filled copy is scored by ``owner_prefill.compare``,
as a real return is: an untouched copy must read as unchanged, an edited one as exactly that change, and a hint must
never swallow a change.

``lint`` checks the generated form without scanning: tokens left unfilled, the marker's places clear of ink, writing
space and box sizes, a label on the same page as its answer, the print margin.

Cases that fail are kept in ``data/forms/fuzz/<form>/corpus.json`` and run again by ``--replay``, so a fix is checked
against what broke before.
"""

from __future__ import annotations

import json
import random
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.forms import FormTemplate, QuestionKind, ReadAs, option_key

FONTS = Path("C:/Windows/Fonts")
HAND_FONTS = ("Inkfree.ttf", "segoepr.ttf", "mvboli.ttf", "comic.ttf")      # print, as most people write a form
CURSIVE_FONTS = ("LHANDW.TTF", "BRADHITC.TTF", "segoesc.ttf")
INKS = ((0.05, 0.05, 0.05), (0.05, 0.1, 0.45), (0.15, 0.15, 0.2))           # black and blue pens


class Fill(Enum):
    TYPED = "typed"
    HAND = "hand"
    CURSIVE = "cursive"
    PREFILLED = "prefilled"          # the emailed pre-filled copy, printed and sent back untouched
    EDITED = "edited"                # the same with one answer changed before printing


class Style(Enum):
    PLAIN = "plain"
    LONG = "long"
    LOOKALIKE = "lookalike"
    PUNCTUATION = "punctuation"
    ACCENTS = "accents"
    CAPS = "caps"


@dataclass(frozen=True)
class Profile:
    name: str
    dpi: int = 150
    angle: float = 1.0
    scale: float = 0.98
    shift: tuple[int, int] = (10, -6)
    noise: float = 0.003
    blur: float = 0.5
    jpeg: int = 70
    gamma: float = 1.0


PROFILES = {p.name: p for p in (
    Profile("clean", dpi=300, angle=0.3, scale=0.99, shift=(4, -3), noise=0.0005, blur=0.0, jpeg=90),
    Profile("office", dpi=200, angle=1.0, scale=0.98, shift=(10, -6), noise=0.002, blur=0.4, jpeg=75),
    Profile("home", dpi=150, angle=1.8, scale=0.97, shift=(18, -12), noise=0.004, blur=0.6, jpeg=60),
    Profile("phone", dpi=120, angle=2.5, scale=0.96, shift=(20, 14), noise=0.006, blur=0.9, jpeg=45, gamma=0.8),
    Profile("fax", dpi=100, angle=3.0, scale=0.97, shift=(-14, 10), noise=0.008, blur=1.0, jpeg=40, gamma=1.3),
    Profile("upside-down", dpi=150, angle=181.5, scale=0.97, shift=(12, 8), noise=0.004, blur=0.6, jpeg=60),
)}


def random_profile(rng: random.Random) -> Profile:
    return Profile("random", dpi=rng.choice((100, 120, 150, 200, 300)), angle=round(rng.uniform(-3, 3), 2),
                   scale=round(rng.uniform(0.94, 1.02), 3), shift=(rng.randint(-25, 25), rng.randint(-25, 25)),
                   noise=round(rng.uniform(0, 0.008), 4), blur=round(rng.uniform(0, 1.1), 2),
                   jpeg=rng.choice((0, 35, 50, 70, 90)), gamma=round(rng.uniform(0.75, 1.35), 2))


@dataclass(frozen=True)
class Case:
    seed: int
    fill: Fill
    style: Style
    profile: Profile

    def label(self) -> str:
        return f"#{self.seed} {self.fill.value}/{self.style.value}/{self.profile.name}"

    def as_json(self) -> dict[str, Any]:
        return {"seed": self.seed, "fill": self.fill.value, "style": self.style.value, "profile": asdict(self.profile)}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Case":
        p = dict(d["profile"])
        p["shift"] = tuple(p["shift"])
        return cls(d["seed"], Fill(d["fill"]), Style(d["style"]), Profile(**p))


# -- made-up answers ------------------------------------------------------------------------------------------------------

FIRST = {Style.PLAIN: ("Maria", "James", "Linh", "Daniel", "Priya", "Robert", "Grace", "Omar"),
         Style.LOOKALIKE: ("Lilli", "Illya", "Ollie", "Bill", "Zoltan", "Sal", "Gil", "Ilona"),
         Style.PUNCTUATION: ("Mary-Kate", "D'Andre", "Jean-Luc", "A. J.", "Ann-Marie"),
         Style.ACCENTS: ("José", "Zoë", "Siobhán", "François", "Björn", "Nguyễn Thị")}
LAST = {Style.PLAIN: ("Garcia", "Nguyen", "Patel", "Smith", "Okafor", "Chen", "Ibrahim", "Sato"),
        Style.LOOKALIKE: ("Ollila", "Lindell", "Iolo", "Bello", "Gill", "Sollis", "Oldfield"),
        Style.PUNCTUATION: ("O'Neil", "Smith-Lowell", "St. John", "McDonald Jr.", "de la Cruz"),
        Style.ACCENTS: ("Muñoz", "Lindqvist", "Ó Briain", "Çelik", "Jiménez", "Søndergaard")}
STREETS_ELSEWHERE = ("Elm Street", "Oak Ave", "Lincoln Blvd", "Willow Ct", "Main St", "Sunset Way", "Folsom Blvd")
CITIES = ("Davis, CA 95616", "Elk Grove, CA 95757", "Folsom, CA 95630", "Reno, NV 89501", "Portland, OR 97205",
          "Roseville, California 95661")
DOMAINS = ("example.com", "example.org", "example.net")


def _pool(table: dict[Style, tuple[str, ...]], style: Style) -> tuple[str, ...]:
    return table.get(style, table[Style.PLAIN])


def _person(rng: random.Random, style: Style) -> tuple[str, str]:
    return rng.choice(_pool(FIRST, style)), rng.choice(_pool(LAST, style))


def _ascii(text: str) -> str:
    import unicodedata

    return "".join(ch for ch in unicodedata.normalize("NFKD", text) if ch.isascii() and (ch.isalnum() or ch in ".-"))


def _email(rng: random.Random, style: Style, first: str, last: str) -> str:
    user = re.sub(r"\.{2,}", ".", f"{_ascii(first).lower()}.{_ascii(last).lower()}").strip(".-")
    if style is Style.LOOKALIKE:
        user += rng.choice(("01", "l1", "0o", "11", "5s"))
    elif rng.random() < 0.5:
        user += str(rng.randint(1, 99))
    if style is Style.LONG:
        user += ".household.notices"
    return f"{user}@{rng.choice(DOMAINS)}"


def _unit_address(rng: random.Random, style: Style) -> str:
    from jason.community.symbols import Street

    number, street = rng.randint(3000, 5700), rng.choice(list(Street)).value.title()
    if style is Style.LONG:
        street = street.replace(" Dr", " Drive").replace(" Ln", " Lane")
    return f"{number} {street}, Sacramento, CA 95835"


def _elsewhere(rng: random.Random, style: Style) -> str:
    if rng.random() < 0.25:
        line = f"PO Box {rng.randint(100, 9999)}"
    else:
        line = f"{rng.randint(10, 19999)} {rng.choice(STREETS_ELSEWHERE)}"
        if style in (Style.LONG, Style.PUNCTUATION) or rng.random() < 0.3:
            line += f", Apt {rng.randint(1, 40)}{rng.choice('ABC')}"
    return f"{line}, {rng.choice(CITIES)}"


def answers(form: FormTemplate, rng: random.Random, style: Style) -> dict[str, Any]:
    """Made-up answers to ``form`` in ``style``, as the fillable PDF takes them: text by field, a check box by
    ``field.option`` (True), a radio group by its option's key."""
    first, last = _person(rng, style)
    out: dict[str, Any] = {}
    for q in form.questions:
        name = q.field
        if q.kind is QuestionKind.CHECKBOX:
            chosen = [o for o in q.options if rng.random() < 0.55] or [rng.choice(q.options)]
            out.update({f"{name}.{option_key(o)}": True for o in chosen})
        elif q.kind is QuestionKind.CHOICE:
            if q.required or rng.random() < 0.6:
                out[name] = option_key(rng.choice(q.options))
        elif q.reads_as is ReadAs.NAME:
            value = f"{first} {last}"
            if style is Style.LONG or rng.random() < 0.25:
                other = _person(rng, style)[0]
                value = f"{first} {last} and {other} {last}"
            out[name] = value
        elif q.reads_as is ReadAs.ADDRESS and q.prefill:
            out[name] = _unit_address(rng, style)
        elif q.reads_as is ReadAs.ADDRESS:
            if q.required or rng.random() < 0.45:
                out[name] = _elsewhere(rng, style)
        elif q.reads_as is ReadAs.EMAIL:
            if q.required or rng.random() < 0.7:
                out[name] = _email(rng, style, first, last)
        elif q.reads_as is ReadAs.PHONE:
            if q.required or rng.random() < 0.5:
                out[name] = rng.choice(("({a}) {b}-{c}", "{a}-{b}-{c}", "{a}.{b}.{c}")).format(
                    a=rng.choice((916, 530, 707)), b=rng.randint(200, 999), c=f"{rng.randint(0, 9999):04d}")
        elif q.reads_as is ReadAs.CONTACT:
            if rng.random() < 0.3:
                f2, l2 = _person(rng, style)
                out[name] = f"{f2} {l2}, " + (_email(rng, style, f2, l2) if rng.random() < 0.5 else _elsewhere(rng, style))
        elif q.required or rng.random() < 0.5:
            out[name] = f"{first} {last}"
    if style is Style.CAPS:                          # a radio group's value stays its option key
        choices = {q.field for q in form.questions if q.kind is QuestionKind.CHOICE}
        out = {k: v.upper() if isinstance(v, str) and k not in choices else v for k, v in out.items()}
    return out


# -- filling ---------------------------------------------------------------------------------------------------------------

def _hand_font(rng: random.Random, cursive: bool) -> Path:
    names = [n for n in (CURSIVE_FONTS if cursive else HAND_FONTS) if (FONTS / n).is_file()]
    if not names:
        raise FileNotFoundError(f"no handwriting font in {FONTS}")
    return FONTS / rng.choice(names)


def _lines_for(text: str, width: float, font: Any, size: float, rows: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = f"{line} {w}".strip()
        if line and font.text_length(trial, fontsize=size) > width and len(lines) < rows - 1:
            lines.append(line)
            line = w
        else:
            line = trial
    return lines + [line] if line else lines


def write_by_hand(blank: Path, layout: Any, values: dict[str, Any], out: Path, rng: random.Random, *,
                  cursive: bool = False) -> list[str]:
    """``values`` written on the printed form as a person writes: a handwriting font, each word a little off the line
    and turned, the size shrunk to fit where it must, boxes marked with a pen stroke. Returns the fields whose writing
    did not fit the space (a design finding)."""
    import pymupdf

    from jason.community.pdf_fields import flatten, split_lines

    # an answer with a line a field (an address) is written a line on each, as a person writes it on the form
    values = split_lines(values, {b.name for b in layout.fields})
    font_path = _hand_font(rng, cursive)
    font = pymupdf.Font(fontfile=str(font_path))
    ink = rng.choice(INKS)
    overflow = []
    with tempfile.TemporaryDirectory() as tmp:
        flat = flatten(blank, Path(tmp) / "flat.pdf")
        with pymupdf.open(flat) as doc:
            for box in layout.fields:
                number = layout.page_numbers[box.page] if box.page < len(layout.page_numbers) else box.page
                page = doc[number]
                page.insert_font(fontname="hand", fontfile=str(font_path))
                x0, y0, x1, y1 = box.rect
                if box.kind in ("checkbox", "radio"):
                    marked = values.get(box.name) is True if box.kind == "checkbox" else values.get(box.name) == box.option
                    if marked:
                        _pen_mark(page, (x0, y0, x1, y1), rng, ink)
                    continue
                text = str(values.get(box.name) or "")
                if not text:
                    continue
                rows = max(1, int((y1 - y0) // 14))
                size = rng.uniform(10.5, 13.0)
                lines = _lines_for(text, x1 - x0 - 4, font, size, rows)
                while size > 7 and (len(lines) > rows or max(font.text_length(l, fontsize=size) for l in lines) > x1 - x0 - 4):
                    size -= 0.5
                    lines = _lines_for(text, x1 - x0 - 4, font, size, rows)
                if len(lines) > rows or max(font.text_length(l, fontsize=size) for l in lines) > x1 - x0 - 4:
                    overflow.append(box.name)
                step = (y1 - y0) / rows
                for row, line in enumerate(lines[:rows]):
                    x = x0 + rng.uniform(1, 6)
                    base = y0 + step * (row + 1) - rng.uniform(1.5, 3.0)
                    for word in line.split():
                        y = base + rng.uniform(-0.8, 0.8)
                        page.insert_text((x, y), word, fontname="hand", fontsize=size * rng.uniform(0.95, 1.05),
                                         color=ink, morph=(pymupdf.Point(x, y), pymupdf.Matrix(rng.uniform(-2.5, 2.5))))
                        x += font.text_length(word + " ", fontsize=size) * rng.uniform(0.98, 1.12)
            doc.save(out)
    return overflow


def _pen_mark(page: Any, rect: tuple[float, float, float, float], rng: random.Random, ink: tuple[float, ...]) -> None:
    """An X or a check across a box, as a pen makes it: past the edges a little, never quite straight."""
    import pymupdf

    x0, y0, x1, y1 = rect
    j = lambda: rng.uniform(-1.2, 1.2)                               # noqa: E731
    width = rng.uniform(0.9, 1.7)
    if rng.random() < 0.6:
        page.draw_line(pymupdf.Point(x0 + j(), y0 + j()), pymupdf.Point(x1 + j(), y1 + j()), color=ink, width=width)
        page.draw_line(pymupdf.Point(x1 + j(), y0 + j()), pymupdf.Point(x0 + j(), y1 + j()), color=ink, width=width)
    else:
        mid = (x0 + (x1 - x0) * 0.4 + j(), y1 + j() * 0.5)
        page.draw_polyline([pymupdf.Point(x0 + j(), y0 + (y1 - y0) * 0.5 + j()), pymupdf.Point(*mid),
                            pymupdf.Point(x1 + 2 + j(), y0 - 2 + j())], color=ink, width=width)


# -- one case ----------------------------------------------------------------------------------------------------------------

@dataclass
class FieldResult:
    field: str
    want: Any
    got: Any
    hinted: Any
    right: bool
    right_hinted: bool
    similarity: float           # 0 to 1, the reading against the answer once both are normalized


@dataclass
class CaseResult:
    case: Case
    fields: list[FieldResult] = field(default_factory=list)
    marker_how: str = ""
    marker_right: bool = False
    aligned: bool = True
    residual: float = 0.0       # the alignment's mean error, points
    overflow: list[str] = field(default_factory=list)
    compare_raw: dict[str, str] = field(default_factory=dict)
    compare_hinted: dict[str, str] = field(default_factory=dict)
    expect: dict[str, str] = field(default_factory=dict)        # what compare should say, for a pre-filled copy
    error: str = ""

    @property
    def share(self) -> float:
        return sum(f.right for f in self.fields) / len(self.fields) if self.fields else 0.0

    @property
    def share_hinted(self) -> float:
        return sum(f.right_hinted for f in self.fields) / len(self.fields) if self.fields else 0.0

    @property
    def failed(self) -> bool:
        """Kept in the corpus: a case that broke, a page that did not align, a typed answer misread, or a pre-filled copy
        not read as it should be. Handwriting OCR misses are expected (the vision model's work) and not kept."""
        typed = self.case.fill not in (Fill.HAND, Fill.CURSIVE)
        return bool(self.error) or not self.aligned or (typed and any(not f.right_hinted for f in self.fields)) or (
            bool(self.expect) and self.compare_hinted != self.expect)


def _norm(key: str, value: Any) -> str:
    from jason.tasks.owner_prefill import normalize

    if isinstance(value, (list, tuple)):
        value = " ".join(map(str, value))
    return normalize(key, value)


def _score(form: FormTemplate, filled: dict[str, Any], reading: Any, hinted: Any) -> list[FieldResult]:
    import difflib

    out = []
    for q in form.questions:
        names = [f"{q.field}.{option_key(o)}" for o in q.options] if q.kind is QuestionKind.CHECKBOX else [q.field]
        for name in names:
            want = filled.get(name, False if q.kind is QuestionKind.CHECKBOX else "")
            got = (reading.fields.get(name).value if reading.fields.get(name) else None)
            hint = (hinted.fields.get(name).value if hinted.fields.get(name) else None)
            if q.kind is QuestionKind.CHECKBOX:
                got, hint = bool(got), bool(hint)
                right, right_h, sim = got == bool(want), hint == bool(want), float(got == bool(want))
            else:
                w, g, h = _norm(name, want), _norm(name, got or ""), _norm(name, hint or "")
                right, right_h = w == g, w == h
                sim = difflib.SequenceMatcher(None, w, g).ratio() if (w or g) else 1.0
            out.append(FieldResult(name, want, got, hint, right, right_h, round(sim, 3)))
    return out


def _prefill(form: FormTemplate, values: dict[str, Any]) -> Any:
    """The made-up answers as a pre-filled copy's values (``owner_prefill.Prefill``): text, boxes, a choice as its
    option."""
    from jason.tasks.owner_prefill import Prefill

    choices = {q.field: q for q in form.questions if q.kind is QuestionKind.CHOICE}
    vals = {k: (choices[k].option_for(v) if k in choices else v) for k, v in values.items()}
    return Prefill(unit_id=0, unit=str(values.get("unit-address", "")), membership_id=0,
                   name=str(values.get("name", "")), values=vals)


def run_case(case: Case, form: FormTemplate, blank: Path, layout: Any, work: Path, *, model: Any = None) -> CaseResult:
    """One case: answers made, filled, marked, scanned, read raw and with hints, and scored."""
    import copy

    from jason.community import form_hints
    from jason.community.fillable import stamp_reference
    from jason.community.form_reader import read_scan
    from jason.community.form_refs import Channel, make
    from jason.community.pdf_fields import fill
    from jason.tasks.form_scans import simulate
    from jason.tasks.owner_prefill import compare, fill_pdf, fingerprints

    rng = random.Random(case.seed)
    result = CaseResult(case)
    values = answers(form, rng, case.style)
    filled = work / f"case-{case.seed}.pdf"
    expected: dict[str, Any] = {}
    sent: dict[str, Any] = {}
    try:
        if case.fill in (Fill.PREFILLED, Fill.EDITED):
            p = _prefill(form, values)
            sent = fingerprints(p)
            sent["unit"] = p.unit
            expected = {k: v for k, v in p.values.items() if isinstance(v, str)}
            if case.fill is Fill.EDITED:
                texts = [k for k, v in values.items() if isinstance(v, str) and k in {q.field for q in form.questions
                         if q.kind not in (QuestionKind.CHOICE, QuestionKind.CHECKBOX)}]
                key = rng.choice(texts)
                fresh = answers(form, random.Random(case.seed + 10**6), case.style)
                new = fresh.get(key) or _elsewhere(rng, case.style)
                values = {**values, key: new if new != values[key] else new + " 2"}
                result.expect = {k: "unchanged" for k in sent["fields"]}
                result.expect[key] = "changed"
            else:
                result.expect = {k: "unchanged" for k in sent["fields"]}
            fill_pdf(blank, _prefill(form, values), filled, form)
            stamp_reference(filled, make(form.code, 2027, Channel.EMAIL, membership_id=case.seed, unit_id=1).text)
            marker = make(form.code, 2027, Channel.EMAIL, membership_id=case.seed, unit_id=1)
        elif case.fill is Fill.TYPED:
            fill(blank, values, filled, multiline_size=form.style.typed_size)
            marker = make(form.code, 2027, Channel.MAIL)
            stamp_reference(filled, marker.text)
        else:
            marker = make(form.code, 2027, Channel.MAIL)
            stamped = work / f"blank-{case.seed}.pdf"
            shutil.copyfile(blank, stamped)
            stamp_reference(stamped, marker.text)
            result.overflow = write_by_hand(stamped, layout, values, filled, rng, cursive=case.fill is Fill.CURSIVE)
        p = case.profile
        scan = simulate(filled, work / f"scan-{case.seed}.pdf", dpi=p.dpi, angle=p.angle, scale=p.scale, shift=p.shift,
                        noise=p.noise, seed=case.seed, blur=p.blur, jpeg=p.jpeg, gamma=p.gamma)
        reading = read_scan(scan, form, layout, model=model)
        result.aligned = not any("could not align" in n for n in reading.notes)
        result.residual = round(reading.residual, 2)
        result.marker_how, result.marker_right = reading.reference_how, reading.reference == marker.text
        hinted = form_hints.apply(copy.deepcopy(reading), form, form_hints.community_hints(expected))
        result.fields = _score(form, values, reading, hinted)
        if sent:
            result.compare_raw = compare(sent, reading.answers(form).answers, form)
            result.compare_hinted = compare(sent, hinted.answers(form).answers, form)
    except Exception as exc:                          # a case that breaks the pipeline is itself a finding
        result.error = f"{type(exc).__name__}: {exc}"
    return result


def cases(seed: int, count: int, *, fills: list[Fill], styles: list[Style], profiles: list[str]) -> list[Case]:
    """``count`` cases drawn from ``seed``: each fill, style, and profile in turn, so a small run still covers them."""
    rng = random.Random(seed)
    out = []
    for n in range(count):
        name = profiles[n % len(profiles)]
        profile = random_profile(rng) if name == "random" else PROFILES[name]
        out.append(Case(seed * 1000 + n, fills[n % len(fills)], styles[(n // len(fills)) % len(styles)], profile))
    return out


# -- static checks of the form -------------------------------------------------------------------------------------------

@dataclass
class Finding:
    kind: str
    where: str
    detail: str


def lint(pdf: Path, layout: Any, form: FormTemplate) -> list[Finding]:
    """The generated form checked without scanning it."""
    import pymupdf

    from jason.community import form_marks

    out: list[Finding] = []
    with pymupdf.open(pdf) as doc:
        for number, page in enumerate(doc):
            text = page.get_text()
            for token in sorted(set(re.findall(r"\[[A-Z][A-Z _]+\]|\{[A-Z][A-Z_:]+\}", text))):
                out.append(Finding("token left unfilled", f"page {number + 1}", token))
            w, h = page.rect.width, page.rect.height
            x, y = form_marks.ORIGIN
            places = {"bar mark": pymupdf.Rect(x - 2, y - 2, x + 162, y + 3 * form_marks.TRACKER + 2),
                      "printed marker": pymupdf.Rect(w - 242, 10, w - 22, 32)}
            for name, rect in places.items():
                pix = page.get_pixmap(dpi=72, clip=rect, colorspace=pymupdf.csGRAY)
                if sum(1 for b in pix.samples if b < 200) > 3:
                    out.append(Finding("marker place not clear", f"page {number + 1}", f"ink where the {name} goes"))
            margin = 4.5                                   # Lob: 1/16 inch clear on every side
            for block in page.get_text("blocks"):
                bx0, by0, bx1, by1 = block[:4]
                if bx0 < margin or by0 < margin or bx1 > w - margin or by1 > h - margin:
                    out.append(Finding("inside the print margin", f"page {number + 1}", str(block[4])[:40]))
            mono: set[str] = set()                                 # the style's print rules, by what the page prints
            dark: list[float] = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        text, font = span["text"].strip(), span["font"].casefold()
                        if text and any(m in font for m in ("courier", "mono", "consol", "ocr")):
                            mono.add(span["font"])
                        if text and set(text) == {"_"} and len(text) >= 8:
                            c = span["color"]
                            gray = (((c >> 16) & 255) + ((c >> 8) & 255) + (c & 255)) / 3 / 255
                            if gray < form.style.line_gray - 0.15:
                                dark.append(gray)
            if mono:
                out.append(Finding("monospaced type", f"page {number + 1}",
                                   f"{', '.join(sorted(mono))}: the reader aligns by the printed lines and reads "
                                   "monospaced type poorly (Courier broke alignment in the layout lab)"))
            if dark:
                out.append(Finding("writing lines dark", f"page {number + 1}",
                                   f"{len(dark)} at gray {min(dark):.2f}; the style asks {form.style.line_gray:.2f}"))
            for w in page.widgets() or []:
                if w.field_type == pymupdf.PDF_WIDGET_TYPE_TEXT and w.text_fontsize and \
                        w.text_fontsize < form.style.typed_size - 0.1:
                    out.append(Finding("typed answer small", w.field_name,
                                       f"{w.text_fontsize:g} points; the style asks {form.style.typed_size:g}"))
    titles = {q.field: q.title.replace("(optional)", "").strip() for q in form.questions}
    for box in layout.fields:
        x0, y0, x1, y1 = box.rect
        q = box.name.split(".")[0]
        if box.kind == "text" and y1 - y0 < form.style.write_height - 2:
            out.append(Finding("writing space short", box.name,
                               f"{y1 - y0:.0f} points tall; the style asks {form.style.write_height:g} "
                               "(at 14 a third of the writing left its space in the layout lab)"))
        if box.kind in ("checkbox", "radio") and min(x1 - x0, y1 - y0) < 8:
            out.append(Finding("box small", box.name, f"{min(x1 - x0, y1 - y0):.0f} points; a pen mark needs about 8"))
        title = titles.get(q, "")
        on = [a for a in layout.anchors if title and title[:24].casefold() in a.text.casefold()]
        if on and all(a.page != box.page for a in on):
            out.append(Finding("label on another page", box.name, f"the question is on page {on[0].page + 1}"))
    return out


# -- the report ----------------------------------------------------------------------------------------------------------------

def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "–"


def report(results: list[CaseResult], findings: list[Finding], *, form: FormTemplate, seed: int, today: str) -> str:
    from collections import Counter, defaultdict

    lines = [f"# Form fuzz: {form.title}", "",
             f"{len(results)} cases from seed {seed}, {today}. Answers are made up (no owner's information). Each answer "
             "is scored the way jason compares answers; **raw** is the scan reader alone, **hinted** adds the reading "
             "hints (what was sent, what each answer holds, the street names).", ""]
    errors = [r for r in results if r.error]
    lines += ["## By fill and scan", "", "| Fill | Scan | Cases | Aligned | Mean error (pt) | Answers right, raw | Hinted | Marker read |",
              "|---|---|---|---|---|---|---|---|"]
    groups: dict[tuple[str, str], list[CaseResult]] = defaultdict(list)
    for r in results:
        groups[(r.case.fill.value, r.case.profile.name)].append(r)
    for (fill_, prof), rs in sorted(groups.items()):
        n = sum(len(r.fields) for r in rs)
        fit = [r.residual for r in rs if r.aligned and not r.error]
        lines.append(f"| {fill_} | {prof} | {len(rs)} | {_pct(sum(r.aligned and not r.error for r in rs), len(rs))} | "
                     f"{(sum(fit) / len(fit)) if fit else 0:.1f} | "
                     f"{_pct(sum(f.right for r in rs for f in r.fields), n)} | "
                     f"{_pct(sum(f.right_hinted for r in rs for f in r.fields), n)} | "
                     f"{_pct(sum(r.marker_right for r in rs), len(rs))} |")
    by_field: dict[str, list[FieldResult]] = defaultdict(list)
    for kind, fills in (("typed (typed, pre-filled, edited)", (Fill.TYPED, Fill.PREFILLED, Fill.EDITED)),
                        ("handwritten (print and cursive)", (Fill.HAND, Fill.CURSIVE))):
        part: dict[str, list[FieldResult]] = defaultdict(list)
        for r in results:
            if r.aligned and r.case.fill in fills:
                for f in r.fields:
                    part[f.field].append(f)
                    if kind.startswith("typed"):
                        by_field[f.field].append(f)
        if not part:
            continue
        lines += ["", f"## By answer, {kind}", "", "| Answer | Read right, raw | Hinted | Mean likeness | A misread |",
                  "|---|---|---|---|---|"]
        for name, fs in part.items():
            wrong = next((f for f in fs if not f.right_hinted and isinstance(f.want, str) and f.want), None)
            example = f"`{wrong.want}` read `{wrong.hinted or ''}`" if wrong else ""
            lines.append(f"| {name} | {_pct(sum(f.right for f in fs), len(fs))} | "
                         f"{_pct(sum(f.right_hinted for f in fs), len(fs))} | {sum(f.similarity for f in fs) / len(fs):.2f} "
                         f"| {example.replace('|', '/')} |")
    lines += ["", "## By style of answer", "", "| Style | Answers right, raw | Hinted |", "|---|---|---|"]
    by_style: dict[str, list[FieldResult]] = defaultdict(list)
    for r in results:
        if r.aligned:
            by_style[r.case.style.value] += [f for f in r.fields if isinstance(f.want, str) and f.want]
    for style, fs in by_style.items():
        lines.append(f"| {style} | {_pct(sum(f.right for f in fs), len(fs))} | {_pct(sum(f.right_hinted for f in fs), len(fs))} |")
    pre = [r for r in results if r.expect and not r.error and r.aligned]
    if pre:
        lines += ["", "## Pre-filled copies, as `compare` reads them", "",
                  "| Fill | Cases | Read exactly as expected, raw | Hinted | False changes, raw | Hinted | Changes the hints swallowed |",
                  "|---|---|---|---|---|---|---|"]
        for fill_ in (Fill.PREFILLED, Fill.EDITED):
            rs = [r for r in pre if r.case.fill is fill_]
            if not rs:
                continue
            false_raw = sum(sum(1 for k, v in r.compare_raw.items() if v != "unchanged" and r.expect.get(k) == "unchanged")
                            for r in rs)
            false_h = sum(sum(1 for k, v in r.compare_hinted.items() if v != "unchanged" and r.expect.get(k) == "unchanged")
                          for r in rs)
            swallowed = sum(sum(1 for k, v in r.expect.items() if v == "changed" and r.compare_hinted.get(k) == "unchanged")
                            for r in rs)
            lines.append(f"| {fill_.value} | {len(rs)} | {_pct(sum(r.compare_raw == r.expect for r in rs), len(rs))} | "
                         f"{_pct(sum(r.compare_hinted == r.expect for r in rs), len(rs))} | {false_raw} | {false_h} | {swallowed} |")
    hows = Counter(r.marker_how or "none" for r in results if not r.error)
    lines += ["", "## The marker", "", "How the marker was read: " + ", ".join(f"{k} {v}" for k, v in hows.most_common()) + ".",
              "A marker is a hint; nothing above depends on it."]
    overflow = Counter(n for r in results for n in r.overflow)
    lines += ["", "## Design findings", ""]
    design = [Finding("writing did not fit", n, f"{c} handwritten cases shrank to 7 points and still overflowed")
              for n, c in overflow.most_common()]
    for name, fs in by_field.items():                 # typed answers: what the form and the reader control
        if len(fs) >= 4 and sum(f.right_hinted for f in fs) / len(fs) < 0.7:
            design.append(Finding("typed answer read poorly", name,
                                  f"{_pct(sum(f.right_hinted for f in fs), len(fs))} right with hints; a larger type size "
                                  "for the pre-filled value or a reading hint for what it holds would help"))
    for prof in sorted({r.case.profile.name for r in results}):
        rs = [r for r in results if r.case.profile.name == prof and not r.error]
        if rs and sum(r.aligned for r in rs) < len(rs):
            design.append(Finding("alignment failed", prof,
                                  f"{len(rs) - sum(r.aligned for r in rs)} of {len(rs)} pages: OCR could not read enough "
                                  "printed lines; registration marks in the corners would align a page without OCR"))
    for f in findings + design:
        lines.append(f"- **{f.kind}** ({f.where}): {f.detail}")
    if not findings and not design:
        lines.append("None.")
    if errors:
        lines += ["", "## Cases that broke", ""] + [f"- {r.case.label()}: {r.error}" for r in errors[:20]]
    return "\n".join(lines) + "\n"


# -- the corpus of failing cases ---------------------------------------------------------------------------------------------

def corpus_path(data_dir: Path, form: FormTemplate) -> Path:
    return Path(data_dir) / "forms" / "fuzz" / form.key.value / "corpus.json"


def load_corpus(data_dir: Path, form: FormTemplate) -> list[Case]:
    path = corpus_path(data_dir, form)
    return [Case.from_json(d) for d in json.loads(path.read_text(encoding="utf-8"))] if path.is_file() else []


def save_corpus(data_dir: Path, form: FormTemplate, failed: list[Case]) -> Path:
    """Add the failing cases to the corpus (each kept once, by its seed, fill, style, and scan)."""
    path = corpus_path(data_dir, form)
    known = {json.dumps(c.as_json(), sort_keys=True): c for c in load_corpus(data_dir, form)}
    known.update({json.dumps(c.as_json(), sort_keys=True): c for c in failed})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([c.as_json() for c in known.values()], indent=1), encoding="utf-8")
    return path


__all__ = ["Case", "CaseResult", "Fill", "Finding", "PROFILES", "Profile", "Style", "answers", "cases", "lint",
           "load_corpus", "random_profile", "report", "run_case", "save_corpus", "write_by_hand"]
