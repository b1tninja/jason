"""Member elections: the inspector's certified results, the secret ballot, and the pre-ballot notice (Civil Code 5100-5145).

Directors are elected by secret ballot (5100(a)). An independent third party, one or three, is the inspector of
elections; the inspector receives and counts the ballots in public at a properly noticed open meeting and determines
the tabulated results, and the inspector's report is prima facie evidence of the facts it states (5110, 5120(a)). The
association gives general notice of the nomination procedure at least 30 days before the nomination deadline (5115(a));
of the ballot return date, time, and address, the counting meeting, the candidate list, and, where a quorum is
required, the 20 percent reconvened-meeting rule at least 30 days before ballots go out (5115(b)); and mails the ballots
at least 30 days before the voting deadline (5115(c)). The ballot does not identify the voter (5115(c)), and a ballot
that points to the election rules online says so in the words "The rules governing this election may be found here:"
(5105(h)(4)(B)(i)). Candidates may be seated by acclamation only after a 90-day initial notice and a 7-to-30-day
reminder (5103(b)). The results are reported to the board, recorded in the minutes of its next meeting, and given by
general notice within 15 days (5120(b)); the election materials are kept a year (5200(c)).

The readers follow Pro Elections LLC's layouts, the association's inspector since 2021: the "Official Election Results"
page (2023 on), the "Post-Election Results and Meeting Notice" (2021, acclamation), the two-sided secret ballot, and
the pre-ballot notice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from jason.community.document_models import (
    DocumentModel,
    Finding,
    ModelContext,
    Severity,
    date_after,
    dates_in,
    first,
    register,
    squash,
)
from jason.community.models.meetings import library_rows, library_text, normalize
from jason.community.reviews import AS_OF, RECORDS
from jason.community.symbols import DocumentKind

RESULTS_NOTICE_DAYS = 15      # CIV 5120(b)
BALLOT_DAYS = 30              # CIV 5115(b), (c)
NOMINATION_NOTICE_DAYS = 30   # CIV 5115(a)
ACCLAMATION_NOTICE_DAYS = 90  # CIV 5103(b)(1)
RULES_PHRASE = "the rules governing this election may be found here"


@dataclass(frozen=True)
class CandidateResult:
    name: str
    votes: int | None = None
    elected: bool = False
    tie_break: bool = False


@dataclass(frozen=True)
class MeasureResult:
    title: str
    yes: int | None = None
    no: int | None = None
    no_response: int | None = None
    outcome: str = ""               # as the inspector states it ("APPROVED")


@dataclass
class ElectionResults:
    inspector: str = ""
    inspector_name: str = ""
    association: str = ""
    election: str = ""
    election_date: date | None = None
    ownership_units: int | None = None
    ballots_received: int | None = None
    quorum_achieved: bool | None = None
    rescheduled: str = ""
    seats: int | None = None
    candidates: tuple[CandidateResult, ...] = ()
    measures: tuple[MeasureResult, ...] = ()
    acclamation: bool = False
    tie_break: str = ""
    term: str = ""
    certified: bool = False
    call_for_candidates: date | None = None
    reminder_notice: date | None = None
    nomination_deadline: date | None = None
    pre_ballot_notice: date | None = None
    ballot_package: date | None = None
    ballot_tally: date | None = None


@dataclass
class Ballot:
    inspector: str = ""
    association: str = ""
    election: str = ""
    secret: bool = False
    seats: int | None = None
    cumulative_voting: bool = False
    max_votes: int | None = None
    candidates: tuple[str, ...] = ()
    measures: tuple[str, ...] = ()
    due: date | None = None
    due_time: str = ""
    count_date: date | None = None
    count_time: str = ""
    count_online: bool = False
    count_location: str = ""
    quorum_ballots: int | None = None
    quorum_rule: str = ""
    rules_phrase: bool = False
    voter_identified: bool = False
    amendment_text: bool = False


@dataclass
class PreBallotNotice:
    inspector: str = ""
    association: str = ""
    election: str = ""
    notice_date: date | None = None
    ballots_mailed: date | None = None
    candidates: tuple[str, ...] = ()
    seats: int | None = None
    corrections_deadline: date | None = None
    return_deadline: date | None = None
    return_time: str = ""
    return_address: bool = False
    count_date: date | None = None
    count_time: str = ""
    count_online: bool = False
    reconvene_statement: bool = False
    reconvene_quorum: str = ""
    voter_list_verification: bool = False


def _int(pattern: str, text: str) -> int | None:
    v = first(pattern, text)
    return int(v) if v.isdigit() else None


def _inspector(text: str) -> str:
    if re.search(r"PRO ELECTIONS|Pro Elections|PROFESSIONAL\s+(?:\n\s*PO Box[^\n]*\n[^\n]*\n\s*)?ELECTION INSPECTORS|pro-ei\.com", text):
        return "Pro Elections LLC"
    return first(r"([A-Z][\w&.,' ]+(?:LLC|Inc\.?))[^\n]*\n[^\n]*Inspector of Elections", text, flags=0)


@AS_OF.check("election-materials", ElectionResults, fields=("election_date",))
def election_materials(r, as_of: date, _facts=None) -> list[Finding]:
    """As of a date: whether the year for keeping the election's materials is still running."""
    if not r.election_date:
        return []
    keep = r.election_date.replace(year=r.election_date.year + 1)
    if as_of <= keep:
        return [Finding("keep-election-materials", f"keep the ballots, envelopes, voter list, and tally until {keep}",
                        Severity.INFO, "CIV 5200(c), 5125")]
    return []


