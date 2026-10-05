"""The board packet: each agenda item researched in depth, for the directors to read before the meeting.

For every action item on the agenda (proposed or on agenda, ``data/board/items.json``) the packet gives:

- **Background** and **the question for the board**, from the item;
- **The law**: each section the item's authority cites, quoted from the statute pages jason keeps (``data/authorities``,
  ``jason export-authorities``), trimmed to the subdivisions cited;
- **What the records show now**: the facts re-read from the review that found the item (the cost centers, the reserve
  transfers, the deadlines, the developer securities, the insurance), so the packet is as current as the data on disk;
- **Evidence** to open: the documents and commands behind the item;
- **Options** and a **draft motion** for the secretary to adapt, with any notice the item needs of its own;
- **Deadlines**.

Executive session items are listed by their Civil Code 4935 subject in general words only, never by title
(``meeting_agenda.executive_lines``); their research goes to the directors separately (CIV 4935(e)). The
packet reads disk only and decides nothing: the options are the board's to weigh, and a draft motion is a starting point.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any, Callable

from jason.community.board_items import PRIORITY_ORDER, BoardItem, ItemStatus, Session, agenda_session
from jason.community.legal_cases import settled_lines

def citations(authority: str) -> list[tuple[str, str]]:
    """("CIV 5515", "(d)") pairs from an authority string ("CIV 5515(d), (e); 5510"), read by the one citation
    grammar (``references.STATUTE_IN_TEXT``): a section whose number ends in a letter keeps it ("CIV 2924f")."""
    from jason.community.references import ABBREVIATIONS, SECTION_NUMBER, STATUTE_IN_TEXT, statute_citation

    found, code = [], ""
    for part in re.split(r"[;,]", authority or ""):
        part = part.strip()
        whole = statute_citation(part)
        m = STATUTE_IN_TEXT.search(part)
        if whole is not None and (whole.code in ABBREVIATIONS or whole.code.endswith(" CCR")):
            code = whole.code                    # the part is one citation: "Civil Code section 5515(d)", "10 CCR 2792.23"
            found.append((whole.base, whole.subdivisions))
        elif m:
            code = m.group("code")
            found.append((f"{code} {m.group('number')}", m.group("subs").replace(" ", "")))
        elif code:
            bare = re.match(rf"^({SECTION_NUMBER})((?:\([a-z0-9]+\))*)$", part)
            if bare and re.match(r"\d{3,5}(?!\d)", part):
                found.append((f"{code} {bare.group(1)}", bare.group(2)))
            elif re.match(r"^\([a-z0-9]+\)", part) and found:
                last, sub = found[-1]
                found[-1] = (last, sub + part)
    return found


def statute_excerpt(data_dir: Path, citation: str, subdivisions: str = "", *, limit: int = 1800) -> str:
    """The section's words, trimmed to the cited top-level subdivisions ("(d)(e)") when given.

    A section the publication prints in two versions under one number is quoted as the version in force today,
    followed by jason's note saying which it is and why (the versions' own operative words). Where the disk does not
    decide, each version's words are given under its own label: never the first alone."""
    from jason.tasks.export_authorities import authority_text, version_label

    found = authority_text(Path(data_dir), citation)
    if not found.get("found"):
        return ""
    if found.get("undecided"):
        return " ".join(f"{version_label(row['label'])} {_excerpt(row.get('text', ''), subdivisions, limit)}"
                        for row in found.get("versions") or [])
    excerpt = _excerpt(str(found.get("text", "")), subdivisions, limit)
    return excerpt + (f" {version_label(found['version'])}" if found.get("version") else "")


def _excerpt(words: str, subdivisions: str, limit: int) -> str:
    text = " ".join(words.split())
    # A subdivision starts the text or follows a sentence's end; "(b) of Section 5300" in a lead-in is a reference, not one.
    start = r"(?:^|(?<=[.:;]\s)|(?<=\)\s))"
    wanted = re.findall(r"\(([a-z])\)((?:\(\d+\))?)", subdivisions)
    if wanted:
        pieces = []
        for letter, paragraph in dict.fromkeys(wanted):
            m = re.search(rf"{start}\({letter}\)\s(.*?)(?=\s\([a-z]\)\s[A-Z]|$)", text)
            if not m:
                continue
            body = m.group(1)
            number = paragraph.strip("()")
            if number:
                p = re.search(rf"\({number}\)\s(.*?)(?=\s\({int(number) + 1}\)\s|$)", body)
                pieces.append(f"({letter})({number}) {p.group(1)}" if p else f"({letter}) {body}")
            else:
                pieces.append(f"({letter}) {body}")
        text = " ".join(pieces) or text
    return text[:limit] + ("..." if len(text) > limit else "")


