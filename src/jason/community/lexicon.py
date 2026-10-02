"""What a word of a recorded instrument may be, and a language model of clean legal text, for reading OCR.

A recorded instrument in California is in English: the recorder may not accept one written in whole or in part in
another language without a certified translation (Gov. Code 27293). So every token of the declaration, an amendment,
an annexation, a deed, or a lien should be one of a few things, and anything else is an OCR suspect:

- an English word (``english``: a general word list, when ``wordfreq`` is installed, and the clean legal corpus);
- a number, date, amount, or citation ("4.15(a)", "$174", "20070920");
- a section label ("(iv)", "(b)");
- a defined term or a proper noun the document itself uses (``document_terms``: its quoted defined terms and the
  capitalized words it repeats);
- a legal term of art in Latin or French (``TERMS_OF_ART``: "et seq.", "pro rata", "lis pendens").

The prior is a hard rule only for recorded instruments; an unrecorded rule or policy is English in practice, and a
translated notice is not. ``language_of`` names a passage's language first, so a passage in another language is never
"corrected" into English, and its share of non-English tokens is a signal of the OCR's quality.

The language model (``Lexicon``) counts the words and word pairs of clean text: the statutes on disk and the governing
documents a person keeps as Docs, never the OCR being corrected, and never the document's own hand-kept copy when that
copy is a second method of reading it. ``jason.community.ocr_correct`` uses it to split run-together words and to rank
the readings of a misread one.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import Callable, Iterable

# Legal terms of art in Latin and law French: English law's own vocabulary, not a foreign language.
TERMS_OF_ART = frozenset("""
ab ad affidavit al alia amicus ante bona capita certiorari contendere curiae de diem duces e.g. et etc ex facie facto
fide habendum i.e. in infra initio inter judicata lis mandamus minimis mutandis mutatis nolo novo nunc officio pari
parte passu pendens per personam post prima pro quasi quo quorum rata rem res se seq sic sponte stirpes sua subpoena
supra tecum tem tunc ultra versus vires viz vs annum
""".split())

# A number, an amount, a date, a citation: "4.15(a)", "$1,250.00", "1/12th", "20070920", "1367.4(d)(4)".
_NUMBER = re.compile(r"^[($§#]*\d[\d.,/:\-]*(?:\([0-9a-z]{1,4}\))*(?:st|nd|rd|th|%)?[).,;:]*$", re.I)
# A section label on its own: "(a)", "(iv)", "a.", "B."
_LABEL = re.compile(r"^\(?(?:[a-z]{1,2}|[ivxlc]{1,6}|\d{1,3})\)[.,;:]?$|^[A-Z]\.$", re.I)
# A prefix that is not split from its word ("nonexclusive" is not "non exclusive").
BOUND_PREFIXES = frozenset({"non", "un", "re", "pre", "co", "sub", "anti", "semi", "multi", "inter", "intra"})
_LETTERS = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)*")
_WORDS = re.compile(r"[^\W\d_]+")                       # letters in any script, for naming a passage's language
_EDGE = re.compile(r"^[^\w]+|[^\w]+$")
# An abbreviation: "FHLMC", "U.S.", "A.C.A.", "LLC".
_ABBREVIATION = re.compile(r"^(?:[A-Z]{2,6}s?|(?:[A-Z]\.){2,5}[A-Z]?\.?)$")


class TokenClass(Enum):
    WORD = "word"                  # an English word: the domain corpus or the general list
    NUMBER = "number"              # a number, amount, date, or citation
    LABEL = "label"                # a section label
    TERM = "term"                  # a defined term or proper noun the document itself uses
    TERM_OF_ART = "term of art"    # Latin or law French
    ABBREVIATION = "abbreviation"  # "FHLMC", "U.S.", "LLC"
    MARK = "mark"                  # punctuation only ("-", "&", "§")
    RUN_TOGETHER = "run together"  # a string general English lists (web text has "ofthe") that splits into likelier words
    SUSPECT = "suspect"            # none of these: an OCR suspect

    @property
    def suspect(self) -> bool:
        return self in (TokenClass.SUSPECT, TokenClass.RUN_TOGETHER)


def core(token: str) -> str:
    """A token without its leading and trailing punctuation ("(Owner's," -> "Owner's")."""
    return _EDGE.sub("", token)


@lru_cache(maxsize=None)
def _frequencies(lang: str) -> dict[str, float]:
    try:
        from wordfreq import get_frequency_dict
    except ImportError:
        return {}
    return get_frequency_dict(lang)


def _wordfreq(word: str, lang: str = "en") -> float:
    """A word's frequency per word of running text in ``lang`` (wordfreq), 0 when unknown or not installed."""
    return _frequencies(lang).get(word, 0.0)


