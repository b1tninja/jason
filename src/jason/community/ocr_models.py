"""Local models as readers of OCR'd words: a text model shown the passage, and a vision model shown the word's crop.

Both return ``ocr_correct.Suggestion`` rows, so their readings meet the lexicon's and the working copy's in
``ocr_correct.combine``. A model's reading is evidence, never an edit, and each is held to the same guard.

- **Explicit expectations** (``EXPECTATIONS_PROMPT``): the model is told what the text is (the OCR of a recorded
  governing document, legal drafting), what to fix (only OCR's errors), what never to do (change meaning, numbers,
  capitalized defined terms, operative words; modernize, paraphrase, improve; add or drop words), with made-up
  examples of each error, and answers with JSON corrections that each state a kind, a reason, and a confidence.
- **Marked suspects** (``MARKED_PROMPT``): the lexicon marks the tokens it doubts, and the model answers only for
  those, so it cannot wander into the rest of the passage.
- **The word's crop** (``VisionWordReader``): Tesseract's word boxes locate the token on the page image, and the
  vision model reads only that crop, with the line around it for context.

Every request goes through ``ollama_extractor._post``, which holds jason's GPU lock; callers run
``local_ai.preflight`` first and release the model when done (``keep_alive: 0``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Sequence

from jason.community.ocr_channel import _edit_distance
from jason.community.ocr_correct import Fix, Method, Suggestion

DEFAULT_TEXT_MODEL = "qwen3.5:9b"

EXPECTATIONS_PROMPT = """You are proofreading the OCR (optical character recognition) of a recorded California \
governing document: a declaration of covenants, conditions, and restrictions, its amendments, or the like. It is \
legal drafting, recorded in English. The OCR engine read a clean typed page and made a few kinds of mistakes. Your \
job is to find only those mistakes and say what the printed page said.

Fix only OCR errors:
- run-together words: "theOwnerofthe Lot" -> "the Owner of the Lot"
- a word broken in two: "A greement" -> "Agreement"
- misread letters that make a non-word: "faiiure" -> "failure", "pcrmitted" -> "permitted", "tenns" -> "terms"
- misidentified punctuation or brackets: "Section 3.2{b)" -> "Section 3.2(b)", "Owner;s" -> "Owner's"
- a broken section label: "5. I 2(c)" -> "5.12(c)"
- stray marks that are not text: a lone "|" or "~" from a ruled line or a speck -> remove

Never:
- change a word that is a real, correctly spelled word, even if you think the drafter meant another; never turn \
"shall" into "may", "or" into "and", "any" into "all", "not" into "now", or the reverse
- change a number, an amount, a date, or a section number, unless it is a broken section label as above
- change the capitalization of a defined term ("Common Area", "Owner", "Board")
- modernize, paraphrase, or "improve" the drafting; fix the drafter's own grammar ("it's" stays "it's"); expand an \
abbreviation
- add words that are not on the page, or drop words that are

