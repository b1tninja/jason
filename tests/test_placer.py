"""Placer County recorder (KoFile) and assessor (MPTSWEB) adapters."""

from datetime import date
from pathlib import Path

from jason.community.placer import PlacerCountyAssessor, PlacerCountyRecorder, walk_ownership
from jason.community.placer.assessor import PlacerParcel
from jason.community.placer.filings import classify_filing, filed_instrument, normalize_filing_name
from jason.community.placer.recorder import (
    PlacerSession,
    normalize_document_number,
    parse_detail,
    parse_search_results,
)
from jason.community.recorder import IndexedInstrument

FIXTURES = Path(__file__).parent / "fixtures"


def test_normalize_document_number_from_assessor_and_index():
    assert normalize_document_number("2023R0014772") == "2023-0014772"
    assert normalize_document_number("2023-0014772") == "2023-0014772"
    assert normalize_document_number("2023-0014772-00") == "2023-0014772"
    assert normalize_document_number("20230014772") == "2023-0014772"


def test_parse_accepts_placer_numbers():
    parsed = PlacerCountyRecorder().parse("2023R0014772")
    assert parsed is not None
    assert parsed.number == "2023-0014772"
    assert parsed.sequence == "0014772"
    assert parsed.recorded.year == 2023


def test_parse_search_results_reads_document_row_info():
    html = (FIXTURES / "placer_search_results.html").read_text(encoding="utf-8")
    rows = parse_search_results(html)
    assert len(rows) == 2
    assert rows[0].number == "2023-0014772"
    assert rows[0].internal_id == "1001"
    assert rows[0].filing_name == "DEED"
    assert rows[0].recorded == date(2023, 3, 27)
    assert rows[0].grantors == ("EXAMPLE SELLER LLC", "EXAMPLE PERSON")
    assert rows[0].grantees == ("EXAMPLE BUYER TRUST",)


def test_parse_detail_reads_trans_add_doc():
    html = (FIXTURES / "placer_trans_add_doc.html").read_text(encoding="utf-8")
    detail = parse_detail(html)
    assert detail is not None
    assert detail.number == "2023-0014772"
    assert detail.pages == 3
    assert detail.filings[0].description == "DEED"
    assert detail.grantors == ("EXAMPLE SELLER LLC", "EXAMPLE PERSON")
    assert detail.grantees == ("EXAMPLE BUYER TRUST",)


def test_assessor_search_unwraps_double_encoded_json():
    payload = (
        '{"Table":{"Row":{"@RowID":"1","Asmt":"328060025000","FeeParcel":"328060025000",'
        '"AsmtStatus":"A","IsShowAddress":"1","TRA":"003020","SitusAddr":"123 EXAMPLE LN"}}}'
    )

    def fetch(url):
        assert "/idaddress/" in url
        return payload

    hits = PlacerCountyAssessor().search("123 example", kind="idaddress", fetch=fetch)
    assert len(hits) == 1
    assert hits[0].apn == "328060025000"
    assert hits[0].address.startswith("123 EXAMPLE")


def test_assessor_parcel_and_characteristics_from_html():
    html = (FIXTURES / "placer_asr_main.html").read_text(encoding="utf-8")

    def fetch(url):
        assert url.endswith("/328060025000")
        return html

    parcel = PlacerCountyAssessor().parcel("328-060-025-000", fetch=fetch)
    assert parcel is not None
    assert parcel.apn == "328060025000"
    assert parcel.document_number == "2023-0014772"
    assert parcel.assessor_document_number == "2023R0014772"
    assert parcel.document_date == date(2023, 3, 27)
    assert parcel.lot_sqft == 5300

    chars = PlacerCountyAssessor().characteristics("328060025000", fetch=fetch)
    assert chars is not None
    assert chars.living_sqft == 2225
    assert chars.bedrooms == 4
    assert chars.baths == 2.5
    assert chars.year_built == 2004
    assert chars.garage_sqft == 426


def test_history_links_grantor_to_earlier_grantee():
    current = IndexedInstrument(
        number="2023-0014772",
        recorded=date(2023, 3, 27),
        sequence="0014772",
        filing_code="",
        filing_name="DEED",
        names=("(R) SAMPLE ANN M", "(R) EXAMPLE BEN A", "(E) EXAMPLE BEN A"),
        internal_id="1",
    )
    prior = IndexedInstrument(
        number="2019-0084274",
        recorded=date(2019, 11, 1),
        sequence="0084274",
        filing_code="",
        filing_name="DEED",
        names=("(R) BUILDER HOMES LLC", "(E) SAMPLE ANN M", "(E) EXAMPLE BEN A"),
        internal_id="2",
    )
    by_number = {current.number: current, prior.number: prior}

    class Stub(PlacerCountyRecorder):
        def open_session(self, *, fetch=None):
            return PlacerSession(fetch=lambda *a, **k: (200, "", {}))

        def search(self, *, number="", name="", **kwargs):
            if number:
                row = by_number.get(normalize_document_number(number) or number)
                return (row,) if row else ()
            return ()

        def detail(self, internal_id, **kwargs):
            return None

    history = Stub().history(("2023-0014772", "2019-0084274"), apn="328060025000")
    assert history.numbers == ("2023-0014772", "2019-0084274")
    assert history.step("2023-0014772").priors == ("2019-0084274",)


