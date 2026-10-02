from datetime import date

from jason.community.processes import (
    BlanketRelease,
    CompanionVesting,
    DeveloperClosing,
    ForeclosureSale,
    PurchaseMoney,
    ReoResale,
    Resale,
    Restatement,
    follow_on,
    gather,
    read,
    window,
)
from jason.community.recorder import FiledInstrument
from mystique.developers import DEVELOPERS


def _doc(number, kind, grantors=(), grantees=(), cites=()):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return FiledInstrument(number, recorded, kind, grantors, grantees, cites)


def test_a_developer_closing_is_complete_when_the_notice_and_the_lien_match():
    grant = _doc("200710291637", "fee", ("WL HOMES LLC",), ("ALDER CASEY A",))
    around = (
        _doc("200710291636", "notice", ("WL HOMES LLC",), ()),
        _doc("200710291638", "lien", ("ALDER CASEY A",), ("BANK OF AMERICA",)),
    )
    found = read(grant, around, DEVELOPERS)
    assert len(found) == 1
    assert found[0].process == "developer closing"
    assert found[0].complete
    assert found[0].continues


def test_a_power_of_attorney_does_not_fill_the_buyer_lien():
    grant = _doc("200809170157", "fee", ("WL HOMES LLC",), ("BIRCH NORA K",))
    around = (
        _doc("200809170156", "notice", ("WL HOMES LLC",), ()),
        _doc("200809170158", "", ("BIRCH NORA K",), ()),
    )
    found = read(grant, around, DEVELOPERS)
    assert found[0].process == "developer closing"
    assert not found[0].complete
    lien = next(item for item in found[0].slots if item.role == "buyer lien")
    assert lien.reason == "other"
    assert lien.number == "200809170158"


def test_an_order_of_sale_does_not_fill_the_notice():
    grant = _doc("200910021505", "fee", ("JOHN LAING HOMES",), ("MAVERICK PARTNERS WEST LLC",))
    around = (
        _doc("200910021504", "", ("JOHN LAING HOMES",), ()),
        _doc("200910021506", "lien", ("MAVERICK PARTNERS WEST LLC",), ("A LENDER",)),
    )
    found = read(grant, around, DEVELOPERS)
    assert found[0].process == "developer closing"
    notice = next(item for item in found[0].slots if item.role == "notice of completion")
    assert notice.reason == "other"


def test_another_parcels_reconveyance_does_not_change_the_closing():
    grant = _doc("200710291637", "fee", ("WL HOMES LLC",), ("ALDER CASEY A",))
    around = (
        _doc("200710291636", "notice", ("WL HOMES LLC",), ()),
        _doc("200710291638", "lien", ("ALDER CASEY A",), ("BANK OF AMERICA",)),
        _doc("200710291640", "release", ("A TRUSTEE",), ("SOMEONE ELSE",)),
    )
    found = read(grant, around, DEVELOPERS)
    assert [item.process for item in found] == ["developer closing"]
    assert found[0].complete


def test_another_buyers_deed_of_trust_does_not_complete_the_closing():
    grant = _doc("200710291637", "fee", ("WL HOMES LLC",), ("ALDER CASEY A",))
    around = (
        _doc("200710291636", "notice", ("WL HOMES LLC",), ()),
        _doc("200710291638", "lien", ("SOMEONE ELSE",), ("BANK OF AMERICA",)),
    )
    found = read(grant, around, DEVELOPERS)
    assert not found[0].complete
    lien = next(item for item in found[0].slots if item.role == "buyer lien")
    assert lien.reason == "other parties"


def test_a_blanket_release_is_complete_when_the_reconveyance_cites_the_lien():
    grant = _doc("201206151335", "fee", ("MYSTIQUE BLDRS LLC",), ("CEDAR ULRIC D",))
    around = (
        _doc("201206151336", "release", ("A TRUSTEE",), ("MYSTIQUE BLDRS LLC",), ("201102010769",)),
        _doc("201102010769", "lien", ("MYSTIQUE BLDRS LLC",), ("ROBIN LOANER",)),
    )
    found = read(grant, around, DEVELOPERS)
    assert len(found) == 1
    assert found[0].process == "blanket release"
    assert found[0].complete
    lien = next(item for item in found[0].slots if item.role == "buyer lien")
    assert not lien.required
    assert lien.reason == "other"


