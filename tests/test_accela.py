"""Sacramento Citizen Access: the read-only client driven through ``fetch``, and the page parsers, on synthetic
pages shaped like the City's."""

from __future__ import annotations

import json
from datetime import date, datetime
from urllib.parse import parse_qs, quote

import pytest

from jason.community.accela import (
    AccelaError,
    AddressHit,
    CapId,
    Collection,
    Condition,
    Document,
    Fee,
    Module,
    ParcelHit,
    ParcelInfo,
    Permit,
    RecordQuery,
    Report,
    ReviewMark,
    SacramentoCitizenAccess,
    apply_delta,
    parse_addresses,
    parse_conditions,
    parse_delta,
    parse_documents,
    parse_fees,
    parse_parcel,
    parse_parcel_grid,
    parse_parcel_links,
    parse_permits_csv,
    parse_related,
    parse_reports,
    parse_tasks,
    redirect_target,
)
from jason.community.recorder import Sacramento

_SEARCH = "ctl00$PlaceHolderMain$btnNewSearch"
_EXPORT = "ctl00$PlaceHolderMain$dgvPermitList$gdvPermitList$gdvPermitListtop4btnExport"
_SEARCH_TYPE = "ctl00$PlaceHolderMain$ddlSearchType"
_PARCEL_NUMBER = "ctl00$PlaceHolderMain$parcelLookupForm$txtAPO_Search_by_Parcel_ParcelNumber"
_ADDRESS = "ctl00$PlaceHolderMain$addressLookupForm$"


class Portal:
    """A stand-in for HTTP: replies in order and keeps every request."""

    def __init__(self, *replies) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str, str | None, dict[str, str]]] = []

    def __call__(self, method: str, url: str, body: str | None, headers: dict[str, str]):
        self.calls.append((method, url, body, dict(headers)))
        reply = self.replies.pop(0)
        return reply if isinstance(reply, tuple) else (200, reply, {})


def _posted(body: str | None) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(body or "", keep_blank_values=True).items()}


def _delta(*items: tuple[str, str, str]) -> str:
    """An ASP.NET AJAX delta: the version item, then ``length|type|id|content|`` per item."""
    return "1|#||4|" + "".join(f"{len(content)}|{kind}|{ident}|{content}|" for kind, ident, content in items)


def _form(viewstate: str, extra: str = "") -> str:
    return (
        "<!DOCTYPE html><html><body><form method=\"post\" id=\"aspnetForm\">"
        f'<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="{viewstate}" />'
        '<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="ev-01" />'
        '<input type="text" name="ctl00$PlaceHolderMain$generalSearchForm$txtGSPermitNumber" value="" />'
        '<select name="ctl00$PlaceHolderMain$ddlSearchType"><option value="0" selected="selected">Address</option>'
        '<option value="1">Parcel</option></select>'
        '<input type="submit" name="ctl00$PlaceHolderMain$btnNewSearch" value="Search" />'
        f"{extra}</form></body></html>"
    )


def _cap_link(id3: str, module: str = "Building") -> str:
    return (
        f"/SACRAMENTO/Cap/CapDetail.aspx?Module={module}&amp;TabName={module}"
        f"&amp;capID1=26BCM&amp;capID2=00000&amp;capID3={id3}&amp;agencyCode=SACRAMENTO"
    )


def _grid_row(n: int, number: str, day: str, id3: str) -> str:
    """One row of the search grid, as long as the portal's (every cell carries the grid's control id)."""
    p = f"ctl00_PlaceHolderMain_dgvPermitList_gdvPermitList_ctl{n:02d}_"
    cell = '<td><div class="ACA_CapListStyle"><span id="{p}{name}">{value}</span></div></td>'
    return (
        '<tr class="ACA_TabRow_Odd">'
        + cell.format(p=p, name="lblUpdatedTime", value=day)
        + f'<td><div class="ACA_CapListStyle"><a id="{p}hlPermitNumber" href="{_cap_link(id3)}">'
        f'<strong><span id="{p}lblPermitNumber1">{number}</span></strong></a></div></td>'
        + cell.format(p=p, name="lblType", value="Residential Alteration")
        + cell.format(p=p, name="lblDescription", value="Replace the water heater in kind")
        + cell.format(p=p, name="lblProjectName", value="")
        + cell.format(p=p, name="lblAddress", value="100 EXAMPLE WAY, SACRAMENTO CA 95835")
        + cell.format(p=p, name="lblStatus", value="Issued")
        + cell.format(p=p, name="lblExpirationDate", value="")
        + f'<td><div class="ACA_CapListStyle"><a id="{p}btnAction" class="NotShowLoading" '
        f'href="javascript:void(0);" title="Actions for this record">Actions</a></div></td></tr>'
    )


