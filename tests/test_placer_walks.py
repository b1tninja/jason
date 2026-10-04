"""Placer through the cached index: parcel history, builder descent, liens and title, bundles (fake rows only)."""

import json
from datetime import date

import pytest

from asspy.core import IndexedInstrument
from asspy.placer.filings import TYPE_IDS
from asspy.placer.recorder import SearchFailed, normalize_document_number
from jason.community.base import Developer
from jason.community.placer import (
    PlacerCountyAssessor,
    PlacerCountyRecorder,
    PlacerParcel,
    descend,
    open_cache,
    parcel_bundle,
    parcel_record,
    placer_index,
    subdivision_bundle,
)
from jason.community.placer.recorder import PlacerSession
from jason.community.title import LienStanding, title_watch

BUILDER = Developer("Example Builder", ("EXAMPLE BUILDER LLC",))
ASSN = "EXAMPLE OAKS OWNERS ASSN"
_NAMES = {ident: name for name, ident in TYPE_IDS.items()}


def _row(number, name, *names, day):
    return IndexedInstrument(number, day, number[-7:], "", name, names, internal_id="id-" + number)


SALE = date(2019, 6, 3)
ROWS = (
    # The community's formation: a declaration, the association's bylaws, the common area deeded to it.
    _row("2019-0000100", "DECLARATION OF RESTRICTIONS", "(R) EXAMPLE BUILDER LLC", day=date(2019, 1, 10)),
    _row("2019-0000101", "BYLAWS", f"(R) {ASSN}", day=date(2019, 1, 10)),
    _row("2019-0000102", "DEED", "(R) EXAMPLE BUILDER LLC", f"(E) {ASSN}", day=date(2019, 1, 10)),
    _row("2019-0000103", "DEED", "(R) SOMEONE ELSE", "(E) UNRELATED BUYER", day=date(2019, 1, 10)),
    # Two lots sold at the builder's closings.
    _row("2019-0000200", "NOTICE OF COMPLETION", "(R) EXAMPLE BUILDER LLC", day=SALE),
    _row("2019-0000201", "DEED", "(R) EXAMPLE BUILDER LLC", "(E) SAMPLE ANN M", day=SALE),
    _row("2019-0000202", "DEED OF TRUST", "(R) SAMPLE ANN M", "(E) EXAMPLE BANK NA", day=SALE),
    _row("2019-0000203", "NOTICE OF COMPLETION", "(R) EXAMPLE BUILDER LLC", day=SALE),
    _row("2019-0000204", "DEED", "(R) EXAMPLE BUILDER LLC", "(E) DOE JOHN", day=SALE),
    _row("2019-0000205", "DEED OF TRUST", "(R) DOE JOHN", "(E) EXAMPLE BANK NA", day=SALE),
    # Lot 1 resold; the first loan paid off; the new owner's association lien.
    _row("2023-0000050", "DEED", "(R) SAMPLE ANN M", "(E) EXAMPLE BEN A", day=date(2023, 3, 1)),
    _row("2023-0000051", "DEED OF TRUST", "(R) EXAMPLE BEN A", "(E) EXAMPLE CREDIT UNION", day=date(2023, 3, 1)),
    _row("2023-0000060", "RECONVEYANCE", "(R) EXAMPLE TRUSTEE CO", "(E) SAMPLE ANN M", day=date(2023, 3, 20)),
    _row("2024-0000010", "NOTICE OF DELINQUENT ASSESSMENT - HOMEOWNERS ASSOCIATION", "(R) EXAMPLE BEN A", f"(E) {ASSN}", day=date(2024, 2, 1)),
)


class FakePlacer(PlacerCountyRecorder):
    """Placer's index over ``ROWS``: number ranges, names with ``%``, document types, inclusive dates."""

    def __init__(self, rows=ROWS, *, fail=0):
        self.rows = rows
        self.fail = fail
        self.calls = []

    def open_session(self, *, fetch=None):
        return PlacerSession(fetch=lambda *a, **k: (200, "", {}))

    def search_page(self, *, number="", number_to="", name="", rows=100, after=None, before=None, types=(), session=None, fetch=None):
        self.calls.append((number, number_to, name, types, after, before))
        if self.fail:
            self.fail -= 1
            raise SearchFailed("blank page")
        wanted = {_NAMES[ident] for ident in types if ident in _NAMES}
        found = []
        for row in self.rows:
            if number:
                low, high = normalize_document_number(number), normalize_document_number(number_to or number)
                if not low <= row.number <= high:
                    continue
            else:
                pattern = name.replace("%", "").strip()
                if pattern and not any(pattern in party for party in row.names):
                    continue
                if types and row.filing_name not in wanted:
                    continue
            if after and row.recorded < after or before and row.recorded > before:
                continue
            found.append(row)
        return len(found), tuple(found[:rows])

    def detail(self, internal_id, **kwargs):
        return None


