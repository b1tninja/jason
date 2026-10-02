"""Reading hints: what the form's definition and jason's records say an answer can hold, used to put an OCR misread
right after the scan reader (``form_reader``) has read the page. OCR itself is not changed; a hint only works on what
it returned, and every change says so (``FieldReading.how`` gains "+hint").

Three kinds of hint, from strongest to weakest:

- **What was sent.** A pre-filled copy printed a value (re-made from PayHOA when the return is read, never kept). A
  reading that is that value once OCR's look-alikes are folded together (l, i, 1; o, 0; s, 5; rn, m; …) and spacing and
  punctuation dropped is that value: the owner left it. A reading that differs in anything else is the owner's change
  and stays as read, so a real correction (a misspelled email put right) is never swallowed. Folding is the only
  test: no "close enough".
- **What the answer is** (``FormQuestion.reads_as``). An email has no spaces, one "@", and a domain; a phone number is
  digits; in an address, a word that is one of the community's street names or a USPS word misread by a letter or two
  is that word, and digits OCR read as letters inside a house number or ZIP are digits.
- **Vocabulary**: the community's street names (``symbols.Street``) and the USPS words.

A hint is evidence like the reading itself; a person confirms the answer.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Any

from jason.community.forms import FormTemplate, QuestionKind, ReadAs

# OCR's look-alikes, folded to one character each (and a pair of letters that reads as one).
_FOLD_PAIRS = (("rn", "m"), ("cl", "d"), ("vv", "w"), ("ii", "u"))
_FOLD = str.maketrans({"l": "1", "i": "1", "|": "1", "!": "1", "j": "1", "o": "0", "q": "0", "s": "5", "b": "8",
                       "z": "2", "g": "6"})
EMAIL_DOMAINS = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "aol.com", "comcast.net",
                 "sbcglobal.net", "att.net", "live.com", "msn.com", "me.com", "example.com", "example.org")
_AT = re.compile(r"\s*(?:\(at\)|\[at\]|\{at\}|©|®|\(a\)|&)\s*", re.I)


def fold(text: str) -> str:
    """``text`` as OCR could have read it either way: lower case, letters and digits only, look-alikes as one."""
    flat = re.sub(r"[^a-z0-9|!@]", "", (text or "").casefold())
    for pair, one in _FOLD_PAIRS:
        flat = flat.replace(pair, one)
    return flat.translate(_FOLD)


@dataclass
class Hints:
    expected: dict[str, str] = field(default_factory=dict)       # the value a copy printed, by field (in memory only)
    vocabulary: tuple[str, ...] = ()                             # words an address may hold: street names, USPS words


def community_hints(expected: dict[str, Any] | None = None) -> Hints:
    """The hints any return of a community form can use: its street names; and, for a pre-filled copy, what it
    printed."""
    from jason.community.postal import _WORDS
    from jason.community.symbols import Street

    words = {w for s in Street for w in s.value.casefold().split()}
    words |= {w for pair in _WORDS.items() for w in pair if len(w) >= 3}
    return Hints({k: str(v) for k, v in (expected or {}).items() if isinstance(v, str) and v},
                 tuple(sorted(words)))


def _email(text: str) -> str:
    flat = _AT.sub("@", text or "").casefold().strip()
    flat = re.sub(r"\s*@\s*", "@", flat)
    flat = re.sub(r"(?<=\w)\s+(?=\w)", ".", flat)            # OCR reads a dot as a space; an email has no spaces
    flat = re.sub(r"\s+", "", flat).replace(",", ".").strip(".")
    flat = re.sub(r"\.c[o0]rn$|\.corn$|\.c0m$|\.con$|\.cpm$", ".com", flat)
    if flat.count("@") != 1:
        return flat
    user, domain = flat.split("@")
    near = difflib.get_close_matches(domain, EMAIL_DOMAINS, n=1, cutoff=0.8)
    return f"{user}@{near[0] if near else domain}"


def _phone(text: str) -> str:
    digits = re.sub(r"\D", "", (text or "").translate(str.maketrans("OoIlSB", "001158")))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}" if len(digits) == 10 else text


def _numberish(token: str) -> str:
    """A house number or a ZIP (four or more characters, mostly digits, every other one a digit's look-alike) with
    its look-alikes as digits. "15B" is an apartment, not a misread, and stays."""
    digits = sum(ch.isdigit() for ch in token)
    if len(token) >= 4 and digits >= len(token) / 2 and re.fullmatch(r"[\dOoIlSBZ]+", token):
        return token.translate(str.maketrans("OoIlSBZ", "0011582"))
    return token


def _address(text: str, vocabulary: tuple[str, ...]) -> str:
    out = []
    for token in re.findall(r"\S+", text or ""):
        core = token.strip(".,")
        fixed = _numberish(core)
        if fixed == core and core.isalpha() and len(core) >= 4 and core.casefold() not in vocabulary:
            near = difflib.get_close_matches(core.casefold(), vocabulary, n=1, cutoff=0.8)
            if near:
                fixed = near[0].upper() if core.isupper() else near[0].capitalize()
        out.append(token.replace(core, fixed) if core else token)
    return _state_from_zip(" ".join(out))


def _state_from_zip(text: str) -> str:
    """An address whose state is missing or misread before its ZIP ("Folsom, cn 95630", "Roseville, 95661") with the
    state the ZIP is in. A word that is a state already stays; a city word stays and the state goes after it."""
    from jason.community.postal import is_state, state_for_zip

    m = re.search(r"^(?P<head>.*?)(?P<prev>\S+)?\s+(?P<zip>\d{5})(?:-\d{4})?\s*$", text or "", re.S)
    if not m or not m.group("prev"):
        return text
    state = state_for_zip(m.group("zip"))
    prev = m.group("prev")
    if not state or is_state(prev):
        return text
    if prev.endswith(",") or len(prev.strip(".,")) > 3:      # "Roseville," or "Roseville": the state goes after it
        return f"{m.group('head')}{prev.rstrip(',')}, {state} {m.group('zip')}"
    return f"{m.group('head')}{state} {m.group('zip')}"        # "cn", "C4": a misread state


_EMAIL_IN = re.compile(r"\S+\s*@\s*\S+(?:\s+(?:com|org|net|edu|gov|us|io)\b)?", re.I)


def _contact(text: str, vocabulary: tuple[str, ...]) -> str:
    """A contact's email put right where it has one (the words round its "@"), the rest as an address."""
    flat = _AT.sub("@", text or "")
    m = _EMAIL_IN.search(flat)
    if not m:
        return _address(flat, vocabulary)
    return " ".join(x for x in (_address(flat[:m.start()].strip(), vocabulary), _email(m.group(0)),
                                _address(flat[m.end():].strip(), vocabulary)) if x)


def put_right(value: str, reads: ReadAs, hints: Hints, sent: str = "") -> tuple[str, str]:
    """``value`` with the hints applied, and which hint changed it ("" when none did)."""
    if not value:
        return value, ""
    if sent and fold(value) == fold(sent):
        return sent, "sent" if value != sent else ""
    fixed = {ReadAs.EMAIL: lambda v: _email(v),
             ReadAs.PHONE: lambda v: _phone(v),
             ReadAs.ADDRESS: lambda v: _address(v, hints.vocabulary),
             ReadAs.CONTACT: lambda v: _contact(v, hints.vocabulary)}.get(reads, lambda v: v)(value)
    if sent and fold(fixed) == fold(sent):
        return sent, "sent"
    return fixed, (reads.value if fixed != value else "")


def apply(reading: Any, form: FormTemplate, hints: Hints) -> Any:
    """The scan reading (``form_reader.ScanReading``) with each text answer put right by the hints, in place; each
    change is marked in its ``how`` and noted."""
    from jason.community.form_reader import FieldReading

    for q in form.questions:
        if q.kind in (QuestionKind.CHOICE, QuestionKind.CHECKBOX):
            continue
        got = reading.fields.get(q.field)
        if got is None or not isinstance(got.value, str):
            continue
        fixed, how = put_right(got.value, q.reads_as, hints, hints.expected.get(q.field, ""))
        if how:
            reading.fields[q.field] = FieldReading(fixed, f"{got.how}+hint", max(got.confidence, 0.7 if how == "sent"
                                                                                  else got.confidence))
            reading.notes.append(f"{q.field}: put right by the {how} hint")
    return reading


__all__ = ["EMAIL_DOMAINS", "Hints", "apply", "community_hints", "fold", "put_right"]
