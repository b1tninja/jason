"""The incident reader and its grouping, on made-up repair paperwork.

The vendors, amounts, claim numbers, and dates are made up; the street names are the development's so the place reader
finds them, and the building table is a two-row slice.
"""

from __future__ import annotations

from datetime import date

from jason.community.base import BuildingRange
from jason.community.incidents import (
    Cause,
    Element,
    Work,
    EvidenceFolder,
    EvidencePlan,
    PlaceRole,
    Stage,
    group_events,
    is_repair_paperwork,
    places_in,
    read_evidence,
    scope_text,
    split_sites,
)
from jason.community.symbols import Building, Parity, Street
from jason.tasks.incidents import _name_date, dedupe, select_drive

RANGES = (BuildingRange(Building.BLDG_8, Street.WHIMSICAL_LN, 5607, 5651, Parity.ANY),
          BuildingRange(Building.BLDG_2, Street.ENCHANTED_WALK, 3007, 3039, Parity.ODD))
SITE = ("3000 MACON",)
KNOWN = {"5679 WHIMSICAL LN": Building.BLDG_3}
PARCELS = frozenset({"5615 WHIMSICAL LN", "5619 WHIMSICAL LN", "5623 WHIMSICAL LN", "5679 WHIMSICAL LN", "3022 ENCHANTED WALK",
                     "5627 WHIMSICAL LN", "3011 ENCHANTED WALK", "5631 WHIMSICAL LN", "5635 WHIMSICAL LN", "5639 WHIMSICAL LN"})
STREETS = (Street.MACON_DR, Street.ENCHANTED_WALK, Street.WHIMSICAL_LN)


def ev(text: str, title: str = "Invoice 100.pdf", day: date = date(2025, 1, 10), **kw):
    return read_evidence(text, title=title, ref=title, channel="payhoa", day=day, buildings=RANGES, site_words=SITE,
                         known=KNOWN, parcels=PARCELS, streets=STREETS, **kw)


ROOF_LEAK = """Acme Roofing
INVOICE # 101
BILL TO
Mystique Community
3011 Enchanted Walk
JOBSITE ADDRESS
5615 Whimsical Lane
Problem: Tile roof leak above upstairs bathroom
WORK PERFORMED: 1/9/25
1. Removed tiles at the wall flashing and found bird debris blocking water flow.
TOTAL $400.00
NO WARRANTY against leaks. Not responsible for mold-related damage.
Terms and Conditions
Any vandalism is excluded.
"""


def test_places_by_role():
    places = {p.address: p for p in places_in(ROOF_LEAK, RANGES, SITE, KNOWN, PARCELS, STREETS)}
    assert places["5615 WHIMSICAL LN"].role is PlaceRole.JOB and places["5615 WHIMSICAL LN"].building is Building.BLDG_8
    assert places["3011 ENCHANTED WALK"].role is PlaceRole.BILLING
    text = ("Project 4119 - 3022 Enchanted Walk\nunits 5619-5623 Whimsical Lane\nWhimsical Lane, 5627 ATR\n"
            "Service at 3000 Macon Drive\nBldg 5 roof\nfound at 5679 Whimsical\n4643 Whimsical Lane")
    found = {p.key: p for p in places_in(text, RANGES, SITE, KNOWN, PARCELS, STREETS)}
    assert "4119 ENCHANTED WALK" not in found and found["3022 ENCHANTED WALK"].role is PlaceRole.JOB
    assert {"5619 WHIMSICAL LN", "5623 WHIMSICAL LN", "5627 WHIMSICAL LN"} <= set(found)
    assert found["3000 MACON DR"].role is PlaceRole.SITE
    assert found["building 5"].building is Building.BLDG_5
    assert found["5679 WHIMSICAL LN"].building is Building.BLDG_3, "an end unit placed by its parcel"
    assert not found["4643 WHIMSICAL LN"].parcel, "a typo is kept but places nothing"


def test_a_roof_leak_invoice_is_an_incident_at_the_job_not_the_bill_to():
    e = ev(ROOF_LEAK)
    assert e.work is Work.REPAIR and not e.claimed and e.causes[0] is Cause.ROOF_LEAK and Cause.BIRDS in e.causes
    assert Element.ROOF in e.elements and e.stage is Stage.INVOICE
    assert [p.address for p in e.where] == ["5615 WHIMSICAL LN"]
    assert Cause.VANDALISM not in e.causes and "mold" not in scope_text(ROOF_LEAK).lower(), "terms and disclaimers are not scope"
    assert is_repair_paperwork(e, trade=True)


