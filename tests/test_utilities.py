"""Utility bills: the SMUD and City parsers, the tariff, abnormal usage, the forecast, and the PayHOA payment audit."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from jason.community.city_utility import SacramentoUtilities, city_due, inches
from jason.community.smud_utility import CITS_0, Smud, estimate, max_kw, smud_due, tou_usage
from jason.community.symbols import Building, Utility
from jason.community.utility import (
    Charge,
    ChargeKind,
    Service,
    UsageUnit,
    UtilityAccount,
    UtilityBill,
    dedupe_bills,
    service_points,
    split_days,
)
from jason.community.utility_analysis import UsagePoint, anomalies, fixed_growth
from jason.community.utility_payments import (
    Attachment,
    audit,
    expected_split,
    group_payments,
    identify,
    match_payments,
)
from jason.community.utility_store import UtilityStore

SMUD_TEXT = """Your Electric Bill
Account Number: 3547597
Bill Issue Date: 01/28/26
Location: 3000 MACON DR BLDG BOOSTER
PUMP UNIT 0
Bill Period: 12/09/25 - 01/08/26 (31 Days)
Cycle: 04 | Location Number: 2512665 | Rate: C&I TOD Secondary 0-20 kW
Rate: C&I TOD Secondary 0-20 kW
Total Amount Due:
$584.09
Meter Summary

Meter
Usage
Type
3149772
1,580
kWh
3149772
3
kW Maximum
3149772
0
kW Peak
Electricity Charges