def test_walk_ownership_discovers_priors_and_builds_diagram():
    parcel = PlacerParcel(
        apn="328060025000",
        address="123 EXAMPLE LN LINCOLN CA 95648",
        document_number="2023-0014772",
        document_date=date(2023, 3, 27),
    )
    current = IndexedInstrument(
        number="2023-0014772",
        recorded=date(2023, 3, 27),
        sequence="0014772",
        filing_code="",
        filing_name="DEED",
        names=("(R) SAMPLE ANN M", "(E) EXAMPLE BEN A"),
        internal_id="1",
    )
    prior = IndexedInstrument(
        number="2019-0084274",
        recorded=date(2019, 11, 1),
        sequence="0084274",
        filing_code="",
        filing_name="DEED",
        names=("(R) BUILDER HOMES LLC", "(E) SAMPLE ANN M"),
        internal_id="2",
    )

    class StubRecorder(PlacerCountyRecorder):
        def open_session(self, *, fetch=None):
            return PlacerSession(fetch=lambda *a, **k: (200, "", {}))

        def search(self, *, number="", name="", **kwargs):
            if number:
                key = normalize_document_number(number) or number
                for row in (current, prior):
                    if row.number == key:
                        return (row,)
                return ()
            if "SAMPLE" in name.upper():
                return (prior, current)
            return ()

        def detail(self, internal_id, **kwargs):
            return None

    class StubAssessor(PlacerCountyAssessor):
        def search(self, query, *, kind="idasmt", fetch=None):
            return ()

        def parcel(self, apn, *, fetch=None):
            return parcel

    walked = walk_ownership(
        "328060025000",
        kind="idasmt",
        assessor=StubAssessor(),
        recorder=StubRecorder(),
        hops=2,
    )
    assert walked is not None
    assert walked.history.apn == "328060025000"
    assert "2019-0084274" in walked.history.numbers
    assert "flowchart TD" in walked.mermaid
    assert "2023-0014772" in walked.markdown
    assert walked.processes
    assert any(step.process for step in walked.processes)
    assert "Conveyance processes" in walked.markdown


def test_placer_filing_names_map_to_kinds():
    assert normalize_filing_name("NOTICE DEFAULT") == "NOTICE OF DEFAULT"
    assert normalize_filing_name("NOTICE TRUSTEES SALE") == "NOTICE OF TRUSTEES SALE"
    assert normalize_filing_name("SATISFACTION OF JUDGMENT") == "RELEASE OF JUDGMENT"
    assert classify_filing("DEED")[0] == "fee"
    assert classify_filing("DEED OF TRUST")[0] == "lien"
    assert classify_filing("RECONVEYANCE")[0] == "release"
    assert classify_filing("SATISFACTION OF JUDGMENT")[0] == "release"
    assert classify_filing("NOTICE DEFAULT")[0] == "default"
    assert classify_filing("AFFIDAVIT OF DEATH")[0] == "death"
    assert classify_filing("SUBSTITUTION OF TRUSTEE")[0] == "substitution"
    row = IndexedInstrument(
        number="2020-0000001",
        recorded=date(2020, 1, 1),
        sequence="0000001",
        filing_code="",
        filing_name="DEED OF TRUST",
        names=("(R) OWNER", "(E) LENDER"),
        internal_id="9",
    )
    filed = filed_instrument(row)
    assert filed.kind == "lien"
    assert filed.filing_code == "230"


def _deed(number: str, filing_name: str, *names: str) -> IndexedInstrument:
    return IndexedInstrument(number, date(2020, 1, 1), number[-7:], "", filing_name, names, internal_id="id-" + number)


def test_a_placer_name_search_keeps_only_the_fee_transfers():
    rows = (
        _deed("2020-0000001", "DEED", "(R) SAMPLE ANN M", "(E) EXAMPLE BEN A"),
        _deed("2020-0000002", "DEED OF TRUST", "(R) EXAMPLE BEN A", "(E) EXAMPLE BANK NA"),
    )

    class Stub(PlacerCountyRecorder):
        def open_session(self, *, fetch=None):
            return PlacerSession(fetch=lambda *a, **k: (200, "", {}))

        def search_page(self, *, name="", **kwargs):
            return len(rows), rows

    found = Stub().for_parties(("SAMPLE ANN M",), limit=30)
    assert [row.number for row in found[0].rows] == ["2020-0000001"] and not found[0].wide


