"""The words in force on a day: a section's earlier versions with their ranges, and which one a recital gives.

Every section, act, and session publication here is made up ("CIV 9901", "Stats. 2090, Ch. 1"), and the fake lawlibrary
answers from this file: nothing leaves the test.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import pytest

from jason.community import law_text
from jason.community.authorities import Authority, Basis
from jason.community.law_readings import Canon, LawReading, Provision, ReadingStanding, ReadingState, Whose, recite, status
from jason.community.law_text import Decided, in_force, own_operative
from jason.sources.lawlibrary import LawLibrary
from jason.tasks.authority_digests import add_version, edition_versions
from jason.tasks.export_authorities import AUTHORITIES_DIR, MANIFEST, authority_pages, export_authorities
from jason.tasks.statute_fetch import Miss, prior_versions

EDITIONS = ["2091", "2093", "2095", "2097"]
OLD = "(a) A notice shall be given in writing.\n\n(b) The notice is given fifteen days before the hearing."
NEW = "(a) A notice shall be given in writing.\n\n(b) The notice is given fourteen days before the hearing."
OLD_TITLE = "9901. (Added by Stats. 2090, Ch. 1, Sec. 2.)"
NEW_TITLE = "9901. (Amended by Stats. 2095, Ch. 7, Sec. 1.)"
SPANS = (Authority("CIV", "9901", "9910", "a made-up chapter", Basis.DUTY),)


def _note(words: str, citation: str, *, effective: str = "", operative: str = "", repealed: str = "", bill: str = "",
          enacted: str = "") -> dict:
    """A history note as lawlibrary's ``read_note`` records it."""
    dates = [{"occasion": o, "day": d, "by": ""} for o, d in (("effective", effective), ("operative", operative),
                                                              ("repealed", repealed)) if d]
    year = citation[len("Stats. "):len("Stats. ") + 4] if citation.startswith("Stats. ") else ""
    return {"note": words, "read": True, "citation": citation, "bill": bill, "effective": effective, "operative": operative,
            "dates": dates, "statute": {"year": year} if year else None, "enacted": enacted, "measure": ""}


def _row(session: str, number: str, title: str, text: str, note: dict) -> dict:
    return {"citation": f"CIV {number}", "code": "CIV", "section": number, "title": title, "text": text, "session": session,
            "history": note["note"], "note": note}


ADDED = _note("Added by Stats. 2090, Ch. 1, Sec. 2.   (AB 1)   Effective January 1, 2091.", "Stats. 2090, Ch. 1, Sec. 2",
              effective="2091-01-01", bill="AB 1")
AMENDED = _note("Amended by Stats. 2095, Ch. 7, Sec. 1.   (AB 7)   Effective June 30, 2095.", "Stats. 2095, Ch. 7, Sec. 1",
                effective="2095-06-30", bill="AB 7")
ROWS = [_row("2091", "9901", OLD_TITLE, OLD, ADDED), _row("2093", "9901", OLD_TITLE, OLD, ADDED),
        _row("2095", "9901", NEW_TITLE, NEW, AMENDED), _row("2097", "9901", NEW_TITLE, NEW, AMENDED)]


def _library(tmp_path: Path, rows: list[dict] = ROWS, editions: list[str] = EDITIONS, session: str = "") -> LawLibrary:
    """A lawlibrary whose worker answers a span from one session publication's rows (the newest unless ``session``)
    and ``versions`` from every publication's."""
    calls: list[dict] = []

    def run(payload):
        calls.append(payload)
        out = {"spans": [], "acts": {}, "versions": []}
        for code, start, end in payload.get("spans", []):
            printed = [r for r in rows if r["session"] == (session or editions[-1]) and r["code"] == code
                       and float(start) <= float(r["section"]) <= float(end)]
            out["spans"].append({"code": code, "start": start, "end": end, "sections": [
                {**{k: r[k] for k in ("citation", "code", "section", "title", "text", "session")},
                 "path": [{"heading": "CHAPTER 1. Made Up [9900. - 9999.]"}]} for r in printed]})
        for asked in payload.get("versions", []):
            out["versions"].append({"code": asked["code"], "editions": editions,
                                    "rows": [r for r in rows if r["code"] == asked["code"] and r["section"] in asked["sections"]]})
        return out

    library = LawLibrary(tmp_path, run=run)
    library.calls = calls
    return library


def _export(tmp_path: Path, **library):
    return export_authorities(_library(tmp_path, **library), tmp_path, spans=SPANS, acts=())


def _lines(recital) -> str:
    return "\n".join(recital.lines())