def wordfreq_available() -> bool:
    try:
        import wordfreq  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass
class Lexicon:
    """Word and word-pair counts of clean text, with a general English list behind them.

    ``english(word)`` is a word's frequency in general English (``wordfreq`` by default; a test passes its own).
    ``terms`` are the document's own defined terms and proper nouns, lowercased."""

    unigrams: Counter = field(default_factory=Counter)
    bigrams: Counter = field(default_factory=Counter)
    terms: frozenset = frozenset()
    english: Callable[[str], float] = _wordfreq
    min_count: int = 2               # a word seen this often in the clean corpus is a word
    english_floor: float = 1e-7      # a word this frequent in general English is a word (zipf 2)
    total: int = 0
    smoothing: float = 500.0         # how far a word pair's count is trusted over the word's own probability
    cache: dict = field(default_factory=dict, repr=False, compare=False)   # candidates already worked out, by word

    @classmethod
    def from_texts(cls, texts: Iterable[str], **kw) -> "Lexicon":
        lex = cls(**kw)
        for text in texts:
            lex.add(text)
        return lex

    def add(self, text: str) -> None:
        words = [w.lower() for w in _LETTERS.findall(text)]
        self.unigrams.update(words)
        self.bigrams.update(zip(words, words[1:]))
        self.total += len(words)

    def with_terms(self, terms: Iterable[str]) -> "Lexicon":
        from dataclasses import replace

        return replace(self, terms=frozenset(t.lower() for t in terms), cache={})

    # What a token is.

    def count(self, word: str) -> int:
        return self.unigrams.get(word.lower(), 0)

    def in_domain(self, word: str) -> bool:
        return self.count(word) >= self.min_count

    def is_english(self, word: str) -> bool:
        return self.english(word.lower()) >= self.english_floor

    def known(self, word: str) -> bool:
        w = word.lower()
        return self.in_domain(w) or self.is_english(w) or w in self.terms or w in TERMS_OF_ART

    def classify(self, token: str) -> TokenClass:
        if re.search(r"\((?:e?s)\)", token, re.I):           # "(s)he", "tenant(s)", "NAME(S)"
            token = re.sub(r"\((?:e?s)\)", "", token, flags=re.I) or token
        c = core(token)
        if not c:
            return TokenClass.MARK if re.fullmatch(r"[-&§—–/.,;:()\"'$%*]+", token) else TokenClass.SUSPECT
        if _NUMBER.match(token) or _NUMBER.match(c):
            return TokenClass.NUMBER
        if _LABEL.match(token):
            return TokenClass.LABEL
        if c.lower() in TERMS_OF_ART or token.lower() in TERMS_OF_ART:
            return TokenClass.TERM_OF_ART
        if _ABBREVIATION.match(c) or _ABBREVIATION.match(token.strip(",;:()")):
            return TokenClass.ABBREVIATION
        if re.search(r"\d", c) and re.fullmatch(r"[A-Za-z0-9-]+", c) and re.search(r"[A-Z0-9]-?\d", c):
            return TokenClass.NUMBER                  # a code or permit number ("P05-164")
        c = re.sub(r"(?:['’]s|\(s\)?|s['’])$", "", c, flags=re.I)   # "Declarant's", "tenant(s)", "Owners'"
        parts = re.split(r"[-/]", c)              # "non-payment", "and/or"
        if not (all(parts) and all(_LETTERS.fullmatch(p) for p in parts)):
            return TokenClass.SUSPECT
        if all(self.in_domain(p) for p in parts):
            return TokenClass.WORD
        if all(self.in_domain(p) or self.is_english(p) for p in parts):
            if len(parts) == 1 and self.run_together(c):
                return TokenClass.RUN_TOGETHER
            return TokenClass.WORD
        if all(self.known(p) for p in parts):
            return TokenClass.TERM
        if len(parts) == 1 and re.fullmatch(r"[A-Za-z]{3,}s", c) and self.known(c[:-1]):
            return TokenClass.WORD                # a plural no list has ("insureds")
        return TokenClass.SUSPECT

    def suspect(self, token: str) -> bool:
        return self.classify(token).suspect

    # Run-together words.

    def splittable(self, piece: str) -> bool:
        """Whether a piece may stand alone in a split: a word of the corpus or a common English word; of single
        letters, only "a"."""
        w = piece.lower()
        if len(w) == 1:
            return w == "a"
        return self.in_domain(w) or self.english(w) >= 1e-5 or w in self.terms

    def segment(self, word: str, prev: str = "", *, max_pieces: int = 4) -> tuple[list[str], float] | None:
        """The likeliest split of ``word`` into two or more words (Viterbi over the language model, the original
        letters and case kept), with its log probability; None when no split is all words."""
        n = len(word)
        if n < 3 or not _LETTERS.fullmatch(word):
            return None
        # best[i]: {pieces so far: (score, pieces)} keyed by the last piece, a small beam.
        best: list[dict[str, tuple[float, list[str]]]] = [dict() for _ in range(n + 1)]
        best[0][prev.lower()] = (0.0, [])
        for i in range(n):
            for last, (score, pieces) in best[i].items():
                if len(pieces) >= max_pieces:
                    continue
                for j in range(i + 1, min(n, i + 24) + 1):
                    piece = word[i:j]
                    if not self.splittable(piece) or (i == 0 and j < n and piece.lower() in BOUND_PREFIXES):
                        continue
                    s = score + self.logp(piece, last)
                    # A capital inside a run of letters ("ofCalifornia") marks a word's start.
                    if i > 0 and piece[0].isupper() and word[i - 1].islower():
                        s += 2.0
                    key = piece.lower()
                    if key not in best[j] or best[j][key][0] < s:
                        best[j][key] = (s, pieces + [piece])
            # keep the beam small
            if len(best[i + 1]) > 8:
                best[i + 1] = dict(sorted(best[i + 1].items(), key=lambda kv: -kv[1][0])[:8])
        found = [v for v in best[n].values() if len(v[1]) >= 2]
        if not found:
            return None
        score, pieces = max(found, key=lambda v: v[0])
        return pieces, score

    def run_together(self, word: str, *, margin: float = 4.0) -> list[str] | None:
        """The split of a string general English lists only as web noise ("ofthe"), when the split is far likelier
        than the string as one word; None for a word of the corpus ("therein" stays one word)."""
        if self.in_domain(word):
            return None
        found = self.segment(word)
        if found is None:
            return None
        pieces, score = found
        return pieces if score - self.logp(word) > margin else None

    # The language model.

    def p(self, word: str) -> float:
        """A word's probability: the clean corpus mixed with general English, floored for the unknown."""
        w = word.lower()
        dom = self.unigrams.get(w, 0) / self.total if self.total else 0.0
        return 0.6 * dom + 0.4 * self.english(w) + 1e-9

    def logp(self, word: str, prev: str = "") -> float:
        """log P(word | prev): the corpus's pairs smoothed toward the word's own probability (Dirichlet)."""
        uni = self.p(word)
        if not prev:
            return math.log(uni)
        pv = prev.lower()
        n = self.unigrams.get(pv, 0)
        a = self.smoothing
        return math.log((self.bigrams.get((pv, word.lower()), 0) + a * uni) / (n + a))


