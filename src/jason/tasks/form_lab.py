"""The form layout lab: which way of drawing a form's answer spaces comes back readable, and keeps people's writing where
it belongs.

A **layout** (``Layout``) is one way to draw the same questions: how an answer's space is marked (a line beneath, a box,
a shaded band, a comb, a box for each character, or nothing), the weight and tone of its lines, its height, where the
label and the help go, the space between questions, the label's typeface and size, the size typed answers print at, and
the check boxes' size and spacing. ``render`` draws the lab form (name, unit address, mailing address, email, phone,
two check boxes, a three-way choice) in a layout as a fillable PDF the scan reader can read.

A **responder** (``Writer``) fills it in. How a person writes depends on what the space tells them, and that is a model,
stated here so it can be argued with and tuned against real returns, not a measurement:

- a **line beneath** says where to write but not how high: people write on it at their own size, letters' tails cross
  it, and a long answer runs on past its end;
- a **box** or **shaded band** says how high and how wide: people shrink their writing to fit, down to about three
  quarters of their size, and a box too short for their writing makes them write over its edges;
- **a box for each character** keeps letters apart, which recognition needs most (NIST's IRS form study, Garris and
  Dimmick 1996: 11% of characters wrong in one long box, 9% in boxes that share their sides, 6% in boxes spaced apart),
  but a long answer runs out of boxes;
- a **comb** (a line with ticks) is followed only some of the time;
- **nothing** leaves the baseline to wander;
- a heavier, darker edge is noticed more and kept to more often (``salience``); a pale one less.

Each writer (neat print, hurried print, cursive) has its own size, unsteadiness, and care for edges. Typed answers are
the fourth responder.

A **battery** (``battery``) is the same cases for every layout (common random numbers: made-up answers, writers, scan
profiles from ``form_fuzz``), so layouts are compared on identical work. ``evaluate`` scores a layout:

- **readability**: each answer read back (``form_reader``, then the reading hints, ``form_hints``) against what was
  written, as jason compares answers; full credit for the same answer, half credit times the likeness otherwise;
- **containment**: how much writing landed on printed text (a label, help) or outside its space, from where the
  writer put each word;
- **space**: how much of the page the questions take, so a layout cannot win by being enormous.

``search`` is a coordinate descent over the layout's settings from the current form's style: each setting is tried at
each of its values with the others held, the best kept, until a pass changes nothing.

``benchmark`` runs readers on the same battery: Tesseract alone, with the hints, and local vision models through Ollama
(the scan reader's prompt and schema), each scored the same way.
"""

from __future__ import annotations

import json
import random
import tempfile
import time
from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

from jason.community.forms import FormKey, FormQuestion, FormTemplate, QuestionKind, ReadAs, option_key

PAGE = (612.0, 792.0)
MARGIN = 54.0
TTF = {"arial": "arial.ttf", "verdana": "verdana.ttf", "georgia": "georgia.ttf", "segoe": "segoeui.ttf",
       "calibri": "calibri.ttf"}
BASE14 = {"helv": "helv", "times": "tiro", "courier": "cour"}


class FieldStyle(Enum):
    RULE = "rule"              # a line beneath
    BOX = "box"
    SHADED = "shaded"          # a pale band, no edge
    COMB = "comb"              # a line beneath with ticks
    CHAR_BOXES = "char-boxes"  # a box for each character, spaced apart
    OPEN = "open"              # nothing


class Place(Enum):
    ABOVE = "above"
    LEFT = "left"                     # tabular: labels in a left column, the spaces aligned in a right one
    BELOW = "below"                   # a caption under the line, as a signature line is captioned
    INSIDE = "inside"                 # a small caption in the top-left corner of a ruled cell, as tax forms do
    NONE = "none"


@dataclass(frozen=True)
class Layout:
    style: FieldStyle = FieldStyle.RULE
    weight: float = 0.5               # line weight, points
    tone: float = 0.0                 # 0 black to 1 white, for the field's lines
    height: float = 17.0              # writing space, points
    label: Place = Place.ABOVE
    help: Place = Place.ABOVE         # between the label and the space, under the space, or not printed
    gap: float = 12.0                 # space between questions, points
    font: str = "helv"
    size: float = 11.0                # the label's size
    value_size: float = 10.0          # what typed answers print at
    box: float = 11.0                 # a check box's side
    box_gap: float = 50.0             # from one option's box to the next option's
    columns: int = 1                  # 2: short answers side by side, as ``pairs`` says
    pairs: str = "contact"            # with 2 columns: "contact" (email and phone) or "every" short answer that fits
                                      # half a line (the 2024 Resident Registration form's two regions a line)
    email_style: FieldStyle | None = None    # the email's own style (None: ``style``)
    phone_style: FieldStyle | None = None    # the phone number's own style (None: ``style``)

    def style_for(self, name: str) -> FieldStyle:
        own = {"email": self.email_style, "phone": self.phone_style}.get(name)
        return own or self.style

    def key(self) -> str:
        return ";".join(f"{k}={v.value if isinstance(v, Enum) else v}" for k, v in asdict(self).items())

    def as_json(self) -> dict[str, Any]:
        return {k: (v.value if isinstance(v, Enum) else v) for k, v in asdict(self).items()}

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "Layout":
        own = {k: FieldStyle(d[k]) if d.get(k) else None for k in ("email_style", "phone_style")}
        return cls(**{**d, **own, "style": FieldStyle(d["style"]), "label": Place(d["label"]), "help": Place(d["help"])})


CURRENT = Layout()                    # the owner form's style today: a thin black line, labels and help above

# The values coordinate descent tries for each setting.
SPACE = {
    "style": list(FieldStyle),
    "email_style": [None, *FieldStyle],
    "phone_style": [None, *FieldStyle],
    "weight": [0.5, 1.0, 1.5, 2.5],
    "tone": [0.0, 0.35, 0.6],
    "height": [14.0, 17.0, 22.0, 28.0],
    "label": [Place.ABOVE, Place.LEFT, Place.BELOW, Place.INSIDE],
    "help": [Place.ABOVE, Place.BELOW, Place.NONE],
    "gap": [6.0, 12.0, 18.0],
    "font": ["helv", "times", "courier", "arial", "verdana", "georgia"],
    "size": [9.0, 11.0, 13.0],
    "value_size": [8.0, 10.0, 12.0],
    "box": [8.0, 11.0, 14.0],
    "box_gap": [30.0, 50.0, 80.0],
    "columns": [1, 2],
    "pairs": ["contact", "every"],
}

