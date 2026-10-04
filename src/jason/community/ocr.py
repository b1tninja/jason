"""Re-reading an image-only PDF into a text layer, so the readers and the passage search cover it.

Three of the governing copies on Drive extract to nothing: the scanner
left no text layer. The fix is OCR into a ``.pdf.md`` beside the PDF, the
same shape the other extracts have, so nothing downstream changes. The
engines, best first: a local vision model on Ollama (``OllamaVisionOcr``,
when Ollama is running with the model pulled); Docling, a Python package
with a Python-only OCR engine (RapidOCR) that runs on Python 3.14 from
Docling 2.59; and PyMuPDF's own OCR, which needs Tesseract's language data. ``engines`` says
which can run, and a run with none writes nothing and says so. OCR output is a text layer, not a fact: the
readers and the scorecard still decide what it says.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol


class OcrEngine(Protocol):
    name: str

    def text_of(self, path: Path) -> str: ...


class PyMuPdfTesseract:
    """PyMuPDF's page OCR, which shells out to Tesseract; ``available`` is whether that works here."""

    name = "pymupdf-tesseract"

    def __init__(self, *, dpi: int = 200, language: str = "eng") -> None:
        self.dpi = dpi
        self.language = language

    @staticmethod
    def tessdata() -> str:
        """Tesseract's language data: ``TESSDATA_PREFIX``, a per-user unpack, or a machine install; empty when none.

        PyMuPDF carries the Tesseract engine itself; it needs only this folder. A per-user copy
        (``%LOCALAPPDATA%\\Programs\\Tesseract-OCR``) needs no administrator rights.
        """
        import os

        candidates = [os.environ.get("TESSDATA_PREFIX", "")]
        for root in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
            if root:
                base = Path(root) / ("Programs" if root == os.environ.get("LOCALAPPDATA") else "") / "Tesseract-OCR" / "tessdata"
                candidates.append(str(base))
        for candidate in candidates:
            if candidate and (Path(candidate) / "eng.traineddata").is_file():
                return candidate
        try:
            import pymupdf

            return pymupdf.get_tessdata() or ""
        except Exception:
            return ""

    @classmethod
    def available(cls) -> bool:
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            return False
        return bool(cls.tessdata())

    def text_of(self, path: Path) -> str:
        import pymupdf

        tessdata = self.tessdata()
        pages: list[str] = []
        with pymupdf.open(path) as document:
            for page in document:
                textpage = page.get_textpage_ocr(dpi=self.dpi, language=self.language, full=True, tessdata=tessdata)
                pages.append(page.get_text(textpage=textpage))
        return "\n\n".join(pages)


@dataclass(frozen=True)
class TesseractWord:
    """One word as Tesseract's own command-line tool read it (its ``tsv`` output), with its box and confidence."""

    page: int
    block: int
    paragraph: int
    line: int
    left: int                        # pixels at the rendering's dpi
    top: int
    width: int
    height: int
    confidence: float                # Tesseract's, 0 to 100
    text: str


def parse_tsv(tsv: str, page: int = 0) -> list[TesseractWord]:
    """The words of one page's ``tesseract IMAGE stdout tsv`` output."""
    out = []
    for row in tsv.splitlines()[1:]:
        cells = row.split("\t")
        if len(cells) < 12 or cells[0] != "5" or not cells[11].strip():
            continue
        try:
            nums = [int(c) for c in cells[2:5]] + [int(c) for c in cells[6:10]]
            conf = float(cells[10])
        except ValueError:
            continue
        out.append(TesseractWord(page, nums[0], nums[1], nums[2], nums[3], nums[4], nums[5], nums[6], conf,
                                 cells[11].strip()))
    return out


