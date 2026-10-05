"""Which document a citation means: reading a citation as written, and scoping it to one document or to several.

A citation of the association's own documents is often written without its document: "Section 7.8" in the minutes,
"R-3(e)" in a letter, "Article 4" in a policy, "this Declaration" in the Declaration, "the Rules" anywhere. The
documents number their sections alike (two of them have a 7.8), so a number alone does not name a section. ``scope``
decides which document is meant from what is written and from where it is written, and says how:

- **Named.** The citation names the document ("Bylaws 7.8", "Rule 2.1 of the Lot Rules"), by a name the
  specification gives it.
- **Self.** "this Declaration", "these Bylaws" in the Declaration or the Bylaws: the citing document.
- **Citing.** A bare "Section 7.8" inside a document that has a 7.8: that document's own. (A bare section in an
  amendment or an annexation is the document it amends: **Amends**.)
- **Only.** A bare number outside the documents (minutes, a letter, a rule row), where exactly one document has it.
- **Form.** The kind of thing cited narrows the documents: a rule's letter-number ("R-3(e)", "R-3(e)") belongs to the
  documents that number their rules so; the word "Article" to the documents that have articles; the word "Rule" to
  the rules documents.
- **Book.** A common name for a book that holds several documents ("the Rules": the owner's manual's rules, the
  parking rules, each separately adopted) is the document of that book that has the section.
- **Part.** The same rule is printed in a part of one document and in the document adopted apart. When both print
  the same words, the section means the document adopted apart, and the other is listed as a reprint.

Where two documents fit, the result is **ambiguous** and names both, each with its own citation; a guess is never
made. A document name written near the citation (the minutes' "CC&R" earlier in the paragraph) is a lead, listed
beside the candidates and never a pick. The citing document's date reads a document kept as amended in the version in
force that day (``Index.has``), so a number the Declaration had on that day is found as the Declaration had it.

This module is pure: it reads no disk. ``jason.tasks.cite.Shelf.index`` builds the ``Index`` from the specification
and the outlines on disk. A ``Part`` is a separately addressed part of one document (the rules inside an owner's
manual): see ``Part`` for what segmentation supplies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any, Callable, Iterable

from jason.community.outlines import _arabic, normalize_number
from jason.community.references import CODES, ancestors

# --- What is written ---------------------------------------------------------------------------------------------------


class Form(Enum):
    """The shapes a citation of an association document takes."""

    SECTION = "section"                     # "Section 7.8", "Bylaws 7.8", "§ 7.8(a)"
    ARTICLE = "article"                     # "Article 4", "Article IV of the Bylaws"
    RULE_LETTERED = "rule, lettered"        # "R-3(e)", "Rules R-3(e)"
    RULE_NUMBERED = "rule, numbered"        # "Rule 2.1 of the Lot Rules"
    SELF = "self-reference"                 # "this Declaration", "these Bylaws"
    DOCUMENT = "whole document"             # "the Rules and Regulations", "the Declaration"
    ROW = "jason's rule row"                # "owner_responses.RULES: delivery"
    ADDRESS = "address"                     # "ccrs#4.15(a)", "rules#R-3": a document's key and a number, exact
    UNKNOWN_DOCUMENT = "unknown document"   # "Section 4 of the Master Plan": names a document nothing here holds


_LABELS = r"(?:\s?\(\s*[A-Za-z0-9]{1,5}\s*\))*"
_LETTERED = r"[A-Z]{1,2}-\d+(?:\.\d+)*"
_NUM = rf"(?:{_LETTERED}|\d+(?:\.\d+)*){_LABELS}"
# "�" is the "§" a scan's text lost to an encoding error: read as a section sign.
_WORD = r"(?:Sections?|Secs?\.?|§§?|�|Articles?|Arts?\.|Rules?|Paragraphs?|Paras?\.|¶)"
_WORD_NOT_RULE = r"(?:Sections?|Secs?\.?|§§?|�|Articles?|Arts?\.|Paragraphs?|Paras?\.|¶)"
# Numbers named together: "6.2, 6.3, and (b)". A further "Section 6.3 of ..." starts its own citation.
# A list keeps the style of its first number: "(?(lt)...)" is true when the first number is a rule's letter-number.
_LIST = (rf"(?:\s*(?:,\s*(?:and|or)?|\band\b|\bor\b|&)\s*(?:(?(lt){_LETTERED}|\d+(?:\.\d+)*){_LABELS}"
         r"|\(\s*[A-Za-z0-9]{1,5}\s*\)))*")
_RANGE = rf"(?:\s*(?:through|thru|to|–|—|-)\s*(?:{_WORD}\s*)?{_NUM})?"
_CODE = "|".join(f"(?:{p})" for p, _ in CODES)
_ROMAN = r"[IVXLC]{1,6}"


def _name_pattern(names: Iterable[str]) -> str:
    alt = sorted({n for n in names if n}, key=len, reverse=True)
    return "|".join(re.escape(n).replace(r"\ ", r"\s+").replace(r"\-", r"[-\s]?").replace(",", ",?") for n in alt) or r"(?!x)x"


def _norm_name(name: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^(?:the|these|this|said)\s+", "", (name or "").strip().lower(), flags=re.I)).replace("’", "'")


@dataclass(frozen=True)
class Mention:
    """One citation as written: where, in what shape, and what it names."""

    form: Form
    text: str                              # the words as written
    start: int
    end: int
    name: str = ""                         # the document's name as written ("Lot Rules"), "" when none
    demonstrative: str = ""                # "this", "these", or "said" before the name
    word: str = ""                         # "Section", "Article", "Rule", "§": as written
    number: str = ""                       # the first number, normalized ("7.8(a)", "R-3(e)", "4")
    numbers: tuple[str, ...] = ()          # every number named together ("7.8", "7.9")
    article: bool = False
    other: str = ""                        # an unknown document's name, as written
    context: tuple[str, ...] = ()          # document names written earlier in the same paragraph (a lead only)
    name_span: tuple[int, int] = (0, 0)    # where the document's name is in the text scanned

    @property
    def named(self) -> bool:
        return bool(self.name)

    @property
    def lettered(self) -> bool:
        return bool(re.match(r"[A-Z]{1,2}-\d", self.number))

    @property
    def expression(self) -> str:
        """The words as a citation reader takes them, with the document's name and the number: a name that stands after a
        list ("Section 6.5(d) and Section 6.6(c) of the Declaration") is put after this one too."""
        if self.name and self.name_span == (0, 0) and self.form not in (Form.DOCUMENT, Form.SELF, Form.ROW, Form.ADDRESS):
            return f"{self.text} of the {self.name}"
        return self.text


def _numbers(text: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(normalize_number(m.group(0)) for m in re.finditer(_NUM, text)))


def _is_code(text: str) -> bool:
    return bool(re.fullmatch(_CODE, " ".join((text or "").split()), re.I))


def _rule_context(text: str, at: int) -> bool:
    """A lettered number counts as a rule's when the word "rule" stands right before it ("Rule R-3", "Rules R-3(e)", "see
    rule no. R-3"): a form's code ("HO-6") or a highway has none."""
    return bool(re.search(r"\b(?:rules?|regulations?)\s+(?:no\.?\s*|number\s+)?$", text[max(0, at - 24):at], re.I))