def test_as_of_before_an_amendment_recites_the_earlier_words_from_disk_with_their_range(tmp_path: Path):
    _export(tmp_path)
    now = law_text.section_digest("CIV 9901", tmp_path)
    [read] = prior_versions(tmp_path, ["civ-9901"], library=_library(tmp_path), when="2099-01-02")
    assert read.found and read.printed == tuple(EDITIONS) and not read.differs
    old, new = read.versions
    assert (old.start, old.until, old.until_by, old.current) == ("2091-01-01", "2095-06-30", "Stats. 2095, Ch. 7, Sec. 1 (AB 7)", False)
    assert (new.start, new.until, new.current, new.digest) == ("2095-06-30", "", True, now)
    assert old.act == "Stats. 2090, Ch. 1, Sec. 2 (AB 1)" and old.editions == ("2091", "2093")
    # The earlier words are a history file under their digest, with the act, the range, and the source.
    kept = tmp_path / "authorities" / "history" / "CIV-9901" / f"{old.digest}.md"
    assert [f["did"] for f in read.files] == ["written"] and tmp_path / read.files[0]["file"] == kept
    text = kept.read_text(encoding="utf-8")
    for line in ("- Source: California Legislature, 2091 to 2093 session publications, read with lawlibrary",
                 "- Editions: 2091, 2093", "- Act: Stats. 2090, Ch. 1, Sec. 2 (AB 1)", "- From: 2091-01-01",
                 "- Until: 2095-06-30", "- Until by: Stats. 2095, Ch. 7, Sec. 1 (AB 7)",
                 "- Legislature's note: Added by Stats. 2090, Ch. 1, Sec. 2. (AB 1) Effective January 1, 2091.",
                 "- Kept: 2099-01-02 (jason law-history --versions)"):
        assert line in text
    assert "fifteen days" in text and "fourteen days" not in text
    # The current words are not written again; the ledger records the day they came into force.
    assert sorted(p.name for p in kept.parent.iterdir()) == [kept.name]
    ledger = law_text.version_ledger(tmp_path, "CIV 9901")
    assert ledger["read"] == "2099-01-02" and [(v["digest"], v["from"], v["newest"]) for v in ledger["versions"]] == [
        (old.digest, "2091-01-01", False), (now, "2095-06-30", True)]

    # A day before the amendment: the earlier words, labeled with their range and source.
    day = date(2092, 5, 1)
    found = in_force("CIV 9901", tmp_path, day)
    assert found.decided is Decided.PRIOR and found.text.digest == old.digest and not found.text.current
    assert law_text.law_text("CIV 9901", tmp_path, as_of=day).words == old.words
    recital = recite("CIV 9901", tmp_path, (), day)
    assert recital.in_force and recital.decided == "prior" and recital.digest == old.digest and recital.others == ()
    assert "fifteen days before the hearing." in recital.words and "fourteen" not in recital.words
    assert "2091 to 2093 session publications" in recital.source
    lines = _lines(recital)
    assert ("In force on 2092-05-01: from 2091-01-01 until 2095-06-30; made by Stats. 2090, Ch. 1, Sec. 2 (AB 1); "
            "ended by Stats. 2095, Ch. 7, Sec. 1 (AB 7)") in lines
    assert f"these are not the words on the shelf now (digest {now[:12]})" in lines and "is after the last session" not in lines
    assert recital.as_dict()["inForce"] == {"shown": True, "decided": "prior", "basis": recital.basis, "quotes": []}
    # Between the last publication that printed them and the next act: still theirs, with what the shelf cannot show.
    gap = recite("CIV 9901", tmp_path, (), date(2095, 3, 1))
    assert gap.digest == old.digest and any("the 2093 session's, which covers 2093 and 2094" in c for c in gap.caveats)
    # On and after the amendment's day: the current words, in force from that day.
    for on in (date(2095, 6, 30), date(2096, 1, 1)):
        after = recite("CIV 9901", tmp_path, (), on)
        assert after.decided == "current" and after.digest == now and "fourteen days" in after.words
        assert "from 2095-06-30; made by Stats. 2095, Ch. 7, Sec. 1 (AB 7)" in after.basis
    assert law_text.law_text("CIV 9901", tmp_path, as_of=date(2096, 1, 1)).digest == now
    # Without a day nothing changes: the current words, and no word about a day.
    plain = recite("CIV 9901", tmp_path, ())
    assert plain.digest == now and plain.decided == "" and "In force on" not in _lines(plain)
    assert law_text.law_text("CIV 9901", tmp_path).digest == now

    # A reading of the earlier words is a reading of the words in force that day, and stale against the shelf now.
    reading = LawReading("notice-days", (Provision("CIV 9901", old.digest),), "Are the days calendar days?",
                         ReadingStanding.READING, Whose.BOARD, date(2092, 1, 1), reading="The days are calendar days.",
                         canon=Canon.ORDINARY_SENSE)
    assert [r.reading.key for r in recite("CIV 9901", tmp_path, [reading], day).readings] == ["notice-days"]
    assert status(reading, tmp_path).state is ReadingState.STALE
    assert [r.reading.key for r in recite("CIV 9901", tmp_path, [reading]).stale] == ["notice-days"]


