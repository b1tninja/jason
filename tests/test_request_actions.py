from pathlib import Path

import pytest

from jason.tasks.request_actions import attach_to_request, comment_on_request, note_on_request


class _Writer:
    def __init__(self) -> None:
        self.comments: list[tuple] = []
        self.notes: list[tuple] = []
        self.files: list[tuple] = []

    def get_form_submission(self, org_id, submission_id):
        return {
            "submission": {
                "membershipId": 800001,
                "unit": {"owners": [{"membershipId": 800001}, {"membershipId": 100}]},
            }
        }

    def add_submission_comment(self, submission_id, message, *, notify_admins=False, recipient_member_ids=None):
        self.comments.append((submission_id, message, notify_admins, list(recipient_member_ids or [])))
        return []

    def add_submission_note(self, org_id, submission_id, note, *, private=True, recipient_member_ids=None):
        self.notes.append((org_id, submission_id, note, private))
        return {"id": 1, "private": private, "note": note}

    def attach_request_file(self, submission_id, path, *, notify=False, filename=None, content_type="application/octet-stream"):
        self.files.append((submission_id, Path(path).name, notify, content_type))
        return {"id": 9, "fileName": Path(path).name}


def test_comment_note_and_attachment_use_the_request_id(tmp_path: Path):
    client = _Writer()
    photo = tmp_path / "gutter.jpg"
    photo.write_bytes(b"jpg")
    comment_on_request(client, 27889, 260564, "  This is an example.  ")
    note_on_request(client, 27889, 260564, "internal")
    saved = attach_to_request(client, 260564, photo)
    assert client.comments == [(260564, "This is an example.", False, [800001, 100])]
    assert client.notes == [(27889, 260564, "internal", True)]
    assert client.files == [(260564, "gutter.jpg", False, "image/jpeg")]
    assert saved["id"] == 9


def test_empty_comment_and_note_are_refused():
    client = _Writer()
    with pytest.raises(ValueError):
        comment_on_request(client, 27889, 260564, "  ")
    with pytest.raises(ValueError):
        note_on_request(client, 27889, 260564, "")
