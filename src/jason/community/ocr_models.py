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
        import math

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
        weights = {c: 0.0 for c in letters}
        for row in (answer.get("logprobs") or [{}])[0].get("top_logprobs") or []:
            c = str(row.get("token") or "").strip()
            if c in weights:
                weights[c] += math.exp(float(row.get("logprob") or -100))
        total = sum(weights.values()) or 1.0
        return {o: weights[c] / total for c, o in zip(letters, options)}

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


__all__ = ["CORRECTIONS_SCHEMA", "DEFAULT_TEXT_MODEL", "EXPECTATIONS_PROMPT", "MARKED_PROMPT", "OllamaTextCorrector",
           "READINGS_SCHEMA", "VISION_WORD_PROMPT", "VisionWordReader", "accepted", "marked_passage", "minimal",
           "parse_corrections", "parse_readings"]