def _line_start(text: str, at: int) -> bool:
    """Whether ``at`` is the first word of its line (past a Markdown heading or emphasis mark)."""
    return re.fullmatch(r"[ \t#*_>|-]*", text[text.rfind("\n", 0, at) + 1:at]) is not None


def _rest_of_line(text: str, at: int) -> str:
    stop = text.find("\n", at)
    return text[at:stop if stop >= 0 else len(text)]


def _heading(text: str, start: int, end: int) -> bool:
    """A line that is only "ARTICLE 5", "ARTICLE 5 - TITLE", or "Article 5. TITLE" in capitals: a heading, not a citation."""
    if not _line_start(text, start):
        return False
    return re.match(r"\s*(?:$|[-–—.:]|[A-Z][A-Z ,&'/-]{3,}\s*$)", _rest_of_line(text, end)) is not None


_FUNCTION_WORDS = frozenset({
    "the", "this", "these", "said", "see", "under", "per", "and", "or", "of", "in", "by", "for", "to", "as", "with", "at",
    "any", "all", "each", "no", "such", "those", "their", "its", "our", "if", "when", "where", "whether", "subject",
    "pursuant", "that", "which", "a", "an", "from", "on", "into", "than", "then", "but", "not", "are", "is", "be", "shall",
    "may", "must", "will", "also", "both", "other", "same", "only", "new", "current", "adopted", "revised", "proposed"})


def _compound(text: str, at: int) -> bool:
    """Whether the name at ``at`` ends a longer capitalized title ("Decorum Rules", "Board Policy Rules"): the word
    right before it starts with a capital and is not a function word."""
    m = re.search(r"([A-Za-z][A-Za-z'’-]*)[ \t]+$", text[max(0, at - 40):at])
    return bool(m) and m.group(1)[:1].isupper() and m.group(1).lower() not in _FUNCTION_WORDS


def _statute_like(number: str) -> bool:
    """A section number the association's documents do not reach: a code's section ("602", "1355", "308.1.4"). The
    documents number their sections from 1 to under 100."""
    m = re.match(r"\d+", number or "")
    return bool(m) and int(m.group(0)) >= 100


