"""A local model reading one section at a time for the references the citation grammar misses.

The grammar (``jason.community.references``) reads citations written the way associations write them: "Section 7.2
of the Bylaws", "Civil Code 5850(c)", "Resolution 20230130-1". Prose references escape it: "the rules adopted by the
Board", "the Association's Enforcement Policy", "as provided in the Declaration" with no section, "the Davis-Stirling
Act", "the City's conditions of approval". ``ReferenceModel`` asks the shared local model, through Ollama, for the
references in one section's own words, answering to a JSON schema, with the documents jason has outlined (their keys,
titles, and the names other documents use for them) so the model names a known document by its key itself.

Nothing the model says is kept on its word. ``verify`` keeps a proposed reference only when the words it quotes occur
in the section (compared without regard to case, spacing, or the style of quotation marks and dashes), and names its
target by the grammar's conventions: a statute as "CIV 4000", a section as "bylaws#7.2", a known document by its key,
a resolution or recorded instrument by the number it prints. A name that is on no list keeps the words the document
uses, as ``named:<name>``. ``dedupe`` sets aside what the grammar already found in the same section. A kept reference
is marked ``method="model"``: it is a lead a person reads, not a pin.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urlparse

from jason.community.outlines import DocumentOutline, normalize_number
from jason.community.references import (
    RefRelation, Reference, TargetKind, _is_prior_davis_stirling, _relation, _sentence, _split_numbers, extract, section_target,
    statute_key,
)

# The codes the grammar names ("CIV 4926"), and a regulation ("10 CCR 2792.23").
CODE_NAMES = ("CIV", "CORP", "HSC", "GOV", "EVID", "BPC", "CCP", "VEH", "PEN")
_CANON_STATUTE = re.compile(rf"^(?P<code>{'|'.join(CODE_NAMES)})\s*(?:§+|[Ss]ec(?:tion)?\.?)?\s*"
                            r"(?P<num>\d{2,6}(?:\.\d+)?(?:\s?\([A-Za-z0-9]{1,4}\))*)$", re.I)
_CANON_REG = re.compile(r"^(?P<title>\d{1,2})\s*CCR\s*(?:§|[Ss]ec(?:tion)?\.?)?\s*(?P<num>\d{3,5}(?:\.\d+)?)$", re.I)
_RESOLUTION_NUMBER = re.compile(r"^(?:\d{8}-\d+|\d{6}-\d+|\d{4}-\d{2}-\d{2}-\d+|\d{4}-\d{1,3})$")
_INSTRUMENT_NUMBER = re.compile(r"^(?:(?:19|20)\d{10}|book \d{8} page \d{1,5})$", re.I)

# An act cited by its name is cited by the section that gives it that name.
ACTS: tuple[tuple[str, str], ...] = (
    ("davis-stirling", "CIV 4000"),               # "This act shall be known ... as the Davis-Stirling Common Interest Development Act"
    ("nonprofit mutual benefit corporation", "CORP 7110"),
    ("fair employment and housing act", "GOV 12900"),
    ("unruh civil rights act", "CIV 51"),
)

KIND_WORDS = {"statute": TargetKind.STATUTE, "section": TargetKind.SECTION, "document": TargetKind.DOCUMENT,
              "resolution": TargetKind.RESOLUTION, "instrument": TargetKind.INSTRUMENT}

# Ollama constrains the answer to this schema, so the parser sees JSON (and still checks it).
ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": list(KIND_WORDS)},
                    "target": {"type": "string"},
                    "quote": {"type": "string"},
                    "relation": {"type": "string", "enum": [r.value for r in RefRelation]},
                },
                "required": ["kind", "target", "quote", "relation"],
            },
        },
    },
    "required": ["references"],
}

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


@dataclass(frozen=True)
class Passage:
    """One section's own words: from its start to the next section of any depth (its subsections are passages of their
    own), cut to the reader's limit. ``section`` is the section's name as the grammar records it, "" outside any."""

    source: str
    section: str
    title: str
    start: int                  # offset into the outline's text
    text: str
    trimmed: bool = False

    @property
    def id(self) -> str:
        return f"{self.source}@{self.start}"


def passages(outline: DocumentOutline, *, max_chars: int = 6000, min_chars: int = 60) -> list[Passage]:
    """Every passage of ``outline`` with at least ``min_chars`` of words. A document with no sections (a resolution, an
    amendment read whole) is read in pieces of ``max_chars`` cut at a line break."""
    text = outline.text
    out: list[Passage] = []

    def add(section: str, title: str, start: int, end: int) -> None:
        body = text[start:end]
        if len("".join(body.split())) < min_chars:
            return
        out.append(Passage(outline.key, section, title, start, body[:max_chars], len(body) > max_chars))

    ordered = sorted(outline.sections, key=lambda s: s.start)
    if not ordered:
        at = 0
        while at < len(text):
            end = min(len(text), at + max_chars)
            if end < len(text) and (cut := text.rfind("\n", at + max_chars // 2, end)) > at:
                end = cut + 1
            add("", "", at, end)
            at = end
        return out
    add("", "", 0, ordered[0].start)            # the preamble before the first section
    for k, s in enumerate(ordered):
        end = next((t.start for t in ordered[k + 1:] if t.start > s.start), len(text))
        add(s.name, s.title, s.start, end)
    return out


@dataclass
class Catalog:
    """The documents a model may name by key: each key, the names that map to it (lowercase), and the prompt's list."""

    keys: set[str] = field(default_factory=set)
    names: dict[str, str] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    outlines: dict[str, DocumentOutline] = field(default_factory=dict)


