"""A reader that asks a local vision model, through Ollama, to fill the concept records from the page images.

Ollama runs on this machine and serves models without a key, so this is
the reader to try first on the scans nothing else can read. It renders the
pages with PyMuPDF, posts them to Ollama's chat endpoint with a JSON
schema as the required output shape (Ollama's ``format`` field), and
parses the answer with the same parser the Claude reader uses. It needs a
model that accepts images; a text-only model returns nothing useful, and
``available`` says which local models can see. A reading is evidence: the
scorecard says what to trust, and nothing is pinned by being read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from jason.community.model_extractor import PROMPT, page_images, parse_answer
from jason.community.readings import DocumentReading

OLLAMA_URL = "http://localhost:11434"
# The one local model jason's readers, the classifier, and OCR share, at one context window:
# Ollama reloads a model whose num_ctx differs, and a second large model does not fit beside it and the embedder
# on the 32 GB card (qwen3.6:27b at 65536 is 20.6 GB; qwen3-embedding:8b is 6.6 GB).
DEFAULT_MODEL = "qwen3.6:27b"
DEFAULT_CONTEXT = 65536

# Ollama constrains the answer to this schema, so the parser never sees prose.
READING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "number": {"type": "string"},
        "recorded": {"type": "string"},
        "pages": {"type": ["integer", "null"]},
        "unrecorded_copy": {"type": "boolean"},
        "title": {"type": "string"},
        "phase": {"type": ["integer", "null"]},
        "declarant": {"type": "string"},
        # Required, and null where the instrument annexes nothing: an optional object is one a model may leave out.
        "annexed": {
            "type": "object",
            "properties": {
                "first_unit": {"type": ["integer", "null"]},
                "last_unit": {"type": ["integer", "null"]},
                "association_common_area": {"type": ["integer", "null"]},
                "condominium_common_area": {"type": ["integer", "null"]},
            },
            "required": ["first_unit", "last_unit", "association_common_area", "condominium_common_area"],
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "string"},
                    "recorded": {"type": "string"},
                    "title": {"type": "string"},
                    "relation": {"type": "string", "enum": ["rescinds", "amends", "annexes_under", "relies_on", "plan", "map", "references"]},
                },
                "required": ["number", "relation"],
            },
        },
        "sections": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["number", "title", "phase", "annexed", "citations"],
}


class OllamaUnavailable(RuntimeError):
    """Ollama is not running here, or no local model accepts images."""


GENERATES = ("/api/chat", "/api/generate", "/api/embed")


def _post(url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    """POST to Ollama. A request that runs a model holds the GPU lock (``jason.locks``), so jason's processes send one
    at a time and never make Ollama load two models at once; a metadata call (``/api/show``) does not wait for it."""
    from contextlib import nullcontext

    from jason.locks import Resource, hold

    request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
    gate = hold(Resource.GPU, timeout=timeout, purpose=f"{payload.get('model', '')} {url.rsplit('/', 1)[-1]}") \
        if url.endswith(GENERATES) else nullcontext()
    with gate, urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def _get(url: str, timeout: int = 5) -> dict[str, Any]:
    with urlopen(Request(url), timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def vision_models(base_url: str = OLLAMA_URL, *, fetch=None) -> tuple[str, ...]:
    """The local models whose capabilities include vision, else empty; empty too when Ollama is down."""
    getter = fetch or (lambda url, payload=None: _get(url) if payload is None else _post(url, payload, 10))
    try:
        names = [item["name"] for item in getter(f"{base_url}/api/tags").get("models", [])]
    except Exception:
        return ()
    found: list[str] = []
    for name in names:
        try:
            detail = getter(f"{base_url}/api/show", {"name": name})
        except Exception:
            continue
        if "vision" in (detail.get("capabilities") or []):
            found.append(name)
    return tuple(found)


class OllamaExtractor:
    name = "ollama"

    def __init__(self, *, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_URL, fetch=None, timeout: int = 600, max_pages: int = 6) -> None:
        self.model = model
        self.base_url = base_url
        self._fetch = fetch
        self.timeout = timeout
        self.max_pages = max_pages

    def check(self) -> None:
        """Fail fast when Ollama is down or the model is not a local vision model."""
        seen = vision_models(self.base_url, fetch=self._fetch)
        if not seen:
            raise OllamaUnavailable(f"no local model at {self.base_url} accepts images; pull one, for example: ollama pull {DEFAULT_MODEL}")
        if self.model not in seen and not any(name.startswith(self.model) for name in seen):
            raise OllamaUnavailable(f"{self.model} is not a local vision model; local vision models: {', '.join(seen)}")
        if self._fetch is None:
            from jason.local_ai import LocalAIUnavailable, preflight

            try:
                preflight(self.model, ollama_url=self.base_url)
            except LocalAIUnavailable as exc:
                raise OllamaUnavailable(str(exc)) from exc

    def extract(self, path: Path) -> DocumentReading:
        """Read without thinking first; ask again with thinking only when the stamp's number comes back empty.

        On September 30, 2026 qwen3.6:27b without thinking read the eight pinned cases in 2.4 minutes with every unit
        range and common area, and missed only the 2007 CC&Rs' stamp; with thinking it read that stamp but took 90 s a
        file and dropped the phase 2 annexation's unit range and common area.
        """
        images = page_images(path, max_pages=self.max_pages)
        reading = parse_answer(self._ask(images, think=False), path)
        if not (reading.number or "").strip():
            reading = parse_answer(self._ask(images, think=True), path)
        return reading

    def _ask(self, images: list[str], *, think: bool) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "think": think,
            "format": READING_SCHEMA,
            "options": {"temperature": 0, "num_ctx": DEFAULT_CONTEXT},
            "messages": [{"role": "user", "content": PROMPT, "images": images}],
        }
        poster = self._fetch or (lambda url, body: _post(url, body, self.timeout))
        answer = poster(f"{self.base_url}/api/chat", payload)
        return (answer.get("message") or {}).get("content", "") if isinstance(answer, dict) else ""
