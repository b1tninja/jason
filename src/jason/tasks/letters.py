"""Letters from the Docs templates: build the templates from the Letterhead, and fill a copy for one letter.

``build_template`` copies the Letterhead Doc into the Templates folder, writes the template's body (``BODIES``) in
place of the Letterhead's sample text with its headings, bold line, and bullets, and puts the mailing address in the
footer. ``fill_letter`` copies a template into the folder the letter belongs in, replaces each ``{TOKEN}`` with its
value everywhere in the Doc, links the link tokens, and reports the tokens still in the copy for the person who edits
it. ``hearing_values`` gives a hearing plan's tokens.

Every call here writes to Drive; the CLI asks for ``--yes``. Nothing is shared, sent, exported, or deleted, and the
template and the Letterhead are never changed by filling a letter.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from jason.community.templates import BODIES, CONTINUATION, TOKEN, Block, DocumentTemplate, TemplateKind
from jason.google.docs_markdown import AGENDA, LETTER, REPORT, DocStyle, Para, find_paragraph, inline, parse
from jason.google.docs_markdown import Kind as PKind
from jason.google.docs_markdown import requests as write_requests


def _tab(doc: dict[str, Any]) -> dict[str, Any]:
    return ((doc.get("tabs") or [{}])[0].get("documentTab")) or doc


def _paragraph_runs(content: list[dict[str, Any]]):
    """(start index, text) for every text run in a segment's content, tables included."""
    for block in content:
        if "paragraph" in block:
            for el in block["paragraph"].get("elements", []):
                if "textRun" in el:
                    yield int(el.get("startIndex", 0)), el["textRun"].get("content", "")
        elif "table" in block:
            for row in block["table"].get("tableRows", []):
                for cell in row.get("tableCells", []):
                    yield from _paragraph_runs(cell.get("content", []))


def document_text(doc: dict[str, Any]) -> str:
    """All of the Doc's text: body, headers, and footers."""
    tab = _tab(doc)
    parts = [text for _, text in _paragraph_runs(tab.get("body", {}).get("content", []))]
    for group in ("headers", "footers"):
        for seg in (tab.get(group) or {}).values():
            parts += [text for _, text in _paragraph_runs(seg.get("content", []))]
    return "".join(parts)


def paragraphs(blocks: tuple[tuple[Block, str], ...]) -> list[Para]:
    """A template body as the Docs writer's paragraphs. Inline ``**bold**`` works in any line; the signature block (from
    "Sincerely," on) is kept on one page."""
    out = []
    for kind, line in blocks:
        spans = inline(line)
        if kind is Block.HEADING:
            out.append(Para(PKind.HEADING, spans, level=3))
        elif kind is Block.BULLET:
            out.append(Para(PKind.BULLET, spans))
        elif not line:
            out.append(Para(PKind.BLANK))
        else:
            para = Para(PKind.TEXT, spans)
            if kind is Block.BOLD:
                for s in para.spans:
                    s.bold = True
            elif kind is Block.TITLE:
                para.align, para.size = "CENTER", 15
            elif kind is Block.BOX:
                para.align, para.boxed = "CENTER", True
            elif kind is Block.NOTE:
                para.note = True
            out.append(para)
    signed = next((k for k, p in enumerate(out) if p.text == "Sincerely,"), None)
    if signed is not None:
        for p in out[signed:-1]:
            p.keep_with_next = True
    return out


def body_requests(blocks: tuple[tuple[Block, str], ...], body_end: int, style: DocStyle = LETTER) -> list[dict[str, Any]]:
    """Replace the body (from index 1 to its last newline) with ``blocks``, styled."""
    requests: list[dict[str, Any]] = []
    if body_end - 1 > 1:
        requests.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": body_end - 1}}})
    return requests + write_requests(paragraphs(blocks), 1, style)


def _segment_text(seg: dict[str, Any]) -> str:
    return "".join(text for _, text in _paragraph_runs(seg.get("content", [])))