class TesseractCli:
    """Tesseract's own command-line tool, reading a rendered page into words with their boxes and confidences.

    PyMuPDF runs the same engine, but builds words itself from the characters' positions and loses the narrow spaces
    of justified type: on a recorded declaration it ran about one word in thirty into the next ("ofthe", "Notmore"),
    where the tool's own words did not (WER 8.1% against 2.2%, the same model and resolution; docs/ocr-correction.md).
    The tool is the per-user unpack PyMuPDF already uses for its language data, or ``TESSERACT_EXE``."""

    name = "tesseract-cli"

    def __init__(self, *, dpi: int = 300, language: str = "eng", timeout: int = 120) -> None:
        self.dpi = dpi
        self.language = language
        self.timeout = timeout

    @staticmethod
    def exe() -> str:
        import os
        import shutil

        candidates = [os.environ.get("TESSERACT_EXE", "")]
        for root in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
            if root:
                sub = "Programs" if root == os.environ.get("LOCALAPPDATA") else ""
                candidates.append(str(Path(root) / sub / "Tesseract-OCR" / "tesseract.exe"))
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return candidate
        return shutil.which("tesseract") or ""

    @classmethod
    def available(cls) -> bool:
        try:
            import pymupdf  # noqa: F401
        except ImportError:
            return False
        return bool(cls.exe())

    def page_words(self, page: Any, number: int = 0) -> list[TesseractWord]:
        """One PyMuPDF page's words, rendered at ``dpi`` in gray and read by the tool."""
        import os
        import subprocess
        import tempfile

        import pymupdf

        pix = page.get_pixmap(dpi=self.dpi, colorspace=pymupdf.csGRAY)
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "page.png"
            pix.save(str(image))
            env = dict(os.environ)
            tessdata = PyMuPdfTesseract.tessdata()
            if tessdata:
                env["TESSDATA_PREFIX"] = tessdata
            done = subprocess.run([self.exe(), str(image), "stdout", "-l", self.language, "tsv"], capture_output=True,
                                  timeout=self.timeout, env=env, check=False)
        return parse_tsv(done.stdout.decode("utf-8", errors="replace"), number)

    def words(self, path: Path, *, pages: tuple[int, ...] = ()) -> list[TesseractWord]:
        import pymupdf

        out: list[TesseractWord] = []
        with pymupdf.open(path) as document:
            for number in pages or range(document.page_count):
                out += self.page_words(document[number], number)
        return out

    def text_of(self, path: Path) -> str:
        """The pages' text: a line per Tesseract line, a blank line between its blocks, pages apart."""
        pages: dict[int, list[TesseractWord]] = {}
        for w in self.words(path):
            pages.setdefault(w.page, []).append(w)
        out = []
        for number in sorted(pages):
            lines: dict[tuple[int, int, int], list[str]] = {}
            for w in pages[number]:
                lines.setdefault((w.block, w.paragraph, w.line), []).append(w.text)
            text, last = [], None
            for key, ws in lines.items():
                if last is not None and key[:2] != last[:2]:
                    text.append("")
                text.append(" ".join(ws))
                last = key
            out.append("\n".join(text))
        return "\n\n".join(out)


class DoclingRapidOcr:
    """Docling's converter with full-page OCR through RapidOCR; installs with ``pip install "docling[rapidocr]"``."""

    name = "docling-rapidocr"

    @staticmethod
    def available() -> bool:
        try:
            import docling  # noqa: F401
        except ImportError:
            return False
        return True

    def text_of(self, path: Path) -> str:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption

        options = PdfPipelineOptions()
        options.do_ocr = True
        options.ocr_options = RapidOcrOptions(force_full_page_ocr=True)
        converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        return converter.convert(str(path)).document.export_to_markdown()


from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL

# The shared local model, at the shared window: Ollama reloads a model whose
# context differs, so OCR asks for the same window rather than a smaller one.
OLLAMA_OCR_MODEL = DEFAULT_MODEL
OLLAMA_OCR_CONTEXT = DEFAULT_CONTEXT
OLLAMA_OCR_PROMPT = (
    "Transcribe every word printed or handwritten on this page, exactly as written, in reading order. "
    "Keep line breaks. Write a table as rows with ' | ' between cells. Include stamps, headers, footers, "
    "and form labels with their filled-in values. Do not summarize, correct, translate, or explain. "
    "Write [illegible] for anything you cannot read; never guess. Output only the transcription."
)


