"""Suggestions for what a scanned page's words are, where OCR misread them. Never silent edits.

OCR of a crisp recorded scan is mostly right and wrong in a few repeatable ways: it runs words together ("ofthe",
"Notmore"), misreads a letter ("faifure", "concem"), reads a rule as "|" or a page number into the running text, and
mangles a section label ("{c)"). Each reader here proposes a ``Suggestion`` for a span of tokens, with its method and
its evidence:

- **lexicon** (``lexicon_suggestions``): a run-together word split by the language model (Viterbi over the clean
  corpus, ``Lexicon.segment``); a non-word read as the likeliest word a few OCR confusions away (a noisy channel:
  ``rn`` for ``m``, ``li`` for ``h``, ``1`` for ``l``), ranked by the words around it. It never touches a word that
  is a word, a number, a label, or a term the document uses.
- **layout** (``layout_suggestions``): a word broken at a line's end, a stray bar or speck, a page number in the
  running text, a curly quote OCR could not encode, a label's bracket.
- **local model**, **vision**, **working copy**: other readers' suggestions in the same shape (``ocr_models``; the
  working copy is a person's transcription of the same text).

A suggestion is evidence. ``guard`` says why it may not be taken without a person reading the page: it changes a
number or an operative word (``living.changes_meaning``), or adds or drops a word beyond its span (the spirit of Code
Civ. Proc. 1858: insert nothing omitted, omit nothing inserted). ``tier`` is the confidence a person sees in the
intake queue: ``likely`` only when two independent methods agree and the guard passes, or, for a guarded change, when
the vision model's reading of the page agrees with a second method.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Iterable, Sequence

from jason.community.lexicon import Lexicon, TokenClass, core
from jason.community.ocr_channel import Channel


class Method(Enum):
    LEXICON = "lexicon"              # the language model over clean text: word splits and the noisy channel
    LAYOUT = "layout"                # line-end hyphens, stray marks, page numbers, quotes, label brackets
    LOCAL_MODEL = "local model"      # a local text model, shown the passage
    VISION = "vision"                # a vision model reading the word's crop of the page image
    WORKING_COPY = "working copy"    # a person's hand-kept transcription of the same text
    PERSON = "person"                # a person reading the page


# Independent readers: the lexicon and layout rules read the same OCR text with the same knowledge of English, so they
# count as one; the others each read something different (a model's judgment, the page's pixels, a person's copy).
_FAMILY = {Method.LEXICON: "text rules", Method.LAYOUT: "text rules", Method.LOCAL_MODEL: "local model",
           Method.VISION: "vision", Method.WORKING_COPY: "working copy", Method.PERSON: "person"}


class Fix(Enum):
    SPLIT = "split"                  # run-together words ("ofthe" -> "of the")
    JOIN = "join"                    # a word broken at a line's end ("assess- ment")
    CHARACTER = "character"          # misread letters ("faifure" -> "failure")
    PUNCTUATION = "punctuation"      # a mark misread or missing its space ("Assessments,which")
    LABEL = "label"                  # a section label ("{c)" -> "(c)")
    STRAY = "stray"                  # a mark that is no word: a rule read as "|", a speck
    FOLIO = "folio"                  # a page number in the running text ("- 12 -")
    OTHER = "other"


class Tier(Enum):
    LIKELY = "likely"                # two independent methods agree and the guard passes: accept in a batch, after a look
    SUGGESTED = "suggested"          # one method, or a guarded change: a person reads the page
    CONFLICT = "conflict"            # methods disagree: a person reads the page


@dataclass(frozen=True)
class Suggestion:
    start: int                       # the span of the passage's tokens (split on whitespace) it replaces
    end: int
    wrong: str                       # those tokens, joined by single spaces
    right: str                       # what the method reads there ("" drops them)
    fix: Fix
    methods: tuple[Method, ...]
    confidence: float = 0.5          # the method's own, 0 to 1 (a posterior, or a model's stated confidence)
    evidence: tuple[str, ...] = ()

    @property
    def guard(self) -> str:
        return guard(self.wrong, self.right, self.fix)

    @property
    def families(self) -> frozenset[str]:
        return frozenset(_FAMILY[m] for m in self.methods)


# Words whose change changes what a provision requires (the same list ``living.changes_meaning`` refuses).
def _operative() -> frozenset[str]:
    from jason.community.living import _OPERATIVE_WORDS

    return _OPERATIVE_WORDS


def guard(wrong: str, right: str, fix: Fix | None = None) -> str:
    """Why a change may not be taken without a person reading the page; empty when it is editorial: spacing alone, or
    letters that change no number, no operative word, and add or drop no word."""
    from jason.community.living import changes_meaning

    if re.sub(r"\s+", "", wrong) == re.sub(r"\s+", "", right):
        return ""
    why = changes_meaning(wrong, right)
    if why:
        return why
    a = [t for t in wrong.split() if re.search(r"[A-Za-z0-9]", t)]
    b = [t for t in right.split() if re.search(r"[A-Za-z0-9]", t)]
    if len(b) > len(a):
        return "adds a word"
    if len(b) < len(a) and fix not in (Fix.STRAY, Fix.FOLIO):
        return "drops a word"
    if len(b) < len(a) and any(re.search(r"[A-Za-z]{2,}", t) for t in a):
        return "drops a word"
    return ""


# Case and punctuation around a word's core.

def _split_edges(token: str) -> tuple[str, str, str]:
    m = re.match(r"^([^\w]*)(.*?)([^\w]*)$", token, re.S)
    return (m.group(1), m.group(2), m.group(3)) if m else ("", token, "")


def _match_case(model: str, word: str) -> str:
    letters = [c for c in model if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 1:
        return word.upper()
    if letters and letters[0].isupper():
        return word[:1].upper() + word[1:]
    return word


_SENTENCE_END = re.compile(r"[.?!][\"')\]]*$")


def case_for(word: str, read: str, prev: str, lexicon: Lexicon) -> str:
    """A corrected word's capitals from where it stands, not from a misread first glyph: all capitals when the token
    was ("OWNER"); the token's own case when its first letter was read right ("Restrictinns" is "Restrictions", as
    the heading wrote it); otherwise the document's own form for a defined term ("tJnit" is "Unit"); a capital after a
    sentence's end; else the form the clean text mostly writes (a name keeps its capital, "Lhe" mid-sentence is "the").
    After a label, at the start of a passage, or where the clean text says too little, the token's own case stands:
    those places can begin a sentence or not."""
    letters = [c for c in read if c.isalpha()]
    if letters and all(c.isupper() for c in letters) and len(letters) > 1:
        return word.upper()
    if letters and letters[0].lower() == word[:1].lower():
        return _match_case(read, word)               # the first glyph was read right, so its case was too
    form = lexicon.term_forms.get(word.lower())
    if form:
        return form
    if prev and _SENTENCE_END.search(prev):
        return word[:1].upper() + word[1:]
    if not prev or re.fullmatch(r"[\(\[{]?[A-Za-z0-9]{1,5}[\)\]}][.,:;]?|[:;\"'“‘]", prev):
        return _match_case(read, word)
    share = lexicon.capital_share(word)
    if share is None:
        return _match_case(read, word)
    return word[:1].upper() + word[1:] if share >= 0.6 else word.lower()


# The noisy channel: what OCR tends to read for what was printed (printed -> read is the reverse of these pairs).
# Each pair is (as read, as printed).
CONFUSIONS: tuple[tuple[str, str], ...] = (
    ("rn", "m"), ("m", "rn"), ("cl", "d"), ("d", "cl"), ("li", "h"), ("h", "li"), ("ii", "u"), ("u", "ii"),
    ("nn", "m"), ("in", "m"), ("m", "in"), ("ni", "m"), ("vv", "w"), ("w", "vv"), ("tl", "d"), ("ri", "n"),
    ("fi", "h"), ("1", "l"), ("l", "1"), ("1", "i"), ("I", "l"), ("l", "I"), ("!", "l"), ("|", "l"), ("|", "I"),
    ("0", "o"), ("0", "O"), ("5", "s"), ("$", "S"), ("$", "s"), ("c", "e"), ("e", "c"), ("f", "t"), ("t", "f"),
    ("f", "l"), ("l", "f"), ("t", "l"), ("l", "t"), ("i", "l"), ("l", "i"), ("n", "u"), ("u", "n"), ("a", "o"),
    ("o", "a"), ("c", "o"), ("o", "c"), ("h", "b"), ("b", "h"), ("e", "o"), ("B", "E"), ("E", "B"), ("é", "e"),
    ("ﬁ", "fi"), ("ﬂ", "fl"),
)
LOG_CONFUSION = math.log(0.02)       # one of the pairs above
LOG_JUNK = math.log(0.02)            # a mark inside a word deleted or read as a letter ("a:.d" -> "and")
LOG_EDIT = math.log(0.001)           # any other letter added, dropped, or changed
LOG_KEEP = math.log(0.9)             # the word was read right


@dataclass(frozen=True)
class Options:
    """Switches for the readings beyond today's text rules; the default is today's behavior. Each is measured in
    docs/ocr-correction.md ("Measurements, October 5, 2026")."""

    channel: Channel | None = None     # the confusions a recognizer makes; None is the hand list (``CONFUSIONS``)
    case_by_context: bool = False      # a corrected word's capitals from its sentence and the document's terms, not
                                       # from the misread first glyph ("Lhe" mid-sentence is "the")
    term_bonus: float = 0.0            # log weight added to a candidate that is one of the document's defined terms
    real_words: float = 0.0            # a real word is read as another when the noisy channel's posterior for the other
                                       # reaches this (0 is off); words already read as real words are doubted only then
    search: bool = False               # also search the vocabulary for words within three edits (``ocr_vocab``)
    real_keep: float = math.log(0.995) # the prior that a real word was printed as read
    real_ratio: float = 5.0            # the other word must be this many times likelier than the one read, by itself
    route_real: float = 0.0            # a real word whose best other reading has this posterior is sent to the page (0 off)


DEFAULT = Options()
HAND_CHANNEL = Channel("hand", tuple((r, p, LOG_CONFUSION) for r, p in CONFUSIONS))


def _edits1(word: str, channel: Channel | None = None) -> Iterable[tuple[str, float]]:
    """Every string one OCR edit from ``word``, with the edit's log probability."""
    letters = "abcdefghijklmnopqrstuvwxyz"
    yield from _confusions(word, channel)
    for i, ch in enumerate(word):
        junk = not ch.isalpha()
        cost = LOG_JUNK if junk else LOG_EDIT
        yield word[:i] + word[i + 1:], cost
        for c in letters:
            if c != ch.lower():
                yield word[:i] + c + word[i + 1:], cost
    for i in range(len(word) + 1):
        for c in letters:
            yield word[:i] + c + word[i:], LOG_EDIT
    for i in range(len(word) - 1):
        if word[i] != word[i + 1]:
            yield word[:i] + word[i + 1] + word[i] + word[i + 2:], LOG_EDIT


