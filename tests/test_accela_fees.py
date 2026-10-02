"""Sacramento Citizen Access fee tables: five lines a page, every page read, and the printed totals kept beside the lines.
Also the row and report parsers that once read a neighbor's markup."""

from __future__ import annotations

import json
from datetime import date

from jason.community.accela import (
    CapId,
    Fee,
    Module,
    Report,
    SacramentoCitizenAccess,
    fee_pages,
    fee_total,
    parse_reports,
    permits_from_html,
)

CAP = CapId("26BCM", "00000", "00001")
RECORD_PAGE = "<html><body>Record COM-2600001: Commercial Repair-Maintenance Record Status: Ready-to-Issue Record Info</body></html>"


def _fee_row(day: str, invoice: str, amount: str) -> str:
    return (
        '<tr class="ACA_TabRow_Odd ACA_TabRow_Odd_FontSize">'
        f'<td><div class="ACA_NShot">{day}</div></td><td><div class="ACA_Medium">{invoice}</div></td>'
        f'<td><div class="ACA_Medium">{amount}</div></td><td><a id="detail" href="CapFees.aspx">View Details</a></td></tr>'
    )


def _fee_page(rows: list[tuple[str, str, str]], *, pages: int, total: str, kind: str = "paid") -> str:
    pager = ""
    if pages > 1:
        links = "".join(f"<td><a href=\"javascript:;\" onClick=\"changePage('{n}','true')\">{n}</a></td>" for n in range(2, pages + 1))
        pager = (f'<tr class="ACA_Table_Pages"><td colspan="6"><table><tr><td>Additional Results:</td>{links}'
                 f"<td><a href=\"javascript:;\" onClick=\"changePage('2','true')\">Next &gt;</a></td></tr></table></td></tr>")
    return (f'<table class="FeeList"><tr class="ACA_BkTit"><th>Date</th><th>Invoice Number</th><th>Amount</th></tr>'
            + "".join(_fee_row(*row) for row in rows) + pager
            + f"<tr><td colspan=\"6\"><strong><i>Total {kind} fees: {total}</i></strong></td></tr></table>")


PAID_1 = _fee_page([("08/05/2026", "885973", "$0.91"), ("08/05/2026", "885973", "$2.80"), ("08/05/2026", "885973", "$1.00"),
                    ("08/05/2026", "885973", "$272.00"), ("08/05/2026", "879230", "$207.00")], pages=2, total="$549.81")
PAID_2 = _fee_page([("08/05/2026", "885973", "$18.20"), ("08/05/2026", "885973", "$47.90")], pages=2, total="$549.81")
DUE = _fee_page([], pages=1, total="$0.00", kind="outstanding")


class Portal:
    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str, str | None, dict[str, str]]] = []

    def __call__(self, method: str, url: str, body: str | None, headers: dict[str, str]):
        self.calls.append((method, url, body, dict(headers)))
        return 200, self.replies.pop(0), {}


def test_the_pager_and_the_printed_total() -> None:
    assert fee_pages(PAID_1) == 2 and fee_pages(DUE) == 1 and fee_pages("") == 1
    assert fee_total(PAID_1) == 54981 and fee_total(DUE) == 0 and fee_total("<table></table>") is None
    assert fee_pages("changePage(&#39;3&#39;,&#39;true&#39;)") == 3


def test_detail_reads_every_page_of_a_fee_table() -> None:
    portal = Portal(RECORD_PAGE, json.dumps({"d": PAID_1}), json.dumps({"d": PAID_2}), json.dumps({"d": DUE}),
                    json.dumps({"d": ""}), json.dumps({"d": ""}))
    detail = SacramentoCitizenAccess(portal).detail(CAP)

    assert len(detail.fees_paid) == 7 and detail.fees_paid[-1] == Fee(True, date(2026, 8, 5), "885973", 4790)
    assert (detail.paid_cents, detail.paid_total_cents) == (54981, 54981)
    assert (detail.unpaid_cents, detail.unpaid_total_cents) == (0, 0)
    assert detail.fees_complete
    names = [call[1].rsplit("/", 1)[-1] for call in portal.calls[1:]]
    assert names == ["DisplayFeePaid", "DisplayFeePaid", "DisplayFeeNoPaid", "GetProcessingData", "GetBuildCapTree"]
    assert [json.loads(call[2])["pageNum"] for call in portal.calls[1:4]] == [1, 2, 1]


def test_a_short_read_is_not_complete() -> None:
    portal = Portal(RECORD_PAGE, json.dumps({"d": PAID_1}), json.dumps({"d": ""}), json.dumps({"d": DUE}),
                    json.dumps({"d": ""}), json.dumps({"d": ""}))
    detail = SacramentoCitizenAccess(portal).detail(CAP)
    assert detail.paid_cents == 48371 and detail.paid_total_cents == 54981
    assert not detail.fees_complete


def test_a_short_row_does_not_take_the_previous_rows_cap_or_date() -> None:
    def row(day: str, number: str, id3: str) -> str:
        link = f"../Cap/CapDetail.aspx?Module=Building&amp;capID1=26BCM&amp;capID2=00000&amp;capID3={id3}&amp;agencyCode=SACRAMENTO"
        return (f'<tr><td><span id="x_lblUpdatedTime">{day}</span></td>'
                f'<td><a href="{link}"><span id="x_lblPermitNumber">{number}</span></a></td></tr>')

    first, second = permits_from_html(row("01/01/2026", "COM-2600001", "00001") + row("02/02/2026", "COM-2600002", "00002"),
                                      Module.BUILDING)
    assert (first.cap.id3, first.opened) == ("00001", date(2026, 1, 1))
    assert (second.cap.id3, second.opened) == ("00002", date(2026, 2, 2))


def test_a_later_escaped_link_does_not_run_into_the_report() -> None:
    page = (
        '<a onclick="print_onclick(&#39;../Report/ReportParameter.aspx?module=Building&amp;reportID=1234'
        '&amp;reportType=LINK_REPORT_CONVERT&#39;);return false;" title="Print/View Record" href="#">Print</a>'
        '<a href="javascript:__doPostBack(&#39;ctl00$foo&#39;,&#39;&#39;)">More</a>'
    )
    assert parse_reports(page) == (Report("Print/View Record", "LINK_REPORT_CONVERT", "1234"),)
