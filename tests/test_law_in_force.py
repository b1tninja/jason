"""The version of a section in force on a day, read from the disk only (``law_text.version_on``), and the tool that
serves it (``jason.api.law_in_force``).

Every section, act, and day here is made up ("CIV 9901", "Stats. 2095, Ch. 7"); the shelf and the history are written
by hand, as a person may write them. Nothing is fetched.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from jason.community import law_text
from jason.community.law_text import Decided, version_on

OLD = ("9901. (Added by Stats. 2090, Ch. 1, Sec. 2.)\n\n(a) A notice shall be given in writing.\n\n"
       "(b) The notice is given fifteen days before the hearing.\n\n(c) The notice names the place.")
NEW = ("9901. (Amended by Stats. 2095, Ch. 7, Sec. 1.)\n\n(a) A notice shall be given in writing.\n\n"
       "(b) The notice is given fourteen days before the hearing.\n\n(c) The notice names the place.")
UNTIL = ("(Amended by Stats. 2090, Ch. 3, Sec. 3.)\n\n(a) The hearing is held in a closed session.\n\n"
         "(b) This section shall remain in effect only until January 1, 2099, and as of that date is repealed.")
FROM = ("(Repealed (in Sec. 3) and added by Stats. 2090, Ch. 3, Sec. 4.)\n\n(a) The hearing is held in an open session.\n\n"
        "(b) This section shall be operative January 1, 2099.")
LETTERED = "9904a. (Added by Stats. 2090, Ch. 2, Sec. 1.)\n\n(a) A lettered made-up section."
PAGE = "authorities/CIV/CIV-9900-9910.md"


@pytest.fixture()
def data(tmp_path: Path) -> Path:
    (tmp_path / "authorities" / "CIV").mkdir(parents=True)
    (tmp_path / PAGE).write_text(
        "# Made-up hearings\n\n- Source: California Legislature, 2097 session publication, read with lawlibrary\n\n"
        f"## CIV 9901\n\n- History: amended by Stats. 2095, Ch. 7\n\n{NEW}\n\n"
        f"## CIV 9902\n\n{FROM}\n\n## CIV 9902\n\n{UNTIL}\n\n## CIV 9904a\n\n{LETTERED}\n", encoding="utf-8")
    (tmp_path / "authorities" / "manifest.json").write_text(json.dumps({"exported": "2099-01-02", "pages": [{
        "file": PAGE, "citation": "CIV 9900-9910", "title": "Made-up hearings", "code": "CIV", "start": "9900",
        "end": "9910", "sections": ["9901", "9902", "9902", "9904a"], "basis": "duty", "why": [], "session": "2097"}]}),
        encoding="utf-8")
    old_digest = law_text.words_digest(OLD)
    history = tmp_path / "authorities" / "history" / "CIV-9901"
    history.mkdir(parents=True)
    (history / f"{old_digest}.md").write_text(
        "# CIV 9901: an earlier version\n\n- Source: California Legislature, 2091 to 2093 session publications, read with "
        "lawlibrary\n- Editions: 2091, 2093\n- Act: Stats. 2090, Ch. 1, Sec. 2 (AB 1)\n- From: 2091-01-01\n"
        "- Until: 2095-06-30\n- Until by: Stats. 2095, Ch. 7, Sec. 1 (AB 7)\n\n## CIV 9901\n\n" + OLD + "\n",
        encoding="utf-8")
    now = law_text.section_digest("CIV 9901", tmp_path)
    (tmp_path / "authorities" / "history" / "versions.json").write_text(json.dumps({"sections": {"CIV 9901": {
        "read": "2099-01-02", "editions": ["2091", "2093", "2095", "2097"], "printed": ["2091", "2093", "2095", "2097"],
        "versions": [{"digest": old_digest, "act": "Stats. 2090, Ch. 1, Sec. 2 (AB 1)", "from": "2091-01-01",
                      "until": "2095-06-30", "until_by": "Stats. 2095, Ch. 7, Sec. 1 (AB 7)", "editions": ["2091", "2093"],
                      "newest": False},
                     {"digest": now, "act": "Stats. 2095, Ch. 7, Sec. 1 (AB 7)", "from": "2095-06-30", "until": "",
                      "editions": ["2095", "2097"], "newest": True}]}}}), encoding="utf-8")
    return tmp_path


def test_an_earlier_day_gives_the_earlier_version_its_subdivision_and_every_version_held(data):
    found = version_on("CIV 9901(b)", data, date(2092, 5, 1))
    assert found.found and found.decided is Decided.PRIOR and (found.citation, found.subdivisions) == ("CIV 9901", "(b)")
    assert found.words == OLD and found.subdivision_words == "(b) The notice is given fifteen days before the hearing."
    assert (found.start, found.until) == ("2091-01-01", "2095-06-30") and not found.text.current
    assert found.text.act == "Stats. 2090, Ch. 1, Sec. 2 (AB 1)" and "2091 to 2093 session publications" in found.text.source
    assert found.label().startswith("the version in force on 2092-05-01 (digest ") and "from 2091-01-01 until 2095-06-30" in found.label()
    # Every version held, oldest first, each with its range and where it stands against the one in force.
    assert [(h.current, h.start, h.until, h.in_force, h.place) for h in found.held] == [
        (False, "2091-01-01", "2095-06-30", True, "in force"), (True, "2095-06-30", "", False, "later")]
    assert found.held[1].digest == law_text.section_digest("CIV 9901", data)
    assert any("split from the section as jason splits it" in c for c in found.caveats)
    assert law_text.NOT_RESTATEMENT in found.caveats
    told = found.as_dict()
    assert told["asOf"] == "2092-05-01" and told["decided"] == "prior" and told["subdivisionWords"].startswith("(b)")
    assert [v["place"] for v in told["versions"]] == ["in force", "later"] and told["versions"][0]["range"].startswith("from 2091-01-01")
    # The same section read on a later day is the current words, in force from the amendment; the earlier one is earlier.
    later = version_on("civ-9901", data, date(2096, 1, 1))
    assert later.decided is Decided.CURRENT and later.words == NEW and later.text.current and later.subdivision_words == ""
    assert [(h.in_force, h.place) for h in later.held] == [(False, "earlier"), (True, "in force")]
    assert law_text.law_text("CIV 9901", data, as_of=date(2096, 1, 1)).digest == later.digest


def test_a_day_the_disk_does_not_cover_picks_nothing_and_still_lists_what_is_held(data):
    before = version_on("CIV 9901", data, date(2089, 1, 1))
    assert not before.found and before.text is None and before.words == "" and before.digest == ""
    assert before.decided is Decided.NOT_SHOWN and "does not show which words of CIV 9901 were in force on 2089-01-01" in before.reason
    assert before.label().startswith("no version shown in force on 2089-01-01")
    assert [(h.in_force, h.place) for h in before.held] == [(False, "later"), (False, "later")]
    assert any("added by a person from an official source" in c for c in before.caveats)
    # A subdivision the version does not print is said, and the whole section is given.
    missing = version_on("CIV 9901(z)", data, date(2096, 1, 1))
    assert missing.found and missing.subdivision_words == "" and any("no paragraph of this version opens with (z)" in c for c in missing.caveats)
    # Not a citation at all.
    none = version_on("the hearing rule", data, date(2096, 1, 1))
    assert not none.found and "say a code and a section" in none.reason and none.held == ()


def test_two_versions_under_one_number_and_a_lettered_number(data):
    sooner = version_on("CIV 9902", data, date(2098, 6, 1))
    assert sooner.decided is Decided.OWN_WORDS and "closed session" in sooner.words
    assert "This section shall remain in effect only until January 1, 2099, and as of that date is repealed." in sooner.quotes
    assert sorted(h.place for h in sooner.held) == ["in force", "later"]
    later = version_on("CIV 9902(a)", data, date(2099, 6, 1))
    assert "open session" in later.words and later.subdivision_words == "(a) The hearing is held in an open session."
    assert sorted(h.place for h in later.held) == ["earlier", "in force"]
    lettered = version_on("Civil Code section 9904a", data, date(2099, 6, 1))
    assert lettered.found and lettered.citation == "CIV 9904a" and "lettered made-up section" in lettered.words
    assert lettered.decided is Decided.CURRENT and "the publication jason took on 2099-01-02" in lettered.basis


def test_the_tool_and_the_api_serve_it_from_disk(data):
    from jason import api
    from jason.mcp import governance
    from jason.mcp.server import tools_for

    assert "law_in_force" in api.__all__ and api.law_in_force is governance.law_in_force
    assert "law_in_force" in [t.__name__ for t in tools_for("governance")]
    served = api.law_in_force("CIV 9901(b)", as_of="2092-05-01", data_dir=data)
    assert served["found"] and served["decided"] == "prior" and "fifteen days" in served["subdivisionWords"]
    assert served["caveat"] == law_text.NOT_RESTATEMENT and len(served["versions"]) == 2
    assert api.law_in_force("CIV 9901", as_of="March 1", data_dir=data) == {"error": "as_of is a day as YYYY-MM-DD"}
    assert api.law_in_force("CIV 9901", data_dir=data)["asOf"] == date.today().isoformat()
    assert sorted(p.name for p in (data / "authorities").rglob("*") if p.is_file()) == sorted(
        ["CIV-9900-9910.md", "manifest.json", "versions.json", next((data / "authorities" / "history" / "CIV-9901").iterdir()).name])
