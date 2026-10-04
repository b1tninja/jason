"""The instrument graph: county-neutral nodes and typed edges with provenance, each edge family kept a DAG, and no
private person in the shared view. Every name here is made up."""

from datetime import date

from asspy.filings import Encumbrance, Process, Step

from jason.community.base import Developer
from jason.community.governing import GoverningRecord, Supersession
from jason.community.instrument_graph import (
    Context,
    EdgeKind,
    InstrumentGraph,
    NodeType,
    PartyKind,
    Seat,
    View,
    add_encumbrance,
    add_filed,
    add_governing,
    add_governing_document,
    add_located,
    add_ownership_history,
    add_process_steps,
    add_reading,
    add_seats,
    add_supersessions,
    instrument_id,
    parcel_id,
    party_kind,
)
from jason.community.documents import Amendment, Document, GoverningDocument
from jason.community.processes import Finding, Reading
from jason.community.recorder import Conveyance, FiledInstrument, succession
from jason.community.symbols import DeveloperDelivery, DocumentKind

ASSOCIATION = "EXAMPLE VILLAGE HOMEOWNERS ASSOCIATION"
BUILDER = "EXAMPLE BUILDERS LLC"
BANK = "EXAMPLE BANK NA"
OWNER_A = "OWNER ALPHA A"
OWNER_B = "OWNER BRAVO B"
APN = "000-0000-000-0001"
CTX = Context("Example", (ASSOCIATION,), (Developer("Example Builders", (BUILDER,)),))


def _filed(number, day, kind, grantors, grantees, refs=(), code="", name=""):
    return FiledInstrument(number, date.fromisoformat(day), kind, tuple(grantors), tuple(grantees), tuple(refs), code, name)


def _edges(graph, kind):
    return {(e.source, e.target) for e in graph.edges if e.kind is kind}


def _id(number):
    return instrument_id(number, "Example")


def test_party_kind_keeps_unclear_names_private():
    assert party_kind(ASSOCIATION, association=(ASSOCIATION,)) is PartyKind.ASSOCIATION
    assert party_kind(BUILDER) is PartyKind.BUSINESS
    assert party_kind(BANK) is PartyKind.BUSINESS
    assert party_kind("EXAMPLE HOMES") is PartyKind.BUSINESS
    assert party_kind("EXAMPLE TRUST COMPANY") is PartyKind.BUSINESS
    assert party_kind(OWNER_A) is PartyKind.PRIVATE
    assert party_kind("ALPHA FAMILY TRUST") is PartyKind.PRIVATE
    assert party_kind("OWNER ALPHA TR") is PartyKind.PRIVATE
    assert party_kind("") is PartyKind.PRIVATE


def test_index_rows_make_conveyances_liens_and_releases():
    graph = InstrumentGraph(county="Example")
    rows = (
        _filed("2001-0000014", "2001-03-01", "fee", [BUILDER], [OWNER_A], code="685", name="GRANT DEED"),
        _filed("2001-0000015", "2001-03-01", "lien", [OWNER_A], [BANK], code="230", name="DEED OF TRUST"),
        _filed("2009-0000300", "2009-05-01", "release", [BANK], [OWNER_A], ["2001-0000015"], "238", "RECONVEYANCE"),
    )
    add_filed(graph, rows, CTX, apn=APN)
    assert (_id("2009-0000300"), _id("2001-0000015")) in _edges(graph, EdgeKind.RELEASES)
    assert (_id("2009-0000300"), _id("2001-0000015")) in _edges(graph, EdgeKind.CITES)
    assert (_id("2001-0000014"), parcel_id(APN)) in _edges(graph, EdgeKind.CARRIES)
    encumbers = [e for e in graph.edges if e.kind is EdgeKind.ENCUMBERS]
    assert encumbers and all(e.lead for e in encumbers)          # a lien indexes a person: a lead
    builder = graph.party(BUILDER, developers=CTX.developers)
    conveys = [e for e in graph.edges if e.kind is EdgeKind.CONVEYS]
    assert conveys[0].source == builder and conveys[0].via == "2001-0000014"
    # An instrument node never carries a person's name.
    for node in graph.nodes.values():
        if node.type is NodeType.INSTRUMENT:
            assert OWNER_A not in node.attrs.get("parties", [])


