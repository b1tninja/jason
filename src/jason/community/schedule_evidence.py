"""What shows a scheduled duty done: evidence rules, as data, for ``jason schedule-evidence``.

An ``EvidenceRule`` names the duties it serves by the references an assignment covers (a statute, ``"CIV 5500"``; a
notice catalog key, ``"notice:board-meeting"``; or a prefix ending in ``":"``, ``"obligation:"``), where jason looks
(``EvidenceSource``), what it looks for there (``words``, each a regular expression, and ``near``, words that must
also appear in the same passage), and how much a hit says (``Weight``):

- **DIRECT**: the record says the duty was done (the minutes record the review; the notice went out in time);
- **SUPPORTING**: the record makes it likely, and a person reads it (the minutes name a report that holds the
  reconciliations; the minutes are on file, but when members could read them is not);
- **AGAINST**: the record says it was done wrongly (the notice went out three days before the meeting).

The rules here hold for any California association. A profile adds its own (``Community.evidence_rules()``) for duties
it covers by its governing documents' sections, or for the words its own minutes use; a profile's rules are tried
first and all that apply are used. A rule that finds nothing is a miss, never a finding: an occurrence with no
evidence stays overdue until a person records it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvidenceSource(Enum):
    MINUTES_TEXT = "minutes text"              # the words in the minutes of the meeting(s) the occurrence falls on
    MINUTES_REPORT = "report the minutes name"  # a stored reading of ``kinds`` the minutes name, holding ``words``
    MEETING_NOTICE = "meeting notice"          # the meeting catalog's notice (or agenda) sent to members, and how early
    MINUTES_FILED = "minutes filed"            # the meeting's minutes on file, and the earliest date one is dated
    MEETING_HELD = "meeting held"              # the meeting catalog: minutes, an agenda, or a call held that day
    MAILING = "mailing"                        # a mailing whose subject or key carries ``words``, inside ``window``
    LIBRARY_FILE = "file on record"            # a library file of ``kinds`` (and ``words`` in its name) for the year
    PAYMENTS = "payments"                      # the obligation rows' payments (``jason deadlines``)


class Weight(Enum):
    DIRECT = "direct"
    SUPPORTING = "supporting"
    AGAINST = "against"


@dataclass(frozen=True)
class EvidenceRule:
    key: str
    covers: tuple[str, ...]                    # an assignment covering any of these takes the rule
    source: EvidenceSource
    weight: Weight = Weight.DIRECT
    words: tuple[str, ...] = ()                # regular expressions; any one is a hit (case-insensitive)
    near: tuple[str, ...] = ()                 # and one of these within the same passage, when set
    kinds: tuple[str, ...] = ()                # MINUTES_REPORT, LIBRARY_FILE: ``DocumentKind`` values
    days: int = 0                              # MEETING_NOTICE: at least this many days before; MINUTES_FILED: within
    window: tuple[int, int] = (0, 0)           # MAILING, MINUTES_TEXT off a meeting: days from the due date (from, to)
    year_offset: int = 0                       # LIBRARY_FILE: the file's year, from the anchor's year
    note: str = ""

    def serves(self, ref: str) -> bool:
        """Whether this rule serves an assignment that covers ``ref``."""
        return any(ref == c or (c.endswith(":") and ref.startswith(c)) or ref.startswith(c + "(") for c in self.covers)


TREASURER_REPORT_PRESENTED = (
    r"(?:review|present|discuss|approv|accept|provid|cover)\w*\s+(?:of\s+)?(?:the|a)\s+treasur\w*.?s?\s+(?:report|update)",
    r"treasur\w*.?s?\s+report\s+(?:was|were)\s+(?:presented|reviewed|discussed|approved|accepted|received)",
    r"reported\s+on\s+the\s+treasur\w*",
)

RULES: tuple[EvidenceRule, ...] = (
    # The board's monthly financial review (Civil Code 5500), or its ratification at the next meeting (5501).
    EvidenceRule("financial-review-reconciliations", ("CIV 5500", "CIV 5501"), EvidenceSource.MINUTES_TEXT,
                 words=(r"\breconcil\w*",), near=(r"\breview\w*", r"\bratif\w*", r"\bapprov\w*", r"\baccept\w*"),
                 note="the minutes record the board's review of the reconciliations"),
    EvidenceRule("financial-review-ratified", ("CIV 5500", "CIV 5501"), EvidenceSource.MINUTES_TEXT,
                 words=(r"\bratif\w*", r"\b5501\b", r"\b5500\b"),
                 near=(r"\breconcil\w*", r"\bfinanc\w*", r"\bstatements?\b", r"\b550[01]\b"),
                 note="the minutes record a 5501 ratification of a review outside the meeting"),
    EvidenceRule("financial-review-report", ("CIV 5500", "CIV 5501"), EvidenceSource.MINUTES_REPORT, Weight.SUPPORTING,
                 words=(r"\breconcil\w*",), kinds=("treasurer_report", "financial_statement"),
                 note="the minutes name a treasurer's report that holds the reconciliations; whether the board reviewed "
                      "them is for the minutes to say"),
    EvidenceRule("financial-review-presented", ("CIV 5500", "CIV 5501"), EvidenceSource.MINUTES_TEXT, Weight.SUPPORTING,
                 words=TREASURER_REPORT_PRESENTED,
                 note="the minutes record the treasurer's report presented or discussed, not the reconciliations"),
    EvidenceRule("financial-review-board-reviewed", ("CIV 5500", "CIV 5501"), EvidenceSource.MINUTES_TEXT,
                 Weight.SUPPORTING, words=(r"\bboard\s+(?:has\s+)?reviewed\b",), near=(r"\bfinancials?\b",),
                 note="the minutes record the board reviewing the financials, without naming the reconciliations"),
    # The board's meetings: notice at least four days before (4920(a)), minutes within 30 days (4950(a)).
    EvidenceRule("meeting-notice", ("CIV 4920", "notice:board-meeting"), EvidenceSource.MEETING_NOTICE, days=4,
                 note="the notice (or the agenda) went to members at least four days before the meeting"),
    EvidenceRule("minutes-filed", ("CIV 4950", "notice:minutes-available"), EvidenceSource.MINUTES_FILED,
                 Weight.SUPPORTING, days=30,
                 note="the minutes are on file and dated within 30 days; when members could first read them is not kept"),
    EvidenceRule("meeting-held", ("CIV 4900", "CIV 4910"), EvidenceSource.MEETING_HELD,
                 note="the meeting's minutes, agenda, or call are on record"),
    EvidenceRule("annual-meeting", ("notice:member-meeting",), EvidenceSource.MINUTES_TEXT,
                 words=(r"annual\s+(?:membership\s+|members.?\s+)?meeting",), window=(-31, 31),
                 note="the minutes of the annual meeting"),
    # The annual reports: the budget report 30 to 90 days before the fiscal year ends (5300), the reviewed statement
    # within 120 days after (5305).
    EvidenceRule("budget-report-mailed", ("CIV 5300", "notice:annual-budget-report"), EvidenceSource.MAILING,
                 words=(r"budget", r"policy\s+statement", r"\b5300\b", r"\b5310\b"), window=(-60, 0),
                 note="a mailing of the budget report in the 30-to-90-day window"),
    EvidenceRule("budget-report-late", ("CIV 5300", "notice:annual-budget-report"), EvidenceSource.MAILING, Weight.AGAINST,
                 words=(r"budget", r"policy\s+statement", r"\b5300\b"), window=(1, 60),
                 note="a mailing of the budget report after the window closed"),
    EvidenceRule("budget-on-file", ("CIV 5300", "notice:annual-budget-report"), EvidenceSource.LIBRARY_FILE,
                 Weight.SUPPORTING, kinds=("budget",), year_offset=1,
                 note="the next year's budget is on file; its mailing is not shown"),
    EvidenceRule("reviewed-statement-on-file", ("CIV 5305", "notice:financial-review"), EvidenceSource.LIBRARY_FILE,
                 Weight.SUPPORTING, kinds=("financial_review",), year_offset=0,
                 note="the CPA's review is on file; its distribution is not shown"),
    # The owner information request (4041), yearly.
    EvidenceRule("owner-information-sent", ("CIV 4041", "notice:owner-info-solicitation"), EvidenceSource.MAILING,
                 words=(r"owner.?info", r"owner\s+information", r"\b4041\b"), window=(-30, 45),
                 note="the request went to the owners"),
    # A recurring deadline: the payments its obligation row reads.
    EvidenceRule("obligation-payments", ("obligation:",), EvidenceSource.PAYMENTS, Weight.SUPPORTING,
                 note="a payment in the obligation's category or to its payee; the filing, report, or notice is the "
                      "record"),
)


def rules_for(assignment: object, community: object | None = None) -> list[EvidenceRule]:
    """The rules that serve an assignment: the profile's first, then jason's, each at most once."""
    profile = tuple(getattr(community, "evidence_rules", lambda: ())()) if community is not None else ()
    covers = tuple(getattr(assignment, "covers", ()))
    out: list[EvidenceRule] = []
    for rule in profile + RULES:
        if any(rule.serves(ref) for ref in covers) and rule.key not in {r.key for r in out}:
            out.append(rule)
    return out


__all__ = ["EvidenceRule", "EvidenceSource", "RULES", "TREASURER_REPORT_PRESENTED", "Weight", "rules_for"]
