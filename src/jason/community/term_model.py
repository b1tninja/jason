"""A model reviewing a contract's terms: the grammar's candidates confirmed or corrected, and the terms it missed.

The grammar (``jason.community.contract_terms``) reads every "shall", "may", and "must" and the sentences a topic rule
names. A model reads the same sections beside those candidates and says, for each, whether it is a term, its kind, who
bears it, its topic, and whether it is something the association can ask the counterparty to produce; then it lists the
terms the grammar missed ("Manager will deliver ...", a list item with no verb of its own).

Two backends answer to one shape (``Backend``), so the reader swaps models by configuration
(docs/deployment-research.md, The model):

- ``OllamaBackend``: a model on this machine, under the GPU lock, after ``jason.local_ai.preflight``. The default.
- ``BedrockBackend``: Claude on Amazon Bedrock (the ``bedrock`` extra: ``anthropic[bedrock]``), through the Mantle client
  with the standard AWS credential chain. It sends the contract's words to AWS, so it is ``remote``: a reading marked
  confidential is refused unless a person allows it for that run, and a person chooses the backend.

Nothing the model says is kept on its word. A missed term is kept only when its quote is in the section (compared
folded, ``reference_model.find_quote``) and only with the kinds, parties, and topics jason defines. A kept reading is
marked ``hybrid:<backend>``: a lead a person reviews. The prompt names kinds and topics, never a party's name, a section
number, or a figure.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import replace
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from jason.community.contract_terms import (
    ContractTerm, Party, Topic, TermKind, _particulars, deliveries, window_of,
)
from jason.community.deontic import Deadline, DeadlineRelation, find_deadline, find_recurrence
from jason.community.reference_model import LOCAL_HOSTS, find_quote

KINDS = [k.value for k in TermKind]
PARTIES = [p.value for p in Party]
TOPICS = [t.name.lower() for t in Topic]
BATCH_CHARS = 9_000                   # the sections asked about at once
QUOTE_CHARS = 600                     # a candidate's words shown to the model

BEDROCK_MODEL = "anthropic.claude-opus-5-5"


class ModelUnavailable(RuntimeError):
    """The backend cannot answer (not installed, not reachable, busy, no credentials, or it declined)."""


class Backend(Protocol):
    name: str
    remote: bool                      # the words leave this machine

    def ask(self, prompt: str, schema: dict[str, Any]) -> str: ...


def _strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Every object closed and every property required: what structured outputs need, and harmless to Ollama."""
    if schema.get("type") == "object":
        props = schema.get("properties", {})
        return {**schema, "properties": {k: _strict(v) for k, v in props.items()}, "required": list(props),
                "additionalProperties": False}
    if schema.get("type") == "array":
        return {**schema, "items": _strict(schema["items"])}
    return schema


_TERM_ITEM = {"type": "object", "properties": {
    "quote": {"type": "string"},
    "kind": {"type": "string", "enum": KINDS},
    "party": {"type": "string", "enum": PARTIES},
    "topic": {"type": "string", "enum": TOPICS},
    "action": {"type": "string"},
    "deadline": {"type": "string"},
    "recurrence": {"type": "string"},
    "deliverable": {"type": "boolean"},
}}
REVIEW_SCHEMA: dict[str, Any] = _strict({"type": "object", "properties": {
    "candidates": {"type": "array", "items": {"type": "object", "properties": {
        "n": {"type": "integer"},
        "term": {"type": "boolean"},
        "kind": {"type": "string", "enum": KINDS},
        "party": {"type": "string", "enum": PARTIES},
        "topic": {"type": "string", "enum": TOPICS},
        "deliverable": {"type": "boolean"},
    }}},
    "missed": {"type": "array", "items": _TERM_ITEM},
}})