def document_terms(text: str, lexicon: Lexicon, *, repeats: int = 3) -> set[str]:
    """The document's own words that no word list has: its quoted defined terms ('"Common Area" shall mean') and the
    capitalized words it repeats (a name, a street), lowercased. A repeated capitalized word that splits into known
    words ("CommonArea") is an OCR slip, not a term."""
    def slip(word: str) -> bool:
        if re.search(r"[a-z][A-Z]", word) or lexicon.known(word):
            return True                                   # run together ("ofDirectors"), or a word already
        found = lexicon.segment(word)
        return found is not None and found[0] and len(found[0]) >= 2 and found[1] > -14.0

    out: set[str] = set()
    for quoted in re.findall(r"[\"“]([A-Z][A-Za-z' -]{1,60})[\"”]", text):
        out.update(w.lower() for w in _LETTERS.findall(quoted) if not slip(w))
    caps = Counter(c for c in (core(t) for t in text.split()) if re.fullmatch(r"[A-Z][a-z]+|[A-Z]{2,}", c))
    for word, n in caps.items():
        if n >= repeats and not slip(word):
            out.add(word.lower())
    return out


# Language identification, by the share of a passage's words each language's list knows.

LANGUAGES = ("en", "es", "vi", "fil", "zh", "ko", "ru", "fr", "pt", "de", "it")


