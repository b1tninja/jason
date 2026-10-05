"""A review as of a day: the pack recites each provision's words in force that day, labels what the disk does not show,
and attaches each stored reading as a reading.

Every section, act, session publication, document, and reading here is made up ("CIV 9901", "Stats. 2090, Ch. 1",
"Covenants"), and the fake lawlibrary answers from this file: nothing leaves the test.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community import law_text
from jason.community import passage_index as pi
from jason.community import retrieval
from jason.community.authorities import Authority, Basis
from jason.community.context_pack import (CORPUS, LawSection, Recitation, assemble, governing_as_of, governing_section,
                                          section_numbers)
from jason.community.law_readings import Canon, LawReading, Provision, ReadingStanding, Whose, recite
from jason.community.living import LivingDocument, LivingInstrument, SourceKind, SourceRef
from jason.community.outlines import outline_from_text
from jason.community.passages import Passage
from jason.community.prompts import (READING_QUOTED, Audience, FactSource, TaskKind, TaskPrompt, as_of_lines, system_prompt,
                                     task_text, verify)
from jason.community.symbols import DocumentKind
from jason.sources.lawlibrary import LawLibrary
from jason.tasks import review_store
from jason.tasks.export_authorities import AUTHORITIES_DIR, MANIFEST, authority_pages, export_authorities
from jason.tasks.manager_review import messages, report, run
from jason.tasks.statute_fetch import prior_versions

GOVERNING = CORPUS[1][0]
GOLDEN = Path(__file__).parent / "fixtures" / "context_pack" / "law_no_as_of.md"

# --- the law: a shelf with history ------------------------------------------------------------------------------------

EDITIONS = ["2091", "2093", "2095", "2097"]
OLD = "(a) A notice of the hearing shall be given in writing.\n\n(b) The notice is given fifteen days before the hearing."
NEW = "(a) A notice of the hearing shall be given in writing.\n\n(b) The notice is given fourteen days before the hearing."
FINE = "(a) A fine is imposed only after the hearing.\n\n(b) The member may speak at the hearing before the fine is imposed."
UNTIL = ("(a) The hearing is held in a closed session.\n\n(b) This section shall remain in effect only until January 1, 2099, "
         "and as of that date is repealed.")
FROM = "(a) The hearing is held in an open session.\n\n(b) This section shall be operative January 1, 2099."
ONE = "(a) A notice of the fine is mailed to the member after the hearing."
TWO = "(a) A notice of the fine is delivered to the member after the hearing."
SPANS = (Authority("CIV", "9901", "9910", "a made-up chapter", Basis.DUTY),)


def _note(words: str, citation: str, effective: str, bill: str) -> dict:
    return {"note": words, "read": True, "citation": citation, "bill": bill, "effective": effective, "operative": "",
            "dates": [{"occasion": "effective", "day": effective, "by": ""}], "statute": {"year": citation[7:11]},
            "enacted": "", "measure": ""}


def _row(session: str, number: str, title: str, text: str, note: dict) -> dict:
    return {"citation": f"CIV {number}", "code": "CIV", "section": number, "title": title, "text": text, "session": session,
            "history": note["note"], "note": note}


ADDED = _note("Added by Stats. 2090, Ch. 1, Sec. 2.   (AB 1)   Effective January 1, 2091.", "Stats. 2090, Ch. 1, Sec. 2",
              "2091-01-01", "AB 1")
AMENDED = _note("Amended by Stats. 2095, Ch. 7, Sec. 1.   (AB 7)   Effective June 30, 2095.", "Stats. 2095, Ch. 7, Sec. 1",
                "2095-06-30", "AB 7")
OLD_TITLE = "9901. (Added by Stats. 2090, Ch. 1, Sec. 2.)"
NEW_TITLE = "9901. (Amended by Stats. 2095, Ch. 7, Sec. 1.)"
FINE_TITLE = "9903. (Added by Stats. 2090, Ch. 1, Sec. 2.)"
ROWS = [_row("2091", "9901", OLD_TITLE, OLD, ADDED), _row("2093", "9901", OLD_TITLE, OLD, ADDED),
        _row("2095", "9901", NEW_TITLE, NEW, AMENDED), _row("2097", "9901", NEW_TITLE, NEW, AMENDED),
        *(_row(session, "9903", FINE_TITLE, FINE, ADDED) for session in EDITIONS)]


def _library(tmp_path: Path) -> LawLibrary:
    """A lawlibrary whose worker answers a span from the newest publication's rows and ``versions`` from every one's."""
    def run(payload):
        out = {"spans": [], "acts": {}, "versions": []}
        for code, start, end in payload.get("spans", []):
            printed = [r for r in ROWS if r["session"] == EDITIONS[-1] and float(start) <= float(r["section"]) <= float(end)]
            out["spans"].append({"code": code, "start": start, "end": end, "sections": [
                {**{k: r[k] for k in ("citation", "code", "section", "title", "text", "session")},
                 "path": [{"heading": "CHAPTER 1. Made Up [9900. - 9999.]"}]} for r in printed]})
        for asked in payload.get("versions", []):
            out["versions"].append({"code": asked["code"], "editions": EDITIONS,
                                    "rows": [r for r in ROWS if r["section"] in asked["sections"]]})
        return out

    return LawLibrary(tmp_path, run=run)


def _shelf(data: Path) -> None:
    """CIV 9901 amended in 2095 with its earlier words in the history; CIV 9903 unchanged since 2091; CIV 9902 printed
    in two versions whose own words say when each operates; CIV 9904 printed in two that do not."""
    export_authorities(_library(data), data, spans=SPANS, acts=())
    prior_versions(data, ["CIV 9901", "CIV 9903"], library=_library(data), when="2099-01-02")
    page = data / authority_pages(data)[0].file
    page.write_text(page.read_text(encoding="utf-8")
                    + f"\n## CIV 9902\n\n(Repealed (in Sec. 3) and added by Stats. 2090, Ch. 3, Sec. 4.)\n\n{FROM}\n"
                    + f"\n## CIV 9902\n\n(Amended by Stats. 2090, Ch. 3, Sec. 3.)\n\n{UNTIL}\n"
                    + f"\n## CIV 9904\n\n(Added by Stats. 2090, Ch. 4, Sec. 1.)\n\n{ONE}\n"
                    + f"\n## CIV 9904\n\n(Added by Stats. 2090, Ch. 5, Sec. 1.)\n\n{TWO}\n", encoding="utf-8")
    path = data / AUTHORITIES_DIR / MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["pages"][0]["sections"] += ["9902", "9902", "9904", "9904"]
    path.write_text(json.dumps(manifest), encoding="utf-8")


# --- the governing documents ------------------------------------------------------------------------------------------

TEN = "The Board shall give an Owner ten days written notice of the hearing before a fine is imposed on the Owner."
FIFTEEN = TEN.replace("ten days", "fifteen days")
DECISION = "The Board shall give the Owner written notice of its decision within ten days after the hearing is held."
SCHEDULE = "A fine is imposed only under the schedule of fines the Board adopts and distributes to the Owners."
BASE = f"ARTICLE 6\n6.2 Hearings.\n(a) Notice. {TEN}\n(b) Decision. {DECISION}\n6.3 Fines. {SCHEDULE}\n"
COVENANTS = BASE.replace(TEN, FIFTEEN)                     # the copy on disk: the document as it reads now
RULES = ("1.1 Hearing\nAn Owner may attend the hearing and speak to the Board before a fine is imposed on the Owner.\n"
         "1.2 Payment\nA fine is due thirty days after the Board gives notice of its decision on the hearing.\n")
FLYER = "A reminder to every Owner: the notice of the hearing on a fine is posted at the mail room for the Owners to read."


def _run(text: str, bold: bool = False, strike: bool = False) -> dict:
    return {"textRun": {"content": text, "textStyle": {"bold": bold, "strikethrough": strike}}}


def _amendment() -> dict:
    """An amendment as a Doc: 6.2(a)'s ten days struck, fifteen days added."""
    before, after = TEN.split("ten days")
    paragraphs = [
        [_run("NOW, THEREFORE, the Association declares:\n")],
        [_run("Article 6, Section 6.2, subsection (a) (\"Notice\") is hereby amended and restated as follows "
              "(stricken out wording will be removed, and bolded wording will be added):\n")],
        [_run(before), _run("ten days", strike=True), _run(" "), _run("fifteen days", bold=True), _run(after + "\n")],
        [_run("IN WITNESS WHEREOF, the Board.\n")],
    ]
    return {"revisionId": "rev-1", "body": {"content": [{"paragraph": {"elements": p}} for p in paragraphs]}}