# Researchers: re-read the facts behind an item from the review that found it.

def _cost_centers(data_dir: Path, community: Any) -> list[str]:
    from jason.tasks.cost_centers import review

    r = review(data_dir, community)
    out = [f"{c['center']}: A.C.A. {', '.join(map(str, c['acas']))}, {c['units']} units" for c in r.get("centers", [])]
    return out + r.get("findings", [])


def _reserve_transfers(data_dir: Path, community: Any) -> list[str]:
    from jason.tasks.reserve_transfers import review

    r = review(data_dir, community)
    out = []
    for b in r.get("borrowings", []):
        state = f"restored {b['repaidOn']}" if b["repaidOn"] else f"outstanding ${b['outstandingCents'] / 100:,.2f}"
        out.append(f"{b['day']} borrowing ${b['cents'] / 100:,.2f}: due back {b['deadline']}; {state}")
        out.extend(f"  - {g}" for g in b.get("gaps", []))
    for y in r.get("budgetYears", []):
        out.append(f"{y['year']}: contributions budgeted ${y['contributionBudgetCents'] / 100:,.2f}, paid ${y['contributionPaidCents'] / 100:,.2f}")
    return out


def _deadlines(words: tuple[str, ...]) -> Callable[[Path, Any], list[str]]:
    def research(data_dir: Path, community: Any) -> list[str]:
        from jason.tasks.deadlines import calendar

        rows = calendar(data_dir, community).get("obligations", [])
        return [f"{r['name']}: {r['standing']}, next {r.get('next') or '-'}, last {r.get('lastDone') or '-'}" + (f". {r['note']}" if r.get("note") else "")
                for r in rows if any(w in r["name"].lower() for w in words)]
    return research


def _securities(data_dir: Path, community: Any) -> list[str]:
    from jason.tasks.developer_security import register

    r = register(data_dir, community)
    return [f"bond {b['number']} phase {b['phase'] or '?'} {b['type'] or ''} {'$' + format(b['penalSumCents'] / 100, ',.2f') if b['penalSumCents'] else ''}: "
            f"{b['status']}" for b in r.get("bonds", [])]


def _legal_case(key: str) -> Callable[[Path, Any], list[str]]:
    def research(data_dir: Path, community: Any) -> list[str]:
        case = next((c for c in community.legal_cases() if c.key == key), None)
        if case is None:
            return []
        out = [f"{case.forum.value}{' ' + case.case_number if case.case_number else ''}; the association is {case.role.value}; {case.status.value}"]
        out += [f"{e.day} {e.step}" for e in case.events]
        if case.net_cents is not None:
            out.append(f"gross ${(case.gross_cents or 0) / 100:,.2f}; net ${case.net_cents / 100:,.2f} to {case.proceeds_account}")
        out += [f"{d.statute}: {'not met' if d.met is False else 'not shown'}: {d.evidence}" for d in case.open_duties]
        return out + settled_lines(case)
    return research


def _meeting_recordings(data_dir: Path, community: Any) -> list[str]:
    """What the association's Zoom account and jason's copy hold, from the last `jason zoom` sync."""
    from jason.tasks.zoom import confidential_mentions, load_index, zoom_dir

    index = load_index(data_dir)
    if not index:
        return ["no Zoom sync on disk; run `jason zoom`"]
    rows = [r for r in index.get("meetings", []) if r.get("cloud")]
    media = [r for r in rows if {"MP4", "M4A"} & set(r["cloud"])]
    out = [f"Zoom's cloud holds audio or video for {len(media)} meetings "
           f"({min(r['date'] for r in media)} to {max(r['date'] for r in media)}), as of {rows[0].get('cloudCheckedAt')}"] if media else []
    held = [r for r in index["meetings"] if (r.get("files") or {}).get("transcript")]
    exec_rows = [r for r in held if confidential_mentions(zoom_dir(data_dir), r)]
    out.append(f"jason's copy (data/zoom) holds {len(held)} transcripts; {len(exec_rows)} mention an executive session or a "
               f"hearing: {', '.join(r['date'] for r in exec_rows)}")
    summaries = [r for r in index["meetings"] if (r.get("files") or {}).get("summary")]
    out.append(f"AI Companion summaries held: {len(summaries)}")
    from jason.tasks.meeting_catalog import load as load_catalog

    catalog = load_catalog(data_dir)
    drive = sorted({m["date"] for m in catalog.get("meetings", []) for r in m["records"]
                    if r["where"] == "Drive" and r["kind"] in ("audio recording", "video recording", "transcript")})
    if drive:
        out.append(f"Drive holds recordings or transcripts of {len(drive)} meetings ({drive[0]} to {drive[-1]}), including the "
                   "May 20 and June 17, 2025 recordings filed with the 26CV016125 matter (`jason meetings`)")
    return out


