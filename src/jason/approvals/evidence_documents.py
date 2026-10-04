"""The documents behind a piece of evidence, and viewing one unmasked: what ``resolve`` lists, and what a person opens.

``resolve`` answers what jason holds of a record, masked. Each answer also lists the documents behind it
(``documents``): the files on disk a person may open whole.

- **A PayHOA request.** The submission as last read in full (``payhoa-files/requests/N/submission.json``), and each
  attachment ``jason sync-request-files`` saved in the request's folder. Never the folder's comments, notes, the
  submission's own file, or a file half written (``.tmp``).
- **A citation.** The whole section as stored, and the governing document's own file, when ``jason cite`` names one
  (a library path, or a Drive id the Drive holdings place in the library or under the data folder) and the library
  does not hold it as confidential: the file itself, and the library's extracted text of it.
- **A Drive file** (``drive:<id>``). jason's copy of it (``data/drive/copies``): its PDF (``pdf``), a Doc's text
  (``text``), a Sheet's first sheet (``csv``), a stored image (``image``), each when on disk.
- **A file on disk** (``file:<path>``, a path under the data folder in a place ``jason.web.access``'s ``PATH_RULES``
  names, of a kind the viewer shows): the file itself, and a PDF's text extract beside it (``<name>.pdf.md``), at the
  file's level (``level_of_path``). A recorded copy: nothing reads it again.
- **A board item or a command.** None.

**Confidential documents** (a library file held as confidential, or any copy of one by its digest; a Drive file the
holdings mark confidential; a restricted book's words) are left out, unless the caller asks with ``private`` (jason-web,
while the person's private view is open). Then each is listed with ``level: "P3"`` and ``CONFIDENTIAL_NOTE``.

A document's ``kind`` comes from its file's extension and nothing else (``EXTENSIONS``): ``pdf``, ``image``,
``text``, or ``file``. HTML, SVG, and XML are ``file``: they are never shown inline, only saved.

**Viewing one** (``view``) is the ask principle 6 of docs/console/README.md names: contact details are masked by the
server until someone asks to see them, and that is logged. It needs a named person, appends one line to
``evidence/views.jsonl`` (``at``, ``by``, ``address``, ``document``, ``kind``; never the contents), and answers the
document unmasked: a submission's questions and answers in the form's order, a text's words, or the file on disk for
jason-web to serve through a short-lived link. It reads disk only, never PayHOA, Google, or Keeper. jason-mcp has no
view: it stays read-only and masked.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

VIEW_LOG = Path("evidence") / "views.jsonl"
UNMASKED = "Unmasked: shown because {by} asked; this view is logged."
CONFIDENTIAL_NOTE = "Confidential: shown in the private view"
CONFIDENTIAL = "P3"                            # a confidential document's data level (jason.web.access.Level)
SUBMISSION_CAVEAT = ("The latest full read of this request jason keeps, not a live read; refreshing it reads PayHOA "
                     "again.")
ATTACHMENT_CAVEAT = ("A file jason sync-request-files saved from the request, as PayHOA held it then; not a live read.")
LIBRARY_CAVEAT = ("The association's library copy of the document (jason library); the recorded or adopted original "
                  "governs.")
EXTRACT_CAVEAT = ("The library's text of the file, read from its text layer or by OCR when scanned; the file itself "
                  "governs where they differ.")
MAX_TEXT = 8 * 1024 * 1024                     # the most bytes a text document is answered inline

# The whitelist: a document's kind and the type it is served as, by its extension. Anything else is a "file".
EXTENSIONS: dict[str, tuple[str, str]] = {
    ".pdf": ("pdf", "application/pdf"),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".gif": ("image", "image/gif"),
    ".webp": ("image", "image/webp"),
    ".txt": ("text", "text/plain; charset=utf-8"),
    ".md": ("text", "text/plain; charset=utf-8"),
    ".csv": ("text", "text/plain; charset=utf-8"),
}
OCTET = "application/octet-stream"
NOT_FILES = frozenset({"comments.json", "notes.json", "submission.json"})


def kind_of(name: str) -> str:
    """``pdf``, ``image``, ``text``, or ``file``, by the extension alone."""
    return EXTENSIONS.get(Path(name).suffix.lower(), ("file", OCTET))[0]


def content_type(name: str) -> str:
    return EXTENSIONS.get(Path(name).suffix.lower(), ("file", OCTET))[1]


@dataclass(frozen=True)
class Document:
    """One document behind an evidence address: what the list shows, and, kept on the server, the file on disk
    (``path``) and the folder it must stay inside (``root``); both None for a submission or a section. ``level`` is
    ``"P3"`` for a confidential one (listed only for the private view), else empty."""
    id: str
    name: str
    kind: str
    size: int = 0
    read_at: str = ""
    note: str = ""
    caveat: str = ""
    path: Path | None = None
    root: Path | None = None
    level: str = ""

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "name": self.name, "kind": self.kind, "size": self.size,
                               "readAt": self.read_at, "note": self.note}
        if self.level:
            out["level"] = self.level
        return out


def confidential(docs: list[Document]) -> list[Document]:
    """``docs`` marked confidential: ``level`` P3 and ``CONFIDENTIAL_NOTE``."""
    return [replace(d, level=CONFIDENTIAL, note=CONFIDENTIAL_NOTE) for d in docs]


def _mtime(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return ""


def _size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def inside(path: Path, root: Path) -> bool:
    """Whether ``path``, resolved (links followed), is a file inside ``root``, resolved."""
    try:
        return path.resolve().is_relative_to(root.resolve()) and path.resolve().is_file()
    except OSError:
        return False


def file_id(name: str) -> str:
    """A file's id: its name, unless the name holds what the server masks (an email address, a phone number); then an
    opaque id, so the list never carries it."""
    from jason.approvals.evidence import mask_text

    return name if not mask_text(name)[1] else "file-" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:16]


# --- a PayHOA request -----------------------------------------------------------------------------------------------------

def request_documents(root: Path, sid: int) -> list[Document]:
    """The request's submission as last read, then each attachment saved in its folder, by name."""
    from jason.approvals.evidence import _files_root
    from jason.tasks import submission_cache

    files = _files_root(root)
    folder = files / "requests" / str(int(sid))
    out: list[Document] = []
    try:
        cached = submission_cache.read(files, sid)
    except ValueError:
        cached = None                          # a file that cannot be read is not a document to open
    if cached is not None:
        sub = submission_cache.body(cached.get("submission"))
        form = sub.get("form") if isinstance(sub.get("form"), dict) else {}
        name = str(cached.get("formName") or form.get("name") or "The request")
        via = str(cached.get("via") or "")
        out.append(Document("submission", f"{name} as submitted", "submission", 0, str(cached.get("readAt") or ""),
                            f"Read by {via}." if via else "", SUBMISSION_CAVEAT))
    if folder.is_dir():
        for p in sorted(folder.iterdir(), key=lambda q: q.name.casefold()):
            if (p.name in NOT_FILES or p.name.endswith(".tmp") or p.is_symlink() or not p.is_file()
                    or not inside(p, folder)):
                continue
            out.append(Document(file_id(p.name), p.name, kind_of(p.name), _size(p), _mtime(p), "", ATTACHMENT_CAVEAT,
                                p, folder))
    return out


