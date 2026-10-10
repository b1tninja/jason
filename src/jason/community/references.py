"""References a document's text makes to the law, to other documents, and to its own sections.

A governing document is a web of references: the Bylaws cite the Corporations and Civil Codes and the Declaration; the
Collection Policy cites the Declaration's assessment sections; a resolution replaces an earlier one; an annexation
cites "subsection 1.3(d)(ii), below". ``extract`` reads them from a document's text with a citation grammar and ties
each to the section of the source it sits in (``DocumentOutline.section_at``). A ``Reference`` names its target the
same way every time, so references from different documents meet in one graph:

- a statute: ``CIV 4926(a)(3)``, ``CORP 7341``, ``10 CCR 2792.23`` (a pre-2014 Davis-Stirling number, 1350 to 1378,
  keeps its old number and is marked ``prior``); a section whose number ends in a letter keeps it (``CIV 2924f``, and
  ``CIV 2924f(a)`` for its subdivision);
- a section of a known document: ``bylaws#7.2``, ``ccrs#6.5(b)``, or the source's own ``#1.3(d)(ii)``;
- a known document as a whole: ``enforcement-policy``;
- a resolution by the number it prints: ``resolution:20230130-1``;
- a recorded instrument: ``instrument:201901161002``.

The verb around a reference says how the source stands to it (replaces, amends, acts under, is subject to, overrides,
takes a definition from, is required by, or plainly cites). The grammar reads what is written; a reference it misses
stays missed, and a model reading the same section can add it later. Nothing here decides that a reference is right.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Iterable

from jason.community.outlines import DocumentOutline, normalize_number


class TargetKind(Enum):
    STATUTE = "statute"
    SECTION = "section"
    DOCUMENT = "document"
    RESOLUTION = "resolution"
    INSTRUMENT = "recorded instrument"


class RefRelation(Enum):
    CITES = "cites"
    REPLACES = "replaces"
    AMENDS = "amends"
    PURSUANT_TO = "acts under"
    SUBJECT_TO = "is subject to"
    NOTWITHSTANDING = "overrides"
    DEFINED_IN = "takes a definition from"
    REQUIRED_BY = "is required by"


@dataclass(frozen=True)
class Reference:
    source: str                  # the citing document's key
    source_section: str          # the section it sits in (number, or title), "" outside any section
    kind: TargetKind
    target: str                  # canonical, as above
    relation: RefRelation
    quote: str                   # the sentence it was read from
    offset: int
    prior: bool = False          # a statute number from before the 2014 renumbering
    method: str = "grammar"      # how it was read: "grammar" here, "model" from jason.community.reference_model

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        raw["kind"], raw["relation"] = self.kind.value, self.relation.value
        if raw["method"] == "grammar":
            del raw["method"]    # the grammar's rows read as they always have
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Reference:
        return cls(**{**raw, "kind": TargetKind(raw["kind"]), "relation": RefRelation(raw["relation"])})


# Code names, longest first; "Civ." alone is the Civil Code as HOA documents abbreviate it ("Civ. §4930").
CODES: tuple[tuple[str, str], ...] = (
    (r"California\s+Civil\s+Code|Cal\.?\s*Civ\.?\s*Code|Civil\s+Code|Civ\.?\s*Code|Civ\.", "CIV"),
    (r"Corporations?\s+Code|Corp\.?\s*Code", "CORP"),
    (r"Health\s+(?:and|&)\s+Safety\s+Code|Health\s+&\s+Saf\.?\s*Code", "HSC"),
    (r"Government\s+Code|Gov\.?\s*Code|Govt\.?\s*Code", "GOV"),
    (r"Evidence\s+Code|Evid\.?\s*Code", "EVID"),
    (r"Business\s+(?:and|&)\s+Professions\s+Code|Bus\.?\s*&\s*Prof\.?\s*Code", "BPC"),
    (r"Code\s+of\s+Civil\s+Procedure", "CCP"),
    (r"Vehicle\s+Code|Veh\.?\s*Code", "VEH"),
    (r"Penal\s+Code", "PEN"),
    (r"(?:California\s+)?Fire\s+Codes?", "CFC"),
    (r"(?:California\s+)?Building\s+Codes?", "CBC"),
    (r"Sacramento\s+City\s+Code", "SCC"),
    (r"(?:California\s+)?Public\s+Resources\s+Code|Pub\.?\s*Res\.?\s*Code", "PRC"),
    (r"Revenue\s+(?:and|&)\s+Taxation\s+Code|Rev\.?\s*&\s*Tax\.?\s*Code", "RTC"),
    (r"Insurance\s+Code|Ins\.?\s*Code", "INS"),
    (r"Water\s+Code", "WAT"),
    # Abbreviations and named acts that outside material uses for a code: "BPC Section 11010.4", "Section 66427 of the Map Act".
    (r"BPC|B\.?\s?&\s?P\.?\s*Code", "BPC"),
    (r"Subdivided\s+Lands\s+(?:Act|Law)|SLA", "BPC"),
    (r"Subdivision\s+Map\s+Act|Map\s+Act", "GOV"),
    (r"Davis[-\s]Stirling(?:\s+Common\s+Interest\s+Development)?\s+Act|DSA", "CIV"),
)
_CODE_ALT = "|".join(f"(?:{p})" for p, _ in CODES)
_CODE_NAME = re.compile(_CODE_ALT, re.I)
_SUB = r"(?:\s?\([a-zA-Z0-9]{1,4}\))*"
# The letter some statute sections end in ("2924a", "1102.6a"): part of the number only when it is written against the
# digits and the number ends there. "5855(a)" is section 5855, subdivision (a); "5855 and" is section 5855.
LETTER = r"(?:[a-z](?![A-Za-z0-9]))?"
# A statute's section number as the codes print it: dotted, with the letter. The one pattern every reader shares.
SECTION_NUMBER = rf"\d+(?:\.\d+)*{LETTER}"
# The codes by the abbreviation the Legislature prints, as jason's own records write a citation ("CIV 5855",
# "SHC 5898.16"): every code lawlibrary's California shelf holds (``authorities.LAWLIBRARY_CODES``; a test keeps the
# two the same).
ABBREVIATIONS = frozenset({
    "BPC", "CCP", "CIV", "COM", "CONS", "CORP", "EDC", "ELEC", "EVID", "FAC", "FAM", "FGC", "FIN", "GOV", "HNC", "HSC",
    "INS", "LAB", "MVC", "PCC", "PEN", "PRC", "PROB", "PUC", "RTC", "SHC", "UIC", "VEH", "WAT", "WIC",
})
_ABBR = "|".join(sorted(ABBREVIATIONS, key=len, reverse=True))
_STAT_NUM = rf"\d{{3,5}}(?:\.\d+)*{LETTER}{_SUB}"   # building and fire codes go deeper: "308.1.4"
_SEP = r"\s*(?:,\s*(?:and|or)\b|,|;|and|or|through|to|-|–)\s*"
_STATUTE = re.compile(rf"\b(?P<code>{_CODE_ALT})\s*(?:[Ss]ections?|§§?|[Ss]ec(?:s)?\.)?\s*"
                      rf"(?P<nums>{_STAT_NUM}(?:(?:{_SEP})(?:{_STAT_NUM}|{_SUB[:-1]}+))*)")
_JASON_STYLE = re.compile(rf"\b(?P<code>{_ABBR})\s+(?P<nums>{_STAT_NUM}(?:(?:,\s*)(?:{_STAT_NUM}|\([a-z0-9]+\)))*)")
# One citation in jason's style inside a longer string ("CIV 5515(d)" in an item's authority line).
STATUTE_IN_TEXT = re.compile(rf"\b(?P<code>{_ABBR})\s+(?P<number>\d{{3,5}}(?:\.\d+)*{LETTER})(?P<subs>(?:\s*\([a-z0-9]+\))*)")
_REG = re.compile(r"\b(?:Title\s+)?(?P<title>\d{1,2})\s+(?:C\.?C\.?R\.?|Cal(?:ifornia)?\.?\s*Code\s+(?:of\s+)?Reg(?:ulations|s)?\.?)\s*"
                  r"(?:§|[Ss]ections?)?\s*(?P<num>\d{3,5}(?:\.\d+)?)")
# A document's section, or a statute's named by the word "Section": a lettered number only with three digits or more
# ("Section 2924f of the Civil Code"), so a document's "Section 3a" reads as it always has.
_SEC_NUM = rf"(?:\d{{3,6}}(?:\.\d+)*[a-z](?![A-Za-z0-9])|\d+(?:\.\d+)*){_SUB}"
# "§" is not a word character, so the start is "not after a letter or digit", not \b ("CC&Rs §§ 2.5, 10.6").
_SECTION = re.compile(rf"(?<![\w§])(?P<word>[Ss]ections?|[Ss]ubsections?|§§?|[Aa]rticles?|[Pp]aragraphs?)\s*"
                      rf"(?P<nums>{_SEC_NUM}(?:(?:{_SEP})(?:{_SEC_NUM}|{_SUB[:-1]}+))*)"
                      r"(?P<tail>,?\s+of\s+(?:the\s+|these\s+|this\s+|said\s+)?(?P<doc>[A-Z][A-Za-z&' ]{2,60}?))?(?=[\s,.;:)\]]|$)")
_AHEAD = re.compile(rf"^\s*(?:,\s*)?(?:and|or)\s+(?:[Ss]ections?|§)\s*{_SEC_NUM}\s*,?\s+of\s+(?:the\s+|these\s+|this\s+)?"
                    r"(?P<doc>[A-Z][A-Za-z&' ]{2,60}?)(?=[\s,.;:)]|$)")
_RESOLUTION = re.compile(r"\b(?:(?P<series>Administrative|Special|Policy)\s+)?Resolution\s+(?:No\.?\s*|Number\s*|#\s*)?"
                         r"(?P<num>\d{8}-\d+|\d{6}-\d+|\d{4}-\d{2}-\d{2}-\d+|\d{4}-\d{1,3})\b", re.I)
_INSTRUMENT = re.compile(r"\b(?:Document|Instrument|Doc\.)\s*(?:No\.?|Number|#)\s*(?P<num>(?:19|20)\d{10})\b"
                         r"|\bBook\s+(?P<book>\d{8})\s*,?\s*Page\s+(?P<page>\d{1,5})\b", re.I)
_SELF = re.compile(r"\b(?:these|this|the)\s+(?:Bylaws|Declaration|Policy|Rules|Resolution|Amendment|Agreement)\b", re.I)
_RELATIONS: tuple[tuple[re.Pattern, RefRelation], ...] = (
    (re.compile(r"\b(?:replac|supersed|rescind|in lieu of)", re.I), RefRelation.REPLACES),
    (re.compile(r"\bamend", re.I), RefRelation.AMENDS),
    (re.compile(r"\bnotwithstanding\b", re.I), RefRelation.NOTWITHSTANDING),
    (re.compile(r"\bsubject to\b", re.I), RefRelation.SUBJECT_TO),
    (re.compile(r"\b(?:defined in|has the meaning|have the meanings?|as defined)\b", re.I), RefRelation.DEFINED_IN),
    (re.compile(r"\b(?:required by|requires?|as required|mandated by)\b", re.I), RefRelation.REQUIRED_BY),
    (re.compile(r"\b(?:pursuant to|in accordance with|under|as provided (?:in|by)|as set forth in|authorized by)\b", re.I), RefRelation.PURSUANT_TO),
)


def _code_of(name: str) -> str:
    for pattern, code in CODES:
        if re.fullmatch(pattern, name.strip(), re.I):
            return code
    return ""


def _split_numbers(nums: str) -> list[str]:
    """"5850(c), (d)" -> ["5850(c)", "5850(d)"]; "5855(d), 5910" -> ["5855(d)", "5910"]; "2924b, 2924c" stay lettered."""
    out: list[str] = []
    base = ""
    for number, subs in re.findall(rf"({SECTION_NUMBER})?((?:\s?\([a-zA-Z0-9]{{1,4}}\))*)", nums):
        subs = re.sub(r"\s+", "", subs)
        if number:
            base = number
            out.append(number + subs)
        elif subs and base:
            out.append(base + subs)
    return out


def _sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(". ", max(0, start - 400), start), text.rfind("\n", max(0, start - 400), start))
    right_candidates = [i for i in (text.find(". ", end, end + 400), text.find("\n", end, end + 400)) if i >= 0]
    right = min(right_candidates) + 1 if right_candidates else min(len(text), end + 200)
    return " ".join(text[left + 1 if left >= 0 else max(0, start - 200):right].split())[:500]


# Up to the end of the sentence (a period and a space; "4.15" does not end it).
_AFTER = re.compile(r"^(?:(?!\.\s)[^;\n]){0,120}?\b(?:is|are)\s+hereby\s+(amended|restated|deleted|removed|added|repealed|rescinded)", re.I)


def _relation(text: str, start: int, end: int | None = None) -> RefRelation:
    if end is not None and (after := _AFTER.match(text[end:end + 160])):
        # "Section 4.15 ... is hereby amended and restated as follows": the verb follows the reference.
        return RefRelation.REPLACES if after.group(1).lower() in ("repealed", "rescinded") else RefRelation.AMENDS
    before = text[max(0, start - 90):start]
    # The verb governs its own clause: stop at a sentence end, a semicolon, or the "and"/"or" before this reference.
    cut = max(before.rfind(". "), before.rfind("\n"), before.rfind(";"), before.rfind(" and "), before.rfind(" or "))
    before = before[cut + 1:] if cut >= 0 else before
    for pattern, relation in _RELATIONS:
        if pattern.search(before):
            return relation
    return RefRelation.CITES


def _is_prior_davis_stirling(code: str, number: str) -> bool:
    m = re.match(r"(\d+)(?:\.(\d+))?", number)
    return code == "CIV" and bool(m) and 1350 <= int(m.group(1)) <= 1378


def alias_pattern(aliases: dict[str, str]) -> re.Pattern | None:
    names = sorted(aliases, key=len, reverse=True)
    if not names:
        return None
    alt = "|".join(re.escape(n).replace(r"\ ", r"\s+") for n in names)
    return re.compile(rf"\b(?P<doc>{alt})(?:['’]s)?(?![A-Za-z])", re.I)


def _regulation_title(text: str, start: int) -> str:
    """The title of the regulations a bare number near ``start`` belongs to, read from the 400 characters of text before it:
    "Title 10" when it says so, 10 for the Real Estate Commissioner's regulations, else "" (a miss, not a guess)."""
    window = text[max(0, start - 400):start]
    if named := list(re.finditer(r"\bTitle\s+(\d{1,2})\b", window)):
        return named[-1].group(1)
    if re.search(r"Real\s+Estate\s+Commissioner|Commissioner[’']?s?\s+Regulations", window, re.I):
        return "10"
    return ""


