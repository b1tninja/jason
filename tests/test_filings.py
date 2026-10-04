from datetime import date

from jason.community.filings import (
    ADVANCES,
    CLOSES,
    ESCALATES,
    OPENS,
    Family,
    Process,
    encumbrances,
    instrument_class,
    naming,
    party_is,
)
from jason.community.governing import delivery_status, locate_governing
from jason.community.recorder import FiledInstrument
from jason.community.symbols import DeveloperDelivery
from mystique.developers import DEVELOPERS

ASSN = "MYSTIQUE COMMUNITY ASSOCIATION"


def _doc(number, code, grantors=(), grantees=(), cites=(), name=""):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    klass = instrument_class(code, name)
    return FiledInstrument(number, recorded, "", tuple(grantors), tuple(grantees), tuple(cites), code, name or klass.name)


def test_each_filing_knows_its_family_sides_and_effect():
    lien = instrument_class("386")
    assert lien.family is Family.LIEN and lien.process is Process.ASSESSMENT_LIEN and lien.effect == OPENS
    assert (lien.r_side, lien.e_side) == ("owner", "association")
    assert instrument_class("655").effect == CLOSES and instrument_class("655").process is Process.ASSESSMENT_LIEN
    assert instrument_class("802").process is Process.TAX_DEFAULT and instrument_class("720").effect == "cures"
    assert instrument_class("230").opens and instrument_class("238").closes and instrument_class("227").effect == ADVANCES
    # A transfer on death deed is a living owner's estate plan, not a death, though its name holds the word.
    tod = instrument_class("", "REVOCABLE TRANSFER ON DEATH DEED")
    assert tod.code == "697" and tod.family is Family.AUTHORITY and (tod.r_side, tod.e_side) == ("transferor", "beneficiary")
    assert instrument_class("153").family is Family.VITAL
    assert instrument_class("531").effect == ESCALATES
    assert instrument_class("", "DECLARATION OF HOMESTEAD").family is Family.AUTHORITY
    assert instrument_class("", "RELEASE OF STATE TAX LIEN").code == "624"
    assert instrument_class("999", "SOMETHING ELSE").family is Family.OTHER


def test_an_assessment_lien_closes_with_its_release_and_a_second_one_escalates():
    items = [
        _doc("201606270115", "386", ("PELLINGHAM ELIO D",), (ASSN,)),
        _doc("201712270328", "655", (ASSN,), ("PELLINGHAM ELIO D",)),
        _doc("201912021149", "386", ("PELLINGHAM ELIO D",), (ASSN,)),
        _doc("202106281613", "624", (ASSN,), ("PELLINGHAM ELIO D",)),
        _doc("202306080522", "386", ("PELLINGHAM ELIO D",), (ASSN,)),
        _doc("202401170833", "531", (ASSN,), ()),
        _doc("202410020596", "720", ("PELLINGHAM ELIO D", "PLACER FORECLOSURE INC TRUSTEE"), ("PELLINGHAM ELIO D",), ("202306080522",)),
    ]
    found = encumbrances(items, association="MYSTIQUE COMMUNITY")
    assert [(e.process, e.status, len(e.steps)) for e in found] == [
        (Process.ASSESSMENT_LIEN, "closed", 2),
        (Process.ASSESSMENT_LIEN, "closed", 2),
        (Process.ASSESSMENT_LIEN, "open", 3),
    ]
    third = found[2]
    assert [step.filing[:3] for step in third.steps] == ["386", "531", "720"]
    # The rescission ends the default, not the lien: a release (655 or 624) would close it.
    assert third.closed is None and third.steps[-1].effect == "cures"
    # Without the rescission the third lien is in default.
    assert encumbrances(items[:-1], association="MYSTIQUE COMMUNITY")[2].status == "in default"


