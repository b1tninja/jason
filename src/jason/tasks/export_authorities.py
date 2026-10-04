"""Export the words of the law Jason relies on, one Markdown page per span, from lawlibrary.

The registry in ``jason.community.authorities`` says which spans. This
task asks lawlibrary for their text and writes ``data/authorities/<CODE>/
<citation>.md`` with the heading path, the session, the official page,
and why Jason holds it, then a manifest. A named act is written one page
per article so a passage keeps its heading. A span inside an exported act
is not written twice; its reason is added to the article page that holds
it. A span the shelf cannot serve is a miss in the manifest. Regulations,
federal law, and agency publications are pointers, with the source that
holds them; ``fetch_publications`` brings the agency PDFs down when a
person asks for that.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jason.community.authorities import (
    ACTS,
    PUBLICATIONS,
    Authority,
    Basis,
    Publication,
    Shelf,
    authorities,
    number_key,
    section_in,
)
from jason.sources.lawlibrary import LawLibrary, Section, article_groups

AUTHORITIES_DIR = "authorities"
PUBLICATIONS_DIR = "authorities/publications"
MANIFEST = "manifest.json"
# The store lock (jason.locks) the export and a reader's read-through hold while they write the shelf.
STORE_KEY = "authorities"
_BRACKET = re.compile(r"\s*\[[^\]]*\]\s*$")


@dataclass
class Page:
    file: str
    citation: str
    title: str
    code: str
    start: str
    end: str
    sections: list[str]
    basis: str
    why: list[str]
    session: str
    # A page a reader's miss brought down (jason.tasks.statute_fetch): the day, and what asked. Empty for the curated list.
    fetched: str = ""
    asked_by: str = ""


@dataclass
class ExportReport:
    session: str = ""
    pages: list[Page] = field(default_factory=list)
    misses: list[str] = field(default_factory=list)
    pointers: list[dict[str, str]] = field(default_factory=list)
    # Sections fetched on demand that no curated span covers: leads for a person to promote with a Basis and a reason.
    on_demand: list[Page] = field(default_factory=list)

    def summary(self) -> str:
        sections = sum(len(p.sections) for p in self.pages)
        return (f"authorities session={self.session or '?'} pages={len(self.pages)} sections={sections} misses={len(self.misses)} "
                f"pointers={len(self.pointers)} on_demand={len(self.on_demand)}")


@dataclass(frozen=True)
class _Want:
    code: str
    start: str
    end: str
    basis: Basis | None
    why: tuple[str, ...]
    heading: str = ""


def heading_title(heading: str) -> str:
    """"ARTICLE 5. Record Inspection [5200. - 5240.]" as "Article 5. Record Inspection"."""
    plain = _BRACKET.sub("", heading).strip()
    head, sep, rest = plain.partition(" ")
    return (head.capitalize() + sep + rest) if head.isupper() else plain


def export_authorities(library: LawLibrary, root: Path, *, spans: tuple[Authority, ...] | None = None, acts=ACTS) -> ExportReport:
    report = ExportReport()
    wanted = list(authorities() if spans is None else spans)
    jobs: list[_Want] = []
    covered: list[tuple[str, str, str]] = []
    for act in acts:
        groups = article_groups(library.act(act.name))
        if not groups:
            report.misses.append(act.name)
            continue
        act_first, act_last = min(number_key(g.first) for g in groups), max(number_key(g.last) for g in groups)
        covered.extend((a.code, a.start, a.end) for a in wanted if a.exportable and a.code == act.code and act_first <= number_key(a.start) and number_key(a.end) <= act_last)
        for group in groups:
            # A span that overlaps this article lends it its reason; a span across several articles lends each.
            overlapping = [a for a in wanted if a.exportable and a.code == act.code and number_key(a.start) <= number_key(group.last) and number_key(group.first) <= number_key(a.end)]
            reasons = [act.why]
            for a in overlapping:
                if a.why not in reasons:
                    reasons.append(a.why)
            jobs.append(_Want(act.code, group.first, group.last, act.basis, tuple(reasons), group.heading))
    regulations = regulation_sections(root / PUBLICATIONS_DIR / REGULATIONS_FILE)
    for a in wanted:
        if a.shelf is Shelf.REGULATION and a.start == a.end and a.start in regulations:
            report.pages.append(_regulation_page(root, a, regulations[a.start]))
            continue
        if not a.exportable:
            report.pointers.append({"citation": a.citation, "shelf": a.shelf.value, "source": a.official, "why": a.why})
            continue
        if (a.code, a.start, a.end) in covered:
            continue
        jobs.append(_Want(a.code, a.start, a.end, a.basis, (a.why,)))
    for pub in PUBLICATIONS:
        report.pointers.append({"citation": pub.title, "shelf": Shelf.PUBLICATION.value, "source": pub.url, "why": pub.why})

    texts = library.spans([(j.code, j.start, j.end) for j in jobs])
    from jason.locks import Resource, hold

    # The same lock a reader's read-through takes, so a page fetched on demand is not lost between read and write.
    with hold(Resource.STORE, STORE_KEY, purpose="jason export-authorities"):
        _write_export(root, report, jobs, texts)
    return report


def _write_export(root: Path, report: ExportReport, jobs: list[_Want], texts) -> None:
    out = root / AUTHORITIES_DIR
    earlier = [Page(**p) for p in read_manifest(root).get("on_demand") or []]
    for job, span in zip(jobs, texts):
        citation = f"{job.code} {job.start}" if job.start == job.end else f"{job.code} {job.start}-{job.end}"
        if not span.found:
            report.misses.append(citation)
            continue
        session = span.sections[0].session
        report.session = report.session or session
        title = heading_title(job.heading or span.sections[0].heading)
        path = out / job.code / (re.sub(r"[^A-Za-z0-9.]+", "-", citation).strip("-") + ".md")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page_markdown(citation, title, job, span.sections, root), encoding="utf-8")
        report.pages.append(Page(
            path.relative_to(root).as_posix(), citation, title, job.code, job.start, job.end,
            [s.number for s in span.sections], job.basis.value if job.basis else "", list(job.why), session,
        ))
    # A page fetched on demand stays until a curated page holds its sections; then the curated page is the copy.
    curated = {(p.code, n) for p in report.pages for n in p.sections}
    files = {p.file for p in report.pages}
    for page in earlier:
        if page.sections and all((page.code, n) in curated for n in page.sections):
            if page.file not in files:
                (root / page.file).unlink(missing_ok=True)
            continue
        if (root / page.file).is_file():
            report.on_demand.append(page)
    out.mkdir(parents=True, exist_ok=True)
    (out / MANIFEST).write_text(json.dumps({
        "exported": date.today().isoformat(), "session": report.session, "pages": [asdict(p) for p in report.pages],
        "misses": report.misses, "pointers": report.pointers, "on_demand": [asdict(p) for p in report.on_demand],
    }, indent=2), encoding="utf-8")


REGULATIONS_FILE = "regs.pdf"
_REG_HEAD = re.compile(r"(?m)^(\d{4}(?:\.\d+)?)\. ([A-Z][^\n]{2,160})$")


def regulation_sections(pdf: Path) -> dict[str, tuple[str, str]]:
    """Each section of the Commissioner's regulations as DRE publishes them: number to (heading, text).

    The PDF prints a section as "2792.23. Heading." at the start of a line;
    the text runs to the next such line. Nothing comes back when the PDF is
    not on disk or PyMuPDF is not installed.
    """
    if not pdf.is_file():
        return {}
    try:
        import pymupdf
    except ImportError:
        return {}
    with pymupdf.open(str(pdf)) as doc:
        text = "\n".join(page.get_text() for page in doc)
    heads = list(_REG_HEAD.finditer(text))
    found: dict[str, tuple[str, str]] = {}
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        body = text[head.end():end].strip()
        found.setdefault(head.group(1), (head.group(2).strip().rstrip("."), body))
    return found


def _regulation_page(root: Path, authority: Authority, section: tuple[str, str]) -> Page:
    heading, body = section
    citation = authority.citation
    path = root / AUTHORITIES_DIR / authority.code.replace(" ", "-") / f"{authority.slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([
        f"# {citation}: {heading}",
        "",
        "- Source: Regulations of the Real Estate Commissioner, California Code of Regulations Title 10, as the Department of Real Estate publishes them",
        f"- Official file: {authority.official}",
        f"- Basis: {authority.basis.value}",
        f"- Why Jason holds it: {authority.why}",
        "",
        f"## {citation}",
        "",
        f"{authority.start}. {heading}.",
        "",
        body,
        "",
    ]), encoding="utf-8")
    return Page(path.relative_to(root).as_posix(), citation, heading, authority.code, authority.start, authority.end,
                [authority.start], authority.basis.value, [authority.why], "DRE publication")


def page_markdown(citation: str, title: str, job: _Want, sections: tuple[Section, ...], root: Path | None = None,
                  *, fetched: str = "") -> str:
    """One page of the shelf. ``fetched`` (the day and what asked) marks a page a reader's miss brought down, in
    place of the curated row's basis and reason."""
    first = sections[0]
    official = f"https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode={job.code}&sectionNum={first.number}."
    lines = [
        f"# {citation}: {title}",
        "",
        f"- Source: California Legislature, {first.session} session publication, read with lawlibrary",
        f"- Official page: {official}",
        f"- Path: {' > '.join(heading_title(h) for h in first.path)}",
    ]
    if fetched:
        lines.append(f"- Fetched: {fetched}; not on the curated list (jason.community.authorities)")
    if job.basis is not None:
        lines.append(f"- Basis: {job.basis.value}")
    for why in job.why:
        lines.append(f"- Why Jason holds it: {why}")
    lines.append("")
    from jason.community.succession import version_note

    for s in sections:
        lines += [f"## {s.citation}", ""]
        # Where the section came from in the 2014 recodification and each amendment since (jason law-history --export).
        note = version_note(root, s.number) if root is not None and s.code == "CIV" else ""
        if note:
            lines += [f"- History: {note}", ""]
        lines += [s.title, "", s.text.strip(), ""]
    return "\n".join(lines)