METHOD = """You read part of a contract between a California common interest development's association and a \
counterparty (a management company, a vendor, a contractor, or a professional firm) and find its terms: what each side \
must do, must not do, may do, or is entitled to; the conditions on them; and the terms stated without such words (the \
term and renewal, the price, the governing law, how disputes are resolved).

kind: duty (must act: "shall", "must", "will", "agrees to", "is responsible for"); prohibition (must not act); \
permission (may act but need not); right (is entitled to); condition (an effect that turns on an event: "shall be \
effective only when", "is late if"); statement (a term stated without a modal: "The term of this Agreement is one \
year", "This Agreement is governed by the laws of ...").
Not terms: a heading alone, a recital ("WHEREAS"), a definition ("shall mean"), a signature or date line, a page \
header or footer, and a list of services that only names a service without saying who provides it.

party: association (the association, its board, officers, or committees); counterparty (the other side, however the \
contract names it: Manager, Contractor, Company, Vendor, or its name); either (either party, each party, the parties); \
other (an owner, a court, an arbitrator, a lender, a third party); unstated.

topic, the review checklist's shelves: """ + ", ".join(f"{t.name.lower()} ({t.value})" for t in Topic) + """.

deliverable: true when the counterparty must produce something the association can ask to see or hold it to: a log or \
roster, a report or statement, an agenda, minutes, a notice, a certificate of insurance, records delivered at the end, \
or any act with a deadline or a schedule. A promise about money the association pays is not a deliverable.

deadline: a time limit as written ("within fourteen (14) days of any termination", "at least four (4) days prior to a \
meeting"), or "". recurrence: how often as written ("monthly", "each quarter"), or "".

quote: words copied exactly, character for character, from the text below, four to forty words, including the words \
that make it a term. Never paraphrase, and never list a term whose words are not in the text."""


def review_prompt(text: str, candidates: list[ContractTerm]) -> str:
    lines = []
    for n, c in enumerate(candidates, 1):
        words = " ".join(c.quote.split())
        lines.append(f"{n}. [{c.kind.value}, {c.party.value}, {c.topic.name.lower()}] {words[:QUOTE_CHARS]}")
    return (METHOD + "\n\nA phrase reader found the candidates below, each with its guess of kind, party, and topic in "
            "[ ]. For each candidate n, say whether it is a term (term: false for a heading, a recital, a definition, a "
            "list of services naming no provider, or a fragment), and give its kind, party, topic, and deliverable. Then "
            "list in missed every term in the text that no candidate covers, with a quote copied exactly; an empty list "
            "when there is none.\n\nText:\n" + text + "\n\nCandidates:\n" + ("\n".join(lines) or "(none)"))


# --- Backends ---------------------------------------------------------------------------------------------------------

