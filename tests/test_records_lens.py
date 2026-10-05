"""The records lens (docs/ingestion-and-review.md, step 2): what depends on another document or store is a lens's
finding, made from a reading's stored fields and from facts a named function gathers; the facts' digest is in the
review's key, so a review is made again exactly when the other records it rests on change. Every reader, text, store,
and profile here is made up."""

from __future__ import annotations

import dataclasses
import inspect
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community import reviews
from jason.community.document_models import REGISTRY, Basis, DocumentModel, Finding, ModelContext, Severity, read, to_plain
from jason.community.reviews import AS_OF, RECORDS, Lens, Records, join, stored
from jason.community.symbols import DocumentKind
from jason.tasks import document_models as task
from jason.tasks import document_reviews as store

KIND = DocumentKind.COMMITTEE_REPORT
D1, D2 = date(2026, 3, 1), date(2027, 3, 1)
INSPECTIONS = "inspections.json"     # the other store: the inspections logged, by permit number


@dataclass
class Permit:
    number: str = ""
    expires: date | None = None


DATES = Lens("test-permit-dates", "As of a date, is the permit still good?", needs_as_of=True)
SHELF = Lens("test-shelf", "Against the inspections on file, was the permit's work inspected?", needs_as_of=True, gathers=True)
GATHERED: list[str] = []     # each time the facts function read the store
CHECKED: list[str] = []      # each time the shelf's check ran


@DATES.check("permit-expiry", Permit, fields=("number", "expires"))
def permit_expiry(r, as_of, _facts=None):
    if r.expires and r.expires < as_of:
        return [Finding("expired", f"permit {r.number} expired {r.expires}", Severity.CHECK, "CODE 1(a)")]
    return [Finding("expires", f"permit {r.number} expires {r.expires}", Severity.INFO)] if r.expires else []


def _inspections(data_dir) -> dict:
    try:
        return json.loads((Path(data_dir) / INSPECTIONS).read_text(encoding="utf-8"))
    except (OSError, TypeError):
        return {}


def inspection_on_file(r, records):
    """The one place the other store is read: the inspection logged for the permit, as plain data."""
    GATHERED.append(r.number)
    if records.data_dir is None:
        return None
    return _inspections(records.data_dir).get(r.number)


@SHELF.check("inspected", Permit, fields=("number",), facts=inspection_on_file, dated=False)
def inspected(r, as_of, inspection):
    CHECKED.append(r.number)
    assert as_of is None                                  # a check that says it needs no date is given none
    if inspection:
        return [Finding("inspected", f"permit {r.number} was inspected {inspection['on']} by {inspection['by']}", Severity.INFO, "CODE 3")]
    return []


@SHELF.check("never-inspected", Permit, fields=("number", "expires"), facts=inspection_on_file)
def never_inspected(r, as_of, inspection):
    if not inspection and r.expires and r.expires < as_of:
        return [Finding("never-inspected", f"permit {r.number} ran out {r.expires} with no inspection on file")]
    return []


def _parse(text: str) -> Permit | None:
    if not text.startswith("PERMIT"):
        return None
    words = text.split()
    return Permit(number=words[1], expires=date.fromisoformat(words[2]) if len(words) > 2 else None)


class PermitModel(DocumentModel):
    """A made-up reader: its own findings rest on the text; the date's are one lens's and the other store's another's."""

    kind = KIND
    name = "test-shelf-permit"
    required = ("number",)
    lens_checks = (permit_expiry, inspected, never_inspected)

    def parse(self, text, context):
        return _parse(text)

    def check(self, r, context):
        # Two lenses' slots stand at the same place (after "numbered"); the order they are returned in is kept.
        return [Finding("numbered", f"permit {r.number}", Severity.INFO), permit_expiry, inspected,
                Finding("keep", "a record to keep", Severity.INFO, "CODE 2"), never_inspected]


class OldPermitModel(DocumentModel):
    """The same reader as it was before the lenses: its check reads the date and opens the other store itself."""

    kind = KIND
    name = "test-shelf-permit"
    required = ("number",)

    def parse(self, text, context):
        return _parse(text)

    def check(self, r, context):
        found = [Finding("numbered", f"permit {r.number}", Severity.INFO)]
        if r.expires and r.expires < context.today:
            found.append(Finding("expired", f"permit {r.number} expired {r.expires}", Severity.CHECK, "CODE 1(a)"))
        elif r.expires:
            found.append(Finding("expires", f"permit {r.number} expires {r.expires}", Severity.INFO))
        inspection = _inspections(context.data_dir).get(r.number) if context.data_dir is not None else None
        if inspection:
            found.append(Finding("inspected", f"permit {r.number} was inspected {inspection['on']} by {inspection['by']}", Severity.INFO, "CODE 3"))
        found.append(Finding("keep", "a record to keep", Severity.INFO, "CODE 2"))
        if not inspection and r.expires and r.expires < context.today:
            found.append(Finding("never-inspected", f"permit {r.number} ran out {r.expires} with no inspection on file"))
        return found


