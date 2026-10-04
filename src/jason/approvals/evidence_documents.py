"""The documents behind a piece of evidence, and viewing one unmasked: what ``resolve`` lists, and what a person opens.

``resolve`` answers what jason holds of a record, masked. Each answer also lists the documents behind it
(``documents``): the files on disk a person may open whole.

- **A PayHOA request.** The submission as last read in full (``payhoa-files/requests/N/submission.json``), and each
  attachment ``jason sync-request-files`` saved in the request's folder. Never the folder's comments, notes, the
  submission's own file, or a file half written (``.tmp``).
- **A citation.** The whole section as stored, and the governing document's own file, when ``jason cite`` names one
  (a library path, or a Drive id the Drive holdings place in the library or under the data folder) and the library
  does not hold it as confidential: the file itself, and the library's extracted text of it.
- **A board item or a command.** None.

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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

VIEW_LOG = Path("evidence") / "views.jsonl"
UNMASKED = "Unmasked: shown because {by} asked; this view is logged."
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
    (``path``) and the folder it must stay inside (``root``); both None for a submission or a section."""
    id: str
    name: str
    kind: str
    size: int = 0
    read_at: str = ""
    note: str = ""
    caveat: str = ""
    path: Path | None = None
    root: Path | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "kind": self.kind, "size": self.size, "readAt": self.read_at,
                "note": self.note}


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

def _library(root: Path, library_path: str, label: str = "") -> list[Document]:
    """A library file by its library path: the file itself and its extracted text, each when on disk under the data
    folder; nothing for a file the library holds as confidential."""
    db = root / "library" / "library.db"
    if not library_path or not db.is_file():
        return []
    try:
        with sqlite3.connect(f"{db.resolve().as_uri()}?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT id, confidential FROM documents WHERE path = ? LIMIT 1",
                               (library_path,)).fetchone()
    except sqlite3.Error:
        return []
    if row is None or row[1]:
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
    return out


_DRIVE_FILE = re.compile(r"/(?:file|document|spreadsheets|presentation)/d/([\w-]+)")


def _drive(root: Path, drive_id: str, label: str = "") -> list[Document]:
    """A Drive file placed on disk by the Drive holdings (``jason drive-catalog``'s ``drive/holdings.json``): its
    library copy, else its first copy under the data folder; nothing for a confidential one."""
    report = root / "drive" / "holdings.json"
    if not drive_id or not report.is_file():
        return []
    try:
        rows = json.loads(report.read_text(encoding="utf-8")).get("rows") or []
    except (OSError, ValueError):
        return []
    row = next((r for r in rows if isinstance(r, dict) and r.get("id") == drive_id), None)
    if row is None or row.get("confidential"):
        return []
    for place in row.get("elsewhere") or ():
        if place.get("channel") == "PayHOA library":
            found = _library(root, str(place.get("where") or ""), label)
            if found:
                return found
    for place in row.get("elsewhere") or ():
        if place.get("channel") == "PayHOA library":
            continue
        path = root / str(place.get("where") or "")
        if place.get("where") and inside(path, root):
            return [Document(f"drive:{drive_id}", str(row.get("name") or path.name), kind_of(path.name), _size(path),
                             _mtime(path), f"{label}: a copy on disk of the Drive file" if label else
                             "a copy on disk of the Drive file", LIBRARY_CAVEAT, path, root)]
    return []


def citation_documents(root: Path, got: dict[str, Any], *, statute: bool, read_at: str = "") -> list[Document]:
    """A resolved citation's documents: the whole section when its words are stored, then the governing document's
    file and its extracted text, from the links ``jason cite`` gives (a library path, a Drive file)."""
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
            out += _library(root, str(link["library"]), label)
        elif link.get("url"):
            found = _DRIVE_FILE.search(urlsplit(str(link["url"])).path)
            if found:
                out += _drive(root, found.group(1), label)
    seen: set[str] = set()
    return [d for d in out if not (d.id in seen or seen.add(d.id))]


# --- one submission, unmasked ---------------------------------------------------------------------------------------------

SKIP_TYPES = frozenset({"hr", "plaintext"})    # a divider and a form's own words: no answer
CHOICE_TYPES = frozenset({"select", "checkbox", "radio", "multiselect"})
DATE_TYPES = frozenset({"date", "datetime"})
FILE_TYPES = frozenset({"file", "upload", "image", "attachment"})
TEXT_TYPES = frozenset({"input", "textarea", "text", "email", "phone", "number"})
_TAG = re.compile(r"<[^>]+>")
_BREAK = re.compile(r"<\s*br\s*/?\s*>|</\s*(?:p|div|li)\s*>", re.IGNORECASE)
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
    text = html.unescape(_TAG.sub(" ", _BREAK.sub("\n", text)))
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


