"""Sacramento County public index tools.

A search hit is not a pin. The index is the county's public document search.
These tools do not log into PayHOA, Google, or Keeper, and they do not open
a browser. A wide name is searched again as a grant deed, a quitclaim, and
the two UCC filings. A filing that is still wide is left out. ``recorder_descend``
walks one step at a time from a deed and from the developer, and caches each
document and its cross-references. A meet is not a pin.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from jason.community.recorder import (
    DocType,
    FiledInstrument,
    Filing,
    IndexedInstrument,
    InstrumentDetail,
    NARROW_FILINGS,
    Sacramento,
    closing_numbers,
    index_name,
    instrument_kind,
    relate_instruments,
    same_party,
)
from jason.community.tax import parcel_number

_NOT_A_PIN = "A hit is not a pin. Keep it when a later detail shows this parcel's APN."


def recorder_search(
    number: str = "",
    name: str = "",
    text: str = "",
    filing: str = "",
    after: str = "",
    before: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """Search the Sacramento public index by document number or party name.

    Pass a twelve-digit document number, or a party name. ``text`` keeps a
    hit only when that second name is the same party. ``filing`` is a code
    such as ``685`` or a name such as ``GRANT_DEED``. A name that matches
    more rows than ``limit`` is wide: the rows come back only for a grant
    deed, a quitclaim, or a UCC filing, and a filing that is still wide is
    omitted. A second name reads the whole name search, so pass a filing and
    a date range with it. A developer name is searched when it is typed here.
    A hit is not a pin.
    """
    return _search(
        Sacramento.county_recorder,
        number=number,
        name=name,
        text=text,
        filing=filing,
        after=after,
        before=before,
        limit=limit,
    )


def recorder_detail(number: str) -> dict[str, Any]:
    """One instrument: APN, parties, and the document numbers it cites.

    Use this on a gap deed. The cited numbers are the next documents to load.
    A hit is not a pin.
    """
    return _detail(Sacramento.county_recorder, number)


def recorder_around(number: str, issued: str = "") -> dict[str, Any]:
    """The subject, the same-day numbers beside it, and the documents it cites.

    A deed of trust is a buyer lien when its trustor is the grant's grantee.
    A same-day number whose parties do not match is someone else's instrument.
    A reconveyance cites the deed of trust it releases. ``issued`` is
    ``YYYY-MM-DD``. A cited instrument recorded before that day is a different
    property. A hit is not a pin.
    """
    stamp = "".join(ch for ch in number if ch.isdigit())
    if len(stamp) != 12:
        return {"number": number, "found": False, "error": "A Sacramento document number is twelve digits.", "links": []}
    opened = _day(issued) if issued.strip() else None
    if issued.strip() and opened is None:
        return {"number": stamp, "found": False, "error": "issued is YYYY-MM-DD.", "links": []}
    recorder = Sacramento.county_recorder
    subject = _filed(recorder, stamp)
    if subject is None:
        return {"number": stamp, "found": False, "links": [], "note": _NOT_A_PIN}
    wanted = [item for item in closing_numbers(stamp) if item]
    wanted.extend(number for number in subject.cross_references if number not in wanted and number != stamp)
    others = tuple(item for number in wanted if (item := _filed(recorder, number)) is not None)
    links = relate_instruments(subject, others, issued=opened)
    return {
        "number": stamp,
        "found": True,
        "issued": opened.isoformat() if opened else "",
        "links": [_link_body(item) for item in links],
        "note": _NOT_A_PIN,
    }


def recorder_descend(
    number: str,
    depth: int = 4,
    developer_depth: int = 2,
    after: str = "",
) -> dict[str, Any]:
    """Walk out from this deed and from the developer, one step at a time.

    Each step searches the grantors and grantees reached so far and stores
    the documents and their cross-references. A lender is not searched. The
    developer side stops after ``developer_depth`` resales. A meet is not a
    pin and is not stored.
    """
    stamp = "".join(ch for ch in number if ch.isdigit())
    if len(stamp) != 12:
        return {"number": number, "meets": [], "error": "A Sacramento document number is twelve digits."}
    if depth < 1:
        return {"number": stamp, "meets": [], "error": "depth starts at 1."}
    if developer_depth < 0:
        return {"number": stamp, "meets": [], "error": "developer_depth starts at 0."}
    opened = _day(after) if after.strip() else None
    if after.strip() and opened is None:
        return {"number": stamp, "meets": [], "error": "after is YYYY-MM-DD."}
    from jason.community import community as active
    from jason.community.index_cache import IndexCache, descend
    from jason.config import Settings

    community = active()
    if opened is None:
        issued = [report.issued for report in community.public_reports() if report.issued is not None]
        opened = min(issued) if issued else None
    cache_path = Settings.load().ownership_db.parent / "index-cache.db"
    with IndexCache(cache_path) as cache:
        found = descend(
            Sacramento.county_recorder,
            cache,
            current=(stamp,),
            developers=community.developers(),
            after=opened,
            depth=depth,
            developer_depth=developer_depth,
        )
        cached = cache.count()
    return {
        "number": stamp,
        "depth": found.depth,
        "cached": cached,
        "current": list(found.current),
        "developerCount": len(found.developer),
        "meets": [
            {
                "kind": item.kind,
                "current": item.current,
                "developer": item.developer,
                "numbers": list(item.numbers),
            }
            for item in found.meets
        ],
        "note": "A meet is not a pin and is not stored.",
    }


def recorder_priors(name: str, before: str, filing: str = "685", limit: int = 20) -> dict[str, Any]:
    """Grant deeds before ``before`` on which ``name`` is the grantee.

    ``before`` is ``YYYY-MM-DD``. These rows are candidates for the deed that
    conveyed the property to that party. They are not a chain. Keep a row
    when its detail APN is the parcel being searched.
    """
    return _priors(
        Sacramento.county_recorder,
        name=name,
        before=before,
        filing=filing,
        limit=limit,
    )


def _search(
    recorder,
    *,
    number: str,
    name: str,
    text: str,
    filing: str,
    after: str,
    before: str,
    limit: int,
) -> dict[str, Any]:
    stamp = "".join(ch for ch in number if ch.isdigit())
    party = " ".join(name.split())
    if not stamp and not party:
        return {"error": "Pass a document number or a party name.", "hits": []}
    code = _filing(filing)
    if filing.strip() and code is None:
        return {"error": f"Unknown filing {filing.strip()}.", "hits": []}
    start = _day(after)
    end = _day(before)
    if after.strip() and start is None:
        return {"error": "after is YYYY-MM-DD.", "hits": []}
    if before.strip() and end is None:
        return {"error": "before is YYYY-MM-DD.", "hits": []}
    cap = _cap(limit)
    if text.strip() and party:
        rows = recorder.search(name=party, filing=code, text=text, after=start, before=end)
        return {
            "query": party,
            "text": " ".join(text.split()),
            "wide": False,
            "total": len(rows),
            "hits": [_hit(row) for row in rows],
            "note": _NOT_A_PIN,
        }
    if stamp:
        rows = recorder.search(number=stamp, filing=code, after=start, before=end, limit=cap)
        return {"query": stamp, "wide": False, "total": len(rows), "hits": [_hit(row) for row in rows], "note": _NOT_A_PIN}
    if code is not None:
        rows = recorder.search(name=party, filing=code, after=start, before=end, limit=cap)
        return {
            "query": party,
            "wide": len(rows) >= cap,
            "total": len(rows),
            "hits": [_hit(row) for row in rows],
            "note": _NOT_A_PIN,
        }
    found = recorder.for_parties(
        (party,),
        after=start,
        before=end,
        limit=cap,
        filings=NARROW_FILINGS,
    )
    if not found:
        return {"query": party, "wide": False, "total": 0, "hits": [], "note": _NOT_A_PIN}
    result = found[0]
    return {
        "query": result.query,
        "wide": result.wide,
        "total": result.total,
        "hits": [_hit(row) for row in result.rows],
        "note": _NOT_A_PIN,
    }


def _filed(recorder, number: str) -> FiledInstrument | None:
    rows = recorder.search(number=number, limit=5)
    if not rows:
        return None
    row = rows[0]
    detail = recorder.detail(row.internal_id) if row.internal_id else None
    if detail is None:
        return FiledInstrument(
            row.number or number,
            row.recorded,
            instrument_kind((row.filing_code,), (row.filing_name,)),
            row.grantors,
            row.grantees,
        )
    codes = tuple(item.code for item in detail.filings)
    descriptions = tuple(item.description for item in detail.filings)
    grantors, grantees, cited = _parties(detail)
    return FiledInstrument(
        detail.number or row.number or number,
        detail.recorded or row.recorded,
        instrument_kind(codes, descriptions),
        tuple(grantors or row.grantors),
        tuple(grantees or row.grantees),
        tuple(cited),
    )


def _link_body(item) -> dict[str, Any]:
    return {
        "number": item.number,
        "recorded": item.recorded.isoformat() if item.recorded else "",
        "kind": item.kind,
        "relation": item.relation,
        "grantorRole": item.grantor_role,
        "granteeRole": item.grantee_role,
        "grantors": list(item.grantors),
        "grantees": list(item.grantees),
        "crossReferences": list(item.cross_references),
        "beforeCommunity": item.before_community,
    }


def _detail(recorder, number: str) -> dict[str, Any]:
    stamp = "".join(ch for ch in number if ch.isdigit())
    if len(stamp) != 12:
        return {"number": number, "found": False, "error": "A Sacramento document number is twelve digits."}
    rows = recorder.search(number=stamp, limit=5)
    if not rows:
        return {"number": stamp, "found": False, "note": _NOT_A_PIN}
    row = rows[0]
    detail = recorder.detail(row.internal_id) if row.internal_id else None
    if detail is None:
        body = _hit(row)
        body["found"] = True
        body["crossReferences"] = []
        body["note"] = _NOT_A_PIN
        return body
    return _detail_body(detail, row)


def _priors(recorder, *, name: str, before: str, filing: str, limit: int) -> dict[str, Any]:
    party = " ".join(name.split())
    end = _day(before)
    if not party or end is None:
        return {"error": "Pass a party name and before as YYYY-MM-DD.", "hits": []}
    code = _filing(filing)
    if code is None:
        return {"error": f"Unknown filing {filing.strip()}.", "hits": []}
    query = index_name(party) or party
    cap = _cap(limit)
    rows = recorder.search(name=query, filing=code, before=end, limit=cap)
    kept = [
        row
        for row in rows
        if row.recorded is not None
        and row.recorded < end
        and any(same_party(query, grantee) for grantee in row.grantees)
    ]
    return {
        "query": query,
        "before": end.isoformat(),
        "total": len(kept),
        "wide": len(rows) >= cap,
        "hits": [_hit(row) for row in kept],
        "note": "A prior candidate is not a chain. Keep it when the detail APN is this parcel.",
    }


def _detail_body(detail: InstrumentDetail, row: IndexedInstrument) -> dict[str, Any]:
    grantors, grantees, cited = _parties(detail)
    apn = _apn(detail.apn)
    return {
        "number": detail.number or row.number,
        "found": True,
        "recorded": detail.recorded.isoformat() if detail.recorded else "",
        "apn": apn,
        "status": detail.status,
        "grantors": grantors or list(row.grantors),
        "grantees": grantees or list(row.grantees),
        "crossReferences": cited,
        "filings": [f"{item.code} {item.description}".strip() for item in detail.filings],
        "note": _NOT_A_PIN,
    }


def _parties(detail: InstrumentDetail) -> tuple[list[str], list[str], list[str]]:
    grantors: list[str] = []
    grantees: list[str] = []
    cited: list[str] = []
    for party in detail.parties:
        role = party.role.upper()
        if "GRANTOR" in role and party.name not in grantors:
            grantors.append(party.name)
        elif "GRANTEE" in role and party.name not in grantees:
            grantees.append(party.name)
        if party.cross_reference and party.cross_reference not in cited:
            cited.append(party.cross_reference)
    return grantors, grantees, cited


def _hit(row: IndexedInstrument) -> dict[str, Any]:
    return {
        "number": row.number,
        "recorded": row.recorded.isoformat() if row.recorded else "",
        "filing": row.filing_name or row.filing_code,
        "grantors": list(row.grantors),
        "grantees": list(row.grantees),
    }


def _filing(value: str) -> Filing | DocType | None:
    text = value.strip()
    if not text:
        return None
    token = text.upper().replace(" ", "_")
    for item in Filing:
        if item.value == text or item.name == token:
            return item
    for item in DocType:
        if item.code == text or item.name == token:
            return item
    return None


def _day(value: str) -> date | None:
    text = value.strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _cap(limit: int) -> int:
    return max(1, min(int(limit or 20), 40))


def _apn(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) != 14:
        return ""
    return parcel_number(digits)
