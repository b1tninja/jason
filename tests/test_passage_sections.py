"""Section-aware passages, near-copy folding, and the "nothing relevant" advisory, on made-up documents."""

from __future__ import annotations

from pathlib import Path

from jason.community import retrieval
from jason.community.passage_sections import (MAX_WORDS, MIN_PASSAGE_WORDS, OutlineIndex, cut_signature, export_header,
                                              section_passages)
from jason.community.passages import PASSAGE_WORDS, Hit, Passage, corpus, rank

DECLARATION = """# Sample Declaration.pdf

- drive_id: `fake-pdf-id`
- mime: `application/pdf`

DECLARATION OF COVENANTS FOR SAMPLE VILLAGE

ARTICLE 1
DEFINITIONS
1.1 Owner. "Owner" means the record holder of fee title to a Unit in Sample Village, whether one or more persons, but not a person holding title only as security for a debt.
1.2 Unit. "Unit" means a separate interest shown on the condominium plan for the project, with its garage, its balcony or patio, and every fixture inside its unfinished walls.

ARTICLE 2
USE RESTRICTIONS
2.1 Pets. No animals other than two household pets may be kept in any Unit, and pets must be leashed in the common area at every hour of the day.
(a) Leashes. A pet in the common area shall be on a leash no longer than six feet at all times, held by a person able to control the animal.
(b) Waste. An owner shall pick up after the pet at once and place the waste in a closed bin kept inside the garage until the day of collection.
2.2 Signs. No sign may be shown from a Unit except one sign advertising the Unit for sale or rent of reasonable size, placed inside a window.
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
    assert owner is not unit                                  # a definition over the minimum stays one passage
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
    outline_text = ("Parking\nResidents park only in their assigned garage and one open space, never in a fire lane, on the "
                    "landscaping, or in a space marked for another unit or a guest.\n"
                    "Guests\nGuests park in the marked guest spaces for no more than 72 hours in any week, and a resident may "
                    "not use a guest space for a vehicle of the household.\n")
    export = "# Sample Rules\n\n- drive_id: `fake-doc-id`\n- mime: `application/vnd.google-apps.document`\n\n" + outline_text
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


MINIMUM = 25                    # the minimum these tests cut with, whatever the default is


def _filler(n: int, word: str = "word") -> str:
    return " ".join(f"{word}{i}" for i in range(n))


def _count(passage: Passage) -> int:
    return len(passage.text.split())


def _cut(path: Path, **kwargs) -> tuple[Passage, ...]:
    return section_passages(path, min_words=MINIMUM, **kwargs)


def _before(path: Path) -> tuple[Passage, ...]:
    return section_passages(path, min_words=0)


def test_a_heading_with_no_words_joins_the_passage_after_it_and_keeps_its_label(tmp_path):
    # A long section's heading is cut off its first paragraph, and another heading stands just before it.
    text = "TABLE OF CONTENTS\n\nPOOL RULES\n\n" + _filler(MAX_WORDS, "pool") + "\n\nGATE RULES\n\n" + _filler(60, "gate") + "\n"
    path = _write(tmp_path, "rules.txt", text)
    found = _cut(path)
    assert [p.text.split()[-1] for p in found] == [f"pool{MAX_WORDS - 1}", "gate59"]
    assert found[0].text.startswith("TABLE OF CONTENTS\n\nPOOL RULES\n\npool0") and found[0].start_word == 0
    assert found[0].heading == "rules > TABLE OF CONTENTS > POOL RULES"          # both headings in the path
    assert found[1].heading == "rules > GATE RULES" and found[1].start_word == 5 + MAX_WORDS
    assert " ".join(p.text for p in found).split() == text.split()                # every word once, in order
    # The cut before left the two headings as a passage of five words, with the first one's label dropped.
    assert _before(path)[0].text == "TABLE OF CONTENTS\n\nPOOL RULES" and _before(path)[0].heading == "rules > POOL RULES"


def test_a_heading_at_the_end_of_a_file_joins_the_passage_before_it(tmp_path):
    text = "POOL RULES\n\n" + _filler(60, "pool") + "\n\nNOTES\n"
    found = _cut(_write(tmp_path, "rules.txt", text))
    assert len(found) == 1 and found[0].text.endswith("pool59\n\nNOTES")         # its words are kept
    assert found[0].heading == "rules > POOL RULES"                               # but it heads nothing in that passage


def test_a_trailing_fragment_joins_the_passage_before_it(tmp_path):
    text = ("POOL RULES\n\n" + _filler(120, "pool") + "\n\n" + _filler(95, "swim") + "\n\nNo glass at the pool.\n\n"
            "GATE RULES\n\n" + _filler(60, "gate") + "\n")
    path = _write(tmp_path, "rules.txt", text)
    assert [_count(p) for p in _before(path)] == [217, 5, 62]                     # the cut before: a stub of five words
    found = _cut(path)
    assert [_count(p) for p in found] == [222, 62]
    assert found[0].text.endswith("swim94\n\nNo glass at the pool.") and found[0].heading == "rules > POOL RULES"
    assert "glass" not in found[1].text and found[1].start_word == 222
    assert all(p.text in text for p in found)                                     # each still a slice of the file


def test_a_short_passage_joins_the_neighbour_it_shares_more_of_its_path_with(tmp_path):
    text = ("# Sample Code 100-105\n\n## SC 100\n\n### Part A\n\n" + _filler(60, "alpha") + "\n\n"
            "## SC 105\n\n105. (Added by a made-up act, section 2.)\n\n### Part B\n\n" + _filler(60, "beta") + "\n")
    found = _cut(_write(tmp_path, "sc-100.md", text))
    opening = next(p for p in found if "105. (Added" in p.text)
    assert "beta0" in opening.text and "alpha59" not in opening.text             # with its own section, not the one before
    assert opening.heading == "Sample Code 100-105 > SC 105 > Part B"
    assert opening.text.startswith("## SC 105") and opening.start_word == text.split().index("105") - 2


def test_short_sections_join_and_the_passage_keeps_each_label_and_every_word(tmp_path):
    text = ("# Sample Rules\n\n## Quiet Hours\n\nQuiet hours run from ten at night to seven in the morning.\n\n"
            "## Trash\n\nBins go out on Monday night and come in by Tuesday night.\n\n"
            "## Parking\n\n" + _filler(80, "park") + "\n")
    path = _write(tmp_path, "Sample Rules.md", text)
    assert len(_before(path)) == 3
    found = _cut(path)
    assert len(found) == 2
    assert found[0].heading == "Sample Rules > Quiet Hours > Trash" and found[1].heading == "Sample Rules > Parking"
    assert "seven in the morning" in found[0].text and "by Tuesday night" in found[0].text
    assert " ".join(p.text for p in found).split() == text.split()
    assert text.split()[found[1].start_word: found[1].start_word + 2] == ["##", "Parking"]
    # A label finds the joined passage, and a recitation is still exact.
    assert rank("trash", found, k=1)[0].passage == found[0] and found[0].text in text


def test_a_page_mark_is_no_heading_and_no_passage_of_its_own(tmp_path):
    text = ("\n<<PAGE 1>>\nSAMPLE GUIDE\n\n" + _filler(40, "intro") + "\n\n<<PAGE 2>>\nRESERVE FUNDING\n\n" + _filler(50, "fund")
            + "\n\n<<PAGE 3>>\n" + _filler(30, "more") + "\n\n<<PAGE 4>>\n")
    path = _write(tmp_path, "guide.txt", text)
    found = _cut(path)
    # A mark ends the sections above it and names nothing: page 3 has no heading of its own.
    assert [p.heading for p in found] == ["guide > SAMPLE GUIDE", "guide > RESERVE FUNDING", "guide"]
    assert found[0].text.startswith("<<PAGE 1>>\nSAMPLE GUIDE") and found[0].start_word == 0
    assert found[1].text.startswith("<<PAGE 2>>\nRESERVE FUNDING")               # a page's mark leads the page's words
    assert found[2].text.startswith("<<PAGE 3>>\nmore0") and found[2].text.endswith("more29\n\n<<PAGE 4>>")
    assert sum(p.text.count("<<PAGE") for p in found) == 4                        # every mark is still in the text
    assert " ".join(p.text for p in found).split() == text.split()
    # The cut before took a mark for a heading, and a page with a few words was a passage: here the marks are not
    # counted as words, so the page of twelve words is under the minimum and joins the page before it.
    old = _write(tmp_path, "old.txt", "<<PAGE 7>>\n" + _filler(30, "more") + "\n\n<<PAGE 8>>\n" + _filler(12, "last") + "\n")
    assert [p.heading for p in _before(old)] == ["old > <<PAGE 7>>", "old > <<PAGE 8>>"]
    assert [(p.heading, _count(p)) for p in _cut(old)] == [("old", 30 + 12 + 4)]


def test_page_marks_with_no_words_between_them_lead_the_next_passage(tmp_path):
    text = "POOL RULES\n\n" + _filler(60, "pool") + "\n\n<<PAGE 2>>\n\n<<PAGE 3>>\nGATE RULES\n\n" + _filler(60, "gate") + "\n"
    found = _cut(_write(tmp_path, "marks.txt", text))
    assert len(found) == 2 and "<<PAGE" not in found[0].text
    assert found[1].text.startswith("<<PAGE 2>>\n\n<<PAGE 3>>\nGATE RULES") and found[1].heading == "marks > GATE RULES"
    assert found[1].start_word == 62


def test_a_join_never_builds_a_passage_far_over_the_maximum(tmp_path):
    # Forty sections of twenty-odd words: they join in twos, never into one long passage.
    sections = "".join(f"## Item {i}\n\n" + _filler(18, f"item{i}x") + "\n\n" for i in range(40))
    found = _cut(_write(tmp_path, "list.md", "# List\n\n" + sections))
    counts = [_count(p) for p in found]
    assert len(found) >= 10 and min(counts) >= MINIMUM and max(counts) <= MAX_WORDS + MINIMUM
    # No room: a section's last lines have joined its full passage, so the short section after it stays as it is.
    text = "## A\n\n" + _filler(58, "a") + "\n\n" + _filler(24, "tail") + "\n\n## B\n\n" + _filler(22, "b") + "\n"
    found = _cut(_write(tmp_path, "full.md", text), max_words=60)
    assert [_count(p) for p in found] == [84, 24] and found[1].text.startswith("## B")
    assert found[0].heading == "full > A" and found[1].heading == "full > B"
    # A file of one short passage has no neighbour.
    assert [_count(p) for p in _cut(_write(tmp_path, "one.md", "## Only\n\nA few words here.\n"))] == [6]


def test_many_headings_with_no_words_give_the_path_only_the_last_few(tmp_path):
    # A scan's shouted words, one a line, are each a heading with no words: the path takes the last three of them
    # before the heading the words sit under.
    text = "NOTICE\n\nTODAY\n\nEVERY\n\nOWNERS\n\nABOUT\n\nPARKING\n\n" + _filler(40, "park") + "\n"
    found = _cut(_write(tmp_path, "scan.txt", text))
    assert len(found) == 1 and found[0].text.startswith("NOTICE\n\nTODAY")
    assert found[0].heading == "scan > EVERY > OWNERS > ABOUT > PARKING"


def test_the_cut_signature_names_the_minimum():
    assert cut_signature("sections") == (f"sections/min{MIN_PASSAGE_WORDS}" if MIN_PASSAGE_WORDS else "sections")
    assert cut_signature("sections", 25) == "sections/min25"
    assert cut_signature("sections", 0) == "sections" and cut_signature("windows", 25) == "windows"


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
