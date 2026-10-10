"""The reference shelf: explanatory material Jason reads to understand a process, apart from the law and the record.

Three shelves already exist and this is a fourth. ``authorities`` holds the words of the law and the agency
publications that are themselves authority (the Commissioner's regulations, the Department's guidelines).
``association-records`` holds the association's own documents. ``jason-pages`` holds what Jason wrote. A reference
work is none of them: a guide, a textbook, or a manual that explains how a process runs (how a subdivision is mapped,
reported, and handed to its association), written by someone who is neither the Legislature nor the association.

It is quality material to learn from, not to quote as the law. A reading of a statute taken from it is checked
against the section on the authorities shelf; a fact about an association is taken from its own record. Each work
says who wrote it, when, what it covers, and how far it can be trusted, so a retriever's source carries that.

A work is fetched as a file, never rewritten. ``fetch_reference`` writes the file, a note that titles it, and its
text (page by page, so a passage can be cited by page).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

REFERENCE_DIR = "reference"


@dataclass(frozen=True)
class ReferenceWork:
    """One published guide Jason holds on the reference shelf."""

    title: str
    url: str
    author: str
    publisher: str
    year: int
    covers: str
    # How far to trust it: what it is good for and where it is out of date.
    caveat: str
    # What a reader of the shelf can take from it, as questions it answers.
    topics: tuple[str, ...] = ()

    @property
    def filename(self) -> str:
        tail = self.url.rsplit("/", 1)[-1] or "reference.pdf"
        return tail if tail.lower().endswith(".pdf") else tail + ".pdf"

    @property
    def note(self) -> str:
        topics = "".join(f"- {t}\n" for t in self.topics)
        return (
            f"# {self.title}\n\n- Author: {self.author}\n- Publisher: {self.publisher}\n- Year: {self.year}\n- Source: {self.url}\n"
            f"- Covers: {self.covers}\n- How far to trust it: {self.caveat}\n"
            f"- Shelf: reference. An explanation of a process; not the law and not the association's record.\n"
            + (f"\nQuestions it answers:\n{topics}" if topics else "")
        )


REFERENCE_WORKS: tuple[ReferenceWork, ...] = (
    ReferenceWork(
        "A Guide to Understanding Residential Subdivisions in California",
        "https://dre.ca.gov/files/pdf/ResidentialSubdivisionsGuide.pdf",
        "Alberto Esquivel and Jaime R. Alvayay",
        "California Department of Real Estate and California State University, Sacramento",
        2014,
        "how a residential subdivision is made and sold: the Subdivision Map Act and the Subdivided Lands Act side by side, the "
        "kinds of subdivision and common interest development, how the association is formed and what the Department reviews, "
        "the public report and its application, and the development process from land purchase to last sale",
        "an explanation, not the law: it predates later amendments (the Commissioner's regulations, the Davis-Stirling Act, "
        "and the Subdivided Lands Act all changed after 2014), so read a section it cites from the current text on the "
        "authorities shelf before relying on it; its figures (report counts, budget examples, fees) are 2012-2014",
        topics=(
            "Which law governs which step: Map Act (local approval, recorded map) or Subdivided Lands Act (public report, sales)?",
            "What is a common interest development, and how do a planned development, a condominium, and a stock cooperative differ?",
            "What does the Department of Real Estate review and decide, and what is outside its authority?",
            "What is in a public report, and what are the preliminary, conditional, final, amended, and renewed reports?",
            "How does a developer secure assessments, subsidies, and the completion of common improvements?",
            "How is the association formed, and what must its governing documents say while the developer controls it?",
        ),
    ),
)


def reference_dir(root: Path) -> Path:
    return Path(root) / REFERENCE_DIR


def pdf_text(data: bytes) -> str:
    """A PDF's text, one ``<<PAGE n>>`` marker before each page. A page with no text layer is left blank."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join(f"\n<<PAGE {i}>>\n{page.extract_text() or ''}" for i, page in enumerate(reader.pages, start=1))


def fetch_reference(root: Path, *, fetch=None, works: tuple[ReferenceWork, ...] = REFERENCE_WORKS) -> list[str]:
    """Bring each work down into ``data/reference``: the PDF, a note that titles it, and its text. A file already there is kept.

    ``fetch(url)`` returns the bytes; the default is one HTTPS request. A work whose text file is missing
    (fetched before the text was kept) has its text written from the PDF on disk without a second request.
    """
    from urllib.request import Request, urlopen

    out = reference_dir(root)
    out.mkdir(parents=True, exist_ok=True)
    fetched: list[str] = []
    for work in works:
        target = out / work.filename
        if not target.is_file():
            if fetch is not None:
                data = fetch(work.url)
            else:
                with urlopen(Request(work.url, headers={"User-Agent": "Mozilla/5.0 (jason)"}), timeout=120) as response:
                    data = response.read()
            target.write_bytes(data)
            fetched.append(work.filename)
        note = out / (work.filename + ".md")
        if not note.is_file():
            note.write_text(work.note, encoding="utf-8")
        text = out / (target.stem + ".txt")
        if not text.is_file():
            text.write_text(pdf_text(target.read_bytes()), encoding="utf-8")
    return fetched


def work_of(filename: str) -> ReferenceWork | None:
    return next((w for w in REFERENCE_WORKS if w.filename.casefold() == filename.casefold()), None)


def find_work(name: str) -> ReferenceWork | None:
    """A work by its file name, else by part of its title (case folded); None for a blank or unknown name."""
    wanted = name.strip()
    if not wanted:
        return None
    return work_of(wanted) or next((w for w in REFERENCE_WORKS if wanted.casefold() in w.title.casefold()), None)


def page_count(root: Path, work: ReferenceWork) -> int:
    """How many pages of text a work has on disk (its ``<<PAGE n>>`` markers); 0 when there is no text."""
    path = reference_dir(root) / (Path(work.filename).stem + ".txt")
    return len(re.findall(r"<<PAGE \d+>>", path.read_text(encoding="utf-8"))) if path.is_file() else 0


def page_text(root: Path, work: ReferenceWork, page: int) -> str:
    """The text of one page (1-based) of a work held on disk, or "" when the work or the page is not there."""
    path = reference_dir(root) / (Path(work.filename).stem + ".txt")
    if not path.is_file():
        return ""
    marker = f"<<PAGE {page}>>"
    body = path.read_text(encoding="utf-8")
    start = body.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = body.find("<<PAGE ", start)
    return body[start:end if end >= 0 else None].strip()