Answer in JSON: {"corrections": [{"original": ..., "corrected": ..., "kind": ..., "reason": ..., "confidence": ...}]}.
- "original" is copied exactly from the passage, one or a few whole whitespace-separated tokens
- "corrected" is what the page says in their place ("" to remove a stray mark)
- "kind" is one of: split, join, character, punctuation, label, stray, other
- "confidence" is your probability, 0 to 1, that the page says "corrected"
- leave everything else in the passage alone; an empty list is a good answer for a clean passage"""

MARKED_PROMPT = """This is OCR of a recorded California governing document (legal drafting, in English). Some tokens \
are marked like [[3:tokan]]: the number, then the token as the OCR read it. For each marked token, give what the \
printed page most likely says. Fix only OCR errors: run-together words ("ofthe" -> "of the"), misread letters \
("faiiure" -> "failure"), misread brackets or punctuation ("{b)" -> "(b)"), stray marks (a lone "|" -> ""). If a \
marked token is a real word, a name, a number, or an abbreviation that is already right, return it unchanged. \
Never change a number, never change one real word into another, never add or drop words. Answer in JSON: \
{"readings": [{"n": 3, "text": "token"}]}, one entry for every marked token."""

CHOOSE_PROMPT = """This is OCR of a recorded California governing document (legal drafting, in English). One token \
is marked like [[tokan]]. Choose which reading the printed page most likely had. Choose the token as read if it is \
a real word, name, number, or abbreviation; never prefer a reading only because it reads better."""

CORRECTIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"corrections": {"type": "array", "items": {
        "type": "object",
        "properties": {"original": {"type": "string"}, "corrected": {"type": "string"},
                       "kind": {"type": "string", "enum": [f.value for f in Fix]},
                       "reason": {"type": "string"}, "confidence": {"type": "number"}},
        "required": ["original", "corrected", "kind", "reason", "confidence"]}}},
    "required": ["corrections"],
}

READINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"readings": {"type": "array", "items": {
        "type": "object", "properties": {"n": {"type": "integer"}, "text": {"type": "string"}},
        "required": ["n", "text"]}}},
    "required": ["readings"],
}


def letter_weights(answer: dict, letters: str) -> dict[str, float]:
    """The probability of each letter as the one-token answer's first token, read from Ollama's ``top_logprobs`` (a
    request with ``logprobs`` and ``top_logprobs``), normalized over ``letters``; all equal when none is returned."""
    import math

    weights = {c: 0.0 for c in letters}
    for row in (answer.get("logprobs") or [{}])[0].get("top_logprobs") or []:
        c = str(row.get("token") or "").strip()
        if c in weights:
            weights[c] += math.exp(float(row.get("logprob") or -100))
    total = sum(weights.values())
    return {c: (w / total if total else 1.0 / len(letters)) for c, w in weights.items()}


def marked_passage(tokens: Sequence[str], suspects: Sequence[int]) -> str:
    marks = set(suspects)
    return " ".join(f"[[{k}:{t}]]" if k in marks else t for k, t in enumerate(tokens))


def _find(tokens: Sequence[str], words: list[str], used: set[int]) -> int:
    """The first place ``words`` occur in ``tokens`` whose start is not ``used``; -1 when nowhere."""
    n = len(words)
    for k in range(len(tokens) - n + 1):
        if k not in used and list(tokens[k:k + n]) == words:
            return k
    return -1


def parse_corrections(answer: str, tokens: Sequence[str], *, method: Method = Method.LOCAL_MODEL
                      ) -> tuple[list[Suggestion], list[dict]]:
    """The model's corrections as suggestions on the passage's tokens, and the ones that name no tokens of the
    passage (unlocatable: the model quoted words that are not there)."""
    try:
        rows = json.loads(answer).get("corrections") or []
    except (ValueError, AttributeError):
        return [], [{"error": "not JSON", "answer": answer[:200]}]
    out, lost, used = [], [], set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        original, corrected = str(r.get("original") or "").strip(), str(r.get("corrected") or "").strip()
        words = original.split()
        if not words or original == corrected:
            continue
        k = _find(tokens, words, used)
        if k < 0:
            lost.append(r)
            continue
        used.add(k)
        # The model quotes context around the change ("amount ofthree" -> "amount of three"): keep only the change.
        fixed = corrected.split()
        while len(words) > 1 and fixed and words[0] == fixed[0]:
            words, fixed, k = words[1:], fixed[1:], k + 1
        while len(words) > 1 and fixed and words[-1] == fixed[-1]:
            words, fixed = words[:-1], fixed[:-1]
        corrected = " ".join(fixed)
        try:
            fix = Fix(str(r.get("kind") or "other"))
        except ValueError:
            fix = Fix.OTHER
        try:
            conf = max(0.0, min(1.0, float(r.get("confidence") or 0)))
        except (TypeError, ValueError):
            conf = 0.0
        out.append(Suggestion(k, k + len(words), " ".join(words), corrected, fix, (method,), conf,
                              (f"{method.value}: {str(r.get('reason') or '')[:160]}",)))
    return out, lost


def parse_readings(answer: str, tokens: Sequence[str], suspects: Sequence[int]) -> list[Suggestion]:
    """The model's readings of the marked tokens, as suggestions where they differ from the OCR."""
    try:
        rows = json.loads(answer).get("readings") or []
    except (ValueError, AttributeError):
        return []
    marks = set(suspects)
    out = []
    for r in rows:
        try:
            k = int(r.get("n"))
        except (TypeError, ValueError, AttributeError):
            continue
        text = str(r.get("text") if r.get("text") is not None else "").strip()
        if k not in marks or text == tokens[k]:
            continue
        fix = Fix.SPLIT if text.replace(" ", "") == tokens[k] else Fix.STRAY if not text else Fix.CHARACTER
        out.append(Suggestion(k, k + 1, tokens[k], text, fix, (Method.LOCAL_MODEL,), 0.5, ("local model, marked",)))
    return out


