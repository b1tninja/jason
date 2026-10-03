"""Revision detection over made-up versions of a made-up rules document."""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from jason.community.outlines import CitableDocument
from jason.community.revision_detection import (ChangeKind, Flag, align, between, docx_text, lineages, name_dates,
                                                name_matches, outline_text, printed_dates, strip_furniture, units,
                                                word_diff)
from jason.community.symbols import DocumentKind

BASE = """RULES

R-1. PETS
a. Pets shall be leashed in the common area.
b. Owners must clean up after their pets.
c. No more than two pets may be kept in a unit.

R-2. PARKING
a. Guests may park in the marked spaces for up to 72 hours.
b. Vehicles in a fire lane shall be towed.
c. The fine for a parking violation is $50.

R-3. TRASH
Containers shall be stored out of sight except on collection day.
"""


def _units(text: str):
    return units(outline_text(text, key="rules"))


def _by(changes, number):
    return next(c for c in changes if (c.after and c.after.number == number) or (c.before and c.before.number == number))


def test_outline_reads_rule_heads_and_lettered_items():
    us = _units(BASE)
    numbers = [u.number for u in us]
    assert numbers[:4] == ["R-1", "R-1(a)", "R-1(b)", "R-1(c)"]      # a one-word line is not a caption
    assert "R-2(c)" in numbers and "R-3" in numbers
    assert us[1].words == "Pets shall be leashed in the common area."


def test_unchanged_text_has_no_real_change():
    assert not [c for c in align(_units(BASE), _units(BASE)) if c.real]


def test_reworded_amount_and_modal_are_flagged():
    after = BASE.replace("is $50.", "is $100.").replace("Vehicles in a fire lane shall be towed.",
                                                          "Vehicles in a fire lane may be towed.")
    changes = [c for c in align(_units(BASE), _units(after)) if c.real]
    fine = _by(changes, "R-2(c)")
    assert fine.kind is ChangeKind.REWORDED and Flag.AMOUNT in fine.flags
    assert fine.ops[0].before == "$50." and fine.ops[0].after == "$100."
    tow = _by(changes, "R-2(b)")
    assert Flag.MODAL in tow.flags


def test_days_flag():
    ops = word_diff("park for up to 72 hours", "park for up to 48 hours")
    assert ops and Flag.DAYS in ops[0].flags


def test_removed_item_renumbers_the_rest():
    after = BASE.replace("b. Owners must clean up after their pets.\nc. No more", "b. No more")
    changes = [c for c in align(_units(BASE), _units(after)) if c.real]
    removed = next(c for c in changes if c.before and c.before.number == "R-1(b)")
    assert removed.kind is ChangeKind.REMOVED and removed.before.words.startswith("Owners must clean")
    renumbered = next(c for c in changes if c.before and c.before.number == "R-1(c)")
    assert renumbered.kind is ChangeKind.RENUMBERED and renumbered.after.number == "R-1(b)"


def test_moved_section_under_another_head():
    after = BASE.replace("c. No more than two pets may be kept in a unit.\n", "").replace(
        "c. The fine for a parking violation is $50.\n",
        "c. The fine for a parking violation is $50.\nd. No more than two pets may be kept in a unit.\n")
    changes = [c for c in align(_units(BASE), _units(after)) if c.real]
    moved = next(c for c in changes if c.before and c.before.number == "R-1(c)")
    assert moved.kind is ChangeKind.MOVED and moved.after.number == "R-2(d)" and moved.moved


def test_split_section():
    before = BASE.replace("Containers shall be stored out of sight except on collection day.",
                          "Containers shall be stored out of sight except on collection day. Recycling goes in the "
                          "blue container and yard waste goes in the green container provided by the city.")
    after = BASE.replace("Containers shall be stored out of sight except on collection day.",
                         "a. Containers shall be stored out of sight except on collection day.\n"
                         "b. Recycling goes in the blue container and yard waste goes in the green container "
                         "provided by the city.")
    changes = [c for c in align(_units(before), _units(after)) if c.real]
    assert any(c.kind is ChangeKind.SPLIT for c in changes)


def test_export_noise_is_not_a_change():
    """The same words as a PDF prints them: page furniture, a hanging label, a broken word, curly quotes."""
    pages = ["Sample Association Rules\nRULES\n\nR-1. PETS\na)\nPets shall be leashed in the com-\nmon area.\n"
             "b) Owners must clean up after their pets.\nPage 1",
             "Sample Association Rules\nc) No more than two pets may be kept in a unit.\n\nR-2. PARKING\n"
             "a) Guests may park in the marked spaces for up to 72 hours.\nPage 2",
             "Sample Association Rules\nb) Vehicles in a fire lane shall be towed.\n"
             "c) The fine for a parking violation is $50.\n\nR-3. TRASH\n"
             "Containers shall be stored out of sight except on collection day.\nPage 3"]
    pdf_text = strip_furniture(pages)
    assert "Sample Association Rules" not in pdf_text and "Page 2" not in pdf_text
    changes = [c for c in align(_units(BASE), _units(pdf_text)) if c.real]
    assert not changes, [(c.kind, c.before and c.before.number, c.after and c.after.number) for c in changes]


