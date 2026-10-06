"""Recognition: given a message or an attachment, is it a response to a form jason sent, and which copy?
(docs/arrivals-design.md, "Recognition is the crux" and "The sent-copy catalog".)

Every copy jason sends carries its reference in several places, so there are several chances to read it. ``recognize``
tries them cheapest first and stops at the first sure answer:

====  ===========  ================================================================  ==========================
rung  name         signal                                                            cost
====  ===========  ================================================================  ==========================
1     subject      ``[Ref NP27E-…]`` in the subject (a reply keeps it) or the body   headers only
2     text-layer   the same in an attachment's text layer (the mail service's        one download; no OCR
                   ``text.txt``, a PDF's text and keywords)
3     field        the hidden ``reference`` field of a returned fillable PDF          one download; no OCR
4     mark         the bar mark and the printed marker on a scan or a photo           one download; OCR
5     layout       the form by its printed lines (``form_reader.identify_form``)      one download; OCR
6     citation     the form's cited authority and printed title in the text           free once the text is read
7     sender       an owner who was sent a copy and has not answered, with a PDF or   free
                   an image: it decides only whether to download, never the result
====  ===========  ================================================================  ==========================

Rungs 1 to 4 end in the sent-copy catalog (``data/forms/references.json``, ``form_references``) and so in a copy: the
form, the cycle, the owner and unit **as sent**, the membership id, the channel, and when it was first sent. That is a
**recognized** copy. A reference one character off is taken to the one sent reference it is near, and says so. A reference
whose check holds but which no sent copy carries is a finding ("a reference we did not send"). Rungs 5 and 6 name a form
and a process but no copy: a **candidate**, which a person attaches to a campaign. Anything else is **not ours** and
leaves this path.

Nothing recognized or unrecognized is final: the result keeps the rung that decided it, how sure it is, and a note in
plain words. The functions take text, bytes, and paths, call no service, and write nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

DPI = 200
SOLID_TEXT = 200                 # characters: a page whose text layer holds this much is read from it, not by OCR
PAGES = 3                        # pages of an attachment read as images (the reference is on every page of a copy)
LAYER_PAGES = 20                 # pages whose text layer is read
FORM_FILE_TYPES = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic")
_WORDS = re.compile(r"[a-z0-9]+")


class Outcome(Enum):
    RECOGNIZED = "recognized"    # a copy of a form we sent, with the owner and unit as sent
    CANDIDATE = "candidate"      # looks like one of our forms; a person decides
    NOT_OURS = "not-ours"        # an invoice, the governing documents, another party's form: it leaves this path


class Rung(Enum):
    SUBJECT = "subject"
    TEXT_LAYER = "text-layer"
    FIELD = "field"
    MARK = "mark"
    LAYOUT = "layout"
    CITATION = "citation"
    SENDER = "sender"

    @property
    def number(self) -> int:
        return list(Rung).index(self) + 1


class Sure(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# -- the sent-copy catalog ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class SentCopy:
    """One entry of the sent-copy catalog: a copy (or a campaign's mailed letter) jason sent. Ids and hashes only."""

    reference: str
    form: str = ""
    year: int | None = None
    channel: str = ""                       # "email" or "mail"
    unit: str = ""                          # the unit's label as sent; empty for a campaign
    unit_id: int | None = None
    membership_id: int | None = None
    first_sent: str = ""
    last_sent: str = ""
    batch: str = ""

    @property
    def identity(self) -> str:
        """"copy" when the reference names one owner and unit; "campaign" when every copy of the mailing is the same."""
        return "copy" if self.membership_id is not None and self.unit_id is not None else "campaign"

    @property
    def campaign(self) -> str:
        from jason.community.form_refs import parse

        markers = parse(self.reference)
        return markers[0].campaign if markers else ""

    @classmethod
    def from_entry(cls, reference: str, entry: Mapping[str, Any]) -> SentCopy:
        def number(key: str) -> int | None:
            value = entry.get(key)
            return int(value) if value is not None and str(value).lstrip("-").isdigit() else None

        return cls(reference, str(entry.get("form") or ""), number("year"), str(entry.get("channel") or "").casefold(),
                   str(entry.get("unit") or ""), number("unitId"), number("membershipId"), str(entry.get("firstSent") or ""),
                   str(entry.get("lastSent") or ""), str(entry.get("batch") or ""))

    def to_json(self) -> dict[str, Any]:
        return {"reference": self.reference, "form": self.form, "year": self.year, "channel": self.channel,
                "identity": self.identity, "unit": self.unit, "unitId": self.unit_id, "membershipId": self.membership_id,
                "firstSent": self.first_sent, "lastSent": self.last_sent}


@dataclass(frozen=True)
class Found:
    """A reference read from some text: the marker, how it was taken (whole; put right by one character; taken to the one
    sent reference it is near), and whether jason sent it."""

    reference: str
    how: str                    # "whole", "put right", "near"
    sent: bool = True


class Catalog:
    """``data/forms/references.json`` held in memory (``form_references.load``), with the lookup ``form_references.lookup``
    makes: a marker whose check holds is the sent copy it names; one that fails is taken to the one sent marker it is
    near. Kept apart so a caller reading many messages loads the file once."""

    def __init__(self, refs: Mapping[str, Mapping[str, Any]]) -> None:
        self.refs = dict(refs)
        self._sent: list[Any] | None = None

    @classmethod
    def load(cls, data_dir: Path) -> Catalog:
        from jason.tasks import form_references

        return cls(form_references.load(Path(data_dir)))

    def __bool__(self) -> bool:
        return bool(self.refs)

    @property
    def sent(self) -> list[Any]:
        from jason.community.form_refs import parse

        if self._sent is None:
            self._sent = [m for key in self.refs for m in parse(key)]
        return self._sent

    def copy(self, reference: str) -> SentCopy | None:
        entry = self.refs.get(reference)
        return SentCopy.from_entry(reference, entry) if entry is not None else None

    def copies(self) -> list[SentCopy]:
        return [SentCopy.from_entry(k, v) for k, v in sorted(self.refs.items())]

    def find(self, text: str) -> Found | None:
        """The reference ``text`` carries, or None. A sent reference is preferred over one we did not send; a marker
        that fails its check counts only when it is one character from exactly one sent marker (``closest``) or reads as
        a sent marker with one character put right (``repaired``): a hint, never a guess among several."""
        from jason.community.form_refs import closest, parse, repaired

        if not text or not text.strip():
            return None
        whole = parse(text)
        for marker in whole:
            if marker.text in self.refs:
                return Found(marker.text, "whole")
        if self.refs:
            near = closest(text, self.sent)
            if near is not None and near.text in self.refs:
                return Found(near.text, "near")
            for marker in repaired(text):
                if marker.text in self.refs:
                    return Found(marker.text, "put right")
        if whole and self.refs:                 # with no catalog at all, nothing can be said to be "not sent"
            return Found(whole[0].text, "whole", sent=False)
        return None


# -- what comes in ------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Attachment:
    """One attachment: its bytes or its path, or only its name (listed, not downloaded). ``text`` is a text layer already
    read (the mail service's ``text.txt``)."""

    name: str = ""
    data: bytes | None = None
    path: Path | None = None
    text: str = ""

    def content(self) -> bytes | None:
        if self.data is not None:
            return self.data
        if self.path is not None and Path(self.path).is_file():
            return Path(self.path).read_bytes()
        return None

    @property
    def label(self) -> str:
        return self.name or (Path(self.path).name if self.path is not None else "an attachment")

    @property
    def listed_only(self) -> bool:
        return self.data is None and self.path is None and not self.text

    @property
    def form_file(self) -> bool:
        """A PDF or an image by its name (a returned form could be one of these)."""
        name = (self.name or (Path(self.path).name if self.path is not None else "")).lower()
        return name.endswith(FORM_FILE_TYPES) or (self.data is not None and self.data[:5] == b"%PDF-")


def _open(att: Attachment) -> Any:
    """The attachment as a PyMuPDF PDF document (an image converted), or None when it has no bytes or cannot be opened."""
    import pymupdf

    data = att.content()
    if not data:
        return None
    try:
        if data[:5] == b"%PDF-":
            return pymupdf.open(stream=data, filetype="pdf")
        kind = "png" if data[:4] == b"\x89PNG" else "jpeg" if data[:2] == b"\xff\xd8" else \
            "tiff" if data[:4] in (b"II*\x00", b"MM\x00*") else Path(att.label).suffix.lstrip(".").lower() or "png"
        with pymupdf.open(stream=data, filetype=kind) as image:
            return pymupdf.open("pdf", image.convert_to_pdf())
    except Exception:  # noqa: BLE001 - a file that cannot be opened is reported, not raised
        return None


def _layer(doc: Any) -> str:
    """A PDF's text layer and its keywords (a stamped copy keeps ``jason-reference:`` there)."""
    parts = [doc[i].get_text() or "" for i in range(min(doc.page_count, LAYER_PAGES))]
    keywords = (doc.metadata or {}).get("keywords") or ""
    return "\n".join([*parts, keywords]) if keywords else "\n".join(parts)


def _field_reference(doc: Any) -> str:
    """The hidden ``reference`` field of a returned fillable PDF (``fillable.REFERENCE_FIELD``)."""
    from jason.community.fillable import REFERENCE_FIELD

    try:
        for index in range(min(doc.page_count, 2)):
            for widget in doc[index].widgets() or []:
                if widget.field_name == REFERENCE_FIELD and widget.field_value:
                    return str(widget.field_value)
    except Exception:  # noqa: BLE001 - a PDF whose fields cannot be read has no field to read
        return ""
    return ""


def _ocr_ready() -> bool:
    from jason.community.ocr import PyMuPdfTesseract

    return PyMuPdfTesseract.available()


# -- the result ---------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Recognition:
    """What an arrival is, and how that was found out."""

    outcome: Outcome
    rung: Rung | None                     # the rung that decided it (for not ours, the last rung that was tried)
    sure: Sure
    note: str                             # in plain words: what was found, where, and what it does not prove
    copy: SentCopy | None = None          # the copy sent, for a recognized arrival
    form: str = ""                        # a known form's key, or ""
    authority: str = ""                   # the form's authority ("Civil Code 4041"), or ""
    reference: str = ""                   # the marker as read (a hint)
    how: str = ""                         # whole, put right, near; and where it was read ("the printed marker", "bars")
    matches_request: bool | None = None   # whether the copy's campaign is the request's
    unsent: bool = False                  # a reference whose check holds that no sent copy carries: "we did not send it"
    worth_download: bool = False          # rung 7: a PDF or image from an owner who was asked and has not answered
    tried: tuple[Rung, ...] = ()
    lines: int = 0                        # printed lines matched, for a layout reading

    @property
    def recognized(self) -> bool:
        return self.outcome is Outcome.RECOGNIZED

    def to_json(self) -> dict[str, Any]:
        return {"outcome": self.outcome.value, "rung": self.rung.value if self.rung else "",
                "rungNumber": self.rung.number if self.rung else 0, "sure": self.sure.value, "note": self.note,
                "form": self.form, "authority": self.authority, "reference": self.reference, "how": self.how,
                "matchesRequest": self.matches_request, "unsent": self.unsent, "worthDownload": self.worth_download,
                "tried": [r.value for r in self.tried], "lines": self.lines,
                "copy": self.copy.to_json() if self.copy else None}


def _day(stamp: str) -> str:
    return stamp[:10]


def _sent_words(copy: SentCopy) -> str:
    when = f" on {_day(copy.first_sent)}" if copy.first_sent else ""
    if copy.identity == "copy":
        return f"the copy sent{when} to {copy.unit or 'one owner'}"
    return f"the {copy.channel or 'campaign'} mailing sent{when} (its marker names the mailing, not an owner)"


def _recognized(found: Found, rung: Rung, where: str, cat: Catalog, request: Any, tried: list[Rung], *,
                reader_how: str = "") -> Recognition:
    copy = cat.copy(found.reference)
    assert copy is not None
    put_right = found.how != "whole" or "put right" in reader_how
    sure = Sure.MEDIUM if put_right else Sure.HIGH
    matches = request.names_campaign(copy.campaign) if request is not None and getattr(request, "marker_campaigns", ()) else None
    form = copy.form or (request.form.key.value if request is not None and matches else "")
    authority = request.form.authority if request is not None and request.form.key.value == form else ""
    how = found.how if found.how != "whole" or "put right" not in reader_how else "put right"
    note = f"{where[:1].upper()}{where[1:]} carries reference {found.reference}: {_sent_words(copy)}."
    if put_right:
        note += (" One character was put right to make it the reference of a sent copy; it is a hint to confirm against "
                 "the copy, not a reading.")
    if matches is False:
        note += " Its campaign is not this request's."
    return Recognition(Outcome.RECOGNIZED, rung, sure, note, copy, form, authority, found.reference, how, matches,
                       tried=tuple(tried))


def identify_reference(catalog: Catalog, text: str, rung: Rung, *, request: Any = None, where: str = "the page",
                       reader_how: str = "") -> Recognition | None:
    """A reference already read (by the form reader, from a page or a field) taken to its sent copy: a Recognized, or None
    when ``text`` names no sent copy."""
    found = catalog.find(text)
    if found is None or not found.sent:
        return None
    return _recognized(found, rung, where, catalog, request, [rung], reader_how=reader_how)


# -- the ladder ---------------------------------------------------------------------------------------------------------

def _words(text: str) -> str:
    return " ".join(_WORDS.findall((text or "").casefold()))


def citation_pattern(authority: str) -> re.Pattern | None:
    """A pattern for the statute ``authority`` names ("Civil Code 4041"), as a text writes it ("Civil Code § 4041",
    "Civ. Code, section 4041", "CIV 4041"), not matching a longer number. None when the authority is not a citation."""
    from jason.community.references import CODES, statute_citation

    cited = statute_citation(authority or "")
    if cited is None:
        return None
    names = [p for p, code in CODES if code == cited.code] + [re.escape(cited.code)]
    number = re.escape(cited.number)
    return re.compile(rf"(?:{'|'.join(f'(?:{n})' for n in names)})[\s,.:]*(?:(?:sections?|secs?\.?|§§?)\s*)?{number}(?![\d.]\d|\d)",
                      re.I)


def same_place(a: str, b: str) -> bool | None:
    """Whether two unit labels name one place: the same house number and street name's first word ("4000 Oak Dr" and
    "4000 Oak Drive, Sacramento, CA"). None when either is empty."""
    x, y = _WORDS.findall((a or "").casefold()), _WORDS.findall((b or "").casefold())
    if not x or not y:
        return None
    if x[0].isdigit() and y[0].isdigit():
        if x[0] != y[0]:
            return False
        return x[1] == y[1] if len(x) > 1 and len(y) > 1 else True
    return x == y


def _forms_of(request: Any, forms: Iterable[Any]) -> tuple[Any, ...]:
    forms = tuple(forms)
    return forms or ((request.form,) if request is not None else ())


def layouts_for(data_dir: Path, request: Any) -> list[Any]:
    """The layout of the request's blank fillable form (the page lines a scan is matched to), or none."""
    blank = Path(data_dir) / request.blank if request is not None and getattr(request, "blank", "") else None
    if blank is None or not blank.is_file():
        return []
    try:
        from jason.community.form_layout import read_layout

        return [read_layout(blank, request.form)]
    except Exception:  # noqa: BLE001 - a blank that cannot be laid out is no layout
        return []


def recognize(data_dir: Path, request: Any = None, *, subject: str = "", body: str = "",
              attachments: Sequence[Attachment] = (), sender_asked: bool | None = None, forms: Iterable[Any] = (),
              layouts: Sequence[Any] | None = None, catalog: Catalog | None = None, images: bool = True,
              dpi: int = DPI) -> Recognition:
    """Is this message a response to a form jason sent, and which copy? ``subject`` and ``body`` are read as text,
    ``attachments`` as files (bytes, a path, a text layer already read, or just a name when nothing was downloaded).
    ``sender_asked`` is whether the sender was sent a copy and has not answered (None when not known): rung 7, which only
    says whether a download is worth it. ``request`` (a ``ResponseRequest``) names the form, its campaigns, and its blank
    form; ``forms`` and ``layouts`` add known forms for rungs 5 and 6. With ``images`` False no page image is read (no bar
    mark, OCR, or layout): the cheap rungs 1 to 3 and the citation in text. Never raises for a file that will not open."""
    cat = catalog if catalog is not None else Catalog.load(Path(data_dir))
    known = _forms_of(request, forms)
    tried: list[Rung] = []
    problems: list[str] = []
    unsent: list[tuple[Found, Rung, str]] = []

    def take(found: Found | None, rung: Rung, where: str, reader_how: str = "") -> Recognition | None:
        if found is None:
            return None
        if not found.sent:
            unsent.append((found, rung, where))
            return None
        return _recognized(found, rung, where, cat, request, tried, reader_how=reader_how)

    # 1. the subject, then a quoted body: headers and text already in hand
    tried.append(Rung.SUBJECT)
    for where, text in (("the subject", subject), ("the message's text", body)):
        if (done := take(cat.find(text), Rung.SUBJECT, where)) is not None:
            return done
    texts: list[str] = [subject or "", body or ""]
    opened: list[tuple[Attachment, Any]] = []
    try:
        for att in attachments:
            doc = _open(att)
            if doc is None and not att.text and not att.listed_only:
                problems.append(f"{att.label} could not be opened")
            opened.append((att, doc))
        # 2. an attachment's text layer
        if any(att.text or doc is not None for att, doc in opened):
            tried.append(Rung.TEXT_LAYER)
        for att, doc in opened:
            layer = att.text or (_layer(doc) if doc is not None else "")
            texts.append(layer)
            if (done := take(cat.find(layer), Rung.TEXT_LAYER, f"the text of {att.label}")) is not None:
                return done
        # 3. a returned fillable PDF's hidden reference field
        if any(doc is not None for _, doc in opened):
            tried.append(Rung.FIELD)
        for att, doc in opened:
            if doc is None:
                continue
            if (done := take(cat.find(_field_reference(doc)), Rung.FIELD, f"the hidden reference field of {att.label}")) is not None:
                return done
        # 4 and 5. the bar mark and the printed marker on a page image; the form by its layout
        looked: list[tuple[Attachment, Any]] = [(a, d) for a, d in opened if d is not None]
        layout_hit: tuple[Any, int] | None = None
        if images and looked:
            ocr = _ocr_ready()
            if not ocr:
                problems.append("Tesseract is not available, so printed text on a scan could not be read")
            done, extra, pages = _read_pages(looked, cat, request, take, tried, ocr, dpi, problems)
            texts += extra
            if done is not None:
                return done
            have = layouts if layouts is not None else layouts_for(Path(data_dir), request)
            if have and pages:
                tried.append(Rung.LAYOUT)
                layout_hit = _identify(pages, list(have), dpi)
    finally:
        for _, doc in opened:
            if doc is not None:
                doc.close()

    # 6. the cited authority and the printed title, in the text
    tried.append(Rung.CITATION)
    cited, titled = _cites("\n".join(texts), known)
    candidate = _candidate(layout_hit, cited, titled, known, tried)
    # 7. the sender: only whether a download is worth it (a PDF or image named, not downloaded, from an owner who was
    # sent a copy and has not answered)
    worth = bool(sender_asked) and any(a.form_file and a.listed_only for a in attachments)
    if sender_asked is not None:
        tried.append(Rung.SENDER)
    flag = unsent[0] if unsent else None
    extra_note = ""
    if flag is not None:
        extra_note = (f" It also carries {flag[0].reference} in {flag[2]}, a reference we did not send: it may be from "
                      "another association, an old test, or a misread; a person looks at it.")
    if candidate is not None:
        return replace(candidate, worth_download=worth, note=candidate.note + extra_note, unsent=flag is not None,
                       reference=flag[0].reference if flag else "", tried=tuple(tried))
    read = [a for a in attachments if not a.listed_only]
    looked_at = (["the subject and text"] if (subject or body) else []) + [a.label for a in read]
    listed = [a.label for a in attachments if a.listed_only]
    note = ("Nothing read names a form we sent: no reference of ours, no returned form's layout, and no citation of a form's "
            "authority" + (f" (looked at {', '.join(looked_at)})" if looked_at else "") + ".")
    if listed:
        note += f" Not downloaded: {', '.join(listed)}."
    if worth:
        note += " The sender was sent a copy and has not answered, so the attachment is worth downloading."
    if problems:
        note += " " + "; ".join(problems) + "."
    content = [r for r in tried if r is not Rung.SENDER]
    return Recognition(Outcome.NOT_OURS, content[-1] if content else None, Sure.MEDIUM if read else Sure.LOW,
                       note + extra_note, reference=flag[0].reference if flag else "", unsent=flag is not None,
                       worth_download=worth, tried=tuple(tried))


def _read_pages(looked: list[tuple[Attachment, Any]], cat: Catalog, request: Any, take: Any, tried: list[Rung], ocr: bool,
                dpi: int, problems: list[str]) -> tuple[Recognition | None, list[str], list[Any]]:
    """Rung 4: each attachment's first pages as images: the page's text (its layer when it holds enough, else OCR), then the
    bar mark and the printed marker (``form_reader.find_marker``). Returns the recognition when a sent copy was named, the
    pages' text for the citation rung, and the pages for the layout rung."""
    from jason.community.form_reader import find_marker, gray_of, ocr_lines

    tried.append(Rung.MARK)
    texts: list[str] = []
    pages: list[Any] = []
    for att, doc in looked:
        for index in range(min(doc.page_count, PAGES)):
            page = doc[index]
            pages.append(page)
            try:
                layer = page.get_text() or ""
                if len(layer.strip()) >= SOLID_TEXT or not ocr:
                    text = layer
                else:
                    text = "\n".join(t for t, _ in ocr_lines(gray_of(page, dpi=dpi), dpi=dpi))
                texts.append(text)
                marker, how = find_marker(page, text, dpi=dpi)
            except Exception as exc:  # noqa: BLE001 - a page that cannot be read is reported, not raised
                problems.append(f"{att.label} page {index + 1} could not be read ({type(exc).__name__})")
                continue
            if how == "disagree":
                problems.append(f"{att.label} page {index + 1}: the printed marker and the bar mark name different copies, "
                                "so neither is used")
            if marker:
                where = {"text": "the printed marker", "bars": "the bar mark", "text and bars": "the printed marker and the bar mark"}
                label = where.get(how.replace(" (put right)", ""), "the page")
                done = take(cat.find(marker), Rung.MARK, f"{label} on page {index + 1} of {att.label}", how)
                if done is not None:
                    return done, texts, pages
    return None, texts, pages


def _identify(pages: list[Any], layouts: list[Any], dpi: int) -> tuple[Any, int] | None:
    """Rung 5: the layout whose printed lines a scanned page matches most, over the pages given."""
    from jason.community.form_reader import identify_form

    best: tuple[Any, int] | None = None
    for page in pages:
        try:
            layout, _, lines = identify_form(page, layouts, dpi=dpi)
        except Exception:  # noqa: BLE001 - a page that cannot be matched names no form
            continue
        if layout is not None and (best is None or lines > best[1]):
            best = (layout, lines)
    return best


def _cites(text: str, forms: Sequence[Any]) -> tuple[list[Any], list[Any]]:
    """The forms whose authority the text cites, and those of them whose printed title it also carries."""
    words = _words(text)
    cited, titled = [], []
    for form in forms:
        pattern = citation_pattern(getattr(form, "authority", ""))
        if pattern is not None and pattern.search(text or ""):
            cited.append(form)
            if _words(form.title) and f" {_words(form.title)} " in f" {words} ":
                titled.append(form)
    return cited, titled


def _candidate(layout_hit: tuple[Any, int] | None, cited: list[Any], titled: list[Any], forms: Sequence[Any],
               tried: list[Rung]) -> Recognition | None:
    """The best candidate from rungs 5 and 6: the layout's form, or the form whose authority the text cites. A citation
    alone is a lead, not proof: a policy statement or a reply quotes the same section."""
    by_key = {f.key.value: f for f in forms}
    form = by_key.get(layout_hit[0].form) if layout_hit is not None else None
    lines = layout_hit[1] if layout_hit is not None else 0
    points, rung, how = 0, Rung.CITATION, []
    if layout_hit is not None:
        points += 2 if lines >= 8 else 1
        rung = Rung.LAYOUT
        how.append(f"its printed lines match the {layout_hit[0].form} form's on {lines} line(s)")
    pick = next((f for f in cited if form is None or f is form), None)
    if pick is not None:
        form = form or pick
        points += 1 + (1 if pick in titled else 0)
        how.append(f"it cites {pick.authority}" + (f" and carries the printed title {pick.title!r}" if pick in titled else
                                                    " but not the form's printed title"))
    if layout_hit is None and pick is None:
        return None
    sure = Sure.HIGH if points >= 4 else Sure.MEDIUM if points >= 2 else Sure.LOW
    key = form.key.value if form is not None else layout_hit[0].form
    authority = form.authority if form is not None else ""
    note = ("; ".join(how).capitalize() + ". That names the form and its process, not a copy we sent: a retyped or "
            "photocopied form, a reply that quotes the law, or a policy statement can look the same. A person decides, and "
            "attaches it to a campaign if it is a return.")
    return Recognition(Outcome.CANDIDATE, rung, sure, note, form=key, authority=authority, tried=tuple(tried), lines=lines)


# -- comparing the copy with the sender and the page ----------------------------------------------------------------------

@dataclass(frozen=True)
class Comparison:
    """The copy as sent, against the owner the sender's address belongs to and the unit written on the page. ``None`` is
    "cannot tell" (an id or a name is missing), never "no"."""

    matches_unit: bool | None = None
    matches_owner: bool | None = None
    matches_written: bool | None = None
    notes: tuple[str, ...] = ()


def compare(copy: SentCopy | None, *, owner: Any = None, written_unit: str = "", sent_name: str = "") -> Comparison:
    """The copy's unit and owner as sent against ``owner`` (the owner the sender's address matched: ``unit``, ``unit_id``,
    ``membership_id``, ``name``) and ``written_unit`` (the unit address the form names). A campaign's marker names no unit
    or owner, so nothing is compared. Each disagreement is a plain note."""
    if copy is None or copy.identity != "copy":
        return Comparison()
    notes: list[str] = []
    unit: bool | None = None
    if owner is not None:
        unit_id = getattr(owner, "unit_id", None)
        unit = (copy.unit_id == int(unit_id)) if unit_id is not None else same_place(copy.unit, getattr(owner, "unit", ""))
        if unit is False:
            notes.append(f"the copy was sent to {copy.unit or 'one unit'}, but the sender's address belongs to "
                         f"{getattr(owner, 'unit', '') or 'another unit'}")
    person: bool | None = None
    if owner is not None and getattr(owner, "membership_id", None) is not None and copy.membership_id is not None:
        person = copy.membership_id == int(owner.membership_id)
        if person is False and unit is not False:
            notes.append(f"the copy was sent to {sent_name or 'a different owner'}, but the sender's address belongs to "
                         f"{getattr(owner, 'name', '') or 'another owner'}")
    written = same_place(copy.unit, written_unit) if written_unit else None
    if written is False:
        notes.append(f"the copy was sent to {copy.unit or 'one unit'}, but the form names {written_unit.strip()}")
    return Comparison(unit, person, written, tuple(notes))


__all__ = ["Attachment", "Catalog", "Comparison", "Found", "Outcome", "Recognition", "Rung", "SentCopy", "Sure", "citation_pattern",
           "compare", "identify_reference", "layouts_for", "recognize", "same_place"]
