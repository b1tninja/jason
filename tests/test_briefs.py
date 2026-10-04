from datetime import date

from jason.community.association_record import ParcelLien, RecordedAssociation
from jason.community.briefs import (
    assessment_liens,
    brief_markdown,
    escrow_brief,
    explain_filing,
    lifecycle_lookup,
    recent_filings,
    unit_brief,
)
from jason.community.filings import CLOSES, ESCALATES, OPENS, Encumbrance, Process, Step
from jason.community.parcel_history import HistoryStep, ParcelHistory
from jason.community.solar import SolarProgram, solar_record
from jason.community.standing import OwnerEvent, TaxStanding

ASSN = "MYSTIQUE COMMUNITY ASSOCIATION"


def _step(order, number, process, grantees, *, price=None, developer="", reassesses=True, grantors=("SELLER",)):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return HistoryStep(order, number, recorded, grantors, grantees, (), process, True, reassesses, developer, price, None, None, False, None, None, None, "handoff", "", "")


def _lifecycle(process, opened, debtor, claimant, *, closed_by=None, escalated_by=None):
    steps = [Step(opened, date(int(opened[:4]), int(opened[4:6]), int(opened[6:8])), {"assessment": "386 NOTICE OF ASSOCIATION LIEN", "mechanics": "389 NOTICE OF CLAIM OR MECHANICS LIEN", "loan": "230 DEED OF TRUST"}[process.name.split("_")[0].lower() if process is not Process.MECHANICS_LIEN else "mechanics"] if process in (Process.ASSESSMENT_LIEN, Process.MECHANICS_LIEN, Process.LOAN) else "376 ABSTRACT OF JUDGMENT", OPENS, (debtor,), (claimant,))]
    if escalated_by:
        steps.append(Step(escalated_by, date(int(escalated_by[:4]), int(escalated_by[4:6]), int(escalated_by[6:8])), "531 NOTICE OF DEFAULT", ESCALATES, (claimant,), ()))
    if closed_by:
        steps.append(Step(closed_by, date(int(closed_by[:4]), int(closed_by[4:6]), int(closed_by[6:8])), "655 RELEASE OF ASSESSMENT OF ASSOCIATION LIEN", CLOSES, (claimant,), (debtor,)))
    return Encumbrance(process, (debtor,), (claimant,), tuple(steps))


PROGRAM = SolarProgram("shared solar", "Watt", (1,), ("ULTRALIGHT RESIDENTIAL SOLAR LLC",), ("ULTRALIGHT",))


def _unit():
    steps = (
        _step(1, "202003090001", "developer closing", ("OAKHURST ONDINE",), price=32_500_000, developer="Watt", grantors=("WATT COMMUNITIES AT MYSTIQUE LLC",)),
        _step(2, "202405010002", "resale", ("NEXT OWNER",), price=42_000_000, grantors=("OAKHURST ONDINE",)),
    )
    liens = (
        ParcelLien("NEXT OWNER", _lifecycle(Process.ASSESSMENT_LIEN, "202506010010", "NEXT OWNER", ASSN, escalated_by="202509010011"), True, True),
        ParcelLien("OAKHURST ONDINE", _lifecycle(Process.ASSESSMENT_LIEN, "202201010012", "OAKHURST ONDINE", ASSN, closed_by="202206010013"), True, True),
        ParcelLien("NEXT OWNER", Encumbrance(Process.MECHANICS_LIEN, ("NEXT OWNER",), ("ACME ROOFING INC",), (Step("202412060014", date(2024, 12, 6), "389 NOTICE OF CLAIM OR MECHANICS LIEN", OPENS, ("NEXT OWNER",), ("ACME ROOFING INC",)),)), True, False),
        ParcelLien("OAKHURST ONDINE", Encumbrance(Process.JUDGMENT_LIEN, ("OAKHURST ONDINE",), ("SOME CREDITOR",), (Step("201001010015", date(2010, 1, 1), "376 ABSTRACT OF JUDGMENT", OPENS, ("OAKHURST ONDINE",), ("SOME CREDITOR",)),)), False, False),
    )
    events = (OwnerEvent("NEXT OWNER", "202507010016", date(2025, 7, 1), "153 AFFIDAVIT OF DEATH", "death of this owner", ("NEXT OWNER",), True, True),)
    solar = solar_record(1, ("NEXT OWNER",), (), PROGRAM)
    return ParcelHistory(
        "20111700220013", "999 MACON DR", 4, 1, 4, "154410SA", "Watt Communities at Mystique", "202405010002", date(2024, 5, 1), (), steps, (), (), True, 2020, 2025,
        liens=liens, taxes=TaxStanding(2020, 2025, (), ((2025, 250000),), ()), owner_events=events, solar=solar,
    )