class OllamaBackend:
    """A model on this machine. ``fetch(url, payload)`` replaces HTTP in tests."""

    remote = False

    def __init__(self, model: str = "", *, base_url: str = "", fetch: Callable[[str, dict], dict] | None = None,
                 timeout: int = 900, keep_alive: str = "5m", num_ctx: int = 0) -> None:
        from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL

        self.model = model or DEFAULT_MODEL
        self.base_url = (base_url or OLLAMA_URL).rstrip("/")
        if (urlparse(self.base_url).hostname or "") not in LOCAL_HOSTS:
            raise ValueError(f"the Ollama backend reads only through an Ollama on this machine, not {self.base_url}")
        self.num_ctx = num_ctx or DEFAULT_CONTEXT
        self._fetch, self.timeout, self.keep_alive, self._checked = fetch, timeout, keep_alive, False

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def _preflight(self) -> None:
        if self._fetch is not None or self._checked:
            return
        from jason.local_ai import LocalAIUnavailable, preflight

        try:
            preflight(self.model, ollama_url=self.base_url)
        except LocalAIUnavailable as exc:
            raise ModelUnavailable(str(exc)) from exc
        self._checked = True

    def ask(self, prompt: str, schema: dict[str, Any]) -> str:
        self._preflight()
        payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "format": schema,
                   "stream": False, "think": False, "keep_alive": self.keep_alive,
                   "options": {"temperature": 0, "num_ctx": self.num_ctx}}
        if self._fetch is not None:
            data = self._fetch(f"{self.base_url}/api/chat", payload)
        else:
            from urllib.error import URLError
            from urllib.request import Request, urlopen

            from jason.locks import Resource, ResourceBusy, hold

            request = Request(f"{self.base_url}/api/chat", data=json.dumps(payload).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
            try:
                with hold(Resource.GPU, timeout=self.timeout, purpose=f"{self.model} contract terms"), \
                        urlopen(request, timeout=self.timeout) as response:
                    data = json.loads(response.read().decode("utf-8"))
            except ResourceBusy as exc:
                raise ModelUnavailable(f"the model server is busy with another jason process: {exc}") from exc
            except (URLError, OSError) as exc:
                raise ModelUnavailable(f"Ollama at {self.base_url} did not answer: {exc}") from exc
        return str((data.get("message") or {}).get("content") or data.get("response") or "")

    def close(self) -> None:
        if self._fetch is None:
            try:
                from jason.local_ai import unload

                unload(self.model)
            except Exception:  # noqa: BLE001 - Ollama gone already: nothing to unload
                pass


class BedrockBackend:
    """Claude on Amazon Bedrock through the Mantle client (``anthropic[bedrock]``).

    The region is ``region``, else ``JASON_BEDROCK_REGION``, else ``AWS_REGION``; the model ``model``, else
    ``JASON_BEDROCK_MODEL``, else ``BEDROCK_MODEL``; credentials come from the AWS chain (``aws_profile`` or
    ``JASON_BEDROCK_PROFILE``, the environment, or an instance role). jason stores no AWS secret. ``client`` replaces the
    SDK in tests.
    """

    remote = True

    def __init__(self, model: str = "", *, region: str = "", profile: str = "", effort: str = "", client: Any = None,
                 max_tokens: int = 16_000) -> None:
        self.model = model or os.environ.get("JASON_BEDROCK_MODEL", "") or BEDROCK_MODEL
        self.region = region or os.environ.get("JASON_BEDROCK_REGION", "") or os.environ.get("AWS_REGION", "")
        self.profile = profile or os.environ.get("JASON_BEDROCK_PROFILE", "")
        self.effort = effort or os.environ.get("JASON_BEDROCK_EFFORT", "") or "medium"
        self.max_tokens = max_tokens
        self._client = client

    @property
    def name(self) -> str:
        return f"bedrock:{self.model}"

    def _sdk(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.region:
            raise ModelUnavailable("Bedrock needs a region: set JASON_BEDROCK_REGION (or AWS_REGION), or pass --region")
        try:
            from anthropic import AnthropicBedrockMantle
        except ImportError as exc:
            raise ModelUnavailable("the Bedrock backend needs the bedrock extra: pip install -e \".[bedrock]\"") from exc
        kwargs: dict[str, Any] = {"aws_region": self.region}
        if self.profile:
            kwargs["aws_profile"] = self.profile
        self._client = AnthropicBedrockMantle(**kwargs)
        return self._client

    def ask(self, prompt: str, schema: dict[str, Any]) -> str:
        client = self._sdk()
        try:
            import anthropic

            errors: tuple[type[BaseException], ...] = (anthropic.APIError,)
        except ImportError:
            errors = ()
        try:
            response = client.messages.create(
                model=self.model, max_tokens=self.max_tokens, messages=[{"role": "user", "content": prompt}],
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}})
        except errors as exc:  # type: ignore[misc]
            raise ModelUnavailable(f"Bedrock did not answer: {exc}") from exc
        if getattr(response, "stop_reason", "") == "refusal":
            details = getattr(response, "stop_details", None)
            raise ModelUnavailable(f"the model declined ({getattr(details, 'category', None) or 'no category'})")
        return "".join(getattr(b, "text", "") for b in getattr(response, "content", []) if getattr(b, "type", "") == "text")

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()