# --- a citation ----------------------------------------------------------------------------------------------------------

def _library(root: Path, library_path: str, label: str = "", *, private: bool = False) -> list[Document]:
    """A library file by its library path: the file itself and its extracted text, each when on disk under the data
    folder. A file the library holds as confidential (or any copy of one, by its digest, as ``jason.web.access``
    judges it) only with ``private``, marked confidential."""
    db = root / "library" / "library.db"
    if not library_path or not db.is_file():
        return []
    try:
        conn = sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT id, confidential, sha256 FROM documents WHERE path = ? LIMIT 1",
                               (library_path,)).fetchone()
            secret = bool(row and row[1])
            if row is not None and not secret and row[2]:
                secret = bool(conn.execute("SELECT MAX(confidential) FROM documents WHERE sha256 = ?",
                                           (row[2],)).fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        return []
    if row is None or (secret and not private):
        return []
    doc_id = str(row[0])
    name = Path(library_path).name
    out: list[Document] = []
    files_root = root / "library" / "files"
    original = files_root / library_path
    where = files_root
    if not inside(original, files_root):
        original, where = None, root
        sidecar = root / "library" / "text" / f"{doc_id}.json"
        try:
            recorded = json.loads(sidecar.read_text(encoding="utf-8")).get("file") if sidecar.is_file() else ""
        except (OSError, ValueError):
            recorded = ""
        if recorded and inside(Path(recorded), root):
            original = Path(recorded)
    note = f"{label}: the library's copy" if label else "the library's copy"
    if original is not None:
        out.append(Document(f"library:{doc_id}", name, kind_of(original.name), _size(original), _mtime(original),
                            note, LIBRARY_CAVEAT, original, where))
    text_root = root / "library" / "text"
    text = text_root / f"{doc_id}.txt"
    if inside(text, text_root):
        out.append(Document(f"library-text:{doc_id}", f"{name}, its extracted text", "text", _size(text),
                            _mtime(text), "the library's text of the file", EXTRACT_CAVEAT, text, text_root))
    return confidential(out) if secret else out


_DRIVE_FILE = re.compile(r"/(?:file|document|spreadsheets|presentation)/d/([\w-]+)")


def _drive(root: Path, drive_id: str, label: str = "", *, private: bool = False) -> list[Document]:
    """A Drive file placed on disk by the Drive holdings (``jason drive-catalog``'s ``drive/holdings.json``): its
    library copy, else its first copy under the data folder. One the holdings mark confidential only with
    ``private``, marked confidential."""
    report = root / "drive" / "holdings.json"
    if not drive_id or not report.is_file():
        return []
    try:
        rows = json.loads(report.read_text(encoding="utf-8")).get("rows") or []
    except (OSError, ValueError):
        return []
    row = next((r for r in rows if isinstance(r, dict) and r.get("id") == drive_id), None)
    secret = bool(row and row.get("confidential"))
    if row is None or (secret and not private):
        return []
    mark = confidential if secret else list
    for place in row.get("elsewhere") or ():
        if place.get("channel") == "PayHOA library":
            found = _library(root, str(place.get("where") or ""), label, private=private)
            if found:
                return mark(found)
    for place in row.get("elsewhere") or ():
        if place.get("channel") == "PayHOA library":
            continue
        path = root / str(place.get("where") or "")
        if place.get("where") and inside(path, root):
            return mark([Document(f"drive:{drive_id}", str(row.get("name") or path.name), kind_of(path.name),
                                  _size(path), _mtime(path), f"{label}: a copy on disk of the Drive file" if label else
                                  "a copy on disk of the Drive file", LIBRARY_CAVEAT, path, root)])
    return []


DRIVE_TEXT_NOTE = {"text/markdown": "the Doc's text, exported as Markdown",
                   "text/plain": "the Doc's text, exported as plain text (Google would not export Markdown)"}


def drive_documents(root: Path, drive_id: str, *, private: bool = False) -> list[Document]:
    """jason's copy of a Drive file (``jason.tasks.drive_copies``), each document only when on disk: ``pdf`` (a Doc,
    Sheet, or Slides file as PDF, or a stored PDF), ``text`` (a Doc's Markdown or plain text), ``csv`` (a Sheet's first
    sheet), ``image`` (a stored image). A stored file the holdings already placed on disk is that file. One the
    holdings mark confidential only with ``private``, marked confidential."""
    from jason.tasks import drive_copies

    record = drive_copies.read_record(root, drive_id)
    if record is None:
        return []
    secret = drive_copies.confidential(root, drive_id)
    if secret and not private:
        return []
    name = str(record.get("name") or drive_id)
    read_at = str(record.get("readAt") or "")
    via = str(record.get("via") or "")
    note = f"Exported from Drive by {via}." if via else "Exported from Drive."
    folder = drive_copies.copies_dir(root)
    files = drive_copies.kept(root, drive_id)
    out: list[Document] = []
    reused = str(record.get("reused") or "")
    if reused and inside(Path(root) / reused, Path(root)):
        path = Path(root) / reused
        kind = kind_of(path.name)
        if kind in ("pdf", "image"):
            out.append(Document(kind, name, kind, _size(path), read_at, "The same file, already on disk.",
                                drive_copies.CAVEAT, path, Path(root)))
    pdf_name = name if name.lower().endswith(".pdf") else f"{name}.pdf"
    for ext, doc_id, shown, kind, said in (
            ("pdf", "pdf", pdf_name, "pdf", note),
            ("md", "text", f"{name}, its text", "text",
             DRIVE_TEXT_NOTE.get(str(record.get("textMime") or ""), "the Doc's text")),
            ("csv", "csv", f"{name}, the first sheet (CSV)", "text", "the Sheet's first sheet, as CSV"),
            *((f"image.{e}", "image", name, "image", note) for e in ("png", "jpg", "gif", "webp"))):
        path = files.get(ext)
        if path is None or not inside(path, folder) or any(d.id == doc_id for d in out):
            continue
        out.append(Document(doc_id, shown, kind, _size(path), read_at, said, drive_copies.CAVEAT, path, folder))
    return confidential(out) if secret else out


RECORDED_CAVEAT = ("jason's recorded or adopted copy on disk; a recorded instrument does not change, so it is not read "
                   "again. The recorded original governs.")
FILE_EXTRACT_NOTE = "the text read from the file (its text layer, or OCR when scanned)"
FILE_KINDS = frozenset({"pdf", "image", "text"})


def file_place(root: Path, rel: str) -> tuple[str, Path] | None:
    """A file named by its path under the data folder, as the ``file:<path>`` address takes it: the path as posix and
    the file, when it is a file inside the folder, in a place ``jason.web.access``'s ``PATH_RULES`` names, of a kind the
    viewer shows (pdf, image, text); None otherwise (outside, missing, unplaced, or another kind)."""
    from jason.web.access import placed

    text = str(rel or "").strip().replace("\\", "/").lstrip("/")
    if not text or "\x00" in text:
        return None
    base = Path(root).resolve()
    try:
        path = (base / text).resolve()
        posix = path.relative_to(base).as_posix()
    except (OSError, ValueError):
        return None
    if not path.is_file() or kind_of(path.name) not in FILE_KINDS or not placed(posix, base):
        return None
    return posix, path


def file_level(root: Path, rel: str) -> str:
    """The data level of a file under the data folder (``jason.web.access.level_of_path``): ``"P0"`` to ``"P4"``."""
    from jason.web.access import level_of_path

    return level_of_path(rel, Path(root)).value


def file_documents(root: Path, rel: str, *, private: bool = False) -> list[Document]:
    """A file under the data folder (``file:<path>``): the file itself (``pdf``, ``image``, or ``text`` by its
    extension), then a PDF's text extract beside it (``<name>.pdf.md``) as ``text``, each only when on disk. A file
    at P3 (confidential by ``jason.web.access``) only with ``private``, marked confidential; P4 never."""
    found = file_place(root, rel)
    if found is None:
        return []
    posix, path = found
    level = file_level(root, posix)
    if level == "P4" or (level == "P3" and not private):
        return []
    folder = path.parent
    kind = kind_of(path.name)
    out = [Document(kind, path.name, kind, _size(path), _mtime(path), "Recorded copy", RECORDED_CAVEAT, path, folder)]
    extract = path.with_name(path.name + ".md")
    if kind == "pdf" and inside(extract, folder):
        out.append(Document("text", f"{path.name}, its text", "text", _size(extract), _mtime(extract),
                            FILE_EXTRACT_NOTE, EXTRACT_CAVEAT, extract, folder))
    return confidential(out) if level == "P3" else out


def citation_documents(root: Path, got: dict[str, Any], *, statute: bool, read_at: str = "",
                       private: bool = False) -> list[Document]:
    """A resolved citation's documents: the whole section when its words are stored, then the governing document's
    file and its extracted text, from the links ``jason cite`` gives (a library path, a Drive file). ``private`` lists
    the confidential ones too, marked; a restricted book's (``jason cite --private``) are all confidential."""
    from jason.approvals.evidence import STATUTE_CAVEAT

    if not got.get("found"):
        return []
    citation = str(got.get("citation") or "")
    out: list[Document] = []
    text = str(got.get("text") or "")
    if text:
        caveat = str(got.get("caveat") or (STATUTE_CAVEAT if statute else ""))
        out.append(Document("section", f"{citation}, the whole section", "text", len(text.encode("utf-8")),
                            read_at, str(got.get("inForce") or ""), caveat))
    for link in got.get("links") or ():
        if not isinstance(link, dict):
            continue
        label = str(link.get("what") or "")
        if link.get("library"):
            out += _library(root, str(link["library"]), label, private=private)
        elif link.get("url"):
            found = _DRIVE_FILE.search(urlsplit(str(link["url"])).path)
            if found:
                out += _drive(root, found.group(1), label, private=private)
    version = got.get("version")
    if isinstance(version, dict) and version.get("restricted"):
        out = confidential(out)
    seen: set[str] = set()
    return [d for d in out if not (d.id in seen or seen.add(d.id))]


# --- one submission, unmasked ---------------------------------------------------------------------------------------------

# PayHOA's builder has only input, textarea, file, checkbox, select, hr, and plaintext; the other names are read too,
# for a submission shaped otherwise.
SECTION_TYPE = "hr"                            # a divider; its label is the section's heading
NOTE_TYPE = "plaintext"                        # the form's own words
SKIP_TYPES = frozenset({SECTION_TYPE, NOTE_TYPE})    # no answer
CHECKBOX_TYPE = "checkbox"
CHOICE_TYPES = frozenset({"select", "checkbox", "radio", "multiselect"})
DATE_TYPES = frozenset({"date", "datetime"})
FILE_TYPES = frozenset({"file", "upload", "image", "attachment"})
TEXT_TYPES = frozenset({"input", "textarea", "text", "email", "phone", "number"})
_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"<\s*br\s*/?\s*>|</\s*(?:p|div|li)\s*>", re.IGNORECASE)
_INLINE = re.compile(r"<\s*/?\s*(?:a|b|strong|em|i|u|span|small|sub|sup)\b[^>]*>", re.IGNORECASE)   # no space
_PARAGRAPH_END = re.compile(r"</\s*p\s*>", re.IGNORECASE)
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_US_DAY = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")