def next_board_meeting(r, records) -> dict[str, Any] | None:
    """From the library: the board's next meeting after the election (the first agenda or minutes the library dates
    after it), that meeting's minutes when they are on file (their name), and whether they speak of the election. None
    with no election date or no library."""
    if records.data_dir is None or r.election_date is None:
        return None
    later = sorted(str(x.get("period")) for x in library_rows(records, (DocumentKind.MINUTES, DocumentKind.AGENDA))
                   if len(str(x.get("period") or "")) == 10 and str(x.get("period")) > r.election_date.isoformat())
    if not later:
        return {"meeting": None, "minutes": None, "mentions_election": False}
    minutes = library_rows(records, (DocumentKind.MINUTES,), date.fromisoformat(later[0]))
    if not minutes:
        return {"meeting": later[0], "minutes": None, "mentions_election": False}
    row = minutes[0]
    return {"meeting": later[0], "minutes": str(row["name"]),
            "mentions_election": bool(re.search(r"election|elected|acclamation", library_text(records, row), re.I))}


@RECORDS.check("results-in-minutes", ElectionResults, fields=("election_date",), facts=next_board_meeting, dated=False)
def results_in_minutes(r, _as_of, following: dict[str, Any] | None) -> list[Finding]:
    """The tabulated results belong in the minutes of the board's next meeting: that meeting's minutes in the library."""
    if following is None:
        return []
    if not following["meeting"] or date.fromisoformat(following["meeting"]) > r.election_date + timedelta(days=120):
        return [Finding("results-minutes-not-on-file", "the library has no board meeting in the four months after this election to show "
                        "the results were recorded in its minutes", Severity.CHECK, "CIV 5120(b)")]
    if following["minutes"] is None:
        return [Finding("results-minutes-not-on-file", f"the board's next meeting was {following['meeting']}; its minutes, which should "
                        "record the results, are not in the library", Severity.CHECK, "CIV 5120(b)")]
    if following["mentions_election"]:
        return [Finding("results-in-minutes", f"the next board minutes ({following['minutes']}) take up the election", Severity.INFO,
                        "CIV 5120(b)")]
    return [Finding("results-not-in-minutes", f"the next board minutes ({following['minutes']}) do not mention the election results",
                    Severity.CHECK, "CIV 5120(b)")]


