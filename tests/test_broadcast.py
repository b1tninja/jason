"""A broadcast drafted on disk: its checks, its attachments against the catalog, and the admin's own membership."""

from jason.commands.broadcast import _upload_spec
from jason.community import mystique
from jason.community.library import LibraryDocument
from jason.community.symbols import PayhoaFolder
from jason.tasks.broadcast import body_of, check, own_membership, preview_page, resolve_attachments

GOOD = '<p>Dear <span class="placeholder">{first name}</span>,</p><p><a href="https://www.eoidirect.com/">EOI</a></p>'

LIBRARY = (
    LibraryDocument("payhoa", "2084291", "Email Attachments/How to obtain custom Evidence of Insurance.pdf",
                    "How to obtain custom Evidence of Insurance.pdf", "Email Attachments/", public=False),
    LibraryDocument("payhoa", "1440273", "Insurance/Assessors Parcel Map.pdf", "Assessors Parcel Map.pdf", "Insurance/", public=True),
    LibraryDocument("payhoa", "2084292", "Email Attachments/Assessors Parcel Map.pdf", "Assessors Parcel Map.pdf",
                    "Email Attachments/", public=False),
)


def test_a_clean_body_passes():
    found = check(GOOD, "Notice")
    assert found.placeholders == ["first name"]
    assert found.links == ["https://www.eoidirect.com/"]
    assert found.problems == []


def test_problems_are_named():
    found = check('<p>Hi {first name}</p><p><span class="placeholder">{unit number}</span></p><a href="eoidirect.com">x</a>', "")
    text = " ".join(found.problems)
    assert "no subject" in text
    assert "{first name}" in text           # bare: not wrapped as the composer wraps it
    assert "unit number" in text            # a placeholder the capture never showed
    assert "eoidirect.com" in text          # not an http(s) link


def test_body_of_a_full_page_is_its_body():
    assert body_of(f"<html><body>\n{GOOD}\n</body></html>") == GOOD
    assert body_of(GOOD) == GOOD


def test_attachments_resolve_by_id_path_or_unique_name():
    got = resolve_attachments(["2084291", "Email Attachments/Assessors Parcel Map.pdf",
                               "How to obtain custom Evidence of Insurance.pdf", "Assessors Parcel Map.pdf", "nope.pdf"],
                              LIBRARY)
    assert [a.id for a in got] == [2084291, 2084292, 2084291, None, None]   # a name in two folders is a miss


def test_own_membership_is_found_by_user_id():
    people = [{"id": 825656, "userId": 1}, {"id": 800001, "userId": 801670}]
    assert own_membership(people, 801670) == 800001
    assert own_membership(people, 5) is None
    assert own_membership(people, None) is None


def test_upload_spec_names_the_library_copy():
    assert _upload_spec(r"D:\x\COI - 26-27_9-30-2026.pdf=Certificate of Insurance 2026-2027.pdf")[1] == \
        "Certificate of Insurance 2026-2027.pdf"
    assert _upload_spec("a/b.pdf")[1] == "b.pdf"


def test_preview_page_escapes_the_frame_but_keeps_the_rendered_body():
    page = preview_page("A & B", "board@example.org", GOOD, resolve_attachments(["2084291"], LIBRARY), check(GOOD, "A & B"))
    assert "A &amp; B" in page and GOOD in page and "#2084291" in page


def test_email_attachments_folder_is_in_the_specification():
    folder = mystique().library_folder(PayhoaFolder.EMAIL_ATTACHMENTS)
    assert folder.path == "Email Attachments/" and folder.payhoa_id == 1101044


UNITS = [
    {"id": 1, "title": "1 A ST", "tags": [{"tag": "Building 3"}, {"tag": "Rental"}],
     "owners": [{"membershipId": 10}, {"membershipId": 11, "hasInvalidEmailAddress": True}]},
    {"id": 2, "title": "2 A ST", "tags": [{"tag": "Building 3"}], "owners": [{"membershipId": 12, "deletedAt": "2025-01-01"}]},
    {"id": 3, "title": "3 B ST", "tags": [{"tag": "Building 6"}], "owners": [{"membershipId": 13}]},
]
PEOPLE = [{"id": 13, "email": "x@example.org", "tags": [{"tag": "Board Member"}]},
          {"id": 20, "email": "", "tags": [{"tag": "Board Member"}]}]


def test_unit_tags_resolve_to_current_owners():
    from jason.tasks.broadcast import recipients, unit_tags

    assert unit_tags(UNITS) == {"Building 3": 2, "Building 6": 1, "Rental": 1}
    found = recipients(UNITS, PEOPLE, tags=["building 3"])
    assert found.unit_ids == [1, 2]
    assert found.membership_ids == [10, 11]                 # the sold unit's former owner is left out
    assert found.invalid_email == [11]
    assert found.other_tags == {"Rental": 1}


def test_member_tags_add_to_unit_tags_and_unknown_tags_are_named():
    from jason.tasks.broadcast import recipients

    found = recipients(UNITS, PEOPLE, tags=["Building 6"], member_tags=["Board Member", "Treasurer"])
    assert found.membership_ids == [13, 20]                 # one member through both, counted once
    assert found.invalid_email == [20]
    assert found.unknown_tags == ["Treasurer"]