TEXT = "PERMIT 12 2026-06-01"
LOG = {"12": {"on": "2026-02-10", "by": "the city"}, "7": {"on": "2026-01-05", "by": "the county"}}


def shelf(tmp_path: Path, log: dict | None = LOG) -> Path:
    if log is None:
        (tmp_path / INSPECTIONS).unlink(missing_ok=True)
    else:
        (tmp_path / INSPECTIONS).write_text(json.dumps(log), encoding="utf-8")
    return tmp_path


def codes(reading) -> list[str]:
    return [f.code for f in reading.findings]


def plain(reading) -> dict:
    return json.loads(json.dumps(reading.as_dict(), default=str))


# A reading and the records lens --------------------------------------------------------------------------------------


def test_a_records_finding_appears_with_the_other_record_and_vanishes_without_it(tmp_path):
    with_it = PermitModel().read(TEXT, ModelContext(today=D1, data_dir=shelf(tmp_path)))
    without = PermitModel().read(TEXT, ModelContext(today=D1, data_dir=shelf(tmp_path, {"7": LOG["7"]})))
    assert codes(with_it) == ["numbered", "expires", "inspected", "keep"] and codes(without) == ["numbered", "expires", "keep"]
    # What the reader found in the document is the same either way: the fields, its own findings, and the as-of lens's.
    assert to_plain(with_it.record) == to_plain(without.record) and with_it.own_findings == without.own_findings
    assert task.text_sha(TEXT) == task.text_sha(TEXT) and with_it.version == without.version
    assert [f for f in with_it.findings if f.lens == DATES.key] == [f for f in without.findings if f.lens == DATES.key]
    a, b = (next(r for r in reading.reviews if r.lens == SHELF.key) for reading in (with_it, without))
    assert a.fields_sha == b.fields_sha and a.facts_sha != b.facts_sha and a.facts_sha and b.facts_sha


def test_a_records_finding_says_which_check_made_it_and_what_it_read(tmp_path):
    reading = PermitModel().read(TEXT, ModelContext(today=D2, data_dir=shelf(tmp_path, {})))
    assert codes(reading) == ["numbered", "expired", "keep", "never-inspected"]
    late = reading.findings[-1]
    assert (late.lens, late.check) == ("test-shelf", "never-inspected") and late.basis == {Basis.TEXT, Basis.STORE, Basis.TODAY}
    seen = PermitModel().read(TEXT, ModelContext(today=D1, data_dir=shelf(tmp_path))).findings[2]
    assert (seen.lens, seen.check) == ("test-shelf", "inspected") and seen.basis == {Basis.TEXT, Basis.STORE, Basis.LAW}   # no date
    # The reader's own check read no store and no date: only the lens's facts function did.
    assert reading.check_basis == frozenset() and reading.fields_basis == {Basis.TEXT}
    row = plain(reading)
    assert row["checkBasis"] == [] and SHELF.reads == {Basis.TEXT, Basis.STORE}
    assert row["lenses"]["test-shelf"]["slots"] == {"inspected": 1, "never-inspected": 2}
    # Two lenses share the row, so each slot records its turn: the as-of lens's slot comes before the shelf's at the same place.
    assert row["lenses"]["test-permit-dates"]["order"] == {"permit-expiry": 0}
    assert row["lenses"]["test-shelf"]["order"] == {"inspected": 1, "never-inspected": 2}