def extract(outline: DocumentOutline, aliases: dict[str, str], *, external: bool = False) -> list[Reference]:
    """Every reference in ``outline``'s text. ``aliases`` maps each name a document goes by (lowercase) to its key.

    ``external`` is for material that is not one of the association's documents (a guide, a manual, an agency
    publication). The association's habits do not hold there: a bare four-digit section is not the Civil Code, and a
    code named later in the sentence is not the code of a number before it. A bare number is read as a regulation
    only when the text before it says whose regulations (``_regulation_title``); otherwise it is left alone.
    """
    text = outline.text
    lower_aliases = {k.lower(): v for k, v in aliases.items()}
    doc_names = alias_pattern(lower_aliases)
    out: list[Reference] = []
    taken: list[tuple[int, int]] = []

    def free(start: int, end: int) -> bool:
        return all(end <= s or start >= e for s, e in taken)

    section_spans: list[tuple[int, int, str]] = []        # each section reference's span, for a short form after it

    def add(kind: TargetKind, target: str, start: int, end: int, prior: bool = False) -> None:
        section = outline.section_at(start)
        out.append(Reference(outline.key, section.name if section else "", kind, target, _relation(text, start, end),
                             _sentence(text, start, end), start, prior))
        if kind is TargetKind.SECTION:
            section_spans.append((start, end, target))

    def whole_name(at: int, name: str, end: int) -> tuple[str, int]:
        """The whole code name ("Civil Code") or document name ("Declaration of Covenants, ...") starting at ``at``."""
        if whole := _CODE_NAME.match(text, at):
            return whole.group(0), whole.end()
        if doc_names and (whole := doc_names.match(text, at)):
            return whole.group("doc"), whole.end()
        return name, end

    def titled_key(at: int) -> str:
        """Another document named in the title of the section around ``at`` or of its parents."""
        section = outline.section_at(at)
        while section is not None and doc_names:
            if (named := doc_names.search(section.title)) and (key := lower_aliases.get(" ".join(named.group("doc").lower().split()))):
                return "" if key == outline.key else key
            section = outline.section(section.parent) if section.parent else None
        return ""

    # An unqualified "Section 4.15" in an amendment or an annexation means the Declaration it amends or supplements.
    default_key = outline.amends or outline.key
    code_near = re.compile(rf"^[^.;]{{0,160}}?\b(?:of\s+(?:the\s+)?)?(?P<code>{_CODE_ALT})", re.I)
    code_right_after = re.compile(rf"^\s*,?\s*(?:of\s+(?:the\s+)?)?(?P<code>{_CODE_ALT})", re.I)
    code_before = re.compile(rf"(?P<code>{_CODE_ALT})\s*\)?\s*,?\s*\(?\s*$", re.I)

    def doc_key(name: str) -> str:
        name = " ".join(name.lower().split())
        if _SELF.fullmatch(name) or name in ("this", "these"):
            return outline.key
        key = lower_aliases.get(name, "")
        if not key:
            stripped = re.sub(r"^(?:the|these|this|said)\s+", "", name)
            key = lower_aliases.get(stripped, "")
            if not key and re.fullmatch(r"(?:bylaws|declaration|policy|rules)", stripped) and outline.kind:
                key = ""
        return key

    for m in list(_STATUTE.finditer(text)) + list(_JASON_STYLE.finditer(text)):
        if not free(m.start(), m.end()):
            continue
        code = _code_of(m.group("code")) or m.group("code").upper()
        for number in _split_numbers(m.group("nums")):
            add(TargetKind.STATUTE, f"{code} {number}", m.start(), m.end(), _is_prior_davis_stirling(code, number))
        taken.append((m.start(), m.end()))
    for m in _REG.finditer(text):
        if free(m.start(), m.end()):
            add(TargetKind.STATUTE, f"{m.group('title')} CCR {m.group('num')}", m.start(), m.end())
            taken.append((m.start(), m.end()))
    for m in _SECTION.finditer(text):
        if not free(m.start(), m.end()):
            continue
        doc = m.group("doc") or ""
        begin = m.start()
        tail_end = m.end()
        if doc:
            # The name after "of the" is read lazily ("Civil"); take the whole code or document name that starts there.
            doc, tail_end = whole_name(m.start("doc"), doc, tail_end)
        if not doc and doc_names:
            # "Declaration Section 6.5(b)", "the Bylaws, Section 8.5(f)", "the Declaration ... under Section 2.5": the
            # name comes first.
            window = text[max(0, m.start() - 70):m.start()]
            lead = re.search(rf"(?:{doc_names.pattern})\s*,?\s*(?:(?:under|in|at|per)\s+)?$", window, re.I)
            if lead:
                doc, begin = lead.group("doc"), m.start() - (len(window) - lead.start())
        if not doc:
            # "Section 6.5(d) and Section 6.6(c) of the Declaration": the name after the last one covers the list.
            nums_end0 = m.start("nums") + len(m.group("nums"))
            if ahead := _AHEAD.match(text[nums_end0:nums_end0 + 90]):
                name, _ = whole_name(nums_end0 + ahead.start("doc"), ahead.group("doc"), 0)
                if _code_of(name) or doc_key(name):
                    doc = name
        code = _code_of(re.sub(r"^(?:the)\s+", "", doc.strip(), flags=re.I)) if doc else ""
        nums_end = m.start("nums") + len(m.group("nums"))
        if not code and not doc:
            # "section 602(k) Penal Code", "California Corporation Code, Section 7110": the code sits beside the number.
            if (right := code_right_after.match(text[nums_end:nums_end + 60])) or \
                    (right := code_before.search(text[max(0, m.start() - 50):m.start()])):
                code = _code_of(right.group("code")) or right.group("code").upper()
        key = doc_key(doc) if doc and not code else ""
        if doc and not code and not key:
            # "Section 4 of the Act": an unknown document; read the numbers as this document's only if nothing names another.
            if not re.match(r"(?:these|this)\b", doc, re.I):
                taken.append((m.start(), m.end()))
                continue
            key = outline.key
        end = tail_end if m.group("doc") else nums_end
        for number in _split_numbers(m.group("nums")):
            # A number whose whole part has four or more digits (5855, 1367.1, 12956.2) is a statute, never a section here.
            bare = re.fullmatch(r"(\d{4,6})((?:\.\d+)?[a-z]?(?:\([a-z0-9]+\))*)", number)
            if code:
                add(TargetKind.STATUTE, f"{code} {number}", begin, end, _is_prior_davis_stirling(code, number))
            elif external and bare:
                if title := _regulation_title(text, begin):
                    add(TargetKind.STATUTE, f"{title} CCR {number}", begin, end)
            elif not key and bare and 1350 <= int(bare.group(1)) <= 6200:
                # A bare four-digit section in an association document is the Civil Code (Davis-Stirling).
                add(TargetKind.STATUTE, f"CIV {number}", begin, end, _is_prior_davis_stirling("CIV", number))
            elif not key and bare:
                # A four-or-more-digit number with no dot is a statute: "subdivision (p) of Section 12955" names its code
                # somewhere in the sentence after it; with no code in sight it is left alone rather than guessed.
                if near := code_near.match(text[end:end + 200]):
                    add(TargetKind.STATUTE, f"{_code_of(near.group('code')) or near.group('code').upper()} {number}", begin, end)
            else:
                number = normalize_number(number)
                if key:
                    target_key = key
                else:
                    # Unqualified: this document's own section when its outline has it or a parent below the top level
                    # (an annexation's "1.3(d)(ii), below"). Else the document the enclosing section's title names (the
                    # Owner's Manual's "WHAT ARE THE CC&Rs?" lists "§ 4.15 (o)"), or the one it amends or supplements.
                    own = outline.section(number) or any(outline.section(a) for a in ancestors(number) if re.search(r"[.(]", a))
                    target_key = outline.key if own else (titled_key(begin) or default_key)
                add(TargetKind.SECTION, f"{target_key}#{number}", begin, end)
        taken.append((begin, end))
    if doc_names:
        for m in doc_names.finditer(text):
            if not free(m.start(), m.end()):
                continue
            key = lower_aliases.get(" ".join(m.group("doc").lower().split()), "")
            if not key or key == outline.key:
                continue
            after = re.match(rf"\s*,?\s*(?:[Ss]ection|§|[Aa]rticle)?\s*(?P<num>{_SEC_NUM})", text[m.end():m.end() + 40])
            if after and re.search(r"[.(]", after.group("num")) or (after and re.match(r"\s*,?\s*(?:[Ss]ection|§|[Aa]rticle)", text[m.end():])):
                number = normalize_number(after.group("num"))
                add(TargetKind.SECTION, f"{key}#{number}", m.start(), m.end() + after.end())
                taken.append((m.start(), m.end() + after.end()))
            else:
                add(TargetKind.DOCUMENT, key, m.start(), m.end())
                taken.append((m.start(), m.end()))
    for m in _RELATIVE.finditer(text):
        # A short form: "subsection (b)" names a part of the section just cited in the same sentence ("Section 4.15
        # (Rental), subsection (a)"), else a part or a sibling of the section it sits in ("as subsection (b) above
        # provides"). One that names nothing in the outline is left alone: a miss stays a miss.
        if not free(m.start(), m.end()) or _QUALIFIED.match(text, m.end()):
            continue
        labels = "".join(f"({x})" for x in re.findall(r"\(([A-Za-z0-9]{1,4})\)", m.group("labels")))
        target = _antecedent(text, m.start(), section_spans, labels)
        if not target and outline.key:
            here = outline.section_at(m.start())
            number = here.number if here else ""
            # A part of this section, else a sibling: no further out, where "paragraph (a) above" could mean any of
            # several (a)s.
            for base in ([number, *list(ancestors(number))[:1]] if number else []):
                if outline.section(base + labels) is not None and base + labels != number:
                    target = f"{outline.key}#{base + labels}"
                    break
        if target:
            add(TargetKind.SECTION, target, m.start(), m.end())
            taken.append((m.start(), m.end()))
    for m in _RESOLUTION.finditer(text):
        if free(m.start(), m.end()):
            add(TargetKind.RESOLUTION, f"resolution:{m.group('num')}", m.start(), m.end())
    for m in _INSTRUMENT.finditer(text):
        if free(m.start(), m.end()):
            target = f"instrument:{m.group('num')}" if m.group("num") else f"instrument:book {m.group('book')} page {m.group('page')}"
            add(TargetKind.INSTRUMENT, target, m.start(), m.end())
    # One reference per target per sentence: a sentence that names the same section twice cites it once.
    seen: set[tuple[str, str]] = set()
    unique = []
    for r in sorted(out, key=lambda r: r.offset):
        if (r.target, r.quote) in seen:
            continue
        seen.add((r.target, r.quote))
        unique.append(r)
    return unique


