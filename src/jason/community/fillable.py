"""A printed form made fillable in place, and a filled one read back.

The paper form (``form_render``) prints each question numbered and bold, each choice as a box (☐), each answer as a
line of underscores, and a signature line. ``make_fillable`` finds those on the PDF's pages and lays a field over each
(``pdf_fields``), so the same file prints for pen and paper and fills on screen:

- a "check one" question: one radio group named by the question's field, a button over each ☐, so choosing one clears
  the rest;
- a "check all" question: a check box over each ☐, named ``<field>.<option>``;
- a text question: a field over its lines, named by the question's field (consecutive lines become one multi-line
  field);
- the signature line: ``signature`` and ``date``.

With the form's definition each field is named by its question's stable ``field``, marked required as the question is,
and labelled with the question (what a screen reader announces); without one the fields are ``q<n>``. The printed
labels only place the fields: an option whose label wraps to the next line is still named for its whole option.

``read_answers`` turns a returned PDF back into a ``FormAnswers`` by question, ready for ``forms.check``, so a form
filled on screen and emailed back is read without retyping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community.forms import FormAnswers, FormQuestion, FormTemplate, QuestionKind, option_key

BOX = "☐"
HEADING = re.compile(r"^(\d+)\.\s")
BOLD = 16                       # PyMuPDF span flag
SIGNATURE = "Signature of owner"


@dataclass
class _Item:
    page: int
    y: float
    x: float
    kind: str                   # "heading", "line", "box", "signature"
    rect: Any
    text: str = ""
    number: int = 0


def _items(doc: Any, pages: Iterable[int], signature: str) -> list[_Item]:
    import pymupdf

    items: list[_Item] = []
    for p in pages:
        page = doc[p]
        words = page.get_text("words")
        signature_y = None
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                text = "".join(s["text"] for s in line["spans"]).strip()
                bold = any(s["flags"] & BOLD or "bold" in s["font"].casefold() for s in line["spans"])
                m = HEADING.match(text)
                if m and bold:
                    items.append(_Item(p, line["bbox"][1], line["bbox"][0], "heading", pymupdf.Rect(line["bbox"]), text,
                                       int(m.group(1))))
                if signature and text.startswith(signature):
                    signature_y = line["bbox"][1]
        for w in words:
            if set(w[4]) == {"_"} and len(w[4]) >= 8:
                kind = "signature" if signature_y is not None and abs(w[1] - signature_y) < 6 else "line"
                items.append(_Item(p, w[1], w[0], kind, pymupdf.Rect(w[:4])))
        boxes = page.search_for(BOX)
        for rect in boxes:
            label = [w for w in words if abs((w[1] + w[3]) / 2 - (rect.y0 + rect.y1) / 2) < 4 and w[0] > rect.x1 - 1]
            label.sort(key=lambda w: w[0])
            nxt = min([r.x0 for r in boxes if abs(r.y0 - rect.y0) < 4 and r.x0 > rect.x1] or [10_000])
            text = " ".join(w[4] for w in label if w[0] < nxt and w[4] != BOX).strip()
            items.append(_Item(p, rect.y0, rect.x0, "box", rect, text))
    items.sort(key=lambda i: (i.page, round(i.y), i.x))
    return items


def _option(question: FormQuestion | None, label: str) -> str:
    """The option key a printed label begins (a label can wrap, so the printed text may be cut short)."""
    key = option_key(label)
    if question is None:
        return key
    return option_key(question.option_for(key))


def make_fillable(path: Path, *, pages: Iterable[int] | None = None, out: Path | None = None,
                  questions: Iterable[FormQuestion] = (), form: FormTemplate | None = None) -> list[str]:
    """Lay form fields over the boxes and lines of the form on ``pages`` (all pages by default); returns the field
    names in page order, as ``pdf_fields.fill`` takes them (a radio group once, by its question's field). Give the form (or its ``questions``) to name, label, and mark the fields from the definition;
    the form also names its signature line."""
    import pymupdf

    from jason.community.pdf_fields import LINE, box_over, check_box, line_field, radio_group, text_field

    from jason.community.forms import FormStyle

    questions = list(form.questions if form else questions)
    signature = form.signature if form else SIGNATURE
    style = form.style if form else FormStyle()
    by_number = dict(enumerate(questions, 1))
    doc = pymupdf.open(path)
    items = _items(doc, list(pages) if pages is not None else range(doc.page_count), signature)
    names: list[str] = []
    radios: dict[str, list[tuple[int, Any, str]]] = {}
    radio_question: dict[str, FormQuestion | None] = {}
    number = 0
    pending: list[_Item] = []

    def question() -> FormQuestion | None:
        return by_number.get(number)

    def field_name() -> str:
        q = question()
        return q.field if q else f"q{number}"

    def flush() -> None:
        if not pending:
            return
        first, last = pending[0], pending[-1]
        # the field covers the writing room above its first line (``FormStyle.write_height``), not only the line
        room = max(4.0, style.write_height - first.rect.height)
        top = first.rect.y0 - room
        # never over the printed line above (a question's help): the reader would read what is left of it as writing
        above = [w[3] for w in doc[first.page].get_text("words") if any(ch.isalnum() for ch in w[4])
                 and w[3] <= first.rect.y0 + 1 and w[2] > first.rect.x0 and w[0] < max(i.rect.x1 for i in pending)]
        if above:
            top = max(top, max(above) + 1.0)
        q = question()
        # one single-line field on each writing line (an address: the street, then "City, ST ZIP"), each over its own
        # line's room: one tall field over two lines set its second line on the first rule, and viewers show a
        # multi-line field differently (October 1, 2026). The lines after the first are ``line_field(name, n)``.
        height, below = field_geometry(style.typed_size)
        rows: list[list[_Item]] = []                # the blanks a row: a line, or "City __ State __ ZIP __"
        for item in pending:
            if rows and abs(item.rect.y1 - rows[-1][0].rect.y1) < 3:
                rows[-1].append(item)
            else:
                rows.append([item])
        names_by_row = _part_names(q, field_name(), [len(r) for r in rows])
        for r, row in enumerate(rows):
            for c, line in enumerate(row):
                # viewers centre a single-line field's text, so the field is placed for its baseline to sit just
                # above the rule (``field_geometry``), running a little below it; never up into the printed line
                # above. The rule is a row of underscores: it lies about a point above the bottom of its text line
                bottom = line.rect.y1 - 1.0 + below
                line_top = max(bottom - height, top if r == 0 else rows[r - 1][0].rect.y1 + 1.0)
                rect = pymupdf.Rect(line.rect.x0, line_top, line.rect.x1, bottom)
                name, part = names_by_row[r][c]
                text_field(doc[line.page], name, rect, required=bool(q and q.required and r == 0 and c == 0),
                           tooltip=_label(q) + (f" ({part})" if part else ""),
                           fontsize=style.typed_size, spellcheck=not _exact(q),
                           max_len=PART_MAX.get(name.rpartition(LINE)[2] if LINE in name else "", 0))
                names.append(name)
        pending.clear()

    if questions:
        _check_headings(items, by_number)
    signature_fields = iter(("signature", "date"))
    for item in items:
        if item.kind == "heading":
            flush()
            number = item.number
        elif item.kind == "line":
            if pending and (item.page != pending[-1].page or item.y - pending[-1].y > 30):
                flush()
            pending.append(item)
        elif item.kind == "box":
            flush()
            q = question()
            option = _option(q, item.text)
            if q is not None and q.kind is QuestionKind.CHOICE:
                if field_name() not in radios:
                    names.append(field_name())          # one field; its value is the option chosen
                radios.setdefault(field_name(), []).append((item.page, box_over(item.rect), option))
                radio_question[field_name()] = q
            else:
                check_box(doc[item.page], f"{field_name()}.{option}", box_over(item.rect),
                          tooltip=f"{_label(q)}: {q.option_for(option) if q else item.text}")
                names.append(f"{field_name()}.{option}")
        elif item.kind == "signature":
            flush()
            name = next(signature_fields, "signature-extra")
            room = max(4.0, style.write_height - item.rect.height)
            text_field(doc[item.page], name, pymupdf.Rect(item.rect.x0, item.rect.y0 - room, item.rect.x1, item.rect.y1 + 1),
                       tooltip=f"{signature} ({name})" if name == "date" else signature, fontsize=style.typed_size)
            names.append(name)
    flush()
    for name, buttons in radios.items():
        q = radio_question[name]
        radio_group(doc, name, buttons, required=bool(q and q.required), tooltip=_label(q))
    _save(doc, path, out)
    return names


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.casefold().replace("(optional)", ""))


def _check_headings(items: list[_Item], by_number: dict[int, FormQuestion]) -> None:
    """Fields are named by question number, so a printed form made from older rows (a template Doc not rewritten)
    would name every field after a moved question wrongly. Each numbered heading printed must begin with its
    question's title (a printed form may leave trailing questions off; a shifted one mismatches where it prints)."""
    printed = {i.number: re.sub(r"^\s*\d+\.\s*", "", i.text) for i in items if i.kind == "heading"}

    def same(n: int, q: FormQuestion) -> bool:
        p, t = _words(printed.get(n, "")), _words(q.title)
        return p[:len(t)] == t or (len(p) >= 3 and t[:len(p)] == p)          # a long title may wrap after its start

    wrong = [f"{n}: printed {printed[n]!r}, the form asks "
             + (repr(by_number[n].title) if n in by_number else "nothing") for n in sorted(printed)
             if n not in by_number or not same(n, by_number[n])]
    if wrong:
        raise ValueError("the printed form does not match the form's questions (rewrite the template Doc: "
                         "jason packet ... --make-templates --yes): " + "; ".join(wrong[:3]))


def field_geometry(size: float) -> tuple[float, float]:
    """A single-line field's height and how far it runs below its writing rule, for typed text of ``size`` points to
    sit on the rule. Every viewer centres the text vertically (MuPDF, pdf.js, PDFBox, Acrobat, PDFium; Apple's PDFKit
    draws its own), its baseline about ``k·size`` below the centre (k 0.26 to 0.36 for Helvetica; 0.30 here). The
    baseline goes ``0.21·size + 0.5`` above the rule, clear of the descenders; the height is what pdf.js needs not to
    clip (1.35·size + 2), rounded up (research of October 1, 2026, docs/forms.md)."""
    height = max(16.0, round(1.8 * size, 1))
    gap = 0.40 * size + 0.5
    return height, round(height / 2 - gap - 0.30 * size, 2)


def _exact(question: FormQuestion | None) -> bool:
    """An answer a spell checker would only mark wrong: a name, an address, an email, a phone number."""
    from jason.community.forms import ReadAs

    return question is not None and question.reads_as in (ReadAs.NAME, ReadAs.ADDRESS, ReadAs.EMAIL, ReadAs.PHONE,
                                                          ReadAs.CONTACT)


# An address's labelled parts on its second row (form_render.ADDRESS_ROW), and the most each takes.
ADDRESS_PARTS = ("city", "state", "zip")
PART_MAX = {"state": 2, "zip": 10}


def _part_names(question: FormQuestion | None, base: str, row_sizes: list[int]) -> list[list[tuple[str, str]]]:
    """Each blank's field name and what it holds (for its tooltip), row by row. The first blank keeps the question's
    field; an address's "City __ State __ ZIP __" row is ``#city``, ``#state``, ``#zip``; any other blank after the
    first is its line, ``#2``, ``#3``."""
    from jason.community.forms import ReadAs
    from jason.community.pdf_fields import line_field

    address = question is not None and question.reads_as is ReadAs.ADDRESS
    out, n = [], 0
    for size in row_sizes:
        row = []
        for c in range(size):
            n += 1
            if address and size == len(ADDRESS_PARTS):
                row.append((line_field(base, ADDRESS_PARTS[c]), ADDRESS_PARTS[c].replace("zip", "ZIP")))
            elif n == 1:
                row.append((base, "street address, with apt, suite, or PMB" if address and len(row_sizes) > 1 else ""))
            else:
                row.append((line_field(base, n), "city, state, ZIP" if address else f"line {n}"))
        out.append(row)
    return out


def _label(question: FormQuestion | None) -> str:
    if question is None:
        return ""
    return question.title + (f". {question.help}" if question.help else "")


def _save(doc: Any, path: Path, out: Path | None) -> None:
    target = Path(out or path)
    if target == Path(path):
        tmp = Path(str(path) + ".tmp")
        doc.save(tmp)
        doc.close()
        tmp.replace(path)
    else:
        doc.save(target)
        doc.close()


REFERENCE_FIELD = "reference"          # a hidden, read-only field holding the copy's reference number


def with_reference(uri: str, reference: str, label: str = "Ref") -> str:
    """A ``mailto:`` link whose subject ends with ``[Ref reference]`` (the subject a sent copy's email carries), once."""
    from urllib.parse import parse_qsl, quote, urlencode

    address, _, query = uri.partition("?")
    params = dict(parse_qsl(query, keep_blank_values=True))
    subject = params.get("subject", "")
    if reference not in subject:
        params["subject"] = f"{subject} [{label} {reference}]".strip()
    return f"{address}?{urlencode(params, quote_via=quote)}"


def stamp_reference(path: Path, reference: str, out: Path | None = None, *, label: str = "Ref", bars: bool = True,
                    bar_gray: float = 0.35) -> Path:
    """Mark a PDF as one copy: ``label reference`` printed small at each page's top right (clear of the footer), the
    same marker as a bar mark at each page's top left (``form_marks``; in gray, like a watermark, by default), a
    hidden read-only field holding it (``read_answers`` reads it back from a returned PDF), and the PDF's keywords."""
    import pymupdf

    from jason.community import form_marks
    from jason.community.form_refs import parse
    from jason.community.pdf_fields import text_field

    target = Path(out or path)
    marker = next(iter(parse(reference)), None) if bars else None
    with pymupdf.open(path) as doc:
        for page in doc:
            if marker is not None:
                form_marks.draw(page, marker, gray=bar_gray)
            r = page.rect
            # 9 points, near black: smaller or lighter text is lost in a 150 dpi home scan (docs/form-identifiers.md).
            page.insert_textbox(pymupdf.Rect(r.width - 240, 12, r.width - 24, 30), f"{label} {reference}", fontsize=9,
                                fontname="helv", color=(0.2, 0.2, 0.2), align=pymupdf.TEXT_ALIGN_RIGHT)
            # A PDF cannot submit itself outside Acrobat; its email link is the return path every reader follows, so
            # the copy's reference rides in the subject and the reply comes back already matched
            for link in page.get_links():
                if str(link.get("uri") or "").startswith("mailto:"):
                    link["uri"] = with_reference(link["uri"], reference, label)
                    page.update_link(link)
        field = text_field(doc[0], REFERENCE_FIELD, pymupdf.Rect(0, 0, 1, 1), tooltip="Reference")
        for widget in doc[0].widgets() or []:
            if widget.field_name == REFERENCE_FIELD:
                widget.field_value = reference
                widget.field_flags |= pymupdf.PDF_FIELD_IS_READ_ONLY
                widget.field_display = pymupdf.PDF_WIDGET_HIDDEN if hasattr(pymupdf, "PDF_WIDGET_HIDDEN") else 1
                widget.update()
        meta = dict(doc.metadata or {})
        meta["keywords"] = " ".join(x for x in (meta.get("keywords") or "", f"jason-reference:{reference}") if x)
        doc.set_metadata(meta)
        tmp = target.with_suffix(".stamping.pdf")
        doc.save(tmp, garbage=3, deflate=True)
    tmp.replace(target)
    return target


def link_phrase(path: Path, phrase: str, uri: str, *, rewrite: Callable[[str], str] | None = None) -> int:
    """Make each place ``phrase`` is printed in the PDF a link to ``uri`` (one copy's own link: the form names the way,
    the copy carries the link), and pass every existing web link through ``rewrite`` when given. Returns the places
    linked."""
    import pymupdf

    found = 0
    with pymupdf.open(path) as doc:
        for page in doc:
            if rewrite is not None:                        # before adding links: a new one unsettles the page's list
                for link in page.get_links():
                    old = str(link.get("uri") or "")
                    if old.startswith("http") and rewrite(old) != old:
                        link["uri"] = rewrite(old)
                        page.update_link(link)
            for rect in page.search_for(phrase):
                page.insert_link({"kind": pymupdf.LINK_URI, "from": rect, "uri": uri})
                found += 1
        tmp = Path(path).with_suffix(".linking.pdf")
        doc.save(tmp, garbage=3, deflate=True)
    tmp.replace(path)
    return found


def read_answers(path: Path, form: FormTemplate, *, source: str = "pdf") -> FormAnswers:
    """The answers in a filled form by question field: the text typed, or the options chosen (a list, for a choice
    question too, so ``forms.check`` can see two choices where one was asked), plus the signature and date lines."""
    from jason.community.pdf_fields import values

    raw = values(path)
    answers: dict[str, Any] = {}
    for q in form.questions:
        if q.kind is QuestionKind.CHOICE and raw.get(q.field):
            answers[q.field] = [q.option_for(str(raw[q.field]))]
        elif q.kind in (QuestionKind.CHOICE, QuestionKind.CHECKBOX):
            chosen = [q.option_for(name.split(".", 1)[1]) for name, on in raw.items()
                      if name.startswith(q.field + ".") and on is True]
            if chosen:
                answers[q.field] = chosen
        elif raw.get(q.field):
            answers[q.field] = raw[q.field]       # an address written out stands, box or no box
        elif q.same_as and raw.get(q.same_as_field) is True:
            answers[q.field] = q.same_as          # "Same as my unit address"
    from jason.community.form_refs import parse

    found = parse(str(raw.get(REFERENCE_FIELD) or ""))
    return FormAnswers(form.key, answers, source=source, signature=str(raw.get("signature") or ""),
                       signed=str(raw.get("date") or ""), reference=found[0].text if found else "")


def read_fillable(path: Path, questions: Iterable[FormQuestion] = ()) -> dict[str, Any]:
    """The answers in a filled form by question title (text, or a list of the options checked)."""
    from jason.community.forms import FormKey

    questions = tuple(questions)
    form = FormTemplate(FormKey.OWNER_INFO, "", "", "", questions)
    return read_answers(path, form).by_title(form)


__all__ = ["make_fillable", "read_answers", "read_fillable"]
