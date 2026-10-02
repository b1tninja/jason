"""Drive files matched to the email attachments they were saved from, by name and content."""

from __future__ import annotations

from jason.tasks.drive_gmail import build


def test_a_drive_copy_created_after_the_email_is_saved_from_it(tmp_path) -> None:
    (tmp_path / "drive").mkdir()
    files = [
        {"id": "d1", "name": "Bylaws.pdf", "path": "My Drive/Bylaws.pdf", "md5": "aaa", "created": "2026-08-02T14:42:32Z"},
        {"id": "d2", "name": "Bylaws.pdf", "path": "My Drive/Governing Documents/Bylaws.pdf", "md5": "aaa", "created": "2020-01-01T00:00:00Z"},
        {"id": "d3", "name": "Minutes.pdf", "path": "My Drive/Minutes.pdf", "md5": "ccc", "created": "2026-01-01T00:00:00Z"},
    ]
    cache = {
        "m1|Bylaws.pdf": {"messageId": "m1", "threadId": "t", "at": "2026-08-02T14:40:00+00:00", "name": "Bylaws.pdf", "md5": "aaa",
                          "bytes": 3, "sent": False, "from": "Title Co <orders@title.com>", "to": "", "subject": "Resale documents"},
        "m2|Minutes.pdf": {"messageId": "m2", "threadId": "t", "at": "2026-02-01T00:00:00+00:00", "name": "Minutes.pdf", "md5": "zzz",
                           "bytes": 3, "sent": True, "from": "sender.example@gmail.com", "to": "", "subject": "draft minutes"},
        "__searched__": {"names": ["Bylaws.pdf", "Minutes.pdf"]},
    }
    result = build(tmp_path, files, cache)
    links = {l["driveId"]: l for l in result["links"]}
    assert links["d1"]["savedFrom"] == "m1" and links["d1"]["messages"][0]["from"] == "title.com"
    assert links["d2"]["savedFrom"] is None
    assert "d3" not in links
    assert [a["name"] for a in result["sameNameDifferentContent"]] == ["Minutes.pdf"]
    assert result["sameNameDifferentContent"][0]["from"] == "personal"
