from jason.community.recorder import Sacramento
from jason.community.tax import (
    SacramentoCountyTax,
    DirectLevy,
    TaxBill,
    TaxLevy,
    account_page,
    ad_valorem_cents,
    bill_page,
    direct_levies,
    follows_reassessment,
    parse_bill,
    parcel_number,
    tax_split,
)

PATH = "/Taxsys-GovHub/v0/items/sacramento-ca:gsgx_property_tax:parents:2bf3d4de-8b5f-11f0-a634-eb87a177e0c1"


def _hit():
    return {
        "results": [
            {
                "hits": [
                    {
                        "child_groups": [
                            {
                                "children": [
                                    {
                                        "external_id": "20250312132",
                                        "display_name": "2025 Secured Annual Bill #20250312132",
                                    },
                                    {
                                        "external_id": "20240409885",
                                        "display_name": "2024 Secured Annual Bill #20240409885",
                                    },
                                ]
                            }
                        ],
                        "custom_parameters": {
                            "external_type": "Secured",
                            "public_url": "/public/property_tax/accounts/201-1170-018-0000",
                        },
                        "display_name": "3000 MACON DR SACRAMENTO, CA 95835",
                        "external_id": "201-1170-018-0000",
                        "objectID": PATH,
                    }
                ]
            }
        ]
    }


def test_search_reads_the_account_and_its_bills():
    def fetch(url, body):
        assert url.startswith("https://ng9exqz0n7-dsn.algolia.net/1/indexes/*/queries?")
        assert "x-algolia-application-id=NG9EXQZ0N7" in url
        request = body["requests"][0]
        assert request["indexName"] == "ca-sacramento.gsgx_property_tax"
        assert request["query"] == "3000 macon dr"
        return _hit()

    found = SacramentoCountyTax().search("3000 macon dr", fetch=fetch)
    assert len(found) == 1
    account = found[0]
    assert account.apn == "201-1170-018-0000"
    assert account.address == "3000 MACON DR SACRAMENTO, CA 95835"
    assert account.kind == "Secured"
    assert account.path == PATH
    assert account.bills[0].number == "20250312132"
    assert account.bills[0].year == 2025
    assert account.amount_cents is None


def test_account_loads_the_payable_for_a_parcel_number():
    def search_fetch(url, body):
        assert body["requests"][0]["query"] == "201-1170-018-0000"
        return _hit()

    def payable_fetch(url):
        assert url == (
            "https://govhub.com/svc/payables/v0/"
            "Taxsys-GovHub%2Fv0%2Fitems%2Fsacramento-ca%3Agsgx_property_tax%3Aparents%3A"
            "2bf3d4de-8b5f-11f0-a634-eb87a177e0c1"
        )
        return {
            "amount": "7.00",
            "description": "Current Owner (August 11, 2016 - Present)",
            "external_id": "201-1170-018-0000",
            "custom_parameters": {"assessee": "Current Owner", "external_type": "Account"},
        }

    account = SacramentoCountyTax().account(
        "20111700180000",
        fetch=search_fetch,
        payable_fetch=payable_fetch,
    )
    assert account is not None
    assert account.apn == "201-1170-018-0000"
    assert account.amount_cents == 700
    assert account.assessee == "Current Owner"
    assert account.description.startswith("Current Owner")
    assert len(account.bills) == 2


def test_account_miss_stays_a_miss():
    def fetch(url, body):
        return {"results": [{"hits": []}]}

    assert SacramentoCountyTax().account("201-1170-018-0000", fetch=fetch, payable_fetch=lambda url: {}) is None


def test_parcel_number_inserts_the_county_dashes():
    assert parcel_number("20111700180000") == "201-1170-018-0000"
    assert parcel_number("201-1170-018-0000") == "201-1170-018-0000"


def test_sacramento_tax_is_the_county_client():
    assert Sacramento.tax().name == "Sacramento"


BILL = """
<h2>2025&zwj; Secured Annual Bill #20250312119</h2>
<table class="assessed-values-table">
  <tr><th>Land</th><th>Improvements</th><th>Personal Property</th><th>Exemptions</th><th>Net Assessed Value</th></tr>
  <tr><td>$87,041</td><td>$145,071</td><td>$0</td><td>-$7,000</td><td>$225,112</td></tr>
</table>
<table>
  <tr><th>Taxing authority</th><th>Rate</th><th>Taxable</th><th>Tax</th></tr>
  <tr><th>Countywide Tax (Secured)</th><td>1.00000000%</td><td>$225,112.00</td><td>$2,251.12</td></tr>
  <tr><th>GRANT JT HIGH GOB</th><td>0.02910000%</td><td>$225,112.00</td><td>$65.51</td></tr>
  <tr><th>Total Ad Valorem Taxes</th><td>1.16870000%</td><td>$2,630.88</td></tr>
</table>
<table>
  <tr><th>Levying authority</th><th>Code</th><th>Phone Number</th><th>Amount</th></tr>
  <tr><th>SAFCA O &amp; M ASSESSMENT DIST #1</th><td>0168</td><td>(916) 874-7606</td><td>$8.42</td></tr>
  <tr><th>Total Direct Charges and Special Assessments</th><td>$847.64</td></tr>
</table>
<table>
  <tr><th>Total</th><td>$3,478.52</td></tr>
  <tr><th>Total payments made</th><td>$3,478.52</td></tr>
  <tr><th>Balance due</th><td>$0.00</td></tr>
</table>
<div class='col label'>Tax Rate Area:</div><div class='col value'>003-435</div>
<div class='col label'>Tax Rate:</div><div class='col value'>1.16870000%</div>
<div class='col label'>Fixtures:</div><div class='col value'>$0</div>
<div class='col label'>homeowners exemption:</div><div class='col value'>$7,000</div>
<div class='col label'>other exemption:</div><div class='col value'>$0</div>
"""


