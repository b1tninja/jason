"""Section numbers recovered from an OCR'd governing document: the label grammar, the slips OCR makes in labels, and
the order labels come in.

``outline_from_text`` reads a line as a section when it starts with a clean label ("4.15", "(a)", "ARTICLE 4"). A
scan's OCR garbles many labels: a dropped dot ("41 Residential Use" for 4.1), a letter for a digit ("ARTICLES
EASEMENTS" for Article 9), a wrong digit ("3.2" for 5.2 between 5.1 and 5.3), a bracket for a parenthesis ("{c)",
"(b}"), a glyph run into its parenthesis ("Gj)", "Q)" for (j)), an empty or half label ("()", "( Rehearing"), a
misread roman numeral ("(it)", "(11)", "(ili)"), and stray marks before the label ("“ (a)", "| (b)", "i 14.5").

``outline_from_ocr`` reads every line start against the labels the document's order allows next, so a garbled token
is read as the label it most resembles among those few, never as any label at all:

- **The grammar.** "ARTICLE n" (digits or roman), "A.n" sections, and parenthesized subsections in four series:
  (a) letters, (i) roman numerals, (A) capitals, (1) digits. Under a section the first subsection is a letter, under
  a letter a roman numeral, under a roman numeral a capital; the other series are allowed at a cost.
- **The confusions.** A token is compared with each expected label by a weighted edit distance: i, l, 1, I, |, ! and
  t are near (OCR's thin strokes); o, 0, O, Q, D; s, 5, S; a dropped or doubled stroke in a roman numeral is cheap; a
  missing dot or parenthesis costs a little; an unrelated glyph costs a whole substitution, which is only accepted
  with a caption after it (a capitalized word) and, for a section number, when the next clear label agrees.
- **The order.** Labels increase: 4.14, 4.15, 4.16; (a), (b); a skipped label is a gap, noted. A clear label that
  goes backwards is out of order and read as text (a cross-reference at a line's start), noted.
- **Inline labels.** A line label whose predecessors are missing ("(iii)" with no (i) or (ii) read) looks back in its
  parent's words for them mid-line ("Rules (i) limiting ..., (ii) limiting ...") and splits them out, then reads the
  rest of the series on that line. An inline enumeration nothing points to is left as words, as in ``outline_from_text``.
- **A caption before its label.** A short Title Case line followed by a label line with no caption of its own, where
  the label's siblings carry captions, is that label's caption (a hanging caption read first).

The result keeps each label as read (``Mark``: how it was read, the cost, whether it is firm) and notes for a person.
``outline_align.align_to_reference`` uses a reference copy to place what the grammar could not. A miss stays a miss.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from jason.community.outlines import DocumentOutline, Section


class Series(Enum):
    LOWER = "lower"        # (a), (b)
    ROMAN = "roman"        # (i), (ii)
    UPPER = "upper"        # (A), (B)
    DIGIT = "digit"        # (1), (2)


class How(Enum):
    CLEAR = "clear"            # read as written
    RECOVERED = "recovered"    # a garbled label read as the one the order expects
    INLINE = "inline"          # a label inside a line, split out because a line label needed it
    ALIGNED = "aligned"        # placed by a reference copy where the reading had a label token
    RENUMBERED = "renumbered"  # an unclear reading given the reference copy's number


class NoteKind(Enum):
    RECOVERED = "recovered"            # a garbled label read as the expected one
    INLINE = "inline"                  # labels split out of a line
    GAP = "gap"                        # a label skipped in the order (a missing page, or a drafting gap)
    OUT_OF_ORDER = "out of order"      # a clear label the order does not allow: read as text
    ALIGNED = "aligned"                # placed by the reference
    RENUMBERED = "renumbered"          # an unclear label given the reference's number
    DISAGREES = "disagrees"            # a clear label the reference numbers otherwise: kept, for a person
    ONLY_IN_REFERENCE = "only in the reference"   # the reference has a section the reading has no label for


@dataclass(frozen=True)
class LabelNote:
    kind: NoteKind
    number: str
    detail: str = ""

    def line(self) -> str:
        return f"{self.kind.value}: {self.number}" + (f": {self.detail}" if self.detail else "")


@dataclass
class Mark:
    """A section start in the reading's text. ``[start, cut)`` is the label as written, replaced by ``label``."""

    number: str
    start: int
    cut: int
    label: str
    title: str
    how: How = How.CLEAR
    cost: float = 0.0
    firm: bool = True          # read clearly and in order: a reference copy never renumbers it
    raw: str = ""              # the label as OCR wrote it

    @property
    def depth(self) -> int:
        return number_depth(self.number)