# Which answers share a line with two columns. "every" pairs what fits half a line; an address to mail to keeps the
# whole line, as on the 2024 form.
PAIRS = {"contact": {"email": "phone"}, "every": {"owner-names": "unit-address", "email": "phone"}}

LAB_FORM = FormTemplate(
    key=FormKey.OWNER_INFO,          # the layout's name only; the lab form is never sent
    title="Form layout trial",
    authority="",
    description="A trial of answer-space layouts; never sent.",
    questions=(
        FormQuestion("Owner name(s)", key="owner-names", reads=ReadAs.NAME, help="As shown on the deed."),
        FormQuestion("Unit address", key="unit-address", reads=ReadAs.ADDRESS, help="Street address of the unit."),
        FormQuestion("Mailing address for notices", key="mailing-address", reads=ReadAs.ADDRESS, required=False,
                     help="Only if it is not your unit address."),
        FormQuestion("Email address", QuestionKind.EMAIL, key="email", required=False,
                     help="Only if you choose email."),
        FormQuestion("Phone number", QuestionKind.PHONE, key="phone", required=False, help="A number we can call."),
        FormQuestion("How should notices reach you?", QuestionKind.CHECKBOX, key="delivery",
                     options=("By mail", "By email")),
        FormQuestion("Is your unit", QuestionKind.CHOICE, key="occupancy",
                     options=("Owner-occupied", "Rented out", "Vacant")),
    ),
)
INTRO = ("Please print clearly. This trial form has the same kinds of questions as the Association's owner "
         "information form: names, addresses, an email, a phone number, and boxes to mark.")


# -- drawing a layout ---------------------------------------------------------------------------------------------------

@dataclass
class Drawn:
    """Where a rendered layout put things: each field's space (points), the printed words, the height used."""
    fields: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    pitches: dict[str, float] = field(default_factory=dict)
    cells: dict[str, list[tuple[float, float, float, float]]] = field(default_factory=dict)
    printed: list[tuple[float, float, float, float]] = field(default_factory=list)
    used: float = 0.0                 # the questions' height, points


def _font(page: Any, layout: Layout) -> tuple[str, Any]:
    """The label font's name on ``page`` and a ``pymupdf.Font`` to measure with."""
    import pymupdf

    if layout.font in BASE14:
        name = BASE14[layout.font]
        return name, pymupdf.Font(name)
    path = Path("C:/Windows/Fonts") / TTF[layout.font]
    page.insert_font(fontname="lab", fontfile=str(path))
    return "lab", pymupdf.Font(fontfile=str(path))


def _edge(layout: Layout) -> tuple[float, float, float]:
    return (layout.tone, layout.tone, layout.tone)


def _space(page: Any, layout: Layout, rect: Any, name: str, drawn: Drawn, lines: int = 1) -> None:
    """Draw an answer's space in the layout's style over ``rect``."""
    import pymupdf

    color, w = _edge(layout), layout.weight
    x0, y0, x1, y1 = rect
    if layout.style is FieldStyle.RULE:
        step = (y1 - y0) / lines
        for i in range(1, lines + 1):
            page.draw_line((x0, y0 + step * i), (x1, y0 + step * i), color=color, width=w)
    elif layout.style is FieldStyle.BOX:
        page.draw_rect(pymupdf.Rect(rect), color=color, width=w)
    elif layout.style is FieldStyle.SHADED:
        shade = 0.9 + 0.08 * layout.tone
        page.draw_rect(pymupdf.Rect(rect), color=None, fill=(shade, shade, shade), width=0)
    elif layout.style is FieldStyle.COMB:
        pitch = max(12.0, (y1 - y0) * 0.75)
        page.draw_line((x0, y1), (x1, y1), color=color, width=w)
        x = x0
        while x <= x1 + 0.1:
            page.draw_line((x, y1), (x, y1 - (y1 - y0) * 0.4), color=color, width=w)
            x += pitch
        drawn.pitches[name] = pitch
    elif layout.style is FieldStyle.CHAR_BOXES:
        row = (y1 - y0) / lines
        side = row - (3 if lines > 1 else 0)
        pitch = side * 1.25                  # spaced apart: a quarter of a box between boxes
        cells = []
        for r in range(lines):               # square boxes, a row for each line, read row after row
            x, top = x0, y0 + r * row
            while x + side <= x1 + 0.1:
                cells.append((x, top, x + side, top + side))
                page.draw_rect(pymupdf.Rect(x, top, x + side, top + side), color=color, width=w)
                x += pitch
        drawn.pitches[name], drawn.cells[name] = pitch, cells


