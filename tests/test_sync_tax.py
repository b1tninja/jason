from jason.community.tax import SacramentoCountyTax, TaxBill
from jason.community.tax_store import TaxStore
from jason.tasks.sync_tax import sync_tax

PATH = "/Taxsys-GovHub/v0/items/sacramento-ca:gsgx_property_tax:parents:2bf3d4de-8b5f-11f0-a634-eb87a177e0c1"


def _account(amount: str = "7.00") -> dict:
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
                                    }
                                ]
                            }
                        ],
                        "custom_parameters": {"external_type": "Secured", "public_url": "/public/property_tax/accounts/201-1170-018-0000"},
                        "display_name": "3000 MACON DR SACRAMENTO, CA 95835",
                        "external_id": "201-1170-018-0000",
                        "objectID": PATH,
                    }
                ]
            }
        ]
    }


def _payable(amount: str = "7.00") -> dict:
    return {
        "amount": amount,
        "description": "Current Owner (August 11, 2016 - Present)",
        "custom_parameters": {"assessee": "Current Owner"},
    }


def test_sync_catalogs_accounts_and_counts_new_bills(tmp_path):
    def search(url, body):
        assert "201-1170-018-0000" in body["requests"][0]["query"]
        return _account()

    with TaxStore(tmp_path / "tax.db") as store:
        first = sync_tax(
            store,
            SacramentoCountyTax(),
            ("20111700180000",),
            fetch=search,
            payable_fetch=lambda url: _payable(),
            page_fetch=lambda url: "",
        )
        assert first.summary() == "accounts=1, bills_new=1, missed=0"
        saved = store.get("201-1170-018-0000")
        assert saved is not None
        assert saved.amount_cents == 700
        assert saved.bills == (TaxBill("20250312132", "2025 Secured Annual Bill #20250312132", 2025),)

        second = sync_tax(
            store,
            SacramentoCountyTax(),
            ("20111700180000",),
            fetch=search,
            payable_fetch=lambda url: _payable("0.00"),
            page_fetch=lambda url: "",
        )
        assert second.bills_new == 0
        assert store.get("20111700180000").amount_cents == 0


def test_sync_records_a_miss_and_keeps_going(tmp_path):
    def search(url, body):
        query = body["requests"][0]["query"]
        if query == "201-1170-018-0000":
            return {"results": [{"hits": []}]}
        raise RuntimeError("portal down")

    with TaxStore(tmp_path / "tax.db") as store:
        result = sync_tax(
            store,
            SacramentoCountyTax(),
            ("20111700180000", "20111700170001"),
            fetch=search,
            payable_fetch=lambda url: {},
            page_fetch=lambda url: "",
        )
    assert result.missed == ["20111700180000"]
    assert result.accounts_synced == 0
    assert len(result.errors) == 1
    assert "20111700170001" in result.errors[0]


def test_sync_stores_the_bill_levies(tmp_path):
    page = """
    <h2>2025 Secured Annual Bill #20250312132</h2>
    <table>
      <tr><th>Land</th><th>Improvements</th><th>Personal Property</th><th>Exemptions</th><th>Net Assessed Value</th></tr>
      <tr><td>$87,041</td><td>$145,071</td><td>$0</td><td>-$7,000</td><td>$225,112</td></tr>
    </table>
    <table>
      <tr><th>Taxing authority</th><th>Rate</th><th>Taxable</th><th>Tax</th></tr>
      <tr><th>Countywide Tax (Secured)</th><td>1.00000000%</td><td>$225,112.00</td><td>$2,251.12</td></tr>
    </table>
    <table>
      <tr><th>Levying authority</th><th>Code</th><th>Phone Number</th><th>Amount</th></tr>
      <tr><th>SAFCA O &amp; M ASSESSMENT DIST #1</th><td>0168</td><td>(916) 874-7606</td><td>$8.42</td></tr>
    </table>
    """

    def pages(url):
        if "/bills/" in url:
            return page
        return '<a href="https://county-taxes.net/iframe-taxsys/x/bills/2C05E746-8B5F-11F0-8D26-D9626B539BB7">2025</a>'

    with TaxStore(tmp_path / "tax.db") as store:
        result = sync_tax(
            store,
            SacramentoCountyTax(),
            ("20111700180000",),
            fetch=lambda url, body: _account(),
            payable_fetch=lambda url: _payable(),
            page_fetch=pages,
        )
        assert result.summary() == "accounts=1, bills_new=1, missed=0"
        bill = store.get("201-1170-018-0000").bills[0]
        assert bill.number == "20250312132"
        assert bill.net_assessed_cents == 22_511_200
        assert bill.levies[0].name == "Countywide Tax (Secured)"
        assert bill.levies[-1].code == "0168"


def test_sync_saves_the_print_pdf_under_the_parcel(tmp_path):
    page = """
    <h2>2025 Secured Annual Bill #20250312132</h2>
    <table>
      <tr><th>Land</th><th>Improvements</th><th>Personal Property</th><th>Exemptions</th><th>Net Assessed Value</th></tr>
      <tr><td>$1</td><td>$2</td><td>$0</td><td>$0</td><td>$3</td></tr>
    </table>
    """

    def pages(url):
        if "/bills/" in url:
            return page
        return '<a href="https://county-taxes.net/iframe-taxsys/x/bills/2C05E746-8B5F-11F0-8D26-D9626B539BB7">2025</a>'

    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    with TaxStore(tmp_path / "tax.db") as store:
        sync_tax(
            store,
            SacramentoCountyTax(),
            ("20111700180000",),
            fetch=lambda url, body: _account(),
            payable_fetch=lambda url: _payable(),
            page_fetch=pages,
            pdf_fetch=lambda url: pdf,
            bills_dir=tmp_path / "tax-bills",
        )
        bill = store.get("201-1170-018-0000").bills[0]
        path = tmp_path / "tax-bills" / "201-1170-018-0000" / "2025-20250312132.pdf"
        assert bill.pdf_path == str(path)
        assert path.read_bytes() == pdf
        assert len(bill.pdf_sha256) == 64
