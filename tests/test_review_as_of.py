"""A review as of a day: the pack recites each provision's words in force that day, labels what the disk does not show,
and attaches each stored reading as a reading.

Every section, act, session publication, document, and reading here is made up ("CIV 9901", "Stats. 2090, Ch. 1",
"Covenants"), and the fake lawlibrary answers from this file: nothing leaves the test.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community import law_text
from jason.community import passage_index as pi
from jason.community import retrieval
from jason.community.authorities import Authority, Basis
from jason.community.context_pack import CORPUS, assemble
from jason.community.law_readings import Canon, LawReading, Provision, ReadingStanding, Whose, recite
from jason.community.living import LivingDocument, LivingInstrument, SourceKind, SourceRef
from jason.community.outlines import outline_from_text
from jason.community.prompts import Audience, FactSource, TaskKind, TaskPrompt
from jason.community.symbols import DocumentKind
from jason.sources.lawlibrary import LawLibrary
from jason.tasks.export_authorities import AUTHORITIES_DIR, MANIFEST, authority_pages, export_authorities
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
    return page[page.index("## Task"):] + "\n=== sources_text ===\n" + pack.sources_text() + "\n"


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