def backend_named(name: str, *, model: str = "", region: str = "", profile: str = "") -> Backend:
    """``ollama`` or ``bedrock``, by a person's choice on the command line."""
    key = (name or "").strip().lower()
    if key in ("ollama", "local"):
        return OllamaBackend(model)
    if key in ("bedrock", "aws"):
        return BedrockBackend(model, region=region, profile=profile)
    raise ValueError(f"no contract-terms backend named {name!r}: ollama or bedrock")


# --- Merging ----------------------------------------------------------------------------------------------------------

def _load(raw: str) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{.*\}", raw or "", re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _enum(cls: Any, word: Any, default: Any) -> Any:
    word = str(word or "").strip().lower()
    if cls is Topic:
        return next((t for t in Topic if t.name.lower() == word), default)
    try:
        return cls(word)
    except ValueError:
        return default


def _deadline(words: str) -> Deadline | None:
    words = " ".join((words or "").split())
    if not words:
        return None
    return find_deadline(words) or Deadline(words, DeadlineRelation.WITHIN)


TRUST = ("fill", "full")              # how far the model's verdicts replace the grammar's (``merge``)


def merge(raw: str, candidates: list[ContractTerm], text: str, *, base: int, source: str, backend: str,
          sections: list[tuple[int, int, str, str]], trust: str = "fill"
          ) -> tuple[list[ContractTerm], list[dict[str, Any]]]:
    """The candidates with the model's verdicts, and its missed terms whose quotes are in ``text`` (the batch's words,
    which start at ``base`` in the document). ``sections`` are (start, end, number, caption) in document offsets, to
    place a missed term.

    ``trust`` "fill" (the default) keeps the grammar's kind, topic, and deliverable flag and drops nothing the grammar
    read with a modal; the model only fills a party the grammar left unstated, drops a modal-less statement it calls no
    term, and adds the terms it found that the grammar missed. "full" takes the model's kind, party, topic, and
    deliverable flag and drops whatever it calls no term. A small local model measured worse than the grammar on the
    fields the grammar reads (docs/document-tools.md, Model trials), as the duty review found before it
    (``duty_model.merge_review(fill_only=True)``)."""
    data = _load(raw)
    if data is None or not isinstance(data.get("candidates"), list):
        return list(candidates), [{"why": "the model's answer is not JSON with a list of candidates",
                                   "raw": (raw or "")[:300]}]
    method = f"hybrid:{backend}"
    verdicts = {v["n"]: v for v in data["candidates"] if isinstance(v, dict) and isinstance(v.get("n"), int)}
    out, dropped = [], []
    for n, c in enumerate(candidates, 1):
        v = verdicts.get(n)
        if v is None:
            out.append(c)
            continue
        if not v.get("term", True) and (trust == "full" or c.kind is TermKind.STATEMENT):
            dropped.append({"why": "the model calls it no term", "candidate": c.quote[:200], "section": c.section})
            continue
        if trust == "full":
            out.append(replace(c, kind=_enum(TermKind, v.get("kind"), c.kind),
                               party=_enum(Party, v.get("party"), c.party), topic=_enum(Topic, v.get("topic"), c.topic),
                               deliverable=bool(v.get("deliverable", c.deliverable)), method=method))
        elif c.party is Party.UNSTATED:
            party = _enum(Party, v.get("party"), c.party)
            filled = replace(c, party=party, method=method)
            # A party the model names can make a duty a deliverable; the grammar's rule decides, as for its own terms.
            out.append(replace(_particulars(filled, ""), method=method) if party is not Party.UNSTATED else filled)
        else:
            out.append(c)
    for item in data.get("missed") or ():
        made = _missed(item, text, base=base, source=source, method=method, sections=sections)
        if isinstance(made, ContractTerm):
            if any(o.start < made.end and made.start < o.end for o in out):
                continue
            out.append(made)
        else:
            dropped.append({"why": made, "item": item})
    return out, dropped