def format_requests(doc: dict[str, Any], continuation: str = "") -> list[dict[str, Any]]:
    """The letterhead's page furniture: ``continuation`` (small, right-aligned) as the header of the pages after the
    first, and the association's name bold in every footer, as the first page's footer sets it. Run again, it changes
    only what differs."""
    tab = _tab(doc)
    style = tab.get("documentStyle", {})
    out: list[dict[str, Any]] = []
    header_id = style.get("defaultHeaderId")
    header = (tab.get("headers") or {}).get(header_id or "", {})
    if header_id and continuation and _segment_text(header).strip() != continuation:
        end = int(header.get("content", [{}])[-1].get("endIndex", 1))
        if end > 1:
            out.append({"deleteContentRange": {"range": {"segmentId": header_id, "startIndex": 0, "endIndex": end - 1}}})
        n = len(continuation.encode("utf-16-le")) // 2
        out += [{"insertText": {"location": {"segmentId": header_id, "index": 0}, "text": continuation}},
                {"updateParagraphStyle": {"range": {"segmentId": header_id, "startIndex": 0, "endIndex": n + 1},
                                          "paragraphStyle": {"alignment": "END"}, "fields": "alignment"}},
                {"updateTextStyle": {"range": {"segmentId": header_id, "startIndex": 0, "endIndex": n},
                                     "textStyle": {"fontSize": {"magnitude": 9, "unit": "PT"},
                                                   "foregroundColor": {"color": {"rgbColor": {"red": 0.4, "green": 0.4, "blue": 0.4}}}},
                                     "fields": "fontSize,foregroundColor"}}]
    footers = tab.get("footers") or {}
    bold = ""
    for seg in footers.values():
        for block in seg.get("content", []):
            for el in (block.get("paragraph") or {}).get("elements", []):
                run = el.get("textRun", {})
                if run.get("textStyle", {}).get("bold") and run.get("content", "").strip():
                    bold = run["content"].strip()
    if bold:
        for seg_id, seg in footers.items():
            for start, text in _paragraph_runs(seg.get("content", [])):
                at = text.find(bold)
                if at >= 0:
                    out.append({"updateTextStyle": {"range": {"segmentId": seg_id, "startIndex": start + at, "endIndex": start + at + len(bold)},
                                                    "textStyle": {"bold": True}, "fields": "bold"}})
    return out


def _body_end(doc: dict[str, Any]) -> int:
    content = _tab(doc).get("body", {}).get("content", [])
    return int(content[-1].get("endIndex", 1)) if content else 1


def banner_requests(doc: dict[str, Any], word: str = "LETTERHEAD") -> list[dict[str, Any]]:
    """Remove a header line that is only ``word`` (the Letterhead Doc's sample title under the association's name),
    with the line break before it, so the name stays the header's last line."""
    out = []
    for seg_id, seg in (_tab(doc).get("headers") or {}).items():
        for block in seg.get("content", []):
            para = block.get("paragraph")
            if para and "".join(e.get("textRun", {}).get("content", "") for e in para.get("elements", [])).strip() == word:
                start, end = int(block.get("startIndex", 0)), int(block["endIndex"])
                if start > 0:
                    out.append({"deleteContentRange": {"range": {"segmentId": seg_id, "startIndex": start - 1, "endIndex": end - 1}}})
    return out


def build_template(drive: Any, docs: Any, template: DocumentTemplate, *, letterhead_id: str, folder_id: str,
                   footer: str) -> dict[str, Any]:
    """Copy the Letterhead into ``folder_id`` as ``template``, write its body, and put ``footer`` in the footers."""
    doc_id = drive.copy(letterhead_id, template.title, folder_id)
    doc = docs.get(doc_id)
    requests = body_requests(BODIES[template.kind], _body_end(doc)) + banner_requests(doc)
    if "LETTERHEAD" in document_text(doc):
        requests.append({"replaceAllText": {"containsText": {"text": " - LETTERHEAD", "matchCase": True},
                                            "replaceText": f" · {footer}"}})
    docs.batch_update(doc_id, requests)
    furniture = format_requests(docs.get(doc_id), CONTINUATION.get(template.kind, ""))
    if furniture:
        docs.batch_update(doc_id, furniture)
    text = document_text(docs.get(doc_id))
    return {"kind": template.kind.slug, "title": template.title, "id": doc_id, "tokens": sorted(set(TOKEN.findall(text))),
            "footerFixed": "LETTERHEAD" not in text}


def rewrite_template(docs: Any, template: DocumentTemplate) -> dict[str, Any]:
    """Replace a built template's body with the current ``BODIES`` text, in place, and set its page furniture
    (``format_requests``): the Doc keeps its id, logo header, and footer text. A person's own edits to the template's body are replaced; the Doc's version history keeps them."""
    if not template.drive_id:
        raise ValueError(f"the {template.kind.value} template has no Drive id")
    doc = docs.get(template.drive_id)
    docs.batch_update(template.drive_id, body_requests(BODIES[template.kind], _body_end(doc)))
    furniture = format_requests(docs.get(template.drive_id), CONTINUATION.get(template.kind, ""))
    if furniture:
        docs.batch_update(template.drive_id, furniture)
    text = document_text(docs.get(template.drive_id))
    return {"kind": template.kind.slug, "id": template.drive_id, "tokens": sorted(set(TOKEN.findall(text)))}