def _script(text: str) -> str:
    """The writing system most of the letters are in: "latin", "han", "hangul", "cyrillic", "arabic", or ""."""
    counts: Counter = Counter()
    for ch in text:
        o = ord(ch)
        if ch.isalpha():
            counts["latin" if o < 0x250 or 0x1E00 <= o <= 0x1EFF else "han" if 0x4E00 <= o <= 0x9FFF or 0x3040 <= o <= 0x30FF else
                   "hangul" if 0xAC00 <= o <= 0xD7AF else "cyrillic" if 0x400 <= o <= 0x4FF else
                   "arabic" if 0x600 <= o <= 0x6FF else "other"] += 1
    return counts.most_common(1)[0][0] if counts else ""


@dataclass(frozen=True)
class LanguageReading:
    language: str          # an ISO 639 code ("en", "es"), or "" when undecided
    english_share: float   # the share of the passage's words general English or the corpus knows
    best_share: float      # the share the named language's list knows
    words: int

    @property
    def english(self) -> bool:
        return self.language == "en"


def language_of(text: str, lexicon: Lexicon | None = None, *, floor: float = 1e-6) -> LanguageReading:
    """The passage's language: the one whose word list knows the largest share of its words (Latin script), or its
    script's language. English counts the corpus and the terms of art too. Undecided ("") for fewer than five words."""
    script = _script(text)
    words = [w.lower() for w in _WORDS.findall(text)]
    if script and script not in ("latin", "other"):
        lang = {"han": "zh", "hangul": "ko", "cyrillic": "ru", "arabic": "ar"}[script]
        return LanguageReading(lang, 0.0, 1.0, len(words))
    if len(words) < 5:
        return LanguageReading("", 0.0, 0.0, len(words))

    def share(lang: str) -> float:
        if lang == "en" and lexicon is not None:
            return sum(lexicon.known(w) for w in words) / len(words)
        return sum(_wordfreq(w, lang) >= floor or (lang == "en" and w in TERMS_OF_ART) for w in words) / len(words)

    shares = {lang: share(lang) for lang in LANGUAGES if lang not in ("zh", "ko", "ru")}
    en = shares["en"]
    best = max(shares, key=lambda k: (shares[k], k == "en"))
    # Short function words are shared across languages; another language wins only by a clear margin, and only over
    # a passage most of whose words are not English (OCR noise lowers the English share, not another's).
    if best != "en" and (shares[best] - en < 0.15 or en >= 0.5):
        best = "en"
    return LanguageReading(best, en, shares[best], len(words))


__all__ = ["LANGUAGES", "LanguageReading", "Lexicon", "TERMS_OF_ART", "TokenClass", "core", "document_terms",
           "language_of", "wordfreq_available"]
