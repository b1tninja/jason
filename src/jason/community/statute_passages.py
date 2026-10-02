"""Words a statute requires a notice to print verbatim, cut from the law on hand when a document is built.

Several notices must reproduce statutory text exactly: the "Notice: Assessments and Foreclosure" (Civil Code 5730), the
alternative dispute resolution sentence (5965), the insurance summary's boldface statement (5300(b)(9)), and the FHA and
VA statements (5300(b)(10), (11)). A template carries a token for each (``{NOTICE_ASSESSMENTS_AND_FORECLOSURE}``), and
the token is filled from the exported statute at build time, so when the Legislature amends the words and
``jason export-authorities`` runs again, the next packet prints the new words. A passage is the quoted text that follows
its marker in the section, with the PDF's line wrapping undone and its paragraphs kept.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

# token -> (section, the text the quotation follows)
STATUTORY_TEXT: dict[str, tuple[str, str]] = {
    "NOTICE_ASSESSMENTS_AND_FORECLOSURE": ("CIV 5730", "(a)"),
    "ADR_STATEMENT": ("CIV 5965", "(a)"),
    "INSURANCE_STATEMENT": ("CIV 5300", "(9)"),
    "FHA_STATEMENT": ("CIV 5300", "(10)"),
    "VA_STATEMENT": ("CIV 5300", "(11)"),
}
OPEN, CLOSE = "“", "”"


def unwrap(text: str) -> str:
    """Undo a PDF's line wrapping: single line breaks inside a paragraph become spaces; paragraphs stay apart."""
    paragraphs = re.split(r"\n\s*\n", text.strip())
    return "\n\n".join(re.sub(r"\s*\n\s*", " ", p).strip() for p in paragraphs if p.strip())


def quoted_after(text: str, marker: str) -> str:
    """The first passage in curly quotes after ``marker`` (a subdivision such as "(9)" at the start of a line)."""
    start = 0
    if marker:
        m = re.search(rf"(?m)^\s*{re.escape(marker)}\s", text) or re.search(re.escape(marker), text)
        if not m:
            raise LookupError(f"{marker} is not in the section")
        start = m.end()
    begin = text.find(OPEN, start)
    if begin < 0:
        raise LookupError(f"no quoted passage after {marker}")
    depth, i = 0, begin
    while i < len(text):
        if text[i] == OPEN:
            depth += 1
        elif text[i] == CLOSE:
            depth -= 1
            if depth == 0:
                return unwrap(text[begin + 1:i])
        i += 1
    raise LookupError(f"the quotation after {marker} does not close")


def passages(data_dir: Path, *, lookup: Callable[[str], dict[str, Any]] | None = None) -> tuple[dict[str, str], list[str]]:
    """Each statutory token's words, and the tokens whose section or passage was not found."""
    from jason.tasks.export_authorities import authority_text

    find = lookup or (lambda citation: authority_text(data_dir, citation))
    values: dict[str, str] = {}
    gaps: list[str] = []
    for token, (citation, marker) in STATUTORY_TEXT.items():
        found = find(citation)
        if not found.get("found"):
            gaps.append(f"{token}: {citation} is not in the law on hand")
            continue
        try:
            values[token] = quoted_after(str(found.get("text") or ""), marker)
        except LookupError as exc:
            gaps.append(f"{token}: {citation} {exc}")
    return values, gaps


__all__ = ["STATUTORY_TEXT", "passages", "quoted_after", "unwrap"]
