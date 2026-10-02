from datetime import date

from jason.community.recorder import ChainStep, Conveyance, FiledInstrument
from jason.community.standing import owner_events, tax_standing
from jason.community.tax import TaxBill


def _bill(year, total, balance=0):
    return TaxBill(str(year), f"{year} Secured Annual Bill", year=year, total_cents=total, payments_cents=total - balance, balance_cents=balance)


def test_tax_standing_reads_due_delinquent_and_gaps():
    paid = tax_standing([_bill(2022, 100), _bill(2023, 100), _bill(2024, 100)])
    assert paid.status == "paid" and paid.power_to_sell is None
    due = tax_standing([_bill(2023, 100), _bill(2024, 100, 100)])
    assert due.status == "due" and due.unpaid == ((2024, 100),)
    late = tax_standing([_bill(2021, 100, 40), _bill(2022, 100), _bill(2023, 100, 100)])
    assert late.status == "delinquent" and late.delinquent == ((2021, 40),) and late.unpaid == ((2023, 100),)
    assert late.oldest_delinquent == 2021 and late.power_to_sell == date(2027, 7, 1)
    gap = tax_standing([_bill(2017, 100), TaxBill("x", "2019 Secured Annual Bill", year=2019), _bill(2023, 100)])
    assert gap.status == "gap in the bills" and gap.missing_years == (2018, 2019, 2020, 2021, 2022)
    assert tax_standing([]).first_year is None


def test_owner_events_name_the_decedent_and_the_survivor():
    steps = (
        ChainStep(Conveyance("202002280100", date(2020, 2, 28), ("WATT COMMUNITIES AT MYSTIQUE LLC",), ("TARNWICK HAROLD R SR TRUSTEE", "TARNWICK EDNA M TRUSTEE"))),
    )
    cache = {
        "TARNWICK HAROLD R SR TRUSTEE": [
            FiledInstrument("202103010001", date(2021, 3, 1), "death", ("TARNWICK HAROLD R SR",), ("TARNWICK EDNA M",), (), "153", "AFFIDAVIT OF DEATH"),
            FiledInstrument("201901010001", date(2019, 1, 1), "", ("TARNWICK HAROLD R SR",), ("TARNWICK EDNA M",), (), "466", "POWER OF ATTORNEY"),
        ],
        "TARNWICK EDNA M TRUSTEE": [
            FiledInstrument("202103010001", date(2021, 3, 1), "death", ("TARNWICK HAROLD R SR",), ("TARNWICK EDNA M",), (), "153", "AFFIDAVIT OF DEATH"),
        ],
    }
    found = owner_events(lambda name: cache.get(name, []), steps, current_owners=steps[0].conveyance.grantees)
    assert [(e.number, e.kind, e.during_tenure, e.still_on_title) for e in found] == [
        ("201901010001", "power of attorney", False, False),
        ("202103010001", "death of this owner", True, True),
    ]