def _record():
    placed = (_lifecycle(Process.ASSESSMENT_LIEN, "202506010010", "NEXT OWNER", ASSN, escalated_by="202509010011"), _lifecycle(Process.ASSESSMENT_LIEN, "201901010020", "SOMEONE GONE", ASSN))
    return RecordedAssociation((), (), placed, (), (), (), ())


def test_the_unit_brief_reads_the_stores_and_carries_its_caveats():
    brief = unit_brief(_unit())
    assert brief["apn"] == "201-1170-022-0013" and brief["owner"]["names"] == ["NEXT OWNER"] and brief["owner"]["since"] == "2024-05-01"
    assert brief["chain"]["lastSale"]["priceCents"] == 42_000_000 and brief["chain"]["reachesDeveloper"]
    assert [l["process"] for l in brief["liens"]["open"]] == ["assessment lien", "mechanics lien"]
    assert brief["liens"]["open"][0]["status"] == "in default" and brief["liens"]["closedWhileOwningHere"] == 1 and brief["liens"]["otherTimeOrProperty"] == 1
    assert brief["liens"]["openOnPriorOwners"] == []
    assert brief["solar"]["standing"] == "NO_FILING" and brief["taxes"]["status"] == "due" and brief["ownerEvents"][0]["stillOnTitle"]
    assert "Civil Code" in brief["liens"]["open"][0]["law"] and len(brief["caveats"]) == 6
    text = brief_markdown(brief)
    assert text.startswith("# 999 MACON DR") and "- **Open liens on the current owner** assessment lien by MYSTIQUE COMMUNITY ASSOCIATION (in default); mechanics lien by ACME ROOFING INC" in text


def test_a_prior_owners_open_loan_is_presumed_paid_at_the_sale():
    base = _unit()
    prior_loan = ParcelLien("OAKHURST ONDINE", Encumbrance(Process.LOAN, ("OAKHURST ONDINE",), ("SOME BANK",), (Step("202003090003", date(2020, 3, 9), "230 DEED OF TRUST", OPENS, ("OAKHURST ONDINE",), ("SOME BANK",)),)), True, False)
    fields = ("apn", "address", "unit", "building", "phase", "report", "developer", "current_number", "current_date", "current_owners", "steps", "events", "findings", "reaches_developer", "first_year", "last_year")
    item = ParcelHistory(*[getattr(base, f) for f in fields], liens=base.liens + (prior_loan,), taxes=base.taxes, owner_events=base.owner_events, solar=base.solar)
    brief = unit_brief(item)
    assert [l["owner"] for l in brief["liens"]["open"]] == ["NEXT OWNER", "NEXT OWNER"]
    assert brief["liens"]["openOnPriorOwners"][0]["presumed"].startswith("paid at the sale")
    escrow = escrow_brief(item, _record())
    assert escrow["openLoans"] == 0 and escrow["priorOwnerLoansPresumedPaid"][0]["owner"] == "OAKHURST ONDINE"
    assert "On prior owners, not closed in the cache" in brief_markdown(brief)


