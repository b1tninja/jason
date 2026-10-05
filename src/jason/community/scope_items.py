"""A proposal's scope of work, read as items: the lines that say what work is done, and what the price covers.

A proposal seldom writes its scope as sentences with a subject. It lists the work as lines, bulleted ("- Reset and
secure 3 slipped tiles"), numbered ("1. Crack seal all cracks"), or plain imperative lines ("Provide access to each
location"), and it says what the price covers in statements of their own ("The price includes all labor, materials,
and equipment", "Traffic control is included at no additional cost", "... and repair minor leaks at no additional
cost"). These are the work the board is paying for, but a reader that looks for a subject and a modal ("We will",
"Contractor shall") reads them as nothing. The board needs them on the list all the same: an item missing from the
scope is work the vendor never promised.

``find_scope_items(text)`` reads both kinds:

- A **work item** is a list item or a plain line that opens with an imperative verb (``WORK_VERBS``). A list item under
  a scope heading ("Scope of Work", "Scope:") is a work item whatever its first word ("- Gutter cleaning").
- An **inclusion** is a sentence, or the coordinated clause of one, that says the price covers something
  (``INCLUSION_RULES``: "at no additional cost", "is included", "the price includes").

Neither is read where the text says the opposite: a line under an "Exclusions" or "Not included" heading, the items
``exemptions.excluded_items`` reads, and a sentence ``exemptions.exemption_of`` reads as an exclusion ("Sales tax is not
included"). A heading, a price line alone ("Total: $1,200"), a signature line, and an address, phone, or email line are
never items. Nor is a line that gives the work to someone else (``OTHERS_RULES``: "Permits by others", "Permits by
owner", "Owner to supply paint"). A miss stays a miss: a line that opens with a noun is not guessed to be work.

An item that is offered rather than included is an **option** (``ScopeKind.OPTION``): one under an optional or
alternate heading (``OPTION_HEADINGS``: "Optional Items", "Add Alternates:"), one opening with a label
(``OPTION_LABEL``: "Alternate:", "Option 2:"), and one priced on top of the base (``OPTION_RULES``: "at an additional
cost").

A list item without closing punctuation carries onto the next line when that line opens in lowercase, is indented under
the item's text, or follows a word that leaves the sentence open ("on", "and", a comma); a line opening with a label
("Alternate: ...") or a new capitalised sentence starts something new. A plain line carries only onto a lowercase line.

Each ``ScopeItem`` carries its offsets into the text given (``text[start:end]`` is the item, with its line breaks), its
words with whitespace collapsed, and the heading it sits under, as written ("CUSTOMER:", "Scope of Work"). jason does
not decide here whose work an item is: a list under a role label ("CUSTOMER:") is the other party's work, and the
caller reads the heading for that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from jason.community.exemptions import ExemptionKind, excluded_items, exemption_of


class ScopeKind(Enum):
    WORK = "work item"
    INCLUSION = "included in the price"
    OPTION = "optional or alternate"


@dataclass(frozen=True)
class ScopeItem:
    text: str
    kind: ScopeKind
    start: int
    end: int
    heading: str = ""


@dataclass(frozen=True)
class ScopeRule:
    """One cue a line or statement carries: its pattern, what the row is for, and words that cancel it."""

    pattern: re.Pattern[str]
    note: str
    unless: re.Pattern[str] | None = None

    def search(self, text: str) -> re.Match[str] | None:
        found = self.pattern.search(text)
        if found is None or (self.unless is not None and self.unless.search(text)):
            return None
        return found


# The older name of the row: an inclusion rule is a scope rule.
InclusionRule = ScopeRule


def _rule(pattern: str, note: str, unless: str = "") -> ScopeRule:
    return ScopeRule(re.compile(pattern, re.IGNORECASE), note,
                     re.compile(unless, re.IGNORECASE) if unless else None)


INCLUSION_RULES: tuple[InclusionRule, ...] = (
    _rule(r"\b(?:at|for|with)\s+no\s+(?:additional|extra|added|further|separate)?\s*(?:cost|charge|fee)s?\b",
          "at no additional cost / charge"),
    _rule(r"\bfree\s+of\s+(?:charge|cost)\b", "free of charge"),
    _rule(r"\bwithout\s+(?:any\s+)?(?:additional|extra|separate)\s+(?:cost|charge|fee)s?\b",
          "without additional charge"),
    _rule(r"\b(?:price|pricing|quote|quotation|proposal|bid|fee|cost|amount|sum|estimate)\s+(?:also\s+)?includes?\b",
          "the price includes"),
    _rule(r"\b(?:is|are)\s+(?:also\s+)?included\b", "is/are included"),
    _rule(r"\bincluded\s+in\s+(?:the|our|this)\s+(?:price|quote|quotation|proposal|bid|fee|cost|estimate)\b",
          "included in the price"),
)

_PARTY = r"(?:the\s+)?(?:owners?|customers?|clients?|association|hoa|board|others|management|manager)"

# Lines that give the work to someone other than the vendor: never a scope item, under a scope heading or not.
OTHERS_RULES: tuple[ScopeRule, ...] = (
    _rule(r"\bby\s+others\b", "by others"),
    _rule(rf"\bby\s+{_PARTY}\s*[.;,)]?\s*$|\b(?:supplied|furnished|provided|done|performed|obtained)\s+"
          rf"by\s+{_PARTY}\b",
          "by the owner / customer / association",
          unless=r"\b(?:approved|directed|selected|chosen|requested|specified|authorized|accepted|agreed)\s+"
                 r"(?:to\s+)?by\b"),
    _rule(rf"^\s*{_PARTY}\s+(?:to|shall|will|must)\s+(?:supply|provide|furnish|obtain|purchase)\b",
          "<party> to supply / provide / furnish"),
)

# A heading over optional or alternate work: its items are offered, not in the base price.
OPTION_HEADINGS: tuple[ScopeRule, ...] = (
    _rule(r"^\s*optional(?:\s+(?:items?|work|services|scope|upgrades?|add[\s-]?ons?))?\s*:?\s*$", "optional"),
    _rule(r"^\s*(?:add(?:itive)?\s+)?alternates?(?:\s+(?:items?|work|pricing))?\s*:?\s*$",
          "alternate(s) / add alternate"),
    _rule(r"^\s*add[\s-]?ons?(?:\s+(?:items?|work|services))?\s*:?\s*$", "add-on(s)"),
    _rule(r"^\s*upgrades?(?:\s+options?)?\s*:?\s*$", "upgrade options"),
)

# A line that offers work instead of including it: a label that opens it, or a price on top of the base.
OPTION_LABEL = re.compile(
    r"^\s*(?:add(?:itive)?\s+)?(?:alternate|option|optional)(?:\s+(?:no\.?\s*)?[0-9A-Za-z]{1,3})?\s*:\s*",
    re.IGNORECASE)
OPTION_RULES: tuple[ScopeRule, ...] = (
    _rule(r"\b(?:at|for)\s+an?\s+(?:additional|extra|added)\s+(?:cost|charge|fee|price)\b",
          "at an additional cost"),
    _rule(r"\bfor\s+an?\s+(?:additional|extra)\s+\$\s?[0-9]", "for an additional $"),
    _rule(r"\b(?:additional|extra)\s+(?:cost|charge)\s+of\s+\$\s?[0-9]", "an additional cost of $"),
)

# Verbs a scope line opens with. A word that is as often a noun ("set", "test", "service") is kept only where the
# subject check below catches its noun reading ("Test results will be sent" has a subject and a modal).
WORK_VERBS: frozenset[str] = frozenset("""
    add adjust aerate apply blow build caulk clean clear coat compact connect construct coordinate cover crack cut
    deliver demolish disconnect dispose edge erect excavate extend fabricate fertilize fill flush frame furnish grade
    grind haul hang hire inspect install jet lay level mask monitor mount mow mulch obtain overseed paint patch perform
    plant power-wash prepare pressure-wash prime protect provide prune pump re-caulk re-secure re-set rebuild recoat
    refinish reinstall relocate remove repair repaint replace reroute reseal reset restore restripe retrofit rewire
    sand saw scrape seal secure service spray stain stripe supply sweep tear test tighten treat trim unclog upgrade
    vacuum verify wash weed weld wire