def _confusions(word: str, channel: Channel | None = None) -> Iterable[tuple[str, float]]:
    if channel is not None:
        yield from channel.reads(word)
        return
    for wrong, right in CONFUSIONS:
        start = word.find(wrong)
        while start >= 0:
            yield word[:start] + right + word[start + len(wrong):], LOG_CONFUSION
            start = word.find(wrong, start + 1)


def candidates(word: str, lexicon: Lexicon, channel: Channel | None = None, steps: int = 2) -> dict[str, float]:
    """Words of the lexicon within two OCR edits of ``word``, at most one of them an arbitrary letter edit (the other a
    known confusion or a stray mark), with the channel's log probability; lowercase, case restored by the caller.
    ``channel`` is the recognizer's confusions (``ocr_channel``); None is the hand list. ``steps`` 1 stops after one edit
    (the real-word check, which runs on every word)."""
    w = word.lower()
    key = ("candidates", w, channel.name if channel is not None else "", steps)
    if key in lexicon.cache:
        return lexicon.cache[key]
    found: dict[str, float] = {}

    def keep(cand: str, cost: float) -> None:
        if cand and cand != w and cost > found.get(cand, -math.inf) and re.fullmatch(r"[a-z]+(?:-[a-z]+)?", cand)                 and _wordlike(cand, lexicon):
            found[cand] = cost

    first: dict[str, float] = {}
    for cand, cost in _edits1(w, channel):
        if cost > first.get(cand, -math.inf):
            first[cand] = cost
    for cand, cost in first.items():
        keep(cand, cost)
    for cand, cost in first.items() if steps > 1 else ():
        second = _edits1(cand, channel) if cost > LOG_EDIT else _confusions(cand, channel)
        for cand2, cost2 in second:
            keep(cand2, cost + cost2)
    lexicon.cache[key] = found
    return found


