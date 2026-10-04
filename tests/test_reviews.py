"""The review store and the first lens (docs/ingestion-and-review.md, step 2): what depends on the date is a lens's
finding, made from a reading's stored fields; a reading shows what it showed before; a review stands until its key
changes. Every reader, text, and profile here is made up."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community import reviews
from jason.community.document_models import REGISTRY, Basis, DocumentModel, Finding, ModelContext, Severity, read, to_plain
from jason.community.reviews import AS_OF, Lens, Review, Reviewed, hydrate, join, position, stored, view
from jason.community.symbols import DocumentKind
from jason.tasks import document_models as task
from jason.tasks import document_reviews as store

KIND = DocumentKind.COMMITTEE_REPORT
D1, D2 = date(2026, 3, 1), date(2027, 3, 1)


class PermitKind(Enum):
    TEMPORARY = "temporary"
    STANDING = "standing"


@dataclass(frozen=True)
class Condition:
    text: str
    by: date | None = None


@dataclass
class Permit:
    number: str = ""
    kind: PermitKind | None = None
    issued: date | None = None
    expires: date | None = None
    conditions: tuple[Condition, ...] = ()
    days_left: int | None = None    # as of a date: the lens fills it, not the parse


LENS = Lens("test-dates", "As of a date, is the permit still good?", needs_as_of=True)
CALLS: list[date] = []


@LENS.check("permit-expiry", Permit, fields=("number", "expires"))
def permit_expiry(r, as_of, _facts=None):
    CALLS.append(as_of)
    if not r.expires:
        return Reviewed((), {"days_left": None})
    left = (r.expires - as_of).days
    if left < 0:
        return Reviewed((Finding("expired", f"permit {r.number} expired {r.expires}", Severity.CHECK, "CODE 1(a)"),), {"days_left": left})
    return Reviewed((Finding("expires", f"permit {r.number} expires {r.expires} ({left} days)", Severity.INFO),), {"days_left": left})


@LENS.check("conditions-due", Permit, fields=("conditions",))
def conditions_due(r, as_of, _facts=None):
    return [Finding("condition-overdue", f"'{c.text}' was due {c.by}") for c in r.conditions if c.by and c.by < as_of]


def _parse(text: str) -> Permit | None:
    if not text.startswith("PERMIT"):
        return None
    words = text.split()
    conditions = tuple(Condition(w.split("=")[0], date.fromisoformat(w.split("=")[1])) for w in words if "=" in w)
    return Permit(number=words[1], kind=PermitKind.TEMPORARY if "temporary" in words else PermitKind.STANDING,
                  issued=date(2026, 1, 1), expires=date.fromisoformat(words[2]) if len(words) > 2 and words[2][0].isdigit() else None,
                  conditions=conditions)


class PermitModel(DocumentModel):
    """A made-up reader: its own findings rest on the text; what depends on the date is the lens's, in a slot."""

    kind = KIND
    name = "test-permit"
    required = ("number", "expires")
    lens_checks = (permit_expiry, conditions_due)

    def parse(self, text, context):
        return _parse(text)

    def check(self, r, context):
        return [Finding("numbered", f"permit {r.number}", Severity.INFO), permit_expiry, Finding("keep", "a record to keep", Severity.INFO, "CODE 2")]


class OldPermitModel(DocumentModel):
    """The same reader as it was before the lens: the date's findings made inside ``check``, the field inside ``parse``."""

    kind = KIND
    name = "test-permit"
    required = ("number", "expires")

    def parse(self, text, context):
        r = _parse(text)
        if r is not None and r.expires:
            r.days_left = (r.expires - context.today).days
        return r

    def check(self, r, context):
        found = [Finding("numbered", f"permit {r.number}", Severity.INFO)]
        if r.expires and r.expires < context.today:
            found.append(Finding("expired", f"permit {r.number} expired {r.expires}", Severity.CHECK, "CODE 1(a)"))
        elif r.expires:
            found.append(Finding("expires", f"permit {r.number} expires {r.expires} ({(r.expires - context.today).days} days)", Severity.INFO))
        found.append(Finding("keep", "a record to keep", Severity.INFO, "CODE 2"))
        found += [Finding("condition-overdue", f"'{c.text}' was due {c.by}") for c in r.conditions if c.by and c.by < context.today]
        return found