def minimal(s: Suggestion) -> bool:
    """Whether a model's edit is small: spacing alone, a stray mark, or few letters changed for the word's length."""
    import difflib

    if s.wrong.replace(" ", "") == s.right.replace(" ", ""):
        return True
    if not s.right:
        return not re.search(r"[A-Za-z]{2,}|\d", s.wrong)
    ratio = difflib.SequenceMatcher(None, s.wrong.lower(), s.right.lower()).ratio()
    return ratio >= 0.6


def accepted(s: Suggestion) -> bool:
    """A model's suggestion passes when its edit is minimal; the guard (``Suggestion.guard``) still decides whether
    it may be taken without a person."""
    return minimal(s)


@dataclass
class OllamaTextCorrector:
    """A local text model, through Ollama, reading a passage's OCR errors."""

    model: str = DEFAULT_TEXT_MODEL
    base_url: str = "http://localhost:11434"
    context: int = 8192
    timeout: int = 300
    fetch: Callable[[str, dict], dict] | None = None

    def _ask(self, system: str, user: str, schema: dict, *, temperature: float = 0.0, seed: int | None = None) -> str:
        from jason.community.ollama_extractor import _post

        options: dict[str, Any] = {"temperature": temperature, "num_ctx": self.context, "num_predict": 2048}
        if seed is not None:
            options["seed"] = seed
        payload = {"model": self.model, "stream": False, "think": False, "format": schema, "keep_alive": "5m",
                   "options": options,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        poster = self.fetch or (lambda url, body: _post(url, body, self.timeout))
        answer = poster(f"{self.base_url}/api/chat", payload)
        return str((answer.get("message") or {}).get("content") or "")

    def expectations(self, tokens: Sequence[str], *, temperature: float = 0.0, seed: int | None = None
                     ) -> tuple[list[Suggestion], list[dict]]:
        answer = self._ask(EXPECTATIONS_PROMPT, "Passage:\n" + " ".join(tokens), CORRECTIONS_SCHEMA,
                           temperature=temperature, seed=seed)
        return parse_corrections(answer, tokens)

    def choose(self, tokens: Sequence[str], i: int, options: Sequence[str], *, window: int = 14) -> dict[str, float]:
        """The model as a scorer, not a writer: it picks among the readings of token ``i`` (the token as read and the
        lexicon's candidates) with one letter, and the probabilities of the letters (Ollama's ``top_logprobs``) are
        its weights; a reading it cannot name is never written. Returns {reading: probability}."""
        from jason.community.ollama_extractor import _post

        letters = "ABCDEFGH"[: len(options)]
        left = " ".join(tokens[max(0, i - window):i])
        right = " ".join(tokens[i + 1:i + 1 + window])
        lines = "\n".join(f"{c}) {o}" for c, o in zip(letters, options))
        prompt = (f"{CHOOSE_PROMPT}\n\nPassage: {left} [[{tokens[i]}]] {right}\n\nThe marked token was read by OCR as "
                  f"\"{tokens[i]}\". Which did the page print?\n{lines}\nAnswer with one letter.")
        payload = {"model": self.model, "stream": False, "think": False, "logprobs": True, "top_logprobs": 10,
                   "keep_alive": "5m", "options": {"temperature": 0, "num_ctx": self.context, "num_predict": 1},
                   "messages": [{"role": "user", "content": prompt}]}
        poster = self.fetch or (lambda url, body: _post(url, body, self.timeout))
        answer = poster(f"{self.base_url}/api/chat", payload)
        weights = letter_weights(answer, letters)
        return {o: weights[c] for c, o in zip(letters, options)}

    def marked(self, tokens: Sequence[str], suspects: Sequence[int]) -> list[Suggestion]:
        if not suspects:
            return []
        answer = self._ask(MARKED_PROMPT, "Passage:\n" + marked_passage(tokens, suspects), READINGS_SCHEMA)
        return parse_readings(answer, tokens, suspects)


# The vision model on the word's crop.

VISION_WORD_PROMPT = """The first image is one word (or a few) cut from a scanned, typed legal document; the second \
is its whole line, for context. Copy exactly the characters printed in the first image: letters, digits, and \
punctuation, keeping capitals as printed. Do not correct spelling and do not guess a word that is not there; if a \
character is unreadable, write ? for it. Answer in JSON: {"text": "..."}."""

WORD_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}