def _wordlike(word: str, lexicon: Lexicon) -> bool:
    return lexicon.in_domain(word) or lexicon.english(word) >= 1e-6 or word in lexicon.terms


def _context(tokens: Sequence[str], i: int, j: int) -> tuple[str, str]:
    prev = core(tokens[i - 1]).lower() if i > 0 else ""
    nxt = core(tokens[j]).lower() if j < len(tokens) else ""
    return (prev if re.fullmatch(r"[a-z]+", prev) else ""), (nxt if re.fullmatch(r"[a-z]+", nxt) else "")


def _score(lexicon: Lexicon, words: list[str], prev: str, nxt: str) -> float:
    s, last = 0.0, prev
    for w in words:
        s += lexicon.logp(w, last)
        last = w
    if nxt:
        s += lexicon.logp(nxt, last) - lexicon.logp(nxt)
    return s


def _posterior(options: dict, head: str, tail: str) -> dict[str, float]:
    top = max(options.values())
    z = sum(math.exp(v - top) for v in options.values())
    return {head + " ".join(k) + tail: math.exp(v - top) / z for k, v in options.items()}


def readings(tokens: Sequence[str], i: int, lexicon: Lexicon, opts: Options = DEFAULT) -> dict[str, float]:
    """The readings the lexicon weighs for a suspect token, as whole tokens (its punctuation kept), with their
    posterior probabilities, the token as read among them; empty when the token is not a suspect or holds a digit."""
    token = tokens[i]
    kind = lexicon.classify(token)
    if not kind.suspect:
        return {}
    head, word, tail = _split_edges(token)
    if not word or re.search(r"\d", word):
        return {}                                              # a number is a person's to read
    prev, nxt = _context(tokens, i, i + 1)
    options: dict[tuple[str, ...], float] = {}
    # The token as read: its own probability (tiny for a non-word).
    options[(word,)] = LOG_KEEP + _score(lexicon, [word.lower()], prev, nxt)
    split = lexicon.segment(word, prev) if re.fullmatch(r"[A-Za-z]+", word) else None
    if split is not None:
        pieces, _ = split
        options[tuple(pieces)] = LOG_CONFUSION / 2 + _score(lexicon, [p.lower() for p in pieces], prev, nxt) + (
            2.0 if re.search(r"[a-z][A-Z]", word) else 0.0)
    if kind is TokenClass.SUSPECT and len(word) >= 2:
        before = tokens[i - 1] if i > 0 else ""
        found = dict(candidates(word, lexicon, opts.channel))
        if opts.search:
            from jason.community.ocr_vocab import search

            for cand, cost in search(word, lexicon, opts.channel or HAND_CHANNEL).items():
                if _wordlike(cand, lexicon) and re.fullmatch(r"[a-z]+(?:-[a-z]+)?", cand):
                    found[cand] = max(found.get(cand, -math.inf), cost)
        for cand, cost in found.items():
            if opts.case_by_context:
                key = (case_for(cand, word, before, lexicon),)
            else:
                key = (_match_case(word, cand),)
            bonus = opts.term_bonus if (cand in lexicon.terms or cand in lexicon.term_forms) else 0.0
            options[key] = max(options.get(key, -math.inf), cost + bonus + _score(lexicon, [cand], prev, nxt))
    return _posterior(options, head, tail)