def test_utility_liens_tax_default_and_loans_pair_by_debtor_or_citation():
    items = [
        _doc("202107090215", "401", (ASSN,), ("CITY OF SACRAMENTO UTILITIES",)),
        _doc("202109131463", "644", ("CITY OF SACRAMENTO UTILITIES",), (ASSN,)),
        _doc("202205110126", "401", (ASSN,), ("CITY OF SACRAMENTO UTILITIES",)),
        _doc("202308250761", "802", ("MYSTIQUE COMMUNITY ASSOC",), ("COUNTY OF SACRAMENTO TAX COLLECTOR",)),
        _doc("202407080293", "720", ("COUNTY OF SACRAMENTO TAX COLLECTOR",), ("MYSTIQUE COMMUNITY ASSOC",)),
        _doc("200709281719", "230", ("FALLOWFIELD PHILIPPA",), ("JOHN LAING MTG L P",)),
        _doc("201212121429", "230", ("BRACKENBURY PHILIPPA L", "BRACKENBURY THADDEUS H JR"), ("FLAGSTAR BK",)),
        _doc("201711220195", "238", (), ("BRACKENBURY PHILIPPA L", "BRACKENBURY THADDEUS H JR"), ("201212121429",)),
        _doc("200710291638", "230", ("COLDHARBOUR ESME A",), ("BANK OF AMER",)),
        _doc("201203021601", "695", ("RECONTRUST CO", "COLDHARBOUR ESME A"), ("CAYMUS CAPITAL RENTAL FUND I LLC",), ("200710291638",)),
    ]
    found = encumbrances(items, association="MYSTIQUE COMMUNITY")
    summary = [(e.process, e.opened.number, e.status) for e in found]
    assert (Process.UTILITY_LIEN, "202107090215", "closed") in summary
    assert (Process.UTILITY_LIEN, "202205110126", "open") in summary
    assert (Process.TAX_DEFAULT, "202308250761", "closed") in summary
    assert (Process.LOAN, "200709281719", "open") in summary
    assert (Process.LOAN, "201212121429", "closed") in summary
    assert (Process.LOAN, "200710291638", "closed") in summary
    sold = next(e for e in found if e.opened.number == "200710291638")
    assert sold.steps[-1].filing.startswith("695")


def test_naming_and_party_side():
    item = _doc("201912021160", "386", ("DITCHLING TIBOR PEREGRINE",), (ASSN,))
    assert naming([item], "DITCHLING TIBOR P") == (item,)
    assert naming([item], "FALLOWFIELD PHILIPPA") == ()
    assert party_is(item, "DITCHLING TIBOR") == "R" and party_is(item, "MYSTIQUE COMMUNITY") == "E"


