"""The Life safety screen's loader (``GET /api/life-safety``; docs/console/screens/life-safety.md): each system the
profile lists with its schedule, the periods that have a report on file, the reports jason could not place, the questions a
fact it lacks leaves, and beside them the backflow program, the watchlist, and the vendor's report portal.

It composes what the CLI already reads (``jason.tasks.inspections.review``, which carries each obligation's row of
``jason deadlines``; ``jason.tasks.backflow``; ``jason.tasks.report_portals``) and works out nothing a view must: every
standing is a word, every count is made here, and the view does no date arithmetic. Disk only: nothing calls Gmail, Drive,
PayHOA, or a vendor's portal; a sync, a filing plan, and a fetch are jobs a person starts with the command the answer names.

**The deficiency register** (``jason.tasks.deficiencies``, ``data/life-safety/deficiencies.json``) is read here. Which
deficiencies impair a safeguard, what cleared each, and whether the insurer was told may bear on a claim, so that detail is
P2 (members' submissions, under a legal hold): a viewer whose office does not open it gets the proposed, open, and cleared counts and ``held`` instead, and the
impairment and insurer counts are ``null``, never a bare zero.

**What is not composed yet** is listed under ``notComposed`` with its reason: the insurer's condition from the policy pages,
the vendors' licences and what each is paid (P1 amounts), and the board items about these systems.

Signed-in roster people read it (a report names buildings and dates, not units). A report's file name is shown as filed;
a code that appears in a record is never shown here (``document_codes`` lists such records by name only).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

Args = dict[str, str]

# The deadlines calendar's standing words, as this screen says them (docs/console/screens/life-safety.md, "Status and time").
STANDING_WORDS = {"done": "current", "done late": "done late", "upcoming": "upcoming", "due soon": "due soon",
                  "overdue": "overdue", "date not on record": "needs input", "no evidence": "no evidence"}
NONE_ON_RECORD = "none on record"
RANK = {"overdue": 0, "due soon": 1, "needs input": 2, NONE_ON_RECORD: 3, "no evidence": 3, "done late": 4, "upcoming": 5,
        "current": 6}

NOT_COMPOSED = (
    {"part": "insurer", "reason": "The insurer's condition is read from the policy pages by the insurance review; it is not "
     "composed here yet.", "command": "jason insurance"},
    {"part": "vendors", "reason": "Licences as read and what each vendor is paid (P1) are not composed here yet.",
     "command": "jason vendors"},
    {"part": "boardItems", "reason": "The board items about these systems are on the Actions screen.",
     "command": "jason board"},
)
CAVEATS = (
    "A record kept outside jason's stores is not seen: \"none on record\" never reads as \"not done\".",
    "Nothing here calls Gmail, Drive, PayHOA, or a vendor's portal. A sync is a person's job; each command is named.",
    "A report jason could not read is listed by name as not read, and one it could not place as unplaced with the field "
    "its reading lacks. Neither is put in a period by its file name.",
    "A standing is the deadlines calendar's, said in this screen's words; a fact the profile lacks is \"needs input\" with the "
    "question that supplies it.",
)


def standing_of(obligation: dict[str, Any]) -> str:
    """One obligation's standing word: the calendar's, else \"none on record\" (no row, or no store shows it)."""
    cal = obligation.get("calendar") or {}
    return STANDING_WORDS.get(str(cal.get("standing") or ""), NONE_ON_RECORD)