def test_a_reconveyance_that_cites_nothing_leaves_the_lien_open():
    grant = _doc("201204241055", "fee", ("MYSTIQUE BLDRS LLC",), ("DOGWOOD JAMIE A", "DOGWOOD KATE M"))
    around = (
        _doc("201204241056", "lien", ("DOGWOOD JAMIE A",), ("MERS",)),
        _doc("201204241057", "release", ("A TRUSTEE",), ("MYSTIQUE BLDRS LLC",)),
    )
    found = read(grant, around, DEVELOPERS)
    assert found[0].process == "blanket release"
    assert not found[0].complete
    released = next(item for item in found[0].slots if item.role == "released lien")
    assert released.reason == "missing"
    assert released.number == "201204241057"
    buyer = next(item for item in found[0].slots if item.role == "buyer lien")
    assert buyer.reason == "present"


def test_a_builder_grant_with_no_notice_and_no_release_is_read_both_ways():
    grant = _doc("201203270471", "fee", ("MYSTIQUE BLDRS LLC",), ("ELM MAREN",))
    found = read(grant, (), DEVELOPERS)
    assert [item.process for item in found] == ["developer closing", "blanket release"]
    assert all(not item.complete for item in found)
    closing = found[0].gaps
    release = found[1].gaps
    assert any(item.role == "notice of completion" for item in closing)
    assert any(item.role == "partial reconveyance" for item in release)


def test_a_trustees_deed_is_complete_when_it_cites_the_deed_of_trust():
    sale = _doc(
        "201111290137",
        "foreclosure",
        ("A TRUSTEE", "FIR ANGELA M"),
        ("FEDERAL NATL MTG ASSN",),
        ("200712131171",),
    )
    around = (_doc("200712131171", "lien", ("FIR ANGELA M",), ("A LENDER",)),)
    found = read(sale, around, DEVELOPERS)
    assert found[0].process == "foreclosure"
    assert found[0].complete
    assert not issubclass(ForeclosureSale, PurchaseMoney)


def test_a_trustees_deed_that_cites_nothing_names_no_lender_search():
    sale = _doc("201203021601", "foreclosure", ("RECONTRUST", "ALDER CASEY A"), ("CAYMUS CAPITAL RENTAL FUND I LLC",))
    found = read(sale, (), DEVELOPERS)
    assert not found[0].complete
    assert found[0].gaps[0].role == "deed of trust"
    assert found[0].gaps[0].reason == "missing"


def test_an_uncited_lender_grant_is_an_reo_resale():
    grant = _doc("201203270988", "fee", ("FEDERAL NATL MTG ASSN",), ("GROVE HALLIE P",))
    found = read(grant, (), DEVELOPERS)
    assert len(found) == 1
    assert found[0].process == "reo resale"
    assert not found[0].complete
    prior = next(item for item in found[0].gaps if item.role == "trustee's deed")
    assert prior.reason == "missing"


def test_an_reo_resale_is_complete_when_it_cites_the_trustees_deed():
    grant = _doc(
        "201203270988",
        "fee",
        ("FEDERAL NATL MTG ASSN",),
        ("GROVE HALLIE P",),
        ("201111290137",),
    )
    around = (_doc("201111290137", "foreclosure", ("A TRUSTEE",), ("FEDERAL NATL MTG ASSN",)),)
    found = read(grant, around, DEVELOPERS)
    assert found[0].complete


def test_a_cited_prior_that_is_not_loaded_stays_unloaded():
    grant = _doc("201203270988", "fee", ("FEDERAL NATL MTG ASSN",), ("GROVE HALLIE P",), ("201111290137",))
    found = read(grant, (), DEVELOPERS)
    prior = next(item for item in found[0].slots if item.role == "trustee's deed")
    assert prior.reason == "unloaded"
    assert prior.number == "201111290137"