PARCEL_DETAIL = (
    "<!DOCTYPE html><html><body>"
    "<div><div><span>Parcel Number:</span></div><div><span>25000100010000</span></div></div>"
    "<div><div>Lot:</div><div>12</div></div>"
    "<div><div>Block:</div><div>A</div></div>"
    "<div><div>Subdivision:</div><div>EXAMPLE UNIT 1</div></div>"
    "<div><div>Parcel Area:</div></div>"
    "<div><div>Zoning:</div><div>R-1A</div></div>"
    "<table><tr><td><a id=\"ctl00_PlaceHolderMain_AddressList_gdvAddressList_ctl02_lbAddress\" href=\"#\">"
    "<strong>100 EXAMPLE WAY, SACRAMENTO CA 95835</strong></a></td></tr>"
    "<tr><td><a id=\"ctl00_PlaceHolderMain_AddressList_gdvAddressList_ctl03_lbAddress\" href=\"#\">"
    "<strong>102  EXAMPLE   WAY, SACRAMENTO CA 95835</strong></a></td></tr></table>"
    "</body></html>"
)

PARCEL = ParcelInfo(
    "25000100010000",
    "12",
    "A",
    "EXAMPLE UNIT 1",
    "",
    "R-1A",
    ("100 EXAMPLE WAY, SACRAMENTO CA 95835", "102 EXAMPLE WAY, SACRAMENTO CA 95835"),
)

_DETAIL_PATH = "/SACRAMENTO/APO/ParcelDetail.aspx?ParcelSeq=123456&ParcelUID=&sourceNumbs=&ParcelNum=25000100010000&agencyCode="


def test_a_missing_form_and_a_bad_cap_id_fail() -> None:
    portal = Portal("<html><body>The site is down for maintenance.</body></html>")
    with pytest.raises(AccelaError, match="did not include a form"):
        SacramentoCitizenAccess(portal).search(Module.BUILDING)
    assert [call[0] for call in portal.calls] == ["GET"]

    rejected = Portal(_form("vs-01"), _delta(("pageRedirect", "", quote("/SACRAMENTO/Error.aspx"))))
    with pytest.raises(AccelaError, match="rejected the search"):
        SacramentoCitizenAccess(rejected).search(Module.BUILDING)

    with pytest.raises(AccelaError, match="returned 503"):
        SacramentoCitizenAccess(Portal((503, "busy", {}))).search(Module.BUILDING)

    for text in ("26BCM:00000", "26BCM::03422", "26BCM-00000-03422", "", "a:b:c:d"):
        with pytest.raises(AccelaError, match="three parts"):
            CapId.parse(text)
    assert CapId.parse("26BCM:00000:03422", module="Planning") == CapId("26BCM", "00000", "03422", "SACRAMENTO", "Planning")


def test_a_one_hit_search_reads_the_record_heading() -> None:
    record_page = (
        "<!DOCTYPE html><html><body><form>"
        '<input type="hidden" name="__VIEWSTATE" value="vs-02" />'
        f'<a href="{_cap_link("00007", "Planning")}">Record details</a>'
        '<span id="ctl00_PlaceHolderMain_lblPermitNumber">PLN-2600007:</span>'
        '<span id="ctl00_PlaceHolderMain_lblPermitType">Site Plan &amp; Design Review</span>'
        '<span id="ctl00_PlaceHolderMain_lblRecordStatus"> Approved </span>'
        "</form></body></html>"
    )
    portal = Portal(_form("vs-01"), record_page)
    result = SacramentoCitizenAccess(portal).search(Module.PLANNING, RecordQuery(permit_number="PLN-2600007"))

    assert result.permits == (
        Permit(
            "PLN-2600007",
            None,
            "Site Plan & Design Review",
            "",
            "",
            "Approved",
            CapId("26BCM", "00000", "00007", "SACRAMENTO", "Planning"),
            Module.PLANNING,
        ),
    )
    assert result.csv_text == "" and result.showing is None
    (get, post) = portal.calls
    assert get[0] == "GET" and "Cap/CapHome.aspx?module=Planning" in get[1]
    sent = _posted(post[2])
    assert post[0] == "POST" and post[1] == get[1]
    assert sent["__EVENTTARGET"] == _SEARCH and sent["__VIEWSTATE"] == "vs-01"
    assert sent["ctl00$PlaceHolderMain$generalSearchForm$txtGSPermitNumber"] == "PLN-2600007"
    assert post[3]["Content-Type"].startswith("application/x-www-form-urlencoded") and post[3]["Referer"] == get[1]


