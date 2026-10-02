"""Dry-run Drive ↔ PayHOA document compare (no network)."""

import json

from jason.tasks.sync_drive_documents import (
    GOOGLE_DOC_MIME,
    DriveSyncReport,
    DriveSyncRow,
    compare_drive_documents,
    dry_run_sync_drive_documents,
    list_rule_drive_files,
    write_sync_plan,
)

RULES = {
    "rules": [
        {
            "id": "governing-root",
            "drive_folder": "Governing Documents",
            "drive_id": "drv-gov",
            "glob": "{CCRs*,Bylaws*,Articles of Incorporation.pdf,Owner's Manual*}",
            "payhoa": "Governing Documents/",
            "mode": "name-match",
        },
        {
            "id": "election-rules",
            "drive_folder": "Governing Documents",
            "drive_id": "drv-gov",
            "glob": "Election Rules*",
            "payhoa": "Elections/",
            "mode": "name-match",
        },
        {
            "id": "policies",
            "drive_folder": "Governing Documents/Policies",
            "drive_id": "drv-pol",
            "glob": "*",
            "exclude": ["old/**"],
            "payhoa": "Governing Documents/Policies/",
            "mode": "name-match",
        },
        {
            "id": "grant-deeds",
            "drive_folder": "Deeds",
            "drive_id": "drv-deeds",
            "glob": "GD *",
            "payhoa": "Grant Deeds/**",
            "mode": "name-match",
        },
        {
            "id": "insurance-current",
            "drive_folder": "Insurance",
            "drive_id": "drv-ins",
            "glob": "{FLOOD POLICY *,Certificate of Insurance*}",
            "payhoa": "Insurance/",
            "mode": "name-match",
            "also_seen_in": "Email Attachments/",
        },
    ],
    "exclude": [
        {
            "drive_folder": "Governing Documents/Audio Book",
            "drive_id": "drv-audio",
            "reason": "about 2049 audio files, no PayHOA name match",
        },
        {
            "drive_folder": "Governing Documents/Proposed",
            "drive_id": "drv-proposed",
            "reason": "drafts, not in PayHOA",
        },
        {
            "drive_folder": "Governing Documents/Applications",
            "drive_id": "drv-apps",
            "reason": "parking permit forms",
        },
        {
            "drive_folder": "Governing Documents/Policies/old",
            "drive_id": "drv-old",
            "reason": "superseded policies",
        },
        {
            "drive_folder": "Plans/John Laing Homes",
            "drive_id": "drv-jl",
            "reason": "about 150 files, no PayHOA name match",
        },
        {
            "drive_folder": "Plans/Watt Communities (New Buildings)",
            "drive_id": "drv-watt",
            "reason": "no PayHOA name match",
        },
        {
            "drive_folder": "Insurance/2021",
            "drive_id": "drv-ins-2021",
            "reason": "no PayHOA name match",
        },
        {
            "drive_folder": "Insurance/2022",
            "drive_id": "drv-ins-2022",
            "reason": "no PayHOA name match",
        },
        {
            "drive_folder": "Insurance/2023",
            "drive_id": "drv-ins-2023",
            "reason": "no PayHOA name match",
        },
    ],
}