def _clean_name(name: str) -> str:
    name = " ".join(_fold_chars(name).lower().split()).strip(" .,;:\"'")
    name = re.sub(r"^(?:the|this|these|said|such)\s+", "", name)
    # "the Association's Enforcement Policy" is the Enforcement Policy; "the City's conditions of approval" keeps the City.
    name = re.sub(r"^(?:association|board)'s\s+", "", name)
    return re.sub(r"'s$", "", name).strip()


def catalog(outlines: Iterable[DocumentOutline]) -> Catalog:
    """The known documents from the outlines: aliases and titles map to keys; a name two documents share maps to none."""
    out = Catalog()
    claims: dict[str, set[str]] = {}
    for o in outlines:
        out.keys.add(o.key)
        out.outlines[o.key] = o
        for name in [o.key, o.title, *o.aliases]:
            if name:
                claims.setdefault(_clean_name(name), set()).add(o.key)
        line = f"- {o.key}: {o.title}" + (f" ({o.kind.replace('_', ' ')})" if o.kind else "")
        if o.aliases:
            line += "; also called: " + ", ".join(o.aliases)
        if o.numbers:
            line += "; prints resolution number " + ", ".join(o.numbers)
        if o.amends:
            line += f"; amends or supplements {o.amends}"
        out.lines.append(line)
    out.names = {name: next(iter(keys)) for name, keys in claims.items() if len(keys) == 1}
    return out


_EXAMPLES = """Examples. Suppose the list had sample-declaration (also called: Declaration, CC&Rs) and sample-rules (also called: Rules and Regulations).
Text: "Each Owner shall comply with the rules adopted by the Board from time to time."
Answer: {"references": [{"kind": "document", "target": "sample-rules", "quote": "the rules adopted by the Board", "relation": "is subject to"}]}
Text: "Assessments shall be collected as provided in the Declaration and the Davis-Stirling Common Interest Development Act."
Answer: {"references": [{"kind": "document", "target": "sample-declaration", "quote": "as provided in the Declaration", "relation": "acts under"}, {"kind": "statute", "target": "CIV 4000", "quote": "the Davis-Stirling Common Interest Development Act", "relation": "acts under"}]}
Text: "No improvement may be made that conflicts with the City's conditions of approval or Section 6.5(b) of the CC&Rs."
Answer: {"references": [{"kind": "document", "target": "City's conditions of approval", "quote": "the City's conditions of approval", "relation": "is subject to"}, {"kind": "section", "target": "sample-declaration#6.5(b)", "quote": "Section 6.5(b) of the CC&Rs", "relation": "is subject to"}]}
Text: "Owners shall keep their patios clean and free of debris."
Answer: {"references": []}"""