def test_consumers_see_what_they_saw_before_for_fixed_inputs(tmp_path):
    for day in (D1, D2):
        for log in (LOG, {"7": LOG["7"]}, None):
            data = shelf(tmp_path, log)
            new = PermitModel().read(TEXT, ModelContext(today=day, data_dir=data))
            old = OldPermitModel().read(TEXT, ModelContext(today=day, data_dir=data))
            assert new.findings == old.findings and new.missing == old.missing and new.record == old.record
            strip = lambda row: {**{k: v for k, v in row.items() if k not in ("lenses", "version", "fieldsBasis", "checkBasis")},  # noqa: E731
                                 "findings": [{k: v for k, v in f.items() if k not in ("lens", "check", "basis")} for f in row["findings"]]}
            assert strip(plain(new)) == strip(plain(old))
    # With no data directory there is no other record to read: the lens finds what the old check found, nothing.
    assert codes(PermitModel().read(TEXT, ModelContext(today=D1))) == codes(OldPermitModel().read(TEXT, ModelContext(today=D1)))


def test_a_review_is_reused_while_its_facts_stand_and_made_again_when_they_change(tmp_path):
    fields, checks = stored(_parse(TEXT)), [inspected, never_inspected]
    data = shelf(tmp_path)
    CHECKED.clear()
    first = SHELF.review(fields, checks, D1, records=Records(None, data, "permit 12.pdf"))
    assert CHECKED == ["12"] and not first.reused and [f.code for f in first.findings] == ["inspected"]
    again = SHELF.review(fields, checks, D1, records=Records(None, data, "permit 12.pdf"), known=first)
    assert again.reused and CHECKED == ["12"]                         # the same fields, facts, date, and lens: it stands
    shelf(tmp_path, {**LOG, "7": {"on": "2026-01-06", "by": "the county"}})     # another permit's row changes
    assert SHELF.review(fields, checks, D1, records=Records(None, data), known=first).reused and CHECKED == ["12"]
    shelf(tmp_path, {**LOG, "12": {"on": "2026-02-11", "by": "the city"}})      # this permit's row changes
    changed = SHELF.review(fields, checks, D1, records=Records(None, data), known=first)
    assert not changed.reused and CHECKED == ["12", "12"] and changed.facts_sha != first.facts_sha
    assert "2026-02-11" in changed.findings[0].message and changed.fields_sha == first.fields_sha
    shelf(tmp_path, None)                                             # the other record is gone
    gone = SHELF.review(fields, checks, D1, records=Records(None, data), known=first)
    assert not gone.reused and gone.findings == () and gone.facts_sha != first.facts_sha
    # With no handle the facts function is given the specification and no store.
    assert SHELF.review(fields, checks, D1).findings == ()


def test_a_facts_function_reads_only_what_its_check_declares():
    lens = Lens("test-undeclared", "what a facts function may read", gathers=True)

    def named(r, records):
        return getattr(records.community, "name", "")

    @lens.check("peek", Permit, fields=("number",), facts=named)
    def peek(r, as_of, facts):
        return []

    @lens.check("allowed", Permit, fields=("number",), facts=named, reads=(Basis.PROFILE,))
    def allowed(r, as_of, name):
        return [Finding("named", f"for {name}")]

    with pytest.raises(ValueError, match="does not declare"):
        lens.review(stored(_parse(TEXT)), [peek], D1, SimpleNamespace(name="Example Association"))
    review = lens.review(stored(_parse(TEXT)), [allowed], D1, SimpleNamespace(name="Example Association"))
    assert review.findings[0].message == "for Example Association" and review.findings[0].basis == {Basis.TEXT, Basis.PROFILE}
    assert allowed.reads == {Basis.TEXT, Basis.PROFILE} and peek.reads == {Basis.TEXT, Basis.STORE}
    handle = Records(SimpleNamespace(), "data", "a.pdf", "2026")
    assert handle.read == set() and handle.name == "a.pdf" and handle.period == "2026"     # the file's own name is no other record
    assert handle.data_dir == "data" and handle.read == {Basis.STORE} and not hasattr(handle, "today")


# The joined row ------------------------------------------------------------------------------------------------------


def test_one_lens_made_again_leaves_the_others_findings_in_their_places(tmp_path):
    data = shelf(tmp_path)
    row = {"id": "1", "name": "permit 12.pdf", **plain(PermitModel().read(TEXT, ModelContext(today=D1, data_dir=data)))}
    assert [f["code"] for f in row["findings"]] == ["numbered", "expires", "inspected", "keep"]
    # The as-of lens a year on: its finding changes where it stood, before the shelf's at the same place.
    later = join(row, DATES.review(row["fields"], [permit_expiry], D2))
    assert [f["code"] for f in later["findings"]] == ["numbered", "expired", "inspected", "keep"]
    assert later["lenses"]["test-shelf"] == row["lenses"]["test-shelf"]
    # The shelf's lens with the inspection gone: its finding leaves, and the as-of lens's stays where it was.
    shelf(tmp_path, {})
    emptied = join(later, SHELF.review(row["fields"], [inspected, never_inspected], D2, records=Records(None, data)))
    assert [f["code"] for f in emptied["findings"]] == ["numbered", "expired", "keep", "never-inspected"]
    fresh = plain(PermitModel().read(TEXT, ModelContext(today=D2, data_dir=data)))
    assert emptied["findings"] == fresh["findings"] and emptied["lenses"] == fresh["lenses"]
    # Joined with its own reviews, a row is the row.
    again = join(join(fresh, DATES.review(fresh["fields"], [permit_expiry], D2)),
                 SHELF.review(fresh["fields"], [inspected, never_inspected], D2, records=Records(None, data)))
    assert again == fresh


