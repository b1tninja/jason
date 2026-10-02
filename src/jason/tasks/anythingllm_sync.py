"""Push Jason's catalogs into AnythingLLM, each in its own folder and workspace.

The catalogs keep authority apart from commentary. ``authorities`` is the
words of the law lawlibrary exported and the agency publications fetched
as files. ``association-records`` is the association's own record set:
the governing documents, annexations, policies, resolutions, and the
public reports on the Drive mirror. ``jason-pages`` is what Jason wrote:
the generated pages and its own instructions, which summarize the other
two and are never quoted as either. A title a folder already holds is
skipped; a title held in another folder is moved rather than parsed
twice. Nothing is sent without the API key.

Each legal case with a Drive folder is its own catalog (``jason.tasks.case_files``): confidential, never in the shared
workspace, synced only when named, and never a source or destination of a move.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from jason.community.anythingllm import AnythingLLM, AnythingLLMModelError, Answer

COMBINED_WORKSPACE = "Mystique"


class Root(Enum):
    DATA = "the data directory"
    PROJECT = "the project checkout"


@dataclass(frozen=True)
class Source:
    root: Root
    folder: str
    pattern: str = "*.md"
    recursive: bool = False
    prefix: str = ""
    # A file's title comes from the heading of the note beside it (``name.pdf.md``) instead of its file name.
    titled_by_note: bool = False
    # Files ending with one of these are left out, such as the notes that title a publication.
    exclude: tuple[str, ...] = ()
    # Title a file "<prefix>: <its path under the folder>", so two files of one name in different subfolders stay apart.
    relative_title: bool = False

    def files(self, data_root: Path, project_root: Path | None) -> tuple[Path, ...]:
        base = (data_root if self.root is Root.DATA else project_root)
        if base is None:
            return ()
        base = base / self.folder if self.folder else base
        if not base.is_dir():
            return ()
        found = base.rglob(self.pattern) if self.recursive else base.glob(self.pattern)
        return tuple(sorted(p for p in found if p.is_file() and not p.name.lower().endswith(self.exclude)))

    def title(self, path: Path, data_root: Path, project_root: Path | None) -> str:
        if self.relative_title:
            base = (data_root if self.root is Root.DATA else project_root or Path()) / self.folder
            try:
                return f"{self.prefix}: {path.relative_to(base).as_posix()}"
            except ValueError:
                pass
        return page_title(path, self)


@dataclass(frozen=True)
class Catalog:
    name: str
    folder: str
    workspace: str
    author: str
    description: str
    sources: tuple[Source, ...]
    # Jason wrote every file here, so a stale copy may be replaced; the association's records are never replaced.
    generated: bool = False
    # Also take the classified PayHOA library (data/library), minus what it marks confidential or not a record.
    library: bool = False
    # Also added to the shared Mystique workspace.
    shared: bool = True
    # Synced only when named (``--catalog``), never by a sync of everything.
    explicit: bool = False
    # For directors and counsel: a document is never moved into or out of this catalog's folder.
    confidential: bool = False


CATALOGS: tuple[Catalog, ...] = (
    Catalog(
        "authorities", "authorities", "Authorities", "California Legislature and agencies",
        "authoritative source: statute text from the current session publication, or an agency publication, as exported by lawlibrary",
        (
            Source(Root.DATA, "authorities", "*.md", recursive=True, exclude=(".pdf.md",)),
            Source(Root.DATA, "authorities/publications", "*.pdf", titled_by_note=True),
        ),
        generated=True,
    ),
    Catalog(
        "association-records", "association-records", "Association Records", "Mystique Community Association",
        "the association's own record: a governing document, annexation, policy, resolution, or public report from the Drive mirror",
        (
            Source(Root.DATA, "artifacts/site-docs/governing_documents", "*.pdf"),
            Source(Root.DATA, "artifacts/site-docs/governing_documents_Annexations", "*.pdf"),
            Source(Root.DATA, "artifacts/site-docs/governing_documents_Policies", "*.pdf"),
            Source(Root.DATA, "artifacts/site-docs/governing_documents_Resolutions", "*.pdf"),
            Source(Root.DATA, "artifacts/site-docs/dre_reports", "*.pdf"),
        ),
        library=True,
    ),
    Catalog(
        "mail", "mail", "Mail", "senders of the association's mail",
        "a letter the association received, through PostScanMail: the sender's words as scanned (OCR can misread), with jason's "
        "sort and the dates and numbers the letter states; correspondence, not the association's record and not an authority",
        (Source(Root.DATA, "mail", "letter.md", recursive=True),),
        generated=True,
    ),
    Catalog(
        "insurance", "insurance", "Insurance", "the association's insurers and agents",
        "the association's insurance: each policy's declarations, forms, certificates, binders, renewal notices, and premium "
        "invoices as `jason policies` gathered them, and Jason's page for each policy (terms, limits, deductibles, findings); the "
        "declarations and forms govern, a page is a reading",
        (
            Source(Root.DATA, "insurance/documents", "*.pdf", prefix="insurance", relative_title=True),
            Source(Root.DATA, "insurance/pages", "*.md", prefix="insurance-pages", relative_title=True),
        ),
    ),
    Catalog(
        "jason-pages", "jason-pages", "Jason Pages", "Jason",
        "a page Jason generated from the stores, or one of its own instructions: a summary, not an authority and not a record",
        (
            Source(Root.DATA, "reports/property-history", "*.md", prefix="property-history"),
            Source(Root.DATA, "reports", "*.md", prefix="reports"),
            Source(Root.PROJECT, "", "SKILLS.md", prefix="instructions"),
            Source(Root.PROJECT, "", "AGENTS.md", prefix="instructions"),
            Source(Root.PROJECT, "docs", "*.md", prefix="docs"),
            Source(Root.PROJECT, "docs/laws", "*.md", prefix="docs-laws"),
            Source(Root.PROJECT, "mystique", "README.md", prefix="mystique"),
        ),
        generated=True,
    ),
)


def catalog_named(name: str, extra: tuple[Catalog, ...] = ()) -> Catalog | None:
    wanted = name.strip().lower()
    return next((c for c in (*CATALOGS, *extra) if c.name == wanted or c.folder == wanted), None)


def chosen_catalogs(names: tuple[str, ...], extra: tuple[Catalog, ...] = ()) -> tuple[Catalog, ...]:
    """The catalogs a sync takes: every catalog not synced only by name, else those named. ``cases`` names every case."""
    wanted = {n.strip().lower() for n in names}
    every = (*CATALOGS, *extra)
    if not wanted:
        return tuple(c for c in every if not c.explicit)
    return tuple(c for c in every if c.name in wanted or c.folder in wanted or ("cases" in wanted and c.name.startswith("case-")))


@dataclass
class SyncReport:
    workspaces: dict[str, str] = field(default_factory=dict)
    uploaded: list[str] = field(default_factory=list)
    moved: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    refreshed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        spaces = ",".join(f"{k}={v}" for k, v in self.workspaces.items())
        return f"anythingllm sync workspaces[{spaces}] uploaded={len(self.uploaded)} refreshed={len(self.refreshed)} moved={len(self.moved)} skipped={len(self.skipped)} errors={len(self.errors)}"


def page_title(path: Path, source: Source) -> str:
    """A page's title: the source prefix and stem, else the page's first heading, else the file name."""
    if source.prefix:
        return f"{source.prefix}: {path.stem}"
    heading_from = path.with_name(path.name + ".md") if source.titled_by_note else path
    if heading_from.suffix.lower() == ".md" and heading_from.is_file():
        for line in heading_from.read_text(encoding="utf-8", errors="ignore").splitlines()[:5]:
            if line.startswith("# "):
                return line[2:].strip()
    return path.name


def is_stale(path: Path, held: dict) -> bool:
    """Whether the file on disk changed after AnythingLLM stored its copy.

    The store prints ``published`` in the machine's local time, as
    "9/28/2026, 12:51:40 PM". A copy with no readable time is not replaced.
    """
    from datetime import datetime

    stamp = str(held.get("published") or "").strip()
    for form in ("%m/%d/%Y, %I:%M:%S %p", "%m/%d/%Y, %H:%M:%S"):
        try:
            published = datetime.strptime(stamp, form)
        except ValueError:
            continue
        return datetime.fromtimestamp(path.stat().st_mtime) > published
    return False


# Kinds the library classifies that do not belong in a shared catalog of records.
_NOT_IN_CATALOG = frozenset({"template", "image", "grant_deed", "tax_bill", ""})


def library_items(root: Path, taken: set[str]) -> list[tuple[Path, str, str]]:
    """The classified library's files for the records catalog: (file, title, description).

    Confidential files, blank templates, photos, deed scans, and tax bills
    stay out. The title is the file name, so a copy the Drive mirror already
    supplied is not uploaded twice; the description says what the file is
    and which Civil Code 5200 record it is, which a retriever's source shows.
    """
    from jason.tasks.library import distinct, load, local_path, mirror_index
    from jason.community.library import LibraryDocument

    mirrors = mirror_index(root)
    found: list[tuple[Path, str, str]] = []
    seen = {title.casefold() for title in taken}
    # One row per distinct file: a copy filed under Confidential/ makes every copy of the same bytes confidential, and a
    # treasurer's report whose aging lists units is confidential by its content (content.PRIVATE_RULES).
    for row in distinct(load(root)):
        if row["confidential"] or row["kind"] in _NOT_IN_CATALOG:
            continue
        title = row["name"]
        if title.casefold() in seen:
            continue
        doc = LibraryDocument(row["source"], row["id"], row["path"], row["name"], "")
        path = local_path(root, doc, mirrors)
        if path is None or path.suffix.lower() not in (".pdf", ".md", ".txt", ".docx", ".csv"):
            continue
        seen.add(title.casefold())
        kind = row["kind"].replace("_", " ")
        records = ", ".join(r.replace("_", " ") for r in row["records"]) or "not a Civil Code 5200 record"
        period = f"; period {row['period']}" if row.get("period") else ""
        found.append((path, title, f"the association's own record: {kind}{period}; Civil Code 5200: {records}; library path {row['path']}"))
    return found


def ensure_workspace(client: AnythingLLM, name: str) -> str:
    slug = client.workspace_slug(name) or client.create_workspace(name)
    if slug:
        client.configure_workspace(slug)
    return slug


def _move(client: AnythingLLM, src: str, dst: str) -> bool:
    """Move a parsed document between folders.

    The store refuses to move a document any workspace still embeds, so on
    a refusal it is removed from every workspace's embeddings and moved
    again; the caller then adds it to the catalog's workspaces.
    """
    if client.move({src: dst}):
        return True
    for space in client.workspaces():
        slug = str(space.get("slug") or "")
        if slug:
            client.update_embeddings(slug, deletes=(src,))
    return client.move({src: dst})


def sync_catalogs(
    client: AnythingLLM, root: Path, project_root: Path | None = None, *, names: tuple[str, ...] = (), combined: str = COMBINED_WORKSPACE,
    refresh: bool = False, include_confidential_mail: bool = False, extra: tuple[Catalog, ...] = (),
) -> SyncReport:
    report = SyncReport()
    chosen = chosen_catalogs(names, extra)
    confidential_folders = {c.folder for c in (*CATALOGS, *extra) if c.confidential}
    if any(c.name == "mail" for c in chosen):
        # The mail catalog is the letters jason wrote a page for: never one carrying a credential, and a confidential
        # kind (an attorney's letter, a bank statement, a check, an escrow request) only when a person asks.
        from jason.tasks.mail import write_letters

        write_letters(root, include_confidential=include_confidential_mail)
    combined_slug = ensure_workspace(client, combined) if combined else ""
    if combined_slug:
        report.workspaces["combined"] = combined_slug
    present = client.documents()
    by_title: dict[str, dict] = {}
    for item in present:
        by_title.setdefault(str(item.get("title") or item.get("name") or ""), item)
    for catalog in chosen:
        try:
            client.create_folder(catalog.folder)
            slug = ensure_workspace(client, catalog.workspace)
        except Exception as exc:
            report.errors.append(f"{catalog.name}: {exc}")
            continue
        report.workspaces[catalog.name] = slug
        spaces = ",".join(s for s in (slug, combined_slug if catalog.shared else "") if s)
        items = [(path, source.title(path, root, project_root), catalog.description) for source in catalog.sources
                 for path in source.files(root, project_root)]
        if catalog.library:
            items += library_items(root, {title for _, title, _ in items})
        renamed: dict[str, list[str]] = {}
        if catalog.name == "mail":
            # A letter is its mail id: one no longer shareable (a credential, a confidential kind, another association's
            # mail) leaves the store; one whose heading changed (its sender now named) is replaced after the new copy lands.
            current = {_mail_id(title): title for _, title, _ in items}
            stale = []
            for title, held in by_title.items():
                if held.get("folder") != catalog.folder or not held.get("name") or not _mail_id(title):
                    continue
                if _mail_id(title) not in current:
                    stale.append(f"{catalog.folder}/{held['name']}")
                elif current[_mail_id(title)] != title:
                    renamed.setdefault(current[_mail_id(title)], []).append(f"{catalog.folder}/{held['name']}")
            if stale:
                try:
                    client.remove_documents(tuple(stale))
                    report.refreshed.extend(f"removed {name}" for name in stale)
                except Exception as exc:
                    report.errors.append(f"mail: removing {len(stale)} letters: {exc}")
        for path, title, description in items:
            if True:
                held = by_title.get(title)
                if held is not None and held.get("folder") != catalog.folder and (
                        catalog.confidential or held.get("folder") in confidential_folders):
                    # A confidential catalog neither gives nor takes a document: upload its own copy.
                    held = None
                if held is not None and held.get("folder") == catalog.folder:
                    if refresh and catalog.generated and is_stale(path, held):
                        # Upload the new copy first, so a failure never leaves the catalog without the page.
                        try:
                            client.upload(path, workspace=spaces, title=title, description=description, folder=catalog.folder, author=catalog.author)
                            if held.get("name"):
                                client.remove_documents((f"{catalog.folder}/{held['name']}",))
                            report.refreshed.append(title)
                        except Exception as exc:
                            report.errors.append(f"{title}: refresh {exc}")
                        continue
                    report.skipped.append(title)
                    continue
                if held is not None and held.get("folder") and held.get("name"):
                    src, dst = f"{held['folder']}/{held['name']}", f"{catalog.folder}/{held['name']}"
                    try:
                        if not _move(client, src, dst):
                            report.errors.append(f"{title}: the store would not move {src}")
                            continue
                        for space in spaces.split(","):
                            client.update_embeddings(space, adds=(dst,))
                        report.moved.append(title)
                        held["folder"] = catalog.folder
                    except Exception as exc:
                        report.errors.append(f"{title}: move {exc}")
                    continue
                try:
                    client.upload(path, workspace=spaces, title=title, description=description, folder=catalog.folder, author=catalog.author)
                    report.uploaded.append(title)
                    by_title[title] = {"title": title, "folder": catalog.folder}
                    if renamed.get(title):
                        client.remove_documents(tuple(renamed[title]))
                        report.refreshed.append(title)
                except Exception as exc:
                    report.errors.append(f"{title}: {exc}")
    return report


def _mail_id(title: str) -> str:
    """The mail id a letter page's heading ends with ("... [mail 115069]"), or "" for any other page."""
    import re

    found = re.search(r"\[mail (\d+)\]\s*$", title)
    return found.group(1) if found else ""