def build_prompt(passage: Passage, catalog: Catalog) -> str:
    """The instructions, the known documents with their names, the naming rules, worked examples, and the section."""
    source = catalog.outlines.get(passage.source)
    where = f"section {passage.section}" if passage.section else "a part with no section number"
    if passage.title and passage.title != passage.section:
        where += f" ({passage.title[:90]})"
    relations = "; ".join(f'"{r.value}"' for r in RefRelation)
    return (
        "You read one section of a California homeowners association's governing document and list every reference it "
        "makes to a law, another document, a board resolution, a recorded instrument, or a numbered section. Look hardest "
        "for references written in words without a section number: \"the rules adopted by the Board\", \"the "
        "Association's Enforcement Policy\", \"as provided in the Declaration\", \"the Davis-Stirling Act\", \"the City's "
        "conditions of approval\". Do not list the document referring to itself as a whole (\"these Rules\", \"this "
        "Policy\"), and do not list a word that only names a thing (\"the Board\", \"the Association\", \"the Common "
        "Area\") rather than a document or law. Do not list a law the text names only in general (\"as required by "
        "law\", \"California law\", \"state law\", \"the Civil Code\" with no section number): a statute needs a section "
        "number or an act's own name.\n\n"
        "Documents jason knows, by key:\n" + "\n".join(catalog.lines) + "\n\n"
        "Name each target this way:\n"
        "- statute: the code and number, \"CIV 4926(a)(3)\", \"CORP 7341\", \"10 CCR 2792.23\" (codes: "
        + ", ".join(CODE_NAMES) + "). An act named without a number is cited by the section that names it: the "
        "Davis-Stirling Common Interest Development Act is \"CIV 4000\", the Nonprofit Mutual Benefit Corporation Law is "
        "\"CORP 7110\". Any other law without a number: its name as written.\n"
        "- section: the document's key, \"#\", and the number, \"bylaws#7.2\", \"ccrs#6.5(b)\"; this document's own "
        "section is \"#1.3\".\n"
        "- document: its key from the list when the name fits one of the list's names or titles; otherwise the name "
        "exactly as the text gives it.\n"
        "- resolution: \"resolution:\" and the number it prints, \"resolution:20230130-1\"; without a number, its name.\n"
        "- instrument: \"instrument:\" and the recorder's document number.\n\n"
        f"relation is how this section stands to the target, one of: {relations}. "
        "quote is a short phrase copied exactly, character for character, from the section text below (three to "
        "fifteen words, including the name of the target). Never paraphrase a quote, and never list a reference whose "
        "words are not in the text. An empty list is a good answer when there are none.\n\n"
        f"{_EXAMPLES}\n\n"
        f"The document: {passage.source}" + (f" ({source.title})" if source else "") + f", {where}.\n"
        f"Text:\n{passage.text}"
    )