def test_as_of_before_an_amendment_without_the_earlier_words_recites_the_current_words_and_says_so(tmp_path: Path):
    _export(tmp_path)
    now = law_text.section_digest("CIV 9901", tmp_path)
    day = date(2092, 5, 1)
    found = in_force("CIV 9901", tmp_path, day)
    assert found.decided is Decided.NOT_SHOWN and found.text is None and not found.shown
    assert law_text.law_text("CIV 9901", tmp_path, as_of=day) is None
    recital = recite("CIV 9901", tmp_path, (), day)
    assert recital.found and not recital.in_force and recital.decided == "not_shown"
    assert recital.digest == now and "fourteen days" in recital.words
    lines = _lines(recital)
    assert "Not shown to be in force on 2092-05-01: these are the words on the shelf now" in lines
    # The section's own credit line says the words are later than the day; the earlier words are not held, and the
    # caveat names the command that would bring them.
    assert any("cannot be the words of 2092-05-01: the credit line names Stats. 2095" in c for c in recital.caveats)
    assert any("the words in force on 2092-05-01 are not held as such" in c
               and "jason law-history --versions --citation CIV-9901" in c for c in recital.caveats)
    assert recital.as_dict()["inForce"]["shown"] is False

    # The words an earlier export replaced are held without a range: still not shown, and the caveat says why.
    _export(tmp_path, session="2093")
    _export(tmp_path)
    was = next(t for t in law_text.history_texts("CIV 9901", tmp_path) if "fifteen days" in t.words)
    assert (was.start, was.until) == ("", "") and was.replaced == date.today().isoformat()
    held = recite("CIV 9901", tmp_path, (), day)
    assert not held.in_force and held.digest == now
    assert any(f"an earlier version is held (digest {was.digest[:12]}): its range is not recorded in full" in c for c in held.caveats)
    # The fetch records the range on the file already there, keeping the header it carried.
    [read] = prior_versions(tmp_path, ["CIV 9901"], library=_library(tmp_path))
    assert [f["did"] for f in read.files] == ["updated"]
    text = (tmp_path / read.files[0]["file"]).read_text(encoding="utf-8")
    assert "words an export replaced" in text and "- Replaced:" in text and "- From: 2091-01-01" in text and "- Until: 2095-06-30" in text
    assert recite("CIV 9901", tmp_path, (), day).digest == was.digest
    assert [f["did"] for f in prior_versions(tmp_path, ["CIV 9901"], library=_library(tmp_path))[0].files] == ["same"]

    # A day before the first publication on lawlibrary's shelf: not there to fetch; a person adds it by hand.
    early = recite("CIV 9901", tmp_path, (), date(2089, 1, 1))
    assert not early.in_force and early.digest == now
    assert any("the 2091 to 2097 session publications print it" in c and "added by a person from an official source" in c
               for c in early.caveats)
    assert any("which does not include 2089-01-01" in c for c in early.caveats)


def test_after_an_export_changes_the_shelf_the_recital_says_to_read_the_versions_again(tmp_path: Path):
    _export(tmp_path)
    prior_versions(tmp_path, ["CIV 9901"], library=_library(tmp_path))
    was = law_text.section_digest("CIV 9901", tmp_path)
    # A later publication amends the section, and an export brings it onto the shelf.
    newest = _note("Amended by Stats. 2098, Ch. 3, Sec. 1.   Effective January 1, 2099.", "Stats. 2098, Ch. 3, Sec. 1",
                   effective="2099-01-01")
    rows = [*ROWS, _row("2099", "9901", "9901. (Amended by Stats. 2098, Ch. 3, Sec. 1.)", NEW.replace("fourteen", "ten"), newest)]
    editions = [*EDITIONS, "2099"]
    _export(tmp_path, rows=rows, editions=editions)
    # The replaced words keep the day the ledger recorded for them; their end is not recorded until the next fetch.
    held = next(t for t in law_text.history_texts("CIV 9901", tmp_path) if t.digest == was)
    assert (held.start, held.until) == ("2095-06-30", "")
    stale = recite("CIV 9901", tmp_path, (), date(2096, 1, 1))
    assert not stale.in_force and "ten days" in stale.words
    assert any("the words on the shelf changed since the versions were read" in c
               and "jason law-history --versions --citation CIV-9901 reads them again" in c for c in stale.caveats)
    [read] = prior_versions(tmp_path, ["CIV 9901"], library=_library(tmp_path, rows=rows, editions=editions))
    assert sorted(f["did"] for f in read.files) == ["same", "updated"]
    again = recite("CIV 9901", tmp_path, (), date(2096, 1, 1))
    assert again.decided == "prior" and again.digest == was and "from 2095-06-30 until 2099-01-01" in again.basis


def test_a_section_the_library_does_not_print_is_a_miss_and_writes_nothing(tmp_path: Path):
    _export(tmp_path)
    library = _library(tmp_path)
    found = prior_versions(tmp_path, ["CIV 9999", "XYZ 12", "CIV 9901", "civ 9901(a)"], library=library)
    assert [(r.citation, r.found, r.miss) for r in found] == [
        ("CIV 9999", False, Miss.NOT_IN_LIBRARY), ("XYZ 12", False, Miss.NOT_IN_LIBRARY), ("CIV 9901", True, None)]
    assert "2091 to 2097" in found[0].detail and len(library.calls) == 1
    assert library.calls[0]["versions"] == [{"code": "CIV", "sections": ["9999", "9901"]}]
    assert not (tmp_path / "authorities" / "history" / "CIV-9999").exists()
    assert law_text.version_ledger(tmp_path, "CIV 9999") == {}

    def broken(payload):
        raise RuntimeError("the worker fell over")

    [failed] = prior_versions(tmp_path, ["CIV 9910"], library=LawLibrary(tmp_path, run=broken))
    assert not failed.found and failed.miss is Miss.WORKER_FAILED and "fell over" in failed.detail