class FakeAssessor(PlacerCountyAssessor):
    parcels = {
        "000000000001": PlacerParcel(apn="000000000001", address="1 EXAMPLE CT", document_number="2023-0000050", document_date=date(2023, 3, 1)),
        "000000000002": PlacerParcel(apn="000000000002", address="2 EXAMPLE CT", document_number="2019-0000204", document_date=SALE),
    }

    def search(self, query, *, kind="idasmt", fetch=None):
        return ()

    def parcel(self, apn, *, fetch=None):
        return self.parcels.get(apn)


@pytest.fixture
def index(tmp_path):
    cache = open_cache(tmp_path / "placer.db")
    yield placer_index(cache, FakePlacer())
    cache.close()


def test_a_placer_parcel_history_reads_the_chain_the_closings_and_the_liens(index):
    record = parcel_record("000000000001", kind="idasmt", index=index, assessor=FakeAssessor(), developers=(BUILDER,), association=ASSN)
    assert record is not None
    assert record.history.numbers == ("2023-0000050", "2019-0000201")
    assert record.history.reached_developer and not record.history.gaps
    readings = {step.number: step for step in record.processes}
    assert readings["2019-0000201"].process == "developer closing" and readings["2019-0000201"].complete
    assert readings["2023-0000050"].process == "resale" and readings["2023-0000050"].complete
    built = record.parcel_history
    assert built.apn == "000000000001" and built.reaches_developer
    assert [step.number for step in built.steps] == ["2019-0000201", "2023-0000050"]
    assert built.steps[0].process == "developer closing"
    assert {item.number for item in built.steps[0].related} >= {"2019-0000200", "2019-0000202"}
    by_process = {lien.encumbrance.process.value: lien for lien in built.liens}
    assert by_process["assessment lien"].community
    standings = {row.number: row.standing for row in title_watch((built,))}
    assert standings["2024-0000010"] is LienStanding.STANDS
    assert standings["2019-0000202"] is LienStanding.RELEASED
    text = record.markdown
    assert "Conveyance processes" in text and "Liens on the owners" in text and "stands" in text
    assert index.cache.apn("2023-0000050") == "000000000001"


def test_a_second_walk_searches_nothing_it_has_seen(index):
    parcel_record("000000000001", kind="idasmt", index=index, assessor=FakeAssessor(), developers=(BUILDER,), association=ASSN)
    before = len(index.recorder.calls)
    again = parcel_record("000000000001", kind="idasmt", index=index, assessor=FakeAssessor(), developers=(BUILDER,), association=ASSN)
    assert again.history.numbers == ("2023-0000050", "2019-0000201")
    assert len(index.recorder.calls) == before


def test_a_failed_search_renews_the_session_mid_walk(tmp_path):
    cache = open_cache(tmp_path / "placer.db")
    try:
        index = placer_index(cache, FakePlacer(fail=1))
        record = parcel_record("000000000002", kind="idasmt", index=index, assessor=FakeAssessor(), developers=(BUILDER,))
        assert index.renewals == 1
        assert record.history.numbers == ("2019-0000204",)
    finally:
        cache.close()


def test_the_builder_descent_reconstructs_each_lot_and_meets_its_parcel(index):
    currents = {"000000000001": "2023-0000050", "000000000002": "2019-0000204"}
    found = descend(index, developers=(BUILDER,), after=date(2019, 1, 1), before=date(2025, 12, 31), depth=3, currents=currents)
    assert [item.number for item in found.grants] == ["2019-0000201", "2019-0000204"]
    assert [item.number for item in found.notices] == ["2019-0000200", "2019-0000203"]
    assert "common area" in " ".join(index.cache.notes("2019-0000102"))
    first = found.lot("000000000001")
    assert first is not None and first.grant.number == "2019-0000201"
    assert first.history.numbers == ("2023-0000050", "2019-0000201")
    assert first.history.step("2023-0000050").priors == ("2019-0000201",)
    second = found.lot("000000000002")
    assert second is not None and second.numbers == ("2019-0000204",)
    # The neighbors of each grant were stored: the notices and the buyers' deeds of trust.
    assert index.cache.get("2019-0000205").kind == "lien"