# What a source's folder says about how far to trust its words.
SHELF_OF_FOLDER = {
    "authorities": "authority: the law or an agency publication",
    "association-records": "record: the association's own document",
    "jason-pages": "summary: a page Jason wrote; not the law and not the record",
    "mail": "correspondence: a letter the association received, as scanned; the sender's words, not the record",
}
CASE_SHELF = ("case file: gathered for one legal matter; confidential, for directors and counsel; evidence and correspondence, "
              "not the association's record and not an authority")


def shelf_of(folder: str) -> str:
    return CASE_SHELF if folder.startswith("case-") else SHELF_OF_FOLDER.get(folder, "unfiled")


def ask(client: AnythingLLM, question: str, *, workspace: str = "", catalog: str = "", mode: str = "query",
        extra: tuple[Catalog, ...] = ()) -> dict:
    """Ask one workspace and say which catalog each source came from.

    The workspace is the one named, else the named catalog's, else the
    shared Mystique workspace, else the first there is. A source from
    ``jason-pages`` is marked a summary so an answer resting on it is read
    as Jason's words, not the statute's or the association's.
    """
    slug = workspace
    if not slug and catalog:
        chosen = catalog_named(catalog, extra)
        slug = client.workspace_slug(chosen.workspace) if chosen else ""
        if not slug:
            return {"available": True, "found": False, "note": f"no workspace for catalog {catalog!r}; run jason anythingllm --sync"}
    if not slug:
        slug = client.workspace_slug(COMBINED_WORKSPACE)
    if not slug:
        spaces = client.workspaces()
        slug = str(spaces[0].get("slug") or "") if spaces else ""
    if not slug:
        return {"available": True, "found": False, "note": "no workspace in AnythingLLM"}
    model_error = ""
    try:
        answer = client.query(slug, question, mode=mode if mode in ("query", "chat") else "query")
    except AnythingLLMModelError as exc:
        # The chat model would not run; the retriever still does, so give its passages unread by any model.
        model_error = str(exc)
        answer = Answer(slug, question, "", client.search(slug, question))
    folders = {str(d.get("title") or ""): str(d.get("folder") or "") for d in client.documents()}
    sources = []
    for source in answer.sources:
        folder = folders.get(source.title, "")
        sources.append({"title": source.title, "catalog": folder, "shelf": shelf_of(folder), "text": source.text, "score": source.score})
    note = "an answer from a model over the documents; read the sources, quote only an authority or a record, and pin nothing from it"
    if any(s["catalog"].startswith("case-") for s in sources):
        note += "; a case file source is confidential: for directors and counsel, never the association's newsletter or an owner"
    result = {
        "available": True, "found": True, "workspace": answer.workspace, "question": answer.question, "answer": answer.text, "sources": sources,
        "note": note,
    }
    if model_error:
        result["modelError"] = model_error
        result["note"] = ("AnythingLLM's chat model failed, so there is no answer; the sources are the passages its retriever "
                          "found, read by no model. " + note)
    return result