def test_governing_records_are_tied_to_the_2792_23_delivery_and_phase():
    items = [
        _doc("200709120757", "301", ("WL HOMES LLC",)),
        _doc("200709120758", "324", ("JOHN LAING HOMES", "MYSTIQUE", "WL HOMES LLC")),
        _doc("200709200938", "220", ("JOHN LAING HOMES", "MYSTIQUE", "WL HOMES LLC")),
        _doc("201901161003", "320", ("MYSTIQUE PHASE 3", "WATT COMMUNITIES AT MYSTIQUE LLC"), (), ("200709200938",)),
        _doc("202003021215", "220", ("MYSTIQUE PHASE 4", "WATT COMMUNITIES AT MYSTIQUE LLC")),
        _doc("202101080352", "320", ("MYSTIQUE PHAS 8", "WATT COMMUNITIES AT MYSTIQUE LLC")),
        _doc("202312060284", "220", ("MYSTIQUE COMMUNITY ASSOCIATION",)),
        _doc("202001170712", "225", ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
        _doc("200709281625", "306", ("WL HOMES LLC",)),
        _doc("201912021149", "386", ("PELLINGHAM ELIO D",), (ASSN,)),
    ]
    records = locate_governing(items, developers=DEVELOPERS)
    roles = {record.number: (record.role, record.phase, record.developer) for record in records}
    assert roles["200709120757"] == ("condominium plan", None, "John Laing Homes")
    assert roles["200709120758"] == ("declaration", None, "John Laing Homes")
    assert roles["200709200938"] == ("restatement or amendment", None, "John Laing Homes")
    assert roles["201901161003"] == ("annexation", 3, "Watt Communities at Mystique")
    assert roles["202003021215"] == ("annexation", 4, "Watt Communities at Mystique")
    assert roles["202101080352"] == ("annexation", 8, "Watt Communities at Mystique")
    assert roles["202312060284"] == ("restatement or amendment", None, "")
    assert roles["200709281625"] == ("notice of completion", None, "John Laing Homes")
    assert "201912021149" not in roles
    status = {item.delivery: item for item in delivery_status(records, phases=(1, 2, 3, 4, 5, 6, 7, 8), annexed_phases=(2, 3, 4, 5, 6, 7, 8))}
    declaration = status[DeveloperDelivery.DECLARATION]
    assert declaration.found and declaration.missing == ("annexation of phase 2", "annexation of phase 5", "annexation of phase 6", "annexation of phase 7")
    assert status[DeveloperDelivery.CONDOMINIUM_PLAN].found
    assert not status[DeveloperDelivery.BYLAWS].found and "Secretary of State" in status[DeveloperDelivery.BYLAWS].missing[0]
    assert "map books" in status[DeveloperDelivery.SUBDIVISION_MAP].missing[0]


def test_the_association_record_reads_governing_liens_and_notices():
    from datetime import date as _date

    from jason.community.association_record import recorded_association
    from jason.community.reports import PublicReport
    from jason.community.symbols import Building

    reports = (
        PublicReport("130654SA", Building.BLDG_8, 1, 12, _date(2007, 11, 15), "John Laing Homes"),
        PublicReport("132246SA", Building.BLDG_3, 2, 12, _date(2008, 2, 29), "John Laing Homes", annexation=_date(2007, 12, 17)),
        PublicReport("163389SA", Building.BLDG_6, 5, 10, _date(2021, 2, 24), "Watt Communities at Mystique", annexation=_date(2020, 4, 28)),
    )
    items = [
        _doc("200709120758", "324", ("JOHN LAING HOMES", "MYSTIQUE", "WL HOMES LLC")),
        _doc("200712171310", "320", ("JOHN LAING HOMES", "WL HOMES LLC")),
        _doc("200609111898", "320", ("JOHN LAING HOMES", "WL HOMES LLC")),
        _doc("200809190460", "324", ("VALENCIA", "WL HOMES LLC")),
        _doc("202004280704", "320", ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
        _doc("201905221469", "320", ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
        _doc("202001170712", "225", ("WATT COMMUNITIES AT MYSTIQUE LLC",)),
        _doc("202312060284", "220", ("MYSTIQUE COMMUNITY ASSOCIATION",), (), ("202001170712",)),
        _doc("200709281731", "685", ("WL HOMES LLC",), ("MYSTIQUE COMMUNITY ASSN",)),
        _doc("201912021160", "386", ("DITCHLING TIBOR PEREGRINE",), (ASSN,)),
        _doc("202002210321", "655", (ASSN,), ("DITCHLING TIBOR PEREGRINE",)),
        _doc("202107090215", "401", (ASSN,), ("CITY OF SACRAMENTO UTILITIES",)),
        _doc("202203011216", "546", (ASSN,), ()),
        _doc("200709281625", "306", ("WL HOMES LLC",)),
    ]
    record = recorded_association(items, project="MYSTIQUE", association="MYSTIQUE COMMUNITY", developers=DEVELOPERS, reports=reports)
    phases = {r.number: r.phase for r in record.governing if r.role == "annexation"}
    assert phases == {"200712171310": 2, "202004280704": 5}
    assert [r.number for r in record.unplaced] == ["201905221469"]  # after opening, no phase, no date match
    assert any(r.number == "202001170712" and r.role == "amendment" for r in record.governing)  # cited by the association's own amendment
    deed = next(s for s in record.deliveries if s.delivery is DeveloperDelivery.COMMON_AREA_DEED)
    assert [r.number for r in deed.records] == ["200709281731"] and deed.records[0].developer == "John Laing Homes"
    assert all(r.number != "200609111898" for r in record.governing)  # before the project: another tract
    assert all(r.number != "200809190460" for r in (*record.governing, *record.unplaced))  # names Valencia
    declaration = next(s for s in record.deliveries if s.delivery is DeveloperDelivery.DECLARATION)
    assert declaration.missing == ()
    assert [(e.process, e.status) for e in record.placed] == [(Process.ASSESSMENT_LIEN, "closed")]
    assert [(e.process, e.status) for e in record.against] == [(Process.UTILITY_LIEN, "open")]
    assert [n.number for n in record.notices] == ["202203011216"]
    # A spec fact places the rescinded annexation and keeps the phase's delivery on the operative one.
    from jason.community.governing import Supersession

    pinned = recorded_association(
        items + [_doc("202003021215", "220", ("MYSTIQUE PHASE 4", "WATT COMMUNITIES AT MYSTIQUE LLC"), (), ("201901161002",))],
        project="MYSTIQUE", association="MYSTIQUE COMMUNITY", developers=DEVELOPERS, reports=reports,
        supersessions=(Supersession("201905221469", "202003021215", phase=4),),
    )
    assert pinned.unplaced == ()
    old = next(r for r in pinned.governing if r.number == "201905221469")
    assert old.phase == 4 and old.role == "annexation" and old.status == "rescinded and superseded by 202003021215"
    assert next(r for r in pinned.governing if r.number == "202003021215").status == "in force"


def test_parcel_liens_mark_tenure_and_community_liens(monkeypatch):
    from datetime import date as _date

    from jason.community.association_record import parcel_liens

    monkeypatch.setattr("asspy.filings.today_for_status", lambda: _date(2020, 1, 1))
    from jason.community.recorder import ChainStep, Conveyance

    steps = (
        ChainStep(Conveyance("200805071322", _date(2008, 5, 7), ("WL HOMES LLC",), ("KESTRELTON BRAM L",))),
        ChainStep(Conveyance("201009101231", _date(2010, 9, 10), ("KESTRELTON BRAM L",), ("YARROWBY COSMO A",))),
        ChainStep(Conveyance("201608110889", _date(2016, 8, 11), ("YARROWBY COSMO A TR",), ("DITCHLING TIBOR P",))),
    )
    cache = {
        "KESTRELTON BRAM L": [
            _doc("200805071324", "230", ("KESTRELTON BRAM",), ("JOHN LAING MTG L P",)),
            _doc("201009150001", "238", (), ("KESTRELTON BRAM L",), ("200805071324",)),
            _doc("201501010001", "376", ("KESTRELTON BRAM L",), ("SOMEONE",)),
        ],
        "DITCHLING TIBOR P": [
            _doc("201912021160", "386", ("DITCHLING TIBOR PEREGRINE",), (ASSN,)),
            _doc("202002210321", "655", (ASSN,), ("DITCHLING TIBOR PEREGRINE",)),
        ],
    }
    found = parcel_liens(lambda name: cache.get(name, []), steps, association="MYSTIQUE COMMUNITY", developers=DEVELOPERS)
    rows = [(lien.owner, lien.encumbrance.process, lien.encumbrance.status, lien.where) for lien in found]
    assert rows == [
        ("KESTRELTON BRAM L", Process.LOAN, "closed", "while owning here"),
        ("KESTRELTON BRAM L", Process.JUDGMENT_LIEN, "open", "another time or property"),
        ("DITCHLING TIBOR P", Process.ASSESSMENT_LIEN, "closed", "this community"),
    ]
    # Ten years after the 2015 abstract, with no renewal of record, the judgment lien has lapsed.
    judgment = found[1].encumbrance
    assert judgment.unenforceable_after == _date(2025, 1, 1)
    monkeypatch.setattr("asspy.filings.today_for_status", lambda: _date(2025, 1, 2))
    assert judgment.status == "lapsed"


def test_no_association_name_skips_no_owner(monkeypatch):
    from datetime import date as _date

    from jason.community.association_record import parcel_liens
    from jason.community.recorder import ChainStep, Conveyance

    monkeypatch.setattr("asspy.filings.today_for_status", lambda: _date(2020, 1, 1))
    steps = (ChainStep(Conveyance("200805071322", _date(2008, 5, 7), ("WL HOMES LLC",), ("KESTRELTON BRAM L",))),)
    cache = {"KESTRELTON BRAM L": [_doc("201501010001", "376", ("KESTRELTON BRAM L",), ("SOMEONE",))]}
    found = parcel_liens(lambda name: cache.get(name, []), steps, association="", developers=DEVELOPERS)
    assert [lien.owner for lien in found] == ["KESTRELTON BRAM L"]


def test_a_renewed_judgment_and_a_federal_tax_lien_run_from_their_newest_recording(monkeypatch):
    from datetime import date as _date

    from jason.community.filings import ADVANCES, OPENS, Encumbrance, Step

    def step(number, day, effect):
        return Step(number, day, "376 ABSTRACT OF JUDGMENT", effect, ("DOE JANE",), ("BANK",))

    renewed = Encumbrance(Process.JUDGMENT_LIEN, ("DOE JANE",), ("BANK",), (step("201001010001", _date(2010, 1, 1), OPENS), step("201912010001", _date(2019, 12, 1), ADVANCES)))
    assert renewed.unenforceable_after == _date(2029, 12, 1)
    monkeypatch.setattr("asspy.filings.today_for_status", lambda: _date(2026, 9, 28))
    assert renewed.status == "open"
    federal = Encumbrance(Process.FEDERAL_TAX_LIEN, ("DOE JANE",), ("IRS",), (Step("201601010001", _date(2016, 1, 1), "402 FEDERAL TAX LIEN", OPENS, ("DOE JANE",), ("IRS",)),))
    assert federal.unenforceable_after == _date(2026, 1, 31) and federal.status == "lapsed"


def test_a_bare_name_lien_carries_a_namesake_caveat_unless_the_claimant_ties_it_here():
    from datetime import date as _date

    from jason.community.association_record import parcel_liens
    from jason.community.briefs import _namesake, lien_row
    from jason.community.filings import NameMatch
    from jason.community.recorder import ChainStep, Conveyance

    steps = (ChainStep(Conveyance("201405291199", _date(2014, 5, 29), ("GRIMSDITCH INGO",), ("PENNYWHISTLE LEOPOLD W",))),)
    cache = [
        _doc("202101050838", "389", ("PENNYWHISTLE LEOPOLD",), ("ACME ABATEMENT INC",)),
        _doc("202102040372", "368", ("PENNYWHISTLE LEOPOLD",), ("ULTRALIGHT RESIDENTIAL SOLAR LLC",)),
    ]
    found = parcel_liens(
        lambda name: cache, steps, association="MYSTIQUE COMMUNITY", developers=DEVELOPERS,
        corroborates=lambda e: any("ULTRALIGHT" in party for party in e.claimant),
    )
    lien, solar = found
    assert lien.name_match is NameMatch.BARE and lien.namesake_risk and not solar.namesake_risk
    row = lien_row(lien, where=lien.where)
    assert row["namesakeRisk"] is True and row["nameMatch"].startswith("the filing gives only") and row["where"] == "while owning here"
    assert "names the owner only as PENNYWHISTLE LEOPOLD; confirm it is this owner" in _namesake(lien) and _namesake(solar) == ""


def test_a_lien_during_an_owners_second_step_is_during_their_tenure():
    from datetime import date as _date

    from jason.community.association_record import parcel_liens
    from jason.community.recorder import ChainStep, Conveyance

    # The owner buys in 2020 and re-vests with a co-owner in 2023; the 2024 judgment names her by initial.
    steps = (
        ChainStep(Conveyance("202003201616", _date(2020, 3, 20), ("SELLER SAM",), ("WINTERGREEN SASKIA MIREN",))),
        ChainStep(Conveyance("202301111162", _date(2023, 1, 11), ("WINTERGREEN SASKIA MIREN",), ("WINTERGREEN SASKIA MIREN", "MIREN ORLA"))),
    )
    judgment = [_doc("202401111161", "376", ("WINTERGREEN SASKIA M",), ("STATE OF CA EMPLOYMENT DEVELOPMENT DEPARTMENT",))]
    found = parcel_liens(lambda name: judgment if name.startswith("WINTERGREEN") else [], steps, association="MYSTIQUE COMMUNITY", developers=DEVELOPERS)
    assert [(lien.owner, lien.encumbrance.process, lien.where) for lien in found] == [("WINTERGREEN SASKIA MIREN", Process.JUDGMENT_LIEN, "while owning here")]