# The store -----------------------------------------------------------------------------------------------------------


def _library(monkeypatch, rows: list[dict], texts: dict[str, str]) -> None:
    import jason.tasks.library as library

    monkeypatch.setattr(library, "load", lambda data_dir: tuple(rows))
    monkeypatch.setattr(library, "distinct", lambda found: list(found))
    monkeypatch.setattr(library, "text_for", lambda data_dir, doc_id: texts[doc_id])


@pytest.fixture
def permits(monkeypatch, tmp_path):
    monkeypatch.setitem(REGISTRY, KIND, [PermitModel()])
    monkeypatch.setitem(reviews.LENSES, DATES.key, DATES)
    monkeypatch.setitem(reviews.LENSES, SHELF.key, SHELF)
    texts = {"1": TEXT, "2": "PERMIT 7 2030-01-01"}
    _library(monkeypatch, [{"id": "1", "name": "permit 12.pdf", "period": "2026", "kind": KIND.value},
                           {"id": "2", "name": "permit 7.pdf", "period": "2026", "kind": KIND.value}], texts)
    shelf(tmp_path)
    CHECKED.clear()
    GATHERED.clear()
    return texts


def test_a_run_keeps_the_records_reviews_beside_the_as_of_ones_and_makes_again_only_those_whose_facts_changed(permits, tmp_path):
    task.run(tmp_path, None, today=D1)
    file = tmp_path / "reviews" / "documents" / "test-shelf" / "2026-03-01.json"
    assert file.is_file() and (tmp_path / "reviews" / "documents" / "test-permit-dates" / "2026-03-01.json").is_file()
    one, two = (store.load(tmp_path, "test-shelf", D1)[doc] for doc in ("1", "2"))
    rows = task.load(tmp_path)
    assert one.key == ("1", rows[0]["textSha"], "test-shelf", SHELF.version, D1) and one.facts_sha and one.facts_sha != two.facts_sha
    assert [f["code"] for f in rows[0]["findings"] if f.get("lens") == "test-shelf"] == ["inspected"] and CHECKED == ["12", "7"]
    written = file.stat().st_mtime_ns
    task.run(tmp_path, None, today=D1)                       # the same documents, date, lens, and other records
    assert CHECKED == ["12", "7"] and file.stat().st_mtime_ns == written and task.load(tmp_path) == rows
    assert len(GATHERED) > 4                                 # the facts are gathered each time: their digest is how a change is seen
    shelf(tmp_path, {**LOG, "7": {"on": "2026-01-09", "by": "the county"}})     # one other record changes
    task.run(tmp_path, None, today=D1)
    assert CHECKED == ["12", "7", "7"]                       # exactly the review that rested on it is made again
    after = store.load(tmp_path, "test-shelf", D1)
    assert after["1"] == one and after["2"].facts_sha != two.facts_sha and "2026-01-09" in after["2"].findings[0].message
    shelf(tmp_path, {"7": LOG["7"]})                         # permit 12's inspection is removed
    task.run(tmp_path, None, today=D1)
    now = task.load(tmp_path)
    assert [f["code"] for f in now[0]["findings"]] == ["numbered", "expires", "keep"]
    assert (now[0]["fields"], now[0]["textSha"], now[0]["version"]) == (rows[0]["fields"], rows[0]["textSha"], rows[0]["version"])


