"""Form fields on a PDF: add them, read them, fill them, and flatten a returned copy. Any PDF, any form.

These are the primitives the form renderers build on (``fillable.make_fillable`` lays them over a printed form); a task
that needs a field on its own page uses them directly.

- ``text_field``: a line or a box to type in, optionally multi-line, required, and capped in length.
- ``check_box``: one box that is on or off, its "on" state named (``Yes`` by default).
- ``radio_group``: one field whose buttons are its options, so choosing one clears the rest. PyMuPDF makes each radio
  button its own field with the same "on" name, which a viewer switches together; ``radio_group`` makes the buttons the
  kids of one parent field, each with its own "on" name, the structure the PDF standard describes.
- ``values``: every field's value: text, True or False for a check box, the chosen option's name for a radio group.
- ``fill``: set fields by name (a copy prefilled for one recipient, such as the unit's address).
- ``flatten``: bake the fields into the page, so an archived copy of a returned form can no longer change.

A tooltip (the field's ``TU``) is what a screen reader announces and a viewer shows on hover; give every field one.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

REQUIRED = 1 << 1                      # field flag: Required
MULTILINE = 1 << 12                    # text field flag: Multiline
DO_NOT_SPELL_CHECK = 1 << 22           # text field flag: DoNotSpellCheck (a name, an address, an email, a phone)

# An answer written on several lines (an address) is one single-line field a line: the first keeps the question's
# field name, the next are "name#2", "name#3". Filling splits a value's lines across them; reading joins them back.
LINE = "#"
# A US address on one line, split before its last line: "City, ST ZIP".
CITY_LINE = re.compile(r"^(.+?),\s*([^,]+,\s*[A-Za-z]{2}\.?\s+\d{5}(?:-\d{4})?)$")


def line_field(name: str, n: int | str) -> str:
    """The field of an answer's ``n``th line (the first is the answer's own), or of a named part ("city")."""
    if isinstance(n, str):
        return f"{name}{LINE}{n}"
    return name if n <= 1 else f"{name}{LINE}{n}"


# An address's parts on its second line, joined back as a mailing address prints it: "City, ST ZIP".
PARTS = ("city", "state", "zip")


def _city_line(parts: dict[str, str]) -> str:
    city, state, zip_code = (parts.get(k, "").strip() for k in PARTS)
    return " ".join(x for x in (f"{city}," if city else "", state, zip_code) if x).strip(" ,")


def base_field(name: str) -> str:
    return name.split(LINE, 1)[0]


def join_lines(values: dict[str, Any]) -> dict[str, Any]:
    """Each answer's line fields joined back into its own field, one line each (empty lines dropped)."""
    out: dict[str, Any] = {}
    lines: dict[str, list[tuple[int, str]]] = {}
    named: dict[str, dict[str, str]] = {}
    for name, value in values.items():
        base, _, n = name.partition(LINE)
        if not n:
            out.setdefault(name, value)
        elif n in PARTS:
            named.setdefault(base, {})[n] = str(value or "").strip()
        else:
            lines.setdefault(base, []).append((int(n) if n.isdigit() else 99, str(value or "").strip()))
    for base in {*lines, *named}:
        parts = [str(out.get(base) or "").strip()] + [v for _, v in sorted(lines.get(base, []))]
        parts.append(_city_line(named.get(base, {})))
        out[base] = "\n".join(p for p in parts if p)
    return out


def split_lines(values: dict[str, Any], names: set[str]) -> dict[str, Any]:
    """A value of several lines spread over its line fields (those ``names`` holds): more lines than fields join onto
    the first ("12 Elm St, Apt 2"), so the last line ("City, ST ZIP") keeps its own; a PDF with one field for the
    answer keeps the value whole."""
    out = dict(values)
    for name, value in values.items():
        if not isinstance(value, str):
            continue
        if line_field(name, "city") in names:     # the address in its parts: the street, then city, state, ZIP
            from jason.community.postal import parse_mailing_address

            found = parse_mailing_address(value)
            if found is not None:
                out[name] = ", ".join(x for x in (found.line1, found.line2) if x)
                for part, text in zip(PARTS, (found.city, found.state, found.zip)):
                    out[line_field(name, part)] = text
            continue                              # unread, it stays whole on the street line for a person to see
        if line_field(name, 2) not in names:
            continue
        if "\n" not in value:                     # "12 Elm St, Apt 2, Davis, CA 95616" in one line: break before the city
            m = CITY_LINE.match(value.strip())
            if not m:
                continue
            value = f"{m.group(1)}\n{m.group(2)}"
        count = 1
        while line_field(name, count + 1) in names:
            count += 1
        parts = [p.strip() for p in value.splitlines() if p.strip()]
        while len(parts) > count:                 # "12 Elm St, Apt 2" above "Davis, CA 95616", as an envelope has it
            parts[0:2] = [f"{parts[0]}, {parts[1]}"]
        for n, part in enumerate(parts, 1):
            out[line_field(name, n)] = part
    return out


