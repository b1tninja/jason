"""Dry-run planner: which Drive files would copy into which PayHOA folders.

Pure functions only. No Drive or PayHOA API calls, uploads, or downloads.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

# Drive root folders that must never be copied from, even if listed.
_DRIVE_ROOT_SKIP = frozenset({"Confidential", "Email Attachments"})
_EMAIL_ATTACHMENTS = "Email Attachments"
_BRACE_RE = re.compile(r"\{([^{}]+)\}")


@dataclass(frozen=True)
class PlannedCopy:
    """One Drive file that would land in a PayHOA folder."""

    drive_file_id: str
    drive_name: str
    payhoa_parent_id: int
    destination_path: str


def plan_document_sync(
    rules: Mapping[str, Any],
    drive_files: Sequence[Mapping[str, Any]],
    payhoa_docs: Sequence[Mapping[str, Any]],
) -> list[PlannedCopy]:
    """Return planned copies from in-memory Drive + PayHOA inventories.

    Name-match only: a Drive file is planned only when a PayHOA document with
    the same ``fileName`` already exists somewhere. Unmatched names are omitted.
    Rows whose destination path already has that file name are skipped.
    """
    rule_rows = list(rules.get("rules") or [])
    excludes = list(rules.get("exclude") or [])
    exclude_ids = {str(row.get("drive_id")) for row in excludes if row.get("drive_id")}
    exclude_folders = {
        _norm_folder(str(row.get("drive_folder") or "")) for row in excludes if row.get("drive_folder")
    }

    by_id = {str(item["id"]): item for item in drive_files if item.get("id") is not None}
    folder_ids = _folder_ids(drive_files, rule_rows, excludes)

    payhoa_dirs = {
        _norm_folder(str(doc.get("path") or "")): doc
        for doc in payhoa_docs
        if doc.get("directory")
    }
    files_by_name: dict[str, list[Mapping[str, Any]]] = {}
    for doc in payhoa_docs:
        if doc.get("directory"):
            continue
        name = str(doc.get("fileName") or "")
        if not name:
            continue
        files_by_name.setdefault(name, []).append(doc)

    planned: list[PlannedCopy] = []
    seen_drive: set[str] = set()

    for item in drive_files:
        drive_id = str(item.get("id") or "")
        if not drive_id or drive_id in folder_ids or drive_id in seen_drive:
            continue
        name = str(item.get("name") or "")
        if not name:
            continue

        folder_path = _drive_folder_path(item, by_id)
        if folder_path is None:
            continue
        if _is_loose_root(folder_path):
            continue
        root = folder_path.split("/", 1)[0] if folder_path else ""
        if root in _DRIVE_ROOT_SKIP:
            continue
        if _under_excluded(folder_path, item, by_id, exclude_ids, exclude_folders):
            continue

        matches = files_by_name.get(name)
        if not matches:
            # Name-match only: do not upload Drive files PayHOA has never seen.
            continue

        rule = _matching_rule(rule_rows, item, by_id, folder_path, name)
        if rule is None:
            continue

        parent_id, dest_path = _destination(rule, name, matches, payhoa_dirs)
        if parent_id is None or dest_path is None:
            continue
        if _already_at_path(matches, dest_path):
            continue

        seen_drive.add(drive_id)
        planned.append(
            PlannedCopy(
                drive_file_id=drive_id,
                drive_name=name,
                payhoa_parent_id=parent_id,
                destination_path=dest_path,
            )
        )

    planned.sort(key=lambda row: (row.destination_path, row.drive_file_id))
    return planned


def _folder_ids(
    drive_files: Sequence[Mapping[str, Any]],
    rule_rows: Sequence[Mapping[str, Any]],
    excludes: Sequence[Mapping[str, Any]],
) -> set[str]:
    ids = {str(p) for item in drive_files for p in (item.get("parents") or [])}
    for row in rule_rows:
        if row.get("drive_id"):
            ids.add(str(row["drive_id"]))
    for row in excludes:
        if row.get("drive_id"):
            ids.add(str(row["drive_id"]))
    return ids


def _drive_folder_path(
    item: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]]
) -> str | None:
    """Slash path of the Drive folders that contain ``item`` (no file name)."""
    parts: list[str] = []
    parents = list(item.get("parents") or [])
    seen: set[str] = set()
    while parents:
        parent_id = str(parents[0])
        if parent_id in seen:
            return None
        seen.add(parent_id)
        parent = by_id.get(parent_id)
        if parent is None:
            # Parent is My Drive root (or outside the inventory): path so far is
            # relative to that root.
            break
        parts.append(str(parent.get("name") or ""))
        parents = list(parent.get("parents") or [])
    parts.reverse()
    return "/".join(p for p in parts if p)


def _is_loose_root(folder_path: str) -> bool:
    """True when the file sits at Drive root, not under a named library folder."""
    return folder_path == ""


def _under_excluded(
    folder_path: str,
    item: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
    exclude_ids: set[str],
    exclude_folders: set[str],
) -> bool:
    if any(
        folder_path == ex or folder_path.startswith(ex + "/") for ex in exclude_folders if ex
    ):
        return True
    ancestors = _ancestor_ids(item, by_id)
    return bool(ancestors & exclude_ids)


def _ancestor_ids(
    item: Mapping[str, Any], by_id: Mapping[str, Mapping[str, Any]]
) -> set[str]:
    out: set[str] = set()
    parents = list(item.get("parents") or [])
    seen: set[str] = set()
    while parents:
        parent_id = str(parents[0])
        if parent_id in seen:
            break
        seen.add(parent_id)
        out.add(parent_id)
        parent = by_id.get(parent_id)
        if parent is None:
            break
        parents = list(parent.get("parents") or [])
    return out


def _matching_rule(
    rule_rows: Sequence[Mapping[str, Any]],
    item: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
    folder_path: str,
    name: str,
) -> Mapping[str, Any] | None:
    ancestors = _ancestor_ids(item, by_id)
    for rule in rule_rows:
        drive_folder = _norm_folder(str(rule.get("drive_folder") or ""))
        drive_id = str(rule.get("drive_id") or "")
        under = False
        if drive_id and drive_id in ancestors:
            under = True
        elif drive_folder and (
            folder_path == drive_folder or folder_path.startswith(drive_folder + "/")
        ):
            under = True
        if not under:
            continue
        if not _glob_match(str(rule.get("glob") or ""), name):
            continue
        rel = _relative_folder(folder_path, drive_folder)
        if _rule_excludes(rule, rel, name):
            continue
        if str(rule.get("id") or "") == "insurance-current" and rel:
            # Folder root only: year and other subfolders stay out.
            continue
        return rule
    return None


def _rule_excludes(rule: Mapping[str, Any], rel_folder: str, name: str) -> bool:
    rel_file = f"{rel_folder}/{name}" if rel_folder else name
    for pattern in rule.get("exclude") or []:
        pat = str(pattern)
        if pat.endswith("/**"):
            prefix = pat[:-3]
            if rel_folder == prefix or rel_folder.startswith(prefix + "/"):
                return True
            if rel_file == prefix or rel_file.startswith(prefix + "/"):
                return True
        elif _glob_match(pat, rel_file) or _glob_match(pat, name):
            return True
    return False


def _relative_folder(folder_path: str, drive_folder: str) -> str:
    if not drive_folder:
        return folder_path
    if folder_path == drive_folder:
        return ""
    prefix = drive_folder + "/"
    if folder_path.startswith(prefix):
        return folder_path[len(prefix) :]
    return folder_path


def _destination(
    rule: Mapping[str, Any],
    name: str,
    matches: Sequence[Mapping[str, Any]],
    payhoa_dirs: Mapping[str, Mapping[str, Any]],
) -> tuple[int | None, str | None]:
    raw = str(rule.get("payhoa") or "").strip()
    if not raw:
        return None, None

    recursive = raw.endswith("**")
    prefix = _norm_folder(raw[:-2] if recursive else raw)

    library = [
        doc
        for doc in matches
        if not _is_email_attachments(doc) and _path_under(str(doc.get("path") or ""), prefix)
    ]
    email_only = [doc for doc in matches if _is_email_attachments(doc)]

    # Prefer a named library path over Email Attachments when both exist.
    if library:
        # Already present under the library prefix; caller skips via path check
        # using the concrete destination of the preferred match.
        preferred = sorted(library, key=lambda d: str(d.get("path") or ""))[0]
        parent_id = preferred.get("parentId")
        dest = str(preferred.get("path") or "")
        if parent_id is None:
            return None, None
        return int(parent_id), dest

    if recursive:
        # Glob does not choose Grant Deeds vs Common Areas; without a library
        # hit, land at the named root folder.
        folder = payhoa_dirs.get(prefix)
    else:
        folder = payhoa_dirs.get(prefix)

    if folder is None or folder.get("id") is None:
        return None, None
    if not email_only and not matches:
        return None, None
    # Name matched somewhere (often Email Attachments only): copy into library.
    dest_path = f"{prefix}/{name}"
    return int(folder["id"]), dest_path


def _already_at_path(matches: Sequence[Mapping[str, Any]], dest_path: str) -> bool:
    target = dest_path.replace("\\", "/")
    for doc in matches:
        if str(doc.get("path") or "").replace("\\", "/") == target:
            return True
    return False


def _is_email_attachments(doc: Mapping[str, Any]) -> bool:
    path = str(doc.get("path") or "")
    return path == _EMAIL_ATTACHMENTS or path.startswith(_EMAIL_ATTACHMENTS + "/")


def _path_under(path: str, prefix: str) -> bool:
    path = path.replace("\\", "/")
    if not prefix:
        return True
    return path == prefix or path.startswith(prefix + "/")


def _norm_folder(value: str) -> str:
    return value.replace("\\", "/").strip().strip("/")


def _glob_match(pattern: str, name: str) -> bool:
    for pat in _expand_braces(pattern):
        if fnmatch.fnmatchcase(name, pat) or fnmatch.fnmatch(name, pat):
            return True
    return False


def _expand_braces(pattern: str) -> list[str]:
    match = _BRACE_RE.search(pattern)
    if not match:
        return [pattern]
    before = pattern[: match.start()]
    after = pattern[match.end() :]
    out: list[str] = []
    for option in match.group(1).split(","):
        out.extend(_expand_braces(before + option + after))
    return out