def _text_question(page: Any, doc: Any, layout: Layout, fontname: str, font: Any, q: FormQuestion, label: str,
                   x0: float, x1: float, y: float, drawn: Drawn, help_size: float) -> float:
    """One written answer between ``x0`` and ``x1`` from ``y``, its label placed the layout's way; returns where it
    ends.

    - ABOVE: the label, the help, then the space.
    - LEFT (tabular): the label in a left column, the space in the right column on the label's line, the help under it.
    - BELOW (caption): the space, then the label as a small caption under its line, the help after the caption.
    - INSIDE (cell caption): a ruled cell, the label small in its top-left corner, the space below the caption."""
    import pymupdf

    from jason.community.pdf_fields import text_field

    lines = 2 if q.field == "mailing-address" else 1
    style = replace(layout, style=layout.style_for(q.field))
    caption = max(7.0, layout.size - 3)
    gray = (0.3, 0.3, 0.3)
    show_help = bool(q.help) and layout.help is not Place.NONE

    def space(rect: tuple[float, float, float, float]) -> None:
        _space(page, style, rect, q.field, drawn, lines)
        text_field(page, q.field, pymupdf.Rect(rect), multiline=lines > 1, fontsize=layout.value_size)
        drawn.fields[q.field] = rect

    if layout.label is Place.LEFT:
        col = x0 + min(150.0, (x1 - x0) * 0.38)
        # the label wraps inside its column; the space starts on the label's first line and the row is as tall as
        # the taller of the two
        words, rows, line = label.split(), [], ""
        for w in words:
            trial = f"{line} {w}".strip()
            if line and font.text_length(trial, fontsize=layout.size) > col - x0 - 8:
                rows.append(line)
                line = w
            else:
                line = trial
        rows.append(line)
        for i, text in enumerate(rows):
            page.insert_text((x0, y + layout.height - 4 + i * (layout.size + 2)), text, fontname=fontname,
                             fontsize=layout.size)
        rect = (col, y, x1, y + layout.height * lines)
        space(rect)
        y = max(rect[3], y + layout.height - 4 + (len(rows) - 1) * (layout.size + 2) + 4)
        if show_help:
            page.insert_text((col, y + help_size + 2), q.help, fontname=fontname, fontsize=help_size, color=gray)
            y += help_size + 4
        return y
    if layout.label is Place.BELOW:
        rect = (x0, y, x1, y + layout.height * lines)
        space(rect)
        y = rect[3] + caption + 2
        text = label + (f"   {q.help}" if show_help else "")
        if font.text_length(text, fontsize=caption) > x1 - x0:
            text = label
        page.insert_text((x0, y), text, fontname=fontname, fontsize=caption, color=gray)
        return y + 3
    if layout.label is Place.INSIDE:
        cell = (x0, y, x1, y + caption + 4 + layout.height * lines)
        page.draw_rect(pymupdf.Rect(cell), color=_edge(layout), width=max(0.5, layout.weight))
        text = label + (f"   {q.help}" if show_help else "")
        if font.text_length(text, fontsize=caption) > x1 - x0 - 6:
            text = label
        page.insert_text((x0 + 3, y + caption + 1), text, fontname=fontname, fontsize=caption, color=gray)
        rect = (x0 + 2, y + caption + 3, x1 - 2, cell[3] - 1)
        _space(page, replace(style, style=FieldStyle.OPEN), rect, q.field, drawn, lines)   # the cell is the edge
        text_field(page, q.field, pymupdf.Rect(rect), multiline=lines > 1, fontsize=layout.value_size)
        drawn.fields[q.field] = rect
        return cell[3]
    page.insert_text((x0, y + layout.size), label, fontname=fontname, fontsize=layout.size)
    y += layout.size + 4
    if show_help:
        page.insert_text((x0, y + help_size), q.help, fontname=fontname, fontsize=help_size, color=gray)
        y += help_size + 4
    rect = (x0, y, x1, y + layout.height * lines)
    space(rect)
    return rect[3]


def render(layout: Layout, out: Path) -> tuple[Path, Drawn]:
    """The lab form drawn in ``layout`` as a fillable PDF, and where things went."""
    import pymupdf

    from jason.community.pdf_fields import check_box, radio_group, text_field

    doc = pymupdf.open()
    page = doc.new_page(width=PAGE[0], height=PAGE[1])
    fontname, font = _font(page, layout)
    drawn = Drawn()
    x0, x1 = MARGIN, PAGE[0] - MARGIN
    page.insert_text((x0, 58), "Owner Information (layout trial)", fontname=fontname, fontsize=16)
    page.insert_textbox(pymupdf.Rect(x0, 70, x1, 104), INTRO, fontname=fontname, fontsize=10)
    y = 112.0
    top = y
    radios: list[tuple[int, Any, str]] = []
    help_size = max(7.5, layout.size - 2)
    questions = list(enumerate(LAB_FORM.questions, 1))
    paired = {} if layout.columns != 2 else PAIRS.get(layout.pairs, PAIRS["contact"])
    skip: set[str] = set()
    for number, q in questions:
        if q.field in skip:
            continue
        label = f"{number}. {q.title}"
        if q.kind not in (QuestionKind.CHECKBOX, QuestionKind.CHOICE):
            if q.field in paired:                  # two short answers side by side, each its own column
                other_n, other = next((n, o) for n, o in questions if o.field == paired[q.field])
                mid = (x0 + x1) / 2
                y_a = _text_question(page, doc, layout, fontname, font, q, label, x0, mid - 9, y, drawn, help_size)
                y_b = _text_question(page, doc, layout, fontname, font, other, f"{other_n}. {other.title}", mid + 9, x1, y,
                                     drawn, help_size)
                skip.add(other.field)
                y = max(y_a, y_b) + layout.gap + 6
            else:
                y = _text_question(page, doc, layout, fontname, font, q, label, x0, x1, y, drawn, help_size) + layout.gap + 6
            continue
        page.insert_text((x0, y + layout.size), label, fontname=fontname, fontsize=layout.size)
        y += layout.size + 4
        fx0 = x0
        if q.help and layout.help is not Place.NONE:
            page.insert_text((x0, y + help_size), q.help, fontname=fontname, fontsize=help_size, color=(0.3,) * 3)
            y += help_size + 4
        if q.kind is QuestionKind.CHECKBOX or q.kind is QuestionKind.CHOICE:
            bx = x0
            for o in q.options:
                r = pymupdf.Rect(bx, y, bx + layout.box, y + layout.box)
                if q.kind is QuestionKind.CHECKBOX:
                    page.draw_rect(r, color=_edge(layout), width=max(0.5, layout.weight))
                    check_box(page, f"{q.field}.{option_key(o)}", r)
                else:
                    page.draw_circle(pymupdf.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2), layout.box / 2, color=_edge(layout),
                                     width=max(0.5, layout.weight))
                    radios.append((0, r, option_key(o)))
                page.insert_text((bx + layout.box + 4, y + layout.box - 2), o, fontname=fontname, fontsize=layout.size)
                bx += layout.box + 8 + font.text_length(o, fontsize=layout.size) + max(10.0, layout.box_gap - 40)
            y += layout.box
        y += layout.gap + 6
    radio_group(doc, "occupancy", radios)
    drawn.used = y - top
    drawn.printed = [tuple(w[:4]) for w in page.get_text("words") if any(ch.isalnum() for ch in w[4])]
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(out)
    doc.close()
    return out, drawn


# -- the responder ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Writer:
    name: str
    fonts: tuple[str, ...]
    size: float                       # their natural writing size (a font size, points)
    unsteady: float                   # baseline wander, points
    turn: float                       # how far a word turns, degrees
    care: float                       # 0 to 1: how much they keep to a space's edges


WRITERS = (
    Writer("neat print", ("segoepr.ttf", "Inkfree.ttf"), 11.0, 0.5, 1.0, 0.95),
    Writer("hurried print", ("mvboli.ttf", "Inkfree.ttf", "comic.ttf"), 13.0, 1.6, 3.0, 0.6),
    Writer("cursive", ("LHANDW.TTF", "BRADHITC.TTF", "segoesc.ttf"), 12.0, 1.0, 2.0, 0.75),
)
TYPED = "typed"