def test_matched_when_library_path_already_has_name():
    drive = [
        {"id": "drv-ins", "name": "Insurance", "parents": []},
        {
            "id": "d1",
            "name": "Certificate of Insurance 2025.pdf",
            "parents": ["drv-ins"],
            "mimeType": "application/pdf",
        },
    ]
    payhoa = [
        {
            "id": 10,
            "parentId": None,
            "directory": True,
            "fileName": "Insurance",
            "path": "Insurance",
        },
        {
            "id": 12,
            "parentId": 10,
            "directory": False,
            "fileName": "Certificate of Insurance 2025.pdf",
            "path": "Insurance/Certificate of Insurance 2025.pdf",
        },
        {
            "id": 11,
            "parentId": 99,
            "directory": False,
            "fileName": "Certificate of Insurance 2025.pdf",
            "path": "Email Attachments/Certificate of Insurance 2025.pdf",
        },
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    assert report.summary() == "matched=1 would_create=0 needs_publish=0 skipped_by_rule=0"
    row = report.matched[0]
    assert row.drive_file_id == "d1"
    assert row.rule_id == "insurance-current"
    assert row.payhoa_path == "Insurance/Certificate of Insurance 2025.pdf"
    assert row.payhoa_parent_id == 10


def test_would_create_prefers_library_over_email_attachments():
    drive = [
        {"id": "drv-ins", "name": "Insurance", "parents": []},
        {
            "id": "d1",
            "name": "Certificate of Insurance 2025.pdf",
            "parents": ["drv-ins"],
        },
    ]
    payhoa = [
        {
            "id": 10,
            "parentId": None,
            "directory": True,
            "fileName": "Insurance",
            "path": "Insurance",
        },
        {
            "id": 11,
            "parentId": 99,
            "directory": False,
            "fileName": "Certificate of Insurance 2025.pdf",
            "path": "Email Attachments/Certificate of Insurance 2025.pdf",
        },
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    assert len(report.would_create) == 1
    assert report.matched == []
    row = report.would_create[0]
    assert row.payhoa_path == "Insurance/Certificate of Insurance 2025.pdf"
    assert row.payhoa_parent_id == 10
    assert row.rule_id == "insurance-current"


def test_rule_match_missing_from_payhoa_needs_publish():
    drive = [
        {"id": "drv-gov", "name": "Governing Documents", "parents": []},
        {"id": "drv-pol", "name": "Policies", "parents": ["drv-gov"]},
        {
            "id": "alpr",
            "name": "ALPR Policy",
            "mimeType": GOOGLE_DOC_MIME,
            "parents": ["drv-pol"],
        },
    ]
    payhoa = [
        {
            "id": 10,
            "parentId": None,
            "directory": True,
            "fileName": "Governing Documents",
            "path": "Governing Documents",
        },
        {
            "id": 11,
            "parentId": 10,
            "directory": True,
            "fileName": "Policies",
            "path": "Governing Documents/Policies",
        },
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    assert report.would_create == []
    assert len(report.needs_publish) == 1
    row = report.needs_publish[0]
    assert row.drive_name == "ALPR Policy"
    assert row.payhoa_path == "Governing Documents/Policies/ALPR Policy.pdf"
    assert row.payhoa_parent_id == 11
    assert row.reason == "missing from PayHOA"


def test_unmatched_name_outside_glob_is_skipped():
    drive = [
        {"id": "drv-gov", "name": "Governing Documents", "parents": []},
        {"id": "d1", "name": "Notes.txt", "parents": ["drv-gov"]},
    ]
    payhoa = [
        {
            "id": 1,
            "parentId": None,
            "directory": True,
            "fileName": "Governing Documents",
            "path": "Governing Documents",
        }
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    assert report.would_create == []
    assert report.matched == []
    assert report.needs_publish == []
    assert len(report.skipped_by_rule) == 1
    assert report.skipped_by_rule[0].reason == "rule governing-root: name does not match glob"


def test_skips_loose_root_confidential_email_attachments():
    drive = [
        {"id": "loose", "name": "CCRs.pdf", "parents": []},
        {"id": "drv-conf", "name": "Confidential", "parents": []},
        {"id": "c1", "name": "CCRs.pdf", "parents": ["drv-conf"]},
        {"id": "drv-ea", "name": "Email Attachments", "parents": []},
        {"id": "e1", "name": "CCRs.pdf", "parents": ["drv-ea"]},
    ]
    payhoa = [
        {
            "id": 1,
            "parentId": None,
            "directory": True,
            "fileName": "Governing Documents",
            "path": "Governing Documents",
        },
        {
            "id": 2,
            "parentId": 1,
            "directory": False,
            "fileName": "CCRs.pdf",
            "path": "Governing Documents/CCRs.pdf",
        },
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    reasons = {r.drive_file_id: r.reason for r in report.skipped_by_rule}
    assert reasons["loose"] == "loose My Drive root"
    assert "Confidential" in reasons["c1"]
    assert "Email Attachments" in reasons["e1"]
    assert report.matched == []
    assert report.would_create == []


def test_skips_excluded_drive_folders():
    drive = [
        {"id": "drv-gov", "name": "Governing Documents", "parents": []},
        {"id": "drv-audio", "name": "Audio Book", "parents": ["drv-gov"]},
        {"id": "a1", "name": "track.mp3", "parents": ["drv-audio"]},
        {"id": "drv-proposed", "name": "Proposed", "parents": ["drv-gov"]},
        {"id": "p1", "name": "CCRs.pdf", "parents": ["drv-proposed"]},
        {"id": "drv-apps", "name": "Applications", "parents": ["drv-gov"]},
        {"id": "app1", "name": "CCRs.pdf", "parents": ["drv-apps"]},
        {"id": "drv-pol", "name": "Policies", "parents": ["drv-gov"]},
        {"id": "drv-old", "name": "old", "parents": ["drv-pol"]},
        {
            "id": "old1",
            "name": "Assessment Collection Policy.pdf",
            "parents": ["drv-old"],
        },
        {"id": "drv-plans", "name": "Plans", "parents": []},
        {"id": "drv-jl", "name": "John Laing Homes", "parents": ["drv-plans"]},
        {"id": "jl1", "name": "plan.pdf", "parents": ["drv-jl"]},
        {
            "id": "drv-watt",
            "name": "Watt Communities (New Buildings)",
            "parents": ["drv-plans"],
        },
        {"id": "w1", "name": "watt.pdf", "parents": ["drv-watt"]},
        {"id": "drv-ins", "name": "Insurance", "parents": []},
        {"id": "drv-ins-2021", "name": "2021", "parents": ["drv-ins"]},
        {
            "id": "i21",
            "name": "Certificate of Insurance.pdf",
            "parents": ["drv-ins-2021"],
        },
    ]
    payhoa = [
        {
            "id": 2,
            "parentId": 1,
            "directory": False,
            "fileName": "CCRs.pdf",
            "path": "Governing Documents/CCRs.pdf",
        },
        {
            "id": 4,
            "parentId": 3,
            "directory": False,
            "fileName": "Assessment Collection Policy.pdf",
            "path": "Governing Documents/Policies/Assessment Collection Policy.pdf",
        },
        {
            "id": 11,
            "parentId": 10,
            "directory": False,
            "fileName": "Certificate of Insurance.pdf",
            "path": "Insurance/Certificate of Insurance.pdf",
        },
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    assert report.matched == []
    assert report.would_create == []
    by_id = {r.drive_file_id: r.reason for r in report.skipped_by_rule}
    assert "Audio Book" in by_id["a1"]
    assert "Proposed" in by_id["p1"]
    assert "Applications" in by_id["app1"]
    assert "Policies/old" in by_id["old1"]
    assert "John Laing" in by_id["jl1"]
    assert "Watt" in by_id["w1"]
    assert "Insurance/2021" in by_id["i21"]


def test_insurance_year_subfolder_not_in_exclude_still_skipped():
    """A year folder is walked only as a folder. Files inside are not collected."""
    drive = [
        {"id": "drv-ins", "name": "Insurance", "parents": []},
        {"id": "drv-2024", "name": "2024", "parents": ["drv-ins"]},
        {
            "id": "d1",
            "name": "FLOOD POLICY 25-26 BLDG 5.pdf",
            "parents": ["drv-2024"],
        },
    ]
    payhoa = [
        {
            "id": 10,
            "parentId": None,
            "directory": True,
            "fileName": "Insurance",
            "path": "Insurance",
        },
        {
            "id": 11,
            "parentId": 99,
            "directory": False,
            "fileName": "FLOOD POLICY 25-26 BLDG 5.pdf",
            "path": "Email Attachments/FLOOD POLICY 25-26 BLDG 5.pdf",
        },
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    assert report.would_create == []
    assert report.skipped_by_rule[0].reason == "insurance-current: year folder, walk does not collect files"


def test_election_rules_would_create_into_elections():
    drive = [
        {"id": "drv-gov", "name": "Governing Documents", "parents": []},
        {"id": "d1", "name": "Election Rules.pdf", "parents": ["drv-gov"]},
    ]
    payhoa = [
        {
            "id": 50,
            "parentId": None,
            "directory": True,
            "fileName": "Elections",
            "path": "Elections",
        },
        {
            "id": 51,
            "parentId": 99,
            "directory": False,
            "fileName": "Election Rules.pdf",
            "path": "Email Attachments/Election Rules.pdf",
        },
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    assert len(report.would_create) == 1
    assert report.would_create[0].rule_id == "election-rules"
    assert report.would_create[0].payhoa_path == "Elections/Election Rules.pdf"


def test_grant_deeds_matched_under_common_areas():
    drive = [
        {"id": "drv-deeds", "name": "Deeds", "parents": []},
        {"id": "d1", "name": "GD 200605041076.pdf", "parents": ["drv-deeds"]},
    ]
    payhoa = [
        {
            "id": 20,
            "parentId": None,
            "directory": True,
            "fileName": "Grant Deeds",
            "path": "Grant Deeds",
        },
        {
            "id": 21,
            "parentId": 20,
            "directory": True,
            "fileName": "Common Areas",
            "path": "Grant Deeds/Common Areas",
        },
        {
            "id": 22,
            "parentId": 21,
            "directory": False,
            "fileName": "GD 200605041076.pdf",
            "path": "Grant Deeds/Common Areas/GD 200605041076.pdf",
        },
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    assert len(report.matched) == 1
    assert report.matched[0].payhoa_path.endswith("GD 200605041076.pdf")
    assert "Grant Deeds" in report.matched[0].payhoa_path


def test_google_doc_notes_watermark_on_would_create():
    drive = [
        {"id": "drv-gov", "name": "Governing Documents", "parents": []},
        {
            "id": "d1",
            "name": "Bylaws.pdf",
            "parents": ["drv-gov"],
            "mimeType": GOOGLE_DOC_MIME,
        },
    ]
    payhoa = [
        {
            "id": 1,
            "parentId": None,
            "directory": True,
            "fileName": "Governing Documents",
            "path": "Governing Documents",
        },
        {
            "id": 2,
            "parentId": 99,
            "directory": False,
            "fileName": "Bylaws.pdf",
            "path": "Email Attachments/Bylaws.pdf",
        },
    ]
    report = compare_drive_documents(drive, payhoa, RULES)
    assert len(report.would_create) == 1
    assert report.would_create[0].mime_type == GOOGLE_DOC_MIME
    assert any("watermark" in n for n in report.would_create[0].notes)


def test_wrapper_accepts_rules_dict():
    drive = [
        {"id": "drv-gov", "name": "Governing Documents", "parents": []},
        {"id": "d1", "name": "CCRs.pdf", "parents": ["drv-gov"]},
    ]
    payhoa = [
        {
            "id": 1,
            "parentId": None,
            "directory": True,
            "fileName": "Governing Documents",
            "path": "Governing Documents",
        },
        {
            "id": 2,
            "parentId": 1,
            "directory": False,
            "fileName": "CCRs.pdf",
            "path": "Governing Documents/CCRs.pdf",
        },
    ]
    report = dry_run_sync_drive_documents(drive, payhoa, rules=RULES)
    assert report.matched[0].drive_name == "CCRs.pdf"
    assert report.summary().startswith("matched=1")


class _Drive:
    def __init__(self) -> None:
        self.files = {
            "drv-gov": {"id": "drv-gov", "name": "Governing Documents"},
            "skip-me": {"id": "skip-me", "name": "Audio Book"},
            "doc": {"id": "doc", "name": "CCRs.pdf"},
        }
        self.children = {
            "drv-gov": [self.files["skip-me"], self.files["doc"]],
        }

    def get_file(self, file_id: str) -> dict:
        return self.files[file_id]

    def list_folder(self, folder_id: str) -> list[dict]:
        return list(self.children.get(folder_id, []))


def test_list_rule_drive_files_skips_excluded_ids():
    rules = {
        "rules": [{"drive_id": "drv-gov"}],
        "exclude": [{"drive_id": "skip-me"}],
    }
    rows = list_rule_drive_files(_Drive(), rules)
    assert [row["id"] for row in rows] == ["drv-gov", "doc"]


def test_write_sync_plan_groups_actions(tmp_path):
    report = DriveSyncReport(
        matched=[DriveSyncRow("m", "Ethics Policy.pdf", "Policies", rule_id="policies")],
        would_create=[
            DriveSyncRow(
                "c",
                "Certificate of Insurance.pdf",
                "Insurance",
                rule_id="insurance-current",
                payhoa_path="Insurance/Certificate of Insurance.pdf",
                payhoa_parent_id=5,
            )
        ],
        needs_publish=[
            DriveSyncRow(
                "a",
                "ALPR Policy",
                "Policies",
                rule_id="policies",
                payhoa_path="Governing Documents/Policies/ALPR Policy.pdf",
                payhoa_parent_id=11,
                mime_type=GOOGLE_DOC_MIME,
                notes=("watermark stays",),
            )
        ],
        skipped_by_rule=[
            DriveSyncRow("s", "Notes.txt", "Governing Documents", reason="name does not match glob")
        ],
    )
    folder = write_sync_plan(report, tmp_path / "sync-plan")
    plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
    text = (folder / "report.md").read_text(encoding="utf-8")
    assert plan["summary"]["needsPublish"] == 1
    assert plan["needsPublish"][0]["driveName"] == "ALPR Policy"
    assert plan["byRule"]["policies"]["matched"] == 1
    assert plan["byRule"]["policies"]["needs_publish"] == 1
    assert "ALPR Policy" in text
    assert "watermark stays" in text
