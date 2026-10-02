"""The board from PayHOA's "Board Member" tag: current and archived, with names from the profile or the detail."""

from __future__ import annotations

from jason.tasks import board_members


class FakePayhoa:
    def __init__(self):
        self.details = []

    def iter_people(self, org_id, per_page=100, status="active"):
        tag = [{"tag": "Board Member", "taggableId": 0}]
        if status == "active":
            yield {"id": 1, "email": "a@x.org", "isAdmin": True, "lastLogin": "2026-09-30T01:00:00Z", "tags": tag,
                   "profile": {"givenNames": "Pat", "familyName": "Lee"}}
            yield {"id": 2, "email": "b@x.org", "tags": [{"tag": "Never Logged In"}], "profile": {}}
        else:
            yield {"id": 3, "email": "", "tags": tag, "profile": {}, "archivedAt": "2025-02-01T00:00:00Z"}

    def get_member(self, org_id, membership_id):
        self.details.append(membership_id)
        return {"profile": {"givenNames": "Sam", "familyName": "Ruiz"}}


def test_the_tagged_members_are_the_board_and_an_archived_one_a_former_director(tmp_path) -> None:
    client = FakePayhoa()
    result = board_members.sync(client, 27889, tmp_path)
    assert [m["name"] for m in result["current"]] == ["Pat Lee"] and result["current"][0]["admin"]
    assert [m["name"] for m in result["former"]] == ["Sam Ruiz"] and client.details == [3]
    assert board_members.current_names(tmp_path) == ["Pat Lee"]