def number_depth(number: str) -> int:
    return 1 + number.count(".") + number.count("(")


def number_parent(number: str) -> str:
    if "(" in number:
        return number[: number.rfind("(")]
    return number.rsplit(".", 1)[0] if "." in number else ""


@dataclass
class LabelReading:
    """An OCR text with its labels read: the marks, and the notes for a person."""

    text: str
    marks: list[Mark]
    notes: list[LabelNote] = field(default_factory=list)
    key: str = ""
    title: str = ""
    kind: str = ""

    def outline(self) -> DocumentOutline:
        """The outline, its text with each label written cleanly ("Gj)" as "(j)", "41" as "4.1")."""
        pieces: list[str] = []
        sections: list[Section] = []
        at = pos = 0
        for m in sorted(self.marks, key=lambda m: m.start):
            if m.start < at:            # a mark inside a label already rewritten
                continue
            pieces.append(self.text[at:m.start])
            pos += m.start - at
            start = pos
            if m.cut > m.start:
                pieces.append(m.label)
                pos += len(m.label)
                at = m.cut
            else:
                at = m.start
            sections.append(Section(m.number, m.title, m.depth, start, parent=number_parent(m.number)))
        pieces.append(self.text[at:])
        out = DocumentOutline(key=self.key, title=self.title, kind=self.kind, text="".join(pieces), sections=sections)
        for k, s in enumerate(out.sections):
            s.end = next((t.start for t in out.sections[k + 1:] if t.depth <= s.depth), len(out.text))
        return out

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for m in self.marks:
            out[m.how.value] = out.get(m.how.value, 0) + 1
        for n in self.notes:
            out[f"note: {n.kind.value}"] = out.get(f"note: {n.kind.value}", 0) + 1
        return out


# Glyphs and the cost of reading one token as another.

_ROMAN = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"),
          (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]


def roman(n: int) -> str:
    out = ""
    for value, symbol in _ROMAN:
        while n >= value:
            out, n = out + symbol, n - value
    return out


def roman_value(token: str) -> int:
    values = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    total, prev = 0, 0
    for ch in reversed(token.lower()):
        v = values.get(ch, 0)
        total, prev = (total - v, prev) if v < prev else (total + v, v)
    return total


def glyph(series: Series, n: int) -> str:
    if series is Series.LOWER:
        return chr(96 + n) if 1 <= n <= 26 else ""
    if series is Series.UPPER:
        return chr(64 + n) if 1 <= n <= 26 else ""
    if series is Series.ROMAN:
        return roman(n)
    return str(n)


# Glyphs OCR confuses with each other: thin strokes, rounds, esses, and a few digit-letter pairs.
_LIKE = (frozenset("il1I|!t"), frozenset("o0OQD"), frozenset("s5S$"), frozenset("z2Z"), frozenset("b8B"),
         frozenset("g9q"), frozenset("6G"))
_THIN = frozenset("il1I|!")


def _sub(a: str, b: str) -> float:
    if a == b:
        return 0.0
    if a.lower() == b.lower():
        return 0.1
    if any(a in group and b in group for group in _LIKE):
        return 0.2
    return 1.0


def _indel(c: str) -> float:
    return 0.4 if c in _THIN else 0.8


def token_cost(token: str, label: str) -> float:
    """How far OCR's ``token`` is from ``label``: 0 for the same, 0.2 for a confusable glyph, 0.5 for a dropped or
    doubled thin stroke, 1 for an unrelated glyph. An empty token (the glyph lost) costs 0.8."""
    if not token:
        return 0.8 + 0.5 * max(0, len(label) - 1)
    n, m = len(token), len(label)
    row = [0.0] * (m + 1)
    for j in range(1, m + 1):
        row[j] = row[j - 1] + _indel(label[j - 1])
    for i in range(1, n + 1):
        prev, row[0] = row[:], row[0] + _indel(token[i - 1])
        for j in range(1, m + 1):
            row[j] = min(prev[j] + _indel(token[i - 1]), row[j - 1] + _indel(label[j - 1]),
                         prev[j - 1] + _sub(token[i - 1], label[j - 1]))
    return row[m]