# Anchored: the OCR's own reading of the line goes with the images (olmOCR's "document anchoring"), and the question
# names the one word in doubt.
VISION_ANCHORED_PROMPT = """The first image is one word (or a few) cut from a scanned, typed legal document; the \
second is its whole line. An OCR engine read the line as:
{line}
and read the word in the first image as "{word}", which may be wrong. Look at the images and copy exactly the \
characters printed in the first image: letters, digits, and punctuation, keeping capitals as printed. Keep the \
spaces between words as printed. Do not correct the drafter's spelling or grammar, and do not guess a word that is \
not there; if a character is unreadable, write ? for it. Answer in JSON: {{"text": "..."}}."""


@dataclass
class VisionWordReader:
    """A vision model reading one word's crop of the page image (``OllamaVisionOcr``'s model by default)."""

    model: str = ""
    base_url: str = "http://localhost:11434"
    timeout: int = 300
    fetch: Callable[[str, dict], dict] | None = None

    def read(self, word_png_b64: str, line_png_b64: str = "", *, ocr_line: str = "", ocr_word: str = "",
             context: int = 0) -> str:
        """What the crop says. With ``ocr_line`` and ``ocr_word`` the OCR's reading goes with the images (anchored)."""
        import os

        from jason.community.ocr import OLLAMA_OCR_CONTEXT, OLLAMA_OCR_MODEL
        from jason.community.ollama_extractor import _post

        model = self.model or os.environ.get("JASON_OCR_MODEL") or OLLAMA_OCR_MODEL
        images = [word_png_b64] + ([line_png_b64] if line_png_b64 else [])
        prompt = (VISION_ANCHORED_PROMPT.format(line=ocr_line, word=ocr_word) if ocr_line and ocr_word
                  else VISION_WORD_PROMPT)
        payload = {"model": model, "stream": False, "think": False, "format": WORD_SCHEMA, "keep_alive": "5m",
                   "options": {"temperature": 0, "num_ctx": context or OLLAMA_OCR_CONTEXT, "num_predict": 64},
                   "messages": [{"role": "user", "content": prompt, "images": images}]}
        poster = self.fetch or (lambda url, body: _post(url, body, self.timeout))
        answer = poster(f"{self.base_url}/api/chat", payload)
        try:
            return str(json.loads(str((answer.get("message") or {}).get("content") or "{}")).get("text") or "").strip()
        except ValueError:
            return ""


# The vision model on a whole line, held to the places the text rules doubt.

VISION_LINE_PROMPT = """The image is one line cut from a scanned, typed legal document. Copy exactly the characters \
printed: letters, digits, and punctuation, keeping capitals as printed and the spaces between words as printed. Do not \
correct spelling or grammar, and do not guess words that are not there; if a character is unreadable, write ? for it. \
Answer in JSON: {"text": "..."}."""


@dataclass
class VisionLineReader:
    """A vision model reading one line's crop of the page image."""

    model: str = ""
    base_url: str = "http://localhost:11434"
    timeout: int = 300
    fetch: Callable[[str, dict], dict] | None = None

    def read(self, line_png_b64: str, *, context: int = 0) -> str:
        import os

        from jason.community.ocr import OLLAMA_OCR_CONTEXT, OLLAMA_OCR_MODEL
        from jason.community.ollama_extractor import _post

        model = self.model or os.environ.get("JASON_OCR_MODEL") or OLLAMA_OCR_MODEL
        payload = {"model": model, "stream": False, "think": False, "format": WORD_SCHEMA, "keep_alive": "5m",
                   "options": {"temperature": 0, "num_ctx": context or OLLAMA_OCR_CONTEXT, "num_predict": 400},
                   "messages": [{"role": "user", "content": VISION_LINE_PROMPT, "images": [line_png_b64]}]}
        poster = self.fetch or (lambda url, body: _post(url, body, self.timeout))
        answer = poster(f"{self.base_url}/api/chat", payload)
        try:
            return str(json.loads(str((answer.get("message") or {}).get("content") or "{}")).get("text") or "").strip()
        except ValueError:
            return ""