# A real word read for another: "ot" for "of". The word list knows both, so the English prior never doubts "ot"; the
# noisy channel does: the context makes "of" far likelier, and the recognizer reads "ot" for "of" now and then.

def real_word_readings(tokens: Sequence[str], i: int, lexicon: Lexicon, opts: Options) -> dict[str, float]:
    """The readings of a token that is a word, as whole tokens with their posteriors, the token as read among them:
    the words one channel step away that the context makes likelier. Empty when the token is not a plain word or no
    other word is within reach."""
    token = tokens[i]
    kind = lexicon.classify(token)
    if kind not in (TokenClass.WORD, TokenClass.TERM):
        return {}
    head, word, tail = _split_edges(token)
    if not word or not re.fullmatch(r"[A-Za-z]+", word):
        return {}
    w = word.lower()
    prev, nxt = _context(tokens, i, i + 1)
    base = lexicon.p(w)
    options: dict[tuple[str, ...], float] = {(word,): opts.real_keep + _score(lexicon, [w], prev, nxt)}
    before = tokens[i - 1] if i > 0 else ""
    for cand, cost in candidates(word, lexicon, opts.channel, steps=1).items():
        if not lexicon.is_english(cand) and not lexicon.in_domain(cand):
            continue
        if lexicon.p(cand) < opts.real_ratio * base or cand in ("a", "i"):
            continue
        key = (case_for(cand, word, before, lexicon) if opts.case_by_context else _match_case(word, cand),)
        bonus = opts.term_bonus if (cand in lexicon.terms or cand in lexicon.term_forms) else 0.0
        options[key] = max(options.get(key, -math.inf), cost + bonus + _score(lexicon, [cand], prev, nxt))
    return _posterior(options, head, tail) if len(options) > 1 else {}