def _words(value: Any) -> str:
    """An answer's words: HTML as text with its line breaks kept, a checkbox's icon as yes or no."""
    text = "" if value is None else str(value)
    folded = text.casefold()
    if "fa-check" in folded:
        return "yes"
    if "fa-times" in folded:
        return "no"
    text = html.unescape(_TAG.sub(" ", _INLINE.sub("", _BREAK.sub("\n", text))))
    return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()


def _items(value: Any) -> list[Any]:
    """An answer as a list: a JSON list (a string holding one, too), or the one value."""
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
        except ValueError:
            return [value]
        return parsed if isinstance(parsed, list) else [value]
    return [] if value in (None, "") else [value]


def _day(value: Any) -> str:
    text = str(value or "").strip()
    m = _DAY.match(text)
    if m:
        return "-".join(m.groups())
    m = _US_DAY.match(text)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return text


def _file_name(value: Any) -> str:
    """A file answer as its file name: the name an object gives, else the last part of a URL or a path."""
    names = []
    for item in _items(value) if not isinstance(value, dict) else [value]:
        if isinstance(item, str) and item.strip().startswith("{"):
            try:
                item = json.loads(item)
            except ValueError:
                pass
        if isinstance(item, dict):
            item = (item.get("name") or item.get("fileName") or item.get("originalName") or item.get("filename")
                    or item.get("url") or item.get("path") or "")
        text = str(item or "").strip()
        if not text:
            continue
        path = urlsplit(text).path if "://" in text else text
        names.append(unquote(path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]) or text)
    return "; ".join(names)


