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
   for the board. (The passage index can answer in the library's place; see below.)
4. **C, a collection's material**, only when the caller names a ``Collection`` (``document_collections``): the passages
   of the collection's index scope that best answer the task's questions, near copies folded, capped per file and
   overall. Each carries the collection's label in place of a tier ("evidence gathered for this matter: neither the
   record nor the law" for a legal case), because a case file is not the association's record. A confidential
   collection goes only into a board task's pack; for any other audience it is refused with a gap line, never
   silently left out. Without an index, or with nothing indexed under the scope, a gap line says so, and so does one
   for the files in the collection's folder that the index does not hold (a PDF with no text extract).
5. **F, jason's records**: the MCP tools the task names, as JSON, trimmed. A collection's context lines (for a legal
   case, its record in the specification) follow them as one more F source, and then its summary page when it has
   one (``jason collection KEY --write``): one source, labeled "jason's summary of the collection: a summary, not the
   record". The summary is never a C source: a collection's scope leaves its generated pages out.
6. **D1**: the text under review.

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
- R reads the classified library, as before, by default. ``records_index`` (``RECORDS_FROM_INDEX``) reads the index's
  ``library`` catalog instead (``index_record_sources``), one of two ways (``records_reach``, ``RecordReach``):
  ``LATEST`` takes the same latest files of each kind and their passages as the index holds them; ``KIND`` ranks every
  file of the kind for the task's questions and fuses that with recency, one passage a file, so an older file that
  answers can be chosen over the latest three. Either way a document the index holds back as confidential stays out
  of a pack that is not the board's, with a gap line saying how many: the index holds back whole kinds the library
  does not flag (``index_sources.HELD_KINDS``), so it is stricter than the library reader.
  Measured on the profile's six tasks that name record kinds (October 4, 2026; docs/rag-roadmap.md): ``LATEST`` gave
  the library reader's sources on none of them, keyword or hybrid. The index cuts a file on its sections and ranks
  each passage with the file's context line; the library reader cuts 220-word windows and ranks the bare words. So
  the passages differ even where the files agree, and nothing says which serve a task better: there is no gold set
  for the pack. It stays off, and so does ``KIND``.
- F and D read no passages.
- C reads only the index: a collection is an index scope, so there are no folders to cut in its place.

A tier is cut from the folders (R: read from the library) as before when the index is missing, lacks one of the
tier's files, or holds one older than the file on disk (``index_covers``): a stale index never answers for a file that
changed. For R the files are those the library reader would read (and, across a kind, every file of the kind the
index holds); a file whose words the library reader joins from a vision reading of some pages and the older text is
in no one indexed file, so it sends the tier back too.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Sequence

from jason.community.authority_order import Tier, tier_of_citation, tier_of_kind
from jason.community.passages import Passage, passages_of
from jason.community.prompts import Audience, TaskPrompt, as_of_lines, system_prompt, task_text
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


class RecordReach(Enum):
    """Which files of a record kind the records tier ranks when it reads the index (``index_record_sources``)."""

    LATEST = "the latest files of the kind"      # the files the library reader takes
    KIND = "every file of the kind"              # all of them, fused with recency


# The records tier from the index's library catalog. Off: its passages are not the library reader's (see above), and
# nothing yet says which serve a task better.
RECORDS_FROM_INDEX = False
RECORDS_REACH = RecordReach.LATEST
RECORD_PER_FILE = 1           # across a kind, passages from any one file
# Across a kind, the k that fuses the questions' rankings (small, as ``retrieval.HYBRID_RRF_K``, so a question's first
# places count) and the weight of the files' order by period, which is fused at ``RRF_K``. Neither is tuned: there is
# no gold set for the pack.
RECORD_RRF_K = 10
RECORD_RECENCY_WEIGHT = 1.0
# Across a kind in dense and hybrid modes, the cosine below which the dense ranking's passage is left out. None: no
# floor has been measured for the records (``retrieval.NO_ANSWER_COSINE`` found none on the governing documents).
RECORD_DENSE_FLOOR: float | None = None
COLLECTION_PASSAGES = 8       # a collection's passages in one pack
COLLECTION_PER_FILE = 2       # of those, from any one file
# A collection's summary page (``document_collections.companion_summary``) is one F source, cut to this length: its
# files, what is missing, its open questions, and its conflicts, without its chronology. It is never ranked with the
# collection's passages: a collection's scope leaves its generated pages out, since a page that quotes every document
# would take the places of the documents themselves. The length is not tuned: there is no gold set for the pack.
COLLECTION_SUMMARY_CHARS = 16000
# Where each kind of source sits among sources of one tier: a collection's material after the records, before the facts.
_LETTER_ORDER = {"S": 0, "G": 1, "R": 2, "C": 3, "F": 4, "D": 5}


@dataclass(frozen=True)
class AttachedReading:
    """A stored reading listed under a source's words (``law_readings.LawReading``), as the review's record keeps it."""

    key: str
    standing: str              # plain, reading, two_readings
    whose: str                 # board, counsel, jason (a lead)
    dated: str
    state: str                 # current (attached as a reading); stale, missing, misquoted (listed, not applied); later
    provision: str             # the provision it was listed under
    says: str = ""             # the reading's own sentences: never the provision's words (``ContextPack.reading_texts``)


@dataclass(frozen=True)
class Recitation:
    """What a law or governing source recites: the provision and the digest of its words. In a pack built as of a
    day it also says whether the disk shows the source's words in force that day, what the page prints above the
    words (``above``: what they are), the provision's words given under a passage that is not them (``words``), and
    the readings listed last (``below``, ``readings``), each labeled. Without a day only the citation and the digest
    are set, and the page prints nothing more."""

    citation: str              # "CIV 5855", "bylaws#7.2"; "" when no section is named for a governing passage
    digest: str = ""
    as_of: date | None = None
    shown: bool | None = None  # as of a day: the source gives words shown to be in force that day
    # How: prior, current, own_words, not_shown (``law_text.Decided``), not_found; for a governing passage as_amended
    # (the passage itself), as_amended_below (the section's words under it), not_kept, unnamed.
    decided: str = ""
    others: tuple[str, ...] = ()   # the digests of the other versions given, where the words do not decide between them
    above: tuple[str, ...] = ()
    words: str = ""
    words_title: str = ""
    below: tuple[str, ...] = ()
    readings: tuple[AttachedReading, ...] = ()


@dataclass(frozen=True)
class Source:
    id: str
    tier: Tier
    title: str
    text: str
    place: str = ""            # a file and passage, a citation, or a tool
    score: float = 0.0
    note: str = ""
    # What the source is when it has no place in the order of authority (a collection's material): shown in place of
    # the tier, which then only sets where the source sits on the page.
    label: str = ""
    standing: Any = None       # its ``passage_index.Standing``, where the source has one
    file: str = ""             # the file it was read from, under the data directory
    section: str = ""          # the section or passage within the file
    provision: Recitation | None = None    # a law source's, always; a governing source's in a pack built as of a day


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
    # The collection the caller named (``document_collections.Collection``), and whether its material is in the pack:
    # a confidential collection is refused to any audience but the board, with a gap line.
    collection: Any = None
    collection_included: bool = False
    # The day the matter turns on, when the caller named one: the law and the governing documents are then recited as
    # of that day (``assemble``). None is today, and the pack is what it was before a review took a day.
    as_of: date | None = None

    def texts(self) -> dict[str, str]:
        """Each source's words, for checking a quotation (``prompts.verify``): its text, and the provision's words
        given under a governing passage as of a day. Never a reading."""
        return {s.id: s.text + (f"\n{s.provision.words}" if s.provision is not None and s.provision.words else "")
                for s in self.sources}

    def reading_texts(self) -> dict[str, str]:
        """By source id, what the readings listed under a source say: a quotation found here and not in the source's
        words quotes a reading as the provision (``prompts.verify``)."""
        found = {s.id: "\n".join(r.says for r in s.provision.readings if r.says) for s in self.sources if s.provision is not None}
        return {sid: says for sid, says in found.items() if says}

    def as_of_lines(self) -> tuple[str, ...]:
        """What the task is told about the day the pack was built for (``prompts.as_of_lines``). None without one."""
        return as_of_lines(self.as_of) if self.as_of is not None else ()

    def _ordered(self) -> list[Source]:
        return sorted((s for s in self.sources if not s.id.startswith("D")),
                      key=lambda s: (s.tier, _LETTER_ORDER.get(s.id[0], 9), int(s.id[1:])))

    def collection_lines(self) -> tuple[str, ...]:
        """What the task is told about the collection's sources: what they are and how to cite them. None without them."""
        ids = [s.id for s in self.sources if s.id.startswith("C")]
        if self.collection is None or not ids:
            return ()
        span = ids[0] if len(ids) == 1 else f"{ids[0]} to {ids[-1]}"
        told = (f"COLLECTION: {self.collection.title} ({self.collection.kind.value}). Sources {span} are "
                f"{self.collection.label}.",
                "Cite a C source by its id for what its document says, and name the document. What a document in the "
                "collection states is its author's statement: it is not a finding, not the association's record unless "
                "its note says so, and never a rule.")
        summary = [s for s in self.sources if s.id.startswith("F") and s.label]      # the collection's summary page
        if not summary:
            return told
        return (*told, f"Source {summary[0].id} is {summary[0].label}. Use it to see what the collection holds and "
                       "what is missing. It is not a document of the collection: what it quotes is its copy of a "
                       "document's words, so say so and name the document, and never cite it as the record or a rule.")

    def task_prompt(self) -> str:
        """The task's prompt for this pack: the task's own text, the as-of lines when the pack was built for a day,
        and the collection's lines when it has sources."""
        return task_text(self.task, ask=self.ask, draft=self.draft, extra=self.as_of_lines() + self.collection_lines())

    def sources_text(self) -> str:
        blocks = []
        for s in self._ordered():
            note = f" — {s.note}" if s.note else ""
            what = f"collection ({s.label})" if s.label else f"tier {int(s.tier)} ({s.tier.label})"
            p = s.provision
            if p is None or not p.above:
                blocks.append(f"[{s.id}] {what}: {s.title}{note}\n{s.text.strip()}")
                continue
            # Built as of a day: what the words are, the words, the provision's words under a passage, the readings.
            lines = [f"[{s.id}] {what}: {s.title}{note}", "ABOUT THE WORDS (not part of them):", *(f"  {a}" for a in p.above),
                     "THE WORDS:", s.text.strip()]
            if p.words:
                lines += [p.words_title, p.words.strip()]
            lines += p.below                   # the readings, each labeled as one: never the words
            blocks.append("\n".join(lines))
        if self.shelf:
            blocks.append("THE LAW ON HAND, by chapter (not sources; what retrieval could draw on):\n" + "\n".join(f"  {line}" for line in self.shelf))
        return "\n\n".join(blocks)

    def markdown(self) -> str:
        parts = [f"# {self.task.kind.value.capitalize()}", "", "## Base prompt", "", system_prompt(self.association), "", "## Task", "",
                 self.task_prompt(), "", "## Sources, in order of authority", ""]
        for s in self._ordered():
            note = f" — {s.note}" if s.note else ""
            where = f" ({s.place})" if s.place else ""
            what = f"Collection: {s.label}" if s.label else f"Tier {int(s.tier)}: {s.tier.label}"
            p = s.provision
            if p is None or not p.above:
                parts += [f"### [{s.id}] {s.title}{where}", f"*{what}{note}*", "", s.text.strip(), ""]
                continue
            parts += [f"### [{s.id}] {s.title}{where}", f"*{what}{note}*", "", *(f"- {a}" for a in p.above), "", s.text.strip(), ""]
            if p.words:
                parts += [p.words_title, "", p.words.strip(), ""]
            if p.below:
                parts += [*p.below, ""]
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
    return [row for row, _ in governing_passages(community, task, data_dir, ask=ask, draft=draft, k=k, mode=mode,
                                                 limit=limit, search=search)]


def governing_passages(community: Any, task: TaskPrompt, data_dir: Path, *, ask: str = "", draft: str = "", k: int = 4,
                       mode: str = "keyword", limit: int = 16, search: Callable[..., Any] | None = None
                       ) -> list[tuple[tuple[Tier, str, str, str, float], Passage]]:
    """``governing_sources``, each row with the passage it was read from (its file and its section heading)."""
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
    read: list[Passage] = []
    for score, passage in hits:
        name = _doc_name(passage.path)
        kind = community.classify_document(name, folder_of.get(str(passage.path.parent.resolve())))
        if wanted and kind not in wanted:
            continue
        if any(k_ == kind and _same(passage.text, text) for k_, (_, _, text, _, _) in zip(kinds, kept)):
            continue
        kept.append((tier_of_kind(kind), name, passage.text, f"{passage.path.name}, passage {passage.index}", score))
        kinds.append(kind)
        read.append(passage)
        if len(kept) >= limit:
            break
    return list(zip(kept, read))


# --- as of a day -----------------------------------------------------------------------------------------------------
#
# A pack built as of a day recites each provision through ``law_readings.recite``: the words in force that day where
# the disk shows them, else the words held now under a plain label, and under them each stored reading as a reading.

def _attached(recital: Any) -> tuple[AttachedReading, ...]:
    """The readings a recital lists, as the review's record keeps them: current, not applied (by state), or later."""
    rows = ([(r, r.status.state.value) for r in (*recital.readings, *recital.not_applied)]
            + [(r, "later") for r in recital.later])
    return tuple(AttachedReading(r.reading.key, r.reading.standing.value, r.reading.whose.value,
                                 r.reading.dated.isoformat(), state, recital.citation,
                                 " ".join(part for part in (r.reading.reading, *r.reading.alternatives) if part))
                 for r, state in rows)


def law_as_of(section: LawSection, data_dir: Path, as_of: date, readings: Sequence[Any] = (), *,
              community: Any = None) -> tuple[str, str, Recitation]:
    """One law source as of a day: (its words, its status for the source's note, what it recites).

    The words are those ``recite`` gives for the day: an earlier version with its range and the act that made it, the
    current words where a record places them in force by then, or, of two versions printed under one number, the one
    their own words pick, with the deciding sentences. Where the disk does not show which words governed, the words
    on the shelf now are given under "Not shown to be in force", every version when the shelf prints several, with
    what would bring the earlier words. Where the shelf cannot be asked at all (the section is not on it), the words
    the pack was given are kept under the same label. Never today's words silently."""
    from jason.community import law_readings, law_text

    day = as_of.isoformat()
    recital = law_readings.recite(section.citation, data_dir, readings, as_of, community=community)
    below = tuple(recital.reading_lines())
    if not recital.found:
        digest = law_text.words_digest(section.text)
        above = (f"Digest of these words: {digest}", f"As of: {day}",
                 f"Not shown to be in force on {day}: these are the words the pack was given, and the shelf could not be "
                 f"asked about that day ({recital.reason or 'the section was not found on the shelf'})")
        return section.text, f"NOT SHOWN TO BE IN FORCE on {day}", Recitation(
            section.citation, digest, as_of, False, "not_found", above=above, below=below, readings=_attached(recital))
    words = recital.words
    for n, other in enumerate(recital.others, start=2):
        words += (f"\n\n[{recital.citation}, version {n} of {len(recital.others) + 1} on the shelf; digest {other.digest}]"
                  f"\n\n{other.words}")
    above = (*recital.about_lines(), *(f"Caveat: {c}" for c in recital.caveats))
    status = f"in force on {day}" if recital.in_force else f"NOT SHOWN TO BE IN FORCE on {day}: the words on the shelf now"
    return words, status, Recitation(recital.citation, recital.digest, as_of, recital.in_force, recital.decided,
                                     tuple(o.digest for o in recital.others), above, below=below, readings=_attached(recital))


def _run(text: str) -> str:
    """A text's words in order, punctuation and case aside, with a space at either end so a word matches whole."""
    return " " + " ".join(re.findall(r"[a-z0-9]+", (text or "").casefold())) + " "


def _passage_is(passage: Passage, words: str) -> bool:
    """Whether a passage's words are a section's words: the passage is a run of the section's words, or it holds the
    section's words whole and nothing else but the labels its own heading names (the section's number and caption,
    the article above it). One changed word is a difference; so is another section's sentence in the passage."""
    mine, theirs = _run(passage.text), _run(words)
    if not mine.strip() or not theirs.strip():
        return False
    if mine in theirs:
        return True
    at = mine.find(theirs)
    if at < 0:
        return False
    labels = set(_run(passage.heading).split())
    return all(word in labels for word in (mine[:at] + " " + mine[at + len(theirs):]).split())


def _overlap(a: str, b: str) -> bool:
    """One text holds most of the other's words: a passage that sits in a section, or a short section in a passage."""
    wa, wb = _words(a), _words(b)
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= SAME_TEXT


def section_numbers(heading: str) -> list[str]:
    """The section numbers a passage's heading names, innermost first: the number each label after the document's
    title opens with ("7.2 Notice" is 7.2, "ARTICLE 7 MEETINGS" is 7). A label that opens with no number names none."""
    from jason.community.outlines import normalize_number

    out: list[str] = []
    for label in reversed([part.strip() for part in (heading or "").split(" > ")[1:]]):
        words = label.split()
        if not words:
            continue
        token = words[1] if words[0].casefold() == "article" and len(words) > 1 else words[0]
        number = normalize_number(token.rstrip(".:-"))
        if any(ch.isdigit() for ch in number) and number not in out:
            out.append(number)
    return out


def governing_section(passage: Passage, data_dir: Path, community: Any, as_of: date, readings: Sequence[Any] = (), *,
                      outlines: Any = None) -> tuple[Any, str, list[str], str]:
    """The section of a document jason keeps by section that a governing passage falls in, recited as of the day:
    (the recital, the document's key, the numbers its heading names, why none was found).

    The G tier ranks passages, not sections. A passage the index cut on its sections carries the section's path in
    its heading; the document is the one whose outline matches the passage's file (``OutlineIndex.find``, as the
    cutter found it). Each number the heading names is tried, innermost first, and counts only when the document has
    that section and the section's words and the passage's overlap. A passage cut by words, a file no outline
    matches, and a heading with no number name no section: a miss with its reason, never a guess."""
    from jason.community import law_readings
    from jason.community.passage_sections import OutlineIndex, export_header

    if not (hasattr(community, "living_documents") and hasattr(community, "citable_documents")):
        return None, "", [], "the profile keeps no documents by section"
    numbers = section_numbers(passage.heading)
    if not numbers:
        return None, "", [], ("its heading names no numbered section" if passage.heading
                              else "it was cut by words and carries no section heading")
    try:
        text = Path(passage.path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        text = ""
    title, meta, _ = export_header(text)
    outline = (outlines or OutlineIndex.load(Path(data_dir) / "outlines")).find(Path(passage.path), title, meta)
    key = str((outline or {}).get("key") or "")
    if not key:
        return None, "", numbers, "no outline of a document jason keeps matches its file"
    why = ""
    for number in numbers:
        recital = law_readings.recite(f"{key}#{number}", data_dir, readings, as_of, community=community)
        if recital.found and _overlap(passage.text, recital.words):
            return recital, key, numbers, ""
        why = recital.reason or f"the passage's words are not those of {key}#{number} as jason keeps it"
    return None, key, numbers, why


def governing_as_of(passage: Passage, data_dir: Path, community: Any, as_of: date, readings: Sequence[Any] = (), *,
                    outlines: Any = None) -> tuple[str, Recitation]:
    """One governing source as of a day: (its status for the source's note, what it recites). The source's text stays
    the passage, which is its file's words as the file reads now.

    - **A document kept as amended** (``Community.living_documents()``): where the passage's words are in its
      section as amended to the day, the passage is in force that day. Where they are not, the section's words on
      that day are given under the passage (``Recitation.words``), and those are the words to recite.
    - **A document kept only as it reads now:** the passage is labeled not shown to be in force that day.
    - **A passage no section is named for:** the same label, with why. No reading is attached to it.

    The readings of the section, and of each section around it the heading names, are listed last, each labeled."""
    from jason.community import law_readings

    day = as_of.isoformat()
    recital, key, numbers, why = governing_section(passage, data_dir, community, as_of, readings, outlines=outlines)
    if recital is None:
        above = (f"As of: {day}",
                 f"Not shown to be in force on {day}: these are the words of this file as it reads now. No section of a "
                 f"document jason keeps by section is named for the passage ({why}), so its words on that day were not "
                 "looked up, and no reading is attached by section.")
        return f"NOT SHOWN TO BE IN FORCE on {day}: the file as it reads now", Recitation("", "", as_of, False, "unnamed", above=above)
    target = recital.citation
    kept = any(getattr(d, "key", "") == key for d in community.living_documents())
    words = title = ""
    if kept and _passage_is(passage, recital.words):
        decided, status = "as_amended", f"in force on {day}"
        line = (f"In force on {day}: the passage's words are in {target} as jason keeps the document amended to that day.")
    elif kept:
        decided, status = "as_amended_below", f"in force on {day}: the words of {target} under the passage"
        line = (f"The passage is this file's copy as it reads now, and its words are not the words of {target} as jason "
                f"keeps the document amended to {day}. In force on {day}: the words of {target} that follow the passage; "
                "recite those.")
        words, title = recital.words, f"{target} as amended to {day} (digest {recital.digest}; {recital.source}):"
    else:
        decided, status = "not_kept", f"NOT SHOWN TO BE IN FORCE on {day}: the file as it reads now"
        line = (f"Not shown to be in force on {day}: {key} is not kept as amended. These are the words of this file as it "
                "reads now, which may differ from the words in force that day.")
    section_words = f"on {day}" if kept else "now"
    above = (f"The passage falls in {target} ({recital.source}). Digest of the section's words {section_words}: {recital.digest}",
             f"As of: {day}", line,
             *(f"Caveat: {c}" for c in recital.caveats if not c.startswith(f"{key} is not kept as amended")))
    below = list(recital.reading_lines())
    attached = list(_attached(recital))
    for number in numbers:
        # A reading of a section around the passage's reads words the passage is part of.
        outer = f"{key}#{number}"
        if outer == target or not any(r.reads(outer) for r in readings):
            continue
        around = law_readings.recite(outer, data_dir, readings, as_of, community=community)
        if around.found and (around.readings or around.not_applied or around.later):
            below += [f"Of {outer}, a section the passage sits in (digest {around.digest}):", *around.reading_lines()]
            attached += _attached(around)
    return status, Recitation(target, recital.digest, as_of, kept, decided, above=above, words=words, words_title=title,
                              below=tuple(below), readings=tuple(attached))


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


def _best_passages(questions: Sequence[str], items: Sequence[Passage],
                   rank: Callable[..., Sequence[Any]]) -> list[tuple[float, Passage]]:
    """The passages that best answer any one of the questions: each question ranks them, a passage keeps its best
    score, and the ``RECORD_PASSAGES`` best are kept."""
    best: dict[tuple[str, int], tuple[float, Passage]] = {}
    for question in questions:
        for hit in rank(question, items, RECORD_PASSAGES * 2):
            key = (str(hit.passage.path), hit.passage.index)
            if key not in best or best[key][0] < hit.score:
                best[key] = (float(hit.score), hit.passage)
    return sorted(best.values(), key=lambda b: -b[0])[:RECORD_PASSAGES]


def _record_title(path: str, period: str) -> str:
    return f"{path}" + (f" ({period})" if period else "")


def _record_place(kind: DocumentKind, passage: Passage) -> str:
    return f"{kind.value.replace('_', ' ')}, passage {passage.index}"


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
            titles[str(path)] = _record_title(title, period)
            items.extend(passages_of(path, text))
        for score, passage in _best_passages(questions, items, rank):
            out.append((tier_of_kind(kind), titles.get(str(passage.path), passage.path.name), passage.text,
                        _record_place(kind, passage), score))
    return out


def _library_index(data_dir: Path) -> dict[str, tuple[str, bool]] | None:
    """Each file of the index's library catalog, with its kind and whether the index holds it back; None without an
    index. Read only."""
    import sqlite3

    from jason.community import passage_index
    from jason.tasks.index_sources import LIBRARY

    path = passage_index.index_path(data_dir)
    if not path.is_file():
        return None
    try:
        db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        try:
            return {rel: (str(kind), bool(held)) for rel, kind, held in
                    db.execute("SELECT path, kind, confidential FROM files WHERE catalog = ?", (LIBRARY,))}
        finally:
            db.close()
    except sqlite3.Error:
        return None


def _held_back_line(count: int, kind: DocumentKind, task: TaskPrompt) -> str:
    what = kind.value.replace("_", " ")
    return (f"the passage index holds back {count} {what} file{'' if count == 1 else 's'} as confidential that the "
            f"library does not flag; this task's audience is {task.audience.value}: nothing from "
            f"{'it' if count == 1 else 'them'} is in this pack")


def index_record_sources(task: TaskPrompt, questions: Sequence[str], data_dir: Path, *, confidential: bool,
                         mode: str = "keyword", embedder: Any = None, reach: RecordReach = RecordReach.LATEST, k: int = 4,
                         indexed: dict[str, float] | None = None
                         ) -> tuple[list[tuple[Tier, str, str, str, float]], list[str]] | None:
    """``record_sources`` from the passage index's library catalog: the sources, and the gap lines for what was held
    back. None when the index cannot answer for the library reader: there is no index, it lacks a file that reader
    would read, it holds one older than the file on disk (``index_covers``), or the reader would join a vision reading
    of some pages with the older text, which no indexed file holds.

    A document is the audience's to read only when both stores say so: the library's flag, as before, and the index's
    (``index_sources.LibrarySource``, which also holds back whole kinds the library does not flag). Each document
    the index alone holds back is counted in a gap line, never silently left out.

    ``reach`` picks the files of each kind:

    - ``LATEST``: the ``RECORD_FILES`` latest by period, as the library reader picks them, their passages as the index
      cut them (on their sections, with the file's context line), ranked as ``record_sources`` ranks.
    - ``KIND``: every file of the kind. Each question ranks the kind's passages (``k * 3`` deep, near copies folded
      onto the latest file's copy), the rankings are fused by reciprocal rank (``RECORD_RRF_K``), and recency is one
      more ranking in the fusion (``RECORD_RECENCY_WEIGHT``, at ``RRF_K``): the files by period, newest first, a
      file with no period after them all. It orders passages the questions rank alike and does not lift one past a
      clearly better answer. One file gives at most ``RECORD_PER_FILE`` passages, so an older file that answers
      the questions can stand beside, or in place of, the latest. In dense and hybrid modes ``RECORD_DENSE_FLOOR``,
      when set, leaves a passage far from a question out of that question's dense ranking."""
    from jason.community import passage_index, retrieval
    from jason.tasks.index_sources import LIBRARY
    from jason.tasks.library import distinct, distinct_key, load, text_joined, text_owner, text_path

    kinds = [kind for kind in task.documents if kind not in GOVERNING_KINDS]
    if not kinds:
        return [], []
    indexed = _indexed(data_dir) if indexed is None else indexed
    held = _library_index(data_dir) if indexed else None
    if not indexed or held is None:
        return None
    copies = load(data_dir)
    documents = {distinct_key(row): row for row in distinct(copies)}
    copy_of = {str(row["id"]): row for row in copies}
    # The index's file for each document: the file is named after one of the document's copies (``text_path``).
    file_of: dict[str, str] = {}
    for rel in held:
        copy = copy_of.get(text_owner(rel))
        if copy is not None:
            file_of.setdefault(distinct_key(copy), rel)
    dense = mode not in ("keyword", "exact")
    live = (embedder or retrieval.default_embedder(data_dir)) if dense else None

    def closed(row: dict[str, Any]) -> bool:
        rel = file_of.get(distinct_key(row))
        return rel is not None and held[rel][1]

    out: list[tuple[Tier, str, str, str, float]] = []
    gaps: list[str] = []
    for kind in kinds:
        rows = [row for row in documents.values() if row["kind"] == kind.value and (confidential or not row["confidential"])]
        rows.sort(key=lambda row: str(row.get("period") or ""), reverse=True)
        seen = rows if confidential else [row for row in rows if not closed(row)]
        if len(seen) < len(rows):
            gaps.append(_held_back_line(len(rows) - len(seen), kind, task))
        # What the library reader would read: the latest files that have words. The index must hold each as it is.
        latest: dict[str, dict[str, Any]] = {}
        for row in seen[:RECORD_FILES]:
            path = text_path(data_dir, row["id"])
            if path is None:
                continue
            rel = _rel(path, data_dir)
            if held.get(rel, ("", False))[0] != kind.value or text_joined(data_dir, row["id"]) \
                    or not index_covers(data_dir, [rel], indexed):
                return None
            latest[rel] = row
        if reach is RecordReach.LATEST:
            if not latest:
                continue
            scope = passage_index.Scope(catalogs=(LIBRARY,), paths=tuple(latest), confidential=confidential)
            loaded = passage_index.load(data_dir, scope, vectors=dense)
            rank = _ranker(mode, data_dir, passage_index.StoredEmbedder(loaded.vectors, live) if dense else None)
            for score, passage in _best_passages(questions, loaded.passages, rank):
                row = latest[_rel(passage.path, data_dir)]
                out.append((tier_of_kind(kind), _record_title(str(row["path"]), str(row.get("period") or "")), passage.text,
                            _record_place(kind, passage), score))
            continue
        # Every file of the kind the audience may read, with the library's row for its title and period.
        shelf: dict[str, dict[str, Any]] = {}
        for rel, (file_kind, flag) in held.items():
            copy = copy_of.get(text_owner(rel))
            if file_kind != kind.value or copy is None or (flag and not confidential):
                continue
            document = documents[distinct_key(copy)]
            if document["confidential"] and not confidential:
                continue
            # A document whose first copy was never classified is shelved under the copy that was.
            shelf[rel] = document if document["kind"] == kind.value else copy
        if not shelf:
            continue
        if not index_covers(data_dir, list(shelf), indexed):
            return None
        periods = sorted({str(row.get("period") or "") for row in shelf.values()} - {""}, reverse=True)
        newest = {period: place for place, period in enumerate(periods, 1)}

        def age(passage: Passage) -> int:
            """The file's place by period, newest first; a file with no period is after them all."""
            return newest.get(str(shelf[_rel(passage.path, data_dir)].get("period") or ""), len(newest) + 1)

        scope = passage_index.Scope(catalogs=(LIBRARY,), kinds=(kind.value,), confidential=confidential)
        fused: dict[tuple[str, int], float] = {}
        found: dict[tuple[str, int], Passage] = {}
        for question in questions:
            place = 0
            for hit in passage_index.search(question, data_dir=data_dir, scope=scope, k=k * 3, mode=mode, embedder=live,
                                            dense_floor=RECORD_DENSE_FLOOR):
                same = [p for p in (hit.hit.passage, *hit.hit.also) if _rel(p.path, data_dir) in shelf]
                if not same:
                    continue
                passage = min(same, key=age)                 # of one passage's copies, the latest file's
                place += 1
                key = (_rel(passage.path, data_dir), passage.index)
                fused[key] = fused.get(key, 0.0) + 1.0 / (RECORD_RRF_K + place)
                found.setdefault(key, passage)
        # Recency never brings in a passage no question reached. Its k is the large one, so the whole spread of the
        # files' order is about one first place of one question: it orders passages the questions rank alike.
        for key, passage in found.items():
            fused[key] += RECORD_RECENCY_WEIGHT / (RRF_K + age(passage))
        kept: list[Passage] = []
        taken: dict[str, int] = {}
        for key, score in sorted(fused.items(), key=lambda kv: -kv[1]):
            passage = found[key]
            if taken.get(key[0], 0) >= RECORD_PER_FILE or any(_same(passage.text, other.text) for other in kept):
                continue
            kept.append(passage)
            taken[key[0]] = taken.get(key[0], 0) + 1
            row = shelf[key[0]]
            out.append((tier_of_kind(kind), _record_title(str(row["path"]), str(row.get("period") or "")), passage.text,
                        _record_place(kind, passage), round(score, 4)))
            if len(kept) >= RECORD_PASSAGES:
                break
    return out, gaps


# --- a collection ----------------------------------------------------------------------------------------------------

def _collection_scope(collection: Any, confidential: bool) -> Any:
    """The collection's index scope for an audience: as it is for one that may see held files, else without whatever
    opened them."""
    from dataclasses import replace

    return collection.scope if confidential else replace(collection.scope, confidential=False, confidential_in=())


def collection_sources(collection: Any, questions: Sequence[str], data_dir: Path, *, confidential: bool, k: int = 4,
                       mode: str = "keyword", embedder: Any = None, limit: int = COLLECTION_PASSAGES,
                       per_file: int = COLLECTION_PER_FILE) -> list[tuple[Any, float]]:
    """The passages of a collection's index scope that best answer the questions: (index hit, fused score), best first.
    Each question ranks the scope and the rankings are fused by reciprocal rank, as the law's are. A near copy of a
    passage already kept is folded, one file gives at most ``per_file``, and the pack takes at most ``limit``. Without
    ``confidential`` the scope loses whatever opened held files: an audience that may not see them never does."""
    from jason.community import passage_index

    scope = _collection_scope(collection, confidential)
    fused: dict[tuple[str, int], float] = {}
    found: dict[tuple[str, int], Any] = {}
    for question in questions:
        hits = passage_index.search(question, data_dir=data_dir, scope=scope, k=k * 3, mode=mode, embedder=embedder)
        for place, hit in enumerate(hits, 1):
            key = (str(hit.hit.passage.path), hit.hit.passage.index)
            fused[key] = fused.get(key, 0.0) + 1.0 / (RRF_K + place)
            found.setdefault(key, hit)
    kept: list[tuple[Any, float]] = []
    taken: dict[str, int] = {}
    for key, score in sorted(fused.items(), key=lambda kv: -kv[1]):
        passage = found[key].hit.passage
        if taken.get(key[0], 0) >= per_file or any(_same(passage.text, other.hit.passage.text) for other, _ in kept):
            continue
        kept.append((found[key], round(score, 4)))
        taken[key[0]] = taken.get(key[0], 0) + 1
        if len(kept) >= limit:
            break
    return kept


def _unindexed(collection: Any, data_dir: Path, indexed: dict[str, float]) -> tuple[int, int]:
    """How many of the files in the collection's folder the index does not hold, and how many files there are. A file
    is held when it is indexed itself or a text extract named after it is ("Complaint.pdf.md" for "Complaint.pdf")."""
    folder = getattr(collection, "folder", "")
    root = data_dir / folder if folder else None
    if root is None or not root.is_dir():
        return 0, 0
    names = [_rel(p, data_dir) for p in sorted(root.rglob("*")) if p.is_file()]
    held = [rel for rel in names if rel in indexed]
    unread = [rel for rel in names if rel not in indexed and not any(other.startswith(rel + ".") for other in held)]
    return len(unread), len(names)


def _collection_tier(pack: ContextPack, collection: Any, questions: Sequence[str], data_dir: Path, *, k: int, mode: str,
                     embedder: Any, indexed: dict[str, float] | None) -> bool:
    """Put a collection's passages in the pack as C sources, or say in the gaps why they are not there. True when the
    task's audience may see the collection (so its context lines may follow)."""
    from jason.community import passage_index

    board = pack.task.audience is Audience.BOARD
    if collection.confidential and not board:
        pack.gaps.append(f"the collection is confidential; this task's audience is {pack.task.audience.value}: "
                         "nothing from it is in this pack")
        return False
    what = f"the collection ({collection.title})"
    counted = passage_index.count(data_dir, _collection_scope(collection, board)) if indexed is not None else None
    if counted is None:
        pack.gaps.append(f"{what} was not searched: there is no passage index to read; run jason index --build")
        return True
    unread, on_disk = _unindexed(collection, data_dir, indexed or {})
    if unread:
        pack.gaps.append(f"the passage index lacks {unread} of the {on_disk} files of {what} on disk (no text to "
                         "search): the pack cannot show them")
    if not counted[1]:
        pack.gaps.append(f"{what} holds no indexed passages: fetch its files, then run jason index --build")
        return True
    kept = collection_sources(collection, questions, data_dir, confidential=board, k=k, mode=mode, embedder=embedder)
    if not kept:
        pack.gaps.append(f"no passage of {what} matched the task's questions ({counted[0]} files, {counted[1]} passages searched)")
    files: dict[str, None] = {}
    for n, (hit, score) in enumerate(kept, 1):
        passage, row = hit.hit.passage, hit.row
        rel = _rel(passage.path, data_dir)
        files.setdefault(rel)
        note = f"standing: {row.standing.value}; catalog: {row.catalog}" + ("; confidential" if row.confidential else "")
        pack.sources.append(Source(f"C{n}", Tier.RECORD, passage.title, passage.text, f"{rel}, passage {passage.index}", score,
                                   note, label=collection.label, standing=row.standing, file=rel,
                                   section=passage.heading or f"passage {passage.index}"))
    # The index answers with the words it cut. A file that changed since is still answered, and the pack says so.
    pack.gaps += [f"{rel} changed after the index cut it, or is gone: the pack shows the indexed words; run jason index --build"
                  for rel in files if not index_covers(data_dir, [rel], indexed)]
    return True


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
             law_index: bool | None = None, embedder: Any = None, collection: Any = None,
             records_index: bool | None = None, records_reach: RecordReach | None = None,
             as_of: date | None = None) -> ContextPack:
    """The pack for one task. With ``use_index`` the governing documents come from the passage index when it covers
    them (``index_covers``), and so does the law's ranking when ``law_index`` (default ``LAW_FROM_INDEX``) and the
    records when ``records_index`` (default ``RECORDS_FROM_INDEX``; ``records_reach``, default ``RECORDS_REACH``, picks
    the files of each kind); the rest are cut from the folders and the library. ``search``, ``law``, and ``files``
    replace a tier's reader (tests). ``embedder`` replaces the local embedder in dense and hybrid modes. ``collection``
    (``document_collections.Collection``) adds the C sources and the collection's context lines; without it the pack
    is what it was before collections.

    ``as_of`` is the day the matter turns on. None is today, and the page is then byte for byte what it was before a
    review took a day; each law source still carries its provision's digest (``Source.provision``), which costs no
    read. With a day:

    - **S:** the sections are found as before, in the law as it stands now, and each is then recited as of the day
      (``law_as_of``, through ``law_readings.recite``): the words in force that day with their range and the act
      that made them, or the words on the shelf now under "Not shown to be in force". A section the shelf prints in
      two versions is one source: the version its own words make operative that day, or both when they do not decide.
    - **G:** a passage stays its file's words as the file reads now, and says so. Where its heading names a section of
      a document jason keeps by section, the section is recited as of the day (``governing_as_of``): for a document
      kept as amended, the section's words on that day, given under the passage when the passage is not them.
    - **Readings** (``Community.law_readings()``): each stored reading of a provision is listed under its words,
      labeled with whose it is, its standing, and its date; a stale one is listed as stale and not applied; one dated
      after the day is set apart. A reading is never part of a source's text (``ContextPack.texts``).
    - **R, C, F** are as they are now: nothing in them is recited by date.
    - The task's prompt gains the as-of lines (``prompts.as_of_lines``), and the gaps count the sources not shown to
      be in force that day.

    Reciting a section of a document kept as amended reads its versions, which ``section_refs.build_versions``
    caches under ``data/section-refs`` when the cache is stale, as ``jason cite`` does."""
    from jason.community.passage_index import Standing

    pack = ContextPack(task, ask=ask, draft=draft, association=tuple(community.prompt_context()), collection=collection,
                       as_of=as_of)
    readings: tuple[Any, ...] = ()
    if as_of is not None:
        from jason.community import law_readings

        readings = law_readings.readings(community)
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
    read = governing_passages(community, task, data_dir, ask=ask, draft=draft, k=k, mode=mode, search=search)
    governing = [row for row, _ in read]
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
    from jason.community.law_text import words_digest

    if as_of is not None:
        # One source a section: two versions under one number are recited together, by their own words.
        seen: set[str] = set()
        chosen = [(s, score) for s, score in chosen if not (s.citation in seen or seen.add(s.citation))]
    for n, (section, score) in enumerate(chosen, 1):
        note = "found for the task's topics" if score else ""
        if section.citation in cited:
            note = (note + "; " if note else "") + "cited by a governing document"
        words, recited = section.text, Recitation(section.citation, words_digest(section.text))
        if as_of is not None:
            words, status, recited = law_as_of(section, data_dir, as_of, readings, community=community)
            note = (note + "; " if note else "") + status
        pack.sources.append(Source(f"S{n}", tier_of_citation(section.citation), section.citation,
                                   _trim(words, STATUTE_CHARS), section.chapter, score, note,
                                   standing=Standing.AUTHORITY, file=section.file, section=section.citation,
                                   provision=recited))

    outlines = None
    if as_of is not None and read:
        from jason.community.passage_sections import OutlineIndex

        outlines = OutlineIndex.load(data_dir / "outlines")
    for n, ((tier, title, text, place, score), passage) in enumerate(sorted(read, key=lambda g: (g[0][0], -g[0][4])), 1):
        if as_of is None:
            pack.sources.append(Source(f"G{n}", tier, title, text, place, score, standing=Standing.RECORD))
            continue
        status, recited = governing_as_of(passage, data_dir, community, as_of, readings, outlines=outlines)
        pack.sources.append(Source(f"G{n}", tier, title, text, place, score, status, standing=Standing.RECORD,
                                   provision=recited))
    if as_of is not None:
        day = as_of.isoformat()
        for letter, what, why in (
                ("S", "law", "each gives the words on the shelf now under that label, with what would bring the earlier "
                             "words (jason law-history --versions reads the session publications lawlibrary holds)"),
                ("G", "governing", "a document not kept as amended, or a passage whose heading names no section, is given "
                                   "as its file reads now")):
            tier_sources = [s for s in pack.sources if s.id.startswith(letter)]
            dark = [s.id for s in tier_sources if s.provision is not None and not s.provision.shown]
            if dark:
                pack.gaps.append(f"as of {day}: {len(dark)} of the {len(tier_sources)} {what} sources are not shown to be in "
                                 f"force that day ({', '.join(dark)}): {why}")

    records = None
    if files is None and indexed and (RECORDS_FROM_INDEX if records_index is None else records_index):
        found = index_record_sources(task, questions, data_dir, confidential=task.audience is Audience.BOARD, mode=mode,
                                     embedder=embedder, reach=RECORDS_REACH if records_reach is None else records_reach,
                                     k=k, indexed=indexed)
        if found is not None:
            records, held_back = found
            pack.gaps += held_back
    if records is None:
        reader = files or (lambda kind: library_files(data_dir, kind, confidential=task.audience is Audience.BOARD))
        records = record_sources(task, questions, rank, files=reader)
    for n, (tier, title, text, place, score) in enumerate(records, 1):
        pack.sources.append(Source(f"R{n}", tier, title, text, place, score, standing=Standing.RECORD))

    if collection is not None:
        pack.collection_included = _collection_tier(pack, collection, questions, data_dir, k=k, mode=mode,
                                                    embedder=embedder, indexed=indexed)

    if draft:
        pack.sources.append(Source("D1", Tier.RECORD, "the current text under review", draft, "draft"))
    facts, gaps = fact_sources(task, data_dir, runner=fact_runner)
    pack.gaps += gaps
    for n, (title, text) in enumerate(facts, 1):
        pack.sources.append(Source(f"F{n}", Tier.RECORD, title, text, "jason records", standing=Standing.PAGE))
    if pack.collection_included and collection.context:
        # What holds for the whole collection, as the specification records it: facts, not the documents' own words.
        pack.sources.append(Source(f"F{len(facts) + 1}", Tier.RECORD, f"{collection.context_title}: {collection.title}",
                                   _trim("\n".join(collection.context), STATUTE_CHARS), "the specification",
                                   note="what holds for the whole collection; not the documents' own words",
                                   standing=Standing.PAGE))
    if pack.collection_included:
        from jason.community.document_collections import companion_summary

        summary = companion_summary(collection, data_dir)
        if summary is not None:
            # The collection's generated summary, once, as a labeled fact source: never a C source, never evidence.
            number = sum(1 for s in pack.sources if s.id.startswith("F")) + 1
            pack.sources.append(Source(f"F{number}", Tier.RECORD, summary.title,
                                       _trim(summary.text, COLLECTION_SUMMARY_CHARS), summary.file, note=summary.note,
                                       label=summary.label, standing=Standing.PAGE, file=summary.file))
    return pack


__all__ = ["COLLECTION_PASSAGES", "COLLECTION_PER_FILE", "CORPUS", "GOVERNING_KINDS", "AttachedReading", "ContextPack",
           "LawSection", "Recitation", "RecordReach", "Source", "assemble", "cited_statutes", "collection_sources",
           "fact_sources", "governing_as_of", "governing_passages", "governing_section", "governing_sources",
           "index_covers", "index_law_ranking", "index_record_sources", "index_search", "law_as_of", "law_corpus",
           "law_shelf", "law_sources", "library_files", "record_sources", "section_numbers"]