def real_word_token(tokens: Sequence[str], i: int, lexicon: Lexicon, opts: Options) -> Suggestion | None:
    """A word the noisy channel reads as another word: the other word's posterior must reach ``opts.real_words``."""
    if opts.real_words <= 0:
        return None
    token = tokens[i]
    found = real_word_readings(tokens, i, lexicon, opts)
    if not found:
        return None
    ranked = sorted(found.items(), key=lambda kv: -kv[1])
    (right, posterior), (_, second) = ranked[0], ranked[1] if len(ranked) > 1 else ("", 0.0)
    if right == token or posterior < opts.real_words:
        return None
    return Suggestion(i, i + 1, token, right, Fix.CHARACTER, (Method.LEXICON,), round(posterior, 3),
                      (f"real word; {posterior:.0%} for the other reading against {1 - posterior:.0%} as read",))


@dataclass(frozen=True)
class Doubt:
    """A token the text rules cannot settle and the page should: where to look, and why."""

    index: int
    why: str                          # "no candidate", "low posterior", "real word"
    posterior: float = 0.0


def doubts(tokens: Sequence[str], lexicon: Lexicon, opts: Options = DEFAULT, *, min_posterior: float = 0.6
           ) -> list[Doubt]:
    """The tokens to send to the page image: a suspect with no candidate reading, or none the context settles, and (with
    ``opts.route_real``) a real word the channel doubts. A suspect the text rules settle is not sent: the vision model
    is asked for guarded readings and for what the rules cannot read."""
    out = []
    for i, token in enumerate(tokens):
        kind = lexicon.classify(token)
        head, word, tail = _split_edges(token)
        if kind.suspect:
            if not word or re.search(r"\d", word) or not re.search(r"[A-Za-z]", word):
                continue                                          # a mark or a number: the guard's business
            found = readings(tokens, i, lexicon, opts)
            ranked = sorted(found.items(), key=lambda kv: -kv[1])
            if len(ranked) < 2:
                out.append(Doubt(i, "no candidate"))
            elif ranked[0][0] == token or ranked[0][1] < min_posterior:
                out.append(Doubt(i, "low posterior", ranked[0][1]))
        elif opts.route_real > 0:
            found = real_word_readings(tokens, i, lexicon, opts)
            ranked = sorted(found.items(), key=lambda kv: -kv[1])
            if ranked and ranked[0][0] != token and ranked[0][1] >= opts.route_real:
                out.append(Doubt(i, "real word", ranked[0][1]))
    return out


def correct_token(tokens: Sequence[str], i: int, lexicon: Lexicon, *, min_posterior: float = 0.6,
                  opts: Options = DEFAULT) -> Suggestion | None:
    """The lexicon's reading of a suspect token: a split into words, or the likeliest word a few OCR edits away, if
    it beats the token as read; None when the token is not a suspect or nothing beats it. With ``opts.real_words`` a
    real word is read as another the context makes likelier."""
    token = tokens[i]
    if not lexicon.classify(token).suspect:
        return real_word_token(tokens, i, lexicon, opts)
    found = readings(tokens, i, lexicon, opts)
    if len(found) < 2:
        return None
    ranked = sorted(found.items(), key=lambda kv: -kv[1])
    (right, posterior), (_, second) = ranked[0], ranked[1]
    if right == token or posterior < min_posterior:
        return None
    fix = Fix.SPLIT if right.replace(" ", "") == token else Fix.CHARACTER
    kind = lexicon.classify(token)
    return Suggestion(i, i + 1, token, right, fix, (Method.LEXICON,), round(posterior, 3),
                      (f"{kind.value}; {posterior:.0%} against {second:.0%} for the next reading",))