def test_a_truncation_note_is_not_a_permit_row() -> None:
    text = (
        "Only the first 5000 records are included in this file.\r\n"
        '"Date","Permit Number","Record Type","Description","Address","Status"\r\n'
        '"09/01/2026","COM-2600001","Residential Alteration","Replace, in kind","100 EXAMPLE WAY, SACRAMENTO CA 95835","Issued"\r\n'
        ",,,,,\r\n"
        '"","COM-2600002","Residential Solar","","","Finaled"\r\n'
    )
    first, second = parse_permits_csv(text, module=Module.BUILDING)
    assert first == Permit(
        "COM-2600001",
        date(2026, 9, 1),
        "Residential Alteration",
        "Replace, in kind",
        "100 EXAMPLE WAY, SACRAMENTO CA 95835",
        "Issued",
        module=Module.BUILDING,
    )
    assert second.number == "COM-2600002" and second.opened is None and second.cap is None
    assert parse_permits_csv("Only the first 5000 records are included in this file.\r\n", module=Module.BUILDING) == ()
    assert parse_permits_csv("", module=Module.BUILDING) == ()


def test_address_lookup_reads_the_result_rows() -> None:
    row = (
        '<tr class="ACA_TabRow_Odd"><td><span id="ctl00_PlaceHolderMain_AddressList_ctl{n}_lblParcelNumber">{parcel}</span></td>'
        '<td><a id="ctl00_PlaceHolderMain_AddressList_ctl{n}_lbAddress" href="#"><strong>{address}</strong></a></td></tr>'
    )
    results = "<html><body><table>" + "".join(
        row.format(n=n, parcel=parcel, address=address)
        for n, parcel, address in (
            ("02", "25000100010000", "100  EXAMPLE WAY, SACRAMENTO CA 95835"),
            ("03", "25000100020000", "102 EXAMPLE WAY, SACRAMENTO CA 95835"),
            ("04", "25000100010000", "100 EXAMPLE WAY, SACRAMENTO CA 95835"),
        )
    ) + "</table></body></html>"
    portal = Portal(_form("vs-01"), results)
    hits = SacramentoCitizenAccess(portal).lookup_address("EXAMPLE", suffix="WAY", number_from="100", number_to="102")

    assert hits == (
        AddressHit("25000100010000", "100 EXAMPLE WAY, SACRAMENTO CA 95835"),
        AddressHit("25000100020000", "102 EXAMPLE WAY, SACRAMENTO CA 95835"),
    )
    (get, post) = portal.calls
    assert "APO/APOLookup.aspx?TabName=APO" in get[1] and post[1] == get[1]
    sent = _posted(post[2])
    assert sent["__EVENTTARGET"] == _SEARCH and sent[_SEARCH_TYPE] == "0"
    assert sent[_ADDRESS + "txtAPO_Search_by_Address_StreetName"] == "EXAMPLE"
    assert sent[_ADDRESS + "ddlStreetSuffix"] == "WAY"
    assert sent[_ADDRESS + "txtAPO_Search_by_Address_StreetNumber$ChildControl0"] == "100"
    assert sent[_ADDRESS + "txtAPO_Search_by_Address_StreetNumber$ChildControl1"] == "102"
    assert sent[_ADDRESS + "ddlAPO_Search_by_Address_Direction"] == ""


def test_an_address_search_row_has_no_parcel_until_it_is_opened() -> None:
    search_row = (
        '<tr class="ACA_TabRow_Odd"><td><a href="javascript:WebForm_DoPostBackWithOptions(new WebForm_PostBackOptions('
        "&quot;ctl00$PlaceHolderMain$AddressList$gdvAddressList$ctl02$lblFullAddress&quot;, &quot;&quot;, true, "
        '&quot;&quot;, &quot;&quot;, false, true))"><strong>100  EXAMPLE WAY, SACRAMENTO CA 95835</strong></a></td></tr>'
    )
    assert parse_addresses(search_row) == (AddressHit("", "100 EXAMPLE WAY, SACRAMENTO CA 95835"),)

    opened = (
        '<span id="ctl00_PlaceHolderMain_ParcelDetail_lblParcelNumber">25000100010000</span>'
        '<table><tr><td><a id="ctl00_PlaceHolderMain_AddressList_ctl02_lbAddress" href="#">'
        "<strong>100 EXAMPLE WAY, SACRAMENTO CA 95835</strong></a></td></tr></table>"
    )
    # The same address with its parcel number wins over the bare search row.
    assert parse_addresses(opened + search_row) == (AddressHit("25000100010000", "100 EXAMPLE WAY, SACRAMENTO CA 95835"),)

    # One match: the portal redirects to the parcel page, and the client follows it.
    portal = Portal(_form("vs-01"), _delta(("pageRedirect", "", quote(_DETAIL_PATH, safe=""))), opened)
    hits = SacramentoCitizenAccess(portal).lookup_address("EXAMPLE", number_from="100")
    assert hits == (AddressHit("25000100010000", "100 EXAMPLE WAY, SACRAMENTO CA 95835"),)
    assert portal.calls[2][:3] == ("GET", "https://aca-prod.accela.com" + _DETAIL_PATH, None)