def test_a_grant_between_owners_that_cites_nothing_is_an_open_resale():
    grant = _doc("202107190658", "fee", ("CAYMUS CAPITAL RENTAL FUND I LLC",), ("HATCHERY SACRAMENTO RENTAL FUND LLC",))
    found = read(grant, (), DEVELOPERS)
    assert found[0].process == "resale"
    assert not found[0].complete
    assert found[0].gaps[0].role == "prior deed"


def test_a_deed_into_the_owners_trust_does_not_continue():
    grant = _doc("202408130870", "fee", ("HAZEL MORGAN",), ("HAZEL MORGAN TRUSTEE",))
    found = read(grant, (), DEVELOPERS)
    assert found[0].process == "restatement"
    assert found[0].complete
    assert not found[0].continues


def test_a_second_deed_into_the_buyer_puts_the_lien_on_the_following_number():
    grant = _doc("200709270983", "fee", ("WL HOMES LLC",), ("IVY BARRETT M",))
    around = (
        _doc("200709270982", "notice", ("WL HOMES LLC",), ()),
        _doc("200709270984", "fee", ("IVY SHERI",), ("IVY BARRETT M",)),
    )
    found = read(grant, around, DEVELOPERS)
    assert found[0].process == "developer closing"
    companion = next(item for item in found[0].slots if item.role == "companion vesting")
    assert companion.reason == "present"
    assert companion.number == "200709270984"
    lien = next(item for item in found[0].gaps if item.role == "buyer lien")
    assert lien.reason == "missing"
    assert lien.number == "200709270985"


def test_a_run_of_companion_deeds_puts_the_lien_after_the_run():
    grant = _doc("200807111415", "fee", ("WL HOMES LLC",), ("JUNIPER JENNA", "JUNIPER RICK"))
    around = (
        _doc("200807111414", "notice", ("WL HOMES LLC",), ()),
        _doc("200807111416", "fee", ("KESTREL DARBY",), ("JUNIPER JENNA",)),
        _doc("200807111417", "fee", ("JUNIPER KARA A",), ("JUNIPER RICK",)),
    )
    found = read(grant, around, DEVELOPERS)
    lien = next(item for item in found[0].gaps if item.role == "buyer lien")
    assert lien.reason == "missing"
    assert lien.number == "200807111418"
    done = read(
        grant,
        (*around, _doc("200807111418", "lien", ("JUNIPER RICK",), ("A LENDER",))),
        DEVELOPERS,
    )
    assert done[0].complete


def test_the_lien_after_a_companion_deed_completes_the_closing():
    grant = _doc("200709270983", "fee", ("WL HOMES LLC",), ("IVY BARRETT M",))
    around = (
        _doc("200709270982", "notice", ("WL HOMES LLC",), ()),
        _doc("200709270984", "fee", ("IVY SHERI",), ("IVY BARRETT M",)),
        _doc("200709270985", "lien", ("IVY BARRETT M",), ("A LENDER",)),
    )
    found = read(grant, around, DEVELOPERS)
    assert found[0].complete


def test_a_neighbor_that_does_not_name_the_buyer_is_not_followed():
    grant = _doc("200809110134", "fee", ("WL HOMES LLC",), ("LARCH CINDA M",))
    around = (
        _doc("200809110133", "notice", ("WL HOMES LLC",), ()),
        _doc("200809110135", "fee", ("FEDERAL HOME LN MTG CORP",), ("MAPLE DONAL S",)),
    )
    found = read(grant, around, DEVELOPERS)
    companion = next(item for item in found[0].slots if item.role == "companion vesting")
    assert companion.reason == "missing"
    lien = next(item for item in found[0].gaps if item.role == "buyer lien")
    assert lien.reason == "other"
    assert lien.number == "200809110135"


def test_the_buyers_power_of_attorney_is_a_companion():
    grant = _doc("200812050439", "fee", ("WL HOMES LLC",), ("NUTMEG YANA",))
    poa = FiledInstrument(
        "200812050440",
        date(2008, 12, 5),
        "",
        ("NUTMEG YANA",),
        ("OAKES MENA Q",),
        (),
        "466",
        "POWER OF ATTORNEY",
    )
    found = read(grant, (_doc("200812050438", "notice", ("WL HOMES LLC",), ()), poa), DEVELOPERS)
    companion = next(item for item in found[0].slots if item.role == "companion vesting")
    assert companion.reason == "present"
    lien = next(item for item in found[0].gaps if item.role == "buyer lien")
    assert lien.number == "200812050441"


