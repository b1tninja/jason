"""Where each field of a form sits on its printed page: the layout a scanned return is read against.

The fillable PDF already knows it: ``fillable.make_fillable`` laid a field over every line and box, named by the form's
question keys. ``read_layout`` reads those fields back (a text field's area, each check box, each radio button with the
option it stands for) and the printed question titles ("3. How should the Association deliver notices to you?") as
anchors: text that OCR finds on a scan, so the scan can be aligned to the page before any field is read. Coordinates are
PDF points from the page's top left, as PyMuPDF gives them.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from jason.community.forms import FormTemplate


@dataclass(frozen=True)
class FieldBox:
    name: str                 # the PDF field: "occupancy", "delivery.by-mail", "mailing-address"
    kind: str                 # "text", "checkbox", or "radio"
    page: int
    rect: tuple[float, float, float, float]
    option: str = ""          # a radio button's option key, or a check box's ("by-mail")

    @property
    def question(self) -> str:
        return self.name.split(".", 1)[0]


@dataclass(frozen=True)
class Anchor:
    text: str                 # a printed question title, as OCR should read it
    page: int
    rect: tuple[float, float, float, float]


@dataclass
class FormLayout:
    form: str
    pages: list[tuple[float, float]] = field(default_factory=list)        # each page's width and height
    fields: list[FieldBox] = field(default_factory=list)
    anchors: list[Anchor] = field(default_factory=list)
    words: list[Anchor] = field(default_factory=list)                     # each printed word, for the precise fit
    source: str = ""                                                      # the blank fillable PDF
    page_numbers: list[int] = field(default_factory=list)                 # each layout page's page in ``source``
    pitches: dict[str, float] = field(default_factory=dict)               # a field written one character a box: its
                                                                          # boxes' pitch (points), for joining letters
    cells: dict[str, list[tuple[float, float, float, float]]] = field(default_factory=dict)   # each box, in order

    def on_page(self, page: int) -> tuple[list[FieldBox], list[Anchor]]:
        return [f for f in self.fields if f.page == page], [a for a in self.anchors if a.page == page]

    def words_on(self, page: int) -> list[Anchor]:
        return [w for w in self.words if w.page == page]

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=1)

    @classmethod
    def from_json(cls, text: str) -> FormLayout:
        raw = json.loads(text)
        return cls(raw["form"], [tuple(p) for p in raw["pages"]],
                   [FieldBox(**{**f, "rect": tuple(f["rect"])}) for f in raw["fields"]],
                   [Anchor(**{**a, "rect": tuple(a["rect"])}) for a in raw["anchors"]],
                   [Anchor(**{**w, "rect": tuple(w["rect"])}) for w in raw.get("words") or []],
                   raw.get("source", ""), list(raw.get("page_numbers") or []), dict(raw.get("pitches") or {}),
                   {k: [tuple(c) for c in v] for k, v in (raw.get("cells") or {}).items()})


QUESTION_LINE = re.compile(r"^\s*(\d{1,2})\.\s+\S")


def read_layout(pdf: Path | str, form: FormTemplate, *, pages: list[int] | None = None) -> FormLayout:
    """The layout of ``form`` as the fillable ``pdf`` lays it out (on ``pages``, or every page with a field). Anchors are
    the lines of text the page prints (the question titles, their help, the options), spread over the whole page, for
    aligning a scan."""
    import pymupdf

    from jason.community.fillable import field_geometry

    _, below = field_geometry(form.style.typed_size)
    layout = FormLayout(form.key.value, source=str(pdf))
    with pymupdf.open(pdf) as doc:
        wanted = pages if pages is not None else [p.number for p in doc if list(p.widgets() or [])]
        for index, number in enumerate(wanted):
            page = doc[number]
            layout.pages.append((page.rect.width, page.rect.height))
            layout.page_numbers.append(number)
            printed = [w[:4] for w in page.get_text("words") if any(ch.isalnum() for ch in w[4])]
            for w in page.widgets() or []:
                name = w.field_name or ""
                kind = {pymupdf.PDF_WIDGET_TYPE_CHECKBOX: "checkbox", pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON: "radio"}.get(
                    w.field_type, "text")
                option = w.on_state() if kind == "radio" else (name.split(".", 1)[1] if "." in name else "")
                r = w.rect
                y0, y1 = r.y0, r.y1
                if kind == "text":
                    # a typed field sits on its rule, running a little below it (fillable.field_geometry); a hand
                    # writes in the whole room above the rule. The box read on a scan is that room: from the rule up
                    # the form's writing height, never into the printed line above it or the label below
                    rule = r.y1 - below
                    y1 = rule + 1.0
                    above = [b[3] for b in printed if b[3] <= rule - 8.0 and b[2] > r.x0 and b[0] < r.x1]
                    y0 = max(min(r.y0, rule - form.style.write_height), (max(above) + 1.0) if above else 0.0)
                layout.fields.append(FieldBox(name, kind, index, (r.x0, y0, r.x1, y1), str(option or "")))
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    text = "".join(s["text"] for s in line["spans"]).strip()
                    if sum(ch.isalnum() for ch in text) >= 8:          # a line of words, not a rule or a box
                        x0, y0, x1, y1 = line["bbox"]
                        layout.anchors.append(Anchor(text, index, (x0, y0, x1, y1)))
            for x0, y0, x1, y1, word, *_ in page.get_text("words"):
                if sum(ch.isalnum() for ch in word) >= 4:
                    layout.words.append(Anchor(word, index, (x0, y0, x1, y1)))
    return layout


def save_layout(layout: FormLayout, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(layout.to_json(), encoding="utf-8")
    return path


__all__ = ["Anchor", "FieldBox", "FormLayout", "read_layout", "save_layout"]
