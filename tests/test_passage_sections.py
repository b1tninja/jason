"""Section-aware passages, near-copy folding, and the "nothing relevant" advisory, on made-up documents."""

from __future__ import annotations

from pathlib import Path

from jason.community import retrieval
from jason.community.passage_sections import OutlineIndex, export_header, section_passages
from jason.community.passages import PASSAGE_WORDS, Hit, Passage, corpus, rank

DECLARATION = """# Sample Declaration.pdf

- drive_id: `fake-pdf-id`
- mime: `application/pdf`

DECLARATION OF COVENANTS FOR SAMPLE VILLAGE

ARTICLE 1
DEFINITIONS
1.1 Owner. "Owner" means the record holder of fee title to a Unit in Sample Village.
1.2 Unit. "Unit" means a separate interest shown on the condominium plan for the project.

ARTICLE 2
USE RESTRICTIONS
2.1 Pets. No animals other than two household pets may be kept in any Unit, and pets must be leashed in the common area.
(a) Leashes. A pet in the common area shall be on a leash no longer than six feet at all times.
(b) Waste. An owner shall pick up after the pet at once and place the waste in a closed bin.
2.2 Signs. No sign may be shown from a Unit except one sign advertising the Unit for sale or rent of reasonable size.
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_export_header_gives_the_title_and_metadata_and_the_body_after_them():
    title, meta, start = export_header(DECLARATION)
    assert title == "Sample Declaration.pdf" and meta["drive_id"] == "fake-pdf-id"
    assert DECLARATION[start:].lstrip().startswith("DECLARATION OF COVENANTS")
    assert export_header("# A heading of the document\n\nWords.") == ("A heading of the document", {}, 0)


def test_sections_cut_on_numbers_and_carry_the_path_as_a_prefix(tmp_path):
    path = _write(tmp_path, "Sample Declaration.pdf.md", DECLARATION)
    found = section_passages(path)
    owner = next(p for p in found if '"Owner" means' in p.text)
    unit = next(p for p in found if '"Unit" means' in p.text)
    assert owner is not unit                                  # a short definition stays one passage
    assert "1.1 Owner" in owner.heading and owner.heading.startswith("Sample Declaration")
    assert "DEFINITIONS" in owner.heading
    pets = next(p for p in found if "2.1 Pets" in p.text)
    assert pets.text.startswith("ARTICLE 2")                 # an article's title, with no words of its own, leads
    assert "2.1 Pets" in pets.heading and "USE RESTRICTIONS" in pets.heading
    leash = next(p for p in found if "six feet" in p.text)
    assert "2.1(a)" in leash.heading
    # The words are the document's own, a slice of the extract; the heading is only for the rankers.
    for p in found:
        assert p.text in DECLARATION
        assert p.ranked == f"{p.heading}\n{p.text}"
    # BM25 reads the prefix: a section's number finds it though its words do not repeat the number.
    assert rank("section 2.1(a)", found, k=1)[0].passage == leash


def test_an_outline_on_disk_gives_a_doc_export_its_numbers(tmp_path):
    export = ("# Sample Rules\n\n- drive_id: `fake-doc-id`\n- mime: `application/vnd.google-apps.document`\n\n"
              "Parking\nResidents park only in their assigned garage and one open space.\n"
              "Guests\nGuests park in the marked guest spaces for no more than 72 hours.\n")
    outline_text = ("Parking\nResidents park only in their assigned garage and one open space.\n"
                    "Guests\nGuests park in the marked guest spaces for no more than 72 hours.\n")
    outline = {"key": "sample-rules", "title": "Sample Rules", "source": "fake-doc-id", "text": outline_text,
               "sections": [{"number": "B-1", "title": "Parking", "depth": 1, "start": 0},
                            {"number": "B-2", "title": "Guests", "depth": 1, "start": outline_text.index("Guests")}]}
    path = _write(tmp_path, "Sample Rules.md", export)
    found = section_passages(path, outlines=OutlineIndex([outline]))
    guests = next(p for p in found if "72 hours" in p.text)
    assert guests.heading == "Sample Rules > B-2 Guests" and "Parking" not in guests.text
    # An outline whose text is not this extract's is not placed on it.
    other = {**outline, "text": "Entirely different words about pool hours and the clubhouse kitchen rules."}
    assert all("B-2" not in p.heading for p in section_passages(path, outlines=OutlineIndex([other])))


def test_a_long_section_splits_on_paragraphs_within_the_cap(tmp_path):
    paragraph = " ".join(f"word{i}" for i in range(90))
    text = "1.1 Long Section.\n\n" + "\n\n".join(paragraph for _ in range(5)) + "\n1.2 Next. Short words here for the next one.\n"
    found = section_passages(_write(tmp_path, "long.md", text))
    long_parts = [p for p in found if "1.1 Long Section" in p.heading]
    assert len(long_parts) >= 2
    assert all(len(p.text.split()) <= PASSAGE_WORDS for p in long_parts)
    assert all(p.text.startswith("word0") or p.text.startswith("1.1") for p in long_parts)   # paragraph boundaries


def test_a_table_keeps_its_heading_row_when_it_splits(tmp_path):
    rows = "\n".join(f"| 20{i:02d} | Component {i} replacement and repainting work | ${i * 100} |" for i in range(80))
    text = "# Sample Reserve\n\n## Expenditures\n\n| Year | Component | Cost |\n|---|---|---|\n" + rows + "\n"
    found = section_passages(_write(tmp_path, "reserve.md", text))
    pieces = [p for p in found if "Component" in p.text]
    assert len(pieces) >= 2
    assert pieces[0].text.startswith("# Sample Reserve\n\n## Expenditures")   # the headings lead the first piece
    assert pieces[0].heading == "Sample Reserve > Expenditures"
    for p in pieces:
        assert "| Year | Component | Cost |\n|---|---|---|\n" in p.text
        assert len(p.text.split()) <= PASSAGE_WORDS + 12
    for p in pieces[1:]:
        assert p.text.startswith("| Year | Component | Cost |\n|---|---|---|\n")
    assert sum(p.text.count("replacement and repainting") for p in pieces) == 80   # every row once


def test_text_with_no_structure_falls_back_to_windows(tmp_path):
    text = " ".join(f"plain{i}" for i in range(500))
    found = section_passages(_write(tmp_path, "notes.txt", text))
    assert [p.start_word for p in found] == [0, 180, 360]
    assert corpus(tmp_path, chunking="windows")[0].heading == ""


def _p(name: str, text: str, index: int = 0) -> Passage:
    return Passage(Path(name), index, 0, text)


SECTION = ("7.4 Garage Doors. Each Owner shall maintain, repair, and replace the garage door of the Owner's Unit, "
           "including its opener, springs, and weather stripping, at the Owner's sole cost.")


def test_near_copies_fold_into_the_best_ranked_with_also_in():
    ocr = SECTION.replace("Garage", "Garaqe").replace("  ", " ").replace("Owner's", "Owner' s")
    hits = [Hit(_p("ccrs.md", SECTION), 3.0), Hit(_p("pool.md", "Pool hours are 8 a.m. to 10 p.m."), 2.5),
            Hit(_p("CCRs scan.pdf.md", ocr), 2.0), Hit(_p("CCRs export.pdf.md", "Recitals. " + SECTION), 1.0)]
    folded = retrieval.collapse(hits)
    assert [h.passage.path.name for h in folded] == ["ccrs.md", "pool.md"]
    assert [p.path.name for p in folded[0].also] == ["CCRs scan.pdf.md", "CCRs export.pdf.md"]
    assert folded[0].score == 3.0 and folded[1].also == ()


def test_forms_that_differ_in_their_numbers_are_not_copies():
    form = "Declaration of Annexation recorded as Document No. {n}, annexing Phase {p} to the Development under Article 13."
    a, b = _p("phase-5.md", form.format(n="202004280704", p=5)), _p("phase-7.md", form.format(n="202101080548", p=7))
    assert not retrieval.near_copies(a, b)
    assert len(retrieval.collapse([Hit(a, 2.0), Hit(b, 1.0)])) == 2


def test_a_tie_between_copies_goes_to_the_preferred_source():
    working, recorded = _p("working copy.md", SECTION), _p("recorded.pdf.md", SECTION)
    hits = [Hit(working, 1.0), Hit(recorded, 1.0)]
    assert retrieval.collapse(hits)[0].passage == working                     # no preference: the ranking's order
    order = {"recorded.pdf.md": 0, "working copy.md": 1}
    lead = retrieval.collapse(hits, prefer=lambda p: order[p.path.name])[0]
    assert lead.passage == recorded and lead.also == (working,)
    lower = [Hit(working, 1.0), Hit(recorded, 0.5)]                             # not tied: the better-ranked copy stays
    assert retrieval.collapse(lower, prefer=lambda p: order[p.path.name])[0].passage == working


def test_the_no_answer_advisory_is_a_note_never_a_filter():
    assert retrieval.no_answer_advisory(0.31, threshold=0.4) == (
        "no passage scored above 0.40 against the question (best 0.31); the answer may not be in these documents")
    assert retrieval.no_answer_advisory(0.55, threshold=0.4) == ""
    assert retrieval.no_answer_advisory(None, threshold=0.4) == ""