RADIO_FLAGS = (1 << 15) | (1 << 14)    # button flags: Radio, and NoToggleToOff (a choice is changed, not cleared)
OFF = "Off"


def _widget(kind: int, name: str, rect: Any, *, tooltip: str, required: bool, flags: int = 0) -> Any:
    import pymupdf

    widget = pymupdf.Widget()
    widget.field_type = kind
    widget.field_name = name
    widget.rect = pymupdf.Rect(rect)
    widget.field_label = tooltip or name
    widget.field_flags = flags | (REQUIRED if required else 0)
    widget.border_width = 0
    return widget


def text_field(page: Any, name: str, rect: Any, *, multiline: bool = False, required: bool = False, tooltip: str = "",
               max_len: int = 0, fontsize: float = 10, value: str = "", spellcheck: bool = True) -> int:
    """A text field over ``rect``; returns its xref. ``spellcheck`` False keeps a viewer from underlining a name,
    an address, an email, or a phone number as misspelled."""
    import pymupdf

    widget = _widget(pymupdf.PDF_WIDGET_TYPE_TEXT, name, rect, tooltip=tooltip, required=required,
                     flags=(MULTILINE if multiline else 0) | (0 if spellcheck else DO_NOT_SPELL_CHECK))
    widget.text_fontsize = fontsize
    if max_len:
        widget.text_maxlen = max_len
    if value:
        widget.field_value = value
    return page.add_widget(widget).xref


def check_box(page: Any, name: str, rect: Any, *, required: bool = False, tooltip: str = "", checked: bool = False) -> int:
    """A check box over ``rect`` (its "on" state is ``Yes``); returns its xref."""
    import pymupdf

    widget = _widget(pymupdf.PDF_WIDGET_TYPE_CHECKBOX, name, rect, tooltip=tooltip, required=required)
    widget.field_value = checked
    return page.add_widget(widget).xref


def box_over(rect: Any, side: float = 10) -> Any:
    """A square of at least ``side`` points centred on a printed box (☐), for a check box or radio button over it."""
    import pymupdf

    r = pymupdf.Rect(rect)
    side = max(r.height, side)
    return pymupdf.Rect(r.x0 - 0.5, r.y0 + (r.height - side) / 2, r.x0 - 0.5 + side, r.y0 + (r.height + side) / 2)


def radio_group(doc: Any, name: str, buttons: Iterable[tuple[int, Any, str]], *, required: bool = False,
                tooltip: str = "") -> int:
    """One radio field ``name`` with a button for each (page number, rect, option name); returns the field's xref.
    The field's value is the chosen option's name; nothing is chosen at first."""
    import pymupdf

    made: list[tuple[int, str]] = []
    for page_number, rect, option in buttons:
        widget = _widget(pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON, f"{name}.{option}", rect, tooltip=tooltip, required=False)
        widget.field_value = False
        made.append((doc[page_number].add_widget(widget).xref, option))
    parent = doc.get_new_xref()
    kids = " ".join(f"{xref} 0 R" for xref, _ in made)
    flags = RADIO_FLAGS | (REQUIRED if required else 0)
    label = f"/TU({_pdf_text(tooltip)})" if tooltip else ""
    doc.update_object(parent, f"<</FT/Btn/Ff {flags}/T({_pdf_text(name)}){label}/V/{OFF}/Kids[{kids}]>>")
    for xref, option in made:
        # A key PyMuPDF set is written even when nulled ("/FT null"), and a viewer then reads the button's type as
        # missing instead of inheriting the group's; the field keys go, and the button keeps only its appearance.
        text = doc.xref_object(xref, compressed=True)
        text = re.sub(r"/(?:T|TU)\((?:\\.|[^\\)])*\)|/(?:FT|V|AS)/\w+|/Ff \d+", "", text)
        doc.update_object(xref, text)
        doc.xref_set_key(xref, "Parent", f"{parent} 0 R")
        doc.xref_set_key(xref, "AS", f"/{OFF}")
        for state in ("N", "D"):
            kind, value = doc.xref_get_key(xref, f"AP/{state}")
            if kind == "dict":
                doc.xref_set_key(xref, f"AP/{state}", value.replace("/Yes ", f"/{_pdf_name(option)} "))
    catalog = doc.pdf_catalog()
    _, fields = doc.xref_get_key(catalog, "AcroForm/Fields")
    inside = {f"{xref} 0 R" for xref, _ in made}
    refs = [r for r in _refs(fields) if r not in inside] + [f"{parent} 0 R"]
    doc.xref_set_key(catalog, "AcroForm/Fields", "[" + " ".join(refs) + "]")
    return parent