TEXT = "PERMIT 12 2026-06-01 temporary fence=2026-02-01 gate=2026-09-01"


def ctx(today: date = D1, **kw) -> ModelContext:
    return ModelContext(today=today, **kw)


def codes(reading) -> list[str]:
    return [f.code for f in reading.findings]


# A reading and its lens ---------------------------------------------------------------------------------------------


def test_a_lens_finding_changes_with_the_date_and_the_reading_does_not():
    early, late = PermitModel().read(TEXT, ctx(D1)), PermitModel().read(TEXT, ctx(D2))
    assert codes(early) == ["numbered", "expires", "keep", "condition-overdue"]
    assert codes(late) == ["numbered", "expired", "keep", "condition-overdue", "condition-overdue"]
    # What the reader itself found is the same on both days; only the lens's part moved.
    assert early.own_findings == late.own_findings and [f.code for f in early.own_findings] == ["numbered", "keep"]
    parsed = {k: v for k, v in to_plain(early.record).items() if k != "days_left"}
    assert parsed == {k: v for k, v in to_plain(late.record).items() if k != "days_left"}
    assert (early.record.days_left, late.record.days_left) == (92, -273)
    assert task.text_sha(TEXT) == task.text_sha(TEXT) and early.version == late.version


def test_a_lens_finding_says_which_lens_made_it_and_what_it_read():
    reading = PermitModel().read(TEXT, ctx(D2))
    by_code = {f.code: f for f in reading.findings}
    assert by_code["expired"].lens == "test-dates" and by_code["expired"].basis == {Basis.TEXT, Basis.TODAY, Basis.LAW}
    assert by_code["condition-overdue"].basis == {Basis.TEXT, Basis.TODAY}
    assert by_code["numbered"].lens == "" and by_code["numbered"].basis == {Basis.TEXT}   # the check itself read nothing but the record
    assert reading.fields_basis == {Basis.TEXT}                                           # and the parse read no date
    row = reading.as_dict()
    assert [f.get("lens") for f in row["findings"]] == [None, "test-dates", None, "test-dates", "test-dates"]
    assert row["lenses"] == {"test-dates": {"version": LENS.version, "asOf": "2027-03-01",
                                            "slots": {"permit-expiry": 1, "conditions-due": 2}, "fields": ["days_left"]}}


def test_a_reading_shows_what_it_showed_before_for_a_fixed_date():
    for day in (D1, D2):
        new, old = PermitModel().read(TEXT, ctx(day)), OldPermitModel().read(TEXT, ctx(day))
        assert new.findings == old.findings and new.missing == old.missing and new.record == old.record
        was, now = old.as_dict(), new.as_dict()
        assert set(now) - set(was) == {"lenses"}
        strip = lambda row: {**{k: v for k, v in row.items() if k not in ("lenses", "version", "fieldsBasis")},  # noqa: E731
                             "findings": [{k: v for k, v in f.items() if k not in ("lens", "basis")} for f in row["findings"]]}
        assert strip(now) == strip(was)


def test_a_check_gets_only_the_fields_it_names_as_their_types():
    seen = {}
    lens = Lens("test-seen", "what a check is given", needs_as_of=True)

    @lens.check("look", Permit, fields=("kind", "conditions", "expires"))
    def look(r, as_of, _facts=None):
        seen.update(vars(r))
        return []

    lens.review(stored(_parse(TEXT)), [look], D1)
    assert set(seen) == {"kind", "conditions", "expires"}
    assert seen["kind"] is PermitKind.TEMPORARY and seen["expires"] == date(2026, 6, 1)
    assert seen["conditions"] == (Condition("fence", date(2026, 2, 1)), Condition("gate", date(2026, 9, 1)))