def test_collections_and_sign_in() -> None:
    portal = Portal("<html><body>Login</body></html>", json.dumps({"type": "success", "message": ""}))
    client = SacramentoCitizenAccess(portal)
    assert client.sign_in("someone@example.com", "not-a-real-password") is True
    (login, sign_in) = portal.calls
    assert login[:2] == ("GET", "https://aca-prod.accela.com/SACRAMENTO/Login.aspx")
    assert sign_in[:2] == ("POST", "https://aca-prod.accela.com/SACRAMENTO/api/PublicUser/SignIn")
    assert json.loads(sign_in[2]) == {"Name": "someone@example.com", "Pwd": "not-a-real-password", "IsRemember": 0}
    assert sign_in[3] == {"Content-Type": "application/json"}

    refused = Portal("<html></html>", json.dumps({"type": "error", "message": "Invalid user name or password"}))
    assert SacramentoCitizenAccess(refused).sign_in("someone@example.com", "wrong") is False
    with pytest.raises(AccelaError, match="did not return JSON"):
        SacramentoCitizenAccess(Portal("<html></html>", "<html>Error</html>")).sign_in("someone@example.com", "wrong")

    page = (
        "<table><tr><td><a href=\"/SACRAMENTO/MyCollection/MyCollectionDetail.aspx?collectionId=4021\" class=\"NotShowLoading\">"
        "<span>Our permits</span></a></td></tr>"
        "<tr><td><a href=\"MyCollectionDetail.aspx?collectionId=4022\"><span>Solar</span> &amp; roofs</a></td></tr></table>"
    )
    portal = Portal(page, "<html><body>Sign in to see your collections.</body></html>")
    client = SacramentoCitizenAccess(portal)
    assert client.collections() == (Collection("4021", "Our permits"), Collection("4022", "Solar & roofs"))
    assert portal.calls[0][:2] == ("GET", "https://aca-prod.accela.com/SACRAMENTO/MyCollection/MyCollectionManagement.aspx")
    assert client.collections() == ()


RECORD_PAGE = (
    "<html><body>"
    '<table id="ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList">'
    '<tr><td><span id="ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList_ctl02_lblGeneralConditionsGroupName">Building</span>'
    '<span id="ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList_ctl02_lblGeneralConditionsGroupCount">- 2 Applied</span><br />'
    '<span id="ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList_ctl02_lblGeneralConditionsType">BLDG</span><br />'
    '<span id="ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList_ctl02_lblGeneralConditionsInfo" class="conditiondetailpage">'
    "<div>DO NOT ISSUE - AIR QUALITY APPROVAL REQUIRED</div><div>An asbestos survey is required &amp; on file.</div>"
    "<div>Applied | Required | 09/24/2026</div></span><br /></td></tr>"
    '<tr><td><span id="ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList_ctl03_lblGeneralConditionsGroupName">Fire</span><br />'
    '<span id="ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList_ctl03_lblGeneralConditionsType">FIRE</span><br />'
    '<span id="ctl00_PlaceHolderMain_capConditions_gdvGeneralConditionsList_ctl03_lblGeneralConditionsInfo" class="conditiondetailpage">'
    "<div>Knox box</div><div>Resolved | Notice | 09/25/2026</div></span></td></tr>"
    "</table>"
    '<a id="ctl00_PlaceHolderMain_btnPrint" onclick="print_onclick(&#39;../Report/ReportParameter.aspx?module=Building'
    '&amp;reportID=1234&amp;reportType=LINK_REPORT_CONVERT&#39;);return false;" title="Print/View Record" href="#">Print</a>'
    "</body></html>"
)

ATTACHMENTS = (
    "<table>"
    '<tr><td><span id="ctl00_gdvAttachmentList_ctl02_lblFileName">Application.pdf</span></td>'
    "<td><a href=\"javascript:void(0)\" onclick=\"ViewDocumentDetails('26BCM-00000-00001', '4455667')\">View</a></td>"
    '<td><span id="ctl00_gdvAttachmentList_ctl02_lblType">Application</span></td>'
    '<td><span id="ctl00_gdvAttachmentList_ctl02_lblSize">1.2 MB</span></td>'
    '<td><span id="ctl00_gdvAttachmentList_ctl02_lblUploadDate">08/05/2026</span></td>'
    '<td><span id="ctl00_gdvAttachmentList_ctl02_lblRecordNumber">COM-2600001</span></td></tr>'
    '<tr><td><span id="ctl00_gdvAttachmentList_ctl03_lblFileName">Plans &amp; details.pdf</span></td>'
    "<td><a href=\"javascript:void(0)\" onclick=\"ViewDocumentDetails( '26BCM-00000-00001' , '4455668' )\">View</a></td>"
    '<td><span id="ctl00_gdvAttachmentList_ctl03_lblType">Plans</span></td>'
    '<td><span id="ctl00_gdvAttachmentList_ctl03_lblSize">14 MB</span></td>'
    '<td><span id="ctl00_gdvAttachmentList_ctl03_lblUploadDate"></span></td>'
    '<td><span id="ctl00_gdvAttachmentList_ctl03_lblRecordNumber">COM-2600001</span></td></tr>'
    "</table>"
)