def test_a_claim_letter_is_a_loss_even_from_an_insurer():
    e = ev("Claim Outcome\nClaim Number: 5020001111-1\nDate of Loss: 03/02/2023\nLoss location: Whimsical Lane, 5627\n"
           "The bath overflow damaged the unit below.", title="Claim Outcome Letter.pdf")
    assert e.claimed and e.work is Work.NONE and e.stage is Stage.CLAIM and e.claim == "5020001111-1"
    assert Cause.PLUMBING in e.causes and [p.address for p in e.where] == ["5627 WHIMSICAL LN"]
    assert is_repair_paperwork(e, trade=False)


def test_non_repair_paperwork_is_left_out():
    policy = ev("Policy Number: ABC123\nNamed Insured: Mystique\nPerils: fire, vandalism, windstorm\nPremium $9,000", title="Policy 25-26.pdf")
    assert not is_repair_paperwork(policy, trade=False)
    form = ev("Condo Project Questionnaire\nIs the project subject to flooding? No\nroof", title="Form-1076-Condo-Project-Questionnaire.pdf")
    assert form.excluded and not is_repair_paperwork(form)
    pest = ev("Pro Active Pest Control\nINVOICE\nNational Pest Emergency Poison Control: (800)222-1222\nGeneral pest service, bi-weekly",
              title="Invoice 200.pdf")
    assert pest.work is Work.MAINTENANCE and "(800)" not in pest.snippet


def test_maintenance_and_improvement():
    gutters = ev("Remove all debris from gutter from 8 sections of buildings\nFlush all downspouts\nTotal $1,600.00", title="Invoice 878.pdf")
    assert gutters.work is Work.MAINTENANCE and Element.GUTTER in gutters.elements


def test_events_join_a_proposal_its_contract_and_its_invoice_but_not_the_neighbor():
    rows = [
        ev("Proposal\nJob address: 5615 Whimsical Lane\nRoof leak repair. Install shield flashing.\nTotal $782.00", title="Proposal 12164.pdf",
           day=date(2026, 4, 24), amount_cents=78200, vendor="Acme Roofing"),
        ev(ROOF_LEAK, day=date(2026, 4, 24), amount_cents=40000, vendor="Acme Roofing",
           payment={"key": 1, "day": "2026-04-27", "amountCents": 40000, "payee": "Acme", "memo": ""}),
        ev("INVOICE 2058\nJobsite address\n5615 Whimsical Lane\nInstalled 9-inch shield flashing at the wall pan flashing.\nTotal $782.00",
           title="Invoice 2058.pdf", day=date(2026, 6, 15), amount_cents=78200, vendor="Acme Roofing",
           payment={"key": 2, "day": "2026-08-10", "amountCents": 78200, "payee": "Acme", "memo": ""}),
        ev("INVOICE\nJobsite address\n3022 Enchanted Walk\nRoof leak: replaced cracked tiles.\nTotal $300.00", title="Invoice 7.pdf",
           day=date(2026, 5, 1), vendor="Acme Roofing"),
    ]
    events = group_events(rows)
    assert len(events) == 2
    unit = next(e for e in events if e.addresses == ("5615 WHIMSICAL LN",))
    assert unit.sudden and not unit.claimed and not unit.routine and len(unit.evidence) == 3
    assert unit.estimated_cents == 78200 and unit.paid_cents == 118200 and unit.buildings == (Building.BLDG_8,)
    assert unit.first == date(2026, 4, 24) and unit.last == date(2026, 6, 15)


def test_a_monthly_invoice_listing_many_units_splits_by_unit():
    monthly = ev("Monthly service\nIrrigation line break @5615 Whimsical\nBroken lateral @ 5631 Whimsical\n"
                 "Valve leak @ 5635 Whimsical\nRepair head @ 5639 Whimsical", title="Invoice 55.pdf", vendor="Green Co")
    parts = split_sites(monthly)
    assert len(parts) == 4 and all(len(p.where) == 1 for p in parts)
    assert len(group_events([monthly])) == 4


def test_community_events_do_not_chain_past_a_window():
    first = ev("Irrigation line break at the site\n3000 Macon Drive\nRepair", title="Invoice 1.pdf", day=date(2024, 1, 5), vendor="Green Co")
    later = [ev("Irrigation line break at the site\n3000 Macon Drive\nRepair", title=f"Invoice {m}.pdf", day=date(2024, m, 5), vendor="Green Co")
             for m in (3, 5, 7, 9, 11)]
    events = group_events([first, *later])
    assert len(events) >= 2 and all(e.community_wide for e in events)
    assert all((e.last - e.first).days <= 150 for e in events)