def read_manifest(root: Path) -> dict[str, Any]:
    path = root / AUTHORITIES_DIR / MANIFEST
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def authority_pages(root: Path) -> tuple[Page, ...]:
    return tuple(Page(**p) for p in read_manifest(root).get("pages") or [])


def on_demand_pages(root: Path) -> tuple[Page, ...]:
    """Pages a reader's miss brought down (jason.tasks.statute_fetch), not on the curated list."""
    return tuple(Page(**p) for p in read_manifest(root).get("on_demand") or [])


_CITE = re.compile(r"^\s*(?:(\d+)\s+)?([A-Z]{2,5})\s*(?:section|§)?\s*(\d+(?:\.\d+)*)\s*$", re.IGNORECASE)


def _on_shelf(root: Path, code: str, number: str) -> dict[str, Any] | None:
    """The section's words from the curated pages, then the pages fetched on demand; None when no page holds them."""
    for pages in (authority_pages(root), on_demand_pages(root)):
        for page in pages:
            if page.code != code or not section_in(Authority(code, page.start, page.end, "", Basis.DUTY), number):
                continue
            path = root / page.file
            text = path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""
            for block in text.split("\n## ")[1:]:
                head, _, body = block.partition("\n")
                if head.strip() == f"{code} {number}":
                    hit = {"found": True, "citation": f"{code} {number}", "page": page.file, "title": page.title,
                           "session": page.session, "why": page.why, "text": body.strip()}
                    if page.fetched:
                        hit["fetched"] = page.fetched
                    return hit
            break
    return None