def test_a_stored_value_is_rebuilt_by_its_field_type_and_left_alone_when_it_does_not_fit():
    plain = stored(_parse(TEXT))
    assert plain["expires"] == "2026-06-01" and plain["kind"] == "temporary" and plain["conditions"][0] == {"text": "fence", "by": "2026-02-01"}
    back = view(Permit, [f.name for f in dataclasses.fields(Permit)], plain)
    assert Permit(**vars(back)) == _parse(TEXT)
    assert hydrate("not a date", date | None) == "not a date" and hydrate("other", PermitKind | None) == "other"
    assert hydrate(None, date) is None and hydrate([1, 2], tuple[int, ...]) == (1, 2)


def test_a_check_that_needs_the_profile_is_given_its_facts_not_the_profile():
    lens = Lens("test-facts", "against the profile", needs_as_of=True)
    given = []

    def limit(r, community):
        return community.limits()[r.kind]

    @lens.check("within-limit", Permit, fields=("kind", "issued", "expires"), facts=limit)
    def within(r, as_of, days):
        given.append(days)
        return [Finding("too-long", f"runs more than {days} days")] if (r.expires - r.issued).days > days else []

    profile = SimpleNamespace(limits=lambda: {PermitKind.TEMPORARY: 90, PermitKind.STANDING: 400})
    review = lens.review(stored(_parse(TEXT)), [within], D1, profile)
    assert given == [90] and [f.code for f in review.findings] == ["too-long"]
    assert review.findings[0].basis == {Basis.TEXT, Basis.PROFILE, Basis.TODAY} and lens.reads == {Basis.TEXT, Basis.PROFILE}
    # The same key, fields, and facts: the stored review stands. Other facts: it is made again.
    assert lens.review(stored(_parse(TEXT)), [within], D1, profile, known=review).reused and given == [90]
    looser = SimpleNamespace(limits=lambda: {PermitKind.TEMPORARY: 200})
    again = lens.review(stored(_parse(TEXT)), [within], D1, looser, known=review)
    assert not again.reused and given == [90, 200] and again.findings == () and again.facts_sha != review.facts_sha


def test_a_slot_the_reader_does_not_list_is_an_error():
    class Forgot(PermitModel):
        lens_checks = (conditions_due,)

    with pytest.raises(ValueError, match="lens_checks"):
        Forgot().read(TEXT, ctx())


def test_a_review_stands_until_part_of_its_key_changes():
    plain, checks = stored(_parse(TEXT)), [permit_expiry]
    CALLS.clear()
    first = LENS.review(plain, checks, D1)
    assert CALLS == [D1] and not first.reused and (first.lens, first.lens_version, first.as_of) == ("test-dates", LENS.version, D1)
    assert LENS.review(plain, checks, D1, known=first).reused and CALLS == [D1]                 # nothing changed
    assert not LENS.review(plain, checks, D2, known=first).reused and CALLS == [D1, D2]        # the date
    assert not LENS.review(plain, checks, D1, known=replace(first, lens_version="an older one")).reused   # the lens
    assert not LENS.review({**plain, "expires": "2026-07-01"}, checks, D1, known=first).reused  # a field the check reads
    assert LENS.review({**plain, "issued": "2025-01-01"}, checks, D1, known=first).reused       # a field it does not read
    assert len(CALLS) == 4


# The joined row ------------------------------------------------------------------------------------------------------


def test_a_stored_row_joined_with_its_own_review_is_the_row_and_another_date_moves_only_the_lens():
    reading = PermitModel().read(TEXT, ctx(D1))
    row = json.loads(json.dumps({"id": "1", **reading.as_dict()}, default=str))
    same = LENS.review(row["fields"], list(PermitModel.lens_checks), D1)
    assert join(row, same) == row
    later = join(row, LENS.review(row["fields"], list(PermitModel.lens_checks), D2))
    assert [f["code"] for f in later["findings"]] == ["numbered", "expired", "keep", "condition-overdue", "condition-overdue"]
    assert later["fields"]["days_left"] == -273 and later["lenses"]["test-dates"]["asOf"] == "2027-03-01"
    assert [f for f in later["findings"] if not f.get("lens")] == [f for f in row["findings"] if not f.get("lens")]
    assert later == json.loads(json.dumps({"id": "1", **PermitModel().read(TEXT, ctx(D2)).as_dict()}, default=str))