# The grammar.

_LEADERS = re.compile(r"(?:\.\s*){5,}")
_TOC = re.compile(r"\.{3,}")               # "Definitions, Generally... 020. eee": OCR's dot leaders
_JUNK = re.compile(r"[\s|\"“”'‘’`~_\-—–»«.,;:!*•]*")
_STRAY = re.compile(r"[A-Za-z][ \t]+(?=[(\[{]|\d)")          # one stray letter before a label: "a (e)", "i 14.5"
_ARTICLE_AT = re.compile(r"(?i:article)[ \t]*([0-9]+|[IVXL]+(?![A-Za-z])|[A-Za-z0-9|$]{1,2}?)(?=[\s_.:\-–—]|$)")
_ARTICLE_CAPTION = re.compile(r"(?:[a-z]{1,2}\s+)?([A-Z][A-Z0-9'’&,;:\- ]{2,}.*)$")
_DOTTED_AT = re.compile(r"([0-9SIlO|!]{1,3})([ \t]?\.[ \t]?|,)([0-9SIlO|!]{1,3})[.,]?(?=\s|$)")
_RUN_AT = re.compile(r"([0-9]{2,4})\.?(?=[ \t]+[A-Z\"“(])")
_SUB_FULL = re.compile(r"[(\[{][ \t]*([A-Za-z0-9|!]{0,5})[ \t]*[)\]}]")
_SUB_OPEN = re.compile(r"[(\[{][ \t]*([A-Za-z0-9|!]{0,2})(?=[ \t])")
_SUB_CLOSE = re.compile(r"([A-Za-z0-9|!]{1,5})[)\]}]")
_AFTER = re.compile(r"[ \t|.»«:;,_\-—~)\]}]*")
_ARTICLE_AFTER = re.compile(r"[\s_.:\-–—]*")

_CHILD: dict[Series | None, tuple[Series, tuple[Series, ...]]] = {
    None: (Series.LOWER, (Series.DIGIT, Series.ROMAN)),
    Series.LOWER: (Series.ROMAN, (Series.DIGIT, Series.UPPER)),
    Series.ROMAN: (Series.UPPER, (Series.DIGIT,)),
    Series.UPPER: (Series.DIGIT, ()),
    Series.DIGIT: (Series.LOWER, ()),
}


def normalize(text: str) -> str:
    """The gaps OCR puts inside numbers closed, as ``outline_from_text`` closes them: "13 .1", "1.3( d)", "6.S(b)"."""
    text = re.sub(r"(\d)\s+\.\s*(\d)", r"\1.\2", text)
    text = re.sub(r"\(\s+([a-zA-Z0-9]{1,4})\s*\)", r"(\1)", text)
    text = re.sub(r"(\d\.)\s?S(?=[\s(\"])", r"\g<1>5", text)
    text = re.sub(r"(\d)\"\(", r"\1(", text)
    return text


def captioned(rest: str) -> bool:
    """Whether words start with a caption: a short first sentence in Title Case ("Owner Responsibility. Each ...")."""
    if not rest[:1].isupper():
        return False
    # OCR reads a caption's period as a comma ("Notice of Default, A notice ...").
    first = re.split(r"(?<=[.:,])\s+(?=[A-Z])", rest.strip(), maxsplit=1)[0].rstrip()
    if not first.endswith((".", ":", ",")):
        return False                    # "Roofreplacement;": a list item, not a caption
    words = [w for w in re.findall(r"[A-Za-z][\w'’/-]*", first) if len(w) > 2]   # OCR's fragments aside
    if not 1 <= len(words) <= 10:
        return False
    return sum(w[0].isupper() for w in words) >= 0.6 * len(words)


def inline_title(text: str, at: int) -> str:
    """A title for a section that starts mid-line: its first words, joined across lines. Never the first line alone,
    so a reader of the outline does not take an inline item's first line for a caption."""
    return " ".join(text[at:at + 200].split())[:90] + "…"