def _answer_of(question: dict[str, Any], value: Any) -> tuple[str, str]:
    """(the answer as a person reads it, its kind: text, choice, date, file, or other)."""
    qtype = str(question.get("type") or "").casefold()
    if qtype in FILE_TYPES:
        return _file_name(value), "file"
    if qtype in DATE_TYPES:
        return _day(value), "date"
    if qtype in CHOICE_TYPES or question.get("isMultiselect"):
        labels = _labels(question)
        return "; ".join(labels.get(str(v), _words(v)) for v in _items(value) if _words(v)), "choice"
    if qtype in TEXT_TYPES:
        return _words(value), "text"
    return _words(value), "other"


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


def submission_view(cached: dict[str, Any]) -> dict[str, Any]:
    """A kept submission as a person reads it, unmasked: ``{form, unit, submitted, status, questions: [{question,
    answer, kind}]}``. The questions are the form's (``form.questions`` when the submission carries them, else each
    answer's own question), in its order (``sortOrder``); answers are matched by question id. A divider or the form's
    own words (``hr``, ``plaintext``) is no question."""
    from jason.tasks.submission_cache import body

    sub = body(cached.get("submission"))
    form = sub.get("form") if isinstance(sub.get("form"), dict) else {}
    answers: dict[str, Any] = {}
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
        own = a.get("question") if isinstance(a.get("question"), dict) else {}
        if qid not in questions:
            questions[qid] = {"id": qid, "label": own.get("label") or a.get("label") or f"Question {qid}", **own}
    rows = []
    for qid, q in sorted(questions.items(), key=lambda kv: _order(kv[1])):
        if str(q.get("type") or "").casefold() in SKIP_TYPES:
            continue
        answer, kind = _answer_of(q, answers.get(qid))
        rows.append({"question": _words(q.get("label") or q.get("title") or f"Question {qid}"), "answer": answer,
                     "kind": kind})
    unit = sub.get("unit") if isinstance(sub.get("unit"), dict) else {}
    return {"form": str(cached.get("formName") or form.get("name") or ""),
            "unit": str(unit.get("title") or unit.get("streetAddress") or "").strip(),
            "submitted": str(sub.get("createdAt") or ""),
            "status": str(cached.get("status") or sub.get("status") or ""),
            "questions": rows}


# --- view one -------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Opened:
    """A document opened for a person: the answer jason-web returns (without its link), and the file it serves."""
    answer: dict[str, Any]
    path: Path | None = None
    root: Path | None = None


def documents_for(address: str, root: Path) -> tuple[str, list[Document]]:
    """The evidence kind of ``address`` and the documents behind it, as ``resolve`` lists them, with their files."""
    from jason.approvals.evidence import EvidenceKind, rule_for

    rule, found = rule_for(address)
    if rule.kind is EvidenceKind.PAYHOA_SUBMISSION and found is not None:
        return rule.kind.value, request_documents(root, int(found.group(1)))
    if rule.kind is EvidenceKind.CITATION:
        from jason.tasks import cite

        got = cite.resolve(address, data_dir=root)
        statute = bool(re.match(r"^[A-Z]{2,5} \d", str(got.get("citation") or address)))
        read_at = _mtime(root / "authorities" / "manifest.json") if statute else ""
        return rule.kind.value, citation_documents(root, got, statute=statute, read_at=read_at)
    return rule.kind.value, []


def _bad_id(document: str) -> bool:
    return (not document or document in (".", "..") or any(c in document for c in "/\\\x00")
            or len(document) > 255)


def _log_view(root: Path, entry: dict[str, Any]) -> None:
    file = root / VIEW_LOG
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as out:
        out.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")


def view(address: str, document: str, *, by: str, approval_id: str = "", data_dir: Path | None = None) -> Opened:
    """Open one document behind ``address`` unmasked for the person ``by``, and log it (``evidence/views.jsonl``).

    Refuses (``ValueError``) an empty ``by``, no address, and a document id that names a path (``/``, ``\\``,
    ``..``); an id the address does not list, or a file no longer on disk, is ``KeyError``. Reads disk only. The
    answer is ``{kind, name, readAt, submission?, text?, caveats}``; a pdf, an image, or another file comes with its
    path and the folder it must stay inside, for jason-web to serve. ``approval_id`` is accepted for the console's
    context and changes nothing here."""
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
    _, docs = documents_for(address, root)
    doc = next((d for d in docs if d.id == document), None)
    if doc is None:
        raise KeyError(f"{address} lists no document {document}")
    answer: dict[str, Any] = {"kind": doc.kind, "name": doc.name, "readAt": doc.read_at,
                              "caveats": [UNMASKED.format(by=by)] + [c for c in (doc.caveat, DISK_ONLY) if c]}
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
        answer["submission"] = submission_view(cached)
    elif doc.id == "section":
        from jason.tasks import cite

        got = cite.resolve(address, data_dir=root)
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
                     "document": doc.id, "kind": doc.kind})
    return Opened(answer, path, root_of)


__all__ = ["ATTACHMENT_CAVEAT", "Document", "EXTENSIONS", "MAX_TEXT", "OCTET", "Opened", "UNMASKED", "VIEW_LOG",
           "citation_documents", "content_type", "documents_for", "file_id", "inside", "kind_of",
           "request_documents", "submission_view", "view"]
