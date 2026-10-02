"""The Drive catalog: a Drive file takes its root's library path, is classified by the library's rules, and is found by content."""

from __future__ import annotations

import hashlib
import json

from jason.community import mystique
from jason.tasks.drive_catalog import holdings, library_path


def _file(path: str, md5: str = "", folder_ids: tuple[str, ...] = ()) -> dict:
    return {"id": path, "name": path.rsplit("/", 1)[-1], "path": path, "folderId": "", "folderIds": list(folder_ids),
            "mimeType": "application/pdf", "size": 1, "md5": md5, "modified": "2026-09-01T00:00:00Z", "owner": "me", "link": ""}


def test_a_file_under_a_drive_root_takes_the_library_path_of_its_folder() -> None:
    community = mystique()
    path, root = library_path(community, _file("My Drive/Meetings/2025/Minutes of 7_15_25.pdf"))
    assert root == "Meetings" and path == "Meetings/2025/Minutes of 7_15_25.pdf"
    assert library_path(community, _file("My Drive/The Helsing Group/Budget 2019.pdf")) == ("", "")


def test_holdings_find_duplicates_versions_and_copies_on_disk(tmp_path) -> None:
    content = b"%PDF minutes"
    md5 = hashlib.md5(content).hexdigest()
    files = [
        _file("My Drive/Meetings/2025/Minutes of 7_15_25.pdf", md5),
        _file("My Drive/Minutes of 7_15_25.pdf", md5),
        _file("My Drive/Financials/Budget.pdf", "aaa"),
        _file("My Drive/archive/Budget.pdf", "bbb"),
    ]
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps({"files": files}), encoding="utf-8")
    scan = tmp_path / "mail" / "1"
    scan.mkdir(parents=True)
    (scan / "letter.pdf").write_bytes(content)
    result = holdings(tmp_path, mystique())
    rows = {r["drivePath"]: r for r in result["rows"]}
    ruled = rows["My Drive/Meetings/2025/Minutes of 7_15_25.pdf"]
    assert ruled["pathRule"] and ruled["kind"] == "minutes" and "minutes" in ruled["records"]
    assert ruled["elsewhere"] == [{"channel": "paper mail scan", "where": "mail/1/letter.pdf"}]
    assert not rows["My Drive/Minutes of 7_15_25.pdf"]["pathRule"]
    [dup] = result["duplicatesInDrive"]
    assert len(dup["paths"]) == 2
    assert [v["name"] for v in result["versionsInDrive"]] == ["Budget.pdf"]
    assert result["records"]["minutes"]["outsideRules"] == ["My Drive/Minutes of 7_15_25.pdf"]