def test_dedupe_keeps_the_payhoa_copy_and_the_earliest_date():
    a = ev(ROOF_LEAK, sha256="abc", payment={"key": 9, "day": "2025-01-12", "amountCents": 40000, "payee": "Acme", "memo": ""})
    b = read_evidence(ROOF_LEAK, title="Invoice 100.pdf", ref="gmail/x.pdf", channel="email", day=date(2025, 1, 9), buildings=RANGES, streets=STREETS, sha256="abc")
    rows = dedupe([b, a])
    assert len(rows) == 1 and rows[0].channel == "payhoa" and rows[0].also == ("gmail/x.pdf",)


def test_drive_selection_honors_private_names_folders_and_size():
    plan = EvidencePlan(folders=(EvidenceFolder("Claims", "claims", confidential=True), EvidenceFolder("Reports", "reports", skip=("Security Patrol/*",))),
                        root_names=("*Estimate*",), private_names=("*MEDICAL*", "*VCA *"), max_bytes=1000)
    pdf = "application/pdf"
    files = [
        {"id": "1", "name": "ATR.pdf", "path": "My Drive/Claims/Bath/ATR.pdf", "mimeType": pdf, "size": 10},
        {"id": "2", "name": "day.pdf", "path": "My Drive/Reports/Security Patrol/day.pdf", "mimeType": pdf, "size": 10},
        {"id": "3", "name": "AAA Repair Estimate.pdf", "path": "My Drive/AAA Repair Estimate.pdf", "mimeType": pdf, "size": 10},
        {"id": "4", "name": "20260810 MEDICAL RECORDS Estimate.pdf", "path": "My Drive/20260810 MEDICAL RECORDS Estimate.pdf", "mimeType": pdf, "size": 10},
        {"id": "5", "name": "EF VCA Invoice.pdf", "path": "My Drive/Claims/EF VCA Invoice.pdf", "mimeType": pdf, "size": 10},
        {"id": "6", "name": "big.pdf", "path": "My Drive/Reports/big.pdf", "mimeType": pdf, "size": 5000},
        {"id": "7", "name": "photo.jpg", "path": "My Drive/Claims/photo.jpg", "mimeType": "image/jpeg", "size": 10},
    ]
    chosen = {f["id"]: f for f in select_drive(files, plan)}
    assert set(chosen) == {"1", "3"} and chosen["1"]["confidential"] and not chosen["3"]["confidential"]


def test_dates_in_file_names():
    assert _name_date("Mystique - 230222 - CO10030-23_5615 Whimsical.pdf") == date(2023, 2, 22)
    assert _name_date("Statement of loss (9.4.26).pdf.PDF") == date(2026, 9, 4)
    assert _name_date("Payment Reminder 2026-01-12T122727.pdf") == date(2026, 1, 12)
    assert _name_date("MYSTIQUE-20220808-SACVALPLU-134749(3107936).pdf") == date(2022, 8, 8)
    assert _name_date("Invoice 905.pdf") is None


def test_one_claim_is_one_event_and_a_units_paperwork_joins_its_loss():
    claim = ev("Claim Number: 1006-00-0001\nDate of Loss: 06/01/2026\nLoss location: 5615 Whimsical Lane\nWater damage.",
               title="Claim Letter.pdf", day=date(2026, 6, 8))
    estimate = ev("Estimate\nClaim Number: 1006-00-0001\nDining room ceiling, walls, flooring", title="Repair Estimate.pdf", day=date(2026, 6, 20))
    door = ev("Proposal\nJob address: 5615 Whimsical Lane\nReplace entry door frame and trim.\nTotal $900.00", title="Proposal 9.pdf",
              day=date(2026, 6, 30), vendor="Door Co")
    events = group_events([claim, estimate, door])
    assert len(events) == 1 and events[0].claimed and events[0].claims == ("1006-00-0001",)