def test_the_records_lens_is_made_again_from_the_stored_rows_and_reads_no_document(permits, tmp_path, monkeypatch, capsys):
    from jason import cli
    from jason.config import Settings

    task.run(tmp_path, None, today=D1)
    readings = (tmp_path / "documents" / "readings.json").read_bytes()
    monkeypatch.setitem(REGISTRY, KIND, [])                  # no reader and no text from here on: the stored rows and the other store
    permits.clear()
    CHECKED.clear()
    same = store.review_stored(tmp_path, None, D1, lens=SHELF)
    assert (same["readings"], same["made"], same["reused"], same["changed"], same["written"], CHECKED) == (2, 0, 2, [], [], [])
    shelf(tmp_path, {"7": LOG["7"]})                         # permit 12's inspection leaves the other store
    result = store.review_stored(tmp_path, None, D1, lens=SHELF)
    assert (result["made"], result["reused"], CHECKED) == (1, 1, ["12"]) and result["reads"] == ["store", "text"]
    assert [(c["id"], [f["code"] for f in c["vanish"]]) for c in result["changed"]] == [("1", ["inspected"])]
    lines = "\n".join(store.review_lines(result))
    assert "- inspected" in lines and "other records as they are on disk now" in lines and "does not hold it" in lines
    joined = store.joined_rows(tmp_path, None, D1, lens=SHELF)
    assert [f["code"] for f in joined[0]["findings"]] == ["numbered", "expires", "keep"] and joined[1] == task.load(tmp_path)[1]
    assert (tmp_path / "documents" / "readings.json").read_bytes() == readings      # the stored readings are as they were
    # The command takes the lens by its key; the as-of lens is the default.
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls, env=None: SimpleNamespace(payhoa_catalog=tmp_path / "payhoa.db")))
    assert cli.cmd_models(cli.build_parser().parse_args(["models", "--as-of", "2026-03-01", "--lens", "test-shelf", "--json"])) == 0
    out = json.loads(capsys.readouterr().out)
    assert (out["lens"], out["made"], out["reused"]) == ("test-shelf", 0, 2)
    assert cli.cmd_models(cli.build_parser().parse_args(["models", "--as-of", "2026-03-01", "--lens", "no-such-lens"])) == 2


def test_the_basis_report_counts_each_lens_and_what_the_readers_own_checks_read(permits, tmp_path):
    task.run(tmp_path, None, today=D1)
    report = task.basis_report(task.load(tmp_path))
    # Eight findings: "numbered" twice from the text alone; "keep" twice (it cites a law) in the reader; "expires" twice by
    # the as-of lens; "inspected" twice by the shelf's.
    assert report["totals"]["findings"] == 8 and report["byLens"] == {"test-permit-dates": 2, "test-shelf": 2}
    assert report["reviewInReaders"] == 2 and report["checkReads"] == {"readers": 1, "profile": 0, "store": 0, "today": 0}
    assert "a store 0" in "\n".join(task.basis_lines(report))
    apart = task.parts(task.load(tmp_path)[0])
    assert [f["code"] for f in apart["lens"]["test-shelf"]["findings"]] == ["inspected"]


# The real lens and the readers that moved ----------------------------------------------------------------------------


def test_the_records_lens_is_a_record_of_rows():
    assert RECORDS.key == "records" and RECORDS.gathers and RECORDS.needs_as_of and len(RECORDS.version) == 12
    assert RECORDS.reads == {Basis.TEXT, Basis.STORE, Basis.PROFILE} and not AS_OF.gathers and reviews.LENSES["records"] is RECORDS
    assert {DocumentKind.AGENDA, DocumentKind.MINUTES, DocumentKind.RESOLUTION, DocumentKind.ELECTION_RESULTS, DocumentKind.BANK_STATEMENT,
            DocumentKind.TAX_BILL, DocumentKind.TREASURER_REPORT, DocumentKind.BUDGET, DocumentKind.RESERVE_STUDY,
            DocumentKind.INSURANCE_POLICY, DocumentKind.EVIDENCE_OF_INSURANCE, DocumentKind.BYLAWS, DocumentKind.POLICY} <= set(RECORDS.kinds)
    for check in RECORDS.checks.values():
        names = {f.name for f in dataclasses.fields(check.record)}
        assert set(check.fields) <= names and set(check.fields) <= set(reviews.hints(check.record)), check.key
        # Its facts come from a named function that reads a store; the check itself is handed no data directory and names none.
        assert check.facts is not None and check.facts.__name__ != "<lambda>" and Basis.STORE in check.reads, check.key
        assert "data_dir" not in inspect.getsource(check.fn) and "context" not in inspect.signature(check.fn).parameters, check.key
    # The checks that also need the date say so; the rest are given none.
    assert {c.key for c in RECORDS.checks.values() if c.dated} == {"agenda-notice", "agenda-minutes", "study-schedule"}
    listed = {c for models in REGISTRY.values() for m in models for c in m.lens_checks if c.lens is RECORDS}
    assert listed == set(RECORDS.checks.values())


