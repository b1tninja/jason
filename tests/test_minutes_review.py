import json
import sys
import types

import pytest

from jason.tasks import minutes_review as task

UNKNOWN = task.UNKNOWN

DRAFT = f"""# DRAFT Minutes of 10/20/26

_Drafted by jason from the Zoom record; "{UNKNOWN}" marks what the record does not show._

## Call to order

The president called the meeting to order at {UNKNOWN}.

_(Bylaws)_

## Attendance and quorum

Directors present: A. Director, B. Director. {{Name the number of directors in office.}}

## Business

### 1. Landscaping contract

The board discussed the bids and chose the lower one.

- **Motion:** Accept the bid ($1,200)
  - Moved: A. Director; seconded: {UNKNOWN}
  - Result: carried

### 2. Collections

Pat Example is delinquent on assessments and the board discussed a lien.

## Adjournment

The meeting adjourned at {UNKNOWN}.
"""


def test_parse_finds_sections_and_blanks():
    parsed = task.parse(DRAFT)
    headings = [s.heading for s in parsed["sections"]]
    assert headings[:4] == ["DRAFT Minutes of 10/20/26", "Call to order", "Attendance and quorum", "Business"]
    blanks = parsed["blanks"]
    assert [b.id for b in blanks] == ["b1", "b2", "b3", "b4"]          # the preamble's quoted marker only explains it
    assert blanks[0].section == "Call to order" and blanks[0].marker == UNKNOWN and "called the meeting to order" in blanks[0].context
    assert blanks[1].marker == "{Name the number of directors in office.}" and blanks[1].section == "Attendance and quorum"
    assert blanks[2].section == "1. Landscaping contract" and blanks[2].context.startswith("- Moved: A. Director")
    assert blanks[3].section == "Adjournment"
    business = next(s for s in parsed["sections"] if s.heading == "Business")
    assert business.blanks == []                                       # the motion's blank is under its item heading
    item = next(s for s in parsed["sections"] if s.heading == "1. Landscaping contract")
    assert item.blanks == ["b3"] and item.level == 3
    assert task.parse("")["blanks"] == []


def test_parse_leaves_links_and_checkboxes_alone():
    parsed = task.parse("See [the agenda](https://example.test/a) and [ ] done, [x] done; the rest [is a blank here].")
    assert [b.marker for b in parsed["blanks"]] == ["[is a blank here]"]


def test_privacy_flags_name_beside_delinquent():
    flags = task.privacy_flags(DRAFT)
    assert len(flags) == 1
    f = flags[0]
    assert f["member"] == "Pat Example" and "delinquent" in f["why"] and f["text"].startswith("Pat Example is delinquent")
    assert f["line"] == DRAFT.splitlines().index("Pat Example is delinquent on assessments and the board discussed a lien.") + 1
    # a director acting for the board, or a role, is not a member's name
    assert task.privacy_flags("Board President moved to send the delinquent accounts to collections.") == []
    assert task.privacy_flags("The board discussed a lien in Executive Session.") == []
    # with PayHOA's names, only a member counts
    assert task.privacy_flags(DRAFT, names=["Someone Else"]) == []
    with_names = task.privacy_flags(DRAFT, names=["Pat Example"])
    assert len(with_names) == 1 and with_names[0]["member"] == "Pat Example" and with_names[0]["replacement"]


def test_fill_replaces_blanks_and_keeps_the_rest():
    filled = task.fill(DRAFT, {"b1": "7:04 PM", "b3": "B. Director", "b4": "  "})
    assert "called the meeting to order at 7:04 PM." in filled
    assert "Moved: A. Director; seconded: B. Director" in filled
    assert filled.count(UNKNOWN) == 2                      # the preamble's and the adjournment's (blank value) stay
    assert "{Name the number of directors in office.}" in filled
    assert task.fill(DRAFT, {}) == "\n".join(DRAFT.splitlines())


