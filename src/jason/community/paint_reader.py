"""Read a paint schedule from its picture with a local vision model.

A palette is often only an image: a scan or export of the developer's table, surfaces down the left and scheme numbers
across the top, a swatch over each printed code and name. This reader sends the picture to the local vision model
(Ollama; the one model jason's other readers share) with a JSON schema as the required answer, and turns the answer into
a ``PaintSchedule``. The prompt names kinds (a table, surfaces, schemes, codes, names), never a community's colors.

A reading is evidence. The model can misread a digit, so the reading is checked against the maker's catalog
(``paint.check``): a code the catalog does not have, or one under another name, is a misreading or a rename, and either
way a person looks. Nothing is pinned by being read.
"""

from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any

from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL, OllamaUnavailable, _post
from jason.community.paint import Maker, PaintRow, PaintSchedule, PaintSpec, Surface

PROMPT = (
    "This image is a paint or exterior materials schedule: a title block, then a table with a scheme number in each "
    "column heading and a surface name at the start of each row. Under each surface a color swatch sits above its "
    "printed color code and color name. Read the title, who it was prepared for, and its date or job number. Then list "
    "each surface row with, for every scheme column that has a color, the scheme number, the code, and the name, copied "
    "exactly as printed (keep the maker's letters in the code). A surface name may continue on a second line (a product "
    "or material); put that second line in note. A column with no color is left out. Do not guess text you cannot read: "
    "leave it empty."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "prepared": {"type": "string"},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "note": {"type": "string"},
                    "colors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"scheme": {"type": "integer"}, "code": {"type": "string"}, "name": {"type": "string"}},
                            "required": ["scheme", "code", "name"],
                        },
                    },
                },
                "required": ["label", "note", "colors"],
            },
        },
    },
    "required": ["title", "prepared", "rows"],
}

SURFACE_WORDS = (
    (Surface.FASCIA, ("fascia", "soffit", "eave")),
    (Surface.TRIM, ("trim",)),
    (Surface.FIELD, ("field", "body", "main wall")),
    (Surface.ENTRY_DOORS, ("entry", "front door")),
    (Surface.GARAGE_DOORS, ("garage",)),
    (Surface.WINDOWS, ("window",)),
    (Surface.RAILINGS, ("rail", "balcon")),
    (Surface.ROOF, ("roof", "tile", "shingle")),
)
MAKER_CODE = re.compile(r"^SW\s*\d{4,5}$", re.IGNORECASE)


def surface_of(label: str) -> Surface:
    text = label.lower()
    return next((surface for surface, words in SURFACE_WORDS if any(w in text for w in words)), Surface.OTHER)


def schedule_from(answer: dict[str, Any], source: str = "") -> PaintSchedule:
    """The model's answer as a schedule. A code in the maker's form is a Sherwin-Williams color, written "SW 7027"."""
    rows: list[PaintRow] = []
    for raw in answer.get("rows") or ():
        specs = []
        for color in raw.get("colors") or ():
            code = re.sub(r"\s+", " ", str(color.get("code", "")).strip())
            if not code:
                continue
            sw = bool(MAKER_CODE.match(code))
            if sw:
                code = "SW " + re.sub(r"\D", "", code)
            specs.append(PaintSpec(int(color.get("scheme") or 1), code, str(color.get("name", "")).strip().title(),
                                   Maker.SHERWIN_WILLIAMS if sw else Maker.OTHER))
        label = str(raw.get("label", "")).strip()
        if label and specs:
            rows.append(PaintRow(surface_of(label), label.upper(), tuple(specs), str(raw.get("note", "")).strip()))
    return PaintSchedule(title=str(answer.get("title", "")).strip(), rows=tuple(rows), source=source,
                         prepared=str(answer.get("prepared", "")).strip())


def read_schedule(path: Path, *, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_URL, timeout: int = 600,
                  post=None) -> PaintSchedule:
    """Ask the local model to read the picture. Fails fast (``OllamaUnavailable``) when Ollama or the model is not
    ready, before anything is sent; ``post`` replaces the HTTP call in tests."""
    if post is None:
        from jason.local_ai import LocalAIUnavailable, preflight

        try:
            preflight(model, ollama_url=base_url)
        except LocalAIUnavailable as exc:
            raise OllamaUnavailable(str(exc)) from exc
        post = lambda url, body: _post(url, body, timeout)  # noqa: E731
    image = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    payload = {
        "model": model, "stream": False, "think": False, "format": SCHEMA,
        "options": {"temperature": 0, "num_ctx": DEFAULT_CONTEXT},
        "messages": [{"role": "user", "content": PROMPT, "images": [image]}],
    }
    answer = post(f"{base_url}/api/chat", payload)
    content = (answer.get("message") or {}).get("content", "") if isinstance(answer, dict) else ""
    try:
        data = json.loads(content)
    except ValueError as exc:
        raise OllamaUnavailable(f"the model's answer was not JSON: {content[:200]!r}") from exc
    return schedule_from(data, source=str(path))


def differences(read: PaintSchedule, known: PaintSchedule) -> tuple[str, ...]:
    """What the reading has that the known schedule lacks, and the reverse, by surface, scheme, and code."""
    mine = {(r.surface, s.scheme, s.code) for r, s in read.specs()}
    theirs = {(r.surface, s.scheme, s.code) for r, s in known.specs()}
    lines = [f"read, not on the schedule: {s.value} scheme {n} {c}" for s, n, c in sorted(mine - theirs, key=str)]
    lines += [f"on the schedule, not read: {s.value} scheme {n} {c}" for s, n, c in sorted(theirs - mine, key=str)]
    return tuple(lines)
