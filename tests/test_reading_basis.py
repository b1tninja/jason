"""The inventory (docs/ingestion-and-review.md, step 1): a finding's basis is observed from what its check read, a
reading's fields from what its parse read, and each stored row records its text's digest, its reader's version, and its
as-of date. Every reader and context here is made up."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from jason.community.document_models import (
    REGISTRY,
    Basis,
    DocumentModel,
    Finding,
    ModelContext,
    ModelReading,
    Severity,
    read,
    reader_version,
)
from jason.community.symbols import DocumentKind
from jason.tasks import document_models as task

TODAY = date(2026, 3, 1)
KIND = DocumentKind.COMMITTEE_REPORT


@dataclass
class Note:
    subject: str = ""
    due: date | None = None
    filed: str = ""


class Profile:
    def subjects(self) -> tuple[str, ...]:
        return ("roof",)


class NoteModel(DocumentModel):
    """A made-up reader: ``parse`` reads the text only; ``check`` reads whatever ``reads`` names."""

    kind = KIND
    name = "test-note"
    required = ("subject", "due")
    reads: tuple[str, ...] = ()

    def parse(self, text, context):
        if not text.startswith("NOTE"):
            return None
        return Note(subject="roof", due=date(2026, 2, 1) if "due" in text else None)

    def check(self, record, context):
        found = [Finding("subject-named", "the note names its subject", Severity.INFO)]
        if "today" in self.reads and record.due and record.due < context.today:
            found.append(Finding("past-due", "the note's date has passed"))
        if "profile" in self.reads and record.subject not in context.community.subjects():
            found.append(Finding("unknown-subject", "the specification has no such subject"))
        if "store" in self.reads and context.data_dir is not None:
            found.append(Finding("filed", "the store was looked in"))
        if "law" in self.reads:
            found.append(Finding("kept", "a record to keep", Severity.INFO, "CIV 0000(a)"))
        return found


def reader(*reads: str) -> NoteModel:
    model = NoteModel()
    model.reads = reads
    return model


def context(**kw) -> ModelContext:
    return ModelContext(community=kw.pop("community", Profile()), data_dir=kw.pop("data_dir", None), today=TODAY, **kw)


def bases(reading: ModelReading) -> dict[str, set[Basis]]:
    return {f.code: set(f.basis) for f in reading.findings}


def test_a_check_that_only_reads_its_record_is_text():
    reading = reader().read("NOTE due", context())
    assert bases(reading) == {"subject-named": {Basis.TEXT}}
    assert reading.fields_basis == {Basis.TEXT}


def test_a_check_that_reads_today_is_today():
    assert bases(reader("today").read("NOTE due", context()))["past-due"] == {Basis.TEXT, Basis.TODAY}


def test_a_check_that_reads_the_profile_is_profile():
    reading = reader("profile").read("NOTE due", context())
    assert bases(reading)["subject-named"] == {Basis.TEXT, Basis.PROFILE}  # per call: every finding of the check carries it
    assert reading.fields_basis == {Basis.TEXT}  # the parse read nothing but the text


def test_a_check_that_reads_the_data_directory_is_store_and_an_authority_is_law(tmp_path):
    found = bases(reader("store", "law").read("NOTE due", context(data_dir=tmp_path)))
    assert found["filed"] == {Basis.TEXT, Basis.STORE}
    assert found["kept"] == {Basis.TEXT, Basis.STORE, Basis.LAW}
    assert Basis.LAW not in found["subject-named"]


def test_what_the_parse_read_marks_the_fields_not_the_findings(tmp_path):
    class Filed(NoteModel):
        def parse(self, text, context):
            record = super().parse(text, context)
            if record is not None and context.data_dir is not None:
                record.filed = "yes" if (Path(context.data_dir) / "notes.json").is_file() else "no"
            return record

    reading = Filed().read("NOTE", context(data_dir=tmp_path))
    assert reading.fields_basis == {Basis.TEXT, Basis.STORE}
    found = bases(reading)
    assert found["missing-due"] == {Basis.TEXT, Basis.STORE}  # a missing field's finding has the fields' basis
    assert found["subject-named"] == {Basis.TEXT}             # the check itself read only the record
    row = reading.as_dict()
    assert row["fieldsBasis"] == ["text", "store"]
    assert [f["basis"] for f in row["findings"]] == [["text", "store"], ["text"]]


def test_the_context_returns_what_it_was_given_and_counts_each_read(tmp_path):
    profile = Profile()
    ctx = ModelContext(profile, tmp_path, TODAY, "note.pdf", "2026-03", True)
    assert ctx.since() == frozenset()
    assert (ctx.name, ctx.period, ctx.confidential) == ("note.pdf", "2026-03", True) and ctx.since() == frozenset()
    mark = ctx.mark()
    assert ctx.today == TODAY and ctx.since(mark) == {Basis.TODAY}
    mark = ctx.mark()
    assert ctx.community is profile and ctx.data_dir == tmp_path
    assert ctx.since(mark) == {Basis.PROFILE, Basis.STORE} and ctx.since() == {Basis.PROFILE, Basis.STORE, Basis.TODAY}
    assert replace(ctx, name="other.pdf").since() == frozenset()  # a new context starts with nothing read
    assert ModelContext().since() == frozenset()


def test_a_finding_is_built_and_compared_as_before():
    plain = Finding("code", "message", Severity.INFO, "CIV 0000")
    assert plain.basis == frozenset()
    assert plain.as_dict() == {"code": "code", "message": "message", "severity": "info", "authority": "CIV 0000"}
    stamped = replace(plain, basis=(Basis.TODAY, Basis.TEXT))
    assert stamped == plain and hash(stamped) == hash(plain) and stamped in (plain,)
    assert stamped.as_dict()["basis"] == ["text", "today"]
    assert Finding(code="c", message="m").severity is Severity.CHECK


def test_a_stand_in_context_leaves_the_basis_unobserved():
    class Bare:
        community, data_dir, today, name, period, confidential = None, None, TODAY, "", "", False

    reading = reader("today").read("NOTE due", Bare())
    assert all(f.basis == frozenset() for f in reading.findings) and reading.fields_basis == frozenset()
    assert "fieldsBasis" not in reading.as_dict() and "basis" not in reading.as_dict()["findings"][0]


def test_what_a_readers_own_read_does_afterwards_is_settled_by_the_registry(monkeypatch, tmp_path):
    class Afterwards(NoteModel):
        def read(self, text, context, kind=None):
            reading = super().read(text, context, kind)
            if reading is not None and context.data_dir is not None:
                reading.findings += (Finding("added-late", "a finding the reader's own read adds"),)
            return reading

    monkeypatch.setitem(REGISTRY, KIND, [Afterwards()])
    found = bases(read(KIND, "NOTE due", context(data_dir=tmp_path)))
    assert found["subject-named"] == {Basis.TEXT, Basis.STORE}
    assert found["added-late"] == {Basis.TEXT, Basis.STORE}


def test_the_reader_version_is_a_short_hash_of_its_source():
    version = reader_version(NoteModel())
    assert len(version) == 12 and int(version, 16) >= 0
    assert version == reader_version(NoteModel) == reader("today").read("NOTE", context()).version
    assert reader("today").read("NOTE", context()).as_dict()["version"] == version


def _library(monkeypatch, rows: list[dict], texts: dict[str, str]) -> None:
    import jason.tasks.library as library

    monkeypatch.setattr(library, "load", lambda data_dir: tuple(rows))
    monkeypatch.setattr(library, "distinct", lambda found: list(found))
    monkeypatch.setattr(library, "text_for", lambda data_dir, doc_id: texts.get(doc_id, ""))


def test_a_stored_row_records_its_text_digest_reader_version_and_as_of_date(monkeypatch, tmp_path):
    model = reader("today", "law")
    monkeypatch.setitem(REGISTRY, KIND, [model])
    _library(monkeypatch, [{"id": "1", "name": "note.pdf", "period": "2026-02", "kind": KIND.value},
                           {"id": "2", "name": "other.pdf", "period": "2026-02", "kind": KIND.value},
                           {"id": "3", "name": "blank.pdf", "period": "2026-02", "kind": KIND.value}],
             {"1": "NOTE due", "2": "not a note"})
    task.run(tmp_path, Profile(), today=TODAY)
    one, two, three = task.load(tmp_path)
    assert one["textSha"] == task.text_sha("NOTE due") and len(one["textSha"]) == 64
    assert (one["asOf"], one["version"], one["fieldsBasis"]) == ("2026-03-01", reader_version(model), ["text"])
    assert {f["code"]: f["basis"] for f in one["findings"]} == {
        "subject-named": ["text", "today"], "past-due": ["text", "today"], "kept": ["text", "today", "law"]}
    # Every key a reader of the store already used is still there.
    assert {"id", "name", "period", "kind", "confidential", "hasText", "model", "complete", "missing", "fields", "findings"} <= set(one)
    # A text no model recognized still records what was read and when; a file with no text records neither.
    assert two["model"] is None and two["textSha"] == task.text_sha("not a note") and two["asOf"] == "2026-03-01" and "version" not in two
    assert three["hasText"] is False and "textSha" not in three and "asOf" not in three


def test_a_drive_reading_read_again_records_the_same_keys(monkeypatch, tmp_path):
    from jason.tasks import drive_minutes

    class Minutes(NoteModel):
        kind = DocumentKind.MINUTES

    monkeypatch.setitem(REGISTRY, DocumentKind.MINUTES, [Minutes()])
    (tmp_path / "documents").mkdir()
    (tmp_path / drive_minutes.FILES).mkdir(parents=True)
    (tmp_path / drive_minutes.FILES / "abc.txt").write_text("NOTE due", encoding="utf-8")
    store = tmp_path / "documents" / "readings.json"
    store.write_text(json.dumps({"readings": [{"id": "drive-abc", "name": "Minutes", "period": "2026-02-01", "kind": "minutes",
                                               "hasText": True, "model": None, "source": "Drive"}]}), encoding="utf-8")
    assert drive_minutes.reread(tmp_path, Profile()) == 1
    row = task.load(tmp_path)[0]
    assert row["textSha"] == task.text_sha("NOTE due") and row["asOf"] == date.today().isoformat()
    assert row["version"] == reader_version(Minutes) and row["source"] == "Drive" and row["model"] == "test-note"


OLD_ROWS = [
    {"id": "1", "name": "a.pdf", "period": "2025-01", "kind": "invoice", "confidential": False, "hasText": True, "model": "invoice",
     "complete": True, "missing": [], "fields": {"total": 100},
     "findings": [{"code": "due-date-passed", "message": "it was due", "severity": "check", "authority": ""}]},
    {"id": "2", "name": "b.pdf", "period": "2025-02", "kind": "invoice", "confidential": False, "hasText": False, "model": None},
]


def test_rows_stored_before_the_new_keys_still_load_and_report(tmp_path):
    (tmp_path / "documents").mkdir()
    (tmp_path / "documents" / "readings.json").write_text(json.dumps({"readAt": "2025-03-01T00:00:00+00:00", "readings": OLD_ROWS}),
                                                           encoding="utf-8")
    rows = task.load(tmp_path)
    assert task.coverage(rows)["read"] == 1 and task.summary(tmp_path, kind="invoice")["found"]
    report = task.basis_report(rows)
    assert report["found"] and (report["readings"], report["observed"]) == (1, 0)
    assert report["totals"] == {"findings": 1, "ingestion": 0, "review": 0, "unobserved": 1, "ingestionThroughFields": 0}
    assert report["readers"][0]["codes"][0]["class"] == "not observed"
    assert any("before the basis was recorded" in c for c in report["caveats"])
    assert task.basis_lines(report)


def test_the_basis_report_says_which_findings_are_reviews_and_whose_fields_read_context():
    def row(model, fields, *findings):
        return {"id": "x", "kind": "invoice", "hasText": True, "model": model, "version": "abc123abc123", "asOf": "2026-03-01",
                "fieldsBasis": fields, "findings": [{"code": c, "message": "", "severity": "check", "authority": "", "basis": b}
                                                    for c, b in findings]}

    rows = [row("bill", ["text"], ("two-totals", ["text"]), ("past-due", ["text", "today"])),
            row("bill", ["text"], ("two-totals", ["text"])),
            row("agenda", ["text", "store"], ("no-time", ["text"]), ("late-notice", ["text", "profile", "today", "law"])),
            row("agenda", ["text", "store"], ("late-notice", ["text", "today", "law"]))]
    report = task.basis_report(rows)
    assert report["totals"] == {"findings": 6, "ingestion": 3, "review": 3, "unobserved": 0, "ingestionThroughFields": 1}
    assert report["fieldsFromContext"] == [{"reader": "agenda", "readings": 2, "store": 2}]
    assert report["asOf"] == {"2026-03-01": 4}
    assert report["byBasis"] == {"text": 3, "text+profile+today+law": 1, "text+today": 1, "text+today+law": 1}
    agenda, bill = report["readers"]
    assert {c["code"]: c["class"] for c in bill["codes"]} == {"two-totals": "ingestion", "past-due": "review"}
    late = next(c for c in agenda["codes"] if c["code"] == "late-notice")
    assert (late["count"], late["textOnly"], late["basis"], late["always"]) == (2, 0, ["text", "profile", "today", "law"], ["text", "today", "law"])
    assert next(c for c in agenda["codes"] if c["code"] == "no-time")["throughFields"] == 1
    assert (bill["ingestion"], bill["review"], bill["versions"]) == (2, 1, ["abc123abc123"])
    lines = "\n".join(task.basis_lines(report))
    assert "past-due" in lines and "review" in lines and "agenda" in lines
    assert task.basis_report(rows, kind="minutes")["found"] is False
