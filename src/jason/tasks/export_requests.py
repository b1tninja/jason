"""Write every catalogued PayHOA request to one markdown file.

Attachment images are embedded. Other saved files are linked. Paths are
relative to the markdown file. Comments and notes come from the files saved
beside the attachments when those JSON files exist, and from the catalog
otherwise.
"""

from __future__ import annotations

import base64
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageFile, ImageOps

ImageFile.LOAD_TRUNCATED_IMAGES = True

from jason.catalog import PayhoaCatalog, unit_label

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SKIP_NAMES = frozenset({"comments.json", "notes.json"})
_IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp"})
_DATA_URI = re.compile(
    r"data:image/(?:png|jpe?g|gif|webp);base64,([A-Za-z0-9+/=\r\n]+)",
    re.IGNORECASE,
)
EMAIL_MAX_EDGE = 800
EMAIL_JPEG_QUALITY = 80


@dataclass
class RequestExport:
    path: Path
    requests: int
    attachments: int

    def summary(self) -> str:
        return (
            f"requests={self.requests} attachments={self.attachments} path={self.path}"
        )


def export_requests(
    catalog: PayhoaCatalog,
    org_id: int,
    dest: str | Path,
    *,
    files_dir: str | Path,
    statuses: tuple[str, ...] | None = None,
    form_name: str | None = None,
) -> RequestExport:
    """Render catalogued requests, newest first.

    ``files_dir`` is the sync-request-files root. ``statuses`` keeps only those
    status values (matched without case). ``form_name`` keeps one form.
    """
    path = Path(dest)
    root = Path(files_dir)
    rows = catalog.search_requests(
        org_id,
        statuses=statuses,
        form_name=form_name,
        include_raw=True,
        limit=None,
    )
    scope = ", ".join(statuses) if statuses else "all statuses"
    if form_name:
        scope = f"{scope}; {form_name}"
    blocks: list[str] = [
        "# PayHOA requests",
        "",
        f"{len(rows)} requests ({scope}), newest first.",
        "",
    ]
    image_root = path.parent / f"{path.stem}-images"
    attachments = 0
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset=\"utf-8\"></head>",
        "<body style=\"font-family: sans-serif; max-width: 680px;\">",
        f"<h1>PayHOA requests</h1><p>{len(rows)} requests ({html.escape(scope)}), newest first.</p>",
    ]
    for index, row in enumerate(rows):
        if index:
            blocks.append("---")
            blocks.append("")
        raw = _parse_raw(row.get("raw_json"))
        request_id = int(row["id"])
        folder = root / "requests" / str(request_id)
        files = _attachment_files(folder)
        attachments += len(files)
        shown = [_shown_attachment(file, path, image_root / str(request_id)) for file in files]
        inline = _InlineImages(image_root / str(request_id), path)
        blocks.append(_request_markdown(row, raw, folder, shown, inline))
        blocks.append("")
        html_parts.append("<hr>")
        html_parts.append(_request_html(row, raw, folder, shown, path, inline))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")
    html_parts.append("</body></html>")
    path.with_suffix(".html").write_text("\n".join(html_parts), encoding="utf-8")
    return RequestExport(path=path, requests=len(rows), attachments=attachments)