def test_shared_view_holds_no_private_person_and_private_view_no_names():
    graph = InstrumentGraph(county="Example")
    add_filed(graph, (_filed("2001-0000014", "2001-03-01", "fee", [BUILDER], [OWNER_A], code="685", name="GRANT DEED"),), CTX, apn=APN)
    graph.parcel(APN, unit="12")
    shared = graph.to_dict(View.SHARED)
    text = repr(shared) + graph.mermaid(View.SHARED)
    assert "ALPHA" not in text and "BRAVO" not in text
    assert not [n for n in shared["nodes"] if n.get("partyKind") == "private"]
    assert any("private person(s) left out" in n for n in shared["notes"])
    private = graph.to_dict(View.PRIVATE)
    person = next(n for n in private["nodes"] if n.get("partyKind") == "private")
    assert person["label"] == "owner, unit 12"
    assert "names" not in person and "ALPHA" not in repr(private)
    named = graph.to_dict(View.PRIVATE, names=True)
    assert next(n for n in named["nodes"] if n.get("partyKind") == "private")["names"] == [OWNER_A]


def test_an_edge_that_would_close_a_cycle_is_reported_not_added():
    graph = InstrumentGraph(county="Example")
    rows = (
        _filed("2005-0000001", "2005-01-01", "fee", [BUILDER], [OWNER_A], ["2005-0000002"]),
        _filed("2005-0000002", "2005-01-02", "fee", [OWNER_A], [OWNER_B], ["2005-0000001"]),
        _filed("2006-0000003", "2006-01-02", "fee", [OWNER_B], [OWNER_A]),            # a buy-back
    )
    add_filed(graph, rows, CTX)
    cites = _edges(graph, EdgeKind.CITES)
    assert len(cites) == 1                                       # the second citation would close the loop
    families = {c.family for c in graph.cycles}
    assert "citation" in families and "party" in families
    for family in ("citation", "party", "chain"):
        assert graph.is_dag(family)
    data = graph.to_dict(View.PRIVATE)
    assert data["cycles"] and data["cycles"][0]["path"]
    assert not graph.to_dict(View.SHARED)["cycles"] or all("person:" not in "".join(c["path"]) for c in graph.to_dict(View.SHARED)["cycles"])


def test_a_chain_from_succession_draws_priors_firm_when_cited_and_leads_by_handoff():
    chain = succession((
        Conveyance("2001-0000014", date(2001, 3, 1), (BUILDER,), (OWNER_A,), apn=APN),
        Conveyance("2010-0000500", date(2010, 6, 1), (OWNER_A,), (OWNER_B,), ("2001-0000014",), apn=APN),
        Conveyance("2015-0000700", date(2015, 2, 1), (OWNER_B,), ("OWNER CHARLIE C",), apn=APN),
    ), apn=APN, developers=CTX.developers)
    graph = InstrumentGraph(county="Example")
    add_ownership_history(graph, chain, CTX)
    priors = {(e.source, e.target): e for e in graph.edges if e.kind is EdgeKind.PRIOR_OF}
    assert priors[(_id("2010-0000500"), _id("2001-0000014"))].provenance.rule == "chain.cites"
    assert not priors[(_id("2010-0000500"), _id("2001-0000014"))].lead
    assert priors[(_id("2015-0000700"), _id("2010-0000500"))].provenance.rule == "chain.prior"
    assert len(_edges(graph, EdgeKind.CARRIES)) == 3


def _record(number, day, role, delivery=DeveloperDelivery.DECLARATION, phase=None, cites=(), superseded_by="", parties=(BUILDER,)):
    return GoverningRecord(number, date.fromisoformat(day), "", role, delivery, tuple(parties), phase, tuple(cites), "", superseded_by)


