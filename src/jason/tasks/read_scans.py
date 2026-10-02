"""Read the image-only governing copies with the local vision model and keep what it said.

A model's reading is evidence, so it is kept apart from the extracts the
parsers read: one JSON per file under ``data/readings/``, with the model
and the day. The records request reads that folder to say which missing
instruments a copy on disk may already be, flagged for a person to verify
against the stamp before dropping the order. Nothing here pins a fact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from jason.community.ocr import image_only
from jason.community.readings import reading_dict

FOLDERS = ("artifacts/site-docs/governing_documents", "artifacts/site-docs/governing_documents_Annexations")


@dataclass
class ScanReport:
    model: str = ""
    read: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"read scans model={self.model or 'none'} read={len(self.read)} skipped={len(self.skipped)} errors={len(self.errors)}"


def readings_folder(root: Path) -> Path:
    return root / "readings"


def read_image_only(root: Path, reader, *, only_image_only: bool = True, refresh: bool = False) -> ScanReport:
    """Run the reader over each image-only PDF in the governing folders and store the reading."""
    report = ScanReport(model=getattr(reader, "model", getattr(reader, "name", "")))
    out = readings_folder(root)
    out.mkdir(parents=True, exist_ok=True)
    for folder in FOLDERS:
        base = root / folder
        for path in sorted(base.glob("*.pdf")) if base.is_dir() else ():
            target = out / f"{path.name}.json"
            if target.is_file() and not refresh:
                report.skipped.append(f"{path.name}: already read")
                continue
            if only_image_only and not image_only(path):
                report.skipped.append(path.name)
                continue
            try:
                reading = reader.extract(path)
            except Exception as exc:
                report.errors.append(f"{path.name}: {exc}")
                continue
            store_reading(target, reading, model=report.model, source=path)
            report.read.append(path.name)
    return report


def store_reading(target: Path, reading, *, model: str, source: Path) -> None:
    payload = {"file": source.name, "folder": str(source.parent), "model": model, "read": date.today().isoformat(), **reading_dict(reading)}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")


def model_read_numbers(root: Path) -> dict[str, dict[str, str]]:
    """Instrument number to the copy a model read it from, for every stored reading with a number."""
    found: dict[str, dict[str, str]] = {}
    folder = readings_folder(root)
    if not folder.is_dir():
        return found
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        number = "".join(ch for ch in str(data.get("number") or "") if ch.isdigit())
        if len(number) == 12:
            found[number] = {"file": str(data.get("file") or path.stem), "model": str(data.get("model") or ""), "read": str(data.get("read") or "")}
    return found
