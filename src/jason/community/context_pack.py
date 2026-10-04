"""The sources for one task, found by retrieval and numbered in order of authority: the RAG step of a manager's review.

A task prompt names topics and kinds of documents, never a section or a figure. ``assemble`` finds what is in force:

1. **S, the law**: the sections of the law on hand (``data/authorities``, as lawlibrary exported it) that best answer
   the task's topics, each section whole, plus every statute a retrieved document passage cites. A pre-2014
   Davis-Stirling number is a gap to resolve, not a section to fetch.
2. **G, the governing documents**: the passages of the declaration, its amendments and annexations, the articles, the
   bylaws, and the rules, policies, and resolutions that best answer the topics, narrowed to the kinds the task names.
   Each passage's tier comes from its document's kind. Copies of one passage in one kind of document (a Doc export, a
   PDF's text, a scan's OCR) are folded into one.
3. **R, the records**: for each other kind the task names (insurance policies, agendas, minutes, budgets), the best
   passages of the association's latest files of that kind in the classified library. A confidential file is read only
   for the board.
4. **F, jason's records**: the MCP tools the task names, as JSON, trimmed.
5. **D1**: the text under review.

The law on hand is also listed by chapter (``shelf``), so a reader can see what the pack could have drawn on and say
when the law it expected is not there. ``markdown`` writes the base prompt, the task prompt, and the sources as one page.

**Where the passages come from.** When the passage index is built (``jason index --build``, ``passage_index``) and holds
every file a tier would cut, the tier ranks the index's passages instead of cutting the folders on every call:

- G ranks the passages under the ``CORPUS`` folders: the same passages, ranked the same way, without cutting them
  again. A member's task never sees a file the index holds back as confidential; the board's does.
- S ranks the law's sections whole, as before, by default. ``law_index`` (``LAW_FROM_INDEX``) ranks the index's
  passages of the law pages instead (standing ``authority``) and reads each hit as the section it falls in. On the
  profile's tasks it replaced a quarter of a task's sections at the median and up to two thirds. Measured on the
  law's 50 gold questions (October 4, 2026; docs/document-tools.md): sections whole, hybrid recall@5 0.98 and MRR@10
  0.84; the index's passages 0.96 and 0.87; the two fused 0.96 and 0.88. Neither is clearly better, so it stays off.
  The section is recited whole either way.
- R stays on the classified library, which the index does not hold yet. F and D read no passages.

A tier is cut from the folders as before when the index is missing, lacks one of the tier's files, or holds one older
than the file on disk (``index_covers``): a stale index never answers for a file that changed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from jason.community.authority_order import Tier, tier_of_citation, tier_of_kind
from jason.community.passages import Passage, passages_of
from jason.community.prompts import Audience, TaskPrompt, system_prompt, task_text
from jason.community.symbols import DocumentKind, PayhoaFolder

# The governing extracts on disk and the PayHOA folder each mirrors (its folder decides a kind a name leaves open).
CORPUS: tuple[tuple[str, PayhoaFolder | None], ...] = (
    ("governing", PayhoaFolder.GOVERNING_DOCUMENTS),
    ("artifacts/site-docs/governing_documents", PayhoaFolder.GOVERNING_DOCUMENTS),
    ("artifacts/site-docs/governing_documents_Annexations", PayhoaFolder.ANNEXATIONS),
    ("artifacts/site-docs/governing_documents_Policies", PayhoaFolder.POLICIES),
    ("artifacts/site-docs/governing_documents_Resolutions", PayhoaFolder.RESOLUTIONS),
)
GOVERNING_KINDS = frozenset({
    DocumentKind.DECLARATION, DocumentKind.AMENDMENT, DocumentKind.ANNEXATION, DocumentKind.ARTICLES, DocumentKind.BYLAWS,
    DocumentKind.OPERATING_RULES, DocumentKind.POLICY, DocumentKind.ELECTION_RULES, DocumentKind.RESOLUTION, DocumentKind.NOTICE,
})
LAW_LIMIT = 12                # law sections from retrieval
LEAD_ARTICLES = 5             # the articles the law sections are drawn from first
ARTICLE_SECTIONS = 3          # sections taken from each leading article before the rest
RRF_K = 60
STATUTE_CHARS = 9000          # one section's text
FACT_CHARS = 6000
RECORD_FILES = 3              # the latest files of each record kind read
RECORD_PASSAGES = 2           # passages kept per record kind
SAME_TEXT = 0.6               # Jaccard overlap above which two passages are copies of one
LAW_FROM_INDEX = False        # rank the law by the index's passages (measured no better than sections whole; see above)


@dataclass(frozen=True)
class Source:
    id: str
    tier: Tier
    title: str
    text: str
    place: str = ""            # a file and passage, a citation, or a tool
    score: float = 0.0
    note: str = ""


@dataclass(frozen=True)
class LawSection:
    citation: str              # "CIV 5810"
    chapter: str               # the page's title: "CIV 5800-5810: Chapter 9. Insurance and Liability"
    text: str
    file: str = ""
    start_word: int = 0        # where the section starts in its page, in words (to read an index passage as its section)


@dataclass
class ContextPack:
    task: TaskPrompt
    ask: str = ""
    draft: str = ""
    association: tuple[str, ...] = ()
    sources: list[Source] = field(default_factory=list)
    shelf: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)

    def texts(self) -> dict[str, str]:
        return {s.id: s.text for s in self.sources}

    def _ordered(self) -> list[Source]:
        order = {"S": 0, "G": 1, "R": 2, "F": 3, "D": 4}
        return sorted((s for s in self.sources if not s.id.startswith("D")),
                      key=lambda s: (s.tier, order.get(s.id[0], 9), int(s.id[1:])))

    def sources_text(self) -> str:
        blocks = []
        for s in self._ordered():
            note = f" — {s.note}" if s.note else ""
            blocks.append(f"[{s.id}] tier {int(s.tier)} ({s.tier.label}): {s.title}{note}\n{s.text.strip()}")
        if self.shelf:
            blocks.append("THE LAW ON HAND, by chapter (not sources; what retrieval could draw on):\n" + "\n".join(f"  {line}" for line in self.shelf))
        return "\n\n".join(blocks)

    def markdown(self) -> str:
        parts = [f"# {self.task.kind.value.capitalize()}", "", "## Base prompt", "", system_prompt(self.association), "", "## Task", "",
                 task_text(self.task, ask=self.ask, draft=self.draft), "", "## Sources, in order of authority", ""]
        for s in self._ordered():
            note = f" — {s.note}" if s.note else ""
            where = f" ({s.place})" if s.place else ""
            parts += [f"### [{s.id}] {s.title}{where}", f"*Tier {int(s.tier)}: {s.tier.label}{note}*", "", s.text.strip(), ""]
        if self.shelf:
            parts += ["## The law on hand, by chapter", ""] + [f"- {line}" for line in self.shelf] + [""]
        if self.gaps:
            parts += ["## Gaps", ""] + [f"- {g}" for g in self.gaps] + [""]
        return "\n".join(parts)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.casefold()))


def _same(a: str, b: str) -> bool:
    """Two passages share most of their words (Jaccard): a Doc export, a PDF's text layer, and a scan's OCR of one
    passage. A rule that repeats a declaration's words is not a copy of it; callers compare only within one kind."""
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / len(wa | wb) >= SAME_TEXT