CAP = CapId("26BCM", "00000", "00001")


def test_conditions_reports_and_the_application_file() -> None:
    assert parse_conditions(RECORD_PAGE) == (
        Condition(
            "Building",
            "BLDG",
            "DO NOT ISSUE - AIR QUALITY APPROVAL REQUIRED",
            "An asbestos survey is required & on file.",
            "Applied",
            "Required",
            date(2026, 9, 24),
        ),
        Condition("Fire", "FIRE", "Knox box", "", "Resolved", "Notice", date(2026, 9, 25)),
    )
    assert parse_reports(RECORD_PAGE) == (Report("Print/View Record", "LINK_REPORT_CONVERT", "1234"),)

    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
    portal = Portal(RECORD_PAGE, (200, pdf + b"\r\n<html>trailing page</html>", {"Content-Type": "application/pdf"}))
    assert SacramentoCitizenAccess(portal).download_report(CAP) == pdf
    (page, report) = portal.calls
    assert page[0] == "GET" and "Cap/CapDetail.aspx?" in page[1] and "capID1=26BCM&capID2=00000&capID3=00001" in page[1]
    assert report[0] == "GET" and report[1] == (
        "https://aca-prod.accela.com/SACRAMENTO/Report/ShowReport.aspx"
        "?Module=Building&reportType=LINK_REPORT_CONVERT&reportID=1234&agencyCode=SACRAMENTO"
    )
    assert report[3] == {"Referer": page[1]}

    with pytest.raises(AccelaError, match="has no report"):
        SacramentoCitizenAccess(Portal(RECORD_PAGE)).download_report(CAP, report_id="999")
    with pytest.raises(AccelaError, match="did not return a PDF"):
        SacramentoCitizenAccess(Portal(RECORD_PAGE, (200, "<html>Session expired</html>", {"Content-Type": "text/html"}))).download_report(CAP)

    portal = Portal(RECORD_PAGE, ATTACHMENTS)
    application, plans = SacramentoCitizenAccess(portal).documents(CAP)
    assert application == Document("Application.pdf", "4455667", "Application", "1.2 MB", date(2026, 8, 5), "COM-2600001")
    assert plans == Document("Plans & details.pdf", "4455668", "Plans", "14 MB", None, "COM-2600001")
    (page, listing) = portal.calls
    assert "FileUpload/AttachmentsList.aspx?" in listing[1] and "agencyCode=SACRAMENTO" in listing[1]
    assert listing[3] == {"Referer": page[1]}


FEES_PAID = (
    '<table class="FeeList"><tr class="ACA_TabRow_Header"><th>Date</th><th>Invoice</th><th>Amount</th></tr>'
    '<tr class="ACA_TabRow_Odd ACA_TabRow_Odd_FontSize"><td><div>08/05/2026</div></td><td><div>885973</div></td>'
    "<td><div>$1,272.00</div></td><td><a href=\"#\">View Receipt</a></td></tr>"
    '<tr class="ACA_TabRow_Even ACA_TabRow_Even_FontSize"><td><div>08/06/2026</div></td><td><div>885974</div></td>'
    "<td><div>$70.81</div></td><td></td></tr></table>"
)

FEES_DUE = (
    '<table class="FeeList"><tr class="ACA_TabRow_Odd ACA_TabRow_Odd_FontSize"><td><div>09/01/2026</div></td>'
    "<td><div>886001</div></td><td><div>$342.81</div></td><td></td></tr>"
    "<tr><td><strong><i>Total outstanding fees: $342.81</i></strong></td></tr></table>"
)

PROCESSING = (
    "<tr><td><img title='complete' src='/SACRAMENTO/app_themes/Default/assets/complete.png' alt='Complete' /></td>"
    "<td class='ACA_ALeft' width='770px' >Formal Review</td></tr>"
    "<tr id='a'><td>Marked as <span class='x'>Corrections Required</span> on <span>09/10/2026</span> by <span>A. Reviewer</span></td></tr>"
    "<tr id='b'><td>Marked as <span class='x'>Approved</span> on <span>09/23/2026</span> by <span>B. Reviewer</span></td></tr>"
    "<tr><td><img title='in progress' src='/SACRAMENTO/app_themes/Default/assets/inprogress.png' alt='In progress' /></td>"
    "<td class='ACA_ALeft' width='770px' >Ready To Issue</td></tr>"
)