def authority_text(root: Path, citation: str, *, fetch: bool = True, asked_by: str = "") -> dict[str, Any]:
    """The words of one section from the shelf, or a miss that names the pointer or the gap.

    A section of a code lawlibrary holds that no page has is asked of lawlibrary once (``statute_fetch.ensure``),
    written to the shelf in the export's format, and read from there; ``fetch=False`` or JASON_AUTHORITIES_FETCH=0
    reads the disk only. A miss names why: not in the library, the library unavailable, or its worker failed.
    """
    match = _CITE.match(citation)
    if not match:
        return {"found": False, "citation": citation, "reason": "say a code and a section, such as CIV 5200"}
    code = (match.group(1) + " " if match.group(1) else "") + match.group(2).upper()
    number = match.group(3)
    hit = _on_shelf(root, code, number)
    if hit:
        return hit
    for pointer in read_manifest(root).get("pointers") or []:
        if pointer.get("citation", "").upper().startswith(code + " "):
            return {**pointer, "found": False, "citation": f"{code} {number}", "reason": "not exported; read the source"}
    if fetch:
        from jason.tasks.statute_fetch import Miss, caller, ensure

        got = ensure(root, code, number, asked_by=asked_by or caller())
        if got.found:
            hit = _on_shelf(root, code, number)
            if hit:
                return hit
        elif got.miss is not Miss.FETCH_OFF:
            return {"found": False, "citation": f"{code} {number}", "miss": got.miss.value if got.miss else "",
                    "reason": got.reason_text(), "detail": got.detail}
    return {"found": False, "citation": f"{code} {number}", "reason": "not in the exported authorities; run jason export-authorities or read it from lawlibrary"}