AFFORDANCE = {FieldStyle.OPEN: 0.3, FieldStyle.RULE: 0.6, FieldStyle.COMB: 0.7, FieldStyle.SHADED: 0.75,
              FieldStyle.BOX: 0.85, FieldStyle.CHAR_BOXES: 0.9}     # how plainly a space says "write here, this big"
BOUNDED = (FieldStyle.BOX, FieldStyle.SHADED, FieldStyle.CHAR_BOXES)


def salience(layout: Layout) -> float:
    """How much an edge is noticed: darker and heavier more (a shaded band by its contrast with the paper)."""
    if layout.style is FieldStyle.SHADED:
        return 0.8
    if layout.style is FieldStyle.OPEN:
        return 0.5
    return max(0.3, min(1.2, (1 - layout.tone) * (layout.weight / 1.0) ** 0.5 + 0.2))


def keeps_inside(layout: Layout, writer: Writer, rng: random.Random) -> bool:
    p = min(0.98, writer.care * (0.5 + 0.5 * AFFORDANCE[layout.style] * salience(layout)))
    return rng.random() < p


@dataclass
class Spill:
    words: int = 0
    over_print: int = 0               # words written on printed text
    outside: int = 0                  # words written past their space's edge


def _overlaps(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def write(pdf: Path, drawn: Drawn, layout: Layout, values: dict[str, Any], writer: Writer, rng: random.Random,
          out: Path) -> Spill:
    """``values`` written on the printed form by ``writer`` as the layout leads them to; returns where the writing
    went."""
    import pymupdf

    from jason.community.pdf_fields import flatten
    from jason.tasks.form_fuzz import FONTS, INKS, _pen_mark

    spill = Spill()
    font_path = FONTS / rng.choice([f for f in writer.fonts if (FONTS / f).is_file()])
    font = pymupdf.Font(fontfile=str(font_path))
    ink = rng.choice(INKS)
    with tempfile.TemporaryDirectory() as tmp:
        flat = flatten(pdf, Path(tmp) / "flat.pdf")
        with pymupdf.open(flat) as doc, pymupdf.open(pdf) as form:
            page = doc[0]
            page.insert_font(fontname="hand", fontfile=str(font_path))
            for w in form[0].widgets() or []:
                if w.field_type in (pymupdf.PDF_WIDGET_TYPE_CHECKBOX, pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON):
                    on = values.get(w.field_name) is True if w.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX else \
                        values.get(w.field_name.split(".")[0]) == w.on_state()
                    if on:
                        r = w.rect
                        _pen_mark(page, (r.x0, r.y0, r.x1, r.y1), rng, ink)
            for name, rect in drawn.fields.items():
                text = str(values.get(name) or "")
                if text:
                    _write_field(page, font, text, rect, name, drawn, replace(layout, style=layout.style_for(name)),
                                 writer, rng, ink, spill)
            doc.save(out)
    return spill


def _write_field(page: Any, font: Any, text: str, rect: tuple[float, float, float, float], name: str, drawn: Drawn,
                 layout: Layout, writer: Writer, rng: random.Random, ink: tuple[float, ...], spill: Spill) -> None:
    import pymupdf

    x0, y0, x1, y1 = rect
    inside = keeps_inside(layout, writer, rng)
    rows = 2 if name == "mailing-address" else 1
    row_h = (y1 - y0) / rows
    size = writer.size * rng.uniform(0.92, 1.08)
    if layout.style in BOUNDED and inside:
        size = min(size, (row_h - 3) / 0.78)               # a cap and a tail inside the box
    pieces: list[tuple[str, float, float, float]] = []    # (text, x, baseline, size)
    if layout.style is FieldStyle.CHAR_BOXES and drawn.cells.get(name):
        cells = drawn.cells[name]
        side = cells[0][2] - cells[0][0]
        csize = min(size, side / 0.8) if inside else size
        pitch = drawn.pitches[name]
        for i, ch in enumerate(text):
            cell = cells[i] if i < len(cells) else (cells[-1][0] + pitch * (i - len(cells) + 1), cells[-1][1],
                                                    cells[-1][2] + pitch * (i - len(cells) + 1), cells[-1][3])
            cx = cell[0] + side / 2
            if ch == " ":
                continue
            j = 0.12 if inside else 0.35
            x = cx - font.text_length(ch, fontsize=csize) / 2 + rng.uniform(-j, j) * side
            base = cell[3] - side * 0.18 + rng.uniform(-j, j) * side * 0.5
            pieces.append((ch, x, base, csize))
    else:
        words = text.split()
        width = x1 - x0 - 6
        lines: list[list[str]] = [[]]
        for word in words:
            trial = " ".join(lines[-1] + [word])
            if lines[-1] and font.text_length(trial, fontsize=size) > width and len(lines) < rows:
                lines.append([word])
            else:
                lines[-1].append(word)
        longest = max(font.text_length(" ".join(l), fontsize=size) for l in lines)
        if longest > width and (inside or layout.style in BOUNDED):
            size = max(size * 0.75, size * width / longest)       # people squeeze a long answer, to a point
        follow = layout.style is FieldStyle.COMB and drawn.pitches.get(name) and rng.random() < 0.5
        for r, line in enumerate(lines[:rows]):
            if layout.style in (FieldStyle.RULE, FieldStyle.COMB):
                base = y0 + row_h * (r + 1) - rng.uniform(0.5, 1.8)      # on the line
            elif layout.style is FieldStyle.OPEN:
                base = y0 + row_h * (r + 0.75) + rng.uniform(-2.5, 2.5) * writer.unsteady
            else:
                base = y0 + row_h * (r + 1) - max(2.0, row_h - size * 0.78) / 2 - size * 0.12
            if not inside:
                base += rng.choice((-1, 1)) * rng.uniform(2.5, 5.5)       # over an edge
            x = x0 + rng.uniform(2, 6)
            for word in line:
                if follow:
                    for ch in word:
                        pieces.append((ch, x, base + rng.uniform(-0.6, 0.6) * writer.unsteady, size))
                        x += drawn.pitches[name]
                    x += drawn.pitches[name]
                    continue
                pieces.append((word, x, base + rng.uniform(-1, 1) * writer.unsteady, size))
                x += font.text_length(word + " ", fontsize=size) * rng.uniform(0.98, 1.1)
    for piece, x, base, sz in pieces:
        w = font.text_length(piece, fontsize=sz)
        box = (x, base - sz * 0.75, x + w, base + sz * 0.22)
        spill.words += 1
        if any(_overlaps(box, p) for p in drawn.printed):
            spill.over_print += 1
        if box[0] < x0 - 2 or box[2] > x1 + 2 or box[1] < y0 - 2 or box[3] > y1 + 2:
            spill.outside += 1
        page.insert_text((x, base), piece, fontname="hand", fontsize=sz, color=ink,
                         morph=(pymupdf.Point(x, base), pymupdf.Matrix(rng.uniform(-writer.turn, writer.turn))))


# -- the battery ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Trial:
    seed: int
    responder: str                    # a writer's name, or "typed"
    profile: str                      # a form_fuzz scan profile
    style: str                        # a form_fuzz answer style


def battery(size: int = 12, seed: int = 7, profiles: tuple[str, ...] = ("office", "home", "phone")) -> list[Trial]:
    """``size`` trials: each responder and each profile in turn, answers in the fuzzer's styles."""
    from jason.tasks.form_fuzz import Style

    responders = [w.name for w in WRITERS] + [TYPED]
    styles = [s.value for s in Style]
    rng = random.Random(seed)
    return [Trial(rng.randrange(10**6), responders[n % len(responders)], profiles[(n // len(responders)) % len(profiles)],
                  styles[n % len(styles)]) for n in range(size)]


def lab_answers(rng: random.Random, style: Any) -> dict[str, Any]:
    from jason.tasks.form_fuzz import _email, _elsewhere, _person, _unit_address

    first, last = _person(rng, style)
    out: dict[str, Any] = {"owner-names": f"{first} {last}", "unit-address": _unit_address(rng, style)}
    if rng.random() < 0.6:
        out["mailing-address"] = _elsewhere(rng, style)
    if rng.random() < 0.8:
        out["email"] = _email(rng, style, first, last)
    if rng.random() < 0.8:
        out["phone"] = rng.choice(("({a}) {b}-{c}", "{a}-{b}-{c}", "{a}.{b}.{c}")).format(
            a=rng.choice((916, 530, 707, 415)), b=rng.randint(200, 999), c=f"{rng.randint(0, 9999):04d}")
    for o in ("by-mail", "by-email"):
        if rng.random() < 0.55:
            out[f"delivery.{o}"] = True
    out["occupancy"] = rng.choice(("owner-occupied", "rented-out", "vacant"))
    return out


@dataclass
class Outcome:
    trial: Trial
    scores: dict[str, float] = field(default_factory=dict)       # field to credit (0 to 1), hinted
    raw: dict[str, float] = field(default_factory=dict)          # field to credit, the reader alone
    readings: dict[str, str] = field(default_factory=dict)
    wanted: dict[str, Any] = field(default_factory=dict)
    spill: Spill = field(default_factory=Spill)
    aligned: bool = True
    scan: str = ""


def _credit(key: str, want: Any, got: Any) -> float:
    import difflib

    from jason.tasks.form_fuzz import _norm

    if isinstance(want, bool) or key.startswith("delivery."):
        return float(bool(want) == bool(got))
    if key == "occupancy":
        return float(str(want) == str(got or ""))
    w, g = _norm(key, want), _norm(key, got or "")
    if w == g:
        return 1.0
    return 0.5 * difflib.SequenceMatcher(None, w, g).ratio() if (w or g) else 1.0


def _score_fields(values: dict[str, Any], fields: dict[str, Any]) -> dict[str, float]:
    out = {}
    for q in LAB_FORM.questions:
        if q.kind is QuestionKind.CHECKBOX:
            for o in q.options:
                k = f"{q.field}.{option_key(o)}"
                out[k] = _credit(k, bool(values.get(k)), bool(fields.get(k)))
        else:
            out[q.field] = _credit(q.field, values.get(q.field, ""), fields.get(q.field, ""))
    return out


def run_trial(layout: Layout, trial: Trial, pdf: Path, drawn: Drawn, work: Path, *, keep_scan: bool = False) -> Outcome:
    import copy

    from jason.community import form_hints
    from jason.community.form_layout import read_layout
    from jason.community.form_reader import read_scan
    from jason.community.pdf_fields import fill
    from jason.tasks.form_fuzz import PROFILES, Style
    from jason.tasks.form_scans import simulate

    rng = random.Random(trial.seed)
    values = lab_answers(rng, Style(trial.style))
    filled = work / f"filled-{trial.seed}.pdf"
    spill = Spill()
    if trial.responder == TYPED:
        fill(pdf, values, filled)
    else:
        writer = next(w for w in WRITERS if w.name == trial.responder)
        spill = write(pdf, drawn, layout, values, writer, rng, filled)
    p = PROFILES[trial.profile]
    scan = simulate(filled, work / f"scan-{trial.seed}.pdf", dpi=p.dpi, angle=p.angle, scale=p.scale, shift=p.shift,
                    noise=p.noise, seed=trial.seed, blur=p.blur, jpeg=p.jpeg, gamma=p.gamma)
    layout_ = read_layout(pdf, LAB_FORM)
    layout_.pitches, layout_.cells = dict(drawn.pitches), dict(drawn.cells)
    reading = read_scan(scan, LAB_FORM, layout_)
    hinted = form_hints.apply(copy.deepcopy(reading), LAB_FORM, form_hints.community_hints())
    out = Outcome(trial, wanted=values, spill=spill, scan=str(scan) if keep_scan else "")
    out.aligned = not any("could not align" in n for n in reading.notes)
    raw_fields = {k: v.value for k, v in reading.fields.items()}
    out.raw = _score_fields(values, raw_fields)
    out.scores = _score_fields(values, {k: v.value for k, v in hinted.fields.items()})
    out.readings = {k: str(v.value) for k, v in hinted.fields.items() if isinstance(v.value, str)}
    return out


@dataclass(frozen=True)
class Costs:
    """What a layout costs a mailed letter, in cents, so space and readability trade in one unit. A taller layout
    takes more pages: ``page_cents`` each (``payhoa.pricing``: billed by printed page, two-sided or not), spread over a
    page's writing height, so every point is charged smoothly though the Mailroom bills whole pages. A misread answer
    costs a person's follow-up (``misread_cents``), on the share of letters that come back on paper (``returned``).
    The step the smooth price leaves out, $2.25 of postage from six billed pages, is the real form's to watch
    (``jason mailroom --pdf`` prints it)."""

    page_cents: float
    misread_cents: float = 150.0
    returned: float = 0.5
    page_points: float = 684.0        # a letter page less its margins

    @property
    def point_cents(self) -> float:
        return self.page_cents / self.page_points

    def paper(self, used: float) -> float:
        return used * self.point_cents

    def misreads(self, readable: float, answers: int) -> float:
        return self.returned * answers * (1.0 - readable) * self.misread_cents


@dataclass
class Evaluation:
    layout: Layout
    readable: float = 0.0             # mean credit, hinted
    readable_raw: float = 0.0
    text: float = 0.0                 # mean credit over the written answers only
    boxes: float = 0.0
    over_print: float = 0.0           # share of handwritten words on printed text
    outside: float = 0.0              # share written past their space
    used: float = 0.0                 # the questions' height, points
    aligned: float = 0.0
    by: dict[str, float] = field(default_factory=dict)            # responder and profile to credit
    seconds: float = 0.0
    costs: Costs | None = None
    answers: int = 0                  # the questions a letter asks

    @property
    def cents(self) -> float | None:
        """A mailed letter's cost of this layout: the paper for its height and the follow-ups for its misreads."""
        if self.costs is None:
            return None
        return self.costs.paper(self.used) + self.costs.misreads(self.readable, self.answers)

    @property
    def objective(self) -> float:
        """Readability, less a tenth for each share of writing on printed text and a twentieth for each share outside
        its space, less the space it takes. With ``costs`` the space is priced: its paper in cents, as the share of
        answers whose follow-ups would cost as much. Without, a tenth of the page share (a 600-point block costs 0.1)."""
        spill = 0.1 * self.over_print + 0.05 * self.outside
        if self.costs is None or not self.answers:
            return self.readable - spill - 0.1 * (self.used / 600)
        per_answer = self.costs.returned * self.answers * self.costs.misread_cents
        return self.readable - spill - self.costs.paper(self.used) / per_answer


def evaluate(layout: Layout, trials: list[Trial], work: Path | None = None, *, costs: Costs | None = None) -> Evaluation:
    start = time.time()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        base = Path(work or tmp)
        pdf, drawn = render(layout, base / "form.pdf")
        outcomes = [run_trial(layout, t, pdf, drawn, base) for t in trials]
    return summarize(layout, outcomes, drawn, time.time() - start, costs=costs)


def summarize(layout: Layout, outcomes: list[Outcome], drawn: Drawn, seconds: float = 0.0, *,
              costs: Costs | None = None) -> Evaluation:
    from collections import defaultdict

    ev = Evaluation(layout, used=drawn.used, seconds=round(seconds, 1), costs=costs, answers=len(LAB_FORM.questions))
    texts = [q.field for q in LAB_FORM.questions if q.kind not in (QuestionKind.CHECKBOX, QuestionKind.CHOICE)]
    allc, rawc, textc, boxc = [], [], [], []
    groups: dict[str, list[float]] = defaultdict(list)
    words = over = outside = 0
    for o in outcomes:
        allc += list(o.scores.values())
        rawc += list(o.raw.values())
        written = [o.scores[k] for k in texts if o.wanted.get(k)]
        textc += written
        boxc += [v for k, v in o.scores.items() if k not in texts]
        mean = sum(o.scores.values()) / len(o.scores) if o.scores else 0.0
        groups[o.trial.responder].append(mean)
        groups[o.trial.profile].append(mean)
        words, over, outside = words + o.spill.words, over + o.spill.over_print, outside + o.spill.outside
    ev.readable = round(sum(allc) / len(allc), 4) if allc else 0.0
    ev.readable_raw = round(sum(rawc) / len(rawc), 4) if rawc else 0.0
    ev.text = round(sum(textc) / len(textc), 4) if textc else 0.0
    ev.boxes = round(sum(boxc) / len(boxc), 4) if boxc else 0.0
    ev.over_print = round(over / words, 4) if words else 0.0
    ev.outside = round(outside / words, 4) if words else 0.0
    ev.aligned = round(sum(o.aligned for o in outcomes) / len(outcomes), 3) if outcomes else 0.0
    ev.by = {k: round(sum(v) / len(v), 3) for k, v in groups.items()}
    return ev


# -- the search ----------------------------------------------------------------------------------------------------------

def search(trials: list[Trial], *, start: Layout = CURRENT, passes: int = 3, log: Path | None = None,
           order: tuple[str, ...] = tuple(SPACE), say: Any = print, costs: Costs | None = None) -> tuple[Layout, list[Evaluation]]:
    """Coordinate descent over ``SPACE`` from ``start`` on the same ``trials``; each evaluation is logged."""
    seen: dict[str, Evaluation] = {}
    history: list[Evaluation] = []

    def score(layout: Layout) -> Evaluation:
        if layout.key() not in seen:
            ev = evaluate(layout, trials, costs=costs)
            seen[layout.key()] = ev
            history.append(ev)
            say(f"  {_short(layout)}: objective {ev.objective:.3f} (readable {ev.readable:.3f}, text {ev.text:.3f}, "
                f"on print {ev.over_print:.2f}, {ev.seconds:.0f} s)")
            if log:
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"layout": layout.as_json(), "objective": ev.objective,
                                        **{k: v for k, v in asdict(ev).items() if k != "layout"}}) + "\n")
        return seen[layout.key()]

    best = start
    best_ev = score(best)
    for n in range(passes):
        changed = False
        for name in order:
            for value in SPACE[name]:
                trial_layout = replace(best, **{name: value})
                ev = score(trial_layout)
                if ev.objective > best_ev.objective + 0.01:      # less is within the battery's noise
                    best, best_ev, changed = trial_layout, ev, True
            say(f"pass {n + 1}, {name}: {getattr(best, name).value if isinstance(getattr(best, name), Enum) else getattr(best, name)}"
                f" (objective {best_ev.objective:.3f})")
        if not changed:
            break
    return best, history


