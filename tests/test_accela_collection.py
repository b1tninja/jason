"""Sacramento Citizen Access collections and record pages: the collection's totals and paging, the row labels, the
record's status, and its completed inspections. The client only reads."""

from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs

from jason.community.accela import (
    CapId,
    CollectionSummary,
    Inspection,
    Module,
    Permit,
    SacramentoCitizenAccess,
    next_page_target,
    parse_collection_summary,
    parse_inspections,
    parse_record_status,
    permits_from_html,
)

_GRID = "ctl00$PlaceHolderMain$dlCAPsGroupByModule$ctl00$CAPsForMyCollection$capList$gdvPermitList"
NEXT = _GRID + "$ctl13$ctl06"

SUMMARY = (
    "<div><span>Total Records: &nbsp; 33 &nbsp; ( 33 &nbsp; Building )</span></div>"
    "<div><span>Inspections Summary: &nbsp; 483 &nbsp; ( 0 &nbsp; Scheduled ,&nbsp; 16 &nbsp; Rescheduled ,&nbsp; "
    "183 &nbsp; Approved ,&nbsp; 271 &nbsp; Denied ,&nbsp; 0 &nbsp; Pending ,&nbsp; 13 &nbsp; Cancelled )</span></div>"
    "<div><span>Fees Summary: &nbsp; $942,630.34 &nbsp; Paid ,&nbsp; $907.81 &nbsp; Due</span></div>"
)


class Portal:
    """A stand-in for HTTP: replies in order and keeps every request."""

    def __init__(self, *replies: str) -> None:
        self.replies = list(replies)
        self.calls: list[tuple[str, str, str | None, dict[str, str]]] = []

    def __call__(self, method: str, url: str, body: str | None, headers: dict[str, str]):
        self.calls.append((method, url, body, dict(headers)))
        return 200, self.replies.pop(0), {}


def _posted(body: str | None) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(body or "", keep_blank_values=True).items()}


def _row(n: int, number: str, day: str, id3: str, record_type: str, description: str, address: str, status: str) -> str:
    """One row of a collection's record list, with the control ids the portal puts on every cell."""
    p = f"ctl00_PlaceHolderMain_dlCAPsGroupByModule_ctl00_CAPsForMyCollection_capList_gdvPermitList_ctl{n:02d}_"
    cell = '<td><div class="ACA_CapListStyle"><span id="{p}{name}">{value}</span></div></td>'
    link = (
        "../Cap/CapDetail.aspx?Module=Building&amp;TabName=Building"
        f"&amp;capID1=26BCM&amp;capID2=00000&amp;capID3={id3}&amp;agencyCode=SACRAMENTO"
    )
    return (
        '<tr class="ACA_TabRow_Odd">'
        + cell.format(p=p, name="lblUpdatedTime", value=day)
        + f'<td><div class="ACA_CapListStyle"><a id="{p}hlPermitNumber" href="{link}">'
        f'<strong><span id="{p}lblPermitNumber">{number}</span></strong></a></div></td>'
        + cell.format(p=p, name="lblType", value=record_type)
        + cell.format(p=p, name="lblDescription", value=description)
        + cell.format(p=p, name="lblAddress", value=address)
        + cell.format(p=p, name="lblStatus", value=status)
        + cell.format(p=p, name="lblProjectName", value="")
        + f'<td><div class="ACA_CapListStyle"><a id="{p}btnRemove" class="NotShowLoading" href="javascript:void(0);" '
        'title="Remove this record from the collection">Remove</a></div></td></tr>'
    )


ROW_1 = _row(2, "COM-2616861", "08/05/2026", "03422", "Commercial Repair-Maintenance",
             "EPC - Repair vehicle damage to the existing garage", "100 EXAMPLE WAY, SACRAMENTO CA 95835", "Ready-to-Issue")
ROW_2 = _row(3, "RES-2600002", "07/01/2026", "03423", "Residential Solar", "Roof mount PV &amp; battery",
             "102 EXAMPLE WAY, SACRAMENTO CA 95835", "Finaled")
ROW_3 = _row(2, "RES-2600003", "06/15/2026", "03424", "Residential Reroof", "Reroof",
             "104 EXAMPLE WAY, SACRAMENTO CA 95835", "Issued")

