"""The best text on file for an attachment: the text layer when it reads, else the cached OCR text, the vision model's first."""

from __future__ import annotations

import hashlib
from pathlib import Path

from jason.tasks.invoice_review import TEXT_CACHE, best_text


def test_a_glyph_coded_layer_gives_way_to_the_vision_models_reading(tmp_path: Path) -> None:
    pdf = tmp_path / "notice.pdf"
    pdf.write_bytes(b"%PDF-1.4 renewal notice")
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    cache = tmp_path / "payhoa" / TEXT_CACHE
    cache.mkdir(parents=True)
    (cache / f"{digest}.txt").write_text("\x00\x01\x01\x03\x03\x01\x04" * 20, encoding="utf-8")        # glyph codes
    (cache / f"{digest}.pymupdf-tesseract.txt").write_text("P aD OPO HILADELPHIA 5010O12496", encoding="utf-8")
    (cache / f"{digest}.ollama-vision.txt").write_text("PHILADELPHIA Policy Number 5010000096 BLDG 2", encoding="utf-8")
    assert best_text(tmp_path, pdf) == "PHILADELPHIA Policy Number 5010000096 BLDG 2"


def test_a_readable_layer_is_used_as_it_is_and_nothing_reads_as_empty(tmp_path: Path) -> None:
    pdf = tmp_path / "invoice.pdf"
    pdf.write_bytes(b"%PDF-1.4 invoice")
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    cache = tmp_path / "payhoa" / TEXT_CACHE
    cache.mkdir(parents=True)
    (cache / f"{digest}.txt").write_text("INVOICE 1-5MS Total $850.00", encoding="utf-8")
    assert best_text(tmp_path, pdf) == "INVOICE 1-5MS Total $850.00"
    assert best_text(tmp_path, tmp_path / "missing.pdf") == ""