def test_a_slot_that_was_empty_keeps_its_place():
    early = date(2026, 1, 15)   # before either condition is due
    row = json.loads(json.dumps(PermitModel().read("PERMIT 12 fence=2026-02-01", ctx(early)).as_dict(), default=str))
    assert [f["code"] for f in row["findings"]] == ["missing-expires", "numbered", "keep"]
    assert row["lenses"]["test-dates"]["slots"] == {"permit-expiry": 2, "conditions-due": 3}
    later = join(row, LENS.review(row["fields"], list(PermitModel.lens_checks), D1))
    assert [f["code"] for f in later["findings"]] == ["missing-expires", "numbered", "keep", "condition-overdue"]


def test_a_slot_is_counted_again_after_a_readers_own_read_drops_or_rewords_a_finding():
    class Afterwards(PermitModel):
        def read(self, text, context, kind=None):
            reading = super().read(text, context, kind)
            reading.findings = tuple(replace(f, message="permit, reworded") if f.code == "numbered" else f
                                     for f in reading.findings if f.code != "missing-expires") + (Finding("added-late", "by the read"),)
            return reading

    reading = Afterwards().read("PERMIT 12 fence=2026-02-01", ctx(D1))
    assert codes(reading) == ["numbered", "keep", "condition-overdue", "added-late"]
    assert reading.as_dict()["lenses"]["test-dates"]["slots"] == {"permit-expiry": 1, "conditions-due": 2}
    assert position((Finding("a", ""), Finding("b", "")), [Finding("b", "other words"), Finding("c", "")]) == 1


# The store -----------------------------------------------------------------------------------------------------------


def _library(monkeypatch, rows: list[dict], texts: dict[str, str]) -> None:
    import jason.tasks.library as library

    monkeypatch.setattr(library, "load", lambda data_dir: tuple(rows))
    monkeypatch.setattr(library, "distinct", lambda found: list(found))
    monkeypatch.setattr(library, "text_for", lambda data_dir, doc_id: texts[doc_id])


@pytest.fixture
def permits(monkeypatch):
    monkeypatch.setitem(REGISTRY, KIND, [PermitModel()])
    monkeypatch.setitem(reviews.LENSES, LENS.key, LENS)
    texts = {"1": TEXT, "2": "PERMIT 7 2030-01-01"}
    _library(monkeypatch, [{"id": "1", "name": "permit 12.pdf", "period": "2026", "kind": KIND.value},
                           {"id": "2", "name": "permit 7.pdf", "period": "2026", "kind": KIND.value, "confidential": True}], texts)
    CALLS.clear()
    return texts


def test_a_run_stores_each_review_apart_and_makes_it_again_only_when_its_key_changes(permits, tmp_path):
    task.run(tmp_path, None, today=D1)
    file = tmp_path / "reviews" / "documents" / "test-dates" / "2026-03-01.json"
    assert file.is_file() and store.path(tmp_path, "test-dates", D1) == file
    body = json.loads(file.read_text(encoding="utf-8"))
    assert (body["lens"], body["asOf"], sorted(body["reviews"])) == ("test-dates", "2026-03-01", ["1", "2"])
    one = store.load(tmp_path, "test-dates", D1)["1"]
    row = task.load(tmp_path)[0]
    assert one.key == ("1", row["textSha"], "test-dates", LENS.version, D1) and (one.reading_version, one.produced_by) == (row["version"], "rule")
    assert (one.reader, one.kind) == ("test-permit", KIND.value) and [f.code for f in one.checks["permit-expiry"]] == ["expires"]
    assert one.fields == {"days_left": 92} and [f["code"] for f in row["findings"] if f.get("lens")] == ["expires", "condition-overdue"]
    assert len(CALLS) == 2
    written = file.stat().st_mtime_ns
    task.run(tmp_path, None, today=D1)                      # the same documents, texts, lens, and date
    assert len(CALLS) == 2 and file.stat().st_mtime_ns == written and task.load(tmp_path)[0] == row
    permits["1"] = TEXT + " shed=2026-01-05"               # another text for document 1: its review is made again
    task.run(tmp_path, None, today=D1)
    assert len(CALLS) == 3 and store.load(tmp_path, "test-dates", D1)["1"].text_sha == task.text_sha(permits["1"])
    task.run(tmp_path, None, today=D2)                      # another date: both, in a file of their own; the earlier one is kept
    assert len(CALLS) == 5 and store.dates(tmp_path, "test-dates") == [D1, D2]


