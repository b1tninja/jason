"""Dry-run Drive → PayHOA document copy planner."""

from jason.tasks.sync_documents import PlannedCopy, plan_document_sync

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
            "reason": "no PayHOA name match",
        },
        {
            "drive_folder": "Governing Documents/Proposed",
            "drive_id": "drv-proposed",
            "reason": "drafts",
        },
        {
            "drive_folder": "Governing Documents/Applications",
            "drive_id": "drv-apps",
            "reason": "forms",
        },
        {
            "drive_folder": "Governing Documents/Policies/old",
            "drive_id": "drv-old",
            "reason": "superseded",
        },
        {
            "drive_folder": "Plans/John Laing Homes",
            "drive_id": "drv-jl",
            "reason": "no match",
        },
        {
            "drive_folder": "Plans/Watt Communities (New Buildings)",
            "drive_id": "drv-watt",
            "reason": "no match",
        },
    ],
}


def _drive(*rows):
    return list(rows)


def _payhoa(*rows):
    return list(rows)


def test_plans_copy_when_name_only_in_email_attachments():
    drive = _drive(
        {"id": "drv-ins", "name": "Insurance", "parents": []},
        {
            "id": "d1",
            "name": "Certificate of Insurance 2025.pdf",
            "parents": ["drv-ins"],
        },
    )
    payhoa = _payhoa(
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
    )
    planned = plan_document_sync(RULES, drive, payhoa)
    assert planned == [
        PlannedCopy(
            drive_file_id="d1",
            drive_name="Certificate of Insurance 2025.pdf",
            payhoa_parent_id=10,
            destination_path="Insurance/Certificate of Insurance 2025.pdf",
        )
    ]


def test_skips_when_same_name_already_at_destination():
    drive = _drive(
        {"id": "drv-ins", "name": "Insurance", "parents": []},
        {
            "id": "d1",
            "name": "Certificate of Insurance 2025.pdf",
            "parents": ["drv-ins"],
        },
    )
    payhoa = _payhoa(
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
    )
    assert plan_document_sync(RULES, drive, payhoa) == []


def test_skips_unmatched_drive_names():
    drive = _drive(
        {"id": "drv-gov", "name": "Governing Documents", "parents": []},
        {"id": "d1", "name": "Brand New Charter.pdf", "parents": ["drv-gov"]},
    )
    payhoa = _payhoa(
        {
            "id": 1,
            "parentId": None,
            "directory": True,
            "fileName": "Governing Documents",
            "path": "Governing Documents",
        }
    )
    assert plan_document_sync(RULES, drive, payhoa) == []


def test_skips_loose_root_files_even_with_name_match():
    drive = _drive(
        {"id": "loose", "name": "CCRs.pdf", "parents": []},
    )
    payhoa = _payhoa(
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
    )
    assert plan_document_sync(RULES, drive, payhoa) == []


def test_skips_excluded_drive_folders():
    drive = _drive(
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
    )
    payhoa = _payhoa(
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
        {
            "id": 3,
            "parentId": 1,
            "directory": True,
            "fileName": "Policies",
            "path": "Governing Documents/Policies",
        },
        {
            "id": 4,
            "parentId": 3,
            "directory": False,
            "fileName": "Assessment Collection Policy.pdf",
            "path": "Governing Documents/Policies/Assessment Collection Policy.pdf",
        },
    )
    assert plan_document_sync(RULES, drive, payhoa) == []


def test_skips_confidential_and_email_attachments_drive_roots():
    drive = _drive(
        {"id": "drv-conf", "name": "Confidential", "parents": []},
        {"id": "c1", "name": "CCRs.pdf", "parents": ["drv-conf"]},
        {"id": "drv-ea", "name": "Email Attachments", "parents": []},
        {"id": "e1", "name": "CCRs.pdf", "parents": ["drv-ea"]},
    )
    payhoa = _payhoa(
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
    )
    assert plan_document_sync(RULES, drive, payhoa) == []


def test_election_rules_go_to_elections_folder():
    drive = _drive(
        {"id": "drv-gov", "name": "Governing Documents", "parents": []},
        {"id": "d1", "name": "Election Rules.pdf", "parents": ["drv-gov"]},
    )
    payhoa = _payhoa(
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
    )
    planned = plan_document_sync(RULES, drive, payhoa)
    assert planned == [
        PlannedCopy(
            drive_file_id="d1",
            drive_name="Election Rules.pdf",
            payhoa_parent_id=50,
            destination_path="Elections/Election Rules.pdf",
        )
    ]


def test_grant_deeds_skips_when_already_under_grant_deeds_tree():
    drive = _drive(
        {"id": "drv-deeds", "name": "Deeds", "parents": []},
        {"id": "d1", "name": "GD 200605041076.pdf", "parents": ["drv-deeds"]},
    )
    payhoa = _payhoa(
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
    )
    assert plan_document_sync(RULES, drive, payhoa) == []


def test_grant_deeds_plans_into_root_when_only_email_match():
    drive = _drive(
        {"id": "drv-deeds", "name": "Deeds", "parents": []},
        {"id": "d1", "name": "GD 200605041076.pdf", "parents": ["drv-deeds"]},
    )
    payhoa = _payhoa(
        {
            "id": 20,
            "parentId": None,
            "directory": True,
            "fileName": "Grant Deeds",
            "path": "Grant Deeds",
        },
        {
            "id": 22,
            "parentId": 99,
            "directory": False,
            "fileName": "GD 200605041076.pdf",
            "path": "Email Attachments/GD 200605041076.pdf",
        },
    )
    planned = plan_document_sync(RULES, drive, payhoa)
    assert planned == [
        PlannedCopy(
            drive_file_id="d1",
            drive_name="GD 200605041076.pdf",
            payhoa_parent_id=20,
            destination_path="Grant Deeds/GD 200605041076.pdf",
        )
    ]


def test_insurance_ignores_year_subfolders():
    drive = _drive(
        {"id": "drv-ins", "name": "Insurance", "parents": []},
        {"id": "drv-2024", "name": "2024", "parents": ["drv-ins"]},
        {
            "id": "d1",
            "name": "FLOOD POLICY 25-26 BLDG 5.pdf",
            "parents": ["drv-2024"],
        },
    )
    payhoa = _payhoa(
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
    )
    assert plan_document_sync(RULES, drive, payhoa) == []


def test_policies_copy_into_policies_folder():
    drive = _drive(
        {"id": "drv-gov", "name": "Governing Documents", "parents": []},
        {"id": "drv-pol", "name": "Policies", "parents": ["drv-gov"]},
        {
            "id": "d1",
            "name": "Assessment Collection Policy.pdf",
            "parents": ["drv-pol"],
        },
    )
    payhoa = _payhoa(
        {
            "id": 1,
            "parentId": None,
            "directory": True,
            "fileName": "Governing Documents",
            "path": "Governing Documents",
        },
        {
            "id": 3,
            "parentId": 1,
            "directory": True,
            "fileName": "Policies",
            "path": "Governing Documents/Policies",
        },
        {
            "id": 4,
            "parentId": 99,
            "directory": False,
            "fileName": "Assessment Collection Policy.pdf",
            "path": "Email Attachments/Assessment Collection Policy.pdf",
        },
    )
    planned = plan_document_sync(RULES, drive, payhoa)
    assert planned == [
        PlannedCopy(
            drive_file_id="d1",
            drive_name="Assessment Collection Policy.pdf",
            payhoa_parent_id=3,
            destination_path="Governing Documents/Policies/Assessment Collection Policy.pdf",
        )
    ]