_RELATIVE = re.compile(r"(?<![\w§])(?:[Ss]ub)?(?:[Ss]ections?|[Pp]aragraphs?|[Ss]ubparagraphs?|[Ss]ubdivisions?|[Cc]lauses?)"
                       r"\s*(?P<labels>\([A-Za-z0-9]{1,4}\)(?:\s?\([A-Za-z0-9]{1,4}\))*)")
# "subdivision (a) of Section 4920 of the Civil Code" names another provision; "of this Section" does not.
_QUALIFIED = re.compile(r"\s*,?\s*of\s+(?!this\b|these\b)", re.I)


def _style(label: str) -> str:
    return "digit" if label.isdigit() else "upper" if label.isupper() else "lower"


def _antecedent(text: str, at: int, spans: list[tuple[int, int, str]], labels: str) -> str:
    """The section a short form hangs from: the last section cited before it in the same sentence, within a few words.
    A label of the same series as the antecedent's last one names a sibling ("Section 4.15(a) and subsection (b)")."""
    for start, end, target in reversed(spans):
        if end > at:
            continue
        between = text[end:at]
        if len(between) > 60 or re.search(r"\.\s|;|\n", between):
            return ""
        first = re.match(r"\(([A-Za-z0-9]{1,4})\)", labels)
        last = re.search(r"\(([A-Za-z0-9]{1,4})\)$", target)
        if first and last and _style(first.group(1)) == _style(last.group(1)):
            return target[: last.start()] + labels
        return target + labels
    return ""