class ElectionResultsModel(DocumentModel):
    kind = DocumentKind.ELECTION_RESULTS
    name = "election-results"
    required = ("inspector", "election_date", "candidates", "certified")
    lens_checks = (election_materials, results_in_minutes)

    def parse(self, text: str, context: ModelContext) -> ElectionResults | None:
        t = normalize(text)
        if not re.search(r"Election Results|tabulated results|declared elected", t, re.I):
            return None
        flat = squash(t)
        r = ElectionResults(inspector=_inspector(t))
        r.association = first(r"\n\s*([A-Z][\w ]+(?:Community )?Association)\s*\n", t, flags=0)
        r.election = first(r"\n\s*(\d{4} (?:Board )?Election(?: of Board Members)?)\s*\n", t)
        r.election_date = date_after(r"Election Date:?", t)
        r.ownership_units = _int(r"Number of Ownership Units:?\s*(\d+)", flat)
        r.ballots_received = _int(r"Number of Ballots Received:?\s*(\d+)", flat)
        q = first(r"Quorum Achieved:?\s*(Yes|No)", flat)
        r.quorum_achieved = None if not q else q.lower() == "yes"
        r.rescheduled = first(r"(?:Rescheduled|Attempted) Meeting Date\(s\):?\s*(\S+)", flat)
        r.seats = _int(r"Number of Seats Up for Election:?\s*(\d+)", flat)
        if r.seats is None:
            r.seats = _int(r"candidates? for (\d+) board seats", flat)
        rows = []
        for m in re.finditer(r"\n\s*([A-Z][A-Za-z.'-]+(?: [A-Z][A-Za-z.'-]+){1,3})\s*\n(?:\s*\n)*\s*(\d+)\s+votes?\s*[-–]\s*(ELECTED|not elected)(\*)?",
                             t):
            rows.append(CandidateResult(m.group(1), int(m.group(2)), m.group(3) == "ELECTED", bool(m.group(4))))
        if not rows:
            names = first(r"Candidates declared elected:?\s*([^\n]+)", t)
            rows = [CandidateResult(n.strip(), None, True) for n in re.split(r",| and ", names) if n.strip()]
            r.acclamation = bool(rows) and bool(re.search(r"less than or equal to the number of (?:board )?seats|acclamation", flat, re.I))
        r.candidates = tuple(rows)
        r.tie_break = first(r"\*\s*(The Inspector of Elections resolved the tie[^\n]*(?:\n[^\n]+)?)", t)
        measures = []
        for m in re.finditer(r"Vote on (?:Resolution Regarding )?(.+?):\s*(.*?)(?=Vote on |I certify|$)", flat, re.I | re.S):
            block = m.group(2)
            yes = re.search(r"\bYes\s+(\d+) votes?(?:\s*-\s*([A-Z ]+?))?(?=\s+No\b|$)", block)
            no = re.search(r"\bNo\s+(\d+) votes?", block)
            nr = re.search(r"No Response\s+(\d+) ballots?", block)
            measures.append(MeasureResult(squash(m.group(1)), int(yes.group(1)) if yes else None, int(no.group(1)) if no else None,
                                          int(nr.group(1)) if nr else None, squash(yes.group(2) or "") if yes else ""))
        r.measures = tuple(measures)
        r.term = first(r"Board Term:?\s*([^\n]+)", t)
        r.certified = bool(re.search(r"I certify|This election is certified|Certification", flat, re.I))
        r.inspector_name = first(r"\bBy:\s*([A-Z][a-z]+ [A-Z][a-z]+)", t, flags=0) or \
            first(r"certified by\s*\n?\s*([A-Z][a-z]+ [A-Z][a-z]+)", t, flags=0)
        for attr, label in (("call_for_candidates", r"Call for Candidates:?"), ("reminder_notice", r"Reminder Notice:?"),
                            ("nomination_deadline", r"Nomination Deadline:?"), ("pre_ballot_notice", r"Pre-Ballot Notice:?"),
                            ("ballot_package", r"Ballot Package:?"), ("ballot_tally", r"Ballot Tally:?")):
            setattr(r, attr, date_after(label, t, window=30))
        return r

    def check(self, r: ElectionResults, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if not r.inspector:
            found.append(Finding("no-inspector", "the results do not name the inspector of elections", Severity.CHECK, "CIV 5110(a)"))
        if not r.certified:
            found.append(Finding("not-certified", "the results carry no certification by the inspector", Severity.CHECK, "CIV 5110(c)(8), (d)"))
        elected = [c for c in r.candidates if c.elected]
        if r.seats and elected and len(elected) != r.seats:
            found.append(Finding("seats-filled", f"{len(elected)} elected for {r.seats} seats", Severity.CHECK))
        if r.tie_break:
            found.append(Finding("tie-break", "a tie was resolved by the inspector: " + squash(r.tie_break)[:160], Severity.INFO))
        if r.quorum_achieved is False:
            found.append(Finding("no-quorum", "the election did not reach a quorum; a reconvened meeting at least 20 days later needs 20 "
                                 "percent of the members", Severity.CHECK, "CIV 5115(d)(2)"))
        if r.ownership_units and r.ballots_received is not None:
            found.append(Finding("turnout", f"{r.ballots_received} ballots from {r.ownership_units} units "
                                 f"({r.ballots_received / r.ownership_units:.0%})", Severity.INFO))
        spec = _spec_units(context)
        if spec and r.ownership_units and r.ownership_units != spec:
            found.append(Finding("unit-count", f"the inspector counted {r.ownership_units} ownership units; the specification has {spec} "
                                 "(annexation phases change the count)", Severity.INFO, "CIV 5110(c)(1)"))
        found += _timeline(r)
        if r.election_date:
            notice_by = r.election_date + timedelta(days=RESULTS_NOTICE_DAYS)
            found.append(Finding("results-notice", f"general notice of the tabulated results was due by {notice_by}", Severity.INFO, "CIV 5120(b)"))
            found.append(election_materials)   # the as-of lens's place: the year for keeping the materials
            found.append(results_in_minutes)   # the records lens's place: the next board meeting's minutes in the library
        return found


def _timeline(r: ElectionResults) -> list[Finding]:
    found = []

    def gap(a: date | None, b: date | None) -> int | None:
        return (b - a).days if a and b else None

    checks = (("nomination-notice", r.call_for_candidates, r.nomination_deadline, NOMINATION_NOTICE_DAYS,
               "the call for candidates came {d} days before the nomination deadline; general notice is due 30 days before", "CIV 5115(a)"),
              ("pre-ballot-notice", r.pre_ballot_notice, r.ballot_package, BALLOT_DAYS,
               "the pre-ballot notice came {d} days before the ballots; it is due 30 days before", "CIV 5115(b)"),
              ("ballot-timing", r.ballot_package, r.ballot_tally or r.election_date, BALLOT_DAYS,
               "the ballots went out {d} days before the voting deadline; they are due 30 days before", "CIV 5115(c), 5105(h)(4)"))
    for code, a, b, need, message, authority in checks:
        d = gap(a, b)
        if d is not None and d < need:
            found.append(Finding(code, message.format(d=d), Severity.PROBLEM, authority))
    if r.acclamation:
        d = gap(r.call_for_candidates, r.nomination_deadline)
        if d is None:
            found.append(Finding("acclamation-notices", "candidates were seated by acclamation; the results do not show the 90-day initial "
                                 "notice and the reminder the law requires first", Severity.CHECK, "CIV 5103(b)"))
        elif d < ACCLAMATION_NOTICE_DAYS:
            found.append(Finding("acclamation-notices", f"candidates were seated by acclamation, but the initial notice came {d} days before "
                                 "the nomination deadline; 90 are required", Severity.PROBLEM, "CIV 5103(b)(1)"))
        r_gap = gap(r.reminder_notice, r.nomination_deadline)
        if r_gap is not None and not 7 <= r_gap <= 30:
            found.append(Finding("acclamation-reminder", f"the reminder came {r_gap} days before the nomination deadline; it is due 7 to "
                                 "30 days before", Severity.PROBLEM, "CIV 5103(b)(2)"))
    return found



def _spec_units(context: ModelContext) -> int | None:
    units = getattr(context.community, "units", None)
    try:
        return len(units()) if callable(units) else None
    except TypeError:
        return None


class BallotModel(DocumentModel):
    kind = DocumentKind.BALLOT
    name = "secret-ballot"
    required = ("election", "candidates", "due", "count_date")

    def parse(self, text: str, context: ModelContext) -> Ballot | None:
        t = normalize(text)
        if not re.search(r"\bBALLOT\b", t[:800], re.I):
            return None
        flat = squash(t)
        r = Ballot(inspector=_inspector(t), secret=bool(re.search(r"SECRET BALLOT", t)))
        r.association = first(r"\n\s*([A-Z][\w ]+Association)\s*\n", t, flags=0)
        r.election = first(r"\n\s*(\d{4} (?:Board )?Election)\s*\n", t)
        r.seats = _int(r"There (?:are|is) (\d+) Board seats?", flat)
        r.cumulative_voting = bool(re.search(r"cumulative voting", flat, re.I))
        r.max_votes = _int(r"maximum of (\d+) votes", flat)
        block = re.search(r"BOARD ELECTION\s*\n(.*?)\n\s*O\s*\n", t, re.S)
        if block:
            r.candidates = tuple(squash(n) for n in re.findall(r"([A-Z][A-Za-z.'-]+(?: [A-Z][A-Za-z.'-]+)+)\s*→", block.group(1)))
        r.measures = tuple(squash(m) for m in re.findall(r"\n\s*([A-Z][A-Z0-9 .-]*(?:RULING|RESOLUTION|AMENDMENT|ASSESSMENT)[A-Z0-9 .-]*)\s*\n", t)
                           if "BOARD ELECTION" not in m)
        due = re.search(r"no later than\s*([\dapm: ]+?)\s*on\s*([A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})", flat, re.I)
        if due:
            r.due_time, r.due = squash(due.group(1)), next(iter(dates_in(due.group(2))), None)
        count = re.search(r"Ballots will be counted on\s*([A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})\s*at\s*([\d:apm]+)\s*(?:at\s*([^.]+))?", flat, re.I)
        if count:
            r.count_date, r.count_time = next(iter(dates_in(count.group(1))), None), count.group(2)
        r.count_online = bool(re.search(r"take place (?:by Zoom|online)|Join the Zoom", flat, re.I))
        r.count_location = first(r"(?:meet in person may gather at|gather at|in person at)\s*([^()]+?\d{5})", flat)
        r.quorum_ballots = _int(r"quorum, which is (\d+) ballots", flat)
        r.quorum_rule = first(r"\(i\.e\.\s*([^)]+)\)", flat)
        r.rules_phrase = RULES_PHRASE in flat.lower()
        front = t.split("SECRET BALLOT INSTRUCTIONS")[0]
        r.voter_identified = bool(re.search(r"(?:Owner|Voter|Member)'?s? Name\s*:|Unit (?:No\.?|Number|#)\s*:|Property Address\s*:|Signature\s*:", front, re.I))
        r.amendment_text = bool(re.search(r"text of the (?:proposed )?amendment|AMENDMENT", flat))
        return r

    def check(self, r: Ballot, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if not r.secret:
            found.append(Finding("not-secret", "the ballot does not say it is a secret ballot", Severity.CHECK, "CIV 5100(a)"))
        if r.voter_identified:
            found.append(Finding("voter-identified", "the ballot face asks for the voter's name, unit, address, or signature",
                                 Severity.PROBLEM, "CIV 5115(c)"))
        if not r.rules_phrase:
            found.append(Finding("rules-phrase", "the ballot does not say \"The rules governing this election may be found here:\" with the "
                                 "address, and the rules may have been delivered another way", Severity.CHECK, "CIV 5105(h)(4)(B)"))
        if r.seats and len(r.candidates) <= r.seats:
            found.append(Finding("uncontested", f"{len(r.candidates)} candidates for {r.seats} seats", Severity.INFO, "CIV 5103"))
        if r.cumulative_voting:
            found.append(Finding("cumulative-voting", "the ballot uses cumulative voting, which the governing documents must provide for",
                                 Severity.INFO, "CIV 5115(e)"))
        if r.count_online and not r.count_location:
            found.append(Finding("ballot-count-online", "ballots are counted at a meeting with no physical location", Severity.CHECK,
                                 "CIV 4926(b), 5120(a)"))
        if r.amendment_text:
            found.append(Finding("amendment-text", "an amendment is on the ballot; its text must go to members with the ballot",
                                 Severity.CHECK, "CIV 5115(g)"))
        return found


class PreBallotNoticeModel(DocumentModel):
    kind = DocumentKind.NOTICE
    name = "pre-ballot-notice"
    required = ("notice_date", "ballots_mailed", "candidates", "return_deadline", "count_date")

    def parse(self, text: str, context: ModelContext) -> PreBallotNotice | None:
        t = normalize(text)
        if not re.search(r"PRE-?BALLOT NOTICE", t, re.I):
            return None
        flat = squash(t)
        r = PreBallotNotice(inspector=_inspector(t))
        r.association = first(r"PRE-?BALLOT NOTICE FOR\s*\n?\s*([^\n]+)", t).title()
        r.election = first(r"\n\s*(\d{4} BOARD ELECTION)\s*\n", t).title()
        r.notice_date = date_after(r"Notice Date:?", t)
        r.ballots_mailed = date_after(r"BALLOTS WILL BE MAILED(?: OUT)?", t, window=30)
        m = re.search(r"appear on the ballot[^\n]*\n(?:[^\n]*\n)?\s*([^\n]+)\n", t)
        if m:
            r.candidates = tuple(n for n in re.split(r"\s{2,}", m.group(1).strip()) if re.match(r"[A-Z][a-z]", n))
        r.seats = _int(r"There (?:are|is) (\d+) board seats?", flat)
        r.corrections_deadline = date_after(r"deadline to report errors or omissions is", flat)
        due = re.search(r"received by the Inspector of Elections no later than\s*([\dapm: ]+?)\s*on\s*([A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})", flat, re.I)
        if due:
            r.return_time, r.return_deadline = squash(due.group(1)), next(iter(dates_in(due.group(2))), None)
        r.return_address = bool(re.search(r"Mail to:|hand delivery", flat, re.I))
        count = re.search(r"Ballots will be counted on\s*([A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})\s*at\s*([\dapm:]+)", flat, re.I)
        if count:
            r.count_date, r.count_time = next(iter(dates_in(count.group(1))), None), count.group(2)
        r.count_online = bool(re.search(r"take place online|Join the Zoom", flat, re.I))
        r.reconvene_statement = bool(re.search(r"(?:rescheduled|reconvened)[^.]*(?:20%|20 percent)", flat, re.I))
        r.reconvene_quorum = first(r"quorum shall be (20% \(\d+ ballots\))", flat)
        r.voter_list_verification = bool(re.search(r"verify the accuracy of their individual information", flat, re.I))
        return r

    def check(self, r: PreBallotNotice, context: ModelContext) -> list[Finding]:
        found: list[Finding] = []
        if r.notice_date and r.ballots_mailed:
            lead = (r.ballots_mailed - r.notice_date).days
            if lead < BALLOT_DAYS:
                found.append(Finding("pre-ballot-late", f"the notice came {lead} days before the ballots; it is due 30 days before",
                                     Severity.PROBLEM, "CIV 5115(b)"))
        if not r.return_address:
            found.append(Finding("no-return-address", "the notice does not give the physical address for returning ballots",
                                 Severity.PROBLEM, "CIV 5115(b)(1)"))
        if not r.reconvene_statement:
            found.append(Finding("no-reconvene-statement", "the notice does not say a reconvened meeting at 20 percent may be called if "
                                 "quorum fails", Severity.CHECK, "CIV 5115(b)(6)"))
        if r.count_online:
            found.append(Finding("ballot-count-online", "the counting meeting takes place online with no physical location",
                                 Severity.CHECK, "CIV 4926(b), 5120(a)"))
        if r.voter_list_verification and r.ballots_mailed:
            found.append(Finding("voter-list", f"members may verify their voter-list entries until {r.ballots_mailed - timedelta(days=30)} "
                                 "(30 days before ballots)", Severity.INFO, "CIV 5105(a)(7)"))
        return found


register(ElectionResultsModel())
register(BallotModel())
register(PreBallotNoticeModel())

__all__ = ["ElectionResults", "CandidateResult", "MeasureResult", "Ballot", "PreBallotNotice", "ElectionResultsModel", "BallotModel",
           "PreBallotNoticeModel"]