def scan(text: str, names: dict[str, str], *, lettered: Iterable[str] = (), document_names: bool = True,
         rows: Iterable[str] = (), headings: bool = True, keys: Iterable[str] = ()) -> list[Mention]:
    """Every citation of an association's document in ``text``, in order. ``names`` maps each lowercase name a document
    goes by to its key; ``lettered`` the prefixes the documents number their rules with ("B"), so a bare "R-3" counts
    wherever it stands. Statutes, resolutions, and recorded instruments are not read here (``jason.community.
    references``); a section "of the Civil Code" is a statute and is left to it. A name written lower case in running
    prose ("the rules require") is not a mention of the document."""
    text = text or ""
    pattern = _name_pattern(names)
    prefixes = set(lettered)
    out: list[Mention] = []
    taken: list[tuple[int, int]] = []

    def free(start: int, end: int) -> bool:
        return all(end <= s or start >= e for s, e in taken)

    def context(at: int) -> tuple[str, ...]:
        para = text.rfind("\n\n", 0, at) + 1
        window = text[max(para, at - 400):at]
        found = [names.get(_norm_name(m.group("name")), "") for m in re.finditer(rf"(?P<name>\b(?:{pattern}))(?![A-Za-z])", window, re.I)
                 if m.group("name")[:1].isupper()]
        return tuple(dict.fromkeys(f for f in found if f))

    def add(m: Mention) -> None:
        if free(m.start, m.end):
            out.append(m)
            taken.append((m.start, m.end))

    def form_of(word: str, number: str, article: bool, named: bool) -> Form:
        if article:
            return Form.ARTICLE
        if re.match(r"[A-Z]{1,2}-\d", number):
            return Form.RULE_LETTERED
        if re.match(r"rules?$", word.strip(". ").lower()):
            return Form.RULE_NUMBERED
        return Form.SECTION

    # "this Declaration", "these Bylaws" (with a number after it, a named section of itself).
    for m in re.finditer(rf"\b(?P<dem>this|these|said)\s+(?P<name>{pattern})(?![A-Za-z])(?!\s+of\s+[A-Z])"
                         rf"(?:\s*,?\s*(?:(?P<word>{_WORD})\s*)?(?P<num>{_NUM}))?", text, re.I):
        if not m.group("name")[:1].isupper() and not m.group("num"):
            continue
        number = normalize_number(m.group("num") or "")
        start, end = m.start(), m.end()
        if number and _statute_like(number):
            end, number = m.end("name"), ""
        add(Mention(Form.SELF if not number else form_of(m.group("word") or "", number, False, True), text[start:end], start, end,
                    m.group("name"), m.group("dem").lower(), m.group("word") or "", number, (number,) if number else (),
                    context=context(start), name_span=(m.start("name"), m.end("name"))))
    # The name first: "Bylaws 7.8", "CC&R 7.8 (a)", "Rules R-3(e)", "Lot Rules, Section 2.1", "the Rules, Rule R-3".
    for m in re.finditer(rf"(?<![\w.-])(?:the\s+)?(?P<name>{pattern})(?:['’]s)?(?![A-Za-z])"
                         rf"(?:\s*,\s*(?:(?:under|in|at|per)\s+)?(?P<w1>{_WORD_NOT_RULE})?|\s+(?:(?:under|in|at|per)\s+)?(?P<w2>{_WORD})?)\s*"
                         rf"(?P<lt>(?=[A-Z]{{1,2}}-\d))?(?P<num>{_NUM}){_LIST}{_RANGE}", text, re.I):
        number = normalize_number(m.group("num"))
        if _statute_like(number) or not free(m.start(), m.end()):
            continue
        word = m.group("w1") or m.group("w2") or ""
        article = bool(re.match(r"art", word, re.I))
        add(Mention(form_of(word, number, article, True), m.group(0), m.start(), m.end(), m.group("name"),
                    "", word, number, _numbers(m.group(0)), article, context=context(m.start()),
                    name_span=(m.start("name"), m.end("name"))))
    # The number first: "Section 7.8 of the Bylaws", "Rule 2.1 of the Lot Rules", "Article IV", "Section 4.2".
    for m in re.finditer(rf"(?<![\w§])(?P<word>(?i:{_WORD}))\s*(?P<lt>(?=[A-Z]{{1,2}}-\d))?(?P<num>{_NUM}|(?<=[Aa]rticle )(?P<roman>{_ROMAN})(?![A-Za-z]))"
                         rf"{_LIST}{_RANGE}"
                         rf"(?P<tail>,?\s+(?:of|in)\s+(?:(?P<det>the|these|this|said)\s+)?(?P<doc>(?i:{pattern})(?![A-Za-z])|"
                         rf"[A-Z][A-Za-z&'’-]*(?:\s+(?:of|and|the)?\s*[A-Z][A-Za-z&'’-]*){{0,5}}))?", text):
        if not free(m.start(), m.end()):
            continue
        article = bool(re.match(r"art", m.group("word"), re.I))
        raw = m.group("roman") or m.group("num")
        number = str(_arabic(raw)) if m.group("roman") else normalize_number(raw)
        if _statute_like(number) or (m.group("roman") and not article):
            continue
        if headings and article and _heading(text, m.start(), m.end("roman") if m.group("roman") else m.end("num")):
            continue                                       # "ARTICLE 5 - ASSESSMENTS": a heading, not a citation
        doc = m.group("doc") or ""
        end = m.end()
        det = (m.group("det") or "").lower()
        if doc and det in ("this", "these", "said") and not _is_code(doc):
            # "Section 5 of this Policy": the document it is written in, by whatever noun the author used.
            add(Mention(form_of(m.group("word"), number, article, True), text[m.start():end], m.start(), end, doc, det,
                        m.group("word"), number, _numbers(m.group(0)), article, context=context(m.start()),
                        name_span=(m.start("doc"), m.end("doc"))))
            continue
        if doc and _is_code(doc):
            continue                                       # "Section 5 of the Civil Code": a statute
        if doc and re.search(rf"\b(?:{_CODE})\b", doc, re.I):
            continue
        if doc and (m.group("tail") or "").strip().startswith(("of", ",")) and not re.fullmatch(pattern, doc, re.I):
            # An unknown document: only a name that is a title ("the Master Plan", "the Act"), not the sentence's next words.
            if re.fullmatch(r"(?:Act|Code|Plan|Map|Agreement|Contract|Lease|Policy|Statement|Report|Study|Resolution|Ordinance)",
                            doc.split()[-1]) or len(doc.split()) > 1:
                add(Mention(Form.UNKNOWN_DOCUMENT, text[m.start():end], m.start(), end, "", "", m.group("word"), number,
                            _numbers(m.group(0)), article, other=doc, context=context(m.start())))
                continue
            end = m.start("tail")
            doc = ""
        elif not doc:
            end = m.start("tail") if m.group("tail") else end
        shared = ""
        if not doc and (ahead := re.match(rf"\s*,?\s*(?:and|or)\s+(?i:{_WORD})\s*{_NUM}\s*,?\s+of\s+(?:the\s+|these\s+|this\s+)?"
                                          rf"(?P<doc>(?i:{pattern})(?![A-Za-z]))", text[end:end + 120])):
            shared = ahead.group("doc")       # "Section 6.5(d) and Section 6.6(c) of the Declaration": the name covers both
        named = bool(doc or shared)
        add(Mention(form_of(m.group("word"), number, article, named), text[m.start():end], m.start(), end, doc or shared, "",
                    m.group("word"), number, _numbers(m.group(0)[: end - m.start()]), article, context=context(m.start()),
                    name_span=(m.start("doc"), m.end("doc")) if doc else (0, 0)))
    # One of jason's own rule rows, as a plan item writes it: "owner_responses.RULES: delivery", "owner_info.FOR_A_PERSON".
    if rows:
        alt = "|".join(re.escape(t) for t in sorted(rows, key=len, reverse=True))
        for m in re.finditer(rf"(?<![\w.])(?P<table>{alt})(?![\w]|\.\w)(?:\s*:\s*(?P<key>[A-Za-z0-9_-]+))?", text):
            if free(m.start(), m.end()):
                add(Mention(Form.ROW, m.group(0), m.start(), m.end(), m.group("table"), number=m.group("key") or ""))
    # A document's key and a number, exact: "ccrs#4.15(a)", "rules#R-3(e)".
    address = "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
    if address:
        for m in re.finditer(rf"(?<![\w#./-])(?P<key>{address})#(?P<num>[A-Za-z0-9][A-Za-z0-9.()~-]*[A-Za-z0-9)])", text):
            if free(m.start(), m.end()):
                add(Mention(Form.ADDRESS, m.group(0), m.start(), m.end(), m.group("key"), number=m.group("num"),
                            numbers=(m.group("num"),)))
    # A rule's letter-number alone: "R-3(e)", "R-3(e)".
    for m in re.finditer(rf"(?<![\w/.#-])(?P<num>{_LETTERED}{_LABELS})(?![\w-])", text):
        if not free(m.start(), m.end()):
            continue
        prefix = m.group("num").split("-", 1)[0]
        if headings and _line_start(text, m.start()) and re.match(r"\s*[.)]?\s*(?:[A-Z][A-Z ,&'/-]{3,}\s*$|$)", _rest_of_line(text, m.end())):
            continue                                       # "R-3. PARKING": the document's own heading
        if prefix not in prefixes and not _rule_context(text, m.start()):
            continue
        add(Mention(Form.RULE_LETTERED, m.group(0), m.start(), m.end(), "", "", "", normalize_number(m.group("num")),
                    (normalize_number(m.group("num")),), context=context(m.start())))
    # A document named whole: "the Rules and Regulations", "the Declaration".
    if document_names:
        for m in re.finditer(rf"(?<![\w.-])(?P<the>the\s+)?(?P<name>{pattern})(?:['’]s)?(?![A-Za-z])(?!\s+of\s+[A-Z])", text, re.I):
            if not m.group("name")[:1].isupper() or not free(m.start(), m.end()):
                continue
            if _compound(text, m.start("name")):
                continue                    # "Decorum Rules": a longer name this is the end of, not the book's
            add(Mention(Form.DOCUMENT, text[m.start():m.end()], m.start(), m.end(), m.group("name"), context=context(m.start())))
    return sorted(out, key=lambda x: x.start)