def _missed(item: Any, text: str, *, base: int, source: str, method: str,
            sections: list[tuple[int, int, str, str]]) -> ContractTerm | str:
    if not isinstance(item, dict):
        return "not an object"
    quote = str(item.get("quote") or "").strip()
    span = find_quote(text, quote)
    if span is None:
        return "its quote is not in the text"
    kind = _enum(TermKind, item.get("kind"), None)
    party = _enum(Party, item.get("party"), Party.UNSTATED)
    topic = _enum(Topic, item.get("topic"), Topic.SCOPE)
    if kind is None:
        return "a kind jason does not define"
    s, e = base + span[0], base + span[1]
    number, caption = next(((num, cap) for ss, se, num, cap in sections if ss <= s < se), ("", ""))
    recurrence, months = find_recurrence(str(item.get("recurrence") or ""))
    words = text[span[0]:span[1]]
    term = ContractTerm(source=source, section=number, caption=caption, start=s, end=e, quote=words, kind=kind,
                        party=party, topic=topic, action=" ".join(str(item.get("action") or "").split())[:240],
                        deadline=_deadline(str(item.get("deadline") or "")),
                        recurrence=recurrence or " ".join(str(item.get("recurrence") or "").split()),
                        recurrence_months=months, notice=topic is Topic.NOTICE, method=method)
    filled = _particulars(term, "")
    return replace(filled, deliverable=bool(item.get("deliverable")) and party is Party.COUNTERPARTY,
                   delivery=filled.delivery or (deliveries(words) if topic is Topic.NOTICE else ()),
                   window_days=filled.window_days or window_of(words))


def batches(sections: list[tuple[int, int, str, str]], limit: int = BATCH_CHARS) -> list[tuple[int, int]]:
    """Runs of whole sections up to ``limit`` characters (a longer section is a batch of its own)."""
    out: list[tuple[int, int]] = []
    start = end = None
    for s, e, _, _ in sections:
        if start is None:
            start, end = s, e
        elif e - start > limit:
            out.append((start, end))
            start, end = s, e
        else:
            end = e
    if start is not None:
        out.append((start, end))
    return out


def review(text: str, terms: list[ContractTerm], backend: Backend, *, source: str,
           sections: list[tuple[int, int, str, str]], trust: str = "fill",
           log: Callable[[str], None] = lambda s: None) -> tuple[list[ContractTerm], list[dict[str, Any]]]:
    """Every batch of sections asked once; the merged terms in document order, and what was dropped."""
    out: list[ContractTerm] = []
    dropped: list[dict[str, Any]] = []
    spans = batches(sections)
    for n, (s, e) in enumerate(spans, 1):
        chunk = text[s:e]
        cands = [t for t in terms if s <= t.start < e]
        prompt = review_prompt(chunk, cands)
        raw = backend.ask(prompt, REVIEW_SCHEMA)
        if _load(raw) is None:                       # one more ask when the answer is not JSON at all
            log(f"{backend.name}: batch {n} answered without JSON; asking once more")
            raw = backend.ask(prompt, REVIEW_SCHEMA)
        kept, lost = merge(raw, cands, chunk, base=s, source=source, backend=backend.name, sections=sections,
                           trust=trust)
        out += kept
        dropped += lost
        log(f"{backend.name}: batch {n} of {len(spans)}: {len(cands)} candidates, {len(kept)} kept")
    out += [t for t in terms if not any(s <= t.start < e for s, e in spans)]
    return sorted(out, key=lambda t: (t.start, t.end)), dropped


__all__ = ["Backend", "OllamaBackend", "BedrockBackend", "BEDROCK_MODEL", "ModelUnavailable", "REVIEW_SCHEMA",
           "review_prompt", "backend_named", "merge", "review", "batches"]