def _doc_name(path: Path) -> str:
    """The name the library would classify: the extract's name without ``.md`` (``Bylaws.pdf.md`` -> ``Bylaws.pdf``)."""
    return path.name[:-3] if path.name.endswith(".md") else path.name


def _ranker(mode: str, data_dir: Path, embedder: Any = None) -> Callable[[str, Sequence[Passage], int], Sequence[Any]]:
    from jason.community import retrieval
    from jason.community.passages import rank

    if mode == "keyword":
        return lambda query, items, k: rank(query, tuple(items), k=k)
    if mode == "exact":
        return lambda query, items, k: retrieval.keyword_exact(query, items, k=k)
    embedder = embedder or retrieval.default_embedder(data_dir)
    return lambda query, items, k: retrieval.hybrid(query, items, k=k, embedder=embedder)


MATTER_WORDS = 60             # how much of the text under review stands for the matter in retrieval


def matter(ask: str = "", draft: str = "") -> str:
    """What this instance of the task is about, in its own words: the question, or the draft's subject and opening. The
    task's topics are general ("what the declaration says on the rule's subject"); the matter names the subject."""
    if ask:
        return ask
    words = re.sub(r"\{[^}]*\}", " ", draft or "").split()
    return " ".join(words[:MATTER_WORDS])


def _questions(task: TaskPrompt, ask: str, draft: str = "") -> list[str]:
    found = matter(ask, draft)
    return [*task.topics, *([found] if found else [])] or [task.purpose]