class ReferenceModel:
    """The shared local model over one passage, answering references to ``ANSWER_SCHEMA``.

    ``fetch(url, payload)`` replaces HTTP in tests. Only an Ollama on this machine is asked: a base URL on another host
    is refused, so nothing a document says leaves the machine.
    """

    def __init__(self, *, model: str = "", base_url: str = "", fetch=None, timeout: int = 600, keep_alive: str = "5m") -> None:
        from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL

        self.model = model or DEFAULT_MODEL
        self.num_ctx = DEFAULT_CONTEXT
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")
        if (urlparse(self.base_url).hostname or "") not in LOCAL_HOSTS:
            raise ValueError(f"the reference model reads only through an Ollama on this machine, not {self.base_url}")
        self._fetch = fetch
        self.timeout = timeout
        # The model is the one AnythingLLM chats with: a short keep_alive would only unload it from under it.
        self.keep_alive = keep_alive
        self._checked = False

    def preflight(self) -> None:
        """Refuse to start on the CPU, short of commit, or with Ollama down (jason.local_ai); once per reader."""
        if self._fetch is not None or self._checked:
            return
        from jason.community.content import ModelUnavailable
        from jason.local_ai import LocalAIUnavailable, preflight

        try:
            preflight(self.model, ollama_url=self.base_url)
        except LocalAIUnavailable as exc:
            raise ModelUnavailable(str(exc)) from exc
        self._checked = True

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self._fetch is not None:
            return self._fetch(f"{self.base_url}{path}", payload)
        from urllib.error import URLError
        from urllib.request import Request, urlopen

        from jason.community.content import ModelUnavailable
        from jason.locks import Resource, ResourceBusy, hold

        request = Request(f"{self.base_url}{path}", data=json.dumps(payload).encode("utf-8"),
                          headers={"Content-Type": "application/json"}, method="POST")
        try:
            # One model request from jason at a time (jason.locks); a wait past the timeout is reported, not retried.
            with hold(Resource.GPU, timeout=self.timeout, purpose=f"{self.model} references"), urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except ResourceBusy as exc:
            raise ModelUnavailable(f"the model server is busy with another jason process: {exc}") from exc
        except (URLError, OSError) as exc:
            raise ModelUnavailable(f"Ollama at {self.base_url} did not answer: {exc}") from exc

    def read(self, passage: Passage, catalog: Catalog) -> str:
        """The model's raw answer for ``passage``."""
        self.preflight()
        data = self._post("/api/chat", {"model": self.model, "messages": [{"role": "user", "content": build_prompt(passage, catalog)}],
                                         "format": ANSWER_SCHEMA, "stream": False, "think": False, "keep_alive": self.keep_alive,
                                         "options": {"temperature": 0, "num_ctx": self.num_ctx}})
        return str((data.get("message") or {}).get("content") or data.get("response") or "")


def parse_answer(raw: str) -> tuple[list[dict[str, str]], int, str]:
    """The proposals in the model's JSON, how many items were malformed, and an error when the whole answer was."""
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return [], 0, "the model did not answer in JSON"
    items = data.get("references") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return [], 0, "the model's answer has no list of references"
    out, bad = [], 0
    for item in items:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item.get(k).strip() for k in ("kind", "target", "quote")):
            bad += 1
            continue
        out.append({"kind": item["kind"].strip().lower(), "target": item["target"].strip(), "quote": item["quote"].strip(),
                    "relation": str(item.get("relation") or "").strip()})
    return out, bad, ""


_CHARS = str.maketrans({"’": "'", "‘": "'", "‛": "'", "`": "'", "“": '"', "”": '"', "„": '"', "–": "-", "—": "-", "‐": "-",
                        "‑": "-", " ": " ", "​": " ", "﻿": " "})


def _fold_chars(text: str) -> str:
    return text.translate(_CHARS)


def folded(text: str) -> tuple[str, list[int]]:
    """``text`` case-folded, its quotation marks and dashes plain, its spacing one space; with each character's offset."""
    out: list[str] = []
    where: list[int] = []
    space = False
    for i, ch in enumerate(_fold_chars(text)):
        if ch.isspace():
            if out and not space:
                out.append(" ")
                where.append(i)
            space = True
            continue
        space = False
        for c in ch.casefold():
            out.append(c)
            where.append(i)
    return "".join(out), where


def find_quote(text: str, quote: str) -> tuple[int, int] | None:
    """Where ``quote`` occurs in ``text`` (start and end offsets), comparing folded; None when it does not."""
    q, _ = folded(quote)
    q = q.strip(" \"'").removesuffix("...").removesuffix("…").strip(" \"'")
    if len(q.replace(" ", "")) < 4:
        return None
    body, where = folded(text)
    at = body.find(q)
    if at < 0:
        return None
    return where[at], where[at + len(q) - 1] + 1