# Layout: what the page's arrangement does to the words.

# Marks standing alone that are no punctuation of running text: a rule read as "|", specks read as ":" or "..".
# A comma standing alone is usually the text's own, spaced off its word; an ellipsis ("...") and a bullet are text.
_STRAY = re.compile(r"^(?:[|~»«_=¦\\!\[\]{}©®:;°`^*]+|\.\.)$")
_BAR_EDGE = re.compile(r"^\|+(?=\w)|(?<=[\w.,;:)])\|+$")
_FOLIO = re.compile(r"^[-~]\s*\d{1,3}\s*[-~]$")
_LABEL_BRACKET = re.compile(r"^[{\[]([a-z]{1,4}|[0-9]{1,2})[)}\]]([.,;:]?)$|^\(([a-z]{1,4}|[0-9]{1,2})[}\]]([.,;:]?)$")
_ROMAN = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv")


def _next_label(label: str) -> list[str]:
    """The labels that may follow ``label`` in its series: (a) -> (b), (iv) -> (v), (3) -> (4); (i) may begin a
    roman series or follow (h)."""
    inner = label.strip("()")
    out = []
    if inner.isdigit():
        out.append(f"({int(inner) + 1})")
    if inner in _ROMAN and _ROMAN.index(inner) + 1 < len(_ROMAN):
        out.append(f"({_ROMAN[_ROMAN.index(inner) + 1]})")
    if len(inner) == 1 and inner.isalpha() and inner < "z":
        out.append(f"({chr(ord(inner) + 1)})")
    return out


