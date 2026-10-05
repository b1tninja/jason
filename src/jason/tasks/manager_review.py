"""A manager's review of one task: the context pack, the local model's answer, and each quote checked.

``build`` assembles the pack for a task (``context_pack.assemble``) and ``save_pack`` writes it as one Markdown page,
``data/briefs/<task>.md``: the base prompt, the task prompt, and the numbered sources. That page is the useful part on
its own: a person, Claude, or any model can work from it.

``run`` sends the pack to the local chat model (Ollama, ``qwen3.6:27b`` at the shared window, no thinking, temperature 0,
the answer constrained to ``ANSWER_SCHEMA``) under the GPU lock after the preflight, then ``verify`` checks each quote
against the source it cites. The text never leaves the machine. The result is ``data/briefs/<task>.review.json`` and a
Markdown report beside it. A review is a draft for the board, never a decision.

Those two files are the latest pack and review, written over each time. ``review_store`` keeps each pack that differed
(and each run) under ``data/reviews``, so reviews of one draft under two collections sit side by side.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Callable

from jason.community.context_pack import ContextPack, assemble
from jason.community.prompts import ANSWER_SCHEMA, Checked, TaskPrompt, parse_answer, system_prompt, verify

BRIEFS = "briefs"


def build(community: Any, task: TaskPrompt, data_dir: Path, *, ask: str = "", draft: str = "", mode: str = "hybrid",
          k: int = 4, collection: Any = None, as_of: date | None = None) -> ContextPack:
    """The pack. A task's topics are paraphrases of what the documents say, so the default is hybrid retrieval (the
    keyword ranking fused with the local embedder); without the embedder it falls back to keyword and says so.
    ``collection`` (``document_collections.Collection``) adds its material as its own tier. ``as_of`` is the day the
    matter turns on: the law and the governing documents are recited as of it, and the stored readings attached
    (``context_pack.assemble``); None is today, and the pack is what it was."""
    from jason.community.retrieval import EmbeddingUnavailable

    try:
        return assemble(community, task, data_dir, ask=ask, draft=draft, mode=mode, k=k, collection=collection, as_of=as_of)
    except EmbeddingUnavailable as exc:
        if mode == "keyword":
            raise
        first = exc
    # The chat model from an earlier review may hold the commit the embedder needs; release it once and try again.
    try:
        from jason.community.ollama_extractor import DEFAULT_MODEL
        from jason.local_ai import unload

        unload(DEFAULT_MODEL)
        return assemble(community, task, data_dir, ask=ask, draft=draft, mode=mode, k=k, collection=collection, as_of=as_of)
    except (EmbeddingUnavailable, OSError) as exc:
        first = exc
    pack = assemble(community, task, data_dir, ask=ask, draft=draft, mode="keyword", k=k, collection=collection, as_of=as_of)
    pack.gaps.append(f"retrieval fell back to keyword: {first}")
    return pack


def brief_path(data_dir: Path, task: TaskPrompt, name: str = "") -> Path:
    return data_dir / BRIEFS / f"{name or task.kind.slug}.md"


def save_pack(pack: ContextPack, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(pack.markdown(), encoding="utf-8")
    return path


def messages(pack: ContextPack) -> list[dict[str, str]]:
    user = (pack.task_prompt() + "\n\nSOURCES, in order of authority:\n\n"
            + pack.sources_text() + ("\n\nGAPS (not among the sources):\n" + "\n".join(f"- {g}" for g in pack.gaps) if pack.gaps else ""))
    return [{"role": "system", "content": system_prompt(pack.association)}, {"role": "user", "content": user}]


def run(pack: ContextPack, *, model: str = "", post: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        timeout: int = 1800) -> Checked:
    """Ask the local model and check its answer. ``post`` is for tests; left unset, the request goes through
    ``ollama_extractor._post`` (the GPU lock) after ``local_ai.preflight``."""
    from jason.community.ollama_extractor import DEFAULT_CONTEXT, DEFAULT_MODEL, OLLAMA_URL, _post

    name = model or DEFAULT_MODEL
    if post is None:
        from jason.community.retrieval import EMBED_MODEL
        from jason.local_ai import preflight, unload

        # Hybrid retrieval left the embedder loaded; the chat model and it do not both fit in commit (docs/document-tools.md).
        unload(EMBED_MODEL)
        preflight(name)
    payload = {"model": name, "stream": False, "think": False, "format": ANSWER_SCHEMA,
               "options": {"temperature": 0, "num_ctx": DEFAULT_CONTEXT}, "messages": messages(pack)}
    poster = post or (lambda url, body: _post(url, body, timeout))
    answer = poster(f"{OLLAMA_URL}/api/chat", payload)
    content = (answer.get("message") or {}).get("content", "") if isinstance(answer, dict) else ""
    # A quote of a reading attached to a source, given as the source's words, is not grounded, and says why.
    return verify(parse_answer(content), pack.texts(), pack.reading_texts())


def report(pack: ContextPack, checked: Checked) -> str:
    """The review as Markdown: issues with their rules and facts, each quote marked when it was not found, or when it
    quotes a reading attached to the source as the provision's words."""
    from jason.community.prompts import READING_QUOTED

    bad = {(u["source"], u["quote"]): u.get("why", "") for u in checked.ungrounded}
    titles = {s.id: s.title for s in pack.sources}
    a = checked.answer

    def mark(item: dict[str, Any]) -> str:
        why = bad.get((item.get("source"), item.get("quote")))
        if why is None:
            return ""
        return f" **({why})**" if why == READING_QUOTED else " **(quote not found)**"

    lines = [f"# Review: {pack.task.kind.value}", ""]
    if pack.as_of is not None:
        lines += [f"As of {pack.as_of.isoformat()}: each law and governing source says whether its words are shown to be "
                  "in force that day.", ""]
    lines += [f"Quotes checked: {checked.grounded} found in their sources, {len(checked.ungrounded)} not found.", ""]
    for issue in a.get("issues") or []:
        lines += [f"## {issue.get('issue')}", ""]
        for item in issue.get("rules") or []:
            lines.append(f"- Rule [{item.get('source')}: {titles.get(item.get('source'), '?')}] ({item.get('force')}): "
                         f"\"{item.get('quote')}\"{mark(item)}")
        for item in issue.get("facts") or []:
            lines.append(f"- Fact [{item.get('source')}]: \"{item.get('quote')}\"{mark(item)}")
        lines += ["", f"Application: {issue.get('application')}", "", f"Conclusion: {issue.get('conclusion')}", ""]
    if a.get("considerations"):
        lines += ["## Considerations", "", "| Consideration | Sources | Status | Note |", "|---|---|---|---|"]
        lines += [f"| {e.get('consideration')} | {', '.join(f'{s} {titles.get(s, chr(63))}' for s in e.get('sources') or [])} | "
                  f"{e.get('status')} | {e.get('note', '')} |" for e in a["considerations"]]
        lines.append("")
    for title, key in (("Conflicts", "conflicts"), ("For the board to decide", "board_decisions"), ("Open questions", "open_questions")):
        items = a.get(key) or []
        if items:
            lines += [f"## {title}", ""]
            lines += [f"- {i['higher']} over {i['lower']}: {i['note']}" if isinstance(i, dict) else f"- {i}" for i in items]
            lines.append("")
    if a.get("draft"):
        lines += ["## Draft", "", a["draft"], ""]
    if pack.gaps:
        lines += ["## Gaps in the sources", ""] + [f"- {g}" for g in pack.gaps]
    return "\n".join(lines) + "\n"


# A source as the review's JSON has always held it. What a source gained for collections and the review store (label,
# standing, file, section) is kept there (``review_store``), so nothing that reads this file sees a change.
_SOURCE_KEYS = ("id", "tier", "title", "text", "place", "score", "note")


def _source_row(source: Any) -> dict[str, Any]:
    row = asdict(source)
    return {key: int(source.tier) if key == "tier" else row[key] for key in _SOURCE_KEYS}


def save_review(pack: ContextPack, checked: Checked, path: Path) -> tuple[Path, Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"task": pack.task.kind.slug, "ask": pack.ask, "answer": checked.answer, "grounded": checked.grounded,
            "ungrounded": checked.ungrounded, "sources": [_source_row(s) for s in pack.sources], "gaps": pack.gaps}
    json_path = path.with_suffix(".review.json")
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path = path.with_suffix(".review.md")
    md_path.write_text(report(pack, checked), encoding="utf-8")
    return json_path, md_path