def _scratch(outline: DocumentOutline, text: str) -> DocumentOutline:
    """``outline`` with other words, so the grammar reads a target as that document would ("Section 7.2" is its own)."""
    return DocumentOutline(key=outline.key, title=outline.title, kind=outline.kind, text=text, sections=outline.sections,
                           amends=outline.amends)


def _by_grammar(outline: DocumentOutline, text: str, catalog: Catalog, kind: TargetKind) -> Reference | None:
    return next((r for r in extract(_scratch(outline, text), catalog.names) if r.kind is kind), None)


def normalize_target(kind: TargetKind, target: str, outline: DocumentOutline, catalog: Catalog) -> tuple[str, bool]:
    """The target named by the grammar's conventions, and whether it is a pre-2014 Davis-Stirling number. A name on no
    list is ``named:<name>``."""
    t = " ".join(_fold_chars(target).split())
    if kind is TargetKind.STATUTE:
        if m := _CANON_STATUTE.match(t):
            code, number = m.group("code").upper(), re.sub(r"\s+", "", m.group("num"))
            return f"{code} {number}", _is_prior_davis_stirling(code, number)
        if m := _CANON_REG.match(t):
            return f"{m.group('title')} CCR {m.group('num')}", False
        if ref := _by_grammar(outline, t, catalog, TargetKind.STATUTE):
            return ref.target, ref.prior
        lower = t.lower()
        if act := next((statute for name, statute in ACTS if name in lower), ""):
            return act, False
        return f"named:{_clean_name(t)}", False
    if kind is TargetKind.SECTION:
        if "#" in t:
            key, number = t.split("#", 1)
            number = normalize_number(re.sub(r"^(?:[Ss]ections?|§+|[Aa]rticles?|[Pp]aragraphs?)\s*", "", number.strip()))
            key = key.strip()
            if not key:
                key = outline.key
            elif key not in catalog.keys:
                key = catalog.names.get(_clean_name(key), "") or f"named:{_clean_name(key)}"
            return f"{key}#{number}", False
        if ref := _by_grammar(outline, t, catalog, TargetKind.SECTION):
            return ref.target, False
        return f"named:{_clean_name(t)}", False
    if kind is TargetKind.DOCUMENT:
        if t in catalog.keys:
            return t, False
        return catalog.names.get(_clean_name(t), "") or f"named:{_clean_name(t)}", False
    if kind is TargetKind.RESOLUTION:
        number = re.sub(r"^resolution:\s*", "", t, flags=re.I)
        if _RESOLUTION_NUMBER.match(number):
            return f"resolution:{number}", False
        if ref := _by_grammar(outline, t, catalog, TargetKind.RESOLUTION):
            return ref.target, False
        return f"named:{_clean_name(t)}", False
    number = re.sub(r"^instrument:\s*", "", t, flags=re.I)
    if _INSTRUMENT_NUMBER.match(number):
        return f"instrument:{number.lower() if number.lower().startswith('book') else number}", False
    if ref := _by_grammar(outline, t, catalog, TargetKind.INSTRUMENT):
        return ref.target, False
    return f"named:{_clean_name(t)}", False


@dataclass(frozen=True)
class ModelReference:
    """A verified reference and the words the model quoted for it (``Reference.quote`` is the whole sentence, as the
    grammar records it)."""

    reference: Reference
    said: str
    passage: str = ""            # the Passage.id it was read from

    def to_dict(self) -> dict[str, Any]:
        return {**self.reference.to_dict(), "said": self.said, "passage": self.passage}


def section_rule(target: str) -> tuple[TargetKind, str, bool] | None:
    """A section target as the grammar would take it: "#5105(i)" is the Civil Code (a four-digit number is never a
    section here), and a target with no section number ("#a)") is none at all (None)."""
    _, _, number = target.partition("#")
    bare = re.fullmatch(r"(\d{4,6})((?:\.\d+)?(?:\([a-z0-9]+\))*)", number)
    if bare and 1350 <= int(bare.group(1)) <= 6200:
        return TargetKind.STATUTE, f"CIV {number}", _is_prior_davis_stirling("CIV", number)
    if not re.match(r"(?:[A-Z]-)?\d", number):
        return None
    return TargetKind.SECTION, target, False