# --- the law ---------------------------------------------------------------------------------------------------------

def law_corpus(data_dir: Path) -> list[LawSection]:
    """Every section of the law on hand, whole, with its chapter: the pages ``jason export-authorities`` wrote."""
    from jason.tasks.export_authorities import authority_pages

    sections: list[LawSection] = []
    for page in authority_pages(data_dir):
        path = data_dir / page.file
        if not path.is_file():
            continue
        chapter = f"{page.citation}: {page.title}"
        body_text = path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
        blocks = body_text.split("\n## ")
        offset = len(blocks[0].split())
        for block in blocks[1:]:
            head, _, body = block.partition("\n")
            sections.append(LawSection(head.strip(), chapter, body.strip(), page.file, offset))
            offset += len(("## " + block).split())
    return sections


def law_shelf(sections: Sequence[LawSection]) -> list[str]:
    return list(dict.fromkeys(s.chapter for s in sections))


def law_sources(questions: Sequence[str], sections: Sequence[LawSection], rank: Callable[..., Sequence[Any]] | None = None, *,
                limit: int = LAW_LIMIT, k: int = 4,
                rank_sections: Callable[[str, int], Sequence[int]] | None = None) -> list[tuple[LawSection, float]]:
    """The sections that best answer the questions, best first, each once. A section is ranked with its chapter's words
    (``rank`` over the sections whole), or ``rank_sections(question, n)`` gives the indexes of the ``n`` best sections
    (``index_law_ranking``: the index's passages, each read as its section)."""
    if rank_sections is None:
        if rank is None:
            raise ValueError("law_sources needs rank or rank_sections")
        items = [Passage(Path(s.file or s.citation), i, 0, f"{s.citation} {s.chapter} {s.text}") for i, s in enumerate(sections)]

        def rank_sections(question: str, n: int) -> Sequence[int]:
            return [hit.passage.index for hit in rank(question, items, n)]
    # Each topic ranks the sections; the rankings are fused (reciprocal rank), so every topic counts the same and a
    # section several topics reach rises above one a single topic put first.
    fused: dict[int, float] = {}
    for question in questions:
        for place, i in enumerate(rank_sections(question, k * 3), 1):
            fused[i] = fused.get(i, 0.0) + 1.0 / (RRF_K + place)
    ordered = [i for i, _ in sorted(fused.items(), key=lambda kv: -kv[1])]
    # A manager who finds the right article reads the sections around the one that led there: the leading articles
    # each give up to ARTICLE_SECTIONS of their reached sections, in turn, before the rest fill the limit.
    articles = list(dict.fromkeys(sections[i].chapter for i in ordered))[:LEAD_ARTICLES]
    by_article = {a: [i for i in ordered if sections[i].chapter == a][:ARTICLE_SECTIONS] for a in articles}
    chosen: list[int] = []
    for depth in range(ARTICLE_SECTIONS):
        chosen += [by_article[a][depth] for a in articles if depth < len(by_article[a])]
    chosen += [i for i in ordered if i not in chosen]
    return [(sections[i], round(fused[i], 4)) for i in chosen[:limit]]


# --- the passage index -----------------------------------------------------------------------------------------------