def clean_expression(text: str) -> str:
    """A citation as one line without its trailing "as amended" / "as restated" (the words read are the document as
    amended already), and an article's roman numeral as its number ("Article IV" is "Article 4")."""
    clean = " ".join(str(text or "").split()).strip().rstrip(".;:")
    clean = re.sub(r"[,\s]*(?:\(?\s*as\s+(?:amended|restated|supplemented)(?:\s+(?:by|through)\s+[^)]*)?\)?)\s*$", "", clean,
                   flags=re.I).strip().rstrip(",")
    return re.sub(rf"\b((?i:articles?|arts?\.))(\s*)({_ROMAN})(?![A-Za-z])", lambda m: f"{m.group(1)}{m.group(2) or ' '}{_arabic(m.group(3))}",
                  clean)


def rewrite(text: str, mention: Mention, key: str) -> str:
    """``text`` (the expression ``mention`` was read from) with the document's name replaced by its key, or the key put
    before a number that named none: the expression the citation parser reads for one document."""
    if mention.name_span != (0, 0):
        start, end = mention.name_span
        lead = re.search(r"(?:this|these|said)\s+$", text[:start], re.I) if mention.demonstrative and \
            not re.search(r"\b(?:of|in)\s+(?:this|these|said)\s+$", text[:start], re.I) else None
        out = text[: lead.start() if lead else start] + key + text[end:]
        # "the Declaration under Section 2.5": the connector is not part of the number's form.
        return re.sub(rf"({re.escape(key)})\s*,?\s*(?:under|in|at|per)\s+(?=\S)", r"\1 ", out, count=1)
    return f"{key} {text}" if mention.number else key