def verify(passage: Passage, proposals: list[dict[str, str]], outline: DocumentOutline,
           catalog: Catalog) -> tuple[list[ModelReference], list[dict[str, Any]]]:
    """The proposals whose quote occurs in the passage, as references; the rest, each with why it was dropped."""
    kept: list[ModelReference] = []
    dropped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in proposals:
        row = {"source": passage.source, "source_section": passage.section, **p}
        kind = KIND_WORDS.get(p["kind"])
        if kind is None:
            dropped.append({**row, "reason": "not a kind of target"})
            continue
        span = find_quote(passage.text, p["quote"])
        if span is None:
            dropped.append({**row, "reason": "quote not in the section"})
            continue
        target, prior = normalize_target(kind, p["target"], outline, catalog)
        if kind is TargetKind.DOCUMENT and target == outline.key:
            dropped.append({**row, "reason": "the document itself"})
            continue
        start, end = passage.start + span[0], passage.start + span[1]
        said = outline.text[start:end]
        if kind is TargetKind.STATUTE and not re.search(r"\d", said) and not any(name in said.lower() for name, _ in ACTS):
            # "as required by law", "the Civil Code", "California law": a law named only in general is no citation, and
            # mapping it to a whole act would invent one. Kept only with a section number or an act's own name.
            dropped.append({**row, "reason": "a law named only in general"})
            continue
        if kind is TargetKind.SECTION:
            checked = section_rule(target)
            if checked is None:
                dropped.append({**row, "reason": "not a section number"})
                continue
            kind, target, prior = checked
        # "ccrs#6.12(d),(f)" is two subsections.
        key, _, number = target.partition("#")
        targets = [f"{key}#{n}" for n in _split_numbers(number)] if kind is TargetKind.SECTION and "," in number else [target]
        try:
            relation = RefRelation(p["relation"])
        except ValueError:
            relation = _relation(outline.text, start, end)
        for one in targets:
            if one in seen:
                continue
            seen.add(one)
            ref = Reference(passage.source, passage.section, kind, one, relation, _sentence(outline.text, start, end), start,
                            prior, method="model")
            kept.append(ModelReference(ref, said, passage.id))
    return kept, dropped


def _covers(model_target: str, grammar_target: str, kind: TargetKind) -> bool:
    if model_target == grammar_target:
        return True
    if kind is TargetKind.STATUTE:
        return statute_key(model_target)[0] == statute_key(grammar_target)[0]
    if kind is TargetKind.SECTION:
        a, b = model_target, grammar_target
        return any(x.startswith(y + s) for x, y in ((a, b), (b, a)) for s in ("(", "."))
    if kind is TargetKind.DOCUMENT:
        return section_target(grammar_target)[0] == model_target
    return False


def dedupe(found: list[ModelReference], grammar: Iterable[Reference]) -> tuple[list[ModelReference], list[ModelReference]]:
    """Split the model's references into new ones and ones the grammar already has in the same section: the same target,
    the same statute at another subdivision, a section or subsection of it, or the document by any section."""
    by_section: dict[tuple[str, str], list[Reference]] = {}
    for r in grammar:
        by_section.setdefault((r.source, r.source_section), []).append(r)
    new, known = [], []
    for m in found:
        r = m.reference
        there = by_section.get((r.source, r.source_section), [])
        (known if any(_covers(r.target, g.target, r.kind) for g in there) else new).append(m)
    return new, known


__all__ = ["Passage", "passages", "Catalog", "catalog", "build_prompt", "ReferenceModel", "parse_answer", "folded", "find_quote",
           "normalize_target", "ModelReference", "verify", "dedupe", "ANSWER_SCHEMA", "ACTS"]