RELATED = (
    '<table id="tableCapTreeList">'
    f'<tr name="_001" class="ACA_TabRow_Odd"><td><table><tr><td><img alt="" /></td><td><a href="{_cap_link("00001")}">COM-2600001</a>'
    "</td></tr></table></td><td>Residential Alteration</td><td>Example Remodel </td>"
    '<td><span class="ACA_NShot">09/01/2026</span></td></tr>'
    f'<tr name="_001_001" class="ACA_TabRow_Even"><td><table><tr><td><a href="{_cap_link("00002")}">ELE-2600002</a>'
    "</td></tr></table></td><td>Electrical</td><td>Panel &amp; meter</td>"
    '<td><span class="ACA_NShot">09/02/2026</span></td></tr>'
    "</table>"
)

DETAIL_PAGE = (
    "<html><body>"
    "<div><span>Record COM-2600001:</span><br /><span>Residential Alteration</span></div>"
    "<div>Record Status: <span>Issued</span></div><div><a href=\"#\">Add to collection</a></div>"
    '<table id="ctl00_PlaceHolderMain_InspectionList_gvListCompleted"><tr><th>Date</th><th>Inspection</th><th>Result</th></tr>'
    "<tr><td>09/15/2026</td><td>Final Building</td><td>Approved</td></tr></table>"
    "</body></html>"
)


def test_detail_reads_fees_processing_and_related_records() -> None:
    portal = Portal(
        DETAIL_PAGE,
        json.dumps({"d": FEES_PAID}),
        json.dumps({"d": FEES_DUE}),
        json.dumps({"d": PROCESSING}),
        json.dumps({"d": RELATED}),
    )
    detail = SacramentoCitizenAccess(portal).detail(CAP)

    assert detail.cap == CAP
    assert detail.fees_paid == (
        Fee(True, date(2026, 8, 5), "885973", 127200),
        Fee(True, date(2026, 8, 6), "885974", 7081),
    )
    assert detail.fees_unpaid == (Fee(False, date(2026, 9, 1), "886001", 34281),)
    assert (detail.paid_cents, detail.unpaid_cents) == (134281, 34281)
    formal, ready = detail.tasks
    assert formal.name == "Formal Review" and formal.marks == (
        ReviewMark("Corrections Required", date(2026, 9, 10), "A. Reviewer"),
        ReviewMark("Approved", date(2026, 9, 23), "B. Reviewer"),
    )
    assert ready.name == "Ready To Issue" and ready.marks == ()
    parent, child = detail.related
    assert (parent.number, parent.record_type, parent.project, parent.opened, parent.depth) == (
        "COM-2600001", "Residential Alteration", "Example Remodel", date(2026, 9, 1), 1)
    assert parent.cap == CapId("26BCM", "00000", "00001")
    assert (child.number, child.record_type, child.project, child.opened, child.depth) == (
        "ELE-2600002", "Electrical", "Panel & meter", date(2026, 9, 2), 2)
    assert child.cap == CapId("26BCM", "00000", "00002")
    assert (detail.record_type, detail.status) == ("Residential Alteration", "Issued")
    assert [(i.when, i.result) for i in detail.inspections] == [(date(2026, 9, 15), "Approved")]
    assert detail.conditions == () and detail.reports == ()

    page, *methods = portal.calls
    assert page[0] == "GET" and "capID3=00001" in page[1]
    assert [call[1].rsplit("/", 1)[-1] for call in methods] == [
        "DisplayFeePaid", "DisplayFeeNoPaid", "GetProcessingData", "GetBuildCapTree"]
    assert all(call[0] == "POST" and "/SACRAMENTO/Cap/CapDetail.aspx/" in call[1] for call in methods)
    assert all(call[3] == {"Content-Type": "application/json; charset=UTF-8", "Referer": page[1]} for call in methods)
    bodies = [json.loads(call[2]) for call in methods]
    assert bodies[0]["moduleName"] == "Building" and bodies[0]["displayReceiptReport"] is False
    assert bodies[1] == {"pageNum": 1, "moduleName": "Building"}
    assert bodies[2] == {"agencyCode": "SACRAMENTO", "moduleName": "Building"}
    assert bodies[3] == {"moduleName": "Building", "isShowAll": False}

    with pytest.raises(AccelaError, match="DisplayFeePaid did not return JSON"):
        SacramentoCitizenAccess(Portal(DETAIL_PAGE, "<html>Error</html>")).detail(CAP)


def test_fee_and_parcel_parsers_accept_an_empty_page() -> None:
    for page in ("", "   ", "<html><body></body></html>"):
        assert parse_fees(page, paid=True) == ()
        assert parse_tasks(page) == ()
        assert parse_related(page) == ()
        assert parse_parcel(page) is None
        assert parse_parcel_grid(page) == ()
        assert parse_parcel_links(page) == ()
        assert parse_addresses(page) == ()
        assert parse_documents(page) == ()
        assert parse_conditions(page) == ()
        assert parse_reports(page) == ()
    # A fee table with only its total line has no invoices.
    assert parse_fees("<table><tr><td>Total outstanding fees: $0.00</td></tr></table>", paid=False) == ()