def _short(layout: Layout) -> str:
    d = CURRENT.as_json()
    diff = {k: v for k, v in layout.as_json().items() if d[k] != v}
    return ", ".join(f"{k} {v}" for k, v in diff.items()) or "the current form"


# -- the readers' benchmark ---------------------------------------------------------------------------------------------

def benchmark(layouts: list[Layout], trials: list[Trial], models: list[str], *, say: Any = print) -> list[dict[str, Any]]:
    """Each reader on the same trials and layouts: Tesseract alone, with the hints, and each vision model (the scan
    reader's prompt and schema, the GPU lock held, ``local_ai.preflight`` first; a model that cannot load is reported,
    not run). Returns one row per layout and reader."""
    from jason.community.form_reader import VisionReader, scan_pages
    from jason.local_ai import LocalAIUnavailable, preflight, unload
    from jason.locks import Resource, hold

    rows = []
    names = [q.field for q in LAB_FORM.questions if q.kind not in (QuestionKind.CHECKBOX, QuestionKind.CHOICE)]
    for layout in layouts:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            base = Path(tmp)
            pdf, drawn = render(layout, base / "form.pdf")
            outcomes = [run_trial(layout, t, pdf, drawn, base, keep_scan=True) for t in trials]
            ev = summarize(layout, outcomes, drawn)
            rows.append({"layout": _short(layout), "reader": "tesseract", "text": _text_credit(outcomes, raw=True),
                         "by": _by_responder(outcomes, raw=True)})
            rows.append({"layout": _short(layout), "reader": "tesseract + hints", "text": ev.text,
                         "by": _by_responder(outcomes)})
            for model in models:
                try:
                    preflight(model)
                except LocalAIUnavailable as exc:
                    rows.append({"layout": _short(layout), "reader": model, "error": str(exc)})
                    say(f"  {model}: {exc}")
                    continue
                reader = VisionReader(model, timeout=240)          # a model that loops is cut off, not waited on
                credits: list[float] = []
                per: dict[str, list[float]] = {}
                failures = 0
                start = time.time()
                for o in outcomes:
                    page = scan_pages(Path(o.scan))[0]
                    try:
                        with hold(Resource.GPU, timeout=1800, purpose=f"form lab {model}"):
                            got = reader.read(page, LAB_FORM, names)
                    except (OSError, ValueError) as exc:          # a timeout or a broken answer: nothing read
                        got = {}
                        failures += 1
                        say(f"  {model}: {type(exc).__name__} on trial {o.trial.seed}")
                    for k in names:
                        if o.wanted.get(k):
                            c = _credit(k, o.wanted[k], got.get(k, ""))
                            credits.append(c)
                            per.setdefault(o.trial.responder, []).append(c)
                seconds = time.time() - start
                unload(model)                         # the next reader, or the next process, needs the memory
                rows.append({"layout": _short(layout), "reader": model,
                             "text": round(sum(credits) / len(credits), 4) if credits else 0.0,
                             "by": {k: round(sum(v) / len(v), 3) for k, v in per.items()},
                             "seconds_per_page": round(seconds / max(1, len(outcomes)), 1), "failures": failures})
                say(f"  {_short(layout)} / {model}: {rows[-1]['text']:.3f}")
    return rows