def read_expression(text: str, names: dict[str, str], *, lettered: Iterable[str] = ()) -> Mention | None:
    """``text`` as one citation: the whole of it is a mention (a trailing "as amended" or "as restated" aside), else
    None. A document written in lower case alone is read, since a person asked for it."""
    clean = clean_expression(text)
    if not clean:
        return None
    for m in scan(clean, names, lettered=lettered, document_names=False, headings=False):
        if m.start == 0 and m.end >= len(clean):
            return m
    pattern = _name_pattern(names)
    whole = re.fullmatch(rf"(?:(?P<dem>this|these|said)\s+|the\s+)?(?P<name>{pattern})(?:['’]s)?", clean, re.I) or \
        re.fullmatch(r"(?P<dem>this|these|said)\s+(?P<name>[A-Za-z]+)", clean, re.I)
    if whole:
        return Mention(Form.SELF if whole.group("dem") else Form.DOCUMENT, clean, 0, len(clean), whole.group("name"),
                       (whole.group("dem") or "").lower())
    return None


# --- Where it is written, and what documents there are ----------------------------------------------------------------


@dataclass(frozen=True)
class Citing:
    """The document or record a citation is written in. ``key`` is a document of the Index ("" for minutes, a letter, a
    rule row, or any text that is not one of the documents); ``day`` the date it was written, which reads a document
    kept as amended in the version in force that day."""

    key: str = ""
    kind: str = ""                         # "amendment", "annexation", ... (``DocumentKind`` values)
    day: date | None = None
    amends: str = ""                       # the document it amends or supplements
    title: str = ""


@dataclass(frozen=True)
class DocInfo:
    key: str
    title: str
    kind: str = ""
    book: str = ""                         # the address key: "decl", "rules", "rules.parking", "manual"
    amends: str = ""
    cite_as: str = ""
    written: date | None = None            # when its text was adopted or last restated
    on_shelf: bool = True                  # an outline is on disk
    pooled: bool = True                    # a document a bare section may mean (not a resolution, amendment, or annexation)
    articles: bool = False                 # its top sections are articles
    lettered: str = ""                     # the prefix its sections are numbered with ("B"), if any


@dataclass(frozen=True)
class Part:
    """A separately addressed part of one document: the rules inside an owner's manual, the discipline policy bound
    into it. This is the interface the document segmentation fills (``document_segments``); today the manual's own
    rows (``jason.community.manual``) supply it.

    ``document`` is the outline's key; ``anchor`` the outline section the part starts at (its number, or its title when
    it has none) and ``through`` the last one (empty: the anchor and what is under it); ``book`` the address key the
    part is cited by ("rules.parking"); ``label`` the name a person gives it ("Lot Rules"); ``aliases`` the other
    names it goes by. A part is cited by the numbers its document prints.

    Where the part comes from is ``source``: ``"classification"`` (the owner's manual's rows) or ``"segments"`` (a stored
    segmentation of the file, ``document_segments``). A segment part also carries ``numbers`` (the outline sections that
    sit inside it, so a section number is checked against the part and never against the whole document), ``path`` (the
    names from the document down to the part: an exhibit's label, then a part's title inside it), ``ref`` (its address in
    the file, ``library:ID#seg=s1/s1.1``) and ``pages``. A part inside an exhibit inside a document is the document's
    ``document``, with the exhibit's label in front of its own title in ``path``."""

    document: str
    anchor: str
    book: str = ""
    label: str = ""
    aliases: tuple[str, ...] = ()
    through: str = ""
    source: str = "classification"
    path: tuple[str, ...] = ()
    numbers: tuple[str, ...] = ()
    ref: str = ""
    pages: tuple[int, int] = (0, 0)
    kind: str = ""

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(n for n in (self.label, *self.aliases) if n))


