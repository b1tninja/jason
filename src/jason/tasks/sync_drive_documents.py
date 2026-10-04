"""Dry-run: compare Drive files to the PayHOA library using sync rules.

Pure comparison only. Never uploads, downloads, or calls create_document.
Google Docs would need export_pdf (not download); a DRAFT text watermark on
the Doc is included in that PDF and cannot be removed via the Docs API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from jason.tasks import sync_documents as _plan

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
_WATERMARK_NOTE = (
    "Google Doc PDF export includes any DRAFT text watermark; "
    "Docs API cannot remove it"
)

@dataclass(frozen=True)
class DriveSyncRow:
    """One Drive file classified against PayHOA and the sync rules."""

    drive_file_id: str
    drive_name: str
    drive_folder: str
    rule_id: str | None = None
    payhoa_path: str | None = None
    payhoa_parent_id: int | None = None
    reason: str | None = None
    mime_type: str | None = None
    notes: tuple[str, ...] = ()


@dataclass
class DriveSyncReport:
    """Dry-run result: already present, would create, or skipped by rule."""

    matched: list[DriveSyncRow] = field(default_factory=list)
    would_create: list[DriveSyncRow] = field(default_factory=list)
    needs_publish: list[DriveSyncRow] = field(default_factory=list)
    skipped_by_rule: list[DriveSyncRow] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"matched={len(self.matched)} "
            f"would_create={len(self.would_create)} "
            f"needs_publish={len(self.needs_publish)} "
            f"skipped_by_rule={len(self.skipped_by_rule)}"
        )

    def counts_by_rule(self) -> dict[str, dict[str, int]]:
        """Per-rule counts for matched, would_create, needs_publish, and skipped."""
        keys = ("matched", "would_create", "needs_publish", "skipped_by_rule")
        buckets = {
            "matched": self.matched,
            "would_create": self.would_create,
            "needs_publish": self.needs_publish,
            "skipped_by_rule": self.skipped_by_rule,
        }
        out: dict[str, dict[str, int]] = {}
        for name, rows in buckets.items():
            for row in rows:
                slot = out.setdefault(row.rule_id or "(no rule)", {key: 0 for key in keys})
                slot[name] += 1
        return out

    def skipped_reasons(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.skipped_by_rule:
            reason = row.reason or "(no reason)"
            counts[reason] = counts.get(reason, 0) + 1
        return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def load_sync_rules(path: str | Path | None = None) -> dict[str, Any]:
    """Load the community document-sync specification, or ``path`` when given."""
    if path is None:
        from jason.community import community as active

        return active().document_sync_rules()
    return json.loads(Path(path).read_text(encoding="utf-8"))


def list_rule_drive_files(drive: Any, rules: Mapping[str, Any]) -> list[dict[str, Any]]:
    """List one level of each sync-rule folder. Does not walk excluded folders."""
    exclude_ids = {
        str(row["drive_id"]) for row in rules.get("exclude") or [] if row.get("drive_id")
    }
    folder_ids: list[str] = []
    for row in rules.get("rules") or []:
        drive_id = str(row.get("drive_id") or "")
        if drive_id and drive_id not in exclude_ids and drive_id not in folder_ids:
            folder_ids.append(drive_id)
    files: list[dict[str, Any]] = []
    seen: set[str] = set()
    for folder_id in folder_ids:
        folder = drive.get_file(folder_id)
        folder_key = str(folder.get("id") or folder_id)
        if folder_key not in seen:
            files.append(folder)
            seen.add(folder_key)
        for child in drive.list_folder(folder_id):
            child_id = str(child.get("id") or "")
            if not child_id or child_id in seen or child_id in exclude_ids:
                continue
            files.append(child)
            seen.add(child_id)
    return files


def compare_drive_documents(
    drive_files: Sequence[Mapping[str, Any]],
    payhoa_docs: Sequence[Mapping[str, Any]],
    rules: Mapping[str, Any],
) -> DriveSyncReport:
    """Classify already-listed Drive files against PayHOA rows and sync rules.

    Name-match for files already in PayHOA. A rule hit with no PayHOA file is
    ``needs_publish``. A name that misses the glob is skipped. Does not upload.
    """
    rule_rows = list(rules.get("rules") or [])
    excludes = list(rules.get("exclude") or [])
    exclude_ids = {str(row.get("drive_id")) for row in excludes if row.get("drive_id")}
    exclude_folders = {
        _plan._norm_folder(str(row.get("drive_folder") or ""))
        for row in excludes
        if row.get("drive_folder")
    }
    exclude_reason = {
        _plan._norm_folder(str(row.get("drive_folder") or "")): str(
            row.get("reason") or row.get("drive_folder") or "excluded"
        )
        for row in excludes
        if row.get("drive_folder")
    }
    for row in excludes:
        if row.get("drive_id"):
            exclude_reason[str(row["drive_id"])] = str(
                row.get("reason") or row.get("drive_folder") or "excluded"
            )

    by_id = {str(item["id"]): item for item in drive_files if item.get("id") is not None}
    folder_ids = _plan._folder_ids(drive_files, rule_rows, excludes)

    payhoa_dirs = {
        _plan._norm_folder(str(doc.get("path") or "")): doc
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

    matched: list[DriveSyncRow] = []
    would_create: list[DriveSyncRow] = []
    needs_publish: list[DriveSyncRow] = []
    skipped: list[DriveSyncRow] = []
    seen: set[str] = set()

    for item in drive_files:
        drive_id = str(item.get("id") or "")
        if not drive_id or drive_id in folder_ids or drive_id in seen:
            continue
        name = str(item.get("name") or "")
        if not name:
            continue
        seen.add(drive_id)

        mime = item.get("mimeType")
        mime_str = str(mime) if mime else None
        notes = _export_notes(mime_str)
        folder_path = _plan._drive_folder_path(item, by_id)
        if folder_path is None:
            skipped.append(
                _row(
                    drive_id,
                    name,
                    "",
                    reason="unresolvable Drive path",
                    mime_type=mime_str,
                    notes=notes,
                )
            )
            continue

        if _plan._is_loose_root(folder_path):
            skipped.append(
                _row(
                    drive_id,
                    name,
                    folder_path,
                    reason="loose My Drive root",
                    mime_type=mime_str,
                    notes=notes,
                )
            )
            continue

        root = folder_path.split("/", 1)[0]
        if root in _plan._DRIVE_ROOT_SKIP:
            skipped.append(
                _row(
                    drive_id,
                    name,
                    folder_path,
                    reason=f"do not sync {root}/ from Drive root",
                    mime_type=mime_str,
                    notes=notes,
                )
            )
            continue

        excluded_reason = _excluded_reason(
            folder_path, item, by_id, exclude_ids, exclude_folders, exclude_reason
        )
        if excluded_reason is not None:
            skipped.append(
                _row(
                    drive_id,
                    name,
                    folder_path,
                    reason=excluded_reason,
                    mime_type=mime_str,
                    notes=notes,
                )
            )
            continue

        rule = _plan._matching_rule(rule_rows, item, by_id, folder_path, name)
        if rule is None:
            # Under a known rule folder but glob/exclude missed, or outside rules.
            near = _near_rule(rule_rows, item, by_id, folder_path)
            if near is not None:
                reason = _skip_reason_for_near_rule(near, folder_path, name)
            else:
                reason = "no matching sync rule"
            skipped.append(
                _row(
                    drive_id,
                    name,
                    folder_path,
                    rule_id=str(near.get("id")) if near else None,
                    reason=reason,
                    mime_type=mime_str,
                    notes=notes,
                )
            )
            continue

        rule_id = str(rule.get("id") or "")
        publish_name = _publish_name(name, mime_str)
        matches = files_by_name.get(publish_name) or []
        if not matches:
            parent_id, dest_path = _folder_destination(rule, publish_name, payhoa_dirs)
            if parent_id is None or dest_path is None:
                skipped.append(
                    _row(
                        drive_id,
                        name,
                        folder_path,
                        rule_id=rule_id,
                        reason="PayHOA destination folder missing",
                        mime_type=mime_str,
                        notes=notes,
                    )
                )
            else:
                needs_publish.append(
                    _row(
                        drive_id,
                        name,
                        folder_path,
                        rule_id=rule_id,
                        payhoa_path=dest_path,
                        payhoa_parent_id=parent_id,
                        reason="missing from PayHOA",
                        mime_type=mime_str,
                        notes=notes,
                    )
                )
            continue

        parent_id, dest_path = _plan._destination(rule, publish_name, matches, payhoa_dirs)
        if parent_id is None or dest_path is None:
            skipped.append(
                _row(
                    drive_id,
                    name,
                    folder_path,
                    rule_id=rule_id,
                    reason="PayHOA destination folder missing",
                    mime_type=mime_str,
                    notes=notes,
                )
            )
            continue

        if _plan._already_at_path(matches, dest_path):
            matched.append(
                _row(
                    drive_id,
                    name,
                    folder_path,
                    rule_id=rule_id,
                    payhoa_path=dest_path,
                    payhoa_parent_id=parent_id,
                    mime_type=mime_str,
                    notes=notes,
                )
            )
            continue

        # Name exists (often Email Attachments only); library path preferred.
        would_create.append(
            _row(
                drive_id,
                name,
                folder_path,
                rule_id=rule_id,
                payhoa_path=dest_path,
                payhoa_parent_id=parent_id,
                mime_type=mime_str,
                notes=notes,
            )
        )

    matched.sort(key=lambda r: (r.drive_folder, r.drive_name, r.drive_file_id))
    would_create.sort(key=lambda r: (r.drive_folder, r.drive_name, r.drive_file_id))
    needs_publish.sort(key=lambda r: (r.drive_folder, r.drive_name, r.drive_file_id))
    skipped.sort(key=lambda r: (r.drive_folder, r.drive_name, r.drive_file_id))
    return DriveSyncReport(
        matched=matched,
        would_create=would_create,
        needs_publish=needs_publish,
        skipped_by_rule=skipped,
    )


def dry_run_sync_drive_documents(
    drive_files: Sequence[Mapping[str, Any]],
    payhoa_docs: Sequence[Mapping[str, Any]],
    *,
    rules: Mapping[str, Any] | None = None,
    rules_path: str | Path | None = None,
) -> DriveSyncReport:
    """Thin wrapper: load sync rules if needed, then compare. Never uploads."""
    loaded = rules if rules is not None else load_sync_rules(rules_path)
    return compare_drive_documents(drive_files, payhoa_docs, loaded)


def write_sync_plan(report: DriveSyncReport, dest: str | Path) -> Path:
    """Write plan.json (actions) and report.md (counts and lists). Does not upload."""
    folder = Path(dest)
    folder.mkdir(parents=True, exist_ok=True)
    plan = {
        "summary": {
            "matched": len(report.matched),
            "wouldCreate": len(report.would_create),
            "needsPublish": len(report.needs_publish),
            "skippedByRule": len(report.skipped_by_rule),
        },
        "byRule": report.counts_by_rule(),
        "skippedByReason": report.skipped_reasons(),
        "wouldCreate": [_plan_row(row) for row in report.would_create],
        "needsPublish": [_plan_row(row) for row in report.needs_publish],
    }
    (folder / "plan.json").write_text(
        json.dumps(plan, indent=2), encoding="utf-8"
    )
    (folder / "report.md").write_text(_report_markdown(report), encoding="utf-8")
    return folder


def _plan_row(row: DriveSyncRow) -> dict[str, Any]:
    return {
        "ruleId": row.rule_id,
        "driveFileId": row.drive_file_id,
        "driveName": row.drive_name,
        "driveFolder": row.drive_folder,
        "payhoaPath": row.payhoa_path,
        "payhoaParentId": row.payhoa_parent_id,
        "mimeType": row.mime_type,
        "reason": row.reason,
        "notes": list(row.notes),
    }


def _report_markdown(report: DriveSyncReport) -> str:
    lines = [
        "# Drive to PayHOA sync plan",
        "",
        "Dry run. Nothing was uploaded.",
        "",
        report.summary(),
        "",
        "## By rule",
        "",
        "| Rule | Matched | Would create | Needs publish | Skipped |",
        "|------|---------|--------------|---------------|---------|",
    ]
    for rule_id, counts in sorted(report.counts_by_rule().items()):
        lines.append(
            f"| {rule_id} | {counts['matched']} | {counts['would_create']} | "
            f"{counts['needs_publish']} | {counts['skipped_by_rule']} |"
        )
    lines.extend(["", "## Skipped reasons", ""])
    for reason, count in report.skipped_reasons().items():
        lines.append(f"- {count} {reason}")
    lines.extend(["", "## Would create", ""])
    lines.extend(_action_lines(report.would_create))
    lines.extend(["", "## Needs publish", ""])
    lines.extend(_action_lines(report.needs_publish))
    lines.append("")
    return "\n".join(lines)


def _action_lines(rows: Sequence[DriveSyncRow]) -> list[str]:
    if not rows:
        return ["None."]
    lines: list[str] = []
    for row in rows:
        note = f" ({row.notes[0]})" if row.notes else ""
        lines.append(
            f"- `{row.rule_id}` {row.drive_name} → `{row.payhoa_path}`{note}"
        )
    return lines


def _row(
    drive_file_id: str,
    drive_name: str,
    drive_folder: str,
    *,
    rule_id: str | None = None,
    payhoa_path: str | None = None,
    payhoa_parent_id: int | None = None,
    reason: str | None = None,
    mime_type: str | None = None,
    notes: tuple[str, ...] = (),
) -> DriveSyncRow:
    return DriveSyncRow(
        drive_file_id=drive_file_id,
        drive_name=drive_name,
        drive_folder=drive_folder,
        rule_id=rule_id,
        payhoa_path=payhoa_path,
        payhoa_parent_id=payhoa_parent_id,
        reason=reason,
        mime_type=mime_type,
        notes=notes,
    )


def _publish_name(name: str, mime_type: str | None) -> str:
    """PayHOA file name. A Google Doc or Word file is published as a PDF."""
    lower = name.lower()
    if mime_type == GOOGLE_DOC_MIME:
        return name if lower.endswith(".pdf") else f"{name}.pdf"
    if lower.endswith((".docx", ".doc")):
        return f"{name.rsplit('.', 1)[0]}.pdf"
    return name


def _folder_destination(
    rule: Mapping[str, Any],
    publish_name: str,
    payhoa_dirs: Mapping[str, Mapping[str, Any]],
) -> tuple[int | None, str | None]:
    raw = str(rule.get("payhoa") or "").strip()
    if not raw:
        return None, None
    prefix = _plan._norm_folder(raw[:-2] if raw.endswith("**") else raw)
    folder = payhoa_dirs.get(prefix)
    if folder is None or folder.get("id") is None:
        return None, None
    return int(folder["id"]), f"{prefix}/{publish_name}"


def _export_notes(mime_type: str | None) -> tuple[str, ...]:
    if mime_type == GOOGLE_DOC_MIME:
        return (_WATERMARK_NOTE,)
    return ()


def _excluded_reason(
    folder_path: str,
    item: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
    exclude_ids: set[str],
    exclude_folders: set[str],
    exclude_reason: Mapping[str, str],
) -> str | None:
    for ex in exclude_folders:
        if not ex:
            continue
        if folder_path == ex or folder_path.startswith(ex + "/"):
            detail = exclude_reason.get(ex) or ex
            return f"excluded: {ex} ({detail})"
    ancestors = _plan._ancestor_ids(item, by_id)
    hit = ancestors & exclude_ids
    if hit:
        aid = sorted(hit)[0]
        detail = exclude_reason.get(aid) or aid
        return f"excluded folder id {aid} ({detail})"
    return None


def _near_rule(
    rule_rows: Sequence[Mapping[str, Any]],
    item: Mapping[str, Any],
    by_id: Mapping[str, Mapping[str, Any]],
    folder_path: str,
) -> Mapping[str, Any] | None:
    """First rule whose Drive folder contains this file (glob may still fail)."""
    ancestors = _plan._ancestor_ids(item, by_id)
    for rule in rule_rows:
        drive_folder = _plan._norm_folder(str(rule.get("drive_folder") or ""))
        drive_id = str(rule.get("drive_id") or "")
        under = False
        if drive_id and drive_id in ancestors:
            under = True
        elif drive_folder and (
            folder_path == drive_folder or folder_path.startswith(drive_folder + "/")
        ):
            under = True
        if under:
            return rule
    return None


def _skip_reason_for_near_rule(
    rule: Mapping[str, Any], folder_path: str, name: str
) -> str:
    drive_folder = _plan._norm_folder(str(rule.get("drive_folder") or ""))
    rel = _plan._relative_folder(folder_path, drive_folder)
    rule_id = str(rule.get("id") or "")
    if rule_id == "insurance-current" and rel:
        from jason.community import community as active
        from jason.community.symbols import InsuranceVisit

        path = f"{drive_folder}/{rel}"
        if active().insurance().visit(path) is InsuranceVisit.YEAR_FOLDER:
            return "insurance-current: year folder, walk does not collect files"
        return "insurance-current: folder root only"
    if _plan._rule_excludes(rule, rel, name):
        return f"rule {rule_id} exclude"
    if not _plan._glob_match(str(rule.get("glob") or ""), name):
        return f"rule {rule_id}: name does not match glob"
    return f"rule {rule_id}: not selected"