def _documents(data: Path) -> LivingDocument:
    """"Covenants", kept as amended (an amendment recorded March 1, 2094), and "Made-Up Rules", kept only as they read
    now; their extracts in the governing folder, their outlines, and a flyer no outline knows."""
    lib = data / "library"
    (lib / "text").mkdir(parents=True)
    with sqlite3.connect(lib / "library.db") as conn:
        conn.execute("CREATE TABLE documents (id TEXT, path TEXT, kind TEXT, confidential INTEGER, sha256 TEXT)")
        conn.execute("INSERT INTO documents VALUES ('1', 'Governing/Covenants.pdf', 'declaration', 0, 'abc')")
    (lib / "text" / "1.txt").write_text(BASE, encoding="utf-8")
    sources = data / "living" / "decl" / "sources"
    sources.mkdir(parents=True)
    (sources / "doc-2.json").write_text(json.dumps(_amendment()), encoding="utf-8")
    first = SimpleNamespace(title="First Amendment", recorded=date(2094, 3, 1), adopted=None, recorder_number="209403010001")
    living = LivingDocument("decl", "Covenants", DocumentKind.DECLARATION,
                            base=SourceRef(SourceKind.LIBRARY_TEXT, "Governing/Covenants.pdf", sha256="abc"),
                            base_from="the recorded copy",
                            instruments=(LivingInstrument("decl-1st", first, SourceRef(SourceKind.DOC, "doc-2")),))
    governing = data / GOVERNING
    governing.mkdir(parents=True)
    (governing / "Covenants.md").write_text(COVENANTS, encoding="utf-8")
    (governing / "Made-Up Rules.md").write_text(RULES, encoding="utf-8")
    (governing / "Flyer.md").write_text(FLYER, encoding="utf-8")
    outlines = data / "outlines"
    outlines.mkdir()
    for key, title, kind, text in (("decl", "Covenants", "declaration", COVENANTS), ("rules", "Made-Up Rules", "operating_rules", RULES)):
        (outlines / f"{key}.json").write_text(json.dumps(outline_from_text(text, key=key, title=title, kind=kind).to_dict()),
                                              encoding="utf-8")
    return living