UNTIL = "(a) Made-up words.\n\n(b) This section shall remain in effect only until January 1, 2099, and as of that date is repealed."
FROM = "(a) Other made-up words.\n\n(b) This section shall be operative January 1, 2099."


def _two_versions(tmp_path: Path, first: str, second: str) -> None:
    """Put a section on the shelf twice under one number, as the publication prints two versions."""
    _export(tmp_path)
    page = tmp_path / authority_pages(tmp_path)[0].file
    page.write_text(page.read_text(encoding="utf-8")
                    + f"\n## CIV 9902\n\n(Repealed (in Sec. 3) and added by Stats. 2090, Ch. 3, Sec. 4.)\n\n{first}\n"
                    + f"\n## CIV 9902\n\n(Amended by Stats. 2090, Ch. 3, Sec. 3.)\n\n{second}\n", encoding="utf-8")
    path = tmp_path / AUTHORITIES_DIR / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["pages"][0]["sections"] += ["9902", "9902"]
    path.write_text(json.dumps(manifest), encoding="utf-8")


def test_a_section_printed_in_two_versions_is_picked_by_its_own_operative_words(tmp_path: Path):
    # The publication's order is not the order they operate in: the later-operative version is printed first.
    _two_versions(tmp_path, FROM, UNTIL)
    later, sooner = law_text.versions("CIV 9902", tmp_path)
    assert "shall be operative" in later.words and law_text.section_digest("CIV 9902", tmp_path) == later.digest
    assert own_operative(sooner.words).until == "2099-01-01" and own_operative(later.words).start == "2099-01-01"

    before = recite("CIV 9902", tmp_path, (), date(2098, 6, 1))
    assert before.decided == "own_words" and before.in_force and before.digest == sooner.digest and before.others == ()
    assert before.quotes == ("This section shall remain in effect only until January 1, 2099, and as of that date is repealed.",
                             "This section shall be operative January 1, 2099.")
    lines = _lines(before)
    assert "of the 2 versions the shelf holds under the number, the versions' own words place this one in force on 2098-06-01" in lines
    assert "Own words that decide it: \"This section shall remain in effect only until January 1, 2099" in lines
    assert any(f"the other version the shelf holds under the number (digest {later.digest[:12]}) came into force on "
               "2099-01-01, after 2098-06-01: \"This section shall be operative January 1, 2099.\"" in c for c in before.caveats)
    assert law_text.law_text("CIV 9902", tmp_path, as_of=date(2098, 6, 1)).digest == sooner.digest

    on = recite("CIV 9902", tmp_path, (), date(2099, 1, 1))
    assert on.decided == "own_words" and on.digest == later.digest and on.others == ()
    assert any(f"(digest {sooner.digest[:12]}) ceased on 2099-01-01" in c for c in on.caveats)
    # Without a day both are recited, in the publication's order, with the caveat.
    both = recite("CIV 9902", tmp_path, ())
    assert both.digest == later.digest and [o.digest for o in both.others] == [sooner.digest]
    assert any("holds 2 versions" in c and "not the order they operate in" in c for c in both.caveats)
    # A reading of the version not in force that day is not applied that day.
    reading = LawReading("made-up", (Provision("CIV 9902", later.digest),), "What do the words require?",
                         ReadingStanding.READING, Whose.COUNSEL, date(2098, 1, 1), reading="They require a thing.",
                         authority="a made-up letter")
    assert status(reading, tmp_path).applies
    then = status(reading, tmp_path, as_of=date(2098, 6, 1))
    assert then.state is ReadingState.STALE and "not the words in force on the day asked" in then.provisions[0].detail

    # A day before jason took the publication, with no record of when the words came in: their own words still pick
    # between the two, and the caveat says the start is not recorded.
    path = tmp_path / AUTHORITIES_DIR / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["exported"] = "2097-01-01"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    earlier = recite("CIV 9902", tmp_path, (), date(2096, 6, 1))
    assert earlier.decided == "own_words" and earlier.digest == sooner.digest
    assert any("jason has no record of the day these words came into force" in c and "Stats. 2090, Ch. 3, Sec. 3" in c
               for c in earlier.caveats)
    # A day before the act the credit line names: neither version, and nothing is picked.
    never = recite("CIV 9902", tmp_path, (), date(2085, 6, 1))
    assert never.decided == "not_shown" and len(never.others) == 1
    assert any("cannot be the words of 2085-06-01" in c for c in never.caveats)


def test_a_reader_quotes_the_version_in_force_today_not_the_one_printed_first(tmp_path: Path):
    from jason.tasks.export_authorities import authority_text

    _two_versions(tmp_path, FROM, UNTIL)
    page = tmp_path / authority_pages(tmp_path)[0].file
    # Acts of years gone by, so today falls between them and the day the versions' own words name.
    page.write_text(page.read_text(encoding="utf-8").replace("Stats. 2090, Ch. 3", "Stats. 2001, Ch. 3"), encoding="utf-8")
    hit = authority_text(tmp_path, "CIV 9902", fetch=False)
    assert hit["found"] and "shall remain in effect only until January 1, 2099" in hit["text"]
    assert "shall be operative January 1, 2099" not in hit["text"]
    assert "Version 2 in the publication's order" in hit["version"] and "shall remain in effect only until" in hit["version"]
    # Where the versions' own words do not say, both are quoted, each labeled, never the first alone; and a section
    # printed once is that print, with no note.
    page.write_text(page.read_text(encoding="utf-8").replace("shall be operative January 1, 2099", "is made up")
                    .replace("shall remain in effect only until January 1, 2099, and as of that date is repealed", "is made up too"),
                    encoding="utf-8")
    both = authority_text(tmp_path, "CIV 9902", fetch=False)
    assert both["undecided"] and "Other made-up words." in both["text"] and "is made up too" in both["text"]
    assert both["text"].count("[jason: version") == 2
    once = authority_text(tmp_path, "CIV 9901", fetch=False)
    assert "fourteen days" in once["text"] and "version" not in once