Item
Usage
Type
Rate
Amount
Power Factor
1.0000
Electricity Usage
693
Non-Summer Off Peak kWh @
0.137700
95.43
Electricity Usage
186
Non-Summer Off Peak kWh @
0.134600
25.04
Electricity Usage (4pm-9pm / M-F)
175
Non-Summer Peak kWh @
0.153200
26.81
Electricity Usage (4pm-9pm / M-F)
54
Non-Summer Peak kWh @
0.154000
8.32
Electricity Usage (9am-4pm)
360 NonSum Off Peak Saver kWh @
0.129500
46.62
Electricity Usage (9am-4pm)
113 NonSum Off Peak Saver kWh @
0.124400
14.06
Maximum Demand Charge
3
Maximum kW @
1.546000
3.44
Maximum Demand Charge
3
Maximum kW @
2.389000
1.85
System Infrastructure Fixed Charge*
29.90
System Infrastructure Fixed Charge*
10.84
Sacramento City Tax*
19.67
State Surcharge*
0.47
A) TOTAL ELECTRIC SERVICE CHARGES/CREDITS
$282.45
"""

CITY_TEXT = """City of Sacramento
Utility Service Bill
February 02, 2026
MYSTIQUE COMMUNITY ASSOCIATION
Amount
Paid
Account
Number
Total Amount
Due
Current Charges
0 WHIMSICAL LN
4664672921
$22.08
$11.04
Service Address:
0 WHIMSICAL LN - Common Area
201-1170-025-0024
Service from 1/3/26 - 2/2/26
Storm Drainage - 1996 Fee
8.79
Flat charge for 4,558 sq ft parcel
Storm Drainage - 2022 Fee
2.25
Storm Drainage Property Related Fee - Common Area
Subtotal
$11.04
Current Charges - Due 2/23/26
$11.04
"""


def test_smud_bill_parses_and_reconciles() -> None:
    bill = Smud().parse(SMUD_TEXT, account="3547597", bill_id="x")
    assert bill.provider is Utility.SMUD
    assert (bill.period_start, bill.period_end, bill.bill_date) == (date(2025, 12, 9), date(2026, 1, 8), date(2026, 1, 28))
    assert bill.total_cents == 28245 and bill.reconciles
    assert bill.due_cents == 58409 and bill.payable_cents == 58409
    assert bill.usage(Service.ELECTRIC, UsageUnit.KWH) == 1580
    assert max_kw(bill) == 3
    assert {r.register for r in bill.reads if r.unit is UsageUnit.KW} == {"kW Maximum", "kW Peak"}
    assert all(r.size == "" for r in bill.reads)
    kinds = bill.by_kind()
    assert kinds[ChargeKind.TAX] == 1967 and kinds[ChargeKind.SURCHARGE] == 47 and kinds[ChargeKind.FIXED] == 4074
    assert identify(SMUD_TEXT) == (Utility.SMUD, "3547597")


def test_smud_tariff_reproduces_the_bill_across_the_january_change() -> None:
    bill = Smud().parse(SMUD_TEXT, account="3547597")
    assert CITS_0.price("fixed", date(2025, 12, 31)) == 40.30 and CITS_0.price("fixed", date(2026, 1, 1)) == 42.00
    assert CITS_0.provisional("fixed", date(2028, 6, 1)) and not CITS_0.provisional("fixed", date(2027, 6, 1))
    assert split_days(date(2025, 12, 9), date(2026, 1, 8), [date(2026, 1, 1)]) == [
        (date(2025, 12, 9), date(2025, 12, 31), 23), (date(2026, 1, 1), date(2026, 1, 8), 8)]
    est = estimate(CITS_0, bill.period_start, bill.period_end, tou_usage(bill), max_kw(bill))
    # SMUD splits the kWh at a price change by the meter's interval data; prorating by days comes within a dollar.
    assert abs(est.total_cents - bill.total_cents) <= 100


def test_smud_no_payment_due_is_zero() -> None:
    assert smud_due("Total Amount Due:\nNO PAYMENT DUE\n") == 0
    assert smud_due("nothing here") is None


def test_city_bill_parses_services_parcel_and_due() -> None:
    bill = SacramentoUtilities().parse(CITY_TEXT, account="4664672921")
    assert bill.provider is Utility.CITY_OF_SACRAMENTO
    assert bill.bill_date == date(2026, 2, 2) and bill.parcel == "201-1170-025-0024"
    assert bill.total_cents == 1104 and bill.reconciles
    assert bill.due_cents == 2208 and city_due(CITY_TEXT) == 2208
    assert bill.by_service() == {Service.STORM_DRAINAGE: 1104}
    assert {c.label for c in bill.charges} == {"Flat charge for 4,558 sq ft parcel", "Storm Drainage Property Related Fee - Common Area"}
    assert all(c.kind is ChargeKind.FIXED for c in bill.charges)
    assert identify(CITY_TEXT) == (Utility.CITY_OF_SACRAMENTO, "4664672921")
    assert inches("4.0") == '4"' and inches("1.50") == '1.5"'


def _bill(account: str, day: date, total: int, *, provider: Utility = Utility.SMUD, due: int | None = None, source: str = "",
          charges: tuple[Charge, ...] = ()) -> UtilityBill:
    charges = charges or (Charge(Service.ELECTRIC, ChargeKind.USAGE, "use", total),)
    return UtilityBill(provider, account, f"{account}-{day}", day, total, day.replace(day=1), day, charges, (), "", "", "",
                       source or f"D:/bills/{account}/{day}.pdf", (), due)


def test_dedupe_prefers_the_portal_copy() -> None:
    portal = _bill("1", date(2026, 1, 28), 500, source="D:/code/smud/data/bills/1/2026-01-28.pdf")
    attached = _bill("1", date(2026, 1, 28), 500, source="D:/code/jason/data/payhoa/attachments/9/1-document-0.pdf")
    assert dedupe_bills([attached, portal]) == [portal]


def test_service_points_and_meter_replacement() -> None:
    from jason.community.utility import MeterRead
    from jason.tasks.utilities import service_map

    old = UtilityBill(Utility.SMUD, "3547597", "a", date(2025, 11, 24), 100, date(2025, 10, 1), date(2025, 10, 31),
                      (Charge(Service.ELECTRIC, ChargeKind.USAGE, "u", 100),), (MeterRead("2650964", Service.ELECTRIC, UsageUnit.KWH, 10),),
                      service_address="3000 MACON DR")
    new = UtilityBill(Utility.SMUD, "3547597", "b", date(2025, 12, 26), 100, date(2025, 11, 1), date(2025, 11, 30),
                      (Charge(Service.ELECTRIC, ChargeKind.USAGE, "u", 100),), (MeterRead("3149772", Service.ELECTRIC, UsageUnit.KWH, 10),),
                      service_address="3000 MACON DR")
    points = service_points([old, new])
    assert [p.meter for p in points] == ["2650964", "3149772"]

    class Spec:
        def utility_accounts(self):
            return (UtilityAccount(Utility.SMUD, "3547597", "Pump room"), UtilityAccount(Utility.SMUD, "6883021", "Building 1", Building.BLDG_1))

    rows = {r["account"]: r for r in service_map([old, new], Spec())}
    assert rows["3547597"]["label"] == "Pump room"
    assert any("replaced by 3149772" in n for n in rows["3547597"]["notes"])
    assert rows["6883021"]["notes"] == ["in the specification, but no bills on disk"]


def _point(end: date, usage: float, days: int = 30) -> UsagePoint:
    from datetime import timedelta

    return UsagePoint(Utility.CITY_OF_SACRAMENTO, "1", Service.WATER_IRRIGATION, str(end), end - timedelta(days=days - 1), end, usage,
                      UsageUnit.CUBIC_FEET, 0)


def test_anomalies_flag_a_spike_and_explain_a_catch_up_read() -> None:
    key = (Utility.CITY_OF_SACRAMENTO, "1", Service.WATER_IRRIGATION)
    spike = [_point(date(y, 7, 15), 30000) for y in (2022, 2023, 2024)] + [_point(date(2025, 7, 15), 90000)]
    found = anomalies({key: spike})
    assert len(found) == 1 and found[0].kind.startswith("high usage") and round(found[0].ratio) == 3

    months = [date(2025, m, 15) for m in range(1, 13)]
    history = [_point(d, 3000) for d in months[:6]] + [_point(d, 0) for d in months[6:10]] + [_point(months[10], 15000)]
    kinds = [a.kind for a in anomalies({key: history})]
    assert kinds[0].startswith("catch-up read after 4 bill(s)")
    assert kinds[1].startswith("no usage")


def test_fixed_growth_is_flat_for_a_flat_fee() -> None:
    bills = [_bill("9", date(y, m, 2), 879, provider=Utility.CITY_OF_SACRAMENTO,
                   charges=(Charge(Service.STORM_DRAINAGE, ChargeKind.FIXED, "Flat charge", 879, period_start=date(y, m, 1), period_end=date(y, m, 2)),))
             for y in (2023, 2024, 2025) for m in (1, 4, 7, 10)]
    assert fixed_growth(bills) == {("9", "Flat charge"): 0.0}


def test_store_round_trips_a_bill(tmp_path: Path) -> None:
    bill = Smud().parse(SMUD_TEXT, account="3547597", source=str(tmp_path / "a.pdf"))
    with UtilityStore(tmp_path / "u.db") as store:
        store.save(bill, size=1, mtime=2.0)
        assert store.known() == {bill.source: (1, 2.0)}
    with UtilityStore(tmp_path / "u.db", readonly=True) as store:
        (back,) = store.bills()
    assert back == bill


def _tx(ident: int, day: str, amount: int, *, category: int = 1, parent: int | None = None, description: str = "ORIG CO NAME:SMUD",
        attachments: list | None = None) -> dict:
    return {"id": ident, "parentId": parent, "transactionDate": f"{day} 00:00:00", "amount": amount, "categoryId": category,
            "description": description, "attachments": attachments or []}


LINES = {Service.ELECTRIC: "Electricity (SMUD)", Service.STORM_DRAINAGE: "Storm Drains", Service.STREET_SWEEPING: "Street Sweeping"}
CATEGORIES = {1: "Electricity (SMUD)", 2: "City of Sacramento Utilities", 3: "Storm Drains", 4: "Street Sweeping"}


def test_payments_group_split_rows_and_match_by_amount_due() -> None:
    city = "ORIG CO NAME:CITY OF SACRAMEN"
    txs = [
        _tx(10, "2026-02-02", 58409, attachments=[{"id": 1, "filename": "document-0.pdf"}]),
        _tx(11, "2026-02-04", 58409),
        _tx(20, "2026-05-21", 564, category=4, parent=99, description=city),
        _tx(21, "2026-05-21", 6224, category=3, parent=99, description=city),
        _tx(30, "2026-06-10", 6788, category=2, description=city),
        _tx(40, "2026-06-10", 5000, description="COSTCO"),
    ]
    payments = group_payments(txs, CATEGORIES)
    assert [p.key for p in payments] == [10, 11, 99, 30]
    split = next(p for p in payments if p.key == 99)
    assert split.amount_cents == 6788 and split.split

    smud_bills = [
        _bill("3547597", date(2026, 1, 28), 28245, due=58409),
        _bill("3547597", date(2026, 2, 27), 26131, due=0),
    ]
    sweep = (Charge(Service.STORM_DRAINAGE, ChargeKind.FIXED, "flat", 6224), Charge(Service.STREET_SWEEPING, ChargeKind.FIXED, "sweep", 564))
    city_bills = [
        _bill("3100000065", date(2026, 5, 18), 6788, provider=Utility.CITY_OF_SACRAMENTO, due=6788, charges=sweep),
        _bill("3100000065", date(2026, 6, 1), 6788, provider=Utility.CITY_OF_SACRAMENTO, due=6788, charges=sweep),
    ]
    matched = match_payments(payments, smud_bills + city_bills)
    assert [b.bill_date for b in matched[10]] == [date(2026, 1, 28)]
    assert 11 not in matched
    assert [b.bill_date for b in matched[99]] == [date(2026, 5, 18)]
    assert [b.bill_date for b in matched[30]] == [date(2026, 6, 1)]
    assert expected_split(matched[30], LINES) == {"Storm Drains": 6224, "Street Sweeping": 564}

    rows = {r["key"]: r for r in audit(payments, smud_bills + city_bills, LINES)}
    assert any(f.startswith("paid twice") for f in rows[11]["findings"])
    assert any("the credit from the second payment" in f for f in rows[11]["findings"])
    assert rows[99]["split"] == "matches the bills" and rows[99]["findings"] == ["no attachment"]
    assert rows[30]["split"] == "not split"
    # The attachment on 10 was never read, so it is not a bill.
    assert any("is not a smud bill" in f for f in rows[10]["findings"])


def test_a_catch_up_payment_pays_two_bills_of_one_account() -> None:
    payments = group_payments([_tx(1, "2026-02-02", 300)], CATEGORIES,
                              {5: Attachment(5, 1, "x.pdf")})
    bills = [_bill("1", date(2025, 12, 26), 100), _bill("1", date(2026, 1, 28), 200)]
    assert [b.total_cents for b in match_payments(payments, bills)[1]] == [100, 200]


def test_misfiled_names_a_file_holding_an_older_bill() -> None:
    from jason.tasks.utilities import misfiled

    bill = _bill("7690555178", date(2026, 6, 17), 1388, provider=Utility.CITY_OF_SACRAMENTO,
                 source="D:/code/i-doxs/data/bills/7690555178/2026-08-19_7690555178-2026-08-19-1388.pdf")
    (row,) = misfiled([bill])
    assert row["namedDate"] == "2026-08-19" and row["billDate"] == "2026-06-17"


def test_the_specification_names_the_utility_accounts() -> None:
    from jason.community import mystique

    spec = mystique()
    accounts = {(a.utility, a.account): a for a in spec.utility_accounts()}
    assert accounts[(Utility.SMUD, "1000003")].building is Building.BLDG_3
    assert spec.utility_budget_lines()[Service.STREET_SWEEPING] == "Street Sweeping"


def test_spread_carries_a_catch_up_read_over_the_unread_months() -> None:
    from jason.community.utility_forecast import spread

    points = [_point(date(2026, 1, 30), 0), _point(date(2026, 3, 1), 0), _point(date(2026, 3, 31), 9000)]
    ((start, end, per_day),) = spread(points)
    assert (start, end) == (date(2026, 1, 1), date(2026, 3, 31)) and round(per_day) == 100


def test_usage_profile_takes_each_months_median_over_recent_years() -> None:
    from jason.community.utility_forecast import usage_profile

    points = [_point(date(y, 7, 31), usage, days=31) for y, usage in ((2023, 3100), (2024, 6200), (2025, 4650))]
    profile = usage_profile(points)
    assert round(profile[7].per_day) == 150 and profile[7].years == (2023, 2024, 2025)
    # A month no year covers takes the median of the covered months.
    assert profile[1].per_day == profile[7].per_day


def test_monthly_fixed_keeps_repeated_lines_sums_prorated_pieces_and_drops_closed_accounts() -> None:
    from jason.community.utility_forecast import monthly_fixed

    def fixed(label: str, cents: int, service: Service = Service.FIRE_SERVICE) -> Charge:
        return Charge(service, ChargeKind.FIXED, label, cents)

    city = Utility.CITY_OF_SACRAMENTO
    live = _bill("1", date(2026, 9, 1), 0, provider=city, charges=(
        fixed("Water - 1 8 inch tap", 16085), fixed("Water - 1 8 inch tap", 16085),
        fixed("Street Sweeping Commercial (for 28 days)", 545, Service.STREET_SWEEPING),
        fixed("Street Sweeping Commercial (for 1 days)", 19, Service.STREET_SWEEPING),
    ))
    closed = _bill("2", date(2023, 1, 24), 0, provider=city, charges=(fixed("Flat charge", 9258, Service.STORM_DRAINAGE),))
    found = monthly_fixed([live, closed])
    assert {k[2:]: v[0] for k, v in found.items()} == {
        ("Water - 1 8 inch tap", 0): 16085, ("Water - 1 8 inch tap", 1): 16085, ("Street Sweeping Commercial", 0): 564}


def test_water_forecast_prices_predicted_usage_and_applies_a_named_scenario() -> None:
    from jason.community.city_utility import WATER_2019
    from jason.community.utility import MeterRead
    from jason.community.utility_forecast import forecast_water

    city = Utility.CITY_OF_SACRAMENTO
    bills = []
    for year in (2024, 2025):
        for month in range(1, 13):
            start = date(year, month, 1)
            end = date(year, month, 28)
            bills.append(UtilityBill(city, "9", f"{year}{month}", end, 0, start, end,
                                     (Charge(Service.WATER_DOMESTIC, ChargeKind.USAGE, "use", 0, 2800, UsageUnit.CUBIC_FEET, period_start=start, period_end=end),
                                      Charge(Service.WATER_DOMESTIC, ChargeKind.FIXED, "Base service charge", 31972, period_start=start, period_end=end)),
                                     (MeterRead("m", Service.WATER_DOMESTIC, UsageUnit.CUBIC_FEET, 2800),)))
    lines = {line.month: line for line in forecast_water(bills, 2027, water_price=WATER_2019, water_increase=0.1)}
    june, july = lines["2027-06"], lines["2027-07"]
    assert june.usage == 3000 and june.usage_cents == round(3000 * 1.4587) and june.fixed_cents == 31972
    assert july.usage_cents == round(3100 * 1.4587 * 1.1) and july.fixed_cents == round(31972 * 1.1)
