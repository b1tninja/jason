"""A local email draft kept as a Google Doc, pictures and all, so a person reads and edits it in Docs.

Docs are the originals people edit (memory: agendas and templates are Docs). A draft in ``data/drafts`` is pushed to
a Doc in My Drive/Templates/PayHOA Broadcasts and pulled back after a person edits it there:

- **push**: Drive imports the draft's HTML as the Doc's body (``{placeholders}`` as plain text, highlighted as the
  template sync does). Drive's import drops pictures, so each ``<img src="local.png">`` is imported as a marker, and
  the picture is inserted at the marker with the Docs API, which fetches it from a link (``picture_link``: PayHOA's
  short-lived upload link; Docs keeps its own copy). The Doc's id for each picture is recorded beside the draft.
- **pull**: the Doc's body read back as composer HTML (``docs_html``, placeholders wrapped again), each picture put
  back as its local file; a picture a person added in the Doc is saved beside the draft from the Doc's own link.

The state is ``data/drafts/docs.json``: per draft, the Doc's id and its pictures by the Doc's object id.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any, Callable

from jason.google.docs_markdown import PICTURE_MARKER as MARKER
from jason.google.docs_markdown import PT_PER_PX, picture_ids, picture_requests
from jason.google.docs_markdown import picture_markers as marker_ranges

STATE = "docs.json"
_IMG = re.compile(r'<img\b[^>]*?\bsrc="(?!https?:|data:|docs-object:)([^"]+)"[^>]*>', re.I)
_WIDTH = re.compile(r'\bwidth="(\d+)"')
_ALT = re.compile(r'\balt="([^"]*)"')


def load_state(drafts: Path) -> dict[str, dict[str, Any]]:
    path = drafts / STATE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def save_state(drafts: Path, state: dict[str, dict[str, Any]]) -> None:
    (drafts / STATE).write_text(json.dumps(state, indent=1), encoding="utf-8")


def import_page(draft_html: str) -> tuple[bytes, list[tuple[str, int]]]:
    """The page Drive imports: the draft with each local picture as a marker paragraph; and the pictures in order,
    each with its width in pixels (0 when the draft gives none)."""
    from jason.tasks.template_docs import PLACEHOLDER

    pictures: list[tuple[str, int]] = []

    def marker(m: re.Match) -> str:
        width = _WIDTH.search(m.group(0))
        pictures.append((m.group(1), int(width.group(1)) if width else 0))
        return MARKER.format(m.group(1))

    body = _IMG.sub(marker, PLACEHOLDER.sub(lambda m: "{" + m.group(1) + "}", draft_html))
    page = f'<!doctype html><html><head><meta charset="utf-8"></head><body>{body}</body></html>'
    return page.encode("utf-8"), pictures


def list_kinds(draft_html: str) -> list[str]:
    """The draft's top-level lists in order, "ol" or "ul"."""
    kinds, depth = [], 0
    for m in re.finditer(r"<(/?)(ol|ul)\b", draft_html, re.I):
        if m.group(1):
            depth -= 1
        else:
            if depth == 0:
                kinds.append(m.group(2).lower())
            depth += 1
    return kinds


def numbering_requests(doc: dict[str, Any], kinds: list[str]) -> list[dict[str, Any]]:
    """Drive's import keeps a list but not whether it was numbered: each list the draft numbers (by order) gets
    numbered again."""
    from jason.tasks.template_docs import _tab

    spans: dict[str, list[int]] = {}
    order: list[str] = []
    for block in (_tab(doc).get("body") or {}).get("content") or []:
        bullet = (block.get("paragraph") or {}).get("bullet")
        if not isinstance(bullet, dict):
            continue
        list_id = str(bullet.get("listId") or "")
        if list_id not in spans:
            order.append(list_id)
            spans[list_id] = [block["startIndex"], block["endIndex"]]
        spans[list_id][1] = block["endIndex"]
    return [{"createParagraphBullets": {"range": {"startIndex": spans[i][0], "endIndex": spans[i][1] - 1},
                                       "bulletPreset": "NUMBERED_DECIMAL_ALPHA_ROMAN"}}
            for i, kind in zip(order, kinds) if kind == "ol"]


def push(drive: Any, draft: Path, *, title: str, folder: str, picture_link: Callable[[Path], str],
         state: dict[str, dict[str, Any]]) -> str:
    """Make or refresh the draft's Doc (a person's edits in the Doc since are replaced: pull first). Returns its id."""
    from jason.google.drive import GOOGLE_DOC_MIME_TYPE
    from jason.tasks.template_docs import highlight_requests

    page, pictures = import_page(draft.read_text(encoding="utf-8"))
    entry = state.get(draft.name) or {}
    doc_id = entry.get("docId")
    if doc_id:
        drive.replace_content(doc_id, page, mime_type="text/html")
        drive.update_metadata(doc_id, name=title)
    else:
        doc_id = drive.upload_bytes(title, page, mime_type="text/html", parent_id=folder, convert_to=GOOGLE_DOC_MIME_TYPE,
                                    description=f"Email draft data/drafts/{draft.name} (jason). Edit here; jason pulls "
                                                "the edits back before sending.",
                                    app_properties={"jason_draft": draft.name})
    docs = drive.docs()
    doc = docs.get(doc_id)
    markers = marker_ranges(doc)
    if markers:
        links = {name: picture_link(draft.parent / name) for name in {m[0] for m in markers}}
        docs.batch_update(doc_id, picture_requests(markers, links, dict(pictures)))
        doc = docs.get(doc_id)
    marks = numbering_requests(doc, list_kinds(draft.read_text(encoding="utf-8"))) + highlight_requests(doc)
    if marks:
        docs.batch_update(doc_id, marks)
    names = [m[0] for m in sorted(markers, key=lambda x: x[1])]
    alts = {m.group(1): (_ALT.search(m.group(0)) or [None, ""])[1]
            for m in _IMG.finditer(draft.read_text(encoding="utf-8"))}
    state[draft.name] = {"docId": doc_id, "title": title, "pictures": dict(zip(picture_ids(doc), names)), "alts": alts}
    return doc_id