def _lone_caption(line: str) -> str:
    """A line that is a caption alone ("Rehearing."): short, Title Case, ending in a period. Empty when not."""
    s = line.strip()
    if not re.fullmatch(r"[A-Z][\w'’,&/ -]{1,70}\.", s) or len(s.split()) > 8:
        return ""
    return s if captioned(s) else ""


@dataclass
class _Level:
    series: Series
    index: int
    mark: Mark
    captioned: bool


@dataclass
class _State:
    article: int = 0
    section: int = 0
    head: Mark | None = None
    levels: list[_Level] = field(default_factory=list)

    def base(self) -> str:
        if self.section:
            return f"{self.article}.{self.section}"
        return str(self.article) if self.article else ""

    def number(self, levels: list[tuple[Series, int]]) -> str:
        return self.base() + "".join(f"({glyph(s, i)})" for s, i in levels)

    def path(self, k: int) -> list[tuple[Series, int]]:
        return [(lv.series, lv.index) for lv in self.levels[:k]]


@dataclass
class _Head:
    """A section-level label read clearly, for looking ahead: an article, or a dotted number."""

    article: bool
    a: int
    b: int = 0


def _clear_head(line: str) -> _Head | None:
    s = line[_JUNK.match(line).end():]
    if m := _ARTICLE_AT.match(s):
        tok = m.group(1)
        if tok.isdigit():
            return _Head(True, int(tok))
        if re.fullmatch(r"[IVXL]+", tok):
            return _Head(True, roman_value(tok))
        return None
    if (m := _DOTTED_AT.match(s)) and m.group(1).isdigit() and m.group(3).isdigit() and "." in m.group(2):
        return _Head(False, int(m.group(1)), int(m.group(3)))
    return None


def _consistent(nxt: _Head | None, a: int, b: int) -> bool:
    """Whether the next clear label agrees with reading this one as a.b (b = 0 for an article)."""
    if nxt is None:
        return True
    if nxt.article:
        return nxt.a > a
    if b == 0:
        return nxt.a == a
    return (nxt.a == a and b < nxt.b <= b + 2) or (nxt.a == a + 1 and nxt.b == 1)


def outline_from_ocr(text: str, *, key: str, title: str = "", kind: str = "") -> LabelReading:
    """The labels of an OCR'd document, read by the grammar, the confusions, and the order (see the module's notes).
    ``reading.outline()`` is the ``DocumentOutline``; ``reading.notes`` say what was recovered, skipped, or doubtful."""
    text = normalize(text)
    lines: list[tuple[int, str]] = []
    at = 0
    for raw in text.splitlines(keepends=True):
        lines.append((at, raw.rstrip("\r\n")))
        at += len(raw)
    heads = [_clear_head(s) for _, s in lines]
    upcoming: list[_Head | None] = [None] * len(lines)
    following: _Head | None = None
    for i in range(len(lines) - 1, -1, -1):
        upcoming[i] = following
        following = heads[i] or following
    reading = LabelReading(text, [], [], key, title, kind)
    st = _State()
    last_marked = -1
    for i, (off, s) in enumerate(lines):
        if not s.strip() or _LEADERS.search(s) or len(_TOC.findall(s)) >= 2:
            continue                       # a table of contents line: its numbers are not sections
        prev = lines[i - 1][1] if i and last_marked != i - 1 else ""
        if _read_article(reading, st, off, s, upcoming[i]) or _read_section(reading, st, off, s, upcoming[i]) \
                or _read_subsection(reading, st, text, off, s, prev, lines[i - 1][0] if i else 0):
            last_marked = i
    reading.marks.sort(key=lambda m: m.start)
    return reading


def _starts(s: str) -> list[int]:
    lead = _JUNK.match(s).end()
    out = [lead]
    if m := _STRAY.match(s, lead):
        out.append(m.end())
    return out