PAGER_NEXT = (
    '<tr class="ACA_Table_Pages"><td><span class="ACA_Table_Pages_Disabled">&lt; Prev</span>'
    "<span>1</span>"
    f'<a href="javascript:__doPostBack(&#39;{_GRID}$ctl13$ctl02&#39;,&#39;&#39;)">2</a>'
    f'<a href="javascript:__doPostBack(&#39;{NEXT}&#39;,&#39;&#39;)">Next &gt;</a></td></tr>'
)
PAGER_LAST = (
    '<tr class="ACA_Table_Pages"><td>'
    f'<a href="javascript:__doPostBack(&#39;{_GRID}$ctl13$ctl01&#39;,&#39;&#39;)">&lt; Prev</a>'
    '<span>2</span><span class="ACA_Table_Pages_Disabled">Next &gt;</span></td></tr>'
)


def _page(viewstate: str, rows: str, pager: str) -> str:
    return (
        "<!DOCTYPE html><html><body><form method=\"post\">"
        f'<input type="hidden" name="__VIEWSTATE" id="__VIEWSTATE" value="{viewstate}" />'
        '<input type="hidden" name="__EVENTVALIDATION" id="__EVENTVALIDATION" value="ev-01" />'
        + SUMMARY
        + '<table id="ctl00_PlaceHolderMain_dlCAPsGroupByModule_ctl00_CAPsForMyCollection_capList_gdvPermitList">'
        + rows
        + pager
        + "</table></form></body></html>"
    )


def test_a_collection_header_gives_its_totals() -> None:
    assert parse_collection_summary(SUMMARY) == CollectionSummary(
        records=33,
        inspections=483,
        inspections_by={"scheduled": 0, "rescheduled": 16, "approved": 183, "denied": 271, "pending": 0, "cancelled": 13},
        fees_paid_cents=94263034,
        fees_due_cents=90781,
    )
    assert parse_collection_summary("<html><body>No records.</body></html>") == CollectionSummary(None, None, {}, None, None)


def test_a_collection_row_carries_its_type_description_address_and_status() -> None:
    first, second = permits_from_html(ROW_1 + ROW_2, Module.BUILDING)
    assert first == Permit(
        "COM-2616861",
        date(2026, 8, 5),
        "Commercial Repair-Maintenance",
        "EPC - Repair vehicle damage to the existing garage",
        "100 EXAMPLE WAY, SACRAMENTO CA 95835",
        "Ready-to-Issue",
        CapId("26BCM", "00000", "03422"),
        Module.BUILDING,
    )
    assert (second.number, second.opened, second.cap.id3) == ("RES-2600002", date(2026, 7, 1), "03423")
    assert (second.record_type, second.description, second.status) == ("Residential Solar", "Roof mount PV & battery", "Finaled")
    # A search grid without the labels still gives the number.
    bare = '<span id="x_ctl02_lblPermitNumber">COM-2600009</span>'
    [row] = permits_from_html(bare, Module.BUILDING)
    assert (row.number, row.record_type, row.description, row.address, row.status, row.cap) == ("COM-2600009", "", "", "", "", None)


def test_next_page_target_is_the_next_link_of_the_grid() -> None:
    assert next_page_target(PAGER_NEXT) == NEXT
    assert next_page_target(PAGER_LAST) == ""
    assert next_page_target("") == ""
    plain_quotes = f"<a href=\"javascript:__doPostBack('{NEXT}','')\">Next &gt;</a>"
    assert next_page_target(plain_quotes) == NEXT
    other = "<a href=\"javascript:__doPostBack('ctl00$PlaceHolderMain$InspectionList$gvListCompleted$ctl13$ctl06','')\">Next &gt;</a>"
    assert next_page_target(other) == ""
    assert next_page_target(other, grid="gvListCompleted") == "ctl00$PlaceHolderMain$InspectionList$gvListCompleted$ctl13$ctl06"