def test_governing_records_amend_annex_and_supersede_the_declaration():
    graph = InstrumentGraph(county="Example")
    records = (
        _record("2001-0000010", "2001-03-01", "declaration", superseded_by="2001-0000020"),
        _record("2001-0000020", "2001-03-08", "restated declaration"),
        _record("2003-0000050", "2003-06-01", "annexation", phase=2, cites=("2001-0000020",)),
        _record("2010-0000100", "2010-02-01", "amendment", parties=(ASSOCIATION,)),
        _record("2001-0000011", "2001-03-01", "common area deed", DeveloperDelivery.COMMON_AREA_DEED, parties=(BUILDER, ASSOCIATION)),
    )
    add_governing(graph, records, CTX)
    add_supersessions(graph, (Supersession("2001-0000010", "2001-0000020", role="declaration", reason="recital F", source="the restated declaration"),), CTX)
    annex = next(e for e in graph.edges if e.kind is EdgeKind.ANNEXES)
    assert (annex.source, annex.target) == (_id("2003-0000050"), _id("2001-0000020")) and not annex.lead
    amend = next(e for e in graph.edges if e.kind is EdgeKind.AMENDS)
    assert amend.target == _id("2001-0000020") and amend.lead and amend.provenance.rule == "governing.role"
    supersedes = next(e for e in graph.edges if e.kind is EdgeKind.SUPERSEDES)
    assert (supersedes.source, supersedes.target) == (_id("2001-0000020"), _id("2001-0000010")) and not supersedes.lead
    assert graph.nodes[_id("2001-0000010")].attrs["supersededBy"] == "2001-0000020"
    assert graph.party(ASSOCIATION, association=CTX.association) == "party:association"
    assert (_id("2001-0000011"), "party:association") in _edges(graph, EdgeKind.VESTS)
    text = graph.mermaid()
    assert "-.->|amends|" in text and "-->|annexes|" in text and "class " in text and "superseded" in text


class _ExampleAmendment(Amendment, Document):
    def __init__(self):
        super().__init__(title="First Amendment", drive_id="x" * 12, sections=("4.2",), recorder_number="2010-0000100", recorded=date(2010, 2, 1))


class _Unrecorded(Amendment, Document):
    def __init__(self):
        super().__init__(title="Second Amendment (draft)", drive_id="y" * 12)


class _Declaration(GoverningDocument):
    def __init__(self):
        super().__init__(title="CC&Rs", drive_id="z" * 12, document_kind=DocumentKind.DECLARATION,
                         recorder_number="2001-0000020", recorded=date(2001, 3, 8), amendments=(_ExampleAmendment(), _Unrecorded()))

    def cite(self):
        return "CC&Rs"


def test_the_specifications_amendment_makes_a_role_lead_firm():
    graph = InstrumentGraph(county="Example")
    add_governing(graph, (_record("2001-0000020", "2001-03-08", "restated declaration"), _record("2010-0000100", "2010-02-01", "amendment")), CTX)
    add_governing_document(graph, _Declaration(), CTX)
    amend = next(e for e in graph.edges if e.kind is EdgeKind.AMENDS)
    assert not amend.lead                                         # the spec's fact joined the role's lead
    assert {p.rule for p in (amend.provenance, *amend.also)} == {"governing.role", "spec.amendment"}
    assert graph.nodes[_id("2001-0000020")].attrs["role"] == "restated declaration"
    assert any("Second Amendment (draft): not recorded" in n for n in graph.notes)


def test_located_rows_are_leads_beside_their_anchor():
    graph = InstrumentGraph(county="Example")
    add_located(graph, (
        {"number": "2001-0000010", "recorded": "2001-03-01", "filing": "DECLARATION OF RESTRICTIONS", "item": "declaration", "tie": "beside", "via": "2001-0000011", "parties": [BUILDER]},
        {"number": "2003-0000050", "recorded": "2003-06-01", "filing": "DECLARATION ANNEX", "item": "annexations", "tie": "declarant", "via": BUILDER, "parties": [BUILDER, OWNER_A]},
    ), CTX)
    beside = next(e for e in graph.edges if e.kind is EdgeKind.BESIDE)
    assert (beside.source, beside.target) == (_id("2001-0000010"), _id("2001-0000011")) and beside.lead
    assert graph.nodes[_id("2003-0000050")].attrs["item"] == "annexations"
    assert all(e.lead for e in graph.edges)
    assert "ALPHA" not in repr(graph.to_dict(View.SHARED))