def push_markdown(drive: Any, source: Path, *, name: str, folder: str, letterhead_id: str, footer: str,
                  picture_link: Callable[[Path], str], state: dict[str, dict[str, Any]], style: str = "report",
                  pdf: Path | None = None, articles: Any = ()) -> dict[str, Any]:
    """A Markdown file (an email draft, a guide, a notice) set on the letterhead as a Doc: a copy of the Letterhead the
    first time, rewritten in place after that, its id in ``state``; and, given ``pdf``, the Doc's PDF (to attach or
    post). The Markdown is the source: the Doc is rewritten from it, so edits belong in the file. The Doc reads as the
    email does: ``{HELP:...}`` filled from ``articles`` and statute citations linked."""
    from jason.community.links import fill_help_markdown, link_citations_markdown
    from jason.google.docs_markdown import LETTER, REPORT
    from jason.tasks.letters import markdown_doc

    entry = state.get(source.name) or {}
    text, _ = fill_help_markdown(source.read_text(encoding="utf-8"), articles)
    made = markdown_doc(drive, drive.docs(), link_citations_markdown(text).splitlines(), name=name,
                        folder_id=folder, letterhead_id=letterhead_id, footer=footer, doc_id=entry.get("docId", ""),
                        style=LETTER if style == "letter" else REPORT,
                        picture_link=lambda f: picture_link(source.parent / f))
    from jason.tasks.template_docs import highlight_requests

    marks = highlight_requests(drive.docs().get(made["id"]))       # {placeholders} PayHOA fills, [FIELDS] a person does
    if marks:
        drive.docs().batch_update(made["id"], marks)
    state[source.name] = {"docId": made["id"], "title": name, "letterhead": True, "pictures": made["pictures"]}
    if pdf is not None:
        made["pdf"] = str(drive.docs().export_pdf(made["id"], pdf))
    return made


def pull(drive: Any, draft: Path, *, state: dict[str, dict[str, Any]], fetch: Callable[[str], bytes]) -> list[str]:
    """Write the Doc's body back over the draft (the old one kept as ``.bak``). Returns the pictures added in the Doc,
    saved beside the draft."""
    from jason.google.docs_html import DOCS_OBJECT, document_html
    from jason.tasks.template_docs import composer_html

    entry = state[draft.name]
    doc = drive.docs().get(entry["docId"])
    body = composer_html(document_html(doc))
    known: dict[str, str] = dict(entry.get("pictures") or {})
    from jason.tasks.template_docs import _tab

    objects = _tab(doc).get("inlineObjects") or doc.get("inlineObjects") or {}     # a tabbed Doc keeps them per tab
    added: list[str] = []
    for object_id in picture_ids(doc):
        if object_id in known:
            continue
        emb = ((objects.get(object_id) or {}).get("inlineObjectProperties") or {}).get("embeddedObject") or {}
        uri = (emb.get("imageProperties") or {}).get("contentUri")
        if not uri:
            continue
        name = f"doc-pictures/{object_id.replace('.', '-')}.png"
        (draft.parent / name).parent.mkdir(parents=True, exist_ok=True)
        (draft.parent / name).write_bytes(fetch(uri))
        known[object_id] = name
        added.append(name)
    alts = entry.get("alts") or {}

    def picture(m: re.Match) -> str:
        object_id = m.group(1)
        name = known.get(object_id, "")
        emb = ((objects.get(object_id) or {}).get("inlineObjectProperties") or {}).get("embeddedObject") or {}
        width = ((emb.get("size") or {}).get("width") or {}).get("magnitude")
        attrs = f' alt="{html.escape(alts.get(name, ""))}"' + (f' width="{round(width / PT_PER_PX)}"' if width else "")
        return f'<img src="{name}"{attrs}>'

    body = re.sub(rf'<img src="{re.escape(DOCS_OBJECT)}([^"]+)"[^>]*>', picture, body)
    if draft.is_file():
        draft.with_suffix(draft.suffix + ".bak").write_text(draft.read_text(encoding="utf-8"), encoding="utf-8")
    draft.write_text(body + "\n", encoding="utf-8")
    entry["pictures"] = known
    return added


__all__ = ["import_page", "load_state", "marker_ranges", "picture_ids", "picture_requests", "pull", "push",
           "save_state"]