def _link_requests(doc: dict[str, Any], urls: list[str]) -> list[dict[str, Any]]:
    out = []
    for start, text in _paragraph_runs(_tab(doc).get("body", {}).get("content", [])):
        for url in urls:
            at = text.find(url)
            while at >= 0:
                # A run's index counts UTF-16 units; the text before the URL is almost always plain ASCII.
                begin = start + len(text[:at].encode("utf-16-le")) // 2
                out.append({"updateTextStyle": {"range": {"startIndex": begin, "endIndex": begin + len(url)},
                                                "textStyle": {"link": {"url": url}}, "fields": "link"}})
                at = text.find(url, at + len(url))
    return out


def fill_letter(drive: Any, docs: Any, template: DocumentTemplate, values: dict[str, str], *, name: str,
                folder_id: str, doc_id: str = "", defaults: dict[str, str] | None = None) -> dict[str, Any]:
    """Copy ``template`` into ``folder_id`` as ``name`` and replace its tokens; report what is left to fill. With
    ``doc_id`` (a Doc filled from this template before), that Doc's body is written again from the template's text and
    filled in place, so a re-run updates the draft instead of making another. ``defaults`` are the profile's values
    (`template_values.profile_values`): they fill what ``values`` leaves, and one the template does not use is not
    reported as ignored."""
    if not template.drive_id:
        raise ValueError(f"the {template.kind.value} template has no Drive id; build it with `jason templates --build --yes`")
    own = {k: str(v) for k, v in values.items() if v not in (None, "")}
    unknown = sorted(set(own) - set(template.tokens))
    given = {k: str(v) for k, v in (defaults or {}).items() if v not in (None, "")} | own
    if doc_id:
        docs.batch_update(doc_id, body_requests(BODIES[template.kind], _body_end(docs.get(doc_id))))
        furniture = format_requests(docs.get(doc_id), CONTINUATION.get(template.kind, ""))
        if furniture:
            docs.batch_update(doc_id, furniture)
    else:
        doc_id = drive.copy(template.drive_id, name, folder_id)
    requests = [{"replaceAllText": {"containsText": {"text": "{" + k + "}", "matchCase": True}, "replaceText": v}}
                for k, v in given.items() if k in template.tokens]
    requests += [{"replaceAllText": {"containsText": {"text": "{" + k + "}", "matchCase": True}, "replaceText": ""}}
                 for k in template.optional if k not in given]
    if requests:
        docs.batch_update(doc_id, requests)
    doc = docs.get(doc_id)
    links = _link_requests(doc, [given[k] for k in template.link_tokens if given.get(k, "").startswith("http")])
    if links:
        docs.batch_update(doc_id, links)
    left = sorted(set(TOKEN.findall(document_text(doc))))
    return {"id": doc_id, "url": f"https://docs.google.com/document/d/{doc_id}/edit", "name": name, "folder": folder_id,
            "filled": sorted(k for k in given if k in template.tokens), "unfilled": left, "ignored": unknown}


def _send(docs: Any, doc_id: str, requests: list[dict[str, Any]], *, chunk: int = 400) -> None:
    """Send requests in order, a batch at a time: each request's indices assume the ones before it applied."""
    for k in range(0, len(requests), chunk):
        docs.batch_update(doc_id, requests[k:k + chunk])


def fill_with_markdown(drive: Any, docs: Any, template: DocumentTemplate, values: dict[str, str], markdown: list[str], *,
                       name: str, folder_id: str, placeholder: str = "{AGENDA_ITEMS}", style: DocStyle = AGENDA,
                       doc_id: str = "", defaults: dict[str, str] | None = None) -> dict[str, Any]:
    """``fill_letter``, then the paragraph that is only ``placeholder`` replaced by ``markdown``, styled (an agenda's
    business). With ``doc_id``, that Doc is filled again in place."""
    result = fill_letter(drive, docs, template, values, name=name, folder_id=folder_id, doc_id=doc_id, defaults=defaults)
    doc = docs.get(result["id"])
    found = find_paragraph(doc, placeholder)
    if found:
        start, end = found
        _send(docs, result["id"], [{"deleteContentRange": {"range": {"startIndex": start, "endIndex": end}}}]
              + write_requests(parse(markdown), start, style))
        doc = docs.get(result["id"])
    furniture = format_requests(doc, "")
    if furniture:
        docs.batch_update(result["id"], furniture)
    result["unfilled"] = sorted(set(TOKEN.findall(document_text(docs.get(result["id"])))))
    return result