def test_a_process_reading_seats_the_closing():
    anchor = "2001-0000014"
    reading = Reading("developer closing", True, (
        Finding("notice of completion", True, "present", "2001-0000013"),
        Finding("grant", True, "present", anchor),
        Finding("buyer lien", True, "present", "2001-0000015"),
        Finding("companion vesting", False, "missing", ""),
    ))
    graph = InstrumentGraph(county="Example")
    graph.instrument(anchor, county="Example")
    add_reading(graph, anchor, reading, CTX, apn=APN)
    assert (_id("2001-0000013"), _id(anchor)) in _edges(graph, EdgeKind.COMPLETES)
    assert (_id("2001-0000015"), parcel_id(APN)) in _edges(graph, EdgeKind.ENCUMBERS)
    assert all(e.lead for e in graph.edges)
    add_seats(graph, "2004-0000100", (Seat("partial reconveyance", "2004-0000101"), Seat("released lien", "2000-0000900", "present")),
              CTX, process="blanket release")
    assert (_id("2004-0000101"), _id("2000-0000900")) in _edges(graph, EdgeKind.RELEASES)


def test_a_lien_lifecycle_releases_its_opener():
    lien = Encumbrance(Process.ASSESSMENT_LIEN, (OWNER_A,), (ASSOCIATION,), (
        Step("2012-0000200", date(2012, 5, 1), "386 NOTICE OF ASSOCIATION LIEN", "opens", (OWNER_A,), (ASSOCIATION,)),
        Step("2012-0000300", date(2012, 8, 1), "655 RELEASE", "closes", (ASSOCIATION,), (OWNER_A,)),
    ))
    graph = InstrumentGraph(county="Example")
    add_encumbrance(graph, lien, CTX, apn=APN)
    assert (_id("2012-0000300"), _id("2012-0000200")) in _edges(graph, EdgeKind.RELEASES)
    assert (_id("2012-0000200"), "party:association") in _edges(graph, EdgeKind.NAMES)
    assert "ALPHA" not in repr(graph.to_dict(View.SHARED))


def test_a_placer_walk_feeds_the_same_builders():
    from jason.community.placer.processes import ProcessStep

    reading = Reading("developer closing", True, (
        Finding("notice of completion", True, "present", "2019-0000099"),
        Finding("grant", True, "present", "2019-0000100"),
        Finding("buyer lien", True, "present", "2019-0000101"),
    ))
    companions = (_filed("2019-0000099", "2019-04-01", "notice", [BUILDER], [], code="", name="NOTICE OF COMPLETION"),
                  _filed("2019-0000101", "2019-04-01", "lien", [OWNER_A], [BANK], name="DEED OF TRUST"),
                  _filed("2019-0000102", "2019-04-01", "fee", [OWNER_A], [OWNER_A, OWNER_B], name="GRANT DEED"))
    step = ProcessStep("2019-0000100", date(2019, 4, 1), "fee", "GRANT DEED", (BUILDER,), (OWNER_A,), "developer closing",
                       True, True, companions, reading)
    graph = InstrumentGraph(county="Placer")
    ctx = Context("Placer", (ASSOCIATION,), CTX.developers)
    add_process_steps(graph, (step,), ctx, apn=APN)
    placer = lambda n: instrument_id(n, "Placer")  # noqa: E731
    assert (placer("2019-0000099"), placer("2019-0000100")) in _edges(graph, EdgeKind.COMPLETES)
    assert (placer("2019-0000102"), placer("2019-0000100")) in _edges(graph, EdgeKind.BESIDE)
    assert graph.nodes[placer("2019-0000101")].attrs["filing"] == "DEED OF TRUST"
    assert graph.to_dict()["counties"] == ["Placer"]


def test_merge_and_neighborhood_keep_each_family_acyclic():
    one = InstrumentGraph(county="Example")
    add_filed(one, (_filed("2005-0000001", "2005-01-01", "fee", [BUILDER], [ASSOCIATION], ["2005-0000002"]),), CTX)
    two = InstrumentGraph(county="Example")
    add_filed(two, (_filed("2005-0000002", "2005-01-02", "fee", [BUILDER], [ASSOCIATION], ["2005-0000001"]),), CTX)
    one.merge(two)
    assert len(_edges(one, EdgeKind.CITES)) == 1 and one.cycles
    near = one.neighborhood(_id("2005-0000001"), depth=1)
    assert _id("2005-0000002") in near.nodes
    assert near.is_dag("citation")