def layout_suggestions(tokens: Sequence[str], lexicon: Lexicon, *, tables: bool = False) -> list[Suggestion]:
    """Line-end hyphens, stray marks, page numbers, undecodable quotes, and label brackets. ``tables``: the text is a
    vision model's transcription, which writes a table's cells between bars and its bullets and checkboxes as marks,
    so no mark is called stray."""
    out: list[Suggestion] = []
    n = len(tokens)
    i = 0
    last_label = ""
    while i < n:
        t = tokens[i]
        # A page number in the running text: "- 12 -", "-12-", "~ 12 -".
        if i + 2 < n and tokens[i] in ("-", "~") and re.fullmatch(r"\d{1,3}", tokens[i + 1]) and tokens[i + 2] in ("-", "~"):
            out.append(Suggestion(i, i + 3, " ".join(tokens[i:i + 3]), "", Fix.FOLIO, (Method.LAYOUT,), 0.8,
                                  ("a page number between dashes, as a page's foot prints it",)))
            i += 3
            continue
        if _FOLIO.match(t):
            out.append(Suggestion(i, i + 1, t, "", Fix.FOLIO, (Method.LAYOUT,), 0.8,
                                  ("a page number between dashes, as a page's foot prints it",)))
            i += 1
            continue
        # A stray mark: a rule read as "|", a speck.
        if not tables and _STRAY.match(t) and not re.search(r"[A-Za-z0-9]", t):
            out.append(Suggestion(i, i + 1, t, "", Fix.STRAY, (Method.LAYOUT,), 0.9,
                                  ("a mark that is no word or punctuation of the text",)))
            i += 1
            continue
        if not tables and _BAR_EDGE.search(t) and re.search(r"[A-Za-z]", t):
            out.append(Suggestion(i, i + 1, t, _BAR_EDGE.sub("", t), Fix.STRAY, (Method.LAYOUT,), 0.9,
                                  ("a rule read as a bar against a word",)))
            i += 1
            continue
        # A word broken at a line's end: "assess- ment" -> "assessment"; "non- payment" -> "non-payment".
        if i + 1 < n and re.fullmatch(r"[A-Za-z]{2,}-", t) and re.fullmatch(r"[a-z]{2,}[^\w\s]*", tokens[i + 1]):
            left = t[:-1]
            h, right_word, tail = _split_edges(tokens[i + 1])
            joined = left + right_word
            if _wordlike(joined.lower(), lexicon) and not lexicon.in_domain(right_word):
                out.append(Suggestion(i, i + 2, f"{t} {tokens[i + 1]}", joined + tail, Fix.JOIN, (Method.LAYOUT,), 0.85,
                                      ("a word broken at a line's end",)))
                i += 2
                continue
            if lexicon.in_domain(f"{left}-{right_word}".lower()) or (
                    lexicon.in_domain(left) and lexicon.in_domain(right_word) and left.lower() in ("non", "co", "pre", "re", "sub", "self")):
                out.append(Suggestion(i, i + 2, f"{t} {tokens[i + 1]}", f"{left}-{right_word}{tail}", Fix.JOIN,
                                      (Method.LAYOUT,), 0.7, ("a hyphenated word broken at a line's end",)))
                i += 2
                continue
        # A curly quote OCR could not encode, read as U+FFFD.
        if "�" in t:
            fixed = re.sub(r"(?<=[\w.,;:)])�+$", '"', t)
            fixed = re.sub(r"^�(?=[A-Z])", '"', fixed)
            if fixed != t and "�" not in fixed:
                out.append(Suggestion(i, i + 1, t, fixed, Fix.PUNCTUATION, (Method.LAYOUT,), 0.85,
                                      ("a quotation mark the OCR could not encode",)))
                i += 1
                continue
        # A label's bracket misread: "{c)" -> "(c)".
        m = _LABEL_BRACKET.match(t)
        if m:
            inner = m.group(1) or m.group(3)
            punct = m.group(2) or m.group(4) or ""
            out.append(Suggestion(i, i + 1, t, f"({inner}){punct}", Fix.LABEL, (Method.LAYOUT,), 0.85,
                                  ("a section label's bracket misread",)))
            last_label = f"({inner})"
            i += 1
            continue
        # A label misread in its letters: "(il)" after "(i)" is "(ii)".
        if re.fullmatch(r"\([a-z0-9]{1,4}\)[.,;:]?", t):
            label = t[: t.index(")") + 1]
            if label.strip("()") not in _ROMAN and not re.fullmatch(r"\([a-z]\)|\(\d{1,2}\)", label) and last_label:
                expected = _next_label(last_label)
                guess = label.replace("l", "i").replace("1", "i").replace("I", "i")
                if guess in expected:
                    out.append(Suggestion(i, i + 1, t, guess + t[len(label):], Fix.LABEL, (Method.LAYOUT,), 0.8,
                                          (f"the label after {last_label}",)))
                    last_label = guess
                    i += 1
                    continue
            last_label = label
        # A word split in two ("A gency", "Develop ment"): one half is no word, and together they are one.
        if i + 1 < n and re.fullmatch(r"[A-Za-z]+", t) and re.fullmatch(r"[a-z]+[^\w\s]*", tokens[i + 1]):
            h, nxt, tail = _split_edges(tokens[i + 1])
            joined = t + nxt
            halves_bad = lexicon.suspect(t) or lexicon.suspect(nxt) or (len(t) == 1 and t not in ("a", "A", "I"))
            if (halves_bad and not h and len(joined) >= 4 and joined.lower() not in _ROMAN
                    and lexicon.in_domain(joined.lower()) and lexicon.count(joined.lower()) >= 5):
                out.append(Suggestion(i, i + 2, f"{t} {tokens[i + 1]}", joined + tail, Fix.JOIN, (Method.LAYOUT,), 0.8,
                                      ("a word read in two pieces",)))
                i += 2
                continue
        # A word and its punctuation run together: "Assessments,which" -> "Assessments, which"; "two(2)" -> "two (2)".
        m = re.fullmatch(r"([A-Za-z]{2,})([,;:])([A-Za-z]{2,})([.,;:)\"']*)", t)
        if m and _wordlike(m.group(1).lower(), lexicon) and _wordlike(m.group(3).lower(), lexicon):
            out.append(Suggestion(i, i + 1, t, f"{m.group(1)}{m.group(2)} {m.group(3)}{m.group(4)}", Fix.PUNCTUATION,
                                  (Method.LAYOUT,), 0.85, ("a mark with no space after it",)))
            i += 1
            continue
        m = re.fullmatch(r"([A-Za-z]{2,})(\((?:\d{1,3}|[a-z]{1,4})\)[^\w\s]*)", t)
        inner = m.group(2)[1:m.group(2).index(")")] if m else ""
        if m and lexicon.known(m.group(1)) and (inner.isdigit() or len(inner) == 1 and inner != "s" or inner in _ROMAN):
            out.append(Suggestion(i, i + 1, t, f"{m.group(1)} {m.group(2)}", Fix.PUNCTUATION, (Method.LAYOUT,), 0.8,
                                  ("a numeral or label in brackets run into its word",)))
            i += 1
            continue
        i += 1
    return out