def test_a_shorter_trustor_is_not_the_buyer():
    grant = _doc("200809110902", "fee", ("WL HOMES LLC",), ("PINE CHRIS C",))
    around = (
        _doc("200809110901", "notice", ("WL HOMES LLC",), ()),
        _doc("200809110903", "lien", ("PINE CHRISTOPHER C",), ("MERS",)),
    )
    found = read(grant, around, DEVELOPERS)
    lien = next(item for item in found[0].gaps if item.role == "buyer lien")
    assert lien.reason == "other parties"


def test_purchase_money_is_the_mixin_on_the_sales_that_can_be_financed():
    assert issubclass(DeveloperClosing, PurchaseMoney)
    assert issubclass(DeveloperClosing, CompanionVesting)
    assert issubclass(BlanketRelease, PurchaseMoney)
    assert issubclass(ReoResale, PurchaseMoney)
    assert issubclass(Resale, PurchaseMoney)
    assert not issubclass(Restatement, PurchaseMoney)


def test_gather_loads_neighbors_and_their_citations():
    grant = _doc("201206151335", "fee", ("MYSTIQUE BLDRS LLC",), ("CEDAR ULRIC D",))
    held = {
        "201206151336": _doc(
            "201206151336",
            "release",
            ("A TRUSTEE",),
            ("MYSTIQUE BLDRS LLC",),
            ("201102010769",),
        ),
        "201102010769": _doc("201102010769", "lien", ("MYSTIQUE BLDRS LLC",), ("ROBIN LOANER",)),
    }
    found = gather(held.get, grant, before=0, after=1)
    assert [item.number for item in found] == ["201206151336", "201102010769"]


def test_a_complete_closing_follows_the_buyer_not_the_lender():
    grant = _doc("200710291637", "fee", ("WL HOMES LLC",), ("ALDER CASEY A",))
    around = (
        _doc("200710291636", "notice", ("WL HOMES LLC",), ()),
        _doc("200710291638", "lien", ("ALDER CASEY A",), ("BANK OF AMERICA",)),
    )
    reading = read(grant, around, DEVELOPERS)[0]
    found = follow_on(reading, grant)
    assert len(found) == 1
    assert found[0].party == "ALDER CASEY A"
    assert found[0].role == "grantor"
    assert "695" in found[0].filings
    assert found[0].after == date(2007, 10, 30)
    assert found[0].before is None
    closed = follow_on(reading, grant, until=date(2012, 3, 1))
    assert closed[0].before == date(2012, 3, 1)


def test_same_day_and_earlier_slots_carry_inclusive_date_bounds():
    grant = _doc("200710291637", "fee", ("WL HOMES LLC",), ("ALDER CASEY A",))
    notice = next(slot for slot in DeveloperClosing().slots() if slot.role == "notice of completion")
    lien = next(slot for slot in ForeclosureSale().slots() if slot.role == "deed of trust")
    assert window(notice, grant) == (date(2007, 10, 29), date(2007, 10, 29))
    assert window(lien, grant) == (None, date(2007, 10, 28))
    found = read(grant, (), DEVELOPERS)
    closing = found[0]
    assert closing.process == "developer closing"
    buyer = next(item for item in closing.gaps if item.role == "buyer lien")
    assert buyer.after == date(2007, 10, 29)
    assert buyer.before == date(2007, 10, 29)


def test_a_cited_prior_recorded_after_the_anchor_is_the_wrong_date():
    sale = _doc(
        "201111290137",
        "foreclosure",
        ("A TRUSTEE", "FIR ANGELA M"),
        ("FEDERAL NATL MTG ASSN",),
        ("201203021601",),
    )
    around = (_doc("201203021601", "lien", ("FIR ANGELA M",), ("A LENDER",)),)
    found = read(sale, around, DEVELOPERS)
    prior = next(item for item in found[0].slots if item.role == "deed of trust")
    assert prior.reason == "wrong date"
    assert prior.after is None
    assert prior.before == date(2011, 11, 28)