class FakeEmbedder:
    def _vec(self, text: str) -> list[float]:
        v = [0.0] * 16
        for word in text.lower().split():
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % 16] += 1.0
        return retrieval._normalize(v)

    def embed_passages(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


class Community:
    """A throwaway profile: its context line, a file's kind, the documents it keeps, and its readings."""

    def __init__(self, living: LivingDocument, rows: tuple = ()):
        self.living, self.rows = living, rows

    def prompt_context(self):
        return ["Example Commons, 12 units"]

    def classify_document(self, name, folder=None):
        if name.startswith("Covenants"):
            return DocumentKind.DECLARATION
        if "Rules" in name:
            return DocumentKind.OPERATING_RULES
        return DocumentKind.NOTICE if name.startswith("Flyer") else None

    def living_documents(self):
        return (self.living,)

    def citable_documents(self):
        return ()

    def law_readings(self):
        return self.rows


TASK = TaskPrompt(TaskKind.HEARING_NOTICE, "A notice of a hearing.", Audience.BOARD,
                  topics=("the notice of the hearing", "when a fine is imposed"),
                  documents=(DocumentKind.DECLARATION, DocumentKind.OPERATING_RULES, DocumentKind.NOTICE,
                             DocumentKind.CORRESPONDENCE),
                  facts=(FactSource("open_items", why="what is open"),),
                  considerations=("Does it say when the hearing is held?",))
ASK = "How many days before the hearing is the notice given?"
LETTER = ("Hearing letter.pdf", "2092-04", "A letter giving an Owner notice of the hearing on a fine.")
EARLY, LATE, BEFORE_ALL = date(2092, 5, 1), date(2096, 1, 1), date(2089, 1, 1)


def _readings(data: Path, profile: Community) -> tuple[LawReading, ...]:
    """The profile's readings, each tied to the digest of the words it read."""
    old = next(t for t in law_text.history_texts("CIV 9901", data) if "fifteen days" in t.words).digest
    new = law_text.section_digest("CIV 9901", data)
    fine = law_text.section_digest("CIV 9903", data)
    ten = recite("decl#6.2(a)", data, (), EARLY, community=profile).digest
    speak = recite("rules#1.1", data, (), community=profile).digest
    return (
        LawReading("notice-days", (Provision("CIV 9901", old),), "Are the days calendar days?", ReadingStanding.READING,
                   Whose.BOARD, date(2092, 1, 1), reading="The days are calendar days.", canon=Canon.ORDINARY_SENSE),
        LawReading("notice-written", (Provision("CIV 9901", new),), "Must the notice be written?", ReadingStanding.PLAIN,
                   Whose.COUNSEL, date(2095, 7, 1), quote="A notice of the hearing shall be given in writing."),
        LawReading("fine-after", (Provision("CIV 9903", fine),), "May the fine be set at the hearing itself?",
                   ReadingStanding.TWO_READINGS, Whose.BOARD, date(2091, 6, 1),
                   alternatives=("The fine may be set when the hearing closes.", "The fine is set at a later meeting.")),
        LawReading("covenant-days", (Provision("decl#6.2(a)", ten),), "Does the day of the hearing count?",
                   ReadingStanding.READING, Whose.COUNSEL, date(2092, 2, 1), reading="The day of the hearing is not counted.",
                   authority="a made-up opinion letter"),
        LawReading("rules-speak", (Provision("rules#1.1", speak),), "May a tenant speak for the Owner?",
                   ReadingStanding.READING, Whose.JASON, date(2092, 3, 1), reading="A tenant may speak with the Owner's letter.",
                   canon=Canon.GIVE_EFFECT),
    )


@pytest.fixture()
def world(tmp_path: Path) -> tuple[Path, Community]:
    _shelf(tmp_path)
    profile = Community(_documents(tmp_path))
    profile.rows = _readings(tmp_path, profile)
    pi.build(tmp_path, sources=(pi.IndexSource("records", GOVERNING, pi.Standing.RECORD),
                                pi.IndexSource("authorities", "authorities", pi.Standing.AUTHORITY)),
             embedder=FakeEmbedder(), kind_of=lambda name: "")
    return tmp_path, profile


def _pack(world: tuple[Path, Community], **kw):
    data, profile = world
    return assemble(profile, TASK, data, mode="keyword", ask=kw.pop("ask", ASK),
                    files=lambda kind: [LETTER] if kind is DocumentKind.CORRESPONDENCE else [],
                    fact_runner=lambda tool, args: {"tool": tool, "open": 2}, **kw)


def _told(pack) -> str:
    page = pack.markdown()
    told = page[page.index("## Task"):] + "\n=== sources_text ===\n" + pack.sources_text() + "\n"
    # A section printed twice is labeled with the day it was asked about (today, with no as-of date): keep the page
    # the same on any day.
    return told.replace(date.today().isoformat(), "TODAY")


def test_without_an_as_of_date_the_pack_is_what_it_was(world):
    """The page below was written by the pack as it stood before a review took an as-of date, from this fixture: a
    shelf with history, two sections printed twice, documents kept by section, and a profile with readings
    (JASON_WRITE_GOLDEN=1 writes it again after a change that is meant to move it)."""
    pack = _pack(world)
    told = _told(pack)
    if os.environ.get("JASON_WRITE_GOLDEN"):
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(told, encoding="utf-8", newline="\n")
    assert told == GOLDEN.read_text(encoding="utf-8")


def _law(pack, citation: str):
    return next(s for s in pack.sources if s.id.startswith("S") and s.title == citation)


def _governing(pack, words: str):
    return next(s for s in pack.sources if s.id.startswith("G") and words in s.text)


def test_without_a_day_a_law_source_still_carries_its_digest_and_nothing_else_is_new(world):
    data, _ = world
    pack = _pack(world)
    assert pack.as_of is None and pack.as_of_lines() == () and pack.task_prompt() == task_text(TASK, ask=ASK)
    assert pack.reading_texts() == {} and pack.texts() == {s.id: s.text for s in pack.sources} and not pack.gaps
    # The digest is the one the shelf and ``jason readings`` give for those words, taken from the words in hand.
    assert _law(pack, "CIV 9901").provision == Recitation("CIV 9901", law_text.section_digest("CIV 9901", data))
    assert sorted(s.provision.digest for s in pack.sources if s.title == "CIV 9902") == sorted(
        t.digest for t in law_text.versions("CIV 9902", data))
    assert all(s.provision is None for s in pack.sources if not s.id.startswith("S"))
    assert "calendar days" not in pack.markdown() and "In force on" not in pack.markdown()


def test_as_of_an_earlier_day_a_law_source_is_the_earlier_words_with_their_range(world):
    data, _ = world
    pack = _pack(world, as_of=EARLY)
    notice = _law(pack, "CIV 9901")
    assert "fifteen days before the hearing." in notice.text and "fourteen" not in notice.text
    recited = notice.provision
    assert (recited.shown, recited.decided, recited.as_of) == (True, "prior", EARLY)
    assert recited.digest == next(t for t in law_text.history_texts("CIV 9901", data) if "fifteen" in t.words).digest
    assert ("In force on 2092-05-01: from 2091-01-01 until 2095-06-30; made by Stats. 2090, Ch. 1, Sec. 2 (AB 1); "
            "ended by Stats. 2095, Ch. 7, Sec. 1 (AB 7)") in recited.above
    assert f"Digest of these words: {recited.digest}" in recited.above
    assert any(a.startswith("Caveat: these are not the words on the shelf now") for a in recited.above)
    assert notice.note == "found for the task's topics; in force on 2092-05-01"
    # A section unchanged since before the day is the current words, said to be in force by a record.
    fine = _law(pack, "CIV 9903").provision
    assert (fine.shown, fine.decided) == (True, "current") and fine.digest == law_text.section_digest("CIV 9903", data)
    assert "In force on 2092-05-01: from 2091-01-01; made by Stats. 2090, Ch. 1, Sec. 2 (AB 1)" in fine.above
    # The label and the digest are printed above the words, on the page and in what a model is sent.
    page, sent = pack.markdown(), pack.sources_text()
    assert page.index("- In force on 2092-05-01: from 2091-01-01 until 2095-06-30") < page.index("fifteen days before the hearing.")
    block = next(b for b in sent.split("\n\n[") if b.startswith("S") and "CIV 9901" in b.split("\n")[0])
    assert block.index("ABOUT THE WORDS (not part of them):") < block.index("In force on 2092-05-01") < block.index("THE WORDS:")
    assert block.index("THE WORDS:") < block.index("fifteen days") < block.index("Readings of these words")
    # After the amendment the same source is the current words, in force from the amendment's day.
    later = _law(_pack(world, as_of=LATE), "CIV 9901")
    assert "fourteen days" in later.text and later.provision.decided == "current"
    assert "In force on 2096-01-01: from 2095-06-30; made by Stats. 2095, Ch. 7, Sec. 1 (AB 7)" in later.provision.above


def test_as_of_a_day_the_disk_does_not_cover_the_current_words_carry_the_not_shown_label(world):
    data, _ = world
    pack = _pack(world, as_of=BEFORE_ALL)
    law = [s for s in pack.sources if s.id.startswith("S")]
    assert law and all(s.provision.shown is False and s.provision.decided == "not_shown" for s in law)
    notice = _law(pack, "CIV 9901")
    assert "fourteen days" in notice.text and notice.provision.digest == law_text.section_digest("CIV 9901", data)
    assert notice.note.endswith("NOT SHOWN TO BE IN FORCE on 2089-01-01: the words on the shelf now")
    label = next(a for a in notice.provision.above if a.startswith("Not shown to be in force on 2089-01-01"))
    assert "these are the words on the shelf now" in label
    # What is held, and what would bring the words of that day.
    assert any("an earlier version is held" in a and "which does not include 2089-01-01" in a for a in notice.provision.above)
    assert any("added by a person from an official source" in a for a in notice.provision.above)
    assert any("jason law-history --versions --citation CIV-9902" in a for a in _law(pack, "CIV 9902").provision.above)
    assert pack.gaps[0].startswith(f"as of 2089-01-01: {len(law)} of the {len(law)} law sources are not shown to be in force "
                                   "that day (S1, S2, S3, S4)") and "jason law-history --versions" in pack.gaps[0]
    # A reading dated after the day is no reading on that day.
    assert [(r.key, r.state) for r in notice.provision.readings] == [("notice-days", "later"), ("notice-written", "later")]
    assert "Dated after 2089-01-01 (not a reading on that day):" in notice.provision.below
    # A section the shelf cannot be asked about keeps the words the pack was given, under the same plain label.
    loose = assemble(world[1], TASK, data, mode="keyword", ask=ASK, as_of=EARLY, files=lambda kind: [],
                     fact_runner=lambda tool, args: {}, use_index=False,
                     law=[LawSection("CIV 9950", "a made-up chapter", "A notice of the hearing is posted.")])
    (only,) = [s for s in loose.sources if s.id.startswith("S")]
    assert only.text == "A notice of the hearing is posted." and only.provision.decided == "not_found" and not only.provision.shown
    assert any(a.startswith("Not shown to be in force on 2092-05-01: these are the words the pack was given") for a in only.provision.above)


def test_a_section_printed_in_two_versions_is_one_source_picked_by_its_own_words_or_both(world):
    data, _ = world
    later, sooner = law_text.versions("CIV 9902", data)                   # the publication prints the later one first
    pack = _pack(world, as_of=EARLY)
    assert [s.title for s in pack.sources if s.id.startswith("S")].count("CIV 9902") == 1
    assert [s.id for s in pack.sources if s.id.startswith("S")] == ["S1", "S2", "S3", "S4"]
    session = _law(pack, "CIV 9902")
    assert "closed session" in session.text and "open session" not in session.text
    assert (session.provision.decided, session.provision.digest, session.provision.others) == ("own_words", sooner.digest, ())
    assert ('Own words that decide it: "This section shall remain in effect only until January 1, 2099, and as of that '
            'date is repealed."') in session.provision.above
    assert 'Own words that decide it: "This section shall be operative January 1, 2099."' in session.provision.above
    after = _law(_pack(world, as_of=date(2099, 6, 1)), "CIV 9902")
    assert "open session" in after.text and "closed session" not in after.text and after.provision.digest == later.digest
    # Two versions whose own words state no day: both are given, each with its digest, and nothing is picked.
    one, two = law_text.versions("CIV 9904", data)
    both = _law(pack, "CIV 9904")
    assert "mailed to the member" in both.text and "delivered to the member" in both.text
    assert f"[CIV 9904, version 2 of 2 on the shelf; digest {two.digest}]" in both.text
    assert (both.provision.shown, both.provision.digest, both.provision.others) == (False, one.digest, (two.digest,))
    assert any("their own words do not" in a for a in both.provision.above)
    assert "1 of the 4 law sources are not shown to be in force that day (S2)" in pack.gaps[0]


def test_a_current_reading_is_attached_and_labeled_and_a_stale_one_is_listed_apart(world):
    early, late = _pack(world, as_of=EARLY), _pack(world, as_of=LATE)
    notice = _law(early, "CIV 9901")
    # Under the earlier words: the board's reading of them, labeled as a reading, whose it is, and its date.
    assert [(r.key, r.standing, r.whose, r.state) for r in notice.provision.readings] == [
        ("notice-days", "reading", "board", "current"), ("notice-written", "plain", "counsel", "later")]
    line = next(b for b in notice.provision.below if b.startswith("- [notice-days]"))
    assert "The board reads this to mean (2092-01-01; a reading, not the words): The days are calendar days." in line
    assert notice.provision.below[0] == "Readings of these words (each a reading, not the words):"
    assert "calendar days" not in notice.text and "calendar days" not in early.texts()[notice.id]
    assert early.reading_texts()[notice.id] == "The days are calendar days."
    page = early.markdown()
    assert page.index("fifteen days before the hearing.") < page.index("- [notice-days] The board reads this to mean")
    # Two readings remain: both are named, and the board asks counsel.
    fine = _law(early, "CIV 9903")
    assert [(r.key, r.standing, r.state) for r in fine.provision.readings] == [("fine-after", "two_readings", "current")]
    assert any("Two readings remain (The board, 2091-06-01); the board asks counsel." in b for b in fine.provision.below)
    # After the amendment the board's reading read other words: it is listed as stale and is not applied. Counsel's
    # plain record of the new words is current.
    after = _law(late, "CIV 9901")
    assert [(r.key, r.state) for r in after.provision.readings] == [("notice-written", "current"), ("notice-days", "stale")]
    apart = after.provision.below.index("Not applied (redone or confirmed against the words on disk before any use):")
    assert after.provision.below[apart + 1].startswith("- [notice-days] STALE: The board, 2092-01-01")
    assert any("Counsel finds the words plain (2095-07-01)" in b for b in after.provision.below[:apart])
    assert not any("reads this to mean" in b for b in after.provision.below)
    # A profile with no reading: the words stand alone, and the pack says so.
    bare = _pack((world[0], Community(world[1].living)), as_of=EARLY)
    assert _law(bare, "CIV 9901").provision.below == ("No reading of these words is stored: the words stand alone.",)
    assert bare.reading_texts() == {}


def test_a_governing_passage_is_recited_by_the_section_its_heading_names(world):
    assert section_numbers("Bylaws > ARTICLE 7 MEETINGS > 7.2 Notice of Meetings > 7.2(c)") == ["7.2(c)", "7.2", "7"]
    assert section_numbers("Handbook > B-18 > b) Due Process") == ["B-18"] and section_numbers("Flyer") == []
    early, late = _pack(world, as_of=EARLY), _pack(world, as_of=LATE)
    # A document kept as amended, on a day before its amendment: the file's copy reads as it does now, so the
    # section's words on that day are given under the passage, and a quote of them checks.
    notice = _governing(early, "(a) Notice.")
    recited = notice.provision
    assert "fifteen days" in notice.text and "ten days written notice" in recited.words and "fifteen" not in recited.words
    assert (recited.citation, recited.shown, recited.decided) == ("decl#6.2(a)", True, "as_amended_below")
    assert recited.words_title == f"decl#6.2(a) as amended to 2092-05-01 (digest {recited.digest}; Covenants):"
    assert any("its words are not the words of decl#6.2(a) as jason keeps the document amended to 2092-05-01" in a
               for a in recited.above)
    assert notice.note == "in force on 2092-05-01: the words of decl#6.2(a) under the passage"
    assert "ten days written notice" in early.texts()[notice.id] and "fifteen days" in early.texts()[notice.id]
    page = early.markdown()
    assert page.index("(a) Notice. The Board shall give an Owner fifteen days") < page.index(recited.words_title) \
        < page.index("ten days written notice of the hearing") < page.index("- [covenant-days] Counsel reads this to mean")
    assert [(r.key, r.whose, r.state, r.provision) for r in recited.readings] == [("covenant-days", "counsel", "current", "decl#6.2(a)")]
    # A passage that is its section's words on the day is in force, with nothing repeated under it.
    decision = _governing(early, "(b) Decision.").provision
    assert (decision.citation, decision.shown, decision.decided, decision.words) == ("decl#6.2(b)", True, "as_amended", "")
    assert any(a.startswith("In force on 2092-05-01: the passage's words are in decl#6.2(b)") for a in decision.above)
    # After the amendment the file's copy is the section as amended, and counsel's reading of the old words is stale.
    amended = _governing(late, "(a) Notice.").provision
    assert (amended.decided, amended.words) == ("as_amended", "") and amended.digest != recited.digest
    assert [(r.key, r.state) for r in amended.readings] == [("covenant-days", "stale")]
    assert any("First Amendment" in a for a in amended.above)
    # A document kept only as it reads now: labeled, its section named, and a reading of the section attached as a lead.
    speak = _governing(early, "1.1 Hearing")
    assert (speak.provision.citation, speak.provision.shown, speak.provision.decided) == ("rules#1.1", False, "not_kept")
    assert any(a.startswith("Not shown to be in force on 2092-05-01: rules is not kept as amended.") for a in speak.provision.above)
    assert any("jason (a lead; no person has adopted it) reads this to mean" in b for b in speak.provision.below)
    assert speak.note == "NOT SHOWN TO BE IN FORCE on 2092-05-01: the file as it reads now"
    # A passage whose heading names no section: the label says why, and no reading is attached.
    flyer = _governing(early, "A reminder to every Owner").provision
    assert (flyer.citation, flyer.shown, flyer.decided, flyer.readings, flyer.below) == ("", False, "unnamed", (), ())
    assert "its heading names no numbered section" in flyer.above[-1] and "no reading is attached by section" in flyer.above[-1]
    assert early.gaps[-1].startswith("as of 2092-05-01: 3 of the 6 governing sources are not shown to be in force that day (G4, G5, G6)")
    # A reading of the section around the passage's is listed too, under the section it reads.
    data, profile = world
    around = LawReading("hearings", (Provision("decl#6.2", recite("decl#6.2", data, (), EARLY, community=profile).digest),),
                        "Is a hearing held for every fine?", ReadingStanding.PLAIN, Whose.BOARD, date(2092, 1, 5))
    wider = _governing(_pack((data, Community(profile.living, (*profile.rows, around))), as_of=EARLY), "(b) Decision.").provision
    assert [(r.key, r.provision) for r in wider.readings] == [("hearings", "decl#6.2")]
    assert any(b.startswith("Of decl#6.2, a section the passage sits in (digest ") for b in wider.below)
    # A passage cut by words carries no heading, and a file no outline matches names no document: a miss with its
    # reason. A number the heading names counts only when the document has that section with the passage's words.
    file = data / GOVERNING / "Covenants.md"
    assert governing_section(Passage(file, 0, 0, FIFTEEN), data, profile, EARLY)[3] == "it was cut by words and carries no section heading"
    stray = Passage(data / GOVERNING / "Flyer.md", 0, 0, FLYER, heading="Flyer > 6.3 Fines")
    assert governing_section(stray, data, profile, EARLY)[3] == "no outline of a document jason keeps matches its file"
    wrong = Passage(file, 0, 0, "Twelve units share the pool and the pool is closed in winter.", heading="Covenants > 6.3 Fines.")
    assert governing_section(wrong, data, profile, EARLY)[::3] == (None, "the passage's words are not those of decl#6.3 as jason keeps it")
    gone = governing_as_of(Passage(file, 0, 0, FIFTEEN, heading="Covenants > 9.9 Pools"), data, profile, EARLY)[1]
    assert gone.decided == "unnamed" and "decl has no section 9.9" in gone.above[-1]


def test_the_task_is_told_how_to_use_the_day_and_what_a_reading_is(world):
    pack = _pack(world, as_of=EARLY)
    told = pack.task_prompt()
    assert pack.as_of_lines() == as_of_lines(EARLY) and told == task_text(TASK, ask=ASK, extra=as_of_lines(EARLY))
    assert told.index("CONSIDER") < told.index("AS OF: 2092-05-01.") < told.index("QUESTION:")
    for words in ("Recite a provision's words as its source gives them for 2092-05-01.",
                  "say so in the answer, and do not rely on them as the law or the rule of that day",
                  "is a reading, labeled with whose it is. It is never the provision's words",
                  "Where two readings remain, say so: the board asks counsel.",
                  "a section repealed since then is not among the sources"):
        assert words in told
    system, user = messages(pack)
    assert system["content"] == system_prompt(("Example Commons, 12 units",)) and "AS OF: 2092-05-01." in user["content"]
    assert "GAPS (not among the sources):\n- as of 2092-05-01: 1 of the 4 law sources" in user["content"]
    # The lines are general: they name no provision, document, or figure.
    assert not re.search(r"\b(CIV|CORP)\b|§|\$\s?\d|section \d", " ".join(as_of_lines(EARLY)))


def test_a_quote_of_the_recited_words_checks_and_a_reading_quoted_as_the_rule_is_flagged(world):
    pack = _pack(world, as_of=EARLY)
    notice, covenant = _law(pack, "CIV 9901"), _governing(pack, "(a) Notice.")
    answer = {"issues": [{"issue": "the notice period", "rules": [
        {"source": notice.id, "quote": "The notice is given fifteen days before the hearing.", "force": "required"},
        {"source": covenant.id, "quote": "ten days written notice of the hearing", "force": "required"},
        {"source": notice.id, "quote": "The days are calendar days.", "force": "required"},          # the board's reading
        {"source": covenant.id, "quote": "The day of the hearing is not counted.", "force": "required"},  # counsel's
        {"source": notice.id, "quote": "The notice is posted at the gate three days after the hearing.", "force": "required"}],
        "facts": [], "application": "", "conclusion": ""}]}
    sent = {}

    def post(url, payload):
        sent.update(payload)
        return {"message": {"content": json.dumps(answer)}}

    checked = run(pack, post=post)
    assert "AS OF: 2092-05-01." in sent["messages"][1]["content"] and checked.grounded == 2
    assert [(u["source"], u["why"]) for u in checked.ungrounded] == [
        (notice.id, READING_QUOTED), (covenant.id, READING_QUOTED), (notice.id, "not found in the source")]
    # Without the readings the check still refuses the quote: a reading is never part of a source's text.
    assert [u["why"] for u in verify(answer, pack.texts()).ungrounded] == ["not found in the source"] * 3
    told = report(pack, checked)
    assert told.startswith("# Review: notice of hearing\n\nAs of 2092-05-01:")
    assert f"\"The days are calendar days.\" **({READING_QUOTED})**" in told
    assert "\"The notice is posted at the gate three days after the hearing.\" **(quote not found)**" in told


def _legacy_digest(pack) -> str:
    """The review's digest as it was before a review took a day."""
    identity = [pack.ask, pack.draft, review_store.collection_key(pack),
                [[s.id, hashlib.sha256(s.text.encode("utf-8")).hexdigest()] for s in pack.sources]]
    return hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode("utf-8")).hexdigest()