@dataclass
class Index:
    """The documents a citation may mean, as the specification and the outlines on disk give them.

    ``names`` maps each lowercase name to its document key. ``groups`` maps the common name of a book that holds several
    documents to their keys ("rules": the manual's rules and each part adopted apart). ``has`` says whether a document
    has a section on a day (the version in force then, for a document kept as amended); ``words`` the section's words
    (to compare two prints of one rule)."""

    docs: dict[str, DocInfo]
    names: dict[str, str]
    groups: dict[str, tuple[str, ...]] = field(default_factory=dict)
    has: Callable[[str, str, date | None], bool] = lambda key, number, day: False
    words: Callable[[str, str], str] = lambda key, number: ""
    parts: tuple[Part, ...] = ()
    scan_names: dict[str, str] = field(default_factory=dict)     # the names a person writes (not an address key)
    address_keys: frozenset[str] = frozenset()                   # the keys an address names a document by ("ccrs", "rules")
    segment_notes: tuple[str, ...] = ()                          # what a stored segmentation was and was not used for, and why

    def key_of(self, name: str) -> str:
        return self.names.get(_norm_name(name), "")

    def group_of(self, name: str) -> tuple[str, ...]:
        return self.groups.get(_norm_name(name), ())

    def lettered_prefixes(self) -> frozenset[str]:
        return frozenset(d.lettered for d in self.docs.values() if d.lettered)

    def parts_named(self, name: str) -> tuple[Part, ...]:
        """The segment parts a name belongs to ("Exhibit A", "Ex. A"). The manual's classification rows name no document,
        so only a stored segmentation's parts are found here."""
        wanted = _norm_name(name)
        return tuple(p for p in self.parts if p.source == "segments" and wanted in {_norm_name(n) for n in p.names})

    def part_of(self, document: str, number: str) -> Part | None:
        """The part of ``document`` a section falls in: the part whose anchor is the section or encloses it (a segment
        part: the part that holds the section among its ``numbers``)."""
        best: Part | None = None
        for p in self.parts:
            if p.document != document:
                continue
            if p.source == "segments":
                holds = bool(p.numbers) and len(p.path) <= 1 and (number in p.numbers or any(a in p.numbers for a in ancestors(number)))
                if holds and (best is None or best.source != "segments" or len(p.numbers) < len(best.numbers)):
                    best = p
                continue
            if not p.anchor:
                continue
            inside = number == p.anchor or number.startswith(p.anchor + "(") or number.startswith(p.anchor + ".")
            if inside and (best is None or (best.source != "segments" and len(p.anchor) > len(best.anchor))):
                best = p
        return best


# --- Scoping ------------------------------------------------------------------------------------------------------------


class Basis(Enum):
    NAMED = "named"
    SELF = "self"
    CITING = "citing"
    AMENDS = "amends"
    ONLY = "only"
    FORM = "form"
    BOOK = "book"
    PART = "part"
    SEGMENT = "segment"                    # a name a stored segmentation gives a part or an exhibit


class Standing(Enum):
    SCOPED = "scoped"                      # one document
    AMBIGUOUS = "ambiguous"                # two or more documents fit
    NO_SECTION = "no_section"              # the documents that could be meant have no such section
    UNKNOWN_DOCUMENT = "unknown_document"  # the name is not a document of the association
    NOT_ON_SHELF = "not_on_shelf"          # a document of the association with no outline on disk


@dataclass(frozen=True)
class Candidate:
    key: str
    has: bool                              # the document has the section
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"document": self.key, "has": self.has, **({"note": self.note} if self.note else {})}


@dataclass(frozen=True)
class Scoped:
    """What a citation means, and why. ``key`` is the document when ``standing`` is SCOPED; ``candidates`` are every
    document considered, each with whether it has the section."""

    standing: Standing
    form: Form
    key: str = ""
    basis: Basis | None = None
    candidates: tuple[Candidate, ...] = ()
    note: str = ""
    leads: tuple[str, ...] = ()            # documents named earlier in the paragraph: a lead, never a pick
    also: tuple[str, ...] = ()             # other documents that print the section's words (a reprint)
    part: str = ""                         # the part of the document the section is in ("rules.parking")
    number: str = ""
    path: tuple[str, ...] = ()             # document, then the exhibit or part names it is nested through
    source: str = ""                       # where a part came from: "segments"

    @property
    def scoped(self) -> bool:
        return self.standing is Standing.SCOPED

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"standing": self.standing.value, "form": self.form.value}
        if self.key:
            out["document"] = self.key
        if self.basis is not None:
            out["basis"] = self.basis.value
        if self.number:
            out["number"] = self.number
        if self.candidates:
            out["candidates"] = [c.as_dict() for c in self.candidates]
        for name, value in (("note", self.note), ("leads", list(self.leads)),
                            ("alsoInBook" if self.basis is Basis.BOOK else "alsoPrintedIn", list(self.also)),
                            ("part", self.part), ("path", list(self.path)), ("partSource", self.source)):
            if value:
                out[name] = value
        return out


def _same_words(a: str, b: str) -> bool:
    def fold(t: str) -> str:
        return re.sub(r"[^a-z0-9]", "", (t or "").lower())

    return bool(fold(a)) and fold(a) == fold(b)