# -- does telling the model the form's rules help it? ---------------------------------------------------------------------

PROMPTS = ("plain", "rules", "rules+sent")


def field_rules(community_streets: tuple[str, ...] | None = None) -> dict[str, str]:
    """What each written answer looks like, as a reader is told it: the form's own rules (``FormQuestion.reads_as``)
    and the community's streets."""
    from jason.community.symbols import Street

    streets = community_streets or tuple(s.value.title() for s in Street)
    return {
        "owner-names": "one or more people's names, as on a deed",
        "unit-address": ("a street address in this community: a house number and one of these streets: "
                         + ", ".join(streets) + "; then Sacramento, CA 95835"),
        "mailing-address": "a US mailing address: a street line or PO Box, an optional apartment, a city, a state, a ZIP",
        "email": "one email address (name@domain), with no spaces",
        "phone": "a 10-digit US phone number",
    }


def prompt_for(kind: str, names: list[str], *, sent: dict[str, str] | None = None) -> tuple[str, dict[str, Any]]:
    """The prompt and JSON schema each condition gives the model. Every condition asks for exactly what is written,
    and says that a value that breaks the rules is still to be written as it is."""
    questions = {q.field: q for q in LAB_FORM.questions}
    rules = field_rules()
    lines = []
    for n in names:
        line = f"- {n}: {questions[n].title}"
        if kind != "plain":
            line += f" (usually {rules[n]})"
        lines.append(line)
    prompt = ("This is a scanned page of a paper form someone filled in by hand. For each field below, write exactly "
              "what the person wrote on its lines (an empty string when nothing is written). Do not copy the printed "
              "questions or help text; transcribe only the handwriting or typing.\n" + "\n".join(lines))
    if kind != "plain":
        prompt += ("\nThe descriptions say what an answer usually looks like, to help you read unclear letters. If "
                   "what is written does not fit, write it exactly as written anyway; do not correct it.")
    if kind == "rules+sent" and sent:
        prompt += ("\nThis copy was mailed with these answers already printed in it. The person may have crossed "
                   "them out or written different ones; report what is on the page now, not these:\n"
                   + "\n".join(f"- {k}: {v}" for k, v in sent.items() if k in names))
    props: dict[str, Any] = {}
    for n in names:
        props[n] = {"type": "string"}
        if kind != "plain":
            props[n]["description"] = rules[n]
    return prompt, {"type": "object", "properties": props, "required": names}