def test_two_reviews_of_one_question_as_of_two_days_are_both_kept(world):
    from jason.commands.review import history_lines

    data, profile = world
    plain, early, late = _pack(world), _pack(world, as_of=EARLY), _pack(world, as_of=LATE)
    assert review_store.review_digest(plain) == _legacy_digest(plain)            # with no day, the key it always had
    paths = [review_store.store(p, data, as_of=date(2026, 10, 4)) for p in (plain, early, late)]
    assert len(set(paths)) == 3 and all(p.is_file() for p in paths)
    assert review_store.store(_pack(world, as_of=EARLY), data) == paths[1]       # the same day, the same record
    kept = [json.loads(p.read_text(encoding="utf-8")) for p in paths]
    assert [(k["asOf"], k["asOfNamed"]) for k in kept] == [("2026-10-04", False), ("2092-05-01", True), ("2096-01-01", True)]
    assert all(k["schema"] == 2 and k["firstWritten"] for k in kept)

    # Without a day a law source's row carries its provision's digest and nothing about a day.
    row = next(s for s in kept[0]["sources"] if s["section"] == "CIV 9901")
    assert row["provision"] == {"citation": "CIV 9901", "digest": law_text.section_digest("CIV 9901", data)}
    assert all("provision" not in s for s in kept[0]["sources"] if not s["id"].startswith("S"))
    # As of the earlier day: the earlier words' digest, shown in force, and each reading with its standing and state.
    old = next(t for t in law_text.history_texts("CIV 9901", data) if "fifteen" in t.words).digest
    row = next(s for s in kept[1]["sources"] if s["section"] == "CIV 9901")
    assert row["provision"] == {
        "citation": "CIV 9901", "digest": old, "shown": True, "decided": "prior", "otherVersions": [], "readings": [
            {"key": "notice-days", "standing": "reading", "whose": "board", "dated": "2092-01-01", "state": "current",
             "provision": "CIV 9901"},
            {"key": "notice-written", "standing": "plain", "whose": "counsel", "dated": "2095-07-01", "state": "later",
             "provision": "CIV 9901"}]}
    both = next(s for s in kept[1]["sources"] if s["section"] == "CIV 9904")["provision"]
    assert both["shown"] is False and both["decided"] == "not_shown" and len(both["otherVersions"]) == 1
    covenant = next(s["provision"] for s in kept[1]["sources"]
                    if s["id"].startswith("G") and s["provision"]["citation"] == "decl#6.2(a)")
    assert covenant["decided"] == "as_amended_below" and covenant["readings"][0]["key"] == "covenant-days"
    after = next(s for s in kept[2]["sources"] if s["section"] == "CIV 9901")["provision"]
    assert after["digest"] == law_text.section_digest("CIV 9901", data) and after["decided"] == "current"
    assert [(r["key"], r["state"]) for r in after["readings"]] == [("notice-written", "current"), ("notice-days", "stale")]
    # The record keeps digests and labels, never the words or what a reading says.
    text = paths[1].read_text(encoding="utf-8")
    assert "fifteen days" not in text and "calendar days" not in text

    # A reading that changes hands is a new review of the same question on the same day, not the old one written over.
    adopted = tuple(replace(r, whose=Whose.BOARD) if r.key == "rules-speak" else r for r in profile.rows)
    again = review_store.store(_pack((data, Community(profile.living, adopted)), as_of=EARLY), data)
    assert again not in paths and paths[1].is_file()
    # So is a changed statute: the same day once the earlier words are no longer held.
    for kept_file in (data / "authorities" / "history" / "CIV-9901").glob("*.md"):
        kept_file.unlink()
    changed = _pack(world, as_of=EARLY)
    assert _law(changed, "CIV 9901").provision.decided == "not_shown"
    assert review_store.store(changed, data) not in (*paths, again)

    rows = review_store.history(data, "hearing-notice")
    assert len(rows) == 5 and [r["asOf"] for r in rows] == ["2026-10-04", "2092-05-01", "2092-05-01", "2092-05-01", "2096-01-01"]
    first = next(r for r in rows if r["digest"] == kept[1]["digest"][:16])
    assert (first["asOfNamed"], first["law"], first["notShown"], first["readings"]) == (True, 4, 1, 4)
    lines = history_lines(data, "hearing-notice")
    assert lines[0].startswith("2026-10-04  none  ") and "as of" not in lines[0]
    named = next(line for line in lines if kept[1]["digest"][:16] in line)
    assert named.startswith("2092-05-01  none  ") and "  as of 2092-05-01 (named; written " in named
    assert named.endswith("4 law sources, 1 not shown in force that day; 4 readings attached")