def test_a_service_contract_listing_perils_is_maintenance():
    contract = ev("Landscape Maintenance Agreement\nMonthly service includes removal of storm damaged plants, vandalism clean up, "
                  "and replacing broken sprinkler heads.", title="Landscape Contract.pdf")
    assert contract.work is Work.MAINTENANCE
    leak = ev("CONTRACT AGREEMENT 9001\nJob site: 5615 Whimsical Lane\nRoof leak above the bedroom. Clean debris from wall flashing, "
              "reset tiles; routine monitoring after.", title="Contract 9001.pdf")
    assert leak.work is Work.REPAIR, "a roof leak named in a contract is a repair, not upkeep"


def test_a_maintenance_vendor_sets_the_work_and_a_claim_stays_a_claim():
    from jason.community.incidents import VendorWork, apply_vendor_work

    call = ev(ROOF_LEAK, vendor="SUMMIT ROOFING COMPANY, INC.")
    claim = ev("Claim Number: 5020001111-1\nDate of Loss: 01/09/2025\nRoof leak at 5615 Whimsical Lane", title="Claim.pdf",
               vendor="SUMMIT ROOFING COMPANY, INC.")
    other = ev(ROOF_LEAK, vendor="Other Roofer")
    rules = (VendorWork("Summit Roofing Company", Work.MAINTENANCE, (Element.ROOF,), "the roof repair vendor"),)
    apply_vendor_work([call, claim, other], rules, {"SUMMIT ROOFING COMPANY, INC.": "Summit Roofing Company"})
    assert call.work is Work.MAINTENANCE and call.hint.startswith("repair -> maintenance")
    assert claim.claimed, "the work changes; the claim does not"
    assert other.work is Work.REPAIR
    event = group_events([call])[0]
    assert event.works == (Work.MAINTENANCE,) and event.sudden and not event.routine, "a leak call stays in view as upkeep of a leak"


LOSS_RUN = """Claim Detail Report by Policy - P&C
Policy #:                   900000001
Company:                      Example Insurance Exchange
Valuation Date:             08/19/2024
Claim Number Date of Loss
Claim Status
Claim Type
Loss Information
ZZ000001
02/23/2023
Closed With Pay
Commercial Property
Net Incurred:
$1,107.32
Cause of Loss Description:
Water Damage (Not Frozen Pipes)
Location of Loss:
5627 Whimsical Lane
Sacramento CA 95835
Losses Paid:
$1,063.44
Expenses:
$43.88
Loss Details
Page 4 of 5
Claim Number Date of Loss
Claim Status
Claim Type
Loss Information
ZZ000002
12/27/2022
Closed Without Pay
Commercial Property
Cause of Loss Description:
Other Weather Related
Location of Loss:
5615-5639 Whimsical Ln
Losses Paid:
$0.00
Loss Details
"""


def test_a_loss_run_is_one_claim_row_per_claim():
    from jason.community.incidents import read_loss_run

    claims = read_loss_run(LOSS_RUN)
    assert [c.number for c in claims] == ["ZZ000001", "ZZ000002"]
    first = claims[0]
    assert (first.carrier, first.policy, first.date_of_loss, first.status) == ("Example Insurance Exchange", "900000001", date(2023, 2, 23), "Closed With Pay")
    assert (first.paid_cents, first.expenses_cents, first.location) == (106344, 4388, "5627 Whimsical Lane")
    assert claims[1].paid_cents == 0 and claims[1].cause == "Other Weather Related"
    assert read_loss_run("Invoice 5\nTotal $10.00") == ()


def test_loss_run_claims_join_the_units_paperwork_and_a_street_span_names_both_ends():
    from jason.tasks.incidents import loss_run_evidence

    ctx = {"buildings": RANGES, "site_words": SITE, "known": KNOWN, "parcels": PARCELS, "streets": STREETS}
    rows = loss_run_evidence(LOSS_RUN, ref="drive:Loss Runs.pdf", channel="drive", sha256="abc", ctx=ctx)
    assert [r.claim for r in rows] == ["ZZ000001", "ZZ000002"] and all(r.claimed and r.stage is Stage.CLAIM for r in rows)
    assert [p.address for p in rows[1].where] == ["5615 WHIMSICAL LN", "5639 WHIMSICAL LN"]
    mitigation = ev("Water mitigation invoice\nJob site: 5627 Whimsical Lane\nExtraction and dry out after the overflow\nTotal $4,782.62",
                    title="Mitigation.pdf", day=date(2023, 2, 25), vendor="Dry Co")
    events = group_events([rows[0], mitigation])
    assert len(events) == 1 and events[0].claim_outcomes["ZZ000001"] == {"status": "Closed With Pay", "paidCents": 106344,
                                                                          "carrier": "Example Insurance Exchange"}