def _pick(m: Mention, keys: Iterable[str], index: Index, citing: Citing | None, basis: Basis, note: str = "") -> Scoped:
    """The documents of ``keys`` that have the mention's number: one is scoped, several are ambiguous, none is no section."""
    day = citing.day if citing else None
    keys = [k for k in dict.fromkeys(keys) if k in index.docs]
    number = m.number
    cands = tuple(Candidate(k, bool(number) and index.has(k, number, day)) for k in keys)
    hits = [c.key for c in cands if c.has]
    leads = tuple(k for k in m.context if k in index.docs)
    if len(hits) == 1:
        return Scoped(Standing.SCOPED, m.form, hits[0], basis, cands, note, leads, number=number,
                      part=_part_book(index, hits[0], number))
    if not hits:
        return Scoped(Standing.NO_SECTION, m.form, "", None, cands, note or "no document that could be meant has "
                      f"{number}", leads, number=number)
    # Several print it. When a part of one document and the document adopted apart print the same words, the section
    # means the one adopted apart (its book is the part's), and the other is a reprint.
    own = [k for k in hits if "." in (index.docs[k].book or "")]
    reprints = [k for k in hits if k not in own]
    if len(own) == 1 and reprints and all(_same_words(index.words(own[0], number), index.words(k, number)) for k in reprints):
        return Scoped(Standing.SCOPED, m.form, own[0], Basis.PART, cands,
                      "the same words are printed in " + ", ".join(reprints) + "; the document adopted apart is the rule's own",
                      leads, tuple(reprints), index.docs[own[0]].book, number)
    return Scoped(Standing.AMBIGUOUS, m.form, "", None, cands, note or "more than one document has " + number, leads, number=number)


def _part_book(index: Index, key: str, number: str) -> str:
    part = index.part_of(key, number)
    return part.book if part else ""


def _scope_part(m: Mention, citing: Citing, index: Index) -> Scoped | None:
    """A name that no document goes by, but a part or an exhibit of a stored segmentation does ("Exhibit A", "Ex. A"). The
    answer is the document the part is in, with ``path`` the way down to it (document, exhibit, part) and ``part`` its
    book or title. The same name in two documents is ambiguous and names both, unless the text is written in one of them
    (it means that document's own). A section number is the part's only where the part's sections are an outline's
    (``Part.numbers``); an exhibit with no outline has no section to find, and a miss says so instead of reading the
    document's section of that number."""
    hits = list(index.parts_named(m.name))
    if not hits:
        return None
    day = citing.day
    leads = tuple(k for k in m.context if k in index.docs)
    note = ""
    own = [p for p in hits if citing.key and p.document == citing.key]
    if own:
        hits, note = own, f"{m.name} written in {citing.key}, which holds it"
    number = m.number

    def holds(p: Part) -> bool:
        if not number:
            return True
        inside = bool(p.numbers) and (number in p.numbers or any(a in p.numbers for a in ancestors(number)))
        return inside and index.has(p.document, number, day)

    seen: dict[tuple[str, tuple[str, ...]], Part] = {}
    for p in hits:
        seen.setdefault((p.document, p.path), p)
    cands = tuple(Candidate(p.document, holds(p), " > ".join(p.path)) for p in seen.values())
    good = [p for p in seen.values() if holds(p)]
    if len(good) == 1:
        p = good[0]
        way = " > ".join((p.document, *p.path))
        return Scoped(Standing.SCOPED, m.form, p.document, Basis.SEGMENT, cands,
                      note or f"{m.name} is a part of a document, by its stored segmentation: {way}", leads, number=number,
                      part=p.book or p.label, path=(p.document, *p.path), source=p.source)
    if not good:
        docs = ", ".join(sorted({p.document for p in seen.values()}))
        if not number:
            return Scoped(Standing.NO_SECTION, m.form, "", None, cands, note, leads)
        why = ("; the part's own sections are not an outline on the shelf, so " + number + " is not read from the document's"
               if not any(p.numbers for p in seen.values()) else "")
        return Scoped(Standing.NO_SECTION, m.form, "", None, cands,
                      (note or f"{m.name} is a part of {docs}, which has no {number} in it") + why, leads, number=number)
    return Scoped(Standing.AMBIGUOUS, m.form, "", None, cands,
                  note or f"{m.name} is a part of more than one document: " + ", ".join(sorted({p.document for p in good})),
                  leads, number=number)


def _rules_pool(index: Index) -> list[str]:
    """The documents that are rules: those in a rules book (the operating rules, the election rules, the discipline and
    collection policies, the architectural procedure) and any that numbers its sections with a letter."""
    return [k for k, d in index.docs.items() if d.pooled and d.on_shelf and
            (d.book.partition(".")[0] in ("rules", "elec", "disc", "coll", "arch", "manual") or d.lettered)]