def line_suggestions(tokens: Sequence[str], reread: str, doubted: Sequence[int], *, offset: int = 0,
                     max_ratio: float = 0.6) -> list[Suggestion]:
    """The vision model's re-reading of a line as suggestions, only where it differs from the OCR's tokens on a doubted
    token (an index of ``tokens``): a re-reading that wanders elsewhere is not taken, and an edit that changes more than
    ``minimal`` allows is not either (the same guard as every model's edit). ``offset`` shifts the spans to the passage's
    token numbers. A line with a "?" in the re-reading, or one far longer or shorter than the OCR's, is not used."""
    import difflib

    new = reread.split()
    if not new or "?" in reread or not tokens:
        return []
    if not 0.7 <= len(new) / len(tokens) <= 1.4:
        return []
    out = []
    marks = set(doubted)
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=list(tokens), b=new, autojunk=False).get_opcodes():
        if tag == "equal" or i2 == i1:
            continue                                            # a word the OCR never read is not a suspect's reading
        # Words changed one for one are judged one by one: a neighbour the rules do not doubt is left as it was.
        spans = ([(i1 + d, i1 + d + 1, j1 + d, j1 + d + 1) for d in range(i2 - i1)]
                 if tag == "replace" and i2 - i1 == j2 - j1 else [(i1, i2, j1, j2)])
        for a, b, c, d in spans:
            if not marks.intersection(range(a, b)) or tokens[a:b] == new[c:d]:
                continue
            right = " ".join(new[c:d])
            s = Suggestion(offset + a, offset + b, " ".join(tokens[a:b]), right,
                           Fix.SPLIT if right.replace(" ", "") == "".join(tokens[a:b]) else
                           Fix.STRAY if not right else Fix.CHARACTER, (Method.VISION,), 0.7,
                           (f"vision: the line's crop reads \"{right}\"",))
            if minimal(s) or (b - a == 1 and d - c == 1 and _edit_distance(s.wrong.lower(), right.lower()) <= 1):
                out.append(s)               # a short word one letter off is minimal too ("ot" for "of")
    return out


# The vision model as a scorer: the crop and the readings the text rules weigh, and one letter back.

NONE_OF_THESE = "(none of these)"

VISION_CHOOSE_PROMPT = """The first image is one word (or a few) cut from a scanned, typed legal document; the second \
is its whole line, for context. An OCR engine read the word as "{word}", which may be wrong. Which of these is printed \
in the first image? Letters, digits, and capitals count: choose the option that matches the characters you see. If \
none matches, choose the last letter.
{options}
Answer with one letter."""


@dataclass
class VisionChooser:
    """The vision model as a scorer, not a writer: it sees the word's crop and the candidate readings (the token as
    read and the readings the lexicon weighs) and answers with one letter; the letters' probabilities (Ollama's
    ``top_logprobs``, which it returns on a request that carries images) are its weights. It never writes a reading it
    was not given: the last option says the page matches none of them. Returns {reading: probability}, ``NONE_OF_THESE``
    among them."""

    model: str = ""
    base_url: str = "http://localhost:11434"
    timeout: int = 300
    fetch: Callable[[str, dict], dict] | None = None

    def choose(self, word_png_b64: str, line_png_b64: str, as_read: str, options: Sequence[str],
               *, context: int = 0) -> dict[str, float]:
        import os

        from jason.community.ocr import OLLAMA_OCR_CONTEXT, OLLAMA_OCR_MODEL
        from jason.community.ollama_extractor import _post

        model = self.model or os.environ.get("JASON_OCR_MODEL") or OLLAMA_OCR_MODEL
        shown = [o for o in dict.fromkeys(options)][:7]
        letters = "ABCDEFGH"[: len(shown) + 1]
        lines = "\n".join(f"{c}) {o}" for c, o in zip(letters, shown)) + f"\n{letters[-1]}) none of these"
        images = [word_png_b64] + ([line_png_b64] if line_png_b64 else [])
        payload = {"model": model, "stream": False, "think": False, "logprobs": True, "top_logprobs": 10,
                   "keep_alive": "5m", "options": {"temperature": 0, "num_ctx": context or OLLAMA_OCR_CONTEXT, "num_predict": 1},
                   "messages": [{"role": "user", "content": VISION_CHOOSE_PROMPT.format(word=as_read, options=lines),
                                 "images": images}]}
        poster = self.fetch or (lambda url, body: _post(url, body, self.timeout))
        weights = letter_weights(poster(f"{self.base_url}/api/chat", payload), letters)
        return {**{o: weights[c] for c, o in zip(letters, shown)}, NONE_OF_THESE: weights[letters[-1]]}


__all__ = ["CORRECTIONS_SCHEMA", "DEFAULT_TEXT_MODEL", "EXPECTATIONS_PROMPT", "MARKED_PROMPT", "NONE_OF_THESE",
           "OllamaTextCorrector", "READINGS_SCHEMA", "VISION_CHOOSE_PROMPT", "VISION_LINE_PROMPT", "VISION_WORD_PROMPT",
           "VisionChooser", "VisionLineReader", "VisionWordReader", "accepted", "letter_weights", "line_suggestions",
           "marked_passage", "minimal", "parse_corrections", "parse_readings"]