def test_claim_papers_seed_their_event_whatever_order_they_arrive():
    estimate = ev("Claim Number: 5020000009-1\nType of Loss: WATER\nEstimate\nstorm", title="ESTIMATE FOR REPAIRS 5020000009-1.pdf",
                  day=date(2023, 2, 23))
    storm = ev("Fallen tree after the storm\nProposal to remove", title="Fallen Tree Proposal.pdf", day=date(2023, 1, 10))
    letter = ev("Claim Number: 5020000009-1-1\nDate of Loss: 02/23/2023\nLoss location: 5627 Whimsical Lane\nSettlement Notice",
                title="Claim Outcome.pdf", day=date(2023, 2, 23))
    owner = ev("Claim number: 030000009-002\nDate of loss: 02/23/2023\n5627 Whimsical Lane\nprimary insurer", title="Primacy.pdf",
               day=date(2023, 2, 23))
    events = group_events([storm, estimate, letter, owner])
    claimed = [e for e in events if e.claimed]
    assert len(claimed) == 1 and set(claimed[0].claims) == {"5020000009", "030000009"}
    assert any(not e.claimed for e in events), "the storm proposal stays its own event"


def test_local_search_finds_the_ledger_minutes_and_email_by_unit_and_claim(tmp_path):
    import json
    import sqlite3

    from jason.tasks.incident_links import event_id, keys_of, local_hits

    row = {"first": "2023-02-23", "last": "2023-06-29", "addresses": ["5627 WHIMSICAL LN"], "buildings": [8], "claims": ["5020000009"],
           "causes": ["plumbing leak or overflow"], "vendors": ["Dry Co"], "claimed": True, "sudden": True, "work": ["repair"]}
    keys = keys_of(row)
    assert keys["units"] == [{"address": "5627 WHIMSICAL LN", "short": "5627 Whimsical"}] and keys["claims"] == ["5020000009"]
    assert event_id(row).startswith("2023-02-23:5627-whimsical-ln:")
    (tmp_path / "gmail").mkdir()
    (tmp_path / "gmail" / "correspondence.json").write_text(json.dumps([
        {"messageId": "m1", "at": "2023-03-01T10:00:00", "subject": "Leak at 5627 Whimsical", "domains": ["dryco.test"], "attachments": []},
        {"messageId": "m2", "at": "2025-01-01T10:00:00", "subject": "5627 Whimsical parking", "domains": [], "attachments": []}]))
    (tmp_path / "payhoa").mkdir()
    with sqlite3.connect(tmp_path / "payhoa" / "ledger.db") as db:
        db.execute("create table entries (day, account, description, memo, vendor, debit, credit)")
        db.execute("insert into entries values ('2023-03-10', 'Repairs', 'DRY CO mitigation', '', 'DRY CO', 478262, 0)")
        db.execute("insert into entries values ('2023-03-10', 'Landscaping', 'Green Co', '', 'GREEN CO', 1000, 0)")
    hits = local_hits(tmp_path, keys)
    assert {(h["source"], h["id"]) for h in hits} == {("email header", "m1"), ("ledger", "2023-03-10:DRY CO mitigation")}


def test_standing_against_the_master_deductible():
    from jason.community.incidents import ClaimStanding

    def leak(amount):
        return ev("INVOICE\nJobsite address\n5615 Whimsical Lane\nRoof leak repair\nTotal", title="Invoice 1.pdf", amount_cents=amount)

    assert group_events([leak(1_500_000)])[0].standing(1_000_000) is ClaimStanding.CANDIDATE
    assert group_events([leak(50_000)])[0].standing(1_000_000) is ClaimStanding.UNDER_DEDUCTIBLE
    assert group_events([leak(None)])[0].standing(1_000_000) is ClaimStanding.COST_UNKNOWN
    upkeep = ev("Monthly service\nClean all gutters\nTotal $1,600.00", title="Invoice 2.pdf", amount_cents=160000)
    assert group_events([upkeep])[0].standing(1_000_000) is ClaimStanding.NONE
    claim = ev("Claim Number: 5020000001-1\nDate of Loss: 01/09/2025\nRoof leak at 5615 Whimsical Lane", title="Claim.pdf")
    assert group_events([claim])[0].standing(1_000_000) is ClaimStanding.CLAIMED


def test_the_specification_carries_the_master_deductible():
    from jason.community import load_mystique

    master = load_mystique().insurance().master()
    assert master is not None and master.deductible_cents == 1_000_000