def publication_text(pdf: Path) -> str:
    """A publication's text from its PDF, one ``<<PAGE n>>`` line before each page (as the reference shelf keeps its
    guides). Empty when the PDF has no text layer or PyMuPDF is not installed."""
    try:
        import pymupdf
    except ImportError:
        return ""
    try:
        with pymupdf.open(str(pdf)) as doc:
            pages = [page.get_text() for page in doc]
    except Exception:  # noqa: BLE001 - a damaged download reads as no text; the PDF stays for a person to open
        return ""
    if not any(page.strip() for page in pages):
        return ""
    return "\n".join(f"\n<<PAGE {n}>>\n{page}" for n, page in enumerate(pages, start=1))


def write_publication_texts(root: Path, publications: tuple[Publication, ...] = PUBLICATIONS) -> list[str]:
    """Write each fetched publication's text beside its PDF (``name.txt``) when it is not there; the names written."""
    out = root / PUBLICATIONS_DIR
    written: list[str] = []
    for pub in publications:
        pdf, text = out / pub.filename, out / pub.text_filename
        if pdf.is_file() and not text.is_file():
            body = publication_text(pdf)
            if body:
                text.write_text(body, encoding="utf-8")
                written.append(text.name)
    return written


def publication_context(pub: Publication) -> str:
    """A publication's context line for the index: what it is, who published it, and why it is held."""
    number = f" ({pub.number})" if pub.number else ""
    return f"{pub.title}{number}; {pub.agency}; {pub.why}"


@dataclass(frozen=True)
class PublicationSource:
    """The publications' text for the passage index (``passage_index.build``): a regulation's adopted text is searched
    as the law, an agency's guidance as reference, and a compilation not at all (its sections are their own pages)."""

    publications: tuple[Publication, ...] = PUBLICATIONS

    @property
    def catalogs(self) -> tuple[str, ...]:
        return ("publications",)

    def entries(self, data_dir: Path):
        from jason.community.authorities import PublicationText
        from jason.community.passage_index import IndexFile, Standing

        standing = {PublicationText.REGULATION: Standing.AUTHORITY, PublicationText.GUIDANCE: Standing.REFERENCE}
        for pub in self.publications:
            path = Path(data_dir) / PUBLICATIONS_DIR / pub.text_filename
            if pub.text in standing and path.is_file():
                yield IndexFile(path, "publications", standing[pub.text], kind="", context=publication_context(pub))


def fetch_publications(root: Path, *, fetch=None, publications: tuple[Publication, ...] = PUBLICATIONS) -> list[str]:
    """Bring the agency PDFs down into data/authorities/publications, each with a title note and its text
    (``name.txt``). A file already there is kept; a text file missing beside a PDF on disk is written without a fetch."""
    from urllib.request import Request, urlopen

    out = root / PUBLICATIONS_DIR
    out.mkdir(parents=True, exist_ok=True)
    fetched: list[str] = []
    for pub in publications:
        target = out / pub.filename
        if target.is_file():
            continue
        if fetch is not None:
            data = fetch(pub.url)
        else:
            with urlopen(Request(pub.url, headers={"User-Agent": "Mozilla/5.0 (jason)"}), timeout=120) as response:
                data = response.read()
        target.write_bytes(data)
        (out / (pub.filename + ".md")).write_text(f"# {pub.title}\n\n- Agency: {pub.agency}\n- Number: {pub.number or 'none'}\n- Source: {pub.url}\n- Why Jason holds it: {pub.why}\n", encoding="utf-8")
        fetched.append(pub.filename)
    write_publication_texts(root, publications)
    return fetched
