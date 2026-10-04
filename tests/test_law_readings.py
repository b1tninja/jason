"""The words of the law apart from readings of them: section digests, the shelf's history, and reading records.

Every statute here is made up ("CIV 9901"), and so is every reading: jason never makes a reading of a real provision.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from jason.community import law_text
from jason.community.authorities import Authority, Basis
from jason.community.law_readings import (
    Canon,
    LawReading,
    Provision,
    ReadingStanding,
    ReadingState,
    Whose,
    readings,
    recite,
    status,
)
from jason.sources.lawlibrary import LawLibrary
from jason.tasks.authority_digests import backfill
from jason.tasks.export_authorities import AUTHORITIES_DIR, MANIFEST, authority_pages, export_authorities

FIRST = "(a) A notice shall be given in writing.\n\n(b) The notice is given ten days before the hearing."
SECOND = "(a) A notice shall be given in writing.\n\n(b) The notice is given fifteen days before the hearing."


def _library(tmp_path: Path, words: dict[str, str], session: str = "2025") -> LawLibrary:
    """A lawlibrary whose worker answers from ``words`` (section number to text): nothing leaves the test."""
    def run(payload):
        out = {"spans": [], "acts": {}}
        for code, start, end in payload.get("spans", []):
            numbers = [n for n in words if float(start) <= float(n) <= float(end)]
            out["spans"].append({"code": code, "start": start, "end": end, "sections": [
                {"citation": f"{code} {n}", "code": code, "section": n, "title": f"{n}. (Added by Stats. 2099, Ch. 1.)",
                 "text": words[n], "path": [{"heading": "CHAPTER 1. Made Up [9900. - 9999.]"}], "session": session}
                for n in numbers]})
        return out

    return LawLibrary(tmp_path, run=run)


SPANS = (Authority("CIV", "9901", "9910", "a made-up chapter", Basis.DUTY),)


def _export(tmp_path: Path, words: dict[str, str], session: str = "2025"):
    return export_authorities(_library(tmp_path, words, session), tmp_path, spans=SPANS, acts=())


def _page(tmp_path: Path) -> Path:
    return tmp_path / authority_pages(tmp_path)[0].file


class _Profile:
    def __init__(self, *rows):
        self.rows = rows

    def law_readings(self):
        return self.rows


def test_a_digest_ignores_the_page_header_the_history_note_and_line_endings(tmp_path: Path):
    _export(tmp_path, {"9901": FIRST, "9910": "Other words."}, session="2025")
    first = law_text.section_digest("CIV 9901", tmp_path)
    assert first == law_text.words_digest(f"9901. (Added by Stats. 2099, Ch. 1.)\n\n{FIRST}") and len(first) == 64
    assert law_text.section_digest("civ-9901", tmp_path) == first and law_text.section_digest("CIV 9901(b)", tmp_path) == first
    assert law_text.section_digest("CIV 9999", tmp_path) is None
    # The same words under another session's header, with CRLF endings, trailing spaces, and jason's History note.
    page = _page(tmp_path)
    text = page.read_text(encoding="utf-8").replace("2025 session", "2026 session")
    text = text.replace("## CIV 9901\n", "## CIV 9901\n\n- History: amended by a made-up act\n").replace("writing.", "writing.   ")
    page.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    assert law_text.section_digest("CIV 9901", tmp_path) == first
    held = law_text.law_text("CIV 9901", tmp_path)
    assert held.words.endswith("ten days before the hearing.") and "History" not in held.words
    assert held.note == "amended by a made-up act" and "2026 session" in held.source
    # The manifest records each section's digest with its citation, in the page's order.
    manifest = json.loads((tmp_path / AUTHORITIES_DIR / MANIFEST).read_text(encoding="utf-8"))
    assert manifest["pages"][0]["digests"] == [["CIV 9901", first], ["CIV 9910", law_text.section_digest("CIV 9910", tmp_path)]]
    assert law_text.words_digest("a\nb") != law_text.words_digest("a\nc")


def test_a_changed_section_is_copied_to_the_history_and_logged(tmp_path: Path):
    report = _export(tmp_path, {"9901": FIRST, "9910": "Other words."}, session="2025")
    assert report.changed == [] and law_text.changes(tmp_path) == []
    old = law_text.section_digest("CIV 9901", tmp_path)
    report = _export(tmp_path, {"9901": SECOND, "9910": "Other words."}, session="2026")
    new = law_text.section_digest("CIV 9901", tmp_path)
    assert new != old and [c["citation"] for c in report.changed] == ["CIV 9901"] and "changed=1" in report.summary()
    row = law_text.changes(tmp_path, "CIV 9901")[0]
    assert (row["old"], row["new"], row["when"]) == (old, new, date.today().isoformat())
    assert "2025 session" in row["old_source"] and "2026 session" in row["new_source"]
    kept = tmp_path / row["history"]
    assert kept == tmp_path / "authorities" / "history" / "CIV-9901" / f"{old}.md"
    text = kept.read_text(encoding="utf-8")
    assert "- Source: California Legislature, 2025 session publication" in text and "ten days before" in text
    # The replaced words are kept, not searched: the passage index takes the page and leaves the history out.
    from jason.community.passage_index import SOURCES

    law = next(s for s in SOURCES if s.catalog == "authorities").files(tmp_path)
    assert _page(tmp_path) in law and kept not in law
    # The current words, the replaced words by their digest (whole or its first characters), and a digest never held.
    assert "fifteen days" in law_text.law_text("CIV 9901", tmp_path).words
    was = law_text.law_text("CIV 9901", tmp_path, digest=old)
    assert "ten days" in was.words and not was.current and was.digest == old and was.session == "2025"
    assert law_text.law_text("CIV 9901", tmp_path, digest=old[:12]).digest == old
    assert law_text.law_text("CIV 9901", tmp_path, digest=new).current
    assert law_text.law_text("CIV 9901", tmp_path, digest="0" * 64) is None
    # The same words again are no change: nothing more is logged.
    assert _export(tmp_path, {"9901": SECOND, "9910": "Other words."}, session="2027").changed == []
    assert len(law_text.changes(tmp_path)) == 1
    # A section the next export no longer has is kept too, with no new digest.
    gone = _export(tmp_path, {"9901": SECOND}, session="2027").changed
    assert [(c["citation"], c["new"]) for c in gone] == [("CIV 9910", "")]
    assert "Other words." in law_text.history_texts("CIV 9910", tmp_path)[0].words


def test_the_backfill_records_digests_for_pages_on_disk_and_reports_what_it_found(tmp_path: Path):
    _export(tmp_path, {"9901": FIRST, "9910": "Other words."})
    path = tmp_path / AUTHORITIES_DIR / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for page in manifest["pages"]:
        page.pop("digests")
    # A page with no section heading, a page listed but not on disk, and a second page holding CIV 9901.
    (tmp_path / AUTHORITIES_DIR / "CIV" / "empty.md").write_text("# CIV 9930: nothing under it\n", encoding="utf-8")
    (tmp_path / AUTHORITIES_DIR / "CIV" / "again.md").write_text("# CIV 9901: again\n\n## CIV 9901\n\nDifferent words.\n", encoding="utf-8")
    row = dict(manifest["pages"][0])
    manifest["pages"] += [{**row, "file": "authorities/CIV/empty.md", "citation": "CIV 9930", "start": "9930", "end": "9930", "sections": []},
                          {**row, "file": "authorities/CIV/gone.md", "citation": "CIV 9940", "start": "9940", "end": "9940", "sections": ["9940"]},
                          {**row, "file": "authorities/CIV/again.md", "citation": "CIV 9901", "start": "9901", "end": "9901", "sections": ["9901"]}]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    report = backfill(tmp_path)
    assert (report.pages, report.sections, report.written) == (4, 3, True)
    assert report.no_sections == ["authorities/CIV/empty.md"]
    assert report.unparsed == ["authorities/CIV/gone.md: listed in the manifest, not on disk"]
    assert report.duplicates == [{"citation": "CIV 9901", "pages": ["authorities/CIV/CIV-9901-9910.md", "authorities/CIV/again.md"], "same": False}]
    assert report.drift == [] and any("3 sections digested on 4 pages" in line for line in report.lines())
    pages = authority_pages(tmp_path)
    assert pages[0].digests[0] == ["CIV 9901", law_text.section_digest("CIV 9901", tmp_path)] and pages[1].digests == []
    # A page changed by hand since the manifest recorded its digest is drift.
    page = tmp_path / pages[0].file
    page.write_text(page.read_text(encoding="utf-8").replace("ten days", "nine days"), encoding="utf-8")
    assert [d["citation"] for d in backfill(tmp_path, write=False).drift] == ["CIV 9901"]


def test_a_section_printed_in_two_versions_keeps_both_and_a_reading_names_the_one_it_read(tmp_path: Path):
    _export(tmp_path, {"9901": FIRST})
    page = _page(tmp_path)
    # The publication prints some sections twice under one number, and some numbers end in a letter.
    page.write_text(page.read_text(encoding="utf-8") + f"\n## CIV 9901\n\n9901. (Repealed and added by Stats. 2099, Ch. 2.)\n\n{SECOND}\n"
                    "\n## CIV 9901a\n\nLettered words.\n", encoding="utf-8")
    path = tmp_path / AUTHORITIES_DIR / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["pages"][0]["sections"] = ["9901", "9901", "9901a"]
    path.write_text(json.dumps(manifest), encoding="utf-8")
    report = backfill(tmp_path)
    assert report.sections == 3 and report.unparsed == [] and report.duplicates == []
    assert report.versions == [{"citation": "CIV 9901", "page": "authorities/CIV/CIV-9901-9910.md", "count": 2}]
    held = law_text.versions("CIV 9901", tmp_path)
    assert len(held) == 2 and "ten days" in held[0].words and "fifteen days" in held[1].words
    assert law_text.section_digest("CIV 9901", tmp_path) == held[0].digest
    assert law_text.law_text("CIV 9901", tmp_path, digest=held[1].digest).words == held[1].words
    assert law_text.law_text("CIV-9901a", tmp_path).words == "Lettered words."
    assert [pair[0] for pair in authority_pages(tmp_path)[0].digests] == ["CIV 9901", "CIV 9901", "CIV 9901a"]
    # A reading of the second version is current, and the recital gives both versions, each with its digest.
    reading = _reading(held[1].digest)
    assert status(reading, tmp_path).applies and status(reading, tmp_path).provisions[0].now == held[1].digest
    recital = recite("CIV 9901", tmp_path, [reading])
    lines = recital.lines()
    assert recital.digest == held[0].digest and [o.digest for o in recital.others] == [held[1].digest]
    assert "CIV 9901, version 2 of 2 on the shelf" in lines and any("holds 2 versions" in line for line in lines)
    assert any(f"Reads CIV 9901 digest {held[1].digest[:12]}." in line for line in lines)
    # An export that brings one version back keeps the other in the history.
    changed = _export(tmp_path, {"9901": FIRST}).changed
    assert sorted((c["citation"], c["old"], c["new"]) for c in changed) == [
        ("CIV 9901", held[1].digest, held[0].digest), ("CIV 9901a", law_text.words_digest("Lettered words."), "")]
    assert status(reading, tmp_path).state is ReadingState.STALE


def _reading(digest: str, **changes):
    row = {"key": "notice-days", "provisions": (Provision("CIV 9901", digest),), "question": "Are the ten days calendar days?",
           "standing": ReadingStanding.READING, "whose": Whose.BOARD, "dated": date(2099, 3, 1),
           "reading": "The days are calendar days.", "canon": Canon.ORDINARY_SENSE, "board_item": "B-1"}
    return LawReading(**{**row, **changes})


def test_a_reading_is_current_then_stale_after_the_words_change_and_recite_lists_it_apart(tmp_path: Path):
    _export(tmp_path, {"9901": FIRST})
    old = law_text.section_digest("CIV 9901", tmp_path)
    reading = _reading(old)
    found = status(reading, tmp_path)
    assert found.state is ReadingState.CURRENT and found.applies and found.changed == ()
    recital = recite("CIV-9901", tmp_path, [reading])
    assert recital.found and recital.digest == old and "2025 session" in recital.source
    assert recital.words == law_text.law_text("CIV 9901", tmp_path).words and "ten days before the hearing." in recital.words
    assert [r.reading.key for r in recital.readings] == ["notice-days"] and recital.not_applied == ()
    lines = recital.lines()
    # The words come first; the reading follows, labeled as a reading, whose it is, and its date.
    words_at = next(i for i, line in enumerate(lines) if "ten days before the hearing." in line)
    reading_at = next(i for i, line in enumerate(lines) if "The days are calendar days." in line)
    assert lines[0] == "CIV 9901" and f"Digest of these words: {old}" in lines and words_at < reading_at
    assert "The board reads this to mean (2099-03-01; a reading, not the words)" in lines[reading_at]
    assert "ordinary sense (CIV 1644)" in lines[reading_at] and "Board item B-1" in lines[reading_at]

    _export(tmp_path, {"9901": SECOND}, session="2026")
    new = law_text.section_digest("CIV 9901", tmp_path)
    found = status(reading, tmp_path)
    assert found.state is ReadingState.STALE and not found.applies
    changed = found.changed[0]
    assert (changed.citation, changed.read, changed.now) == ("CIV 9901", old, new) and f"CIV-9901/{old}.md" in changed.detail
    recital = recite("CIV 9901", tmp_path, [reading])
    assert "fifteen days before the hearing." in recital.words and recital.digest == new
    assert recital.readings == () and [r.reading.key for r in recital.stale] == ["notice-days"]
    lines = recital.lines()
    apart = lines.index("Not applied (redone or confirmed against the words on disk before any use):")
    assert any("No reading of these words is stored" in line for line in lines[:apart])
    assert "STALE" in lines[apart + 1] and old[:12] in lines[apart + 1] and new[:12] in lines[apart + 1]
    assert not any("reads this to mean" in line for line in lines)
    assert not any("calendar days" in line for line in recital.lines(stale=False))
    # A reading of the new words is current again; one reading a section that is not on the shelf is missing.
    assert status(_reading(new[:16]), tmp_path).state is ReadingState.CURRENT
    both = _reading(new, provisions=(Provision("CIV 9901", new), Provision("CIV 9999", "a" * 12)))
    missing = status(both, tmp_path)
    assert missing.state is ReadingState.MISSING and [p.citation for p in missing.changed] == ["CIV 9999"]
    assert [r.reading.key for r in recite("CIV 9901", tmp_path, [both]).not_applied] == ["notice-days"]


def test_a_plain_record_quotes_the_words_and_carries_no_reading(tmp_path: Path):
    _export(tmp_path, {"9901": FIRST})
    digest = law_text.section_digest("CIV 9901", tmp_path)
    plain = _reading(digest, standing=ReadingStanding.PLAIN, whose=Whose.COUNSEL, reading="", canon=None,
                     question="Must the notice be written?", quote="A notice shall be given in writing.")
    assert plain.reading == "" and status(plain, tmp_path).state is ReadingState.CURRENT
    lines = recite("CIV 9901", tmp_path, [plain]).lines()
    assert any("Counsel finds the words plain (2099-03-01)" in line and "\"A notice shall be given in writing.\"" in line for line in lines)
    assert not any("reads this to mean" in line for line in lines)
    with pytest.raises(ValueError, match="carries no reading"):
        _reading(digest, standing=ReadingStanding.PLAIN)
    # Words the record points to that are not in the provision are a misquote: not applied.
    wrong = _reading(digest, standing=ReadingStanding.PLAIN, reading="", canon=None, quote="A notice may be given orally.")
    assert status(wrong, tmp_path).state is ReadingState.MISQUOTED and recite("CIV 9901", tmp_path, [wrong]).readings == ()
    elided = _reading(digest, standing=ReadingStanding.PLAIN, reading="", canon=None, quote="A notice ... ten days before")
    assert status(elided, tmp_path).applies


def test_two_readings_shows_both_and_prefers_neither(tmp_path: Path):
    _export(tmp_path, {"9901": FIRST})
    digest = law_text.section_digest("CIV 9901", tmp_path)
    two = _reading(digest, standing=ReadingStanding.TWO_READINGS, reading="", canon=None,
                   alternatives=("The days are calendar days.", "The days are business days."))
    line = next(line for line in recite("CIV 9901", tmp_path, [two]).lines() if "Two readings remain" in line)
    assert "the board asks counsel" in line and "(1) The days are calendar days." in line and "(2) The days are business days." in line
    with pytest.raises(ValueError, match="names both"):
        _reading(digest, standing=ReadingStanding.TWO_READINGS, reading="", alternatives=("only one",))
    with pytest.raises(ValueError, match="canon or authority"):
        _reading(digest, canon=None)
    with pytest.raises(ValueError, match="digest"):
        Provision("CIV 9901", "abc")
    # jason's own reading is a lead, and labeled so.
    lead = _reading(digest, whose=Whose.JASON)
    assert lead.lead and any("jason (a lead; no person has adopted it) reads this" in line for line in recite("CIV 9901", tmp_path, [lead]).lines())


def test_a_profile_with_no_readings_recites_the_words_alone(tmp_path: Path):
    from jason.community import community

    _export(tmp_path, {"9901": FIRST})
    assert community().law_readings() == () and readings(_Profile()) == () and readings(None) == ()
    recital = recite("CIV 9901", tmp_path, readings(_Profile()))
    assert recital.found and recital.readings == () and recital.not_applied == ()
    lines = recital.lines()
    assert "ten days before the hearing." in "\n".join(lines) and lines[-1] == "No reading of these words is stored: the words stand alone."
    miss = recite("CIV 9999", tmp_path, ())
    assert not miss.found and "not on the shelf" in miss.lines()[0]
    with pytest.raises(ValueError, match="same key"):
        readings(_Profile(_reading("a" * 12), _reading("b" * 12)))


def test_as_of_sets_a_later_reading_apart_and_says_when_the_shelf_changed(tmp_path: Path):
    _export(tmp_path, {"9901": FIRST})
    _export(tmp_path, {"9901": SECOND}, session="2026")
    reading = _reading(law_text.section_digest("CIV 9901", tmp_path))
    recital = recite("CIV 9901", tmp_path, [reading], date(2099, 1, 1))
    assert recital.readings == () and [r.reading.key for r in recital.later] == ["notice-days"]
    assert recite("CIV 9901", tmp_path, [reading], date(2099, 12, 31)).later == ()
    early = recite("CIV 9901", tmp_path, [], date(2000, 1, 1))
    assert any("was replaced on" in c and "after 2000-01-01" in c for c in early.caveats)


def test_a_reading_of_a_governing_document_section_is_tied_to_its_words(tmp_path: Path):
    from jason.community.outlines import outline_from_text

    def write(text: str) -> None:
        outline = outline_from_text(text, key="rules", title="Made-Up Rules", kind="operating_rules")
        folder = tmp_path / "outlines"
        folder.mkdir(exist_ok=True)
        (folder / "rules.json").write_text(json.dumps(outline.to_dict()), encoding="utf-8")

    class NoDocuments(_Profile):
        def living_documents(self):
            return ()

        def citable_documents(self):
            return ()

    profile = NoDocuments()
    write("1.1 Pets\nEach unit may keep two pets.\n1.2 Parking\nEach unit has one space.\n")
    first = recite("rules#1.1", tmp_path, (), community=profile)
    assert first.found and "two pets" in first.words and len(first.digest) == 16
    reading = LawReading("pets", (Provision("rules#1.1", first.digest),), "Does a fish count as a pet?",
                         ReadingStanding.READING, Whose.BOARD, date(2099, 3, 1), reading="A fish is not counted.",
                         authority="a made-up resolution")
    assert status(reading, tmp_path, community=profile).applies
    assert [r.reading.key for r in recite("rules#1.1", tmp_path, [reading], community=profile).readings] == ["pets"]
    write("1.1 Pets\nEach unit may keep one pet.\n1.2 Parking\nEach unit has one space.\n")
    again = recite("rules#1.1", tmp_path, [reading], community=profile)
    assert "one pet" in again.words and again.readings == () and [r.reading.key for r in again.stale] == ["pets"]
    assert status(reading, tmp_path, community=profile).changed[0].now == again.digest
    assert not recite("rules#1.9", tmp_path, [], community=profile).found