def statute_key(target: str) -> tuple[str, str]:
    """"CIV 4926(a)(3)" -> ("CIV 4926", "(a)(3)"); "CIV 2924f(a)" -> ("CIV 2924f", "(a)"): the letter a section's
    number ends in is part of the section, a parenthesized label is a subdivision."""
    m = re.match(r"^(.*?\d+(?:\.\d+)?[a-z]?)((?:\([^)]*\))*)$", target)
    return (m.group(1), m.group(2)) if m else (target, "")


@dataclass(frozen=True)
class StatuteCitation:
    """One statute citation, read: the code as the Legislature abbreviates it, the section's number as the code
    prints it, and any subdivisions."""

    code: str                    # "CIV", "SHC", "10 CCR"
    number: str                  # "5855", "2924.12", "2924f"
    subdivisions: str = ""       # "(a)(1)"

    @property
    def base(self) -> str:
        """The section, as the shelf heads it: "CIV 2924f"."""
        return f"{self.code} {self.number}"

    @property
    def letter(self) -> str:
        """The letter the number ends in ("f" for 2924f), or ""."""
        return self.number[-1] if self.number[-1:].isalpha() else ""

    def __str__(self) -> str:
        return self.base + self.subdivisions


_REGULATIONS = r"C\.?C\.?R\.?|Cal(?:ifornia)?\.?\s*Code\s+(?:of\s+)?Reg(?:ulation)?s?\.?"
_ONE_CITATION = re.compile(
    rf"^\s*(?:(?:Title\s+)?(?P<title>\d{{1,2}})[\s-]+)?(?P<code>{_REGULATIONS}|{_CODE_ALT}|[A-Za-z]{{2,5}}\.?)[\s,-]*"
    rf"(?:(?:sections?|secs?\.?|§§?)\s*)?(?P<number>\d+(?:\.\d+)*[a-z]?)\s*(?P<subs>(?:\s?\([^()]*\))*)\s*$", re.I)