def _minutes_recaps(data_dir: Path, community: Any) -> list[str]:
    """The posted minutes that carry Zoom's AI recap naming executive-session subjects, from the meeting catalog."""
    from jason.tasks.meeting_catalog import load as load_catalog

    out = []
    for m in load_catalog(data_dir).get("meetings", []):
        recaps = [r for r in m["records"] if r["kind"] == "minutes" and r["note"].startswith("AI recap") and "names" in r["note"]]
        if recaps:
            places = sorted({r["location"].split("/")[0] for r in recaps})
            out.append(f"{m['date']}: {recaps[0]['note'].split('; ', 1)[1]}; posted in {', '.join(places)}")
    return out or ["no posted minutes with an AI recap naming executive subjects (run `jason meetings`)"]


def _meeting_notices(data_dir: Path, community: Any) -> list[str]:
    """Each meeting's notice timing and delivery, and the meetings with no minutes, from the meeting catalog."""
    from jason.tasks.meeting_catalog import load as load_catalog

    out = []
    for m in load_catalog(data_dir).get("meetings", []):
        for c in m["checks"]:
            if c.startswith(("the notice went", "no notice to members", "PayHOA's email notice failed", "no minutes found")):
                out.append(f"{m['date']}: {c.split(';')[0]}")
    return out or ["no notice or minutes findings (run `jason meetings --sync`)"]


RESEARCHERS: dict[str, Callable[[Path, Any], list[str]]] = {
    "meeting-notice-and-minutes": _meeting_notices,
    "minutes-ai-recap-executive": _minutes_recaps,
    "meeting-recordings-retention": _meeting_recordings,
    "settlement-disclosure-6100": _legal_case("watt-construction-defects-2022"),
    "defect-repairs-and-941-review": _legal_case("watt-construction-defects-2022"),
    "cost-centers-not-kept": _cost_centers,
    "reserve-loan-march-2024": _reserve_transfers,
    "due-to-reserve-6531": _reserve_transfers,
    "fire-sprinkler-inspections": _deadlines(("sprinkler",)),
    "fire-alarm-deficiencies": _deadlines(("fire alarm",)),
    "insurance-renewals-2026": _deadlines(("insurance renewal",)),
    "developer-bond-phase-7": _securities,
}

