from datetime import date

from jason.community.filings import ADVANCES, CLOSES, CURES, Family, Process, encumbrances, instrument_class
from jason.community.recorder import FiledInstrument


def _doc(number, code, grantors=(), grantees=(), cites=(), kind="", name=None):
    recorded = date(int(number[:4]), int(number[4:6]), int(number[6:8]))
    return FiledInstrument(number, recorded, kind, tuple(grantors), tuple(grantees), tuple(cites), code, instrument_class(code).name if name is None else name)


def test_the_other_filings_are_classified():
    assert instrument_class("406").process is Process.SUPPORT_LIEN and instrument_class("623").closes
    assert instrument_class("379").process is Process.FEDERAL_TAX_LIEN and instrument_class("631").process is Process.FEDERAL_TAX_LIEN
    assert instrument_class("381").process is Process.COUNTY_TAX_LIEN and instrument_class("407").process is Process.SPECIAL_TAX
    assert instrument_class("183").process is Process.COUNTY_REIMBURSEMENT and instrument_class("398").process is Process.CODE_ENFORCEMENT
    assert instrument_class("208").effect == ADVANCES and instrument_class("235").process is Process.LOAN and instrument_class("616").effect == CURES
    assert instrument_class("285").family is Family.MAP and instrument_class("307").family is Family.PLAN and instrument_class("555").family is Family.AUTHORITY
    assert instrument_class("367").effect == ADVANCES and instrument_class("371").closes
    assert instrument_class("", "", "lien").code == "230" and instrument_class("", "", "fee").family is Family.CONVEYANCE and instrument_class("", "", "release").code == "238"


def test_support_federal_and_county_tax_liens_pair_with_their_releases():
    found = encumbrances((
        _doc("200606161879", "406", ("OKAFOR DESMOND J",), ("COUNTY OF SACTO",)),
        _doc("200510192255", "379", ("CASTELLAN SILAS S",), ("UNITED STATES",)),
        _doc("200701010001", "631", ("UNITED STATES",), ("CASTELLAN SILAS S",)),
        _doc("201105040759", "405", ("THORNBURY DORIAN D III", "UPSHAW TOBIAS G"), ("COUNTY OF SACTO TAX",)),
        _doc("202006220312", "623", ("COUNTY OF SACRAMENTO TAX COLLECTOR",), ("THORNBURY DORIAN DEAN III", "UPSHAW TOBIAS G"), ("201105040759",)),
        _doc("202210120304", "381", ("LOCKHART JUNE", "LOCKHART PERRIN"), ("COUNTY OF SACRAMENTO TAX COLLECTOR",)),
        _doc("202301010002", "624", ("COUNTY OF SACRAMENTO TAX COLLECTOR",), ("LOCKHART JUNE",)),
    ))
    summary = {e.opened.number: (e.process, e.status) for e in found}
    assert summary["200606161879"] == (Process.SUPPORT_LIEN, "open")
    assert summary["200510192255"] == (Process.FEDERAL_TAX_LIEN, "closed")
    assert summary["201105040759"] == (Process.JUDGMENT_LIEN, "closed")
    assert summary["202210120304"] == (Process.COUNTY_TAX_LIEN, "closed")  # the plain release joined the county's lien by the debtor's name
    assert len(found) == 4


def test_a_rescission_cures_a_loan_default_and_closes_a_tax_default():
    loan = encumbrances((
        _doc("202001010001", "230", ("OWNER JANE",), ("BIG BANK",)),
        _doc("202101010002", "531", ("OWNER JANE",), ("BIG BANK",)),
        _doc("202106010003", "720", ("BIG BANK",), ("OWNER JANE",), ("202101010002",)),
    ))
    assert len(loan) == 1 and loan[0].status == "open" and loan[0].closed is None and [s.effect for s in loan[0].steps][-1] == CURES
    cancelled = encumbrances((
        _doc("202001010001", "230", ("OWNER JANE",), ("BIG BANK",)),
        _doc("202101010002", "531", ("OWNER JANE",), ("BIG BANK",)),
        _doc("202106010004", "616", ("OWNER JANE",), (), ("202101010002",)),
    ))
    assert cancelled[0].status == "open" and cancelled[0].steps[-1].filing.startswith("616")
    tax = encumbrances((
        _doc("202308250761", "802", ("MYSTIQUE COMMUNITY ASSOC",), ("COUNTY OF SACRAMENTO TAX COLLECTOR",)),
        _doc("202407080293", "720", ("COUNTY OF SACRAMENTO TAX COLLECTOR",), ("MYSTIQUE COMMUNITY ASSOC",)),
    ))
    assert tax[0].status == "closed" and tax[0].closed == date(2024, 7, 8)


def test_loan_paperwork_advances_the_loan_and_a_tax_sale_notice_escalates_a_default():
    found = encumbrances((
        _doc("201907080829", "230", ("YARDLEY JUDE L",), ("TCF NATIONAL BANK",)),
        _doc("202009211336", "208", ("YARDLEY JUDE L", "TCF NATIONAL BANK"), ("CALIBER HOME LOANS INC",), ("201907080829",)),
        _doc("202205091088", "230", ("ADEYEMI TALIA",), ("TH MSR HOLDINGS LLC",)),
        _doc("202411080424", "235", ("ADEYEMI TALIA",), ("TH MSR HOLDINGS LLC",), ("202205091088",)),
    ))
    assert [(e.opened.number, e.status, len(e.steps)) for e in found] == [("201907080829", "open", 2), ("202205091088", "open", 2)]
    tax = encumbrances((
        _doc("201105040001", "802", ("WL HOMES LLC",), ("COUNTY OF SACRAMENTO TAX COLLECTOR",)),
        _doc("201608251658", "542", ("WL HOMES LLC",), ("COUNTY OF SACTO TAX",)),
    ))
    assert len(tax) == 1 and tax[0].status == "noticed for tax sale"
    business = encumbrances((_doc("198107071037", "542", ("NORCROSS JEROME L",), ("IVERSON KIT",)),))
    assert business == ()


def test_code_enforcement_reimbursement_and_special_tax_open_their_own_lifecycles():
    found = encumbrances((
        _doc("200005300538", "398", ("ROOKWOOD WALLACE M",), ("CITY OF SACTO",)),
        _doc("200101010001", "619", ("CITY OF SACTO",), ("ROOKWOOD WALLACE M",)),
        _doc("199410260704", "183", ("QUIMBY MILES",), ("COUNTY OF SACTO DRR",)),
        _doc("202103241732", "407", ("SUTCLIFFE GRETA",), ("CALIFORNIA HOME FINANCE AUTHORITY COMMUNITY FACILITIES DISTRICT",)),
    ))
    summary = {e.opened.number: (e.process, e.status) for e in found}
    assert summary["200005300538"] == (Process.CODE_ENFORCEMENT, "closed")
    assert summary["199410260704"] == (Process.COUNTY_REIMBURSEMENT, "open")
    assert summary["202103241732"] == (Process.SPECIAL_TAX, "open")


def test_rows_with_only_a_walk_kind_still_form_a_loan():
    found = encumbrances((
        _doc("200712210174", "", ("WESTBROOK LORNA R",), ("JOHN LAING MTG L P",), kind="lien", name=""),
        _doc("201001010001", "", ("JOHN LAING MTG L P",), ("WESTBROOK LORNA R",), ("200712210174",), kind="release", name=""),
    ))
    assert len(found) == 1 and found[0].process is Process.LOAN and found[0].status == "closed"