def _malformed(values: dict[str, Any], rng: random.Random) -> tuple[dict[str, Any], list[str]]:
    """The answers with an email or a phone number written wrongly, as people do: the "@" left out, a digit short."""
    out, broken = dict(values), []
    if out.get("email"):
        out["email"] = out["email"].replace("@", " at ", 1) if rng.random() < 0.5 else out["email"].replace(".", "", 1)
        broken.append("email")
    if out.get("phone"):
        digits = "".join(ch for ch in out["phone"] if ch.isdigit())
        out["phone"] = f"{digits[:3]}-{digits[3:6]}-{digits[6:9]}"            # nine digits
        broken.append("phone")
    return out, broken


def _edited(values: dict[str, Any], rng: random.Random, style: Any) -> tuple[dict[str, Any], list[str]]:
    """The answers with one or two written fields changed from what was sent (the owner's update)."""
    from jason.tasks.form_fuzz import _elsewhere, _email, _person

    out, changed = dict(values), []
    first, last = _person(rng, style)
    for name in rng.sample(["owner-names", "mailing-address", "email", "phone"], 2):
        new = {"owner-names": f"{first} {last}", "mailing-address": _elsewhere(rng, style),
               "email": _email(rng, style, first, last), "phone": f"(916) {rng.randint(200, 999)}-{rng.randint(0, 9999):04d}"}[name]
        if new != out.get(name):
            out[name] = new
            changed.append(name)
    return out, changed