# Options and a draft motion, by item; an item without one gets the generic frame.
OPTIONS: dict[str, tuple[list[str], str]] = {
    "reserve-loan-march-2024": (["Adopt a repayment plan restoring the $16,000 to reserves by a set date",
                                 "Find, with documentation, that a temporary delay is in the association's best interest (5515(d))",
                                 "Levy a special assessment to recover the funds (5515(e); limits in 5605)",
                                 "Establish first whether the loan was repaid in a way the records do not show"],
                                "Move that the board direct the treasurer to account for the $16,000 transferred from reserves on March 14, "
                                "2024, and adopt the following plan to restore it to the reserve fund by ______: ______."),
    "cost-centers-not-kept": (["Refer to counsel for an opinion on the annexations' cost center requirement and past allocations",
                               "Direct the budget committee to present the 2027 budget with the General, Phases 1 and 2, and Annexed "
                               "Property components", "Direct the reserve preparer to separate the cost centers' components and funding"],
                              "Move that the board refer the cost center requirement of the declarations of annexation (section 1.3) to "
                              "counsel and direct that the 2027 budget and reserve funding plan be prepared with the cost centers kept apart."),
    "settlement-disclosure-6100": (["Direct counsel to prepare a supplemental 6100(a) disclosure to members (amendments are allowed and "
                                    "keep their privilege, 6100(b), (c))",
                                    "Direct the manager or secretary to add the latest 6100 information to every resale packet (4525(a)(7))",
                                    "Direct the reserve preparer to itemize the unspent settlement funds separately (4177(b), 5565(b)(3))",
                                    "Ask counsel first whether any defects were corrected, which would narrow the disclosure"],
                                   "Move that the board direct counsel to prepare, for the board's review, a supplemental disclosure to "
                                   "the members under Civil Code 6100 of the October 2023 settlement with the builder; that the latest "
                                   "6100 information be included in every resale disclosure packet under Civil Code 4525(a)(7); and that "
                                   "the reserve study preparer itemize the unspent settlement funds separately under Civil Code 4177(b) "
                                   "and 5565(b)(3)."),
    "defect-repairs-and-941-review": (["Adopt a repair plan by priority within the settlement funds (the settled items were "
                                       "priced well above the net received), starting with site drainage and the garage entry "
                                       "aprons",
                                       "Decide whether the 2023-2024 JB Bostick concrete and seal coat work counts against the "
                                       "settlement funds, and have the treasurer track the remaining funds as their own fund",
                                       "Ask counsel in writing to prepare or review the repair contracts under the fee "
                                       "agreement's post-recovery scope, and for the signed fee agreement",
                                       "Calendar a building-condition review with counsel before the first 10-year date",
                                       "Discuss the scope and the cost of repair in executive session: the pricing is marked "
                                       "for mediation only (Evidence Code 1119)"],
                                      "Move that the board ask Berding & Weil to confirm in writing that drafting, review, and "
                                      "negotiation of contracts to repair the items released in the October 2023 settlement fall "
                                      "within its contingency fee agreement, and to provide the signed agreement; direct [a "
                                      "director] to obtain proposals for the site drainage and garage entry repairs for the "
                                      "board's review; and schedule a review of building conditions with counsel before "
                                      "February 2029."),
    "minutes-ai-recap-executive": (["Direct the Secretary to replace the posted minutes (PayHOA Meetings and Resale Documents) with "
                                    "versions that note executive session matters only generally, keeping the originals preserved "
                                    "under the litigation hold",
                                    "Stop appending Zoom's AI recap to the minutes; prepare minutes from the template (motions, "
                                    "roll-call votes, a general note of the executive session)",
                                    "Ask counsel whether members or buyers who received the resale packets need a notice"],
                                   "Move that the board direct the Secretary to (1) prepare corrected minutes for each meeting whose "
                                   "posted minutes carry Zoom's AI recap, noting executive session matters only generally (Civil Code "
                                   "4935(e)), for approval at the next meeting; (2) replace the posted copies once approved, keeping "
                                   "the originals preserved; and (3) no longer append AI summaries to minutes."),
    "meeting-recordings-retention": (["Adopt a meeting records policy: approved minutes are the only record of proceedings; the "
                                      "Secretary records open sessions only, announced, solely to prepare minutes; the recording, "
                                      "transcript, and any AI summary are deleted within 30 days after the minutes are approved, "
                                      "except anything under a litigation hold",
                                      "Keep transcripts and AI summaries of open sessions as working papers, access limited to "
                                      "directors, deleted on a fixed schedule; recordings deleted after the minutes",
                                      "Turn off Zoom AI Companion and stop cloud recording before adjourning to executive session, "
                                      "or hold executive session as a separate unrecorded meeting; never record hearings or counsel",
                                      "Before deleting anything, ask defense counsel to confirm a litigation hold for the "
                                      "26CV016125 matter and release what is not needed"],
                                     "Move that the board (1) direct that no meeting recording, transcript, AI summary, or chat be "
                                     "deleted until defense counsel for 26CV016125 confirms in writing what must be preserved; (2) "
                                     "direct the Secretary to turn off Zoom AI Companion and to stop recording before any executive "
                                     "session; and (3) direct the Secretary to present a meeting records policy for adoption at the "
                                     "next meeting."),
    "meeting-schedule-resolution": (["Adopt a resolution fixing regular meetings on the third Tuesday of every month at 7:00 pm on Zoom",
                                     "Keep the quarterly schedule and notice the other months as special meetings"],
                                    "Move that the board adopt an administrative resolution fixing regular board meetings on the third "
                                    "Tuesday of each month at 7:00 pm by teleconference, superseding Resolution 20230130-1 as to regular meetings."),
    "fire-sprinkler-inspections": (["Engage a State Fire Marshal licensed (A or C-16) firm for the annual inspection and test now",
                                    "Contract the quarterly inspections, or train a person to do them (19 CCR 904.1)",
                                    "Schedule the five-year internal inspection"],
                                   "Move that the board authorize the treasurer to engage ______ for the annual fire sprinkler inspection and "
                                   "test of buildings 3 and 8, not to exceed $______, and to arrange the quarterly inspections."),
}