def test_a_released_builder_lien_must_predate_the_grant():
    grant = _doc("201206151335", "fee", ("MYSTIQUE BLDRS LLC",), ("CEDAR ULRIC D",))
    around = (
        _doc("201206151336", "release", ("A TRUSTEE",), ("MYSTIQUE BLDRS LLC",), ("201102010769",)),
        _doc("201102010769", "lien", ("MYSTIQUE BLDRS LLC",), ("ROBIN LOANER",)),
    )
    found = read(grant, around, DEVELOPERS)
    assert found[0].complete
    released = next(item for item in found[0].slots if item.role == "released lien")
    assert released.after is None
    assert released.before == date(2012, 6, 14)


def test_an_open_reo_names_the_earlier_window_for_the_trustees_deed():
    grant = _doc("201203270988", "fee", ("FEDERAL NATL MTG ASSN",), ("GROVE HALLIE P",))
    found = read(grant, (), DEVELOPERS)
    prior = next(item for item in found[0].gaps if item.role == "trustee's deed")
    assert prior.after is None
    assert prior.before == date(2012, 3, 26)


def test_a_complete_foreclosure_does_not_follow_the_lender():
    sale = _doc(
        "201111290137",
        "foreclosure",
        ("A TRUSTEE", "FIR ANGELA M"),
        ("FEDERAL NATL MTG ASSN",),
        ("200712131171",),
    )
    around = (_doc("200712131171", "lien", ("FIR ANGELA M",), ("A LENDER",)),)
    reading = read(sale, around, DEVELOPERS)[0]
    assert reading.complete
    assert follow_on(reading, sale) == ()


def test_an_open_reo_does_not_invent_a_foreclosed_owner():
    grant = _doc("201203270988", "fee", ("FEDERAL NATL MTG ASSN",), ("GROVE HALLIE P",))
    reading = read(grant, (), DEVELOPERS)[0]
    assert follow_on(reading, grant) == ()


def test_each_process_says_whether_it_reassesses():
    from jason.community.processes import ExcludedTransfer, Rerecording

    assert DeveloperClosing.reassesses and BlanketRelease.reassesses
    assert ForeclosureSale.reassesses and ReoResale.reassesses and Resale.reassesses
    assert not Restatement.reassesses and not Rerecording.reassesses and not ExcludedTransfer.reassesses


def test_a_grant_re_recorded_within_the_window_reads_as_a_re_recording():
    first = _doc("202112270931", "fee", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("SPRUCE ESAU", "SPRUCEY RAHEL"))
    again = _doc("202201191398", "fee", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("SPRUCE ESAU", "SPRUCEY RAHEL"))
    readings = read(again, (first,), DEVELOPERS)
    assert [item.process for item in readings] == ["re-recording"]
    assert readings[0].complete and not readings[0].continues and not readings[0].reassesses
    assert readings[0].slots[1].number == "202112270931"
    # Without the twin in hand the same grant reads as the builder's sale.
    assert {item.process for item in read(again, (), DEVELOPERS)} == {"developer closing", "blanket release"}


def test_a_twin_needs_the_same_parties_and_an_earlier_day():
    from jason.community.processes import earlier_twin, twins

    first = _doc("200709281724", "fee", ("WL HOMES LLC",), ("TAMARACK DENNY C", "TAMARACK MELISA S"))
    again = _doc("200710131262", "fee", ("WL HOMES LLC",), ("TAMARACK DENNY C", "TAMARACK MELISA S"))
    spouse = _doc("200710131263", "fee", ("WL HOMES LLC",), ("TAMARACK DENNY C",))
    late = _doc("200812131262", "fee", ("WL HOMES LLC",), ("TAMARACK DENNY C", "TAMARACK MELISA S"))
    same_day = _doc("200709281725", "fee", ("WL HOMES LLC",), ("TAMARACK DENNY C", "TAMARACK MELISA S"))
    assert earlier_twin(again, (first, spouse)).number == "200709281724"
    assert earlier_twin(spouse, (first,)) is None
    assert earlier_twin(late, (first,)) is None
    assert earlier_twin(same_day, (first,)) is None
    assert [(a.number, b.number) for a, b in twins((again, first, spouse, late))] == [("200709281724", "200710131262")]