def scope(m: Mention, citing: Citing | None, index: Index) -> Scoped:
    """Which document ``m`` means, from what is written and where it is written (see the module's rules)."""
    citing = citing or Citing()
    form = m.form
    if form is Form.ADDRESS:
        return Scoped(Standing.SCOPED, form, m.name, Basis.NAMED, (Candidate(m.name, True),), "the document's own key",
                      number=m.number)
    if m.named:
        key = index.key_of(m.name)
        group = index.group_of(m.name)
        if len(group) > 1:
            if m.demonstrative and citing.key in group:
                return Scoped(Standing.SCOPED, form, citing.key, Basis.SELF, (Candidate(citing.key, True),),
                              f"{m.demonstrative} {m.name}: the citing document, one of the book's documents", number=m.number)
            if m.demonstrative:
                # "these Rules" in a text that is not one of the rules: it means the document it is written in, and
                # nothing says which that is.
                return Scoped(Standing.AMBIGUOUS, form, "", None, tuple(Candidate(k, True) for k in group),
                              f"{m.demonstrative} {m.name} names the document it is written in, and the citing text is "
                              "not one of the documents", tuple(k for k in m.context if k in index.docs), number=m.number)
            if m.number and citing.key in group and index.has(citing.key, m.number, citing.day):
                # "the Rules, R-3" inside the rules: the book's name, and the citing document is one of its documents.
                return Scoped(Standing.SCOPED, form, citing.key, Basis.CITING, tuple(
                    Candidate(k, k == citing.key) for k in group), "the name covers several documents; the citing "
                    "document is one of them and has the section", number=m.number)
            if not m.number:
                main = next((k for k in group if index.docs[k].book.count(".") == 0), group[0])
                cands = tuple(Candidate(k, True) for k in group)
                return Scoped(Standing.SCOPED, form, main, Basis.BOOK, cands,
                              "a common name for a book of several documents: " + ", ".join(group), also=tuple(
                                  k for k in group if k != main))
            return _pick(m, group, index, citing, Basis.BOOK, "the name covers several documents")
        if not key and not group and not m.demonstrative and (found := _scope_part(m, citing, index)) is not None:
            return found
        if not key and m.demonstrative and citing.key and citing.key in index.docs:
            # "this Policy", "these Rules": whatever the noun, the document it is written in.
            return Scoped(Standing.SCOPED, form, citing.key, Basis.SELF, (Candidate(citing.key, True),),
                          f"{m.demonstrative} {m.name}: the citing document", number=m.number)
        if not key:
            return Scoped(Standing.UNKNOWN_DOCUMENT, form, note=f"no document of the association is named {m.name!r}")
        if key not in index.docs or not index.docs[key].on_shelf:
            return Scoped(Standing.NOT_ON_SHELF, form, key, Basis.NAMED, note=f"{key} has no outline on disk (jason outlines)")
        basis, note = Basis.NAMED, ""
        if m.demonstrative:
            if citing.key and (citing.key == key or citing.amends == key):
                basis = Basis.SELF
            else:
                note = (f"{m.demonstrative} {m.name} is read as the document named: "
                        + (f"the citing document is {citing.key}" if citing.key else "nothing says where it is written"))
        return Scoped(Standing.SCOPED, form, key, basis, (Candidate(key, True),), note, tuple(k for k in m.context if k != key
                                                                                            and k in index.docs), number=m.number)
    if form is Form.UNKNOWN_DOCUMENT:
        return Scoped(Standing.UNKNOWN_DOCUMENT, form, note=f"{m.other!r} is not a document of the association")
    if form in (Form.DOCUMENT, Form.SELF):
        return Scoped(Standing.UNKNOWN_DOCUMENT, form, note="no document is named")
    number = m.number
    # A bare number, inside the document that has it.
    if citing.key and citing.key in index.docs:
        doc = index.docs[citing.key]
        # An annexation that numbers its own "1.3(d)(ii)" cites it as its own; a part of a section it has counts too.
        own = index.has(citing.key, number, citing.day) or any(
            index.has(citing.key, up, citing.day) for up in ancestors(number) if re.search(r"[.(]", up))
        if own:
            return Scoped(Standing.SCOPED, form, citing.key, Basis.CITING, (Candidate(citing.key, True),),
                          "the citing document's own section", number=number, part=_part_book(index, citing.key, number))
        if citing.amends and citing.amends in index.docs and (doc.kind in ("amendment", "annexation") or doc.amends):
            return Scoped(Standing.SCOPED, form, citing.amends, Basis.AMENDS, (Candidate(citing.amends, True),),
                          f"a bare section in {citing.key}, which amends {citing.amends}, and which has no such section",
                          number=number)
    # Elsewhere: the documents the form allows, and which of them have the number.
    pool = [k for k, d in index.docs.items() if d.pooled and d.on_shelf]
    basis = Basis.ONLY
    if form is Form.RULE_LETTERED:
        pool = [k for k in pool if index.docs[k].lettered == number.split("-", 1)[0]] or [k for k in _rules_pool(index) if k in pool]
        basis = Basis.FORM
    elif form is Form.RULE_NUMBERED:
        pool = [k for k in _rules_pool(index) if k in pool]
        basis = Basis.FORM
    elif form is Form.ARTICLE:
        pool = [k for k in pool if index.docs[k].articles]
        basis = Basis.FORM
    if citing.key:
        pool = [k for k in pool if k != citing.key] if citing.key in index.docs and not index.has(citing.key, number,
                                                                                                  citing.day) else pool
    return _pick(m, pool, index, citing, basis)


__all__ = ["Basis", "Candidate", "Citing", "DocInfo", "Form", "Index", "Mention", "Part", "Scoped", "Standing", "read_expression",
           "scan", "scope"]