def test_parse_bill_keeps_value_and_levies():
    bill = parse_bill(BILL)
    assert bill.number == "20250312119"
    assert bill.year == 2025
    assert bill.land_cents == 8_704_100
    assert bill.improvement_cents == 14_507_100
    assert bill.fixture_cents == 0
    assert bill.homeowner_exemption_cents == 700_000
    assert bill.other_exemption_cents == 0
    assert bill.net_assessed_cents == 22_511_200
    assert bill.tax_rate_area == "003-435"
    assert bill.rate_e8 == 116_870_000
    assert bill.ad_valorem_cents == 263_088
    assert bill.direct_cents == 84_764
    assert bill.total_cents == 347_852
    assert bill.balance_cents == 0
    assert bill.levies[0] == TaxLevy(
        "ad_valorem",
        "Countywide Tax (Secured)",
        225_112,
        rate_e8=100_000_000,
        taxable_cents=22_511_200,
    )
    assert bill.levies[1].name == "GRANT JT HIGH GOB"
    assert bill.levies[1].rate_e8 == 2_910_000
    assert bill.levies[-1] == TaxLevy("direct", "SAFCA O & M ASSESSMENT DIST #1", 842, code="0168")
    # The 1% countywide line is 1% of the net assessed value.
    assert bill.levies[0].amount_cents == bill.net_assessed_cents // 100


def _year(year: int, land: int, improvements: int, net: int, ad: int, directs: tuple[TaxLevy, ...]) -> TaxBill:
    return TaxBill(
        number=str(year),
        name=f"{year} Secured Annual Bill #{year}",
        year=year,
        land_cents=land,
        improvement_cents=improvements,
        homeowner_exemption_cents=700_000,
        net_assessed_cents=net,
        ad_valorem_cents=ad,
        direct_cents=sum(levy.amount_cents for levy in directs),
        total_cents=ad + sum(levy.amount_cents for levy in directs),
        levies=(
            TaxLevy("ad_valorem", "Countywide Tax (Secured)", net // 100, rate_e8=100_000_000, taxable_cents=net),
            *directs,
        ),
    )


def test_direct_charges_do_not_follow_the_reassessment():
    # 5651 Whimsical, 2016 factored value and 2017 enrollment after the sale.
    before = _year(
        2016,
        5_411_200,
        9_729_300,
        14_440_500,
        172_694,
        (
            TaxLevy("direct", "SAFCA O & M ASSESSMENT DIST #1", 150, code="0168"),
            TaxLevy("direct", "N. NATOMAS BASINS 1 & 2 & 3", 32_768, code="0672"),
        ),
    )
    after = _year(
        2017,
        7_500_000,
        12_500_000,
        19_300_000,
        226_176,
        (
            TaxLevy("direct", "SAFCA O & M ASSESSMENT DIST #1", 150, code="0168"),
            TaxLevy("direct", "N. NATOMAS BASINS 1 & 2 & 3", 32_788, code="0672"),
        ),
    )
    bills = (before, after)
    assert tax_split(before).total_cents == before.total_cents
    assert tax_split(after).price_cents == 226_176
    assert tax_split(after).fixed_cents == 32_938
    assert tax_split(after).enrolled_cents == 20_000_000
    charges = {levy.code: levy for levy in direct_levies(bills)}
    assert charges["0168"].same_each_year
    assert follows_reassessment(charges["0168"], bills) is False
    assert follows_reassessment(charges["0672"], bills) is False


def test_a_charge_that_scales_with_value_follows_the_reassessment():
    before = _year(2016, 5_411_200, 9_729_300, 14_440_500, 172_694, (TaxLevy("direct", "Scaled", 32_768, code="9999"),))
    after = _year(2017, 7_500_000, 12_500_000, 19_300_000, 226_176, (TaxLevy("direct", "Scaled", 43_290, code="9999"),))
    levy = direct_levies((before, after))[0]
    assert isinstance(levy, DirectLevy)
    assert follows_reassessment(levy, (before, after)) is True


def test_one_percent_of_net_value_is_the_countywide_line():
    assert ad_valorem_cents(22_511_200, 100_000_000) == 225_112
    assert ad_valorem_cents(22_511_200, 116_870_000) == 263_088


def test_bill_page_uses_the_iframe_host():
    public = (
        "https://county-taxes.net/sacramento/property-tax/"
        "TOKEN/bills/2ADC2330-8B5F-11F0-89A4-D5F3C6C7CF39"
    )
    assert bill_page(public).startswith(
        "https://county-taxes.net/iframe-taxsys/sacramento-ca.county-taxes.com/govhub/property-tax/"
    )


def test_account_page_is_the_iframe_for_the_payable_path():
    assert account_page(PATH).endswith(
        "c2FjcmFtZW50by1jYTpnc2d4X3Byb3BlcnR5X3RheDpwYXJlbnRzOjJiZjNkNGRlLThiNWYtMTFmMC1hNjM0LWViODdhMTc3ZTBjMQ=="
    )