def test_two_versions_whose_words_state_no_operative_day_are_both_shown(tmp_path: Path):
    _two_versions(tmp_path, "(a) Made-up words, one way.", "(a) Made-up words, another way.")
    first, second = law_text.versions("CIV 9902", tmp_path)
    assert not own_operative(first.words).stated
    recital = recite("CIV 9902", tmp_path, (), date(2098, 6, 1))
    assert recital.decided == "not_shown" and recital.digest == first.digest and [o.digest for o in recital.others] == [second.digest]
    assert any("their own words do not show which was in force that day" in c for c in recital.caveats)
    assert any("their own words do not decide between them" in c for c in recital.caveats)
    assert law_text.law_text("CIV 9902", tmp_path, as_of=date(2098, 6, 1)) is None
    # A sentence about an amendment, or about another section, is not the section speaking of itself.
    assert not own_operative("(c) The amendments made to this section shall become operative on January 1, 2099.").stated
    assert own_operative("This section shall become inoperative on July 1, 2098, and, as of January 1, 2099, is repealed, "
                         "unless Section 9902.5 applies.").until == "2098-07-01"
    assert own_operative("(d) This section shall become operative on January 1, 2099.").start == "2099-01-01"


def test_a_hand_added_prior_version_is_found(tmp_path: Path):
    _export(tmp_path)
    now = law_text.section_digest("CIV 9901", tmp_path)
    words = f"{OLD_TITLE}\n\n{OLD}\n"
    with pytest.raises(ValueError, match="official source"):
        add_version(tmp_path, "CIV 9901", words, source="", by="A. Person")
    with pytest.raises(ValueError, match="whole section"):
        add_version(tmp_path, "CIV 9901(b)", words, source="a made-up source", by="A. Person")
    with pytest.raises(ValueError, match="range is empty"):
        add_version(tmp_path, "CIV 9901", words, source="a made-up source", by="A. Person", start="2095-01-01", until="2091-01-01")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        add_version(tmp_path, "CIV 9901", words, source="a made-up source", by="A. Person", start="January 1")
    path, did = add_version(tmp_path, "civ-9901", words, source="Statutes of 2090, chapter 1, section 2 (a made-up volume)",
                            by="A. Person", start="2091-01-01", until="2095-06-30", act="Stats. 2090, Ch. 1, Sec. 2",
                            when="2099-02-03")
    digest = law_text.words_digest(words)
    assert did == "written" and path == tmp_path / "authorities" / "history" / "CIV-9901" / f"{digest}.md"
    text = path.read_text(encoding="utf-8")
    assert "- Source: Statutes of 2090, chapter 1, section 2 (a made-up volume)" in text
    assert "- Added by hand: A. Person, 2099-02-03" in text and "- From: 2091-01-01" in text
    recital = recite("CIV 9901", tmp_path, (), date(2092, 5, 1))
    assert recital.decided == "prior" and recital.digest == digest and "fifteen days" in recital.words
    assert recital.source == "Statutes of 2090, chapter 1, section 2 (a made-up volume)"
    assert any("added by hand (A. Person, 2099-02-03)" in c for c in recital.caveats)
    assert add_version(tmp_path, "CIV 9901", words, source="another source", by="B. Person") == (path, "held")
    assert law_text.law_text("CIV 9901", tmp_path, digest=digest[:12]).added == "A. Person, 2099-02-03"

    # A version added with no end is held, and never picked: its range is not recorded in full.
    open_path, _ = add_version(tmp_path, "CIV 9910", "Words with no recorded end.", source="a made-up source", by="A. Person",
                               start="2080-01-01")
    assert "- Until: not recorded" in open_path.read_text(encoding="utf-8")
    found = in_force("CIV 9910", tmp_path, date(2085, 1, 1))
    assert found.decided is Decided.NOT_SHOWN and found.text is None
    assert any("its range is not recorded in full (from 2080-01-01" in c for c in found.caveats)

    # A file a person writes into the folder by hand is read the same way, whatever its name.
    folder = tmp_path / "authorities" / "history" / "CIV-9905"
    folder.mkdir(parents=True)
    (folder / "from-the-statutes.md").write_text(
        "# CIV 9905: an earlier version\n\n- Source: Statutes of 2080, chapter 5 (a made-up volume)\n- Act: Stats. 2080, Ch. 5\n"
        "- From: 2081-01-01\n- Until: 2090-01-01\n- Added by hand: A. Person, 2099-02-03\n\n## CIV 9905\n\nRepealed made-up words.\n",
        encoding="utf-8")
    gone = recite("CIV 9905", tmp_path, (), date(2085, 1, 1))
    assert gone.found and gone.decided == "prior" and gone.words == "Repealed made-up words."
    assert any("CIV 9905 is no longer on the shelf" in c for c in gone.caveats)
    assert "from 2081-01-01 until 2090-01-01; made by Stats. 2080, Ch. 5" in gone.basis
    after = recite("CIV 9905", tmp_path, (), date(2095, 1, 1))
    assert not after.found and "which does not include 2095-01-01" in after.reason
    plain = recite("CIV 9905", tmp_path, ())
    assert not plain.found and "The history holds 1 earlier version(s)" in plain.reason
    assert law_text.section_digest("CIV 9901", tmp_path) == now