def test_a_grant_between_family_is_an_excluded_transfer_that_continues():
    from jason.community.processes import family_transfer

    gift = _doc("201103300428", "fee", ("PINE CHRISTOPHER",), ("PINE GWYN",))
    readings = read(gift, (), DEVELOPERS)
    assert [item.process for item in readings] == ["excluded transfer"]
    assert readings[0].continues and not readings[0].reassesses
    assert [item.role for item in readings[0].gaps] == ["prior deed"]
    assert family_transfer(("DOE JORDAN C",), ("DOE JORDAN C TRUSTEE", "JCDT TRUST")) is False
    assert family_transfer(("WATT COMMUNITIES AT MYSTIQUE LLC",), ("WATT COMMUNITIES LLC",)) is True
    assert family_transfer(("THE ROBIN & SKY FAMILY TRUST",), ("AIRES BLOCK LLC",)) is False
    sale = _doc("201408010234", "fee", ("QUINCE MICA K", "QUINCE STEVAN A"), ("REDWOOD EUGEN S",))
    assert [item.process for item in read(sale, (), DEVELOPERS)] == ["resale"]
    assert read(sale, (), DEVELOPERS)[0].reassesses


def test_a_re_recording_may_add_the_builders_parent_beside_the_builder():
    from jason.community.processes import earlier_twin

    first = _doc("202112281312", "fee", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("UMBER DANI", "VIOLET BRITT"))
    again = _doc("202201200309", "fee", ("WATT COMMUNITIES AT MYSTIQUE LLC", "WATT COMMUNITIES LLC"), ("UMBER DANI", "VIOLET BRITT"))
    other_buyer = _doc("202201200310", "fee", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("UMBER DANI",))
    assert earlier_twin(again, (first,)).number == "202112281312"
    assert earlier_twin(other_buyer, (first,)) is None


def test_a_lien_indexed_without_the_initial_or_the_junior_is_still_the_buyers():
    notice = _doc("200709281625", "notice", ("WL HOMES LLC",))
    grant = _doc("200709281626", "fee", ("WL HOMES LLC",), ("WILLOW CARL W JR",))
    lien = _doc("200709281627", "lien", ("WILLOW CARL W",), ("HOMECOMINGS FINL LLC",))
    readings = read(grant, (notice, lien), DEVELOPERS)
    assert readings[0].process == "developer closing" and readings[0].complete
    other = _doc("200709281627", "lien", ("WILLOW CARLA",), ("HOMECOMINGS FINL LLC",))
    assert not read(grant, (notice, other), DEVELOPERS)[0].complete
    grant2 = _doc("200807210403", "fee", ("WL HOMES LLC",), ("YARROW JOSH E", "YARROW MIRA S"))
    lien2 = _doc("200807210404", "lien", ("YARROW JOSH", "YARROW MIRA"), ("JOHN LAING MTG L P",))
    assert read(grant2, (_doc("200807210402", "notice", ("WL HOMES LLC",)), lien2), DEVELOPERS)[0].complete


def test_the_notice_can_sit_behind_a_companion_vesting():
    notice = _doc("202203180705", "notice", ("WATT COMMUNITIES AT MYSTIQUE LLC",))
    companion = _doc("202203180706", "fee", ("ZINNIA DANA LARK",), ("ZINNIA NAOMA",))
    grant = _doc("202203180707", "fee", ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("ZINNIA NAOMA",))
    lien = _doc("202203180708", "lien", ("ZINNIA NAOMA",), ("CALIBER HOME LOANS INC",))
    reading = read(grant, (notice, companion, lien), DEVELOPERS)[0]
    assert reading.process == "developer closing" and reading.complete
    assert [(item.role, item.number) for item in reading.slots if item.reason == "present"] == [
        ("notice of completion", "202203180705"),
        ("grant", "202203180707"),
        ("companion vesting", "202203180706"),
        ("buyer lien", "202203180708"),
    ]
    # A stranger's deed in that slot is not skipped over.
    stranger = _doc("202203180706", "fee", ("XU ALINA",), ("WREN GWENDA",))
    assert not read(grant, (notice, stranger, lien), DEVELOPERS)[0].complete