def _rel(path: Path | str, data_dir: Path) -> str:
    path = Path(path)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(data_dir.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _indexed(data_dir: Path) -> dict[str, float] | None:
    """Each file the passage index holds, with when it was cut; None without an index. Read only."""
    import sqlite3

    from jason.community import passage_index

    path = passage_index.index_path(data_dir)
    if not path.is_file():
        return None
    try:
        db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            return {rel: float(at) for rel, at in db.execute("SELECT path, indexed_at FROM files")}
        finally:
            db.close()
    except sqlite3.Error:
        return None


def index_covers(data_dir: Path, files: Sequence[Path | str], indexed: dict[str, float] | None = None) -> bool:
    """The index holds every one of ``files`` (paths under ``data_dir``) as it is on disk now: none is missing, and none
    changed after it was cut. No files is no cover: an empty tier has nothing to read from the index."""
    indexed = _indexed(data_dir) if indexed is None else indexed
    if not indexed or not files:
        return False
    for file in files:
        rel = _rel(file, data_dir)
        at = indexed.get(rel)
        if at is None:
            return False
        try:
            if (data_dir / rel).stat().st_mtime > at:
                return False
        except OSError:
            return False
    return True


def _folder_files(folder: Path) -> list[Path]:
    """The files ``passages.corpus`` would cut under a folder."""
    return [p for p in sorted(folder.rglob("*")) if p.is_file() and p.suffix.lower() in (".md", ".txt")]


def index_search(data_dir: Path, *, confidential: bool, embedder: Any = None) -> Callable[..., Sequence[Any]]:
    """A ``retrieval.search`` over the index: the same call (query, folders, k, data_dir, mode), the passages of those
    folders ranked as cutting them would rank them, and confidential files only when ``confidential``."""
    from jason.community import passage_index

    def search(query: str, *folders: Path | str, k: int, data_dir: Path = data_dir, mode: str = "hybrid") -> Sequence[Any]:
        scope = passage_index.Scope(folders=tuple(_rel(f, Path(data_dir)) for f in folders), confidential=confidential)
        return [h.hit for h in passage_index.search(query, data_dir=data_dir, scope=scope, k=k, mode=mode, embedder=embedder)]

    return search


def index_law_ranking(sections: Sequence[LawSection], data_dir: Path, *, mode: str, embedder: Any = None,
                      depth: int | None = None) -> Callable[[str, int], list[int]]:
    """``rank_sections`` for ``law_sources`` from the index: the law pages' passages ranked for the question, each read
    as the section it falls in (by its heading, else by where it starts), the first ``n`` sections in order. A passage
    before a page's first section (its title and source lines) answers for no section."""
    from jason.community import passage_index, retrieval

    by_file: dict[str, list[int]] = {}
    for i, s in enumerate(sections):
        by_file.setdefault(_rel(s.file, data_dir), []).append(i)
    for indexes in by_file.values():
        indexes.sort(key=lambda i: sections[i].start_word)
    folders = tuple(sorted({rel.rsplit("/", 1)[0] for rel in by_file if "/" in rel}))
    scope = passage_index.Scope(standings=(passage_index.Standing.AUTHORITY,), folders=folders)

    def section_of(passage: Passage) -> int | None:
        indexes = by_file.get(_rel(passage.path, data_dir))
        if not indexes:
            return None
        labels = {label.strip() for label in passage.heading.split(" > ")[1:]}
        for i in indexes:
            if sections[i].citation in labels:
                return i
        found = None
        for i in indexes:
            if sections[i].start_word <= passage.start_word:
                found = i
        return found

    def rank_sections(question: str, n: int) -> list[int]:
        # A section is several passages, so the ranking goes deep enough to reach n sections.
        hits = passage_index.search(question, data_dir=data_dir, scope=scope, k=depth or max(n * 4, retrieval.DENSE_DEPTH),
                                    mode=mode, embedder=embedder)
        out: list[int] = []
        for h in hits:
            i = section_of(h.hit.passage)
            if i is not None and i not in out:
                out.append(i)
                if len(out) >= n:
                    break
        return out

    return rank_sections


def cited_statutes(texts: list[str]) -> tuple[list[str], list[str]]:
    """The statutes the texts cite: (current citations, pre-2014 Davis-Stirling citations)."""
    from jason.community.outlines import outline_from_text
    from jason.community.references import TargetKind, extract, statute_key

    current: dict[str, None] = {}
    prior: dict[str, None] = {}
    for text in texts:
        for ref in extract(outline_from_text(text, key="passage"), {}):
            if ref.kind is TargetKind.STATUTE:
                (prior if ref.prior else current).setdefault(statute_key(ref.target)[0], None)
    return list(current), list(prior)


# --- the governing documents -----------------------------------------------------------------------------------------

def governing_sources(community: Any, task: TaskPrompt, data_dir: Path, *, ask: str = "", draft: str = "", k: int = 4,
                      mode: str = "keyword", limit: int = 16, search: Callable[..., Any] | None = None) -> list[tuple[Tier, str, str, str, float]]:
    """The best passages for the task's questions: (tier, title, text, place, score), copies folded, best first. When the
    task names governing kinds, only those kinds are kept."""
    from jason.community import retrieval

    folders = [(data_dir / rel, folder) for rel, folder in CORPUS if (data_dir / rel).is_dir()]
    folder_of = {str(path.resolve()): folder for path, folder in folders}
    wanted = {kind for kind in task.documents if kind in GOVERNING_KINDS}
    find = search or retrieval.search
    hits: list[tuple[float, Any]] = []
    for query in _questions(task, ask, draft):
        for hit in find(query, *[p for p, _ in folders], k=k * 3, data_dir=data_dir, mode=mode):
            hits.append((hit.score, hit.passage))
    hits.sort(key=lambda h: -h[0])
    kept: list[tuple[Tier, str, str, str, float]] = []
    kinds: list[Any] = []
    for score, passage in hits:
        name = _doc_name(passage.path)
        kind = community.classify_document(name, folder_of.get(str(passage.path.parent.resolve())))
        if wanted and kind not in wanted:
            continue
        if any(k_ == kind and _same(passage.text, text) for k_, (_, _, text, _, _) in zip(kinds, kept)):
            continue
        kept.append((tier_of_kind(kind), name, passage.text, f"{passage.path.name}, passage {passage.index}", score))
        kinds.append(kind)
        if len(kept) >= limit:
            break
    return kept


# --- the records -----------------------------------------------------------------------------------------------------

def library_files(data_dir: Path, kind: DocumentKind, *, confidential: bool, files: int = RECORD_FILES) -> list[tuple[str, str, str]]:
    """The latest files of one kind in the classified library: (title, period, text)."""
    from jason.tasks.library import distinct, load, text_for

    rows = [r for r in distinct(load(data_dir)) if r["kind"] == kind.value and (confidential or not r["confidential"])]
    rows.sort(key=lambda r: str(r.get("period") or ""), reverse=True)
    out = []
    for row in rows[:files]:
        text = text_for(data_dir, row["id"])
        if text.strip():
            out.append((str(row["path"]), str(row.get("period") or ""), text))
    return out


def record_sources(task: TaskPrompt, questions: Sequence[str], rank: Callable[..., Sequence[Any]], *,
                   files: Callable[[DocumentKind], list[tuple[str, str, str]]]) -> list[tuple[Tier, str, str, str, float]]:
    """For each record kind the task names, the passages of its latest files that best answer the questions."""
    out: list[tuple[Tier, str, str, str, float]] = []
    for kind in task.documents:
        if kind in GOVERNING_KINDS:
            continue
        items: list[Passage] = []
        titles: dict[str, str] = {}
        for title, period, text in files(kind):
            path = Path(title)
            titles[str(path)] = f"{title}" + (f" ({period})" if period else "")
            items.extend(passages_of(path, text))
        best: dict[tuple[str, int], tuple[float, Passage]] = {}
        for question in questions:
            for hit in rank(question, items, RECORD_PASSAGES * 2):
                key = (str(hit.passage.path), hit.passage.index)
                if key not in best or best[key][0] < hit.score:
                    best[key] = (float(hit.score), hit.passage)
        for score, passage in sorted(best.values(), key=lambda b: -b[0])[:RECORD_PASSAGES]:
            out.append((tier_of_kind(kind), titles.get(str(passage.path), passage.path.name), passage.text,
                        f"{kind.value.replace('_', ' ')}, passage {passage.index}", score))
    return out


# --- jason's records -------------------------------------------------------------------------------------------------

def fact_sources(task: TaskPrompt, data_dir: Path, *, runner: Callable[[str, dict[str, Any]], Any] | None = None) -> tuple[list[tuple[str, str]], list[str]]:
    """Each named jason record as (title, JSON text), and the ones that could not be read."""
    out: list[tuple[str, str]] = []
    gaps: list[str] = []
    for source in task.facts:
        args = dict(source.args)
        try:
            if runner is not None:
                result = runner(source.tool, args)
            else:
                import inspect

                from jason.mcp import county

                tool = getattr(county, source.tool)
                if "data_dir" in inspect.signature(tool).parameters:
                    args["data_dir"] = data_dir
                result = tool(**args)
        except Exception as exc:  # a missing store is a gap in the pack, not a failure of the task
            gaps.append(f"{source.tool}: {exc}")
            continue
        text = json.dumps(result, ensure_ascii=False, default=str)
        if len(text) > FACT_CHARS:
            text = text[:FACT_CHARS] + " …(trimmed)"
        label = source.tool + (" " + ", ".join(f"{k}={v}" for k, v in source.args) if source.args else "")
        out.append((label + (f": {source.why}" if source.why else ""), text))
    return out, gaps


# --- the pack --------------------------------------------------------------------------------------------------------

def _trim(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + " …(trimmed)"


def assemble(community: Any, task: TaskPrompt, data_dir: Path, *, ask: str = "", draft: str = "", k: int = 4,
             mode: str = "keyword", follow_citations: bool = True, law: Sequence[LawSection] | None = None,
             search: Callable[..., Any] | None = None, files: Callable[[DocumentKind], list[tuple[str, str, str]]] | None = None,
             fact_runner: Callable[[str, dict[str, Any]], Any] | None = None, use_index: bool = True,
             law_index: bool | None = None, embedder: Any = None) -> ContextPack:
    """The pack for one task. With ``use_index`` the governing documents come from the passage index when it covers
    them (``index_covers``), and so does the law's ranking when ``law_index`` (default ``LAW_FROM_INDEX``); the rest are
    cut from the folders. ``search``, ``law``, and ``files`` replace a tier's reader (tests). ``embedder`` replaces the
    local embedder in dense and hybrid modes."""
    pack = ContextPack(task, ask=ask, draft=draft, association=tuple(community.prompt_context()))
    rank = _ranker(mode, data_dir, embedder)
    questions = _questions(task, ask, draft)
    indexed = _indexed(data_dir) if use_index else None

    sections = list(law) if law is not None else law_corpus(data_dir)
    pack.shelf = law_shelf(sections)
    by_citation = {s.citation: s for s in sections}
    if not sections:
        pack.gaps.append("no law on hand; run jason export-authorities")
    pages = list(dict.fromkeys(s.file for s in sections))
    if (LAW_FROM_INDEX if law_index is None else law_index) and indexed and all(pages) and index_covers(data_dir, pages, indexed):
        chosen = law_sources(questions, sections, k=k,
                             rank_sections=index_law_ranking(sections, data_dir, mode=mode, embedder=embedder))
    else:
        chosen = law_sources(questions, sections, rank, k=k)

    if search is None and indexed:
        governing_files = [f for rel, _ in CORPUS if (data_dir / rel).is_dir() for f in _folder_files(data_dir / rel)]
        if index_covers(data_dir, governing_files, indexed):
            search = index_search(data_dir, confidential=task.audience is Audience.BOARD, embedder=embedder)
    if search is None and embedder is not None:
        from jason.community import retrieval

        def search(query: str, *folders: Path | str, k: int, data_dir: Path, mode: str) -> Sequence[Any]:
            return retrieval.search(query, *folders, k=k, data_dir=data_dir, mode=mode, embedder=embedder)
    governing = governing_sources(community, task, data_dir, ask=ask, draft=draft, k=k, mode=mode, search=search)
    cited: set[str] = set()
    if follow_citations:
        cited = set(cited_statutes([text for _, _, text, _, _ in governing])[0])
        current, prior = cited_statutes([text for _, _, text, _, _ in governing] + ([draft] if draft else []))
        have = {s.citation for s, _ in chosen}
        for citation in current:
            if citation in have:
                continue
            if citation in by_citation:
                chosen.append((by_citation[citation], 0.0))
                have.add(citation)
            else:
                pack.gaps.append(f"{citation} is cited by a source but is not in the law on hand")
        pack.gaps += [f"{c} is a former Davis-Stirling number cited by a source; find the section in force" for c in prior]
    for n, (section, score) in enumerate(chosen, 1):
        note = "found for the task's topics" if score else ""
        if section.citation in cited:
            note = (note + "; " if note else "") + "cited by a governing document"
        pack.sources.append(Source(f"S{n}", tier_of_citation(section.citation), section.citation,
                                   _trim(section.text, STATUTE_CHARS), section.chapter, score, note))

    for n, (tier, title, text, place, score) in enumerate(sorted(governing, key=lambda g: (g[0], -g[4])), 1):
        pack.sources.append(Source(f"G{n}", tier, title, text, place, score))

    reader = files or (lambda kind: library_files(data_dir, kind, confidential=task.audience is Audience.BOARD))
    for n, (tier, title, text, place, score) in enumerate(record_sources(task, questions, rank, files=reader), 1):
        pack.sources.append(Source(f"R{n}", tier, title, text, place, score))

    if draft:
        pack.sources.append(Source("D1", Tier.RECORD, "the current text under review", draft, "draft"))
    facts, gaps = fact_sources(task, data_dir, runner=fact_runner)
    pack.gaps += gaps
    for n, (title, text) in enumerate(facts, 1):
        pack.sources.append(Source(f"F{n}", Tier.RECORD, title, text, "jason records"))
    return pack


__all__ = ["CORPUS", "GOVERNING_KINDS", "ContextPack", "LawSection", "Source", "assemble", "cited_statutes", "fact_sources",
           "governing_sources", "index_covers", "index_law_ranking", "index_search", "law_corpus", "law_shelf", "law_sources",
           "library_files", "record_sources"]