def test_edition_rows_become_versions_each_with_the_range_the_notes_state():
    editions = ["2091", "2093", "2095", "2097"]
    enacted = _note("Enacted 2001.", "Enacted 2001", enacted="2001")
    amended = _note("Amended by Stats. 2094, Ch. 2, Sec. 1.   Effective January 1, 2095.   Repealed as of January 1, 2099, by its "
                    "own provisions.", "Stats. 2094, Ch. 2, Sec. 1", effective="2095-01-01", repealed="2099-01-01")
    delayed = _note("Repealed and added by Stats. 2094, Ch. 2, Sec. 2.   Effective January 1, 2095.   Operative January 1, 2099, "
                    "by its own provisions.", "Stats. 2094, Ch. 2, Sec. 2", effective="2095-01-01", operative="2099-01-01")
    again = _note("Amended by Stats. 2096, Ch. 9, Sec. 1.   Effective January 1, 2097.", "Stats. 2096, Ch. 9, Sec. 1",
                  effective="2097-01-01")
    late = _note("Amended (as added by Stats. 2094, Ch. 2, Sec. 2) by Stats. 2096, Ch. 9, Sec. 2.   Effective January 1, 2097.   "
                 "Operative January 1, 2099.", "Stats. 2096, Ch. 9, Sec. 2", effective="2097-01-01", operative="2099-01-01")
    rows = [_row("2091", "9903", "9903. (Enacted 2001.)", "First words.", enacted),
            _row("2093", "9903", "9903. (Enacted 2001.)", "First words.", enacted),
            _row("2095", "9903", "(Amended by Stats. 2094, Ch. 2, Sec. 1.)", "Second words.", amended),
            _row("2095", "9903", "(Repealed and added by Stats. 2094, Ch. 2, Sec. 2.)", "Words not yet operative.", delayed),
            _row("2097", "9903", "(Amended by Stats. 2096, Ch. 9, Sec. 1.)", "Third words.", again),
            _row("2097", "9903", "(Amended by Stats. 2096, Ch. 9, Sec. 2.)", "Later words, amended before they operated.", late)]
    first, second, waiting, third, later = edition_versions("CIV 9903", editions, rows)
    # A note that names no day leaves the start not recorded; the first publication on the shelf is the floor.
    assert (first.start, first.floor, first.until, first.act) == ("", "2091-01-01", "2095-01-01", "the code's enactment in 2001")
    assert first.until_by == "Stats. 2094, Ch. 2, Sec. 1"
    assert (second.start, second.until, second.editions) == ("2095-01-01", "2097-01-01", ("2095",))
    # A version amended before its operative day was never in force: its range is empty, and it is never picked.
    assert (waiting.start, waiting.until) == ("2099-01-01", "2097-01-01") and not waiting.current
    assert waiting.until_by == "Stats. 2096, Ch. 9, Sec. 1, in effect before these words' operative day"
    assert (third.start, third.until, third.until_by, third.current) == ("2097-01-01", "", "", True)
    assert (later.start, later.current) == ("2099-01-01", True)
    assert "Legislature" in first.source and "2091 to 2093 session publications" in first.source

    # A section the next publication does not print: its end is the repeal the caller knows, else not recorded.
    gone = [_row("2091", "9904", "9904. (Added by Stats. 2090, Ch. 1, Sec. 9.)", "Words later repealed.", ADDED)]
    [unknown] = edition_versions("CIV 9904", editions, gone)
    assert (unknown.start, unknown.until) == ("2091-01-01", "") and "a repeal leaves no note" in unknown.until_by
    [known] = edition_versions("CIV 9904", editions, gone, repealed="2094-01-01", repealed_by="its repeal by Stats. 2092, Ch. 8")
    assert (known.until, known.until_by) == ("2094-01-01", "its repeal by Stats. 2092, Ch. 8")
    # Printed, then not, then printed again: no range is recorded for those words.
    back = [_row("2091", "9904", "(Added by Stats. 2090, Ch. 1.)", "Words.", ADDED),
            _row("2093", "9904", "(Amended by Stats. 2092, Ch. 4.)", "Other words.", again),
            _row("2095", "9904", "(Added by Stats. 2090, Ch. 1.)", "Words.", ADDED)]
    twice = next(t for t in edition_versions("CIV 9904", editions, back) if t.words.endswith("\n\nWords."))
    assert (twice.start, twice.until) == ("", "") and "not consecutive: 2091, 2095" in twice.until_by

    # What the notes of real publications do, with made-up acts. An amendment is not in force before its act takes
    # effect, whatever earlier operative day its words still carry; "Superseded on" ends a version; a day that is
    # not after the start is not an end; and a reprint under the same act leaves the earlier print's end unrecorded.
    urgent = _note("Amended by Stats. 2092, Ch. 4, Sec. 1.   Effective September 18, 2092.   Superseded on January 1, 2093; see "
                   "further amendment by Sec. 1.5.", "Stats. 2092, Ch. 4, Sec. 1", effective="2092-09-18")
    urgent["dates"].append({"occasion": "superseded", "day": "2093-01-01", "by": ""})
    joined = _note("Amended by Stats. 2092, Ch. 4, Sec. 1.5.   Effective September 18, 2092.   Operative January 1, 2093.",
                   "Stats. 2092, Ch. 4, Sec. 1.5", effective="2092-09-18", operative="2093-01-01")
    reenacted = _note("Amended by Stats. 2096, Ch. 9, Sec. 3.   Effective January 1, 2097.   Operative January 1, 2093, by its own "
                      "provisions.", "Stats. 2096, Ch. 9, Sec. 3", effective="2097-01-01", operative="2093-01-01")
    reenacted["dates"].append({"occasion": "inoperative", "day": "2092-09-18", "by": ""})
    rows = [_row("2091", "9906", "(Amended by Stats. 2092, Ch. 4, Sec. 1.)", "Urgent words.", urgent),
            _row("2091", "9906", "(Amended by Stats. 2092, Ch. 4, Sec. 1.5.)", "Joined words.", joined),
            _row("2093", "9906", "(Amended by Stats. 2092, Ch. 4, Sec. 1.5.)", "Joined words, reprinted.", joined),
            _row("2095", "9906", "(Amended by Stats. 2092, Ch. 4, Sec. 1.5.)", "Joined words, reprinted.", joined),
            _row("2097", "9906", "(Amended by Stats. 2096, Ch. 9, Sec. 3.)", "Reenacted words.", reenacted)]
    by_words = {t.words.split("\n")[-1]: t for t in edition_versions("CIV 9906", editions, rows)}
    one = by_words["Urgent words."]
    assert (one.start, one.until, one.until_by) == ("2092-09-18", "2093-01-01", "Stats. 2092, Ch. 4, Sec. 1.5")
    # With both printed only in one publication, the note's "Superseded on" is what ends the first.
    both = {t.words.split("\n")[-1]: t for t in edition_versions("CIV 9906", editions, [rows[0], rows[1], rows[4]])}
    assert (both["Urgent words."].until, both["Urgent words."].until_by) == (
        "2093-01-01", "a later amendment the Legislature's note names (superseded)")
    assert both["Joined words."].until == "" and "absent from the 2093 session publication" in both["Joined words."].until_by
    print1, print2, last = by_words["Joined words."], by_words["Joined words, reprinted."], by_words["Reenacted words."]
    assert (print1.start, print1.until) == ("2093-01-01", "") and "under the same act with other words" in print1.until_by
    assert (print2.start, print2.until, print2.until_by) == ("2093-01-01", "2097-01-01", "Stats. 2096, Ch. 9, Sec. 3")
    assert (last.start, last.until, last.current) == ("2097-01-01", "", True)