def _read_article(reading: LabelReading, st: _State, off: int, s: str, nxt: _Head | None) -> bool:
    for p in _starts(s):
        m = _ARTICLE_AT.match(s, p)
        if not m:
            continue
        tok = m.group(1)
        after = _ARTICLE_AFTER.match(s, m.end()).end()
        rest = s[after:].strip()
        cap = _ARTICLE_CAPTION.match(rest)
        if rest and not cap:
            continue                                   # "Article 6 of this Declaration": a reference, not a heading
        value = int(tok) if tok.isdigit() else roman_value(tok) if re.fullmatch(r"[IVXL]+", tok) else 0
        targets = [(st.article + 1, 0.0), (st.article + 2, 0.6), (st.article + 3, 0.9)]
        if value > st.article + 1:
            targets.append((value, 0.0 if st.article == 0 else 0.3))     # a clear number: an excerpt, or a gap
        best: tuple[float, int, float] | None = None
        for target, pen in targets:
            cost = 0.0 if value == target else token_cost(tok, str(target))
            total = cost + pen + (0.0 if _consistent(nxt, target, 0) else 0.8)
            if best is None or total < best[0]:
                best = (total, target, cost)
        if best is None or best[0] > 1.2:
            continue
        total, target, cost = best
        title = cap.group(1).strip() if cap else ""
        mark = Mark(str(target), off, off + after, f"ARTICLE {target} ", title or rest,
                    How.CLEAR if cost == 0 else How.RECOVERED, round(total, 2), cost == 0 and total == 0,
                    s[p:m.end()])
        reading.marks.append(mark)
        if cost:
            reading.notes.append(LabelNote(NoteKind.RECOVERED, str(target), f'"{s[p:m.end()]}" read as Article {target}'))
        if target > st.article + 1:
            reading.notes.append(LabelNote(NoteKind.GAP, str(target), f"no Article {st.article + 1} read"))
        st.article, st.section, st.head, st.levels = target, 0, mark, []
        return True
    return False


def _read_section(reading: LabelReading, st: _State, off: int, s: str, nxt: _Head | None) -> bool:
    for p in _starts(s):
        parses: list[tuple[str, str, float, int]] = []       # (article token, section token, form cost, end)
        if m := _DOTTED_AT.match(s, p):
            parses.append((m.group(1), m.group(3), 0.0 if "." in m.group(2) else 0.1, m.end()))
        if m := _RUN_AT.match(s, p):
            run = m.group(1)
            parses += [(run[:k], run[k:], 0.3, m.end()) for k in range(1, len(run))]
        if not parses:
            continue
        after = _AFTER.match(s, max(e for *_, e in parses)).end()
        rest = s[after:]
        caption = bool(re.match(r"[A-Z\"“]", rest))
        if st.article == 0 and st.section == 0:
            clear = [(x, y, f, e) for x, y, f, e in parses if x.isdigit() and y.isdigit() and f == 0.0]
            if not clear:
                continue
            x, y, _, e = clear[0]
            targets = [(int(x), int(y), 0.0)]
        else:
            a, n = st.article, st.section
            targets = [(a, n + 1, 0.0), (a, n + 2, 0.4), (a, n + 3, 0.7), (a, n + 4, 1.0), (a + 1, 1, 0.3)]
            for x, y, form, _ in parses:
                if form == 0.0 and x.isdigit() and y.isdigit():
                    # A clear number further on: an excerpt that starts mid-article, a gap, or an article whose
                    # heading was not read. The next clear label decides against a garbled one ("9.4" before "9.2").
                    if int(x) == a and int(y) > n + 1:
                        targets.append((a, int(y), 0.2 + min(0.05 * (int(y) - n - 1), 0.25)))
                    elif int(x) > a:
                        targets.append((int(x), int(y), 0.5))
        best: tuple[float, float, float, int, int, int, str] | None = None
        for x, y, form, e in parses:
            for a, b, pen in targets:
                cost = form + token_cost(x, str(a)) + token_cost(y, str(b))
                total = cost + pen + (0.0 if _consistent(nxt, a, b) else 0.8)
                if best is None or total < best[0]:
                    best = (total, cost, pen, a, b, e, f"{x}.{y}" if form != 0.3 else x + y)
        total, cost, pen, a, b, e, raw = best
        if not (total <= 0.45 or (total <= 1.5 and caption)):
            clear = [x for x, y, f, _ in parses if f == 0.0 and x.isdigit() and y.isdigit()]
            if clear:
                reading.notes.append(LabelNote(NoteKind.OUT_OF_ORDER, raw, f"after {st.base() or 'the start'}: read as text"))
            continue
        number = f"{a}.{b}"
        after = _AFTER.match(s, e).end()
        mark = Mark(number, off, off + after, f"{number} ", s[after:][:120],
                    How.CLEAR if cost <= 0.1 else How.RECOVERED, round(total, 2),
                    cost <= 0.1 and pen == 0 and total <= 0.1, raw)
        reading.marks.append(mark)
        if cost > 0.1:
            reading.notes.append(LabelNote(NoteKind.RECOVERED, number, f'"{raw}" read as {number}'))
        if a > st.article and st.article:
            reading.notes.append(LabelNote(NoteKind.GAP, number, f"no ARTICLE {a} heading read before it"))
        elif a == st.article and b > st.section + 1:
            missed = f"{a}.{st.section + 1}" + (f" to {a}.{b - 1}" if b - 1 > st.section + 1 else "")
            reading.notes.append(LabelNote(NoteKind.GAP, number, f"after {st.base()}: {missed} not read"))
        st.article, st.section, st.head, st.levels = a, b, mark, []
        return True
    return False