def test_as_of_makes_the_lens_again_from_the_stored_rows_and_reads_no_document(permits, tmp_path, monkeypatch):
    task.run(tmp_path, None, today=D1)
    readings = (tmp_path / "documents" / "readings.json").read_bytes()
    monkeypatch.setitem(REGISTRY, KIND, [])                 # no reader and no text from here on: only the stored rows
    permits.clear()
    CALLS.clear()
    same = store.review_stored(tmp_path, None, D1, lens=LENS)
    assert (same["readings"], same["made"], same["reused"], same["changed"], same["written"], CALLS) == (2, 0, 2, [], [], [])
    result = store.review_stored(tmp_path, None, D2, lens=LENS)
    assert (result["lens"], result["version"], result["asOf"], result["made"], result["reused"]) == ("test-dates", LENS.version, "2027-03-01", 2, 0)
    assert result["storedAsOf"] == {"2026-03-01": 2} and result["reads"] == ["text"]
    first, second = result["changed"]
    assert [f["code"] for f in first["appear"]] == ["expired", "condition-overdue"] and [f["code"] for f in first["vanish"]] == ["expires"]
    assert first["fields"] == {"days_left": [92, -273]}
    # A confidential file's findings are leads like any other; its fields are held back unless asked for.
    assert second["reworded"][0]["code"] == "expires" and second["fields"] == {"days_left": ["(held back)", "(held back)"]}
    assert store.review_stored(tmp_path, None, D2, lens=LENS, include_confidential=True)["changed"][1]["fields"] == {"days_left": [1402, 1037]}
    assert (tmp_path / "documents" / "readings.json").read_bytes() == readings     # the stored readings are as they were
    joined = store.joined_rows(tmp_path, None, D2, lens=LENS)
    assert [f["code"] for f in joined[0]["findings"]] == ["numbered", "expired", "keep", "condition-overdue", "condition-overdue"]
    assert joined[0]["fields"]["days_left"] == -273 and store.joined_rows(tmp_path, None, D1, lens=LENS) == task.load(tmp_path)
    lines = "\n".join(store.review_lines(result))
    assert "+ expired" in lines and "- expires" in lines and "reads no document" in lines
    assert len(CALLS) == 2                                  # the second pass over D2 and the joined views made nothing again


def test_reviews_are_stored_beside_what_is_there_and_only_with_a_document(tmp_path):
    made = LENS.review(stored(_parse(TEXT)), [permit_expiry], D1)
    assert store.save(tmp_path, [made]) == []               # no document id: nothing to key it by
    a, b = replace(made, document="a", text_sha="x"), replace(made, document="b", text_sha="y")
    assert store.save(tmp_path, [a]) == [store.path(tmp_path, "test-dates", D1)]
    store.save(tmp_path, [b])
    loaded = store.load(tmp_path, "test-dates", D1)
    assert loaded == {"a": a, "b": b} and loaded["a"].findings == made.findings and loaded["a"].findings[0].lens == "test-dates"
    assert store.save(tmp_path, [replace(a, reused=True)]) == []     # taken from the store unchanged: no write
    assert store.load(tmp_path, "test-dates", D2) == {} and Review.from_dict(a.as_dict()) == a
    assert store.ROOT == Path("reviews") / "documents"     # data/reviews/<task> is another store's


# The real readers that moved -----------------------------------------------------------------------------------------

