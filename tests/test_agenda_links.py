"""Agenda links: chips and hyperlinks under their items, link kinds, Drive ids, and the index by file."""

from __future__ import annotations

import json

import pytest

from jason.community import mystique
from jason.community.agenda_links import LinkKind, drive_id, link_kind, links_in_doc

M = mystique()


def _para(style: str, *elements: dict) -> dict:
    return {"paragraph": {"paragraphStyle": {"namedStyleType": style}, "elements": list(elements)}}


def _text(t: str, url: str = "") -> dict:
    return {"textRun": {"content": t, "textStyle": {"link": {"url": url}} if url else {}}}


def _chip(title: str, uri: str, mime: str = "application/pdf") -> dict:
    return {"richLink": {"richLinkProperties": {"title": title, "uri": uri, "mimeType": mime}}}


DOC = {"title": "Agenda for 7/7/26", "tabs": [{"documentTab": {"body": {"content": [
    {"table": {"tableRows": [{"tableCells": [{"content": [_para("NORMAL_TEXT", _text("Join via Zoom", "https://us06web.zoom.us/j/1"))]}]}]}},
    _para("HEADING_4", _text("Review all open maintenance requests")),
    _para("HEADING_5", _text("Garage door, building 2 ")),
    _para("NORMAL_TEXT", _text("📷", "https://photos.app.goo.gl/juWsCPPNknXuAHk87"),
          _chip("Proposal 6021-1.pdf", "https://drive.google.com/open?id=1ZV1uqsVWIfWHMZC25LKrPmgkTwauoS3N")),
    _para("HEADING_4", _text("Collections")),
    _para("NORMAL_TEXT", _chip("Sunrise Assessment Services", "https://drive.google.com/drive/folders/102o2mXQ9xQmNo1mjxeaS9C0iiYq2TvJZ?usp=sharing",
                               "application/vnd.google-apps.folder")),
    _para("HEADING_5", _text("See: "), _chip("Call for Candidates.pdf", "https://drive.google.com/file/d/1GJlFNRhJKjyuxJ6GA5KEJbrB8ShdUQJg/view")),
]}}}]}


@pytest.mark.parametrize("url,kind,did", [
    ("https://drive.google.com/file/d/1v8omH0nvh1xRk5goNX8Sof70Ns9q0D_a/view?usp=sharing", LinkKind.DRIVE_FILE, "1v8omH0nvh1xRk5goNX8Sof70Ns9q0D_a"),
    ("https://drive.google.com/open?id=1VGTTAfdNBIsqY6Tb_LnHEt2NGyem_5a7", LinkKind.DRIVE_FILE, "1VGTTAfdNBIsqY6Tb_LnHEt2NGyem_5a7"),
    ("https://drive.google.com/drive/folders/102o2mXQ9xQmNo1mjxeaS9C0iiYq2TvJZ?usp=sharing", LinkKind.DRIVE_FOLDER, "102o2mXQ9xQmNo1mjxeaS9C0iiYq2TvJZ"),
    ("https://docs.google.com/document/d/1g6JeENkyNmP0nxggkO3Bb5JK472TFKq1L4eNBH97Yzc/edit", LinkKind.GOOGLE_DOC, "1g6JeENkyNmP0nxggkO3Bb5JK472TFKq1L4eNBH97Yzc"),
    ("https://photos.app.goo.gl/juWsCPPNknXuAHk87", LinkKind.PHOTOS, ""),
    ("https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=4930.", LinkKind.LAW, ""),
    ("https://prod-portal-sacramento-ca.journaltech.com/public-portal/?q=node/397/2516556", LinkKind.COURT, ""),
    ("https://www.amazon.com/dp/B0HDXYC7BW/", LinkKind.WEB, ""),
])
def test_a_link_is_named_by_the_rules_and_a_drive_link_gives_its_id(url, kind, did) -> None:
    assert link_kind(url, M.agenda_link_rules()) is kind and drive_id(url) == did


def test_each_link_sits_under_its_item_and_subitem() -> None:
    links = links_in_doc(DOC, M.agenda_link_rules())
    got = [(l.item, l.subitem, l.kind, l.text) for l in links]
    assert got[0] == ("", "", LinkKind.ZOOM, "Join via Zoom")
    assert ("Review all open maintenance requests", "Garage door, building 2", LinkKind.PHOTOS, "📷") in got
    assert ("Review all open maintenance requests", "Garage door, building 2", LinkKind.DRIVE_FILE, "Proposal 6021-1.pdf") in got
    assert ("Collections", "", LinkKind.DRIVE_FOLDER, "Sunrise Assessment Services") in got
    # A sub-item's title keeps the chip it holds, so the label reads as the agenda does.
    assert ("Collections", "See: [Call for Candidates.pdf]", LinkKind.DRIVE_FILE, "Call for Candidates.pdf") in got


def test_the_index_labels_each_file_with_every_meeting_and_item_that_used_it(tmp_path) -> None:
    from jason.tasks.agenda_links import build, for_meeting, lookup

    (tmp_path / "meetings" / "agenda-docs").mkdir(parents=True)
    later = json.loads(json.dumps(DOC))
    later["title"] = "Agenda for 7/21/26"
    for i, doc in enumerate((DOC, later)):
        (tmp_path / "meetings" / "agenda-docs" / f"d{i}.json").write_text(json.dumps({**doc, "_path": "My Drive/Meetings/2026/x"}), encoding="utf-8")
    (tmp_path / "drive").mkdir()
    (tmp_path / "drive" / "files.json").write_text(json.dumps([{"id": "1ZV1uqsVWIfWHMZC25LKrPmgkTwauoS3N", "name": "Proposal 6021-1.pdf",
                                                              "path": "My Drive/Proposal 6021-1.pdf", "mimeType": "application/pdf"}]), encoding="utf-8")
    result = build(tmp_path, M)
    assert all(l["kind"] != "Zoom meeting" for a in result["agendas"] for l in a["links"])
    proposal = lookup(tmp_path, "6021")[0]
    assert proposal["drive"]["path"] == "My Drive/Proposal 6021-1.pdf" and proposal["inDrive"] and proposal["documentKind"] == "proposal"
    assert [l["date"] for l in proposal["labels"]] == ["2026-07-21", "2026-07-07"] and "maintenance and repairs" in proposal["topics"]
    folder = lookup(tmp_path, "102o2mXQ9xQmNo1mjxeaS9C0iiYq2TvJZ")[0]
    assert not folder["inDrive"]                                   # linked, but not in this Drive's listing
    assert {l["kind"] for l in for_meeting(tmp_path, "2026-07-07")} >= {"Google Photos album", "Drive file", "Drive folder"}