""".split())

_LIST_MARKER = re.compile(r"^(?P<lead>\s*(?:[-*•▪◦·]|o|[0-9]+[.)]|\([0-9]+\)|\(?[a-zA-Z][.)]))(?:\s+|$)")
_BARE_MARKER = re.compile(r"^\s*(?:[-*•▪◦·]|o)\s*$")
_FIRST_WORD = re.compile(r"^[\"'(]*(?P<word>[A-Za-z][A-Za-z-]*)\b")
# An imperative has no subject: a modal or a copula right after the first word or two means the first word is a noun.
_HAS_SUBJECT = re.compile(r"^\S+(?:\s+\S+)?\s+(?:will|shall|must|may|should|can|is|are|was|were|has|have|had)\b",
                          re.IGNORECASE)
_TERMINAL = re.compile(r"[.;:!?]\s*$")

_SCOPE_HEADING = re.compile(
    r"^\s*(?:scope(?:\s+of\s+(?:the\s+)?(?:work|services|repairs?))?|work\s+to\s+be\s+(?:performed|done)|"
    r"(?:description\s+of\s+)?work(?:\s+description)?|services(?:\s+to\s+be\s+(?:provided|performed))?|"
    r"specifications?|repairs?(?:\s+to\s+be\s+performed)?)\s*:?\s*$",
    re.IGNORECASE)
_EXCLUSION_START = re.compile(
    r"^\s*(?:work\s+)?(?:exclusions?|not\s+included|excluded(?:\s+(?:items|work))?|work\s+not\s+included|"
    r"items\s+not\s+included)\b\s*:?",
    re.IGNORECASE)
_HEADING_COLON = re.compile(r"^\s*[^.]{1,60}:\s*$")
_HEADING_CAPS = re.compile(r"^\s*[A-Z][A-Z0-9 &/,'()-]{2,60}:?\s*$")
_SMALL_WORDS = frozenset("a an and as at by for in of on or the to with & -".split())

# Lines that are never an item: signature blanks, addresses, phones, emails, and a price with no work in it.
_NOT_ITEM = re.compile(
    r"_{3,}|@\w|\b[A-Z]{2}\s+[0-9]{5}\b|\(?\b[0-9]{3}\)?[\s.-][0-9]{3}-[0-9]{4}\b|"
    r"^\s*(?:signed|accepted|date|by|name|title|signature|billing\s+address|bill\s+to|attention)\b",
    re.IGNORECASE)
_PRICE = re.compile(r"\$\s?[0-9]")

# A sentence ends at a period, question or exclamation mark, then space and a capital or digit; a business suffix's
# period ("Example Roofing, Inc. will") does not end one.
_SENTENCE_END = re.compile(r"(?<!\bInc)(?<!\bCo)(?<!\bCorp)(?<!\bLtd)(?<!\bNo)(?<!\bSt)[.!?](?=\s+[A-Z0-9(\"']|\s*$)")
# Words that name an attachment, not work: "Exhibit A is included for reference" includes no work in the price.
_ATTACHMENT = re.compile(r"\b(?:exhibit|schedule|attachment|appendix|addendum|copy|copies|this\s+page)\b",
                         re.IGNORECASE)


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or _LIST_MARKER.match(line):
        return False
    if _HEADING_COLON.match(stripped) or _SCOPE_HEADING.match(stripped):
        return True
    if _HEADING_CAPS.match(stripped) and any(c.isalpha() for c in stripped):
        return True
    words = stripped.split()
    if len(words) <= 5 and not _TERMINAL.search(stripped):
        return all(w[0].isupper() or w[0].isdigit() or w.lower() in _SMALL_WORDS for w in words)
    return False


# A line that opens with a label ("Alternate: ...", "Note: ...") starts something new; it never carries on an item.
_LABEL = re.compile(r"^\s*[A-Z][A-Za-z-]*(?:\s+[A-Za-z0-9.-]+){0,2}\s*:(?:\s|$)")
# An item that ends on one of these words, or a comma or dash, is mid-sentence: the next line carries it on even when
# that line opens with a capital ("Install gutters on" / "Building 3").
_DANGLING_END = re.compile(r"(?:[,&/-]|\b(?:a|an|and|as|at|by|for|from|in|into|of|on|onto|or|over|the|to|under|"
                           r"with|including|per|between|along|across|around|behind|near|plus))\s*$",
                           re.IGNORECASE)


def _is_option_heading(line: str) -> bool:
    return any(rule.search(line) for rule in OPTION_HEADINGS)


def _gives_to_others(words: str) -> bool:
    """The line gives the work to someone other than the vendor ("Permits by others", "Owner to supply paint")."""
    return any(rule.search(words) for rule in OTHERS_RULES)


def _carries(body: str, nxt: _Line, is_list: bool, text_col: int) -> bool:
    """Whether the next line carries on an item that has not ended, rather than starting something new.

    A list item carries onto a lowercase line, a line indented under its text, or a capitalised line after a word that
    leaves the sentence open. A plain line carries only onto a lowercase line.
    """
    stripped = nxt.text.strip()
    if (not stripped or _TERMINAL.search(body) or _LIST_MARKER.match(nxt.text) or _BARE_MARKER.match(nxt.text)
            or _is_heading(nxt.text) or _LABEL.match(nxt.text) or OPTION_LABEL.match(nxt.text)):
        return False
    opener = stripped.lstrip("\"'(")
    if opener[:1].islower():
        return True
    if not is_list:
        return False
    indent = len(nxt.text) - len(nxt.text.lstrip())
    return (indent >= text_col > 0) or bool(_DANGLING_END.search(body))


def _opens_with_verb(item: str) -> bool:
    first = _FIRST_WORD.match(item)
    if not first or first.group("word").lower() not in WORK_VERBS:
        return False
    return not _HAS_SUBJECT.match(item.strip())


def _collapse(text: str) -> str:
    return " ".join(text.split())


@dataclass
class _Line:
    start: int  # offset of the line's first character
    text: str  # the line without its line break


def _lines(text: str) -> list[_Line]:
    out: list[_Line] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        body = raw.rstrip("\r\n")
        out.append(_Line(offset, body))
        offset += len(raw)
    return out


def _work_items(text: str) -> list[ScopeItem]:
    excluded = {_collapse(item).lower() for item in excluded_items(text)}
    lines = _lines(text)
    items: list[ScopeItem] = []
    heading = ""
    in_scope = in_exclusions = in_options = False
    exclusion_items_seen = False
    pending_bullet = False
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.text.strip()
        if not stripped:
            if in_exclusions and exclusion_items_seen:
                in_exclusions = False
            i += 1
            continue
        if _BARE_MARKER.match(line.text):
            pending_bullet = True
            i += 1
            continue
        marker = _LIST_MARKER.match(line.text)
        is_list = bool(marker) or pending_bullet
        pending_bullet = False
        if not is_list and _EXCLUSION_START.match(stripped):
            in_exclusions, exclusion_items_seen, in_scope, in_options = True, False, False, False
            heading = stripped
            i += 1
            continue
        if not is_list and _is_option_heading(stripped):
            heading = stripped
            in_scope = in_options = True
            in_exclusions = False
            i += 1
            continue
        if not is_list and _is_heading(line.text):
            heading = stripped
            in_scope = bool(_SCOPE_HEADING.match(stripped))
            in_exclusions = in_options = False
            i += 1
            continue
        # The item's text: after the marker (and an "Alternate:" label), carried onto the next lines while it has not
        # ended.
        lead = len(marker.group(0)) if marker else len(line.text) - len(line.text.lstrip())
        label = OPTION_LABEL.match(line.text[lead:])
        if label:
            lead += label.end()
        start = line.start + lead
        end = line.start + len(line.text.rstrip())
        body = line.text[lead:].rstrip()
        j = i + 1
        while j < len(lines) and _carries(body, lines[j], is_list, lead):
            nxt = lines[j]
            body += " " + nxt.text.strip()
            end = nxt.start + len(nxt.text.rstrip())
            j += 1
        i = j
        if in_exclusions:
            exclusion_items_seen = True
            continue
        words = _collapse(body)
        if not words or words.lower() in excluded or _NOT_ITEM.search(words) or _gives_to_others(words):
            continue
        verb = _opens_with_verb(words)
        if not verb:
            if not (is_list and in_scope) or _PRICE.search(words) or len(words.split()) < 2:
                continue
        elif not is_list and len(words.split()) < 3:
            continue
        found = exemption_of(words)
        if found is not None and found.kind is ExemptionKind.EXCLUDED:
            continue
        offered = in_options or bool(label) or any(rule.search(words) for rule in OPTION_RULES)
        items.append(ScopeItem(words, ScopeKind.OPTION if offered else ScopeKind.WORK, start, end, heading))
    return items


def _sentences(text: str) -> list[tuple[int, int]]:
    """Spans of the text's sentences. A line break ends one after a heading, before a list item, or after a stop."""
    spans: list[tuple[int, int]] = []
    lines = _lines(text)
    begin: int | None = None
    last_end = 0

    def close(stop: int) -> None:
        nonlocal begin
        if begin is not None and stop > begin:
            chunk = text[begin:stop]
            cursor = 0
            for found in _SENTENCE_END.finditer(chunk):
                piece_end = found.end()
                spans.append((begin + cursor, begin + piece_end))
                cursor = piece_end
                while cursor < len(chunk) and chunk[cursor].isspace():
                    cursor += 1
            if cursor < len(chunk.rstrip()):
                spans.append((begin + cursor, begin + len(chunk.rstrip())))
        begin = None

    for k, line in enumerate(lines):
        stripped = line.text.strip()
        if not stripped or _is_heading(line.text) or _BARE_MARKER.match(line.text):
            close(last_end)
            continue
        marker = _LIST_MARKER.match(line.text)
        if marker or begin is None or _LABEL.match(line.text) or OPTION_LABEL.match(line.text):
            close(last_end)
            begin = line.start + (len(marker.group(0)) if marker else len(line.text) - len(line.text.lstrip()))
        last_end = line.start + len(line.text.rstrip())
        if _TERMINAL.search(line.text):
            close(last_end)
    close(last_end)
    return spans