def test_one_parcel_row_opens_the_detail_page() -> None:
    target = "ctl00$PlaceHolderMain$RefParcelLookUpList$dgvRefParcelLookUpList$ctl02$lbParcelNumber"
    grid = _form(
        "vs-03",
        '<table><tr class="ACA_TabRow_Odd"><td><a id="ctl00_PlaceHolderMain_RefParcelLookUpList_dgvRefParcelLookUpList_ctl02_lbParcelNumber" '
        f'href="javascript:WebForm_DoPostBackWithOptions(new WebForm_PostBackOptions(&quot;{target}&quot;, &quot;&quot;, true, '
        '&quot;&quot;, &quot;&quot;, false, true))"><strong>25000100010000</strong></a></td>'
        '<td><span id="ctl00_PlaceHolderMain_RefParcelLookUpList_dgvRefParcelLookUpList_ctl02_lblLot">12</span></td>'
        '<td><span id="ctl00_PlaceHolderMain_RefParcelLookUpList_dgvRefParcelLookUpList_ctl02_lblBlock">A</span></td></tr></table>',
    )
    assert parse_parcel_grid(grid) == (ParcelHit("25000100010000", lot="12", block="A", target=target),)

    portal = Portal(_form("vs-01"), _form("vs-02"), grid, PARCEL_DETAIL)
    assert SacramentoCitizenAccess(portal).lookup_parcel("25000100010000") == PARCEL
    get, switch, search, open_row = portal.calls
    assert [call[0] for call in portal.calls] == ["GET", "POST", "POST", "POST"]
    assert _posted(switch[2])["__EVENTTARGET"] == _SEARCH_TYPE and _posted(switch[2])[_SEARCH_TYPE] == "1"
    sent = _posted(search[2])
    assert sent["__EVENTTARGET"] == _SEARCH and sent["__VIEWSTATE"] == "vs-02" and sent[_PARCEL_NUMBER] == "25000100010000"
    opened = _posted(open_row[2])
    assert open_row[1] == get[1] and opened["__EVENTTARGET"] == target and opened["__VIEWSTATE"] == "vs-03"

    # A search that finds nothing is no parcel.
    empty = Portal(_form("vs-01"), _form("vs-02"), _form("vs-03", "<span>No records found.</span>"))
    assert SacramentoCitizenAccess(empty).lookup_parcel("99999999999999") is None


def test_parcel_lookup_follows_the_redirect() -> None:
    redirect = _delta(("pageRedirect", "", quote(_DETAIL_PATH, safe="")))
    portal = Portal(_form("vs-01"), _form("vs-02"), redirect, PARCEL_DETAIL)
    assert SacramentoCitizenAccess(portal).lookup_parcel("25000100010000") == PARCEL
    assert [call[0] for call in portal.calls] == ["GET", "POST", "POST", "GET"]
    assert portal.calls[3][1] == (
        "https://aca-prod.accela.com/SACRAMENTO/APO/ParcelDetail.aspx"
        "?ParcelSeq=123456&ParcelUID=&sourceNumbs=&ParcelNum=25000100010000&agencyCode="
    )


def test_sacramento_exposes_citizen_access() -> None:
    client = Sacramento.citizen_access()
    assert isinstance(client, SacramentoCitizenAccess)
    assert (client.name, client.agency) == ("Sacramento", "SACRAMENTO")
    # Each call is a fresh session with its own cookies.
    assert Sacramento.citizen_access() is not client


