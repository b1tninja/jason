import json
from types import SimpleNamespace

import pytest

from jason.community import intake
from jason.community.living import LivingDocument, SourceKind, SourceRef
from jason.community.symbols import DocumentKind
from jason.tasks import living_docs as ld
from jason.tasks import ocr_reread as rr
from jason.tasks.ocr_reread import Fate

OLD = ("ARTICLE 1\n1.1 Owners.\n(a) Upkeep. The Owner shall keep ofthe Unit and its Condominiurns in good repair.\n"
       "(b) Pets. Pets maybe kept in a Unit at any time.\n")
NEW = ("ARTICLE 1\n1.1 Owners.\n(a) Upkeep. The Owner shall keep of the Unit and its Condominiurns in good repair.\n"
       "(b) Pets. Pets rnay be kept in a Unit at any time.\n")
ROWS = [
    {"section": "1.1(a)", "wrong": "ofthe", "right": "of the", "kind": "transcribed", "source": "page 1"},
    {"section": "1.1(a)", "wrong": "Condominiurns", "right": "Condominiums", "kind": "transcribed", "source": "page 1"},
    {"section": "1.1(b)", "wrong": "maybe kept", "right": "may be kept", "kind": "transcribed", "source": "page 1"},
    {"section": "1.1(b)", "wrong": "Pcts", "right": "Pets", "kind": "transcribed", "source": "page 1"},
]


def _p(number, body):
    return SimpleNamespace(number=number, body=body, caption="", removed=False)


def test_migrate_sorts_each_transcription_by_what_the_new_reading_reads():
    old = [_p("1.1(a)", "The Owner shall keep ofthe Unit and its Condominiurns in good repair."),
           _p("1.1(b)", "Pets maybe kept in a Unit at any time.")]
    new = [_p("1.1(a)", "The Owner shall keep of the Unit and its Condominiurns in good repair."),
           _p("1.1(b)", "Pets rnay be kept in a Unit at any time.")]
    found = rr.migrate(ROWS, [("base", old, new)])
    assert [m.fate for m in found] == [Fate.UNNECESSARY, Fate.CARRIED, Fate.REKEYED, Fate.STALE]
    assert (found[1].wrong, found[1].right) == ("Condominiurns", "Condominiums")
    rekeyed = found[2]
    assert rekeyed.wrong in new[1].body and "rnay" in rekeyed.wrong and "may be kept" in rekeyed.right
    assert rr.migrated_rows(found) == [ROWS[1]]


def test_a_section_the_new_reading_numbers_otherwise_is_found_between_its_neighbours():
    old = [_p("1.9", "Assessment means a charge."), _p("1.10", "Common Area means the property the Ownor shares."),
           _p("1.11", "Condominium means a Unit.")]
    relabeled = [_p("1.9", "Assessment means a charge."), _p("1.40", "Common Area means the property the Ownor shares."),
                 _p("1.11", "Condominium means a Unit.")]
    gone = [_p("1.9", "Assessment means a charge."), _p("1.11", "Condominium means a Unit.")]
    rows = [{"section": "1.10", "wrong": "Ownor", "right": "Owner"},
            {"section": "1.10", "wrong": "Common Area means", "right": "\"Common Area\" means"}]
    carried, rekeyed = rr.migrate(rows, [("base", old, relabeled)])
    assert (carried.fate, carried.section, carried.wrong) == (Fate.CARRIED, "1.40", "Ownor")
    assert "numbers it 1.40" in carried.why and rr.migrated_rows([carried])[0]["carried_from"]["section"] == "1.10"
    assert rekeyed.fate is Fate.CARRIED
    assert {m.fate for m in rr.migrate(rows, [("base", old, gone)])} == {Fate.UNPLACED}