def _sub_parses(s: str, p: int) -> list[tuple[str, float, int]]:
    """(token, form cost, end) for the ways a subsection label can start at ``p``."""
    out: list[tuple[str, float, int]] = []
    if m := _SUB_FULL.match(s, p):
        out.append((m.group(1), 0.0, m.end()))
    if m := _SUB_OPEN.match(s, p):
        out.append((m.group(1), 0.3, m.end()))
    if m := _SUB_CLOSE.match(s, p):
        tok = m.group(1)
        out.append((tok, 0.3, m.end()))
        if len(tok) > 1 and tok[0] in "GCQ":
            out.append((tok[1:], 0.2, m.end()))            # "Gj)": the parenthesis read as a letter
        if len(tok) == 1:
            out.append(("", 0.3, m.end()))                  # "Q)": the parenthesis and glyph read as one letter
    return out


def _inline(text: str, g: str, lo: int, hi: int) -> re.Match[str] | None:
    return re.compile(r"(?:(?<=[\s;:,])|^)[(\[{][ \t]*" + re.escape(g) + r"[ \t]*[)\]}](?=[ \t\n])").search(text, lo, hi)


def _read_subsection(reading: LabelReading, st: _State, text: str, off: int, s: str, prev: str, prev_off: int) -> bool:
    if not st.base():
        return False
    best = None    # (total, cost, form, k, series, index, relation, end, token, inline matches)
    for p in _starts(s):
        for tok, form, end in _sub_parses(s, p):
            rest = s[_AFTER.match(s, end).end():]
            line_caption = captioned(rest)
            for k, series, index, pen, relation in _candidates(st):
                g = glyph(series, index)
                if not g:
                    continue
                cost = token_cost(tok, g)
                style = 0.0
                if cost >= 0.8 and relation in ("next", "skip") and st.levels[k].captioned != line_caption:
                    style = 0.25           # a lost glyph: the level whose items look like this line is likelier
                if not tok and relation == "first":
                    style = 0.2            # a first subsection's label is seldom the one lost
                total = form + cost + pen + style
                options = [(total, cost, index, relation, [])]
                if relation in ("next", "first", "other") and cost > 0.2:
                    # A clear label later in the series, its predecessors inline before it.
                    for later in range(index + 1, index + 12):
                        if not glyph(series, later) or token_cost(tok, glyph(series, later)) > 0.2:
                            continue
                        lo = (st.levels[k].mark if relation == "next" else
                              st.levels[-1].mark if st.levels else st.head).cut
                        found, pos = [], lo
                        for j in range(index, later):
                            hit = _inline(text, glyph(series, j), pos, off + p)
                            if hit is None:
                                break
                            found.append(hit)
                            pos = hit.end()
                        if len(found) == later - index:
                            options.append((form + token_cost(tok, glyph(series, later)) + pen + 0.1,
                                            token_cost(tok, glyph(series, later)), later, relation + "+inline", found))
                        elif relation == "next" and token_cost(tok, glyph(series, later)) == 0:
                            # A clear later sibling with its predecessors not read: a gap, not another glyph.
                            options.append((form + pen + 0.6 + 0.1 * (later - index - 1), 0.0, later, "skip", []))
                        break
                for total, cost, idx, rel, found in options:
                    if best is None or total < best[0]:
                        best = (total, cost, form, k, series, idx, rel, end, tok, found, p, rest)
    if best is None:
        return False
    total, cost, form, k, series, index, relation, end, tok, found, p, rest = best
    limit = 1.35 if relation == "next" else 1.2
    if not (total <= 0.6 or (total <= limit and rest[:1].isupper())):
        return False
    path = st.path(k)
    prior = st.levels[k].index if k < len(st.levels) else 0
    for j, hit in enumerate(found):
        g = glyph(series, index - len(found) + j)
        number = st.number([*path, (series, index - len(found) + j)])
        mark = Mark(number, hit.start(), hit.end(), f"({g})", inline_title(text, hit.end()), How.INLINE, 0.0, True,
                    hit.group(0))
        reading.marks.append(mark)
        st.levels = [*st.levels[:k], _Level(series, index - len(found) + j, mark, False)]
    number = st.number([*path, (series, index)])
    g = glyph(series, index)
    after = _AFTER.match(s, end).end()
    line_caption = captioned(rest)
    start, label, title = off, f"({g}) ", rest[:120]
    lone = _lone_caption(prev)
    if not line_caption and lone and k < len(st.levels) and st.levels[k].captioned:
        # A hanging caption read on the line before its label.
        start, label, title, line_caption = prev_off, f"({g}) {lone} ", f"{lone} {rest}"[:120], True
    firm = form + cost <= 0.5 and relation.split("+")[0] in ("next", "first")
    how = How.CLEAR if form + cost <= 0.1 else How.RECOVERED
    mark = Mark(number, start, off + after, label, title, how, round(total, 2), firm, s[p:end])
    reading.marks.append(mark)
    st.levels = [*st.levels[:k], _Level(series, index, mark, line_caption)]
    if how is How.RECOVERED:
        reading.notes.append(LabelNote(NoteKind.RECOVERED, number, f'"{s[p:end]}" read as ({g})'))
    if relation == "skip":
        missed = ", ".join(f"({glyph(series, j)})" for j in range(prior + 1, index))
        reading.notes.append(LabelNote(NoteKind.GAP, number, f"{missed} not read before it"))
    if found:
        reading.notes.append(LabelNote(NoteKind.INLINE, number, "split out before it: "
                                       + ", ".join(f"({glyph(series, index - len(found) + j)})" for j in range(len(found)))))
        # The rest of an inline series on the same line.
        line_end = off + len(s)
        pos, nxt, more = off + after, index + 1, []
        while glyph(series, nxt) and (hit := _inline(text, glyph(series, nxt), pos, line_end)):
            m2 = Mark(st.number([*path, (series, nxt)]), hit.start(), hit.end(), f"({glyph(series, nxt)})",
                      inline_title(text, hit.end()), How.INLINE, 0.0, True, hit.group(0))
            reading.marks.append(m2)
            st.levels = [*st.levels[:k], _Level(series, nxt, m2, False)]
            more.append(f"({glyph(series, nxt)})")
            pos, nxt = hit.end(), nxt + 1
        if more:
            reading.notes.append(LabelNote(NoteKind.INLINE, number, "split out after it: " + ", ".join(more)))
    return True


def _candidates(st: _State) -> list[tuple[int, Series, int, float, str]]:
    """The labels the order allows next: each open level's next (or one skipped), and the first child."""
    out: list[tuple[int, Series, int, float, str]] = []
    for k in range(len(st.levels) - 1, -1, -1):
        lv = st.levels[k]
        pen = 0.05 * (len(st.levels) - 1 - k)
        out.append((k, lv.series, lv.index + 1, pen, "next"))
        out.append((k, lv.series, lv.index + 2, pen + 0.6, "skip"))
    primary, others = _CHILD[st.levels[-1].series if st.levels else None]
    k = len(st.levels)
    out.append((k, primary, 1, 0.1, "first"))
    out += [(k, series, 1, 0.35, "other") for series in others]
    return out


__all__ = ["How", "LabelNote", "LabelReading", "Mark", "NoteKind", "Series", "captioned", "glyph", "normalize",
           "number_depth", "number_parent", "outline_from_ocr", "roman", "roman_value", "token_cost"]