def test_identical_words_printed_under_two_acts_are_one(tmp_path: Path):
    _export(tmp_path)
    for chapter in ("86", "87"):
        add_version(tmp_path, "CIV 9901", f"(Added by Stats. 2080, Ch. {chapter}, Sec. 12.)\n\nIdentical made-up words.",
                    source="a made-up volume", by="A. Person", start="2081-01-01", until="2086-01-01")
    add_version(tmp_path, "CIV 9901", "(Added by Stats. 2070, Ch. 1.)\n\nOne reading.", source="a made-up volume",
                by="A. Person", start="2071-01-01", until="2076-01-01")
    add_version(tmp_path, "CIV 9901", "(Added by Stats. 2070, Ch. 2.)\n\nAnother reading.", source="a made-up volume",
                by="A. Person", start="2071-01-01", until="2076-01-01")
    twin = in_force("CIV 9901", tmp_path, date(2083, 1, 1))
    assert twin.decided is Decided.PRIOR and twin.text.words.endswith("Identical made-up words.")
    assert any("print these words 2 times, each under its own credit line" in c for c in twin.caveats)
    # Two versions with different words and overlapping ranges: nothing is picked, and both are named.
    clash = recite("CIV 9901", tmp_path, (), date(2073, 1, 1))
    assert clash.decided == "not_shown" and "fourteen days" in clash.words
    assert any("2 earlier versions of CIV 9901 whose recorded ranges each include 2073-01-01" in c for c in clash.caveats)