def _labels(question: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for o in question.get("options") or ():
        if isinstance(o, dict):
            label = str(o.get("label") or o.get("value") or "")
            for key in (o.get("value"), o.get("id"), o.get("label")):
                if key not in (None, ""):
                    out.setdefault(str(key), label)
    return out


def _chosen(question: dict[str, Any], value: Any) -> str:
    """A select's answer as its options' labels; a multiselect's in the options' order, then any value no option
    names."""
    labels = _labels(question)
    picked = [v for v in _items(value) if _words(v)]
    if not question.get("isMultiselect"):
        return "; ".join(labels.get(str(v), _words(v)) for v in picked)
    wanted = {str(v) for v in picked}
    out: list[str] = []
    matched: set[str] = set()
    for o in question.get("options") or ():
        if not isinstance(o, dict):
            continue
        keys = {str(k) for k in (o.get("value"), o.get("id"), o.get("label")) if k not in (None, "")}
        if keys & wanted:
            out.append(str(o.get("label") or o.get("value") or ""))
            matched |= keys
    return "; ".join(out + [_words(v) for v in picked if str(v) not in matched])


_FILE_IDS = re.compile(r"^\s*\d+(?:\s*,\s*\d+)*\s*$")


def _files_of(value: Any, uploads: list[Any], documents: list[Document]) -> tuple[str, list[str]]:
    """A file answer as its files' names, and the ids of the documents saved for them. PayHOA answers a file question
    with its files' ids, comma-separated ("9" or "9,12"); each upload's name is on the answer's ``files``, and
    ``jason sync-request-files`` saves it in the request's folder as ``{id}_{name}``."""
    text = "" if value is None else str(value)
    if not _FILE_IDS.match(text):
        return _file_name(value), []
    names: dict[str, str] = {}
    for f in uploads:
        if isinstance(f, dict) and f.get("id") not in (None, ""):
            names.setdefault(str(f["id"]), str(f.get("fileName") or f.get("name") or ""))
    saved = [d for d in documents if d.kind != "submission" and d.path is not None]
    shown: list[str] = []
    linked: list[str] = []
    for fid in dict.fromkeys(p.strip() for p in text.split(",")):
        name = names.get(fid, "")
        doc = next((d for d in saved if name and d.path.name == f"{fid}_{name}"), None) or next(
            (d for d in saved if d.path.name.startswith(f"{fid}_")), None)
        if doc is not None:
            linked.append(doc.id)
            name = name or doc.path.name[len(fid) + 1:]
        shown.append(name or f"file {fid}")
    return "; ".join(shown), linked


def _answer_of(question: dict[str, Any], value: Any) -> tuple[str, str]:
    """(the answer as a person reads it, its kind: text, choice, date, file, or other)."""
    qtype = str(question.get("type") or "").casefold()
    if qtype in FILE_TYPES:
        return _file_name(value), "file"
    if qtype in DATE_TYPES:
        return _day(value), "date"
    if qtype in CHOICE_TYPES or question.get("isMultiselect"):
        return _chosen(question, value), "choice"
    if qtype in TEXT_TYPES:
        return _words(value), "text"
    return _words(value), "other"


def _checked(value: Any) -> bool:
    """A checked box. PayHOA answers a checkbox with an icon: ``fa-check-square-o`` checked, ``fa-times`` not."""
    text = "" if value is None else str(value).strip().casefold()
    if "fa-check" in text:
        return True
    if "fa-times" in text:
        return False
    return text in ("1", "true", "yes", "on", "checked")


def _qid(answer: dict[str, Any]) -> str:
    question = answer.get("question") if isinstance(answer.get("question"), dict) else {}
    return str(answer.get("formQuestionId") or answer.get("questionId") or question.get("id") or "")


def _order(question: dict[str, Any]) -> tuple[float, float]:
    def number(v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return float("inf")
    return number(question.get("sortOrder")), number(question.get("id"))


_PREFIXED = re.compile(r"^(\d+)\.\s+(.+?):\s+(.+)$", re.DOTALL)    # "N. Title: Option", one box of a question
_SAME = re.compile(r"^same as\b", re.IGNORECASE)                     # the usual answer, as a box
_OTHER = re.compile(r"^other\b", re.IGNORECASE)                      # "Other", with a line to say what
_CERTIFY = re.compile(r"^i certify\b", re.IGNORECASE)                # the attestation
NONE_CHOSEN = "None chosen"
BOTH_GIVEN = "both given"


@dataclass(frozen=True)
class _Entry:
    """One question of the submission, its answer row's value (``answered``: whether it has one), its uploads, and
    the field jason's lock records it answers (``""`` when no lock knows it)."""
    qid: str
    question: dict[str, Any]
    value: Any = None
    answered: bool = False
    files: tuple[Any, ...] = ()
    field: str = ""

    @property
    def type(self) -> str:
        return str(self.question.get("type") or "").casefold()

    @property
    def label(self) -> str:
        return _words(self.question.get("label") or self.question.get("title") or "")

    @property
    def help(self) -> str:
        return _words(self.question.get("description"))

    @property
    def required(self) -> bool:
        return bool(self.question.get("isRequired") or self.question.get("required"))


def _prefixed(label: str) -> tuple[str, str] | None:
    """("N. Title", "Option") for a box labelled the way jason's builder labels one option of a question."""
    m = _PREFIXED.match(label)
    return (f"{m.group(1)}. {m.group(2)}", m.group(3)) if m else None


def _parts(label: str) -> tuple[str, str]:
    """A grouped box's question and option: the numbered prefix, else the part before the first ": "."""
    found = _prefixed(label)
    if found:
        return found
    head, sep, tail = label.partition(": ")
    return (head, tail) if sep else (label, label)


def _lock_fields(records: list[Any] | None, form_id: Any) -> dict[str, str]:
    """Question id to field, from jason's record of the form (``data/payhoa/forms.json``), a deleted one too."""
    if form_id in (None, ""):
        return {}
    rows = [r for r in records or () if isinstance(r, dict) and str(r.get("formId")) == str(form_id)]
    questions = rows[-1].get("questions") if rows else None
    return {str(k): str(v or "") for k, v in questions.items()} if isinstance(questions, dict) else {}


def _row(question: str, answer: str, kind: str, *, help_text: str = "", required: bool = False,
         flag: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {"question": question, "answer": answer, "kind": kind}
    if help_text:
        row["help"] = help_text
    if required:
        row["required"] = True
    if flag:
        row["flag"] = flag
    return row


def _groups(entries: list[_Entry]) -> tuple[dict[tuple[Any, ...], list[_Entry]], dict[tuple[Any, ...], _Entry]]:
    """The checkboxes that are one question, and the line each "Same as" or "Other" box goes with.

    A box the lock knows groups by its field (``base.option``: the boxes sharing ``base``); a box the lock does not
    know groups with the boxes next to it labelled with the same "N. Title". A box with neither is alone. A group
    with a "Same as ..." or an "Other" option takes the text question that shares its field (``base``) or its prefix."""
    groups: dict[tuple[Any, ...], list[_Entry]] = {}
    run, last = 0, ""
    for e in entries:
        key: tuple[Any, ...] | None = None
        if e.type == CHECKBOX_TYPE:
            if e.field:
                if "." in e.field:
                    key = ("lock", e.field.rsplit(".", 1)[0])
                last = ""
            else:
                found = _prefixed(e.label)
                if found:
                    run += 0 if found[0] == last else 1
                    last = found[0]
                    key = ("label", run, found[0])
                else:
                    last = ""
        else:
            last = ""
        if key is not None:
            groups.setdefault(key, []).append(e)
    grouped = {e.qid for boxes in groups.values() for e in boxes}
    partners: dict[tuple[Any, ...], _Entry] = {}
    for key, boxes in groups.items():
        if not any(_SAME.match(_parts(b.label)[1]) or _OTHER.match(_parts(b.label)[1]) for b in boxes):
            continue
        prefix = _parts(boxes[0].label)[0]
        base = key[1] if key[0] == "lock" else ""
        taken = grouped | {p.qid for p in partners.values()}
        partner = next((e for e in entries if e.type in TEXT_TYPES and e.qid not in taken and (
            (base and e.field in (base, f"{base}.other"))
            or (not e.field and (_prefixed(e.label) or ("",))[0] == prefix))), None)
        if partner is not None:
            partners[key] = partner
    return groups, partners


def _group_row(boxes: list[_Entry], partner: _Entry | None) -> dict[str, Any]:
    """One question asked as several boxes: the checked options in order ("None chosen" when none), a "Same as" box
    with its line, or "Other" with what was written."""
    text = _words(partner.value) if partner else ""
    answered = any(b.answered for b in boxes) or bool(partner and partner.answered)
    chosen: list[str] = []
    same: bool | None = None
    for b in boxes:
        option, ticked = _parts(b.label)[1], _checked(b.value)
        if partner and _SAME.match(option):
            same = bool(same) or ticked
            if ticked:
                chosen.append(option)
        elif partner and _OTHER.match(option):
            if ticked or text:
                chosen.append(f"Other: {text}" if text else "Other (not specified)")
        elif ticked:
            chosen.append(option)
    if same is not None and text:
        chosen.append(text)
    if same is not None or not answered:
        answer = "; ".join(chosen)
    else:
        answer = "; ".join(chosen) or NONE_CHOSEN
    helps = list(dict.fromkeys(h for h in [b.help for b in boxes] + [partner.help if partner else ""] if h))
    return _row(_parts(boxes[0].label)[0], answer, "choice", help_text=" ".join(helps),
                required=any(e.required for e in [*boxes, *([partner] if partner else [])]),
                flag=BOTH_GIVEN if same and text else "")


def _entry_row(e: _Entry, documents: list[Document]) -> dict[str, Any] | None:
    """One question on its own: a section heading, the form's words, a lone box, or a question and its answer."""
    if e.type == SECTION_TYPE:
        heading = e.label or e.help
        return _row(heading, "", "section") if heading else None
    if e.type == NOTE_TYPE:
        words = e.label or e.help
        return _row(words, "", "note", help_text=e.help if e.label else "") if words else None
    question = e.label or f"Question {e.qid}"
    if e.type == CHECKBOX_TYPE and not e.question.get("options"):
        attest = e.required and bool(_CERTIFY.match(question))
        ticked = _checked(e.value)
        answer = "" if not e.answered else (("Certified" if ticked else "Not certified") if attest
                                            else ("Checked" if ticked else "Not checked"))
        return _row(question, answer, "check", help_text=e.help, required=e.required)
    if e.type in FILE_TYPES:
        answer, linked = _files_of(e.value, list(e.files), documents)
        row = _row(question, answer, "file", help_text=e.help, required=e.required)
        if linked:
            row["files"] = linked
        return row
    answer, kind = _answer_of(e.question, e.value)
    return _row(question, answer, kind, help_text=e.help, required=e.required)


def _intro(description: Any) -> str:
    """The form's description as text: its line breaks kept, a blank line between paragraphs."""
    text = _words(_PARAGRAPH_END.sub("</p>\n", str(description or "")))
    return re.sub(r"\n{3,}", "\n\n", text)


def submission_view(cached: dict[str, Any], *, records: list[Any] | None = None,
                    documents: list[Document] | tuple[Document, ...] = ()) -> dict[str, Any]:
    """A kept submission as a person reads it, unmasked: ``{form, unit, submitted, completed?, status, intro,
    questions: [{question, answer, kind, help?, required?, flag?, files?}]}``.

    The questions are the form's (``form.questions`` when the submission carries them, else each answer's own
    question), in its order (``sortOrder``); answers are matched by question id. A divider (``hr``) is a ``section``
    row with its heading, and the form's own words (``plaintext``) a ``note``. The boxes jason's builder makes of one
    "choose any" question are one ``choice`` row: grouped by the fields jason's record of the form gives them
    (``records``, ``data/payhoa/forms.json``), else by their shared "N. Title" label; a "Same as" box and its line,
    and an "Other" box and its line, are one row too. A lone box is a ``check``. A file answer names its files, with
    the ids of the ``documents`` saved for them (``files``), for the viewer to open."""
    from jason.tasks.submission_cache import body

    sub = body(cached.get("submission"))
    form = sub.get("form") if isinstance(sub.get("form"), dict) else {}
    answers: dict[str, Any] = {}
    uploads: dict[str, tuple[Any, ...]] = {}
    questions: dict[str, dict[str, Any]] = {}
    for q in form.get("questions") or ():
        if isinstance(q, dict) and q.get("id") not in (None, ""):
            questions[str(q["id"])] = q
    for a in sub.get("answers") or ():
        if not isinstance(a, dict):
            continue
        qid = _qid(a)
        if not qid:
            continue
        answers[qid] = a.get("answer") if "answer" in a else a.get("value")
        uploads[qid] = tuple(a.get("files") or ()) if isinstance(a.get("files"), list) else ()
        own = a.get("question") if isinstance(a.get("question"), dict) else {}
        if qid not in questions:
            questions[qid] = {"id": qid, "label": own.get("label") or a.get("label") or f"Question {qid}", **own}
    fields = _lock_fields(records, sub.get("formId") or form.get("id") or cached.get("formId"))
    entries = [_Entry(qid, q, answers.get(qid), qid in answers, uploads.get(qid, ()), fields.get(qid, ""))
               for qid, q in sorted(questions.items(), key=lambda kv: _order(kv[1]))]
    groups, partners = _groups(entries)
    member = {e.qid: key for key, boxes in groups.items() for e in boxes}
    member.update({p.qid: key for key, p in partners.items()})
    rows: list[dict[str, Any]] = []
    done: set[tuple[Any, ...]] = set()
    docs = list(documents)
    for e in entries:
        key = member.get(e.qid)
        if key is None:
            row = _entry_row(e, docs)
            if row is not None:
                rows.append(row)
        elif key not in done:
            done.add(key)
            rows.append(_group_row(groups[key], partners.get(key)))
    unit = sub.get("unit") if isinstance(sub.get("unit"), dict) else {}
    out: dict[str, Any] = {"form": str(cached.get("formName") or form.get("name") or ""),
                           "unit": str(unit.get("title") or unit.get("streetAddress") or "").strip(),
                           "submitted": str(sub.get("createdAt") or ""),
                           "status": str(cached.get("status") or sub.get("status") or ""),
                           "intro": _intro(form.get("description")),
                           "questions": rows}
    if sub.get("completionDate"):
        out["completed"] = _day(sub["completionDate"])
    return out


# --- view one -------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Opened:
    """A document opened for a person: the answer jason-web returns (without its link), and the file it serves."""
    answer: dict[str, Any]
    path: Path | None = None
    root: Path | None = None


def documents_for(address: str, root: Path, *, private: bool = False) -> tuple[str, list[Document]]:
    """The evidence kind of ``address`` and the documents behind it, as ``resolve`` lists them, with their files;
    ``private`` lists the confidential ones too (the private view)."""
    from jason.approvals.evidence import EvidenceKind, rule_for

    rule, found = rule_for(address)
    if rule.kind is EvidenceKind.PAYHOA_SUBMISSION and found is not None:
        return rule.kind.value, request_documents(root, int(found.group(1)))
    if rule.kind is EvidenceKind.DRIVE and found is not None:
        return rule.kind.value, drive_documents(root, found.group(1), private=private)
    if rule.kind is EvidenceKind.FILE and found is not None:
        return rule.kind.value, file_documents(root, found.group(1), private=private)
    if rule.kind is EvidenceKind.CITATION:
        from jason.tasks import cite

        got = cite.resolve(address, data_dir=root, private=private)
        statute = bool(re.match(r"^[A-Z]{2,5} \d", str(got.get("citation") or address)))
        read_at = _mtime(root / "authorities" / "manifest.json") if statute else ""
        return rule.kind.value, citation_documents(root, got, statute=statute, read_at=read_at, private=private)
    return rule.kind.value, []


def _form_records(root: Path) -> list[Any]:
    """jason's records of its PayHOA forms (``data/payhoa/forms.json``), deleted ones too; none when unreadable."""
    from jason.tasks.payhoa_forms import load_records

    try:
        rows = load_records(root)
    except (OSError, ValueError, AttributeError):
        return []
    return rows if isinstance(rows, list) else []


def _bad_id(document: str) -> bool:
    return (not document or document in (".", "..") or any(c in document for c in "/\\\x00")
            or len(document) > 255)


def _log_view(root: Path, entry: dict[str, Any]) -> None:
    file = root / VIEW_LOG
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as out:
        out.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def view(address: str, document: str, *, by: str, approval_id: str = "", data_dir: Path | None = None,
         private: bool = False) -> Opened:
    """Open one document behind ``address`` unmasked for the person ``by``, and log it (``evidence/views.jsonl``).

    Refuses (``ValueError``) an empty ``by``, no address, and a document id that names a path (``/``, ``\\``,
    ``..``); an id the address does not list, or a file no longer on disk, is ``KeyError``. Reads disk only. The
    answer is ``{kind, name, readAt, submission?, text?, caveats}``; a pdf, an image, or another file comes with its
    path and the folder it must stay inside, for jason-web to serve. ``approval_id`` is accepted for the console's
    context and changes nothing here. ``private`` (the private view) opens a confidential document too; its answer
    carries ``level: "P3"``."""
    from jason.approvals.evidence import DISK_ONLY, _root

    del approval_id
    by = " ".join(str(by or "").split())
    if not by:
        raise ValueError("a view names the person (by): it shows the document unmasked under their name")
    address = " ".join(str(address or "").split())
    if not address:
        raise ValueError("name the evidence address whose document to open")
    document = str(document or "").strip()
    if _bad_id(document):
        raise ValueError(f"{document or '(none)'} is not a document id: name one the evidence lists")
    root = _root(data_dir)
    _, docs = documents_for(address, root, private=private)
    doc = next((d for d in docs if d.id == document), None)
    if doc is None:
        raise KeyError(f"{address} lists no document {document}")
    answer: dict[str, Any] = {"kind": doc.kind, "name": doc.name, "readAt": doc.read_at,
                              "caveats": [UNMASKED.format(by=by)] + [c for c in (doc.caveat, DISK_ONLY) if c]}
    if doc.level:
        answer["level"] = doc.level
    path = root_of = None
    if doc.kind == "submission":
        from jason.approvals.evidence import _files_root
        from jason.tasks import submission_cache

        sid = int(address.rsplit(":", 1)[1])
        try:
            cached = submission_cache.read(_files_root(root), sid)
        except ValueError as exc:
            raise KeyError(f"request {sid}'s last read could not be opened ({exc})") from exc
        if cached is None:
            raise KeyError(f"request {sid} has no full read on disk")
        answer["submission"] = submission_view(cached, records=_form_records(root), documents=docs)
    elif doc.id == "section":
        from jason.tasks import cite

        got = cite.resolve(address, data_dir=root, private=private)
        if not got.get("found") or not got.get("text"):
            raise KeyError(f"{address}: its words are no longer on disk")
        answer["text"] = str(got["text"])
    elif doc.path is None or doc.root is None or not inside(doc.path, doc.root):
        raise KeyError(f"{doc.name} is no longer on disk")
    elif doc.kind == "text":
        if _size(doc.path) > MAX_TEXT:
            raise ValueError(f"{doc.name} is too large to show as text ({_size(doc.path)} bytes)")
        answer["text"] = doc.path.read_text(encoding="utf-8", errors="replace")
    else:
        path, root_of = doc.path.resolve(), doc.root.resolve()
    _log_view(root, {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "by": by, "address": address,
                     "document": doc.id, "kind": doc.kind, **({"level": doc.level} if doc.level else {})})
    return Opened(answer, path, root_of)


__all__ = ["ATTACHMENT_CAVEAT", "CONFIDENTIAL", "CONFIDENTIAL_NOTE", "Document", "EXTENSIONS", "MAX_TEXT", "OCTET", "Opened", "UNMASKED", "VIEW_LOG",
           "citation_documents", "confidential", "content_type", "documents_for", "drive_documents", "file_documents",
           "file_id", "file_level", "file_place", "inside", "kind_of",
           "request_documents", "submission_view", "view"]