def test_placer_ownership_matches_the_assessor_spelling_and_reads_the_row_detail():
    parcel = PlacerParcel(apn="000000000000", address="123 EXAMPLE LN", document_number="2020R0000001", document_date=date(2020, 1, 1))
    asked = {}

    class StubRecorder(PlacerCountyRecorder):
        def search(self, *, number="", **kwargs):
            return (_deed("2020-0000001", "DEED", "(R) SAMPLE ANN M", "(E) EXAMPLE BEN A"),)

        def detail(self, internal_id, **kwargs):
            asked.update(kwargs, id=internal_id)
            return None

    class StubAssessor(PlacerCountyAssessor):
        def parcel(self, apn, *, fetch=None):
            return parcel

        def recorder(self):
            return StubRecorder()

    assert StubAssessor().ownership("000000000000") is None
    assert asked["id"] == "id-2020-0000001" and asked["number"] == "2020-0000001" and asked["filing_name"] == "DEED"


def _row(number: str, filing_name: str, *names: str, day: date = date(2019, 10, 25)) -> IndexedInstrument:
    return IndexedInstrument(number, day, number[-7:], "", filing_name, names, internal_id="id-" + number)


def _range_recorder(rows: tuple[IndexedInstrument, ...]):
    class Stub(PlacerCountyRecorder):
        def open_session(self, *, fetch=None):
            return PlacerSession(fetch=lambda *a, **k: (200, "", {}))

        def search(self, *, number="", number_to="", name="", **kwargs):
            low, high = normalize_document_number(number), normalize_document_number(number_to or number)
            return tuple(row for row in rows if low <= row.number <= high)

        def detail(self, internal_id, **kwargs):
            return None

    return Stub()


def test_a_builder_grant_reads_as_a_developer_closing_from_its_numbered_neighbors():
    from jason.community.base import Developer
    from jason.community.placer.processes import read_chain

    builder = Developer("Example Builder", ("EXAMPLE BUILDER LLC",))
    rows = (
        _row("2019-0000010", "NOTICE OF COMPLETION", "(E) EXAMPLE BUILDER LLC THE"),
        _row("2019-0000011", "DEED", "(R) EXAMPLE BUILDER LLC THE", "(E) SAMPLE ANN M"),
        _row("2019-0000012", "DEED OF TRUST", "(R) SAMPLE ANN", "(E) EXAMPLE BANK NA"),
        _row("2019-0000013", "RECONVEYANCE", "(E) OTHER OWNER"),
        _row("2019-0000013", "SUBSTITUTION OF TRUSTEE", "(R) OTHER OWNER", "(E) EXAMPLE BANK NA"),
        _row("2019-0000009", "DEED", "(R) SOMEONE ELSE", "(E) ANOTHER BUYER", day=date(2019, 10, 24)),
    )
    recorder = _range_recorder(rows)
    history = recorder.history(("2019-0000011",), developers=(builder,))
    (step,) = read_chain(history, recorder=recorder, developers=(builder,))
    assert step.process == "developer closing" and step.complete
    seats = {item.role: (item.reason, item.number) for item in step.reading.slots}
    assert seats["notice of completion"] == ("present", "2019-0000010")
    assert seats["buyer lien"] == ("present", "2019-0000012")
    # The other parcel's payoff on the same day, and the deed the day before, are not this closing's.
    assert [item.number for item in step.companions] == ["2019-0000010", "2019-0000012"]


def test_a_placer_resale_finds_its_prior_deed_by_party_and_one_number_is_one_instrument():
    from asspy.placer.filings import filed_instruments
    from jason.community.placer.processes import read_chain

    rows = (
        _row("2015-0000100", "DEED", "(R) SELLER PAT", "(E) SAMPLE ANN M", day=date(2015, 7, 24)),
        _row("2019-0000020", "DEED", "(R) SAMPLE ANN M", "(E) EXAMPLE BEN A"),
        _row("2019-0000021", "ASSIGNMENT OF RENTS", "(R) EXAMPLE BEN A", "(E) EXAMPLE BANK NA"),
        _row("2019-0000021", "DEED OF TRUST", "(R) EXAMPLE BEN A", "(E) EXAMPLE BANK NA"),
    )
    assert [item.kind for item in filed_instruments(rows[2:])] == ["lien"]
    recorder = _range_recorder(rows)
    history = recorder.history(("2019-0000020", "2015-0000100"))
    steps = {step.number: step for step in read_chain(history, recorder=recorder)}
    resale = steps["2019-0000020"]
    assert resale.process == "resale" and resale.complete
    seats = {item.role: (item.reason, item.number) for item in resale.reading.slots}
    assert seats["prior deed"] == ("present", "2015-0000100") and seats["buyer lien"] == ("present", "2019-0000021")