AGENDA = ("Example Community Association\nRegular Meeting of the Board of Directors\nTo be held on March 17, 2026 at 7:00 pm on Zoom\n"
          "Agenda\n1. Call to Order\n2. Open Forum\n3. Adjournment\n")
MINUTES = ("Example Community Association\nRegular Meeting of the Board of Directors\nHeld on March 17, 2026 at 7:00 pm on Zoom\n"
           "Minutes\n1. Call to Order\nThe meeting was called to order at 7:02 pm. Directors Present: Pat Board, Sam Board\n"
           "2. Open Forum\nNo member spoke.\n3. Adjournment\nThe meeting was adjourned at 7:40 pm.\n")


def test_minutes_are_set_beside_the_agenda_on_file_by_the_lens_and_parsed_the_same_without_it(monkeypatch, tmp_path):
    from jason.community.models import meetings

    library = [{"id": "a1", "name": "2026-03-17 agenda.pdf", "period": "2026-03-17", "kind": "agenda"}]
    monkeypatch.setattr(meetings, "_library", lambda d: tuple(library))
    monkeypatch.setattr(meetings, "_library_text", lambda d, doc_id: AGENDA)
    context = ModelContext(today=date(2026, 3, 20), data_dir=tmp_path, name="2026-03-17 minutes.pdf")
    on_file = read(DocumentKind.MINUTES, MINUTES, context)
    found = {f.code: f for f in on_file.findings}
    assert "agenda-on-file" in found and "2026-03-17 agenda.pdf" in found["agenda-on-file"].message
    assert (found["agenda-on-file"].lens, found["agenda-on-file"].check) == ("records", "minutes-agenda")
    assert Basis.STORE in found["agenda-on-file"].basis and Basis.TODAY not in found["agenda-on-file"].basis
    assert Basis.STORE not in on_file.check_basis and Basis.STORE not in on_file.fields_basis    # only the facts function read the library
    library.clear()                                          # the agenda leaves the library
    missing = read(DocumentKind.MINUTES, MINUTES, ModelContext(today=date(2026, 3, 20), data_dir=tmp_path, name="2026-03-17 minutes.pdf"))
    codes_now = [f.code for f in missing.findings]
    assert "no-agenda-on-file" in codes_now and "agenda-on-file" not in codes_now
    assert to_plain(on_file.record) == to_plain(missing.record) and on_file.own_findings == missing.own_findings
    assert codes_now.index("no-agenda-on-file") == [f.code for f in on_file.findings].index("agenda-on-file")     # the same place
    a, b = (next(r for r in reading.reviews if r.lens == "records") for reading in (on_file, missing))
    assert a.fields_sha == b.fields_sha and a.facts_sha != b.facts_sha


def test_an_agenda_is_set_beside_the_minutes_on_file_once_they_are_due(monkeypatch, tmp_path):
    from jason.community.models import meetings

    library = [{"id": "m1", "name": "2026-03-17 minutes.pdf", "period": "2026-03-17", "kind": "minutes"}]
    monkeypatch.setattr(meetings, "_library", lambda d: tuple(library))
    monkeypatch.setattr(meetings, "_mailings", lambda d: ())
    late = date(2026, 6, 1)
    held = read(DocumentKind.AGENDA, AGENDA, ModelContext(today=late, data_dir=tmp_path, name="2026-03-17 agenda.pdf"))
    assert "no-minutes-on-file" not in [f.code for f in held.findings]
    library.clear()
    lacking = read(DocumentKind.AGENDA, AGENDA, ModelContext(today=late, data_dir=tmp_path, name="2026-03-17 agenda.pdf"))
    finding = next(f for f in lacking.findings if f.code == "no-minutes-on-file")
    assert (finding.lens, finding.check) == ("records", "agenda-minutes") and {Basis.STORE, Basis.TODAY} <= finding.basis
    # Before the thirty days run, the same library gives no finding: the check needs the date as well as the library.
    early = read(DocumentKind.AGENDA, AGENDA, ModelContext(today=date(2026, 3, 20), data_dir=tmp_path, name="2026-03-17 agenda.pdf"))
    assert "no-minutes-on-file" not in [f.code for f in early.findings]
    assert to_plain(early.record) == to_plain(lacking.record) == to_plain(held.record)