def statute_citation(text: str) -> StatuteCitation | None:
    """A whole string read as one statute citation, however it is written: "CIV 2924f", "civ-5855", "CIV 5855(a)",
    "Civil Code section 2924f", "Civ. Code, § 2924.12", "SHC 5898.16", "10 CCR 2792.23", "10-CCR-2792.23". None when
    the text is not a code and a section number.

    The number is read as written. A letter written against the digits is part of the number ("2924a" is the section
    after 2924); a letter in parentheses is a subdivision ("5855(a)"). Whether a lettered number is a section at all
    is for the shelf to say (``subdivision_reading``)."""
    m = _ONE_CITATION.match(text or "")
    if not m:
        return None
    name = " ".join(m.group("code").split())
    if m.group("title"):
        code = f"{m.group('title')} " + ("CCR" if re.fullmatch(_REGULATIONS, name, re.I) else name.rstrip(".").upper())
    else:
        code = _code_of(name) or (name.rstrip(".").upper() if re.fullmatch(r"[A-Za-z]{2,5}\.?", name) else "")
    if not code:
        return None
    return StatuteCitation(code, m.group("number").lower(), re.sub(r"\s+", "", m.group("subs") or ""))


def subdivision_reading(citation: StatuteCitation, listed: Iterable[str]) -> StatuteCitation | None:
    """What a lettered number may have been written for, read against the sections a shelf lists for the code.

    "CIV 2924a" where the shelf lists 2924a is that section, and nothing else is offered (None). "CIV 5855a" where the
    shelf lists 5855 and no 5855a is ambiguous as written: the shelf holds no such section, and the letter may be the
    subdivision. Then the citation it would be, "CIV 5855(a)", is returned for a reader to offer; a reader never
    quotes one section's words under another's number. None too when the shelf lists neither."""
    letter = citation.letter
    if not letter:
        return None
    listed = set(listed)
    if citation.number in listed or citation.number[:-1] not in listed:
        return None
    return StatuteCitation(citation.code, citation.number[:-1], f"({letter})" + citation.subdivisions)


def section_target(target: str) -> tuple[str, str]:
    """"bylaws#7.2" -> ("bylaws", "7.2")."""
    key, _, number = target.partition("#")
    return key, number


def ancestors(number: str) -> Iterable[str]:
    """"3.3(a)(i)" -> "3.3(a)", "3.3", "3": the sections a missing subsection falls back to."""
    n = number
    while n:
        if "(" in n:
            n = n[: n.rfind("(")]
        elif "." in n:
            n = n.rsplit(".", 1)[0]
        else:
            return
        yield n


__all__ = ["TargetKind", "RefRelation", "Reference", "extract", "statute_key", "section_target", "ancestors", "alias_pattern", "CODES",
           "ABBREVIATIONS", "LETTER", "SECTION_NUMBER", "STATUTE_IN_TEXT", "StatuteCitation", "statute_citation",
           "subdivision_reading"]