def _card(system: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for o in system["obligations"]:
        cal = o.get("calendar") or {}
        rows.append({"obligation": o["obligation"], "authority": o["authority"], "cadence": o["cadence"],
                     "standing": standing_of(o), "calendarStanding": cal.get("standing"), "next": cal.get("next"),
                     "daysLeft": cal.get("daysLeft"), "lastDone": cal.get("lastDone"), "counts": o["counts"],
                     "countedFrom": o["countedFrom"], "countedHow": o["countedHow"], "periods": o["periods"],
                     "earlier": o["earlier"]})
    worst = min((r["standing"] for r in rows), key=lambda w: RANK.get(w, 5), default=NONE_ON_RECORD)
    return {**system["system"], "standing": worst, "obligations": rows, "unassigned": system["unassigned"],
            "doesNotApply": system["doesNotApply"], "undetermined": system["undetermined"], "notRead": system["notRead"]}


def _backflow() -> Any:
    """The backflow program's reader, imported when asked: a checkout without it leaves those parts \"not read\"."""
    from jason.tasks import backflow

    return backflow


def _part(build: Any) -> dict[str, Any]:
    """A part that fails to read is an answer naming it, not a failed screen."""
    try:
        return build()
    except Exception as exc:  # noqa: BLE001 - one unreadable store leaves the others standing
        return {"found": False, "note": f"not read: {type(exc).__name__}"}


def compose(data_dir: Path, community: Any, *, today: date | None = None, system: str = "",
            private: bool = False) -> dict[str, Any]:
    """The screen's read for ``community``: the systems with their schedules and reports, the summary counts, the
    backflow program, the watchlist, the portal, and what is not composed. ``private`` is whether the viewer may see the
    impairment and insurer record (P2, under a legal hold)."""
    from jason.tasks import deficiencies as register
    from jason.tasks.inspections import review

    day = today or date.today()
    records = review(data_dir, community, as_of=day)
    if system:
        one = records.of(system)
        if one is None:
            return {"found": False, "asOf": day.isoformat(), "systems": [],
                    "note": f"no system {system!r}; the specification lists {', '.join(s.system.key for s in records.systems) or 'none'}"}
        records = one
    body = records.as_dict()
    cards = [_card(s) for s in body["systems"]]
    obligations = [o for c in cards for o in c["obligations"]]
    counts = {w: sum(1 for o in obligations if o["standing"] == w) for w in ("overdue", "due soon", "needs input", NONE_ON_RECORD)}
    portal = next((p for p in community.vendor_portals() if getattr(p, "reports", None)), None) if hasattr(community, "vendor_portals") else None

    def portal_part() -> dict[str, Any]:
        from jason.tasks.report_portals import filing_plan_view, portal_view

        if portal is None:
            return {"found": False, "note": "The specification names no vendor with a public report portal."}
        return {"portal": portal_view(data_dir, portal), "filingPlan": filing_plan_view(data_dir, portal.key)}

    reg = _part(lambda: register.view(data_dir, system=system, detail=private))
    counts_of = reg.get("counts") if reg.get("found") else None
    banner = [r["id"] for r in reg.get("rows", []) if r.get("insurerNotTold")] if private else []
    return {
        "found": body["community"] != "" or bool(cards), "asOf": day.isoformat(), "listed": records.listed,
        "community": body["community"],
        "summary": {"systems": len(cards), "obligations": len(obligations), "overdue": counts["overdue"], "dueSoon": counts["due soon"], "needsInput": counts["needs input"],
                    "noneOnRecord": counts[NONE_ON_RECORD],
                    "proposedDeficiencies": counts_of["proposed"] if counts_of else None,
                    "openDeficiencies": counts_of["open"] if counts_of else None,
                    "clearedDeficiencies": counts_of["cleared"] if counts_of else None,
                    "impairments": counts_of["impairments"] if counts_of and private else None,
                    "insurerNotTold": counts_of["insurerNotTold"] if counts_of and private else None, "unplaced": len(body["unplaced"]),
                    "questions": len(body["questions"])},
        "systems": cards, "unplaced": body["unplaced"], "recordKeeping": body["recordKeeping"],
        "questions": body["questions"], "otherFilings": body["otherFilings"], "sources": body["sources"],
        "backflow": _part(lambda: _backflow().view(data_dir, community, today=day)),
        "watchlist": _part(lambda: _backflow().watchlist(data_dir, community, today=day)),
        "portal": _part(portal_part),
        "deficiencies": reg,
        "banner": ({"ids": banner, "sentence": "A person recorded an impairment on a scheduled safeguard, and no record shows "
                    "the insurer was told."} if banner else None),
        "notComposed": list(NOT_COMPOSED),
        "empty": "" if cards else "The specification lists no life safety systems (Community.life_safety_systems()).",
        "caveats": [*CAVEATS, *body["caveats"]],
    }


def life_safety(args: Args) -> dict[str, Any]:
    """``GET /api/life-safety[?system=KEY]``: the screen's read, for a signed-in roster person (401 otherwise)."""
    from jason.community import community
    from jason.mcp.county import _data_dir
    from jason.web import access

    viewer = access.signed_in()
    private = access.may_see(viewer, access.Level.P2, private=access.private_window() is not None)[0]
    if private:
        try:
            access.served(viewer, access.Level.P2, address="api/life-safety")
        except OSError:
            private = False                # an opening that cannot be logged is not served
    return compose(Path(_data_dir(None)), community(), system=(args.get("system") or "").strip(), private=private)


ACTS = ("confirm", "impairs", "cleared", "insurer-told", "propose")
ACTING_REFUSED = "Viewing as {who} (admin view): the register is written in a person's own name. Go back to yourself first."


def write(key: str, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /api/write/life-safety/<deficiency id>`` with ``{act, ...}``: a person's entry in the deficiency register
    (``jason.tasks.deficiencies``), append only, in the name of whoever signed in (a ``by`` in the body is not trusted).
    ``act`` is ``confirm``; ``impairs`` (``value``: true or false); ``cleared`` (``record``, ``kind``, ``on``);
    ``insurer-told`` (``record``, ``on``); or ``propose`` (key ``propose``: read the reports' readings into proposed rows).
    For an office that opens P2, never while an admin views as someone else. jason contacts no insurer: this records what
    a person did."""
    from flask import abort

    from jason.community import community
    from jason.mcp.county import _data_dir
    from jason.tasks import deficiencies as register
    from jason.web import access

    viewer = access.signed_in()
    if viewer.acting:
        abort(access.refusal(403, ACTING_REFUSED.format(who=viewer.label)))
    ok, why = access.may_see(viewer, access.Level.P2, private=access.private_window() is not None)
    if not ok:
        abort(access.refusal(403, why))
    act, by, root = str(body.get("act") or "").strip(), viewer.account, Path(_data_dir(None))
    if act not in ACTS:
        raise ValueError(f"act is one of {', '.join(ACTS)}")
    if act == "propose":
        added = register.propose(root, community())
        return {"added": len(added), "ids": [r["id"] for r in added]}
    if act == "confirm":
        row = register.confirm(root, key, by=by)
    elif act == "impairs":
        if not isinstance(body.get("value"), bool):
            raise ValueError("value is true or false: whether it impairs a scheduled safeguard")
        row = register.set_impairs(root, key, body["value"], by=by)
    elif act == "cleared":
        row = register.clear(root, key, record=str(body.get("record") or ""), kind=str(body.get("kind") or ""),
                             on=str(body.get("on") or ""), by=by)
    else:
        row = register.insurer_told(root, key, record=str(body.get("record") or ""), on=str(body.get("on") or ""), by=by)
    return {**row, **register.state_of(row)}


__all__ = ["ACTS", "CAVEATS", "NONE_ON_RECORD", "NOT_COMPOSED", "STANDING_WORDS", "compose", "life_safety", "standing_of", "write"]