def test_the_command_takes_a_day_and_says_what_the_pack_showed(world):
    import argparse

    from jason.commands.review import as_of_lines as said
    from jason.commands.review import register

    parser = argparse.ArgumentParser()
    register(parser.add_subparsers(), lambda p: None, lambda args: None)
    assert parser.parse_args(["review", "question", "--as-of", "2092-05-01"]).as_of == "2092-05-01"
    assert parser.parse_args(["review", "question"]).as_of is None
    assert said(_pack(world)) == []
    lines = said(_pack(world, as_of=EARLY))
    assert lines[0] == ("as of 2092-05-01: 4 law sources: 3 shown in force that day (1 from an earlier version), 1 not shown "
                        "(the words on the shelf now, labeled)")
    assert any(line.startswith("  S3 CIV 9901: prior; digest ") for line in lines)
    assert any(line.startswith("as of 2092-05-01: 6 governing sources: ") and "2 not shown (the document is not kept as amended)" in line
               and "1 not shown (no section named for the passage)" in line for line in lines)
    assert lines[-1].startswith("readings listed under the words: 4 current, 1 later")
    assert said(_pack((world[0], Community(world[1].living)), as_of=EARLY))[-1] == (
        "no stored reading reads these provisions: the words stand alone")


def test_manager_context_takes_a_day(world, monkeypatch):
    import jason.community
    from jason.mcp.county import manager_context
    from jason.tasks import manager_review

    data, profile = world
    profile.task_prompt = lambda kind: replace(TASK, facts=(), documents=TASK.documents[:3])    # no library to read here
    monkeypatch.setattr(jason.community, "community", lambda: profile)
    real = manager_review.build
    monkeypatch.setattr(manager_review, "build", lambda community, task, data_dir, **kw: real(
        community, task, data_dir, **{**kw, "mode": "keyword"}))
    assert manager_context(task="hearing-notice", ask=ASK, data_dir=data, as_of="March 1")["note"] == "as_of is a day as YYYY-MM-DD"
    plain = manager_context(task="hearing-notice", ask=ASK, data_dir=data)
    assert set(plain) == {"task", "sources", "gaps", "pack"} and "In force on" not in plain["pack"]
    served = manager_context(task="hearing-notice", ask=ASK, data_dir=data, as_of="2092-05-01")
    assert served["asOf"] == "2092-05-01" and "- In force on 2092-05-01: from 2091-01-01 until 2095-06-30" in served["pack"]
    notice = next(row for row in served["law"] if row["citation"] == "CIV 9901")
    assert notice["shownInForce"] and notice["decided"] == "prior" and notice["readings"][0] == {
        "key": "notice-days", "standing": "reading", "whose": "board", "state": "current"}
    assert any("do not rely on them as the law or the rule of that day" in c for c in served["caveats"])
    assert any("never the provision's" in c for c in served["caveats"])
    assert not (data / "reviews").exists() and not (data / "briefs").exists()