def test_save_review_writes_both_files_and_refuses(tmp_path):
    (tmp_path / "board").mkdir()
    src = tmp_path / "board" / "minutes-draft-2026-10-20.md"
    src.write_text(DRAFT, encoding="utf-8")
    assert task.list_drafts(tmp_path)[0] == {**task.list_drafts(tmp_path)[0], "date": "2026-10-20", "blanks": 4, "filled": 0, "reviewed": False, "privacyFlags": 1, "minutesFile": ""}

    with pytest.raises(ValueError):
        task.save_review(tmp_path, "2026-10-20", {"b1": "7:04 PM"}, by="")
    with pytest.raises(ValueError, match="b9"):
        task.save_review(tmp_path, "2026-10-20", {"b9": "x"}, by="Secretary")
    with pytest.raises(KeyError):
        task.save_review(tmp_path, "2026-11-17", {}, by="Secretary")
    with pytest.raises(ValueError):
        task.save_review(tmp_path, "soon", {}, by="Secretary")
    assert not (tmp_path / "board" / "minutes-2026-10-20.md").exists()

    saved = task.save_review(tmp_path, "2026-10-20", {"b1": "7:04 PM"}, by="Secretary")
    assert saved["by"] == "Secretary" and saved["values"] == {"b1": "7:04 PM"} and saved["open"] == 3
    assert saved["history"] == [f"{saved['savedAt'][:10]}: Secretary filled 1 blank(s) (b1)"]
    review = json.loads((tmp_path / "board" / "minutes-draft-2026-10-20.review.json").read_text(encoding="utf-8"))
    assert review["values"] == {"b1": "7:04 PM"} and review["by"] == "Secretary" and review["savedAt"] and len(review["history"]) == 1
    minutes = (tmp_path / "board" / "minutes-2026-10-20.md").read_text(encoding="utf-8")
    assert "order at 7:04 PM." in minutes
    assert src.read_text(encoding="utf-8") == DRAFT                  # the draft is never edited

    again = task.save_review(tmp_path, "2026-10-20", {"b4": "8:40 PM"}, by="Secretary")
    assert again["values"] == {"b1": "7:04 PM", "b4": "8:40 PM"} and len(again["history"]) == 2 and again["open"] == 2
    rows = task.list_drafts(tmp_path)
    assert rows[0]["reviewed"] and rows[0]["reviewedBy"] == "Secretary" and rows[0]["filled"] == 2 and rows[0]["minutesFile"].endswith("minutes-2026-10-20.md")


def test_loader_and_writer(tmp_path, monkeypatch):
    (tmp_path / "board").mkdir()
    (tmp_path / "board" / "minutes-draft-2026-10-20.md").write_text(DRAFT, encoding="utf-8")
    county = types.ModuleType("jason.mcp.county")
    county._data_dir = lambda _arg: tmp_path
    mcp = types.ModuleType("jason.mcp")
    monkeypatch.setitem(sys.modules, "jason.mcp", mcp)
    monkeypatch.setitem(sys.modules, "jason.mcp.county", county)
    from jason.web.extra import minutes_review as page

    listing = page.minutes_review({})
    assert listing["found"] and listing["count"] == 1 and listing["drafts"][0]["date"] == "2026-10-20" and listing["caveats"]
    missing = page.minutes_review({"date": "2026-11-17"})
    assert not missing["found"] and missing["command"] == "jason board --minutes 2026-11-17"

    one = page.minutes_review({"date": "2026-10-20"})
    assert one["found"] and len(one["blanks"]) == 4 and one["open"] == 4 and one["reviewedBy"] == ""
    assert one["command"] == "jason board --minutes 2026-10-20" and one["commands"]["privacy"] == "jason minutes-privacy --correct"
    assert one["privacy"][0]["member"] == "Pat Example" and one["markdown"] == "\n".join(DRAFT.splitlines())

    with pytest.raises(ValueError):
        page.write("2026-10-20", {"by": "Secretary"})
    with pytest.raises(ValueError):
        page.write("2026-10-20", {"values": {"b1": "7:04 PM"}, "by": ""})
    out = page.write("2026-10-20", {"values": {"b1": "7:04 PM"}, "by": "Secretary"})
    assert out["reviewedBy"] == "Secretary" and out["open"] == 3
    assert next(b for b in out["blanks"] if b["id"] == "b1")["value"] == "7:04 PM" and "order at 7:04 PM." in out["markdown"]
    assert out["minutesFile"].endswith("minutes-2026-10-20.md")