def prompt_trial(trials: list[Trial], models: list[str], *, layout: Layout = CURRENT, say: Any = print) -> dict[str, Any]:
    """Each model reads the same handwritten scans under each prompt (``PROMPTS``), on three sets: answers as written
    (accuracy), answers changed from what the copy was sent with (does the model report the old value it was told?),
    and answers written wrongly (does it quietly correct them?). Returns the scores by model, set, and prompt."""
    import copy as _copy

    from jason.community.form_reader import scan_pages
    from jason.community.ollama_extractor import OLLAMA_URL, _post
    from jason.local_ai import LocalAIUnavailable, preflight, unload
    from jason.tasks.form_fuzz import PROFILES, Style, _norm
    from jason.tasks.form_scans import simulate

    names = [q.field for q in LAB_FORM.questions if q.kind not in (QuestionKind.CHECKBOX, QuestionKind.CHOICE)]
    results: dict[str, Any] = {"layout": _short(layout), "trials": len(trials), "models": {}}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        base = Path(tmp)
        pdf, drawn = render(layout, base / "form.pdf")
        cases = []                                    # (set, trial, written, sent, special fields, scan)
        for t in trials:
            rng = random.Random(t.seed)
            style = Style(t.style)
            sent = lab_answers(rng, style)
            for kind in ("as written", "edited", "malformed"):
                if kind == "as written":
                    written, special = dict(sent), []
                elif kind == "edited":
                    written, special = _edited(sent, random.Random(t.seed + 1), style)
                else:
                    written, special = _malformed(sent, random.Random(t.seed + 2))
                filled = base / f"{kind[:4]}-{t.seed}.pdf"
                if t.responder == TYPED:
                    from jason.community.pdf_fields import fill

                    fill(pdf, written, filled)
                else:
                    writer = next(w for w in WRITERS if w.name == t.responder)
                    write(pdf, drawn, layout, written, writer, random.Random(t.seed + 3), filled)
                p = PROFILES[t.profile]
                scan = simulate(filled, base / f"scan-{kind[:4]}-{t.seed}.pdf", dpi=p.dpi, angle=p.angle, scale=p.scale,
                                shift=p.shift, noise=p.noise, seed=t.seed, blur=p.blur, jpeg=p.jpeg, gamma=p.gamma)
                cases.append((kind, t, written, sent, special, scan))
        for model in models:
            try:
                preflight(model)
            except LocalAIUnavailable as exc:
                results["models"][model] = {"error": str(exc)}
                say(f"  {model}: {exc}")
                continue
            table: dict[str, dict[str, dict[str, float]]] = {}
            for kind, t, written, sent, special, scan in cases:
                page = scan_pages(scan)[0]
                import base64

                image = base64.b64encode(page.get_pixmap(dpi=150).tobytes("png")).decode("ascii")
                for prompt_kind in PROMPTS:
                    prompt, schema = prompt_for(prompt_kind, names, sent={k: str(v) for k, v in sent.items()
                                                                          if k in names and v})
                    try:
                        answer = _post(f"{OLLAMA_URL}/api/chat", {
                            "model": model, "stream": False, "think": False, "format": schema,
                            "options": {"temperature": 0},
                            "messages": [{"role": "user", "content": prompt, "images": [image]}]}, 240)
                        got = json.loads((answer.get("message") or {}).get("content") or "{}")
                    except (OSError, ValueError):
                        got = {}
                    cell = table.setdefault(kind, {}).setdefault(prompt_kind, {"credit": 0.0, "n": 0, "old": 0,
                                                                              "fixed": 0, "special": 0})
                    for n in names:
                        if written.get(n):
                            cell["credit"] += _credit(n, written[n], got.get(n, ""))
                            cell["n"] += 1
                    for n in special:                  # the trap fields
                        cell["special"] += 1
                        read = _norm(n, got.get(n, ""))
                        if kind == "edited" and read and read == _norm(n, sent.get(n, "")):
                            cell["old"] += 1           # reported what it was told, not what is written
                        if kind == "malformed" and read and read != _norm(n, written[n]) and \
                                read == _norm(n, sent.get(n, "")):
                            cell["fixed"] += 1         # quietly put the owner's answer right
            unload(model)
            results["models"][model] = {
                kind: {pk: {"credit": round(c["credit"] / max(1, c["n"]), 4), "trap fields": c["special"],
                            "reported what it was told": c["old"], "quietly corrected": c["fixed"]}
                       for pk, c in row.items()} for kind, row in table.items()}
            say(f"  {model}: " + json.dumps(results["models"][model]))
    return results


def _text_credit(outcomes: list[Outcome], *, raw: bool = False) -> float:
    texts = [q.field for q in LAB_FORM.questions if q.kind not in (QuestionKind.CHECKBOX, QuestionKind.CHOICE)]
    c = [(o.raw if raw else o.scores)[k] for o in outcomes for k in texts if o.wanted.get(k)]
    return round(sum(c) / len(c), 4) if c else 0.0


def _by_responder(outcomes: list[Outcome], *, raw: bool = False) -> dict[str, float]:
    texts = [q.field for q in LAB_FORM.questions if q.kind not in (QuestionKind.CHECKBOX, QuestionKind.CHOICE)]
    per: dict[str, list[float]] = {}
    for o in outcomes:
        per.setdefault(o.trial.responder, []).extend((o.raw if raw else o.scores)[k] for k in texts if o.wanted.get(k))
    return {k: round(sum(v) / len(v), 3) for k, v in per.items() if v}


def sample(layout: Layout, out_dir: Path, *, seed: int = 3, responder: str = "hurried print") -> list[Path]:
    """The layout blank and filled by a responder, as PNGs to look at."""
    import pymupdf

    out_dir.mkdir(parents=True, exist_ok=True)
    tag = "".join(ch if ch.isalnum() else "-" for ch in _short(layout))[:60] or "current"
    pdf, drawn = render(layout, out_dir / f"{tag}.pdf")
    from jason.tasks.form_fuzz import Style

    rng = random.Random(seed)
    values = lab_answers(rng, Style.PLAIN)
    writer = next(w for w in WRITERS if w.name == responder)
    filled = out_dir / f"{tag}-filled.pdf"
    write(pdf, drawn, layout, values, writer, rng, filled)
    paths = []
    for src, name in ((pdf, f"{tag}-blank.png"), (filled, f"{tag}-filled.png")):
        with pymupdf.open(src) as doc:
            doc[0].get_pixmap(dpi=90).save(out_dir / name)
        paths.append(out_dir / name)
    return paths


__all__ = ["CURRENT", "Evaluation", "FieldStyle", "LAB_FORM", "Layout", "Place", "SPACE", "Trial", "WRITERS", "Writer",
           "battery", "benchmark", "evaluate", "render", "run_trial", "sample", "search", "summarize", "write"]