def test_ocr_letter_slip_is_noise_but_a_number_is_not():
    ops = word_diff("Pets shall be leashed in the common area.", "Pets shall be leashcd in the comrnon area.",
                    ocr=True)
    assert ops and all(o.noise for o in ops)
    ops = word_diff("up to 72 hours", "up to 78 hours", ocr=True)
    assert ops and not ops[0].noise


def test_lineage_ids_and_between():
    v1, v2, v3 = BASE, BASE.replace("is $50.", "is $75."), BASE.replace("is $50.", "is $100.")
    chain = [_units(v) for v in (v1, v2, v3)]
    steps = [align(chain[0], chain[1]), align(chain[1], chain[2])]
    lins = lineages("rules", ["2020-01-01", "2021-01-01", "2022-01-01"], chain, steps)
    fine = next(l for l in lins if l.id == "rules@2020-01-01/R-2(c)")
    assert [s.unit.words for s in fine.steps][-1].endswith("$100.")
    c = between(fine, 0, 2)
    assert c.kind is ChangeKind.REWORDED and c.ops[0].before == "$50." and c.ops[0].after == "$100."
    added = BASE.replace("R-3. TRASH", "R-4. NOISE\nQuiet hours are 10 pm to 7 am.\n\nR-3. TRASH")
    chain2 = [chain[0], _units(added)]
    lins2 = lineages("rules", ["2020-01-01", "2023-05-01"], chain2, [align(chain2[0], chain2[1])])
    assert any(l.id == "rules@2023-05-01/R-4" for l in lins2)


