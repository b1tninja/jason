"""Write open requests to a new Google Sheet, one tab per kind.

The kind, the vendor, and the issue of each request are the specification's (``Community.request_groups()``, one
``RequestGroup`` a request); a request with no row is listed as unclear with its own message. Rows on a tab sit
together by vendor. Owner mail that does not match the unit is marked, because that usually means a tenant lives there.
A resident is a person on the request who is not one of the unit's owners. Photo columns use an IMAGE formula. The
picture is a resized copy in Drive, shared so anyone with the link can fetch it, because Sheets loads photos without
the viewer's sign-in. A PayHOA link does not display.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

from jason.catalog import PayhoaCatalog, person_name
from jason.community.request_forms import RequestGroup, RequestKind
from jason.tasks.export_requests import email_image

TABS = ("Association", "Homeowner", "Unclear", "Not a repair")
_TAB_FOR = {
    RequestKind.ASSOCIATION: "Association",
    RequestKind.HOMEOWNER: "Homeowner",
    RequestKind.UNCLEAR: "Unclear",
    RequestKind.NOT_MAINTENANCE: "Not a repair",
}
_UNSORTED = RequestGroup(0, RequestKind.UNCLEAR, "Unclear")      # a request the specification has no row for


def _community(community: Any) -> Any:
    """``community``, else the active profile (read when asked for, never at import)."""
    if community is not None:
        return community
    from jason.community import community as active

    return active()


HEADER = (
    "Vendor",
    "Request",
    "Created",
    "Unit",
    "Title",
    "Issue",
    "Form",
    "Status",
    "Owner",
    "Owner email",
    "Owner phone",
    "Owner mailing",
    "Owner mail is not the unit",
    "Resident",
    "Resident email",
    "Resident phone",
    "Photo 1",
    "Photo 2",
    "Photo 3",
    "Files",
)


class _Sheets(Protocol):
    def create(self, title: str, *, sheet_titles: tuple[str, ...] | None = None) -> dict[str, Any]: ...

    def get(
        self,
        spreadsheet_id: str,
        *,
        ranges: list[str] | None = None,
        include_grid: bool = False,
        fields: str | None = None,
    ) -> dict[str, Any]: ...

    def values_get(self, spreadsheet_id: str, range_a1: str) -> dict[str, Any]: ...

    def values_update(self, spreadsheet_id: str, range_a1: str, rows: list[list[Any]]) -> dict[str, Any]: ...

    def batch_update(self, spreadsheet_id: str, requests: list[dict[str, Any]]) -> dict[str, Any]: ...


@dataclass
class RequestSheet:
    spreadsheet_id: str
    url: str
    tabs: dict[str, int]

    def summary(self) -> str:
        counts = " ".join(f"{name}={count}" for name, count in self.tabs.items())
        return f"spreadsheet={self.spreadsheet_id} {counts} url={self.url}"


def image_formula(file_id: str) -> str:
    """A formula Sheets can fetch. The Drive file must be readable by link."""
    return f'=IMAGE("https://lh3.googleusercontent.com/d/{file_id}")'


def request_image_paths(folder: Path, names: list[str]) -> list[Path]:
    """Image files for one request, preferring the names already on the sheet."""
    if not folder.is_dir():
        return []
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES
    ]
    chosen: list[Path] = []
    for name in names:
        if not name or str(name).startswith("="):
            continue
        match = next(
            (
                path
                for path in files
                if path.name == name or path.name.endswith("_" + name)
            ),
            None,
        )
        if match is not None and match not in chosen:
            chosen.append(match)
    wanted = [name for name in names if name and not str(name).startswith("=")]
    if wanted:
        return chosen[:3]
    return sorted(files, key=lambda path: path.name)[:3]


def embed_sheet_photos(
    sheets: _Sheets,
    drive: Any,
    spreadsheet_id: str,
    files_dir: Path,
    *,
    community: Any = None,
) -> int:
    """Upload resized photos and write IMAGE formulas into an existing sheet. The pictures go to a Drive folder named
    for the association (``Community.short_name``)."""
    folder_id = _photo_folder(drive, f"{_community(community).short_name} request photos")
    image_root = files_dir.parent.parent / "payhoa-requests-images"
    uploaded = 0
    meta = sheets.get(spreadsheet_id, fields="sheets.properties")
    height: list[dict[str, Any]] = []
    for sheet in meta.get("sheets") or []:
        props = sheet.get("properties") if isinstance(sheet, dict) else None
        if not isinstance(props, dict):
            continue
        title = str(props.get("title") or "")
        if title not in TABS:
            continue
        body = sheets.values_get(spreadsheet_id, f"'{title}'!A2:S80")
        rows = body.get("values") or []
        photo_rows: list[list[str]] = []
        for row in rows:
            padded = list(row) + [""] * (19 - len(row))
            names = [str(cell) for cell in padded[16:19]]
            request_id = str(padded[1]).strip()
            folder = files_dir / request_id
            formulas: list[str] = []
            for name in names:
                if name.startswith("=IMAGE("):
                    formulas.append(name)
                    continue
                if not name:
                    formulas.append("")
                    continue
                paths = request_image_paths(folder, [name])
                if not paths:
                    formulas.append(name)
                    continue
                jpeg = email_image(
                    paths[0], image_root / request_id / f"{paths[0].stem}.jpg"
                )
                file_id = drive.upload_bytes(
                    jpeg.name,
                    jpeg.read_bytes(),
                    mime_type="image/jpeg",
                    parent_id=folder_id,
                )
                drive.share_with_link(file_id)
                formulas.append(image_formula(file_id))
                uploaded += 1
            photo_rows.append(formulas)
        if photo_rows:
            sheets.values_update(spreadsheet_id, f"'{title}'!Q2", photo_rows)
        sheet_id = props.get("sheetId")
        if sheet_id is not None and rows:
            height.append(
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": 1,
                            "endIndex": 1 + len(rows),
                        },
                        "properties": {"pixelSize": 180},
                        "fields": "pixelSize",
                    }
                }
            )
    if height:
        sheets.batch_update(spreadsheet_id, height)
    return uploaded


def _photo_folder(drive: Any, name: str) -> str:
    """The id of the Drive folder called ``name``, made when there is none."""
    rows = drive.list_files(
        f"name = '{name}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    if rows:
        return str(rows[0]["id"])
    return str(drive.create_folder(name))


def attachment_columns(items: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """Image URLs for the first three photos, and every file name."""
    urls: list[str] = []
    labels: list[str] = []
    for item in items:
        name = str(item.get("fileName") or item.get("name") or "").strip() or "file"
        labels.append(name)
        url = str(item.get("downloadUrl") or "").strip()
        kind = str(item.get("fileType") or item.get("contentType") or "").lower()
        image = Path(name).suffix.lower() in _IMAGE_SUFFIXES or kind.startswith("image/")
        if image and url:
            urls.append(url)
    return urls[:3], labels


def request_sheet_tabs(
    catalog: PayhoaCatalog,
    org_id: int,
    *,
    statuses: tuple[str, ...] = ("pending",),
    files: dict[int, list[str]] | None = None,
    photos: dict[int, list[str]] | None = None,
    community: Any = None,
) -> dict[str, list[list[Any]]]:
    """Rows for each kind tab, vendors kept together, newest first inside a vendor. The kind, vendor, and issue of a
    request are its ``RequestGroup`` row in the specification (``community``, else the active profile)."""
    photos = photos or {}
    people = _people(catalog, org_id)
    units = _units(catalog, org_id)
    groups = {int(group.request_id): group for group in _community(community).request_groups()}
    grouped: dict[str, list[tuple[str, str, list[Any]]]] = {name: [] for name in TABS}
    names = files or {}
    for row in catalog.search_requests(org_id, statuses=statuses, include_raw=True, limit=None):
        request_id = int(row["id"])
        group = groups.get(request_id, _UNSORTED)
        vendor, issue = group.vendor, group.issue
        tab = _TAB_FOR.get(group.kind, "Unclear")
        raw = _parse(row.get("raw_json"))
        title = _answer(raw, "Title") or str(row.get("title") or "")
        if not issue:
            issue = _answer(raw, "Message")
        unit_id = row.get("unit_id")
        unit = units.get(int(unit_id)) if unit_id is not None else None
        owners, resident, offsite = _contacts(unit, people, raw.get("membershipId"))
        created = str(row.get("created_at") or "")
        if "T" in created:
            created = created.split("T", 1)[0]
        labels = names.get(request_id) or []
        pictures = photos.get(request_id) or [
            label
            for label in labels
            if Path(label).suffix.lower() in _IMAGE_SUFFIXES
        ]
        values = [
            vendor,
            request_id,
            created,
            _unit_line(unit, raw),
            title,
            issue,
            str(row.get("form_name") or ""),
            str(row.get("status") or ""),
            owners["name"],
            owners["email"],
            owners["phone"],
            owners["mail"],
            "yes" if offsite else "",
            resident["name"],
            resident["email"],
            resident["phone"],
            pictures[0] if len(pictures) > 0 else "",
            pictures[1] if len(pictures) > 1 else "",
            pictures[2] if len(pictures) > 2 else "",
            "\n".join(labels),
        ]
        grouped[tab].append((vendor, created, values))
    tables: dict[str, list[list[Any]]] = {}
    for name in TABS:
        buckets: dict[str, list[tuple[str, list[Any]]]] = {}
        for vendor, created, values in grouped[name]:
            buckets.setdefault(vendor, []).append((created, values))
        body: list[list[Any]] = [list(HEADER)]
        for vendor in sorted(buckets):
            for _created, values in sorted(buckets[vendor], key=lambda item: item[0], reverse=True):
                body.append(values)
        tables[name] = body
    return tables


def write_request_sheet(
    sheets: _Sheets, title: str, tables: dict[str, list[list[Any]]]
) -> RequestSheet:
    """Create a spreadsheet and write one tab per kind. Does not edit an existing file."""
    names = tuple(name for name in TABS if name in tables)
    created = sheets.create(title, sheet_titles=names)
    spreadsheet_id = str(created.get("spreadsheetId") or "")
    if not spreadsheet_id:
        raise ValueError("spreadsheet was not created")
    counts: dict[str, int] = {}
    height: list[dict[str, Any]] = []
    for sheet in created.get("sheets") or []:
        props = sheet.get("properties") if isinstance(sheet, dict) else None
        if not isinstance(props, dict):
            continue
        name = str(props.get("title") or "")
        sheet_id = props.get("sheetId")
        rows = tables.get(name) or [list(HEADER)]
        sheets.values_update(spreadsheet_id, f"'{name}'!A1", rows)
        counts[name] = max(0, len(rows) - 1)
        if sheet_id is None:
            continue
        height.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
                    "fields": "gridProperties.frozenRowCount",
                }
            }
        )
        if len(rows) > 1:
            height.append(
                {
                    "updateDimensionProperties": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": 1,
                            "endIndex": len(rows),
                        },
                        "properties": {"pixelSize": 120},
                        "fields": "pixelSize",
                    }
                }
            )
    if height:
        sheets.batch_update(spreadsheet_id, height)
    return RequestSheet(
        spreadsheet_id=spreadsheet_id,
        url=f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
        tabs=counts,
    )


def _contacts(
    unit: dict[str, Any] | None,
    people: dict[int, dict[str, Any]],
    reporter_id: Any,
) -> tuple[dict[str, str], dict[str, str], bool]:
    owners: list[dict[str, str]] = []
    owner_ids: list[int] = []
    offsite = False
    unit_line = _unit_line(unit, {})
    for owner in (unit or {}).get("owners") or []:
        if not isinstance(owner, dict) or owner.get("membershipId") is None:
            continue
        membership_id = int(owner["membershipId"])
        owner_ids.append(membership_id)
        card = _card(people.get(membership_id))
        mail_line = card["mail"].split(",")[0]
        if _offsite(mail_line, unit_line):
            offsite = True
            card["mail"] = card["mail"] + " (not the unit)"
        owners.append(card)
    resident = {"name": "", "email": "", "phone": "", "mail": ""}
    if reporter_id is not None and int(reporter_id) not in owner_ids:
        resident = _card(people.get(int(reporter_id)))
    elif offsite:
        resident = {
            "name": "No separate resident is in the catalog",
            "email": "",
            "phone": "",
            "mail": "",
        }
    return _merge(owners), resident, offsite


def _card(person: dict[str, Any] | None) -> dict[str, str]:
    if not person:
        return {"name": "", "email": "", "phone": "", "mail": ""}
    profile = person.get("profile") if isinstance(person.get("profile"), dict) else {}
    user = person.get("user") if isinstance(person.get("user"), dict) else {}
    mail = ", ".join(
        part
        for part in (
            str(profile.get("address1") or "").strip(),
            str(profile.get("city") or "").strip(),
            str(profile.get("state") or "").strip(),
            str(profile.get("zip") or "").strip(),
        )
        if part
    )
    return {
        "name": person_name(person),
        "email": str(person.get("email") or user.get("email") or "").strip(),
        "phone": str(profile.get("phone") or "").strip(),
        "mail": mail,
    }


def _merge(cards: list[dict[str, str]]) -> dict[str, str]:
    merged = {"name": "", "email": "", "phone": "", "mail": ""}
    for key in merged:
        merged[key] = "\n".join(card[key] for card in cards if card.get(key))
    return merged


def _offsite(mailing: str, unit_line: str) -> bool:
    mail = " ".join(mailing.upper().split())
    unit = " ".join(unit_line.upper().split())
    if not mail or not unit:
        return False
    return not (mail.startswith(unit) or unit.startswith(mail))


def _unit_line(unit: dict[str, Any] | None, raw: dict[str, Any]) -> str:
    if unit:
        line = str(unit.get("streetAddress") or unit.get("title") or "").strip()
        if line:
            return line
    nested = raw.get("unit") if isinstance(raw.get("unit"), dict) else {}
    return str(nested.get("streetAddress") or nested.get("title") or "").strip()


def _answer(raw: dict[str, Any], label: str) -> str:
    wanted = label.lower()
    for item in raw.get("answers") or []:
        if not isinstance(item, dict):
            continue
        question = item.get("question") if isinstance(item.get("question"), dict) else {}
        if str(question.get("label") or "").lower() != wanted:
            continue
        return " ".join(str(item.get("answer") or "").split())
    return ""


def _people(catalog: PayhoaCatalog, org_id: int) -> dict[int, dict[str, Any]]:
    rows = catalog._conn.execute(
        "SELECT id, raw_json FROM people WHERE org_id = ?",
        (org_id,),
    ).fetchall()
    found: dict[int, dict[str, Any]] = {}
    for row in rows:
        found[int(row["id"])] = _parse(row["raw_json"])
    return found


def _units(catalog: PayhoaCatalog, org_id: int) -> dict[int, dict[str, Any]]:
    rows = catalog._conn.execute(
        "SELECT id, raw_json FROM units WHERE org_id = ?",
        (org_id,),
    ).fetchall()
    found: dict[int, dict[str, Any]] = {}
    for row in rows:
        found[int(row["id"])] = _parse(row["raw_json"])
    return found


def _parse(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