def test_a_stray_number_is_passed_over_and_a_second_one_is_not_keyed():
    old = [_p("3.1(a)", "Declarant shall convey the Common Area."),
           _p("3.1(b)", 'Upon the conveyanceofthe first Unit, each Unit shall have an interest of 1/8".'),
           _p("3.2", "Ownership of each Condominium shall include a Unit.")]
    new = [_p("3.1(b)", "6.2 6.3 6.4 6.5 6.6 6.7"),                       # a table of contents line
           _p("3", "Declarant shall convey the Common Area."),
           _p("3(b)", 'Upon the conveyance of the first Unit, each Unit shall have an interest of 1/8".'),
           _p("3.2", "Ownership of each Condominium shall include a Unit.")]
    rows = [{"section": "3.1(b)", "wrong": "conveyanceofthe", "right": "conveyance of the"},
            {"section": "3.1(b)", "wrong": '1/8"', "right": "1/8th"}]
    gone, carried = rr.migrate(rows, [("base", old, new)])
    assert (gone.fate, gone.section) == (Fate.UNNECESSARY, "3(b)")
    assert (carried.fate, carried.section, carried.wrong) == (Fate.CARRIED, "3(b)", '1/8"')
    twice = [_p("9.5", "See Section 9.5 for the Ownor."), _p("9.5", "The Ownor shall maintain the pipes.")]
    (m,) = rr.migrate([{"section": "9.5", "wrong": "Ownor", "right": "Owner"}],
                      [("base", [_p("9.5", "The Ownor shall maintain the pipes.")], twice)])
    assert m.fate is Fate.UNPLACED and "another section numbered 9.5" in m.why


def test_a_carried_key_that_is_no_longer_unique_is_widened():
    old = [_p("1", "the Ownor and the Owner")]
    new = [_p("1", "the Ownor and the Ownor")]
    found = rr.migrate([{"section": "1", "wrong": "Ownor", "right": "Owner"}], [("base", old, new)])
    assert found[0].fate is Fate.CARRIED
    assert new[0].body.count(found[0].wrong) == 1 and found[0].right.endswith("Owner and")


def test_rekeyed_transcriptions_become_questions_never_records():
    old = [_p("1.1(b)", "Pets maybe kept in a Unit at any time.")]
    new = [_p("1.1(b)", "Pets rnay be kept in a Unit at any time.")]
    found = rr.migrate([ROWS[2]], [("base", old, new)])
    (ask,) = rr.rekey_asks("decl", "cli", found)
    assert ask.subject == "reread:decl#1.1(b)" and ask.kind is intake.AskKind.OCR_READING
    assert ask.status is intake.AskStatus.OPEN and ask.suggestion == found[0].right
    assert not ask.likely                         # "rnay" to "may" touches an operative word: the page decides
    assert ask.detail["wrong"] == found[0].wrong and ask.detail["was"]["wrong"] == "maybe kept"


def test_word_error_scores_runs_and_skips_amended_sections():
    ref = ("the Owner shall keep the Unit in good repair and pay each assessment when it is due to the "
           "Association at its office").split()
    owner = ["1"] * len(ref)
    hyp = ("the Owner shall keep tbe Unit in good repair and pay each assessment when it is due to the "
           "Association at its office").split()
    s = rr.word_error(hyp, ref, owner, set())
    assert s.words == len(ref) and s.edits == 1 and s.differences == [("1", "tbe", "the")]
    assert rr.word_error(hyp, ref, owner, {"1"}).words == 0
    assert rr.difference_kind("ofthe", "of the") == "spacing"
    assert rr.difference_kind("Unit,", "unit") == "case or punctuation"


@pytest.fixture
def scanned(tmp_path, monkeypatch):
    """A living document whose base is a scan: the original reading is cached; the cli reading is OCR'd on demand."""
    import jason.community.ocr as ocr
    import jason.community.scan_marks as scan_marks

    calls = []

    def fake_scan_lines(pdf, *, dpi=300, engine="auto"):
        calls.append(engine)
        text = NEW if engine == "tesseract-cli" else OLD
        return [scan_marks.ScanLine(0, k, 0.5, 0.52, tuple(scan_marks.ScanChar(c, False, 0.0) for c in line))
                for k, line in enumerate(text.splitlines())]

    monkeypatch.setattr(scan_marks, "scan_lines", fake_scan_lines)
    monkeypatch.setattr(ocr.TesseractCli, "available", classmethod(lambda cls: True))
    living = LivingDocument("decl", "Declaration", DocumentKind.DECLARATION,
                            base=SourceRef(SourceKind.SCAN, "scan-1"), base_from="the recorded copy")
    cache = ld.living_dir(tmp_path, "decl") / "sources"
    cache.mkdir(parents=True)
    (cache / "scan-1.pdf").write_bytes(b"%PDF-1.4 a scan")
    import hashlib

    digest = hashlib.sha256(b"%PDF-1.4 a scan").hexdigest()
    (cache / f"scan-1.{digest[:16]}.txt").write_text(OLD, encoding="utf-8")
    ld.transcriptions_path(tmp_path, "decl").write_text(json.dumps(ROWS), encoding="utf-8")
    return SimpleNamespace(living=living, cache=cache, digest=digest, calls=calls, data=tmp_path)