def _docx(paragraphs: list[tuple[str, int | None]]) -> bytes:
    """A Word file whose list (numId 1) letters its first level and numbers its second."""
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = []
    for text, level in paragraphs:
        num = f'<w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="1"/></w:numPr>' if level is not None else ""
        body.append(f'<w:p><w:pPr>{num}</w:pPr><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>')
    document = f'<?xml version="1.0"?><w:document {w}><w:body>{"".join(body)}</w:body></w:document>'
    numbering = (f'<?xml version="1.0"?><w:numbering {w}><w:abstractNum w:abstractNumId="0">'
                 '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%1."/></w:lvl>'
                 '<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="(%2)"/></w:lvl>'
                 '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", document)
        z.writestr("word/numbering.xml", numbering)
    return buf.getvalue()


def test_docx_text_draws_list_labels():
    data = _docx([("R-1. PETS", None), ("Pets shall be leashed.", 0), ("Dogs.", 1), ("Cats.", 1),
                  ("Owners must clean up.", 0)])
    text = docx_text(data)
    assert "a. Pets shall be leashed." in text and "  (1) Dogs." in text and "  (2) Cats." in text
    assert "b. Owners must clean up." in text
    numbers = [u.number for u in _units(text)]
    assert numbers == ["R-1", "R-1(a)", "R-1(a)(1)", "R-1(a)(2)", "R-1(b)"]


def test_docx_pending_suggestions_are_not_the_text():
    """A Doc's Word export carries its unaccepted suggestions as tracked changes: the text stands without them."""
    w = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    para = ('<w:p><w:r><w:t xml:space="preserve">Trash may be put out </w:t></w:r>'
            '<w:del w:id="1" w:author="x"><w:r><w:delText xml:space="preserve">after 6 pm on </w:delText></w:r></w:del>'
            '<w:ins w:id="2" w:author="x"><w:r><w:t xml:space="preserve">on </w:t></w:r></w:ins>'
            '<w:r><w:t>collection day.</w:t></w:r></w:p>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<?xml version="1.0"?><w:document {w}><w:body>{para}</w:body></w:document>')
    data = buf.getvalue()
    from jason.community.revision_detection import docx_suggestions

    assert docx_text(data) == "Trash may be put out after 6 pm on collection day."
    assert docx_text(data, accept=True) == "Trash may be put out on collection day."
    assert docx_suggestions(data) == [("delete", "after 6 pm on"), ("insert", "on")]


def test_names_and_dates():
    phrases = ["Sample Rules", "Rules and Regulations"]
    assert name_matches("Sample Rules.pdf", phrases)
    assert name_matches("Sample Rules - revised (scanned copy).pdf", phrases)
    assert name_matches("Sample Association - 221120 - Sample Rules.pdf", phrases, allowed=["Sample Association"])
    assert not name_matches("Notice of Proposed Change to Sample Rules.pdf", phrases)
    assert name_matches("Old handbook.pdf", phrases, extra=[r"\bhandbook\b"])
    assert not name_matches("Sample Rules.pdf", phrases, exclude=[r"sample"])
    assert name_dates("Sample - 221120 - Rules.pdf") == [date(2022, 11, 20)]
    assert name_dates("rules 022620.pdf") == [date(2020, 2, 26)]
    assert name_dates("2022.1.04 Proposed rules.pdf") == [date(2022, 1, 4)]
    got = printed_dates("Rules\nEFFECTIVE: SEPTEMBER 15, 2022\nRevised 4/18/23")
    assert (date(2022, 9, 15), "EFFECTIVE: SEPTEMBER 15, 2022") in got and any(d == date(2023, 4, 18) for d, _ in got)


# ---------------------------------------------------------------------------------------------------------------------
# The task: versions found on disk, ordered, compared, and tied to an adoption on record.

@dataclass(frozen=True)
class _Record:
    key: str
    title: str
    document: str
    document_title: str = ""
    files: str = ""
    words: tuple = ()
    decided: date | None = None
    note: str = ""


class _Spec:
    name = "Sample Association"

    def citable_documents(self):
        return (CitableDocument("sample-rules", "Sample Rules", "doc-id-1", DocumentKind.OPERATING_RULES,
                                aliases=("Sample Rules",)),)

    def revision_series(self):
        return ()

    def rule_change_records(self):
        return (_Record("fines-2021", "Rule R-2 fine increase", "sample-rules", decided=date(2021, 3, 1)),)


def test_build_finds_versions_and_adoption(tmp_path: Path):
    from jason.tasks import revision_detection as rd

    files = tmp_path / "gmail" / "files"
    rows = []
    for k, (day, text) in enumerate([("2020-06-01", BASE), ("2021-02-01", BASE.replace("is $50.", "is $100.")),
                                     ("2022-02-01", BASE.replace("is $50.", "is $100.").replace(
                                         "Containers shall be stored", "Containers may be stored"))]):
        folder = files / f"m{k}"
        folder.mkdir(parents=True)
        (folder / "Sample Rules.md").write_text(text, encoding="utf-8")
        rows.append({"messageId": f"m{k}", "at": f"{day}T12:00:00+00:00", "direction": "out", "subject": "rules",
                     "name": "Sample Rules.md", "path": f"gmail/files/m{k}/Sample Rules.md", "sha256": "", "bytes": 1})
    # The same words again, sent later: one version, two sightings.
    (files / "m9").mkdir()
    (files / "m9" / "Sample Rules.md").write_text(BASE, encoding="utf-8")
    rows.append({"messageId": "m9", "at": "2020-09-01T00:00:00+00:00", "direction": "out", "subject": "rules",
                 "name": "Sample Rules.md", "path": "gmail/files/m9/Sample Rules.md", "sha256": "", "bytes": 1})
    (tmp_path / "gmail" / "files.json").write_text(json.dumps({"files": rows}), encoding="utf-8")

    result = rd.build(_Spec(), tmp_path, "sample-rules")
    assert result["counts"]["versions"] == 3 and len(result["chain"]) == 3
    first = result["versions"][0]
    assert first["on"] == "2020-06-01" and len(first["sightings"]) == 2
    fine = next(c for c in result["changes"] if c["numberAfter"] == "R-2(c)")
    assert fine["flags"][0] == "amount" and fine["fromOn"] == "2020-06-01" and fine["toOn"] == "2021-02-01"
    assert fine["adoption"] and fine["adoption"][0]["strength"] == "names this section" and not fine["finding"]
    trash = next(c for c in result["changes"] if c["numberAfter"] == "R-3")
    assert "shall/may" in trash["flags"] and trash["finding"].startswith("changed between 2021-02-01")
    assert "does not name this section" in trash["finding"]          # the R-2 change is in the window, named apart
    lin = next(l for l in result["lineages"] if l["id"] == "sample-rules@2020-06-01/R-2(c)")
    assert [t["stage"] for t in lin["timeline"]][-1] == "adopted"
    out, page = rd.write(tmp_path, result)
    text = page.read_text(encoding="utf-8")
    assert "replaced \"$50.\" with \"$100.\"" in text and "no adoption found" in text
    assert rd.section_history(tmp_path, "sample-rules", "R-2(c)")["changes"]