def lexicon_suggestions(tokens: Sequence[str], lexicon: Lexicon, *, min_posterior: float = 0.6,
                        opts: Options = DEFAULT) -> list[Suggestion]:
    out = []
    for i in range(len(tokens)):
        s = correct_token(tokens, i, lexicon, min_posterior=min_posterior, opts=opts)
        if s is not None:
            out.append(s)
    return out


def suggest(tokens: Sequence[str], lexicon: Lexicon, *, language_check: bool = True, tables: bool = False,
            opts: Options = DEFAULT) -> list[Suggestion]:
    """The text rules' suggestions for a passage's tokens: layout first, then the lexicon on the tokens layout left.
    A passage that is not in English gets none (``lexicon.language_of``)."""
    from jason.community.lexicon import language_of

    if language_check and len(tokens) >= 8 and language_of(" ".join(tokens), lexicon).language not in ("en", ""):
        return []
    found = layout_suggestions(tokens, lexicon, tables=tables)
    taken = {k for s in found for k in range(s.start, s.end)}
    for s in lexicon_suggestions(tokens, lexicon, opts=opts):
        if s.start not in taken:
            found.append(s)
    return sorted(found, key=lambda s: s.start)


def apply(tokens: Sequence[str], suggestions: Iterable[Suggestion]) -> list[str]:
    """The tokens with the suggestions taken (non-overlapping; the first by position wins). For measuring and for a
    reading copy, never for the record."""
    out = list(tokens)
    chosen, end = [], -1
    for s in sorted(suggestions, key=lambda s: (s.start, -s.end)):
        if s.start >= end:
            chosen.append(s)
            end = s.end
    for s in reversed(chosen):
        out[s.start:s.end] = s.right.split()
    return out


# Agreement: several readers, one span.

def combine(*groups: Iterable[Suggestion]) -> list[Suggestion]:
    """Suggestions from several methods merged by span: the same span and the same reading become one suggestion with
    every method that read it; the same span read differently keeps each reading (a conflict, ``tier``)."""
    merged: dict[tuple[int, int, str], Suggestion] = {}
    for group in groups:
        for s in group:
            key = (s.start, s.end, _canon(s.right))
            if key in merged:
                m = merged[key]
                methods = tuple(dict.fromkeys(m.methods + s.methods))
                merged[key] = replace(m, methods=methods, confidence=max(m.confidence, s.confidence),
                                      evidence=tuple(dict.fromkeys(m.evidence + s.evidence)))
            else:
                merged[key] = s
    return sorted(merged.values(), key=lambda s: (s.start, s.end))


def _canon(text: str) -> str:
    return " ".join(text.translate(str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})).split())


def tier(s: Suggestion, rivals: Sequence[Suggestion] = ()) -> Tier:
    """How sure the suggestion is, for the intake queue. ``rivals`` are other readings of the same span."""
    if any(r.right != s.right and (r.start, r.end) == (s.start, s.end) for r in rivals):
        return Tier.CONFLICT
    if len(s.families) < 2:
        return Tier.SUGGESTED
    if not s.guard:
        return Tier.LIKELY
    # A number or an operative word: only the page itself, read by a person or by the vision model with a second.
    return Tier.LIKELY if Method.PERSON in s.methods or Method.VISION in s.methods else Tier.SUGGESTED


__all__ = ["CONFUSIONS", "DEFAULT", "Doubt", "Fix", "HAND_CHANNEL", "Method", "Options", "Suggestion", "Tier", "apply",
           "candidates", "case_for", "combine", "correct_token", "doubts", "readings", "real_word_readings", "guard",
           "layout_suggestions", "lexicon_suggestions", "suggest", "tier"]