def _pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "-", text) or "on"


def _refs(array: str) -> list[str]:
    return [f"{a} {b} R" for a, b in re.findall(r"(\d+)\s+(\d+)\s+R", array or "")]


def _radio_state(doc: Any, widget: Any) -> str:
    return doc.xref_get_key(widget.xref, "AS")[1].lstrip("/")


def values(path: Path | str) -> dict[str, Any]:
    """Every field's value by name: text as typed (stripped), a check box as True or False, a radio group as the chosen
    option's name or None."""
    import pymupdf

    out: dict[str, Any] = {}
    with pymupdf.open(path) as doc:
        for page in doc:
            for widget in page.widgets() or []:
                name = widget.field_name or ""
                if widget.field_type == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON:
                    state = _radio_state(doc, widget)
                    out.setdefault(name, None)
                    if state and state != OFF:
                        out[name] = state
                elif widget.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX:
                    out[name] = widget.field_value not in (False, OFF, "", None)
                else:
                    out[name] = str(widget.field_value or "").strip()
    return join_lines(out)


def fill(path: Path | str, filled: dict[str, Any], out: Path | str, *, multiline_size: float | None = None) -> list[str]:
    """Write a copy of ``path`` to ``out`` with fields set by name: text, a check box (truthy), or a radio group (the
    option's name). ``multiline_size`` sets the font of a multi-line text field, so two printed lines fit between its
    rules. Returns the names given that the PDF has no field for."""
    import pymupdf

    left = dict(filled)
    with pymupdf.open(path) as doc:
        filled = split_lines(filled, {w.field_name or "" for page in doc for w in page.widgets() or []})
        groups: dict[str, list[tuple[int, str]]] = {}      # a group's buttons: (xref, its "on" state)
        for page in doc:
            for widget in page.widgets() or []:
                name = widget.field_name or ""
                if name not in filled:
                    continue
                if widget.field_type == pymupdf.PDF_WIDGET_TYPE_RADIOBUTTON:
                    groups.setdefault(name, []).append((widget.xref, widget.on_state()))
                    continue
                widget.field_value = bool(filled[name]) if widget.field_type == pymupdf.PDF_WIDGET_TYPE_CHECKBOX \
                    else str(filled[name])
                if multiline_size and widget.field_flags & pymupdf.PDF_TX_FIELD_IS_MULTILINE:
                    widget.text_fontsize = multiline_size
                widget.update()
                left.pop(name, None)
        for name, buttons in groups.items():
            chosen = _pdf_name(str(filled[name]))
            for xref, on_state in buttons:
                doc.xref_set_key(xref, "AS", f"/{chosen if on_state == chosen else OFF}")
            parent = doc.xref_get_key(buttons[0][0], "Parent")[1].split()[0]
            doc.xref_set_key(int(parent), "V", f"/{chosen}")
            left.pop(name, None)
        doc.save(out)
    return sorted(left)


def flatten(path: Path | str, out: Path | str) -> Path:
    """A copy with every field baked into the page: what was typed and checked stays visible and can no longer change."""
    import pymupdf

    with pymupdf.open(path) as doc:
        doc.bake(annots=False, widgets=True)
        doc.save(out)
    return Path(out)


__all__ = ["LINE", "MULTILINE", "REQUIRED", "base_field", "join_lines", "line_field", "split_lines", "box_over", "check_box", "fill", "flatten", "radio_group", "text_field", "values"]
