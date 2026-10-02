"""A reader that asks a language model to fill the concept records from the page images.

The county's copies are poor scans, and a model reading the page images
sees a broken stamp and a dropped digit the way a person does. This
extractor renders each page with PyMuPDF, sends the images with a prompt
that names the records in ``readings`` as the answer's shape, and parses
the JSON that comes back into a ``DocumentReading``. It needs the
``anthropic`` package (the ``models`` extra) and a key in
``ANTHROPIC_API_KEY``; without either it fails fast and nothing is sent.
A model's reading is evidence like any other: it is scored by
``extraction.evaluate`` against the pinned facts, and it pins nothing.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.readings import AnnexedProperty, Citation, DocumentKindGuess, DocumentReading, Relation, Stamp

MODEL = "claude-fable-5-1"
MAX_PAGES = 8
DPI = 110

PROMPT = """You are reading a scanned instrument from the Sacramento County recorder's official records. Read the page images and answer with one JSON object and nothing else, with these keys:
- "number": the instrument's own twelve-digit document number from the recorder's stamp (Doc# or BOOK yyyymmdd PAGE nnnn joined), or "" if the copy carries no stamp.
- "recorded": the recording date from the stamp as YYYY-MM-DD, or "".
- "pages": the page count the stamp prints, or null.
- "unrecorded_copy": true when the copy shows the recorder's box but no stamp.
- "title": the instrument's title as printed.
- "phase": the phase number in the title, or null.
- "declarant": who made the instrument, as the text says, or "".
- "annexed": {"first_unit": int or null, "last_unit": int or null, "association_common_area": int or null, "condominium_common_area": int or null} for the property an annexation covers.
- "citations": a list of {"number": twelve digits, "recorded": "YYYY-MM-DD" or "", "title": the cited instrument's name, "relation": one of "rescinds", "amends", "annexes_under", "relies_on", "plan", "map", "references"} for every earlier instrument the text names by document number, with the relation the sentence states.
- "sections": the section numbers an amendment says it amends, deletes, adds, or restates, as strings.
Read digits carefully; a stamp's digits are more reliable than a recital's. Do not guess a value the pages do not show."""


class ExtractionUnavailable(RuntimeError):
    """The model extractor cannot run here: no package or no key."""


class ClaudeExtractor:
    name = "claude"

    def __init__(self, *, client: Any = None, model: str = MODEL, api_key: str | None = None) -> None:
        self._client = client
        self.model = model
        self._api_key = api_key

    def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        key = self._api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ExtractionUnavailable("no ANTHROPIC_API_KEY; the model extractor sends nothing without one")
        try:
            import anthropic
        except ImportError as exc:
            raise ExtractionUnavailable('the anthropic package is not installed; pip install -e ".[models]"') from exc
        self._client = anthropic.Anthropic(api_key=key)
        return self._client

    def extract(self, path: Path) -> DocumentReading:
        client = self._connect()
        images = page_images(path)
        content: list[dict[str, Any]] = [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image}} for image in images
        ]
        content.append({"type": "text", "text": PROMPT})
        response = client.messages.create(model=self.model, max_tokens=2000, messages=[{"role": "user", "content": content}])
        text = "".join(getattr(block, "text", "") for block in getattr(response, "content", []) if getattr(block, "type", "") == "text")
        return parse_answer(text, path)


def page_images(path: Path, *, max_pages: int = MAX_PAGES, dpi: int = DPI) -> list[str]:
    """The first pages of a PDF as base64 PNGs, rendered with PyMuPDF."""
    import base64

    import pymupdf

    document = pymupdf.open(path)
    found: list[str] = []
    for index in range(min(document.page_count, max_pages)):
        pixmap = document[index].get_pixmap(dpi=dpi)
        found.append(base64.b64encode(pixmap.tobytes("png")).decode("ascii"))
    return found


_RELATIONS = {
    "rescinds": Relation.RESCINDS, "amends": Relation.AMENDS, "annexes_under": Relation.ANNEXES_UNDER,
    "relies_on": Relation.RELIES_ON, "plan": Relation.PLAN, "map": Relation.MAP, "references": Relation.REFERENCES,
}


def parse_answer(text: str, path: Path | str = "") -> DocumentReading:
    """The model's JSON as a ``DocumentReading``. A malformed answer reads as an empty document."""
    body = text.strip()
    match = re.search(r"\{.*\}", body, re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        data = {}
    number = "".join(ch for ch in str(data.get("number") or "") if ch.isdigit())
    if len(number) != 12:
        number = ""
    stamp = Stamp(number, _day(data.get("recorded")), _int(data.get("pages")), None, None, bool(data.get("unrecorded_copy")) and not number)
    annexed_data = data.get("annexed") or {}
    annexed = AnnexedProperty(
        _int(annexed_data.get("first_unit")), _int(annexed_data.get("last_unit")),
        (_int(annexed_data.get("association_common_area")),) if _int(annexed_data.get("association_common_area")) else (),
        (_int(annexed_data.get("condominium_common_area")),) if _int(annexed_data.get("condominium_common_area")) else (),
    )
    citations = []
    for item in data.get("citations") or []:
        cited = "".join(ch for ch in str(item.get("number") or "") if ch.isdigit())
        if len(cited) != 12 or cited == number:
            continue
        citations.append(Citation(cited, _day(item.get("recorded")), str(item.get("title") or ""), _RELATIONS.get(str(item.get("relation") or "").lower(), Relation.REFERENCES), "model"))
    title = str(data.get("title") or "")
    kind = _kind(title)
    phase = _int(data.get("phase"))
    if phase is None:
        # The models leave the phase field empty and put it in the title; the title is the phase's source anyway.
        hit = re.search(r"\bPHASE\s+(\d{1,2})\b", title, re.I)
        phase = int(hit.group(1)) if hit else None
    return DocumentReading(
        Path(path), kind, title, stamp, phase, tuple(citations), annexed,
        str(data.get("declarant") or ""), tuple(str(s) for s in data.get("sections") or []), len(body),
    )


def _kind(title: str) -> DocumentKindGuess:
    upper = title.upper()
    if "ANNEXATION" in upper:
        return DocumentKindGuess.ANNEXATION
    if "AMENDMENT" in upper:
        return DocumentKindGuess.AMENDMENT
    if "DECLARATION" in upper:
        return DocumentKindGuess.DECLARATION
    if "PLAN" in upper:
        return DocumentKindGuess.CONDOMINIUM_PLAN
    if "DEED" in upper:
        return DocumentKindGuess.DEED
    return DocumentKindGuess.OTHER


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None