class OllamaVisionOcr:
    """A local vision model on Ollama, reading one rendered page per request.

    It reads what Tesseract garbles (stamps, tables, handwriting, skewed
    scans), at a few seconds a page on the GPU. It is still a model: the
    prompt asks for ``[illegible]`` over a guess, and the readers and the
    scorecard decide what the text says. ``JASON_OCR_MODEL`` names another
    model; ``JASON_OCR_OLLAMA=0`` turns the engine off (the tests do).
    """

    name = "ollama-vision"

    def __init__(self, *, model: str = "", base_url: str = OLLAMA_URL, dpi: int = 150, max_pages: int | None = None,
                 timeout: int = 300, fetch=None) -> None:
        import os

        self.model = model or os.environ.get("JASON_OCR_MODEL") or OLLAMA_OCR_MODEL
        self.base_url = base_url.rstrip("/")
        self.dpi = dpi
        self.max_pages = max_pages
        self.timeout = timeout
        self._fetch = fetch

    def available(self) -> bool:
        import os

        if os.environ.get("JASON_OCR_OLLAMA", "1") == "0":
            return False
        if not _vision_ready(self.base_url, self.model):
            return False
        if self._fetch is None:
            # On the CPU, or short of memory, the vision model would crawl or crash; the next engine reads instead.
            from jason.local_ai import LocalAIUnavailable, preflight

            try:
                preflight(self.model, ollama_url=self.base_url)
            except LocalAIUnavailable:
                return False
        return True

    def page_text(self, image_png_b64: str) -> str:
        """One page image's transcription."""
        import re

        from jason.community.ollama_extractor import _post

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": OLLAMA_OCR_PROMPT, "images": [image_png_b64]}],
            "stream": False,
            "think": False,
            "keep_alive": "5m",
            "options": {"temperature": 0, "num_ctx": OLLAMA_OCR_CONTEXT, "num_predict": 4096},
        }
        poster = self._fetch or (lambda url, body: _post(url, body, self.timeout))
        answer = poster(f"{self.base_url}/api/chat", payload)
        text = str((answer.get("message") or {}).get("content") or "")
        return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()

    def text_of(self, path: Path) -> str:
        import base64

        if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
            if path.suffix.lower() in (".tif", ".tiff"):
                import pymupdf

                with pymupdf.open(path) as document:
                    images = [base64.b64encode(page.get_pixmap(dpi=self.dpi).tobytes("png")).decode("ascii") for page in document]
            else:
                images = [base64.b64encode(path.read_bytes()).decode("ascii")]
        else:
            import pymupdf

            images = []
            with pymupdf.open(path) as document:
                for index, page in enumerate(document):
                    if self.max_pages is not None and index >= self.max_pages:
                        break
                    images.append(base64.b64encode(page.get_pixmap(dpi=self.dpi).tobytes("png")).decode("ascii"))
        return "\n\n".join(self.page_text(image) for image in images)


_READY: dict[tuple[str, str], bool] = {}


def _vision_ready(base_url: str, model: str) -> bool:
    """Whether Ollama answers here with this model able to read images; asked once per process."""
    key = (base_url, model)
    if key not in _READY:
        from jason.community.ollama_extractor import vision_models

        names = vision_models(base_url)
        _READY[key] = model in names or f"{model}:latest" in names
    return _READY[key]


def engines() -> tuple[OcrEngine, ...]:
    """The engines that can run on this machine, best first."""
    found: list[OcrEngine] = []
    vision = OllamaVisionOcr()
    if vision.available():
        found.append(vision)
    if DoclingRapidOcr.available():
        found.append(DoclingRapidOcr())
    if TesseractCli.available():
        found.append(TesseractCli())        # Tesseract's own word spacing; PyMuPDF's runs words together
    if PyMuPdfTesseract.available():
        found.append(PyMuPdfTesseract())
    return tuple(found)


@dataclass
class OcrReport:
    engine: str = ""
    written: list[Path] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return f"ocr engine={self.engine or 'none'} written={len(self.written)} skipped={len(self.skipped)} errors={len(self.errors)}"


def image_only(path: Path, *, threshold: int = 400) -> bool:
    """True when the PDF's own text layer, or the extract beside it, holds almost nothing."""
    beside = path.with_name(path.name + ".md")
    if beside.is_file() and len(beside.read_text(encoding="utf-8", errors="ignore")) > threshold:
        return False
    try:
        import pymupdf

        document = pymupdf.open(path)
        return sum(len(page.get_text()) for page in document) < threshold
    except Exception:
        return True


def ocr_folder(folder: Path, *, engine: OcrEngine | None = None, only_image_only: bool = True, header: Callable[[Path], str] | None = None) -> OcrReport:
    """Write a ``.pdf.md`` beside each PDF the engine can read; existing text layers are left alone."""
    report = OcrReport()
    chosen = engine or (engines()[0] if engines() else None)
    if chosen is None:
        report.errors.append("no OCR engine is installed: pip install \"docling[rapidocr]\", or install Tesseract for PyMuPDF")
        return report
    report.engine = chosen.name
    for path in sorted(folder.glob("*.pdf")):
        if only_image_only and not image_only(path):
            report.skipped.append(path.name)
            continue
        try:
            text = chosen.text_of(path)
        except Exception as exc:
            report.errors.append(f"{path.name}: {exc}")
            continue
        if not text.strip():
            report.skipped.append(f"{path.name}: no text came back")
            continue
        head = header(path) if header else f"# {path.name} - ocr: `{chosen.name}`\n\n"
        target = path.with_name(path.name + ".md")
        target.write_text(head + text, encoding="utf-8")
        report.written.append(target)
    return report


def _unused(_: Any) -> None:
    return None
