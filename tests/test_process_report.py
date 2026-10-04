"""The process report: owners by role unless asked, businesses named, the parcel's strand by each deed's prior."""

import re
from datetime import date

from jason.tasks.process_report import process_markdown


def _bundle() -> dict:
    deed = lambda n, d, r, e, priors=(): {"number": n, "recorded": d, "grantors": list(r), "grantees": list(e), "priors": list(priors), "cited": []}
    steps = [
        deed("2023-0000500", "2023-03-01", ["SAMPLE PAT Q"], ["SAMPLE PAT Q", "EXAMPLE JO"], ["2015-0000400"]),
        deed("2015-0000400", "2015-07-01", ["EXAMPLE OWNER A"], ["SAMPLE PAT Q"], ["2009-0000300", "2001-0000100"]),
        deed("2009-0000300", "2009-05-01", ["US EXAMPLE BANK NA TR"], ["EXAMPLE OWNER A"]),
        deed("2001-0000100", "2001-02-01", ["EXAMPLE HOMES INC"], ["EXAMPLE OWNER A", "CASEY SAMPLE"]),
    ]
    instruments = [
        {"number": s["number"], "recorded": s["recorded"], "kind": "fee", "filingCode": "", "filingName": "DEED",
         "family": "conveyance", "grantors": s["grantors"], "grantees": s["grantees"], "crossReferences": []}
        for s in steps
    ] + [
        {"number": "2009-0000301", "recorded": "2009-05-01", "kind": "loan", "filingCode": "", "filingName": "DEED OF TRUST",
         "family": "loan", "grantors": ["EXAMPLE OWNER A"], "grantees": ["EXAMPLE MORTGAGE CORP"], "crossReferences": []},
    ]
    readings = [
        {"number": "2023-0000500", "process": "restatement", "complete": True, "slots": [], "companions": []},
        {"number": "2015-0000400", "process": "resale", "complete": True, "slots": [], "companions": []},
        {"number": "2009-0000300", "process": "reo resale", "complete": False,
         "slots": [{"role": "trustee's deed", "reason": "missing", "number": ""}], "companions": ["2009-0000301"]},
        {"number": "2001-0000100", "process": "resale", "complete": True, "slots": [], "companions": []},
    ]
    loan = {"owner": "EXAMPLE OWNER A", "process": "loan", "status": "closed", "duringTenure": True, "debtor": ["EXAMPLE OWNER A"],
            "claimant": ["EXAMPLE MORTGAGE CORP"],
            "steps": [{"number": "2009-0000301", "recorded": "2009-05-01", "filing": "230 DEED OF TRUST", "effect": "opens"},
                      {"number": "2012-0000900", "recorded": "2012-01-01", "filing": "531 NOTICE OF DEFAULT", "effect": "escalates"},
                      {"number": "2015-0000401", "recorded": "2015-07-01", "filing": "238 RECONVEYANCE", "effect": "closes"}]}
    return {"county": "placer", "scope": "parcel", "label": "000000000001", "instruments": instruments,
            "histories": [{"apn": "000000000001", "developers": [], "reachedDeveloper": False, "gaps": ["2009-0000300"], "steps": steps}],
            "readings": readings, "formations": [], "liens": [loan], "parcels": [{"apn": "000000000001", "newest": "2023-0000500"}],
            "notes": []}


def test_owners_by_role_businesses_by_name_and_the_strand_by_prior():
    md = process_markdown(_bundle(), address="123 Main St", today=date(2026, 10, 3))
    for person in ("SAMPLE PAT", "EXAMPLE JO", "CASEY SAMPLE", "EXAMPLE OWNER A"):
        assert person not in md
    assert "Owner A" in md and "EXAMPLE HOMES INC" in md and "US EXAMPLE BANK NA TR" in md
    # The 2015 deed's own prior is the 2009 deed (listed first); the 2001 deed only shares a name.
    assert "2009-0000300 → 2015-0000400 → 2023-0000500" in md
    assert "d20010000100 -.-|shares a name| d20150000400" in md
    assert "trustee's deed<br/>(not found)" in md
    assert "notice_of_default --> reconveyance : 1" in md
    assert len(re.findall(r"```mermaid", md)) >= 6


def test_names_when_asked():
    md = process_markdown(_bundle(), names=True, today=date(2026, 10, 3))
    assert "EXAMPLE OWNER A" in md and "Owner A (" not in md