def test_bundles_carry_shared_shapes_and_formations(index):
    record = parcel_record("000000000001", kind="idasmt", index=index, assessor=FakeAssessor(), developers=(BUILDER,), association=ASSN)
    bundle = parcel_bundle(record, index, developers=(BUILDER,))
    kinds = {(item.kind, item.anchor.number) for item in bundle.formations}
    assert ("closing", "2019-0000201") in kinds and ("community", "2019-0000100") in kinds
    community = next(item for item in bundle.formations if item.kind == "community")
    roles = {member.instrument.number: member.role for member in community.members}
    assert roles == {"2019-0000101": "bylaws", "2019-0000102": "common-area deed"}
    closing = next(item for item in bundle.formations if item.anchor.number == "2019-0000201")
    assert {member.role for member in closing.members} >= {"notice of completion", "buyer lien"}
    assert bundle.instrument("2024-0000010").filing_code == "386"
    shape = bundle.as_dict()
    json.dumps(shape)
    assert shape["county"] == "placer" and shape["scope"] == "parcel"
    assert {"instruments", "histories", "readings", "formations", "liens", "parcels"} <= set(shape)

    found = descend(index, developers=(BUILDER,), after=date(2019, 1, 1), before=date(2025, 12, 31), depth=2,
                    currents={"000000000001": "2023-0000050"})
    whole = subdivision_bundle(found, index)
    assert len(whole.histories) == 2
    assert {item.number for item in whole.readings} >= {"2019-0000201", "2019-0000204", "2023-0000050"}
    assert ("000000000001", "2023-0000050") in whole.parcels
    json.dumps(whole.as_dict())


def test_a_wide_placer_name_is_narrowed_by_document_type():
    rows = tuple(_row(f"2020-{index:07d}", "DEED OF TRUST", "(R) SAMPLE ANN M", "(E) EXAMPLE BANK NA", day=date(2020, 1, 2)) for index in range(1, 40))
    rows += (_row("2020-0000500", "DEED", "(R) SELLER PAT", "(E) SAMPLE ANN M", day=date(2020, 1, 2)),)
    recorder = FakePlacer(rows)
    (found,) = recorder.for_parties(("SAMPLE ANN M",), limit=30)
    assert [row.number for row in found.rows] == ["2020-0000500"]
    assert recorder.calls[-1][3] and set(recorder.calls[-1][3]) <= set(TYPE_IDS.values())


def test_the_placer_reports_write_pages_tabs_and_bundles(index, tmp_path):
    from jason.tasks.placer_history import placer_parcel_report, placer_subdivision_report
    from jason.tasks.property_history import property_tabs

    one = placer_parcel_report("000000000001", tmp_path / "parcel", kind="idasmt", developers=(BUILDER,), association=ASSN,
                               index=index, assessor=FakeAssessor())
    assert [path.name for path in one.paths] == ["000000000001.md", "000000000001.json"]
    assert json.loads(one.paths[1].read_text(encoding="utf-8"))["scope"] == "parcel"
    whole = placer_subdivision_report((BUILDER,), tmp_path / "subdivision", after=date(2019, 1, 1), before=date(2025, 12, 31),
                                      currents={"000000000001": "2023-0000050"}, association=ASSN, owner_filings=True, index=index)
    page = whole.paths[0].read_text(encoding="utf-8")
    assert "2 grants" in page and "common-area deed" in page
    assert "2024-0000010" in whole.paths[2].read_text(encoding="utf-8")
    tabs = property_tabs(whole.histories)
    assert len(tabs["Deed chain"]) > 1


def test_without_range_searches_the_party_searches_fill_each_closing(index):
    found = descend(index, developers=(BUILDER,), after=date(2019, 1, 1), before=date(2025, 12, 31), depth=2, neighbors=False)
    assert not found.neighbors
    assert not any(call[0] for call in index.recorder.calls)  # no number-range search ran
    whole = subdivision_bundle(found, index, governing=False)
    readings = {step.number: step for step in whole.readings}
    assert readings["2019-0000201"].process == "developer closing" and readings["2019-0000201"].complete
    assert readings["2019-0000204"].complete


def test_a_namesake_with_another_suffix_is_not_the_owner_and_liens_need_no_association(tmp_path):
    from jason.community.placer.parcel import same_owner

    assert same_owner("SAMPLE ANN M", "SAMPLE ANN") and same_owner("EXAMPLE-SMITH ANN", "EXAMPLESMITH ANN")
    assert not same_owner("SAMPLE ROBERT W JR", "SAMPLE ROBERT")
    rows = ROWS + (_row("2021-0000070", "DEED", "(R) SAMPLE ANN M JR", "(E) SOMEONE ELSE", day=date(2021, 5, 5)),)
    cache = open_cache(tmp_path / "placer.db")
    try:
        index = placer_index(cache, FakePlacer(rows))
        found = descend(index, developers=(BUILDER,), after=date(2019, 1, 1), before=date(2025, 12, 31), depth=2, neighbors=False)
        assert "2021-0000070" not in {number for lot in found.lots for number in lot.numbers}
        record = parcel_record("000000000001", kind="idasmt", index=index, assessor=FakeAssessor(), developers=(BUILDER,))
        assert {lien.encumbrance.process.value for lien in record.parcel_history.liens} >= {"loan", "assessment lien"}
    finally:
        cache.close()