def test_the_escrow_brief_says_what_the_association_can_tell(monkeypatch):

    monkeypatch.setattr("asspy.filings.today_for_status", lambda: date(2025, 9, 1))
    brief = escrow_brief(_unit(), _record())
    assert [l["status"] for l in brief["assessmentLiens"]] == ["in default", "closed"]
    assert brief["defaults"][0]["process"] == "assessment lien"
    assert brief["mechanicsLiens"][0]["status"] == "expired" and brief["mechanicsLiens"][0]["unenforceableAfter"] == "2025-03-06"
    assert brief["deathsOnTitle"][0]["owner"] == "NEXT OWNER" and brief["association"]["openPlacedByAssociation"] == 2
    told = "\n".join(brief["tellEscrow"])
    assert "assessment lien of 2025-06-01 stands" in told and "expired unsued on 2025-03-06" in told and "Solar: no lease filing found" in told
    assert "A death record names NEXT OWNER" in told and "does not approve, deny, or assign" in told


def test_recent_filings_list_what_moved_and_what_to_do():
    rows = recent_filings((_unit(),), _record(), date(2025, 1, 1))
    numbers = [row["number"] for row in rows]
    assert numbers == ["202506010010", "202507010016", "202509010011"]
    assert rows[0]["action"].startswith("collections") and "membership record" in rows[1]["action"]
    earlier = recent_filings((_unit(),), _record(), date(2024, 1, 1))
    assert earlier[0]["number"] == "202405010002" and earlier[0]["action"].startswith("new owner")


def test_lifecycle_lookup_and_assessment_liens_and_explain():
    found = lifecycle_lookup((_unit(),), _record(), "2025-0901-0011")
    assert found["found"] and found["where"] == "owner lien" and found["status"] == "in default" and found["address"] == "999 MACON DR"
    chain = lifecycle_lookup((_unit(),), _record(), "202405010002")
    assert chain["where"] == "chain" and chain["to"] == ["NEXT OWNER"]
    assert not lifecycle_lookup((_unit(),), _record(), "999999999999")["found"]
    liens = assessment_liens((_unit(),), _record())
    assert liens["count"] == 2 and liens["open"] == 1 and liens["notOnAUnit"][0]["debtor"] == ["SOMEONE GONE"] and "5650" in liens["law"]
    assert "collection agency" in liens["note"]
    assert explain_filing("389")["process"] == "mechanics lien" and "8460" in explain_filing("389")["law"]
    assert explain_filing("release of mechanics lien")["code"] == "635" and explain_filing("720")["effect"] == "cures"
    assert not explain_filing("zzz")["found"]


def test_the_board_digest_gathers_what_moved_the_liens_to_act_on_and_the_associations_own(monkeypatch):
    from jason.community.briefs import board_digest

    monkeypatch.setattr("asspy.filings.today_for_status", lambda: date(2025, 9, 15))
    digest = board_digest((_unit(),), _record(), date(2025, 1, 1))
    assert digest["since"] == "2025-01-01" and digest["recorded"]["count"] == 3
    assert [row["number"] for row in digest["liens"]["inDefault"]] == ["202506010010"]
    assert digest["liens"]["counts"]["IN_DEFAULT"] == 1 and digest["liens"]["counts"]["EXPIRED"] == 1
    assert [row["opened"] for row in digest["association"]["open"]] == ["2025-06-01"] and digest["association"]["otherAssociations"] == []
    assert digest["solar"] == {"NO_FILING": 1} and digest["more"]["liens"] == "title_watch(attention=True)"


def test_a_transfer_on_death_deed_is_noted_not_read_as_a_death():
    from jason.community.briefs import _event_action

    tod = OwnerEvent("OWNER", "202506130888", date(2025, 6, 13), "697 REVOCABLE TRANSFER ON DEATH DEED",
                     "transfer on death deed: names who takes the unit at the owner's death; revocable, and no death has occurred", ("OWNER",), True, False)
    death = OwnerEvent("OWNER", "202608130001", date(2026, 8, 13), "153 AFFIDAVIT OF DEATH", "death of this owner", ("OWNER",), True, True)
    assert _event_action(tod).startswith("note on the owner's file: a beneficiary is named") and _event_action(death).startswith("membership record")