ORDER = ("EXHIBIT A\nORDER FORM\nCustomer:\nExample Community Association\nInitial Term:\n24 Months\nRenewal Term:\n24 Months\n"
         "Annual Recurring Subtotal:\n$5,000.00\nContract Total:\n$10,702.00\nThis Agreement will automatically renew for successive "
         "renewal terms unless either Party gives the other Party notice of non-renewal at least thirty (30) days prior to the end.\n"
         "The Parties have executed this Agreement.\nDate:\n\\FSDateSigned2\\\nDate:\n\\FSDateSigned1\\\n"
         "DocuSign Envelope ID: 445C09D6-6CE8-45AE-847C-5F9CBA389783\nPat Vendor\n11/10/2024\nGeneral Counsel\n11/10/2024\nSam Board\n")


def test_a_contract_is_parsed_the_same_on_any_day_and_its_current_term_is_the_lenses():
    from jason.community.models.contracts_agreements import ContractModel

    early, late = date(2026, 9, 29), date(2029, 1, 1)
    a, b = ContractModel().parse(ORDER, ctx(early)), ContractModel().parse(ORDER, ctx(late))
    assert a == b and to_plain(a) == to_plain(b) and a.term_end == date(2026, 11, 10) and a.current_term_end is None
    first, second = read(DocumentKind.CONTRACT, ORDER, ctx(early)), read(DocumentKind.CONTRACT, ORDER, ctx(late))
    assert Basis.TODAY not in first.fields_basis and first.fields_basis == second.fields_basis
    # The field is still on the record and in the row, as of the date, and the row says the lens filled it.
    assert (first.record.current_term_end, second.record.current_term_end) == (date(2026, 11, 10), date(2030, 11, 10))
    row = first.as_dict()
    assert row["fields"]["current_term_end"] == "2026-11-10" and row["lenses"]["as-of"]["fields"] == ["current_term_end"]
    renewal = {f.code: f for f in first.findings}["auto-renewal"]
    assert renewal.lens == "as-of" and renewal.severity is Severity.CHECK and Basis.TODAY in renewal.basis
    assert all(Basis.TODAY not in f.basis for f in first.own_findings)
    assert {k: v for k, v in to_plain(first.record).items() if k != "current_term_end"} == \
        {k: v for k, v in to_plain(second.record).items() if k != "current_term_end"}


AGENDA = ("Example Community Association\nRegular Meeting of the Board of Directors\nTo be held on March 17, 2026 at 7:00 pm on Zoom\n"
          "Agenda\n1. Call to Order\n2. Open Forum\n3. Adjournment\n")


def test_an_agendas_notice_fields_come_from_the_log_after_the_parse(monkeypatch, tmp_path):
    from jason.community.models import meetings

    monkeypatch.setattr(meetings, "_mailings", lambda d: ({"subject": "Regular Meeting of the Board of Directors - March 17th at 7:00 pm",
                                                           "sent": "2026-03-15T01:30:00.000000Z"},))
    monkeypatch.setattr(meetings, "_library", lambda d: ())
    context = ctx(date(2026, 3, 20), data_dir=tmp_path)
    parsed = meetings.AgendaModel().parse(AGENDA, context)
    assert parsed.meeting_date == date(2026, 3, 17) and parsed.notice_sent is None and parsed.notice_subject == ""
    assert Basis.STORE not in context.since()               # the parse looked in no store
    reading = read(DocumentKind.AGENDA, AGENDA, ctx(date(2026, 3, 20), data_dir=tmp_path))
    assert Basis.STORE not in reading.fields_basis
    assert reading.enriched == ("notice_sent", "notice_subject") and Basis.STORE in reading.enriched_basis
    assert reading.record.notice_sent == date(2026, 3, 14) and "March 17th" in reading.record.notice_subject   # as a consumer sees it
    row = reading.as_dict()
    assert row["fields"]["notice_sent"] == "2026-03-14" and row["enriched"]["fields"] == ["notice_sent", "notice_subject"]
    assert "store" in row["enriched"]["basis"] and "notice-sent-late" in {f["code"] for f in row["findings"]}
    apart = task.parts(row)
    assert set(apart["enriched"]) == {"notice_sent", "notice_subject"} and "notice_sent" not in apart["ingestion"]["fields"]