def test_the_floor_of_an_undated_note_holds_a_day_the_publications_cover(tmp_path: Path):
    enacted = _note("Enacted 2001.", "Enacted 2001", enacted="2001")
    rows = [_row(e, "9901", "9901. (Enacted 2001.)", OLD, enacted) for e in EDITIONS]
    _export(tmp_path, rows=rows)
    prior_versions(tmp_path, ["CIV 9901"], library=_library(tmp_path, rows=rows))
    shown = in_force("CIV 9901", tmp_path, date(2092, 5, 1))
    assert shown.decided is Decided.CURRENT and "from a day not recorded" in shown.basis and "by 2091-01-01" in shown.basis
    assert "made by the code's enactment in 2001" in shown.basis
    # Before the first publication on the shelf the disk shows nothing, and nothing is inferred from the act's year.
    before = in_force("CIV 9901", tmp_path, date(2020, 1, 1))
    assert before.decided is Decided.NOT_SHOWN and before.text is None
    assert any("jason has no record of the day the words on the shelf" in c and "(Enacted 2001.)" in c for c in before.caveats)


def test_a_dated_citation_of_a_statute_gives_the_words_of_that_day_or_a_miss(tmp_path: Path):
    from types import SimpleNamespace

    from jason.community.cite import Reason
    from jason.tasks.cite import Shelf, resolve

    _export(tmp_path)
    community = SimpleNamespace(living_documents=lambda: (), citable_documents=lambda: ())
    miss = resolve("CIV 9901@2092-05-01", shelf=Shelf(community, tmp_path))
    assert not miss["found"] and miss["reason"] == Reason.EDITION_NOT_HELD.value
    assert "jason law-history --versions --citation CIV-9901" in miss["detail"]
    prior_versions(tmp_path, ["CIV 9901"], library=_library(tmp_path))
    shelf = Shelf(community, tmp_path)                       # a shelf remembers what it resolved
    then = shelf("CIV 9901@2092-05-01")
    assert then.found and "fifteen days" in then.text and then.version["decided"] == "prior" and not then.version["current"]
    assert then.version["inForce"].startswith("from 2091-01-01 until 2095-06-30") and then.version["asOf"] == "2092-05-01"
    assert then.version["source"].startswith("authorities/history/CIV-9901/") and then.version["official"]
    part = shelf("CIV 9901(b)@2092-05-01")
    assert part.text.startswith("(b) The notice is given fifteen days") and not part.version["official"]
    assert "fourteen days" in shelf("CIV 9901@2096-01-01").text and "fourteen days" in shelf("CIV 9901").text
    assert resolve("CIV 9901@2089-01-01", shelf=shelf)["reason"] == Reason.EDITION_NOT_HELD.value


def test_the_command_reads_the_cited_and_changed_sections_and_reports(tmp_path: Path, capsys):
    from jason.commands.law_versions import run
    from jason.tasks.law_history import repeals, versions_wanted

    _export(tmp_path)
    (tmp_path / "outlines").mkdir()
    (tmp_path / "outlines" / "references.json").write_text(json.dumps([
        {"kind": "statute", "target": "CIV 9901(b)", "source": "rules"}, {"kind": "statute", "target": "CIV 9901", "source": "bylaws"},
        {"kind": "section", "target": "bylaws#7.2", "source": "rules"}, {"kind": "statute", "target": "42 USC 3601", "source": "rules"}]),
        encoding="utf-8")
    history = tmp_path / "authorities" / "history"
    history.mkdir(parents=True, exist_ok=True)
    (history / "changes.json").write_text(json.dumps({"changes": [{"changes": [
        {"citation": "CIV 9904", "section": "9904", "change": "repealed", "statute": "Stats. 2092, Ch. 8", "bill": "AB 8",
         "operative": "2094-01-01", "after": "2093"},
        {"citation": "CIV 9907", "section": "9907", "change": "amended", "operative": "2090-01-01", "after": "2091"}]}]}),
        encoding="utf-8")
    assert versions_wanted(tmp_path) == ["CIV 9901"]
    assert versions_wanted(tmp_path, since="2093") == ["CIV 9901", "CIV 9904"]
    assert versions_wanted(tmp_path, shelf=True) == ["CIV 9901"]
    assert repeals(tmp_path) == {"CIV 9904": ("2094-01-01", "its repeal by Stats. 2092, Ch. 8 (AB 8)")}

    args = argparse.Namespace(versions=True, add_version="", citation=[], since="", shelf=False, json=False)
    assert run(args, tmp_path, lambda: _library(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "CIV 9901: printed in the 2091 to 2097 session publications; 2 version(s)" in out
    assert "from 2091-01-01 until 2095-06-30 (Stats. 2095, Ch. 7, Sec. 1 (AB 7)); Stats. 2090, Ch. 1, Sec. 2 (AB 1)" in out
    assert "1 of 1 sections read; 1 earlier versions in the history (1 written)" in out
    assert recite("CIV 9901", tmp_path, (), date(2092, 5, 1)).decided == "prior"
    # A version added from a file, by a named person, with its source.
    words = tmp_path / "words.txt"
    words.write_text("Made-up words of long ago.\n", encoding="utf-8")
    add = argparse.Namespace(versions=False, add_version=str(words), citation=["CIV-9901"], source="a made-up volume, page 3",
                             by="A. Person", start="2080-01-01", until="2091-01-01", act="", since="", shelf=False, json=False)
    assert run(add, tmp_path, lambda: None) == 0 and "kept " in capsys.readouterr().out
    assert recite("CIV 9901", tmp_path, (), date(2085, 1, 1)).words == "Made-up words of long ago."
    add.source = ""
    assert run(add, tmp_path, lambda: None) == 2 and "official source" in capsys.readouterr().err