def item_section(item: BoardItem, data_dir: Path, community: Any, *, n: int, meeting: date | None = None) -> list[str]:
    out = [f"## {n}. {item.title}", "", f"_Priority: {item.priority.value}. Category: {item.category.value}._", "", "**Background.** " + item.summary,
           "", "**The question for the board.** " + item.ask, ""]
    cites = citations(item.authority)
    if item.authority:
        out.append(f"**The law.** {item.authority}")
        for cite, sub in cites:
            excerpt = statute_excerpt(data_dir, cite, sub)
            if excerpt:
                out.append(f"> **{cite}{sub}.** {excerpt}")
        out.append("")
    research = RESEARCHERS.get(item.id)
    if research is not None:
        try:
            facts = research(Path(data_dir), community)
        except Exception as exc:  # the packet still stands without one item's live facts
            facts = [f"(could not re-read: {exc})"]
        if facts:
            out.append("**What the records show now.**")
            out.extend(f"  - {f.strip()[2:]}" if f.startswith("  - ") else f"- {f}" for f in facts)
            out.append("")
    if item.notes:
        # the board's notes, with any {REPORT:key} run now (live_reports): the facts as of the packet, not the note
        from jason.tasks.live_reports import expand

        notes = expand(item.notes, Path(data_dir), community, context={"on": meeting or date.today()})
        out.append("**Notes.** " + notes[0] if notes else "**Notes.**")
        out += notes[1:] + [""]
    if item.evidence:
        out.append("**Evidence.** " + "; ".join(item.evidence))
        out.append("")
    options, motion = OPTIONS.get(item.id, ([], ""))
    out.append("**Options.**")
    out.extend(f"{k}. {o}" for k, o in enumerate(options or ["Act as asked", "Refer for more information (to a committee, counsel, or a vendor)",
                                                            "Defer to a later meeting"], start=1))
    out.append("")
    out.append("**Draft motion.** " + (motion or f"Move that the board {item.ask[0].lower() + item.ask[1:]}"))
    if item.special_notice:
        out.append("")
        out.append(f"**Notice.** The agenda must carry: {item.special_notice}.")
    if item.due:
        out.append("")
        out.append(f"**Deadline.** {item.due.isoformat()}" + (" (passed)" if item.due < date.today() else ""))
    out.append("")
    return out


def _planned_subjects(data_dir: Path, meeting: date) -> dict[str, Any]:
    """The 4935 subject the meeting's agenda plan gives each board item, by item id; none when there is no plan."""
    from jason.tasks import agenda_plan

    try:
        plan = agenda_plan.load(Path(data_dir), meeting.isoformat())
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {k: v.get("subject") for k, v in (plan.get("items") or {}).items() if isinstance(v, dict) and v.get("subject")}


def packet(data_dir: Path, community: Any, meeting: date) -> list[str]:
    from jason.tasks.board_items import load

    items = sorted((i for i in load(data_dir) if i.status in (ItemStatus.PROPOSED, ItemStatus.ON_AGENDA)),
                   key=lambda i: (PRIORITY_ORDER[i.priority], i.id))
    open_items = [i for i in items if agenda_session(i) is Session.OPEN]
    executive = [i for i in items if agenda_session(i) is Session.EXECUTIVE]
    out = [f"# Board packet: {meeting:%B} {meeting.day}, {meeting.year}", "",
           "**Confidential: for the directors and counsel. Not for posting or forwarding; parts draw on privileged advice and "
           "on figures shared for mediation only (Evidence Code 1119).**", "",
           "_Prepared by jason from the association's records for the directors. Research, not advice: the options are the board's to "
           "weigh, statute text is quoted from the stored pages, and counsel's reading governs._", "", "## Contents", ""]
    out += [f"{k}. {i.title} ({i.priority.value})" for k, i in enumerate(open_items, start=1)]
    if executive:
        # By each matter's 4935 subject in the statute's words, never its title: a packet can be forwarded or served
        # beyond the directors, and a title can name the member, the party, or the matter (CIV 4935(e)).
        from jason.tasks.meeting_agenda import executive_lines
        out += ["", "Executive session (research provided to the directors separately):"]
        out += [f"- {line}" for line in executive_lines([], executive, _planned_subjects(data_dir, meeting))]
    out.append("")
    standing = getattr(community, "packet_reports", lambda: ())()
    if standing:
        # the reports every packet carries (the treasurer's report as PayHOA ran it), shown as already built
        from jason.tasks.live_reports import expand

        out += ["## Reports", ""]
        for ref in standing:
            out += expand(ref, Path(data_dir), community, context={"on": meeting}) + [""]
    for k, item in enumerate(open_items, start=1):
        out += item_section(item, Path(data_dir), community, n=k, meeting=meeting)
    return out


__all__ = ["packet", "item_section", "citations", "statute_excerpt", "RESEARCHERS", "OPTIONS"]