def test_the_as_of_lens_is_a_record_of_rows():
    assert AS_OF.key == "as-of" and AS_OF.needs_as_of and len(AS_OF.version) == 12 and int(AS_OF.version, 16) >= 0
    assert Basis.STORE not in AS_OF.reads and AS_OF.reads == {Basis.TEXT, Basis.PROFILE}
    assert {DocumentKind.CONTRACT, DocumentKind.INSURANCE_POLICY, DocumentKind.MINUTES, DocumentKind.INVOICE} <= set(AS_OF.kinds)
    assert DocumentKind.AGENDA not in AS_OF.kinds           # its date checks also read the library: a collection's lens, not this one
    for check in AS_OF.checks.values():
        names = {f.name for f in dataclasses.fields(check.record)}
        assert set(check.fields) <= names and set(check.fields) <= set(reviews.hints(check.record)), check.key
    # Every reader that lists a check is registered for a kind the lens names, and lists only this lens's rows.
    listed = {c for models in REGISTRY.values() for m in models for c in m.lens_checks if c.lens is AS_OF}
    assert listed == set(AS_OF.checks.values())


# The inventory, with a lens ------------------------------------------------------------------------------------------


def test_the_basis_report_counts_a_lenses_findings_apart(permits, tmp_path):
    task.run(tmp_path, None, today=D1)
    rows = task.load(tmp_path)
    report = task.basis_report(rows)
    # Seven findings: "numbered" twice from the text alone; "keep" twice (it cites a law) in the reader; three by the lens.
    assert report["totals"] == {"findings": 7, "ingestion": 2, "review": 5, "unobserved": 0, "ingestionThroughFields": 0}
    assert report["byLens"] == {"test-dates": 3} and report["reviewInReaders"] == 2
    by_code = {c["code"]: c["class"] for c in report["readers"][0]["codes"]}
    assert by_code == {"numbered": "ingestion", "keep": "review", "expires": "lens", "condition-overdue": "lens"}
    assert report["fieldsFromLens"] == [{"reader": "test-permit", "fields": ["days_left"]}] and report["fieldsFromContext"] == []
    assert "by the test-dates lens" in "\n".join(task.basis_lines(report))
    apart = task.parts(rows[0])
    assert [f["code"] for f in apart["ingestion"]["findings"]] == ["numbered"] and "days_left" not in apart["ingestion"]["fields"]
    assert [f["code"] for f in apart["lens"]["test-dates"]["findings"]] == ["expires", "condition-overdue"]
    assert apart["lens"]["test-dates"]["fields"] == {"days_left": 92} and [f["code"] for f in apart["other"]] == ["keep"]


def test_the_models_command_takes_an_as_of_date(tmp_path, monkeypatch, capsys):
    from jason import cli
    from jason.config import Settings

    _library(monkeypatch, [{"id": "c1", "name": "order form.pdf", "period": "2024", "kind": DocumentKind.CONTRACT.value}], {"c1": ORDER})
    task.run(tmp_path, None, today=date(2026, 9, 29))
    readings = (tmp_path / "documents" / "readings.json").read_bytes()
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls, env=None: SimpleNamespace(payhoa_catalog=tmp_path / "payhoa.db")))
    args = cli.build_parser().parse_args(["models", "--as-of", "2029-01-01"])
    assert args.as_of == "2029-01-01" and cli.cmd_models(args) == 0
    out = capsys.readouterr().out
    assert "as of 2029-01-01" in out and "1 reviews made, 0 already stored" in out
    assert "~ auto-renewal (check to info)" in out and "= current_term_end: 2026-11-10 to 2030-11-10" in out
    assert store.dates(tmp_path, "as-of") == [date(2026, 9, 29), date(2029, 1, 1)]
    assert (tmp_path / "documents" / "readings.json").read_bytes() == readings
    assert cli.cmd_models(cli.build_parser().parse_args(["models", "--as-of", "2029-01-01", "--json"])) == 0
    assert json.loads(capsys.readouterr().out)["reused"] == 1