def test_a_collection_pages_by_posting_the_next_link() -> None:
    portal = Portal(_page("vs-01", ROW_1 + ROW_2, PAGER_NEXT), _page("vs-02", ROW_3, PAGER_LAST))
    summary, records = SacramentoCitizenAccess(portal).collection("4021")

    assert summary.records == 33 and summary.fees_due_cents == 90781
    assert [r.number for r in records] == ["COM-2616861", "RES-2600002", "RES-2600003"]
    assert records[2].cap == CapId("26BCM", "00000", "03424") and records[2].status == "Issued"
    first, second = portal.calls
    url = "https://aca-prod.accela.com/SACRAMENTO/MyCollection/MyCollectionDetail.aspx?collectionId=4021"
    assert first[:3] == ("GET", url, None)
    assert second[0] == "POST" and second[1] == url
    sent = _posted(second[2])
    assert sent["__EVENTTARGET"] == NEXT and sent["__EVENTARGUMENT"] == ""
    assert sent["__VIEWSTATE"] == "vs-01" and sent["__EVENTVALIDATION"] == "ev-01"
    assert second[3] == {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", "Referer": url}


def test_a_collection_stops_when_a_page_adds_nothing_or_at_the_page_limit() -> None:
    # The portal answered the "Next >" post with the same records: stop rather than loop.
    portal = Portal(_page("vs-01", ROW_1 + ROW_2, PAGER_NEXT), _page("vs-02", ROW_1 + ROW_2, PAGER_NEXT))
    _summary, records = SacramentoCitizenAccess(portal).collection("4021")
    assert [r.number for r in records] == ["COM-2616861", "RES-2600002"] and len(portal.calls) == 2

    portal = Portal(_page("vs-01", ROW_1 + ROW_2, PAGER_NEXT))
    _summary, records = SacramentoCitizenAccess(portal).collection("4021", max_pages=0)
    assert len(records) == 2 and len(portal.calls) == 1

    portal = Portal(_page("vs-01", ROW_1, PAGER_NEXT), _page("vs-02", ROW_3, PAGER_LAST))
    assert [r.number for r in SacramentoCitizenAccess(portal).collection_records("4021")] == ["COM-2616861", "RES-2600003"]


def test_a_record_page_gives_its_type_and_status() -> None:
    page = (
        "<html><body><div><span>Record COM-2616861:</span><br /><span>Commercial Repair-Maintenance</span></div>"
        "<div>Record Status: <span>Ready-to-Issue</span></div><div><a href=\"#\">Add to collection</a></div></body></html>"
    )
    assert parse_record_status(page) == ("Commercial Repair-Maintenance", "Ready-to-Issue")
    info = "<h1>Record RES-2600002: Residential Solar</h1><div>Record Status: Finaled</div><h1>Record Info</h1>"
    assert parse_record_status(info) == ("Residential Solar", "Finaled")
    assert parse_record_status("<html><body>Record Info</body></html>") == ("", "")


def test_completed_inspections_are_read_from_the_record_page() -> None:
    page = (
        '<table id="ctl00_PlaceHolderMain_InspectionList_gvListCompleted">'
        "<tr><th>Date</th><th>Inspection</th><th>Result</th></tr>"
        "<tr><td>09/15/2026</td><td>Final Building</td><td>Approved</td></tr>"
        "<tr><td>9/2/2026</td><td>Framing</td><td>Denied</td></tr>"
        "<tr><td>08/20/2026</td><td>Pre-construction meeting</td><td></td></tr>"
        "</table>"
    )
    assert parse_inspections(page) == (
        Inspection(date(2026, 9, 15), "Final Building Approved", "Approved"),
        Inspection(date(2026, 9, 2), "Framing Denied", "Denied"),
        Inspection(date(2026, 8, 20), "Pre-construction meeting", ""),
    )
    none = (
        '<table id="ctl00_PlaceHolderMain_InspectionList_gvListCompleted">'
        "<tr><td>There are no completed inspections on this record.</td></tr></table>"
    )
    assert parse_inspections(none) == ()
    assert parse_inspections("<html><body></body></html>") == ()


def test_the_client_has_no_payment_or_scheduling_calls() -> None:
    names = {name for name in dir(SacramentoCitizenAccess) if not name.startswith("_")}
    assert not names & {
        "pay", "pay_fees", "checkout", "schedule_inspection", "reschedule_inspection", "cancel_inspection",
        "upload", "upload_document", "apply", "submit", "add_to_collection", "remove_from_collection",
    }
    assert names >= {"search", "detail", "documents", "collection", "collections"}