def email_image(src: Path, dest: Path, *, max_edge: int = EMAIL_MAX_EDGE) -> Path:
    """Write a JPEG small enough to paste into an email. The original stays put."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(dest, "JPEG", quality=EMAIL_JPEG_QUALITY, optimize=True)
    return dest


def _mostly_blank(path: Path) -> bool:
    """A truncated PNG often opens as a black frame with a thin strip of the photo."""
    with Image.open(path) as image:
        small = image.convert("RGB").resize((32, 24))
        pixels = list(getattr(small, "get_flattened_data", small.getdata)())
    lit = sum(1 for red, green, blue in pixels if red + green + blue > 40)
    return lit < len(pixels) * 0.05


def _shown_attachment(path: Path, dest: Path, image_dir: Path) -> tuple[Path, str]:
    """Return the file to link and its markdown target. Photos are email-sized JPEGs."""
    if path.suffix.lower() in _IMAGE_SUFFIXES and path.suffix.lower() != ".gif":
        copy = email_image(path, image_dir / f"{path.stem}.jpg")
        rel = copy.resolve().relative_to(dest.parent.resolve()).as_posix()
        return copy, rel
    rel = path.resolve().relative_to(dest.parent.resolve()).as_posix()
    return path, rel


class _InlineImages:
    """Pull data-URI pictures out of request text and save email-sized JPEGs."""

    def __init__(self, image_dir: Path, dest: Path) -> None:
        self.image_dir = image_dir
        self.dest = dest
        self.shown: list[tuple[Path, str]] = []
        self._n = 0
        self._cache: dict[str, str] = {}

    def text(self, value: str) -> str:
        cached = self._cache.get(value)
        if cached is not None:
            return cached
        cleaned = _DATA_URI.sub(self._save, value)
        cleaned = _plain(cleaned)
        self._cache[value] = cleaned
        return cleaned

    def _save(self, match: re.Match[str]) -> str:
        payload = re.sub(r"\s+", "", match.group(1))
        try:
            raw = base64.b64decode(payload, validate=False)
        except ValueError:
            return ""
        self._n += 1
        src = self.image_dir / f"inline-{self._n}.bin"
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(raw)
        dest = self.image_dir / f"inline-{self._n}.jpg"
        try:
            copy = email_image(src, dest)
        except OSError:
            src.unlink(missing_ok=True)
            return " [photo in this message was cut off] "
        src.unlink(missing_ok=True)
        if _mostly_blank(copy):
            copy.unlink(missing_ok=True)
            return " [photo in this message was cut off] "
        rel = copy.resolve().relative_to(self.dest.parent.resolve()).as_posix()
        self.shown.append((copy, rel))
        return ""


def _request_markdown(
    row: dict[str, Any],
    raw: dict[str, Any],
    folder: Path,
    files: list[tuple[Path, str]],
    images: _InlineImages,
) -> str:
    title = _answer_by_label(raw, "Title") or str(row.get("title") or "").strip() or "Request"
    created = str(row.get("created_at") or "")
    if "T" in created:
        created = created.split("T", 1)[0]
    meta = " · ".join(
        part
        for part in (
            f"**{row['id']}**",
            _inline(str(row.get("form_name") or "")),
            _inline(str(row.get("status") or "")),
            _inline(_unit(raw)),
            _inline(created),
        )
        if part
    )
    lines = [
        f"## {_inline(title)}",
        "",
        meta,
        "",
    ]
    tags = _tags(raw)
    if tags:
        lines.append(f"Tags: {', '.join(_inline(tag) for tag in tags)}")
        lines.append("")
    answers = [
        (label, text)
        for label, text in _answers(raw, images)
        if label.strip().lower() != "title"
    ]
    if answers:
        lines.append("### Answers")
        lines.append("")
        for label, text in answers:
            lines.append(f"**{_inline(label)}**")
            lines.append("")
            lines.append(text)
            lines.append("")
    comments = _load_json_list(folder / "comments.json")
    if comments is None:
        comments = _as_list(raw.get("comments"))
    if comments:
        lines.extend(_thread("Comments", comments, "message", images))
    notes = _load_json_list(folder / "notes.json")
    if notes:
        lines.extend(_thread("Notes", notes, "note", images))
    files = [*files, *images.shown]
    if files:
        lines.append("### Attachments")
        lines.append("")
        for file, rel in files:
            lines.append(_attachment_markdown(file, rel))
            lines.append("")
    return "\n".join(lines).rstrip()


def _request_html(
    row: dict[str, Any],
    raw: dict[str, Any],
    folder: Path,
    files: list[tuple[Path, str]],
    dest: Path,
    images: _InlineImages,
) -> str:
    title = _answer_by_label(raw, "Title") or str(row.get("title") or "").strip() or "Request"
    created = str(row.get("created_at") or "")
    if "T" in created:
        created = created.split("T", 1)[0]
    meta = " · ".join(
        part
        for part in (
            str(row["id"]),
            str(row.get("form_name") or ""),
            str(row.get("status") or ""),
            _unit(raw),
            created,
        )
        if part
    )
    parts = [f"<h2>{html.escape(_inline(title))}</h2>", f"<p>{html.escape(meta)}</p>"]
    tags = _tags(raw)
    if tags:
        parts.append(f"<p>Tags: {html.escape(', '.join(tags))}</p>")
    for label, text in _answers(raw, images):
        if label.strip().lower() == "title":
            continue
        parts.append(f"<p><strong>{html.escape(label)}</strong><br>{html.escape(text)}</p>")
    comments = _load_json_list(folder / "comments.json")
    if comments is None:
        comments = _as_list(raw.get("comments"))
    for item in comments or []:
        if isinstance(item, dict):
            text = images.text(str(item.get("message") or ""))
            if text:
                parts.append(f"<p>{html.escape(text)}</p>")
    for file, rel in [*files, *images.shown]:
        if file.suffix.lower() in _IMAGE_SUFFIXES or file.suffix.lower() == ".jpg":
            parts.append(
                f"<p><img src=\"{html.escape(rel)}\" alt=\"{html.escape(file.name)}\" "
                f"width=\"640\" style=\"max-width:100%;height:auto\"></p>"
            )
        else:
            parts.append(
                f"<p><a href=\"{html.escape(rel)}\">{html.escape(file.name)}</a></p>"
            )
    return "\n".join(parts)


def _tags(raw: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for item in _as_list(raw.get("tags")):
        if isinstance(item, dict):
            label = str(item.get("tag") or "").strip()
        else:
            label = str(item).strip()
        if label and label not in found:
            found.append(label)
    return found


def _attachment_markdown(path: Path, rel: str) -> str:
    name = _inline(path.name)
    if path.suffix.lower() in _IMAGE_SUFFIXES or path.suffix.lower() == ".jpg":
        return f"![{name}]({rel})"
    return f"[{name}]({rel})"


def _attachment_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.name not in _SKIP_NAMES
    )


def _answers(raw: dict[str, Any], images: _InlineImages) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for item in _as_list(raw.get("answers")):
        if not isinstance(item, dict):
            continue
        question = item.get("question")
        label = ""
        if isinstance(question, dict):
            label = str(question.get("label") or "")
        text = images.text(str(item.get("answer") or ""))
        if not text:
            continue
        found.append((label or "Answer", text))
    return found


def _thread(heading: str, rows: list[Any], field: str, images: _InlineImages) -> list[str]:
    lines = [f"### {heading}", ""]
    wrote = False
    for item in rows:
        if not isinstance(item, dict):
            continue
        text = images.text(str(item.get(field) or item.get("message") or ""))
        if not text:
            continue
        wrote = True
        who = _who(item)
        when = str(item.get("createdAt") or "").strip()
        label = " ".join(part for part in (who, when) if part)
        if label:
            lines.append(f"**{_inline(label)}**")
            lines.append("")
        lines.append(text)
        lines.append("")
    if not wrote:
        return []
    return lines


def _who(item: dict[str, Any]) -> str:
    membership = item.get("membership")
    if isinstance(membership, dict):
        profile = membership.get("profile")
        if isinstance(profile, dict):
            given = str(profile.get("givenNames") or "").strip()
            family = str(profile.get("familyName") or "").strip()
            name = f"{given} {family}".strip()
            if name:
                return name
        name = str(membership.get("name") or "").strip()
        if name:
            return name
    return str(item.get("author") or "").strip()


def _unit(raw: dict[str, Any]) -> str:
    unit = raw.get("unit")
    if isinstance(unit, dict):
        return unit_label(unit)
    return ""


def _answer_by_label(raw: dict[str, Any], label: str) -> str:
    wanted = label.strip().lower()
    for item in _as_list(raw.get("answers")):
        if not isinstance(item, dict):
            continue
        question = item.get("question")
        qlabel = ""
        if isinstance(question, dict):
            qlabel = str(question.get("label") or "")
        if qlabel.strip().lower() == wanted:
            return _plain(str(item.get("answer") or ""))
    return ""


def _load_json_list(path: Path) -> list[Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _parse_raw(raw_json: str | None) -> dict[str, Any]:
    if not raw_json:
        return {}
    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _plain(value: str) -> str:
    text = _HTML_TAG_RE.sub(" ", value)
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def _inline(value: str) -> str:
    return " ".join(value.split())
