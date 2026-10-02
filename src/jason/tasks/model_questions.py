"""Ask the local model a kind's questions about each library file and set its answers beside the rule reader.

``run`` takes the stored readings of one kind (``data/documents/readings.json``, from ``jason models``), reads each
file's text (``text_for``), asks the question set (``jason.community.question_sets``) of the local model with its JSON
schema, and judges each answer (``jason.community.questions.judge``). The result is
``data/documents/questions-<kind>.json``: per file, each question's verdict, and per question, how often the two
readers agree, differ, or neither finds it. Each request holds the GPU lock and runs the preflight first; the text
never leaves the machine. A confidential file is asked like any other and its answers stay on disk.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from jason.community.questions import QuestionSet, Verdict, judge, prompt, schema
from jason.community.symbols import DocumentKind

MAX_CHARS = 60_000                      # well inside the 64k-token window with the prompt and the answer


def _asker(model: str) -> Callable[[str, dict[str, Any]], dict[str, Any]]:
    from jason.community.ollama_extractor import DEFAULT_CONTEXT, OLLAMA_URL, _post

    def ask(text: str, fmt: dict[str, Any]) -> dict[str, Any]:
        body = {"model": model, "stream": False, "think": False, "format": fmt,
                "options": {"temperature": 0, "num_ctx": DEFAULT_CONTEXT},
                "messages": [{"role": "user", "content": text}]}
        answer = _post(f"{OLLAMA_URL}/api/chat", body, 900)
        return json.loads((answer.get("message") or {}).get("content") or "{}")

    return ask


def ask_file(qs: QuestionSet, text: str, fields: dict[str, Any], ask: Callable[[str, dict[str, Any]], dict[str, Any]]) -> list[dict[str, Any]]:
    answers = ask(prompt(qs, text[:MAX_CHARS]), schema(qs))
    return [judge(q, answers.get(q.key) or {}, text, fields) for q in qs.questions]


def run(data_dir: Path, community: Any, kind: DocumentKind, *, limit: int = 0, model: str = "",
        ask: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None, log: Callable[[str], None] | None = None) -> dict[str, Any]:
    from jason.tasks.library import text_for

    hook = getattr(community, "question_sets", None)
    sets = hook() if callable(hook) else {}
    if not sets:
        from jason.community.question_sets import QUESTION_SETS as sets
    qs = sets.get(kind)
    if qs is None:
        raise ValueError(f"no question set for {kind.value}; there are sets for {', '.join(k.value for k in sets)}")
    if ask is None:
        from jason.community.ollama_extractor import DEFAULT_MODEL
        from jason.local_ai import preflight

        model = model or DEFAULT_MODEL
        preflight(model)
        ask = _asker(model)
    store = json.loads((Path(data_dir) / "documents" / "readings.json").read_text(encoding="utf-8")).get("readings", [])
    rows = [r for r in store if r.get("kind") == kind.value and r.get("hasText")]
    if limit:
        rows = rows[:limit]
    files = []
    for n, row in enumerate(rows, 1):
        text = text_for(Path(data_dir), row["id"])
        started = datetime.now(timezone.utc)
        try:
            verdicts = ask_file(qs, text, row.get("fields") or {}, ask)
            error = ""
        except Exception as exc:  # one file the model cannot answer does not stop the run
            verdicts, error = [], f"{type(exc).__name__}: {exc}"
        seconds = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
        files.append({"id": row["id"], "name": row.get("name"), "confidential": bool(row.get("confidential")),
                      "seconds": seconds, "error": error, "answers": verdicts})
        if log:
            log(f"{n}/{len(rows)} {row.get('name')}: {seconds}s {error or Counter(v['verdict'] for v in verdicts).most_common()}")
    by_question: dict[str, Counter] = defaultdict(Counter)
    for f in files:
        for v in f["answers"]:
            by_question[v["key"]][v["verdict"]] += 1
    result = {"askedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind.value, "model": model,
              "files": files, "byQuestion": {k: dict(c) for k, c in by_question.items()}}
    out = Path(data_dir) / "documents" / f"questions-{kind.value}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


def summary_lines(result: dict[str, Any]) -> list[str]:
    order = [v.value for v in Verdict]
    out = [f"{result['kind']}: {len(result['files'])} files asked of {result['model'] or 'the model'}; "
           f"{sum(1 for f in result['files'] if f['error'])} failed", "",
           f"  {'question':<24} " + " ".join(f"{v[:10]:>10}" for v in order)]
    for key, counts in result["byQuestion"].items():
        out.append(f"  {key:<24} " + " ".join(f"{counts.get(v, 0):>10}" for v in order))
    return out


__all__ = ["ask_file", "run", "summary_lines"]