def markdown_doc(drive: Any, docs: Any, markdown: list[str], *, name: str, folder_id: str, letterhead_id: str, footer: str,
                 continuation: str = "", style: DocStyle = REPORT, doc_id: str = "",
                 picture_link: Any = None) -> dict[str, Any]:
    """A Doc on the letterhead holding ``markdown``: ``doc_id`` rewritten in place when it is given and still readable,
    else a new copy of the Letterhead in ``folder_id``. Nothing is shared. A picture line (``![alt](file)``) is put in
    from ``picture_link(file)``, a link the Docs API can read; without it the marker line stays for a person to see."""
    doc = None
    if doc_id:
        try:
            doc = docs.get(doc_id)
        except Exception:
            doc = None
    requests: list[dict[str, Any]] = []
    created = doc is None
    if created:
        doc_id = drive.copy(letterhead_id, name, folder_id)
        doc = docs.get(doc_id)
        requests += banner_requests(doc)
        if "LETTERHEAD" in document_text(doc):
            requests.append({"replaceAllText": {"containsText": {"text": " - LETTERHEAD", "matchCase": True},
                                                "replaceText": f" · {footer}"}})
    end = _body_end(doc)
    if end - 1 > 1:
        requests.append({"deleteContentRange": {"range": {"startIndex": 1, "endIndex": end - 1}}})
    paras = parse(markdown)
    requests += write_requests(paras, 1, style)
    _send(docs, doc_id, requests)
    furniture = format_requests(docs.get(doc_id), continuation)
    if furniture:
        docs.batch_update(doc_id, furniture)
    pictures: list[str] = []
    if picture_link is not None:
        from jason.google.docs_markdown import picture_markers, picture_requests

        markers = picture_markers(docs.get(doc_id))
        if markers:
            widths = {p.picture: p.width for p in paras if p.picture}
            docs.batch_update(doc_id, picture_requests(markers, {f: picture_link(f) for f, _, _ in markers}, widths))
            pictures = [f for f, _, _ in sorted(markers, key=lambda m: m[1])]
    return {"id": doc_id, "url": f"https://docs.google.com/document/d/{doc_id}/edit", "name": name, "created": created,
            "pictures": pictures}


def matter_folder(drive: Any, parent_id: str, name: str) -> str:
    """The matter's folder in ``parent_id``, created when it is not there."""
    return drive.child_folder(parent_id, name) or drive.create_folder(name, parent_id)


def long_date(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


def hearing_values(plan: Any, *, city_state_zip: str, owner: str = "", delivery: str = "", sections: str = "",
                   contact: str = "", cure: str = "", today: date | None = None) -> dict[str, str]:
    """A hearing plan's tokens for the notice of hearing. The owner's name and the governing sections come from a
    person; jason does not look up or quote them."""
    z = plan.zoom or {}
    hour = plan.start.strftime("%I:%M %p").lstrip("0")
    return {
        "DATE": long_date(today or date.today()), "OWNER_NAME": owner, "ADDRESS": plan.address, "CITY_STATE_ZIP": city_state_zip,
        "DELIVERY_METHOD": delivery, "HEARING_DATE": f"{plan.start:%A}, {long_date(plan.start.date())}", "HEARING_TIME": hour,
        "ZOOM_LINK": z.get("joinUrl") or "", "ZOOM_MEETING_ID": str(z.get("id") or ""), "ZOOM_PASSCODE": z.get("passcode") or "",
        "ZOOM_DIAL_IN": "; ".join(z.get("dialIn") or []), "VIOLATION": plan.violation, "GOVERNING_SECTIONS": sections,
        "CONTACT": contact, "CURE": cure,
    }


def parse_assignments(pairs: list[str]) -> dict[str, str]:
    """``KEY=value`` pairs from the command line; keys upper-cased."""
    out = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            raise ValueError(f"expected KEY=value, got {pair!r}")
        out[key.strip().upper().strip("{}")] = value.replace("\\n", "\n")
    return out


__all__ = ["body_requests", "build_template", "document_text", "fill_letter", "hearing_values", "long_date", "matter_folder",
           "parse_assignments"]