def test_search_posts_the_form_then_downloads_the_csv() -> None:
    grid = _form(
        "vs-02",
        '<table id="ctl00_PlaceHolderMain_dgvPermitList_gdvPermitList"><tr class="ACA_Grid_Caption"><td>'
        '<span class="ACA_Grid_Caption">Showing 1-2 of 3</span></td><td>'
        '<a id="ctl00_PlaceHolderMain_dgvPermitList_gdvPermitList_gdvPermitListtop4btnExport" '
        f"href=\"javascript:__doPostBack('{_EXPORT}','')\">Download results</a></td></tr>"
        + _grid_row(2, "COM-2600001", "09/01/2026", "00001")
        + _grid_row(3, "COM-2600002", "09/02/2026", "00002")
        + "</table>",
    )
    csv_text = (
        '"Date","Permit Number","Record Type","Description","Address","Status"\r\n'
        '"09/01/2026","COM-2600001","Residential Alteration","Replace the water heater in kind","100 EXAMPLE WAY, SACRAMENTO CA 95835","Issued"\r\n'
        '"","COM-2600002","Residential Solar","Roof mount PV","102 EXAMPLE WAY, SACRAMENTO CA 95835","Finaled"\r\n'
        '"08/15/2026","COM-2600003","Residential Reroof","Reroof","104 EXAMPLE WAY, SACRAMENTO CA 95835","Expired"\r\n'
    )
    portal = Portal(_form("vs-01"), grid, "1|#||4|", csv_text)
    client = SacramentoCitizenAccess(portal, clock=lambda: datetime(2026, 9, 29, 10, 7, 45))
    query = RecordQuery(start=date(2026, 1, 1), end=date(2026, 9, 29), street_name="EXAMPLE")
    result = client.search(Module.BUILDING, query)

    assert result.csv_text == csv_text and result.showing == (1, 2, 3)
    first, second, third = result.permits
    assert first == Permit(
        "COM-2600001",
        date(2026, 9, 1),
        "Residential Alteration",
        "Replace the water heater in kind",
        "100 EXAMPLE WAY, SACRAMENTO CA 95835",
        "Issued",
        CapId("26BCM", "00000", "00001"),
        Module.BUILDING,
    )
    # The CSV left the date out; the grid had it.
    assert second.cap == CapId("26BCM", "00000", "00002") and second.opened == date(2026, 9, 2)
    # Not on the grid page that was on screen: no cap id.
    assert third.number == "COM-2600003" and third.cap is None and third.opened == date(2026, 8, 15)

    home, search, export, download = portal.calls
    assert home[0] == "GET" and "Cap/CapHome.aspx?module=Building&TabName=Building" in home[1]
    sent = _posted(search[2])
    assert search[0] == "POST" and sent["__EVENTTARGET"] == _SEARCH and sent["__EVENTARGUMENT"] == ""
    assert sent["ctl00$PlaceHolderMain$generalSearchForm$txtGSStartDate"] == "01/01/2026"
    assert sent["ctl00$PlaceHolderMain$generalSearchForm$txtGSEndDate"] == "09/29/2026"
    assert sent["ctl00$PlaceHolderMain$generalSearchForm$txtGSStreetName"] == "EXAMPLE"
    assert sent["ctl00$PlaceHolderMain$generalSearchForm$txtGSPermitNumber"] == ""
    posted = _posted(export[2])
    assert export[0] == "POST" and posted["__EVENTTARGET"] == _EXPORT and posted["__VIEWSTATE"] == "vs-02"
    assert download[:3] == ("GET", "https://aca-prod.accela.com/SACRAMENTO/Export2CSV.ashx?flag=457", None)
    assert download[3] == {"Referer": home[1]}

    # An export that returns no CSV falls back to the grid.
    portal = Portal(_form("vs-01"), grid, "1|#||4|", "<html>Session expired</html>")
    fallback = SacramentoCitizenAccess(portal, clock=lambda: datetime(2026, 9, 29, 10, 7, 45)).search(Module.BUILDING)
    assert fallback.csv_text == "" and [p.number for p in fallback.permits] == ["COM-2600001", "COM-2600002"]
    assert [p.cap.id3 for p in fallback.permits] == ["00001", "00002"]


def test_the_capture_redirect_is_the_parcel_detail_page() -> None:
    encoded = quote(_DETAIL_PATH, safe="")
    payload = _delta(("updatePanel", "ctl00_PlaceHolderMain_updatePanel", ""), ("pageRedirect", "", encoded))
    assert parse_delta(payload)[-1] == ("pageRedirect", "", encoded)
    assert redirect_target(payload) == _DETAIL_PATH
    assert redirect_target(PARCEL_DETAIL) == ""

    links = (
        '<a href="/SACRAMENTO/APO/ParcelDetail.aspx?ParcelSeq=123456&amp;ParcelNum=25000100010000">one</a>'
        '<a href="/SACRAMENTO/APO/ParcelDetail.aspx?ParcelSeq=123456&amp;ParcelNum=25000100010000">again</a>'
        '<a href="/SACRAMENTO/APO/ParcelDetail.aspx?ParcelSeq=123457&amp;ParcelNum=25000100020000">two</a>'
        '<a href="/SACRAMENTO/APO/ParcelDetail.aspx?ParcelSeq=1">no number</a>'
    )
    assert parse_parcel_links(links) == (ParcelHit("25000100010000", "123456"), ParcelHit("25000100020000", "123457"))

    # Switching the search type answers with a delta; its hidden fields carry into the search post.
    switched = _delta(("hiddenField", "__VIEWSTATE", "vs-02"), ("hiddenField", "__EVENTVALIDATION", "ev-02"))
    assert apply_delta({"__VIEWSTATE": "vs-01", "keep": "x"}, switched) == {
        "__VIEWSTATE": "vs-02", "keep": "x", "__EVENTVALIDATION": "ev-02"}
    portal = Portal(_form("vs-01"), switched, payload)
    assert SacramentoCitizenAccess(portal).find_parcels("25000100010000") == (ParcelHit("25000100010000", "123456"),)
    assert len(portal.calls) == 3
    sent = _posted(portal.calls[2][2])
    assert sent["__VIEWSTATE"] == "vs-02" and sent["__EVENTVALIDATION"] == "ev-02"
    assert sent[_SEARCH_TYPE] == "1" and sent[_PARCEL_NUMBER] == "25000100010000"