def _exclusion_spans(text: str) -> list[tuple[int, int]]:
    """Where the text is under an exclusions heading: from the heading to the next blank line after items, or heading."""
    spans: list[tuple[int, int]] = []
    open_at: int | None = None
    seen = False
    for line in _lines(text):
        stripped = line.text.strip()
        if _EXCLUSION_START.match(stripped):
            if open_at is None:
                open_at, seen = line.start, False
            continue
        if open_at is None:
            continue
        if not stripped:
            if seen:
                spans.append((open_at, line.start))
                open_at = None
            continue
        if _is_heading(line.text):
            spans.append((open_at, line.start))
            open_at = None
            continue
        seen = True
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def _clause_start(sentence: str, cue_at: int) -> int:
    """Where the coordinated clause holding the cue starts: "We will inspect ... and repair leaks at no cost"."""
    best = 0
    for found in re.finditer(r"(?:,\s*|\s+)(?:and|then|also)\s+(?P<verb>[A-Za-z-]+)\b", sentence[:cue_at]):
        if found.group("verb").lower() in WORK_VERBS:
            best = found.start("verb")
    return best


def _inclusions(text: str) -> list[ScopeItem]:
    excluded_at = _exclusion_spans(text)
    items: list[ScopeItem] = []
    for s_start, s_end in _sentences(text):
        if any(a <= s_start < b for a, b in excluded_at):
            continue
        sentence = text[s_start:s_end]
        words = _collapse(sentence)
        if words.endswith(":") or _NOT_ITEM.search(words) or _gives_to_others(words):
            continue
        found = exemption_of(words)
        if found is not None and found.kind is ExemptionKind.EXCLUDED:
            continue
        for rule in INCLUSION_RULES:
            cue = rule.search(sentence)
            if not cue:
                continue
            if _ATTACHMENT.search(sentence[:cue.start()]):
                break
            start = s_start + _clause_start(sentence, cue.start())
            items.append(ScopeItem(_collapse(text[start:s_end]), ScopeKind.INCLUSION, start, s_end))
            break
    return items


def find_scope_items(text: str) -> list[ScopeItem]:
    """The scope's work items and inclusion statements, in the order they appear.

    An inclusion that lies inside a work item ("- Repair leaks at no additional cost") is read once, as the work item.
    """
    work = _work_items(text)
    items = list(work)
    for inclusion in _inclusions(text):
        if not any(w.start < inclusion.end and inclusion.start < w.end for w in work):
            items.append(inclusion)
    return sorted(items, key=lambda item: item.start)


__all__ = ["ScopeKind", "ScopeItem", "ScopeRule", "InclusionRule", "INCLUSION_RULES", "OTHERS_RULES",
           "OPTION_HEADINGS", "OPTION_LABEL", "OPTION_RULES", "WORK_VERBS", "find_scope_items"]