def test_a_reread_is_cached_beside_the_original_and_the_original_stays_in_use(scanned):
    original = scanned.cache / f"scan-1.{scanned.digest[:16]}.txt"
    assert ld.scan_base_text(scanned.living.base, scanned.cache) == OLD and scanned.calls == []
    assert ld.scan_base_text(scanned.living.base, scanned.cache, reading="cli") == NEW.strip()
    assert (scanned.cache / f"scan-1.{scanned.digest[:16]}.cli.txt").is_file() and scanned.calls == ["tesseract-cli"]
    assert original.read_text(encoding="utf-8") == OLD
    assert "keep of the Unit" in ld.build(scanned.living, scanned.data).current.text_of("1.1(a)")
    assert "maybe" in ld.build(scanned.living, scanned.data, transcribed=()).current.text_of("1.1(b)")
    with pytest.raises(ValueError, match="no reading"):
        ld.scan_base_text(scanned.living.base, scanned.cache, reading="other")


def test_dry_run_writes_the_evidence_and_changes_nothing_in_use(scanned):
    active = ld.transcriptions_path(scanned.data, "decl")
    before = active.read_bytes()
    r = rr.dry_run(scanned.living, scanned.data, "cli", lexicon=False)
    assert r.counts() == {"no longer needed": 1, "carried": 1, "re-keyed": 1, "stale already": 1}
    assert active.read_bytes() == before and not intake.store_path(scanned.data).exists()
    assert ld.chosen_reading(scanned.data, "decl") == ""
    p = rr.paths(scanned.data, "decl", "cli")
    assert json.loads(p["transcriptions"].read_text(encoding="utf-8")) == [ROWS[1]]
    assert len(json.loads(p["asks"].read_text(encoding="utf-8"))) == 1
    assert "## The transcriptions" in p["report"].read_text(encoding="utf-8")
    assert any("1 carried" in line for line in rr.lines(r))


def test_switch_needs_a_person_and_an_unchanged_set_then_keeps_the_old(scanned):
    rr.dry_run(scanned.living, scanned.data, "cli", lexicon=False)
    with pytest.raises(ValueError, match="names the person"):
        rr.switch(scanned.living, scanned.data, "cli", "")
    active = ld.transcriptions_path(scanned.data, "decl")
    ld.add_transcription(scanned.data, "decl", "1.1(b)", "at any", "at any", source="a late answer")
    with pytest.raises(ValueError, match="changed since the dry run"):
        rr.switch(scanned.living, scanned.data, "cli", "Pat")
    active.write_text(json.dumps(ROWS), encoding="utf-8")
    rr.dry_run(scanned.living, scanned.data, "cli", lexicon=False)
    out = rr.switch(scanned.living, scanned.data, "cli", "Pat")
    assert json.loads(active.read_text(encoding="utf-8")) == [ROWS[1]]
    backup = active.with_name("transcriptions.original.backup.json")
    assert json.loads(backup.read_text(encoding="utf-8")) == ROWS
    assert ld.chosen_reading(scanned.data, "decl") == "cli"
    assert [a.subject for a in intake.load(scanned.data)] == ["reread:decl#1.1(b)"]
    assert any("Pat" in line for line in out)
    built = ld.build(scanned.living, scanned.data)
    assert "of the Unit" in built.current.text_of("1.1(a)") and "Condominiums" in built.current.text_of("1.1(a)")
    with pytest.raises(ValueError, match="already reads"):
        rr.dry_run(scanned.living, scanned.data, "cli", lexicon=False)


def test_switch_refuses_a_dry_run_numbered_otherwise_than_the_builds(scanned):
    other = "text" if rr.build_numbering() != "text" else "labels"
    r = rr.dry_run(scanned.living, scanned.data, "cli", lexicon=False, numbering=other)
    assert r.sections["numbering"] == other
    with pytest.raises(ValueError, match="numbered sections by"):
        rr.switch(scanned.living, scanned.data, "cli", "Pat")
    assert ld.chosen_reading(scanned.data, "decl") == ""
