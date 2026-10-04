"""Notices a statute requires a contract to print: the law's words, not terms the parties negotiated.

A home improvement contract must carry notices in the Legislature's own words (Business and Professions Code 7159(d)
and (e)): the mechanics lien warning, information about the Contractors State License Board, the right to cancel, the
insurance disclosures, and the statements about the down payment and progress payments. A reader of terms that takes
them as the contractor's promises reads "you must make available to the contractor ... goods delivered to you" as the
association's duty and the CSLB's description of itself as a clause.

``NOTICES`` are rows in match order: each names the notice, the phrases that open it, and the statute. ``find_notices``
returns where each one sits in a text, so a reader can file the words inside on their own topic. The rows quote the
openings the statute prescribes (BPC 7159 is on the authorities shelf); a row whose statute is not on the shelf says
so in ``about``. Pure: no network, no store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class StatutoryNotice:
    key: str
    title: str
    opens: tuple[str, ...]      # phrases that begin the notice, matched ignoring case and spacing
    authority: str              # the statute that requires it
    about: str


NOTICES: tuple[StatutoryNotice, ...] = (
    StatutoryNotice("mechanics-lien-warning", "Mechanics Lien Warning",
                    ("mechanics lien warning", "mechanics' lien warning"),
                    "BPC 7159(e)(4)",
                    "the notice a home improvement contract prints about the right of anyone unpaid to record a lien"),
    StatutoryNotice("cslb-information", "Information about the Contractors State License Board",
                    ("information about the contractors state license board", "information about the contractors' state license board"),
                    "BPC 7159(e)(5)",
                    "the CSLB's description of itself and how to complain, printed in at least 12-point type"),
    StatutoryNotice("right-to-cancel", "Three-Day (or Five-Day) Right to Cancel",
                    ("three-day right to cancel", "five-day right to cancel", "seven-day right to cancel",
                     "notice of the three-day right to cancel", "notice of the five-day right to cancel"),
                    "BPC 7159(e)(6)",
                    "the buyer's right to cancel a home improvement contract, with what each side must return"),
    StatutoryNotice("notice-of-cancellation", "Notice of Cancellation (form)",
                    ("notice of cancellation",),
                    "BPC 7159(e)(6)(B)",
                    "the detachable form the buyer may use to cancel"),
    StatutoryNotice("cgl-insurance", "Commercial General Liability Insurance",
                    ("commercial general liability insurance (cgl)", "a notice concerning commercial general liability insurance",
                     "does not carry commercial general liability insurance", "carries commercial general liability insurance"),
                    "BPC 7159(e)(1)",
                    "whether the contractor carries commercial general liability insurance, and with whom"),
    StatutoryNotice("workers-compensation", "Workers' Compensation Insurance",
                    ("a notice concerning workers' compensation insurance", "is exempt from workers' compensation requirements",
                     "carries workers' compensation insurance for all employees"),
                    "BPC 7159(e)(2)",
                    "whether the contractor has employees and carries workers' compensation for them"),
    StatutoryNotice("extra-work-change-orders", "Note About Extra Work and Change Orders",
                    ("note about extra work and change orders", "extra work and change orders become part of the contract"),
                    "BPC 7159(d)(13), (e)(3)",
                    "how extra work and change orders become part of the contract"),
    StatutoryNotice("downpayment", "Down payment",
                    ("the downpayment may not exceed",),
                    "BPC 7159(d)(8)",
                    "the cap on a home improvement contract's down payment, in capitals"),
    StatutoryNotice("progress-payments", "Schedule of progress payments",
                    ("the schedule of progress payments must specifically describe",),
                    "BPC 7159(d)(9)",
                    "what a schedule of progress payments must describe"),
    StatutoryNotice("mechanics-lien-notice-to-owner", "Notice to Owner (mechanics lien law)",
                    ("notice to owner", "notice to property owner", "under the california mechanics' lien law",
                     "under the california mechanics lien law"),
                    "CIV 8000-8848",
                    "an owner's notice about mechanics liens in the older home improvement form, or a preliminary notice's "
                    "notice to the owner; the mechanics lien law is not on the authorities shelf"),
    StatutoryNotice("arbitration-of-disputes", "Arbitration of Disputes",
                    ("arbitration of disputes",),
                    "BPC 7191",
                    "the arbitration clause's required heading and notice in a residential construction contract; BPC 7191 "
                    "is not on the authorities shelf, so read the clause beside the statute before relying on this row"),
)

SPAN_CAP = 2500  # characters: a notice longer than this ends at the cap


def _phrase(text: str) -> str:
    return r"\s+".join(re.escape(word) for word in text.split()).replace("'", "['’]")


_OPENERS = [(n, re.compile(_phrase(p), re.I)) for n in NOTICES for p in n.opens]
# Where a notice's text ends: a run of blank lines, a numbered section, a page break, a heading line in capitals, a
# page-number line, or a signature line ("Signed:", "Accepted:", "By:", "Signature", a run of blanks to fill in).
# A heading is a short line in capitals with no sentence's period (a notice printed in capitals is not a heading).
_END = re.compile(r"\n\s*\n\s*\n|\n\s*\d+(?:\.\d+)*\.?\s+[A-Z]|\f|\n[A-Z][A-Z0-9 ,'’()&/-]{8,60}:?\s*\n|"
                  r"\n\s*(?i:page)\s+\d+(?:\s*(?i:of|/)\s*\d+)?\s*\n|"
                  r"\n\s*(?:(?i:signed|accepted|signature)\b|(?i:by):)[^\n]*|\n[^\n]*_{6,}")


def find_notices(text: str) -> list[tuple[StatutoryNotice, int, int]]:
    """Each statutory notice in ``text`` with its span ``(start, end)``, in the order they appear. A notice starts at
    the line its opening phrase is on and ends at the next blank-line run, numbered section, page break, all-capitals
    heading, or another notice's opening, or after ``SPAN_CAP`` characters. Overlapping matches keep the first row."""
    # Each opening: the start of its line, whether the phrase opens that line (a heading or a notice's first words),
    # and the notice. A phrase in the middle of a line ("... receiving the notice of cancellation") can start a notice
    # but never ends another one.
    starts: list[tuple[int, bool, StatutoryNotice]] = []
    for notice, pattern in _OPENERS:
        for m in pattern.finditer(text):
            line_start = text.rfind("\n", 0, m.start()) + 1
            heads_line = not text[line_start:m.start()].strip(" \t\"“'‘(*-•")
            starts.append((line_start, heads_line, notice))
    starts.sort(key=lambda s: (s[0], not s[1]))
    found: list[tuple[StatutoryNotice, int, int]] = []
    for i, (start, _, notice) in enumerate(starts):
        if found and start < found[-1][2]:
            continue                      # inside a notice already found
        line_end = text.find("\n", start)
        line_end = len(text) if line_end < 0 else line_end
        # Another notice's heading ends this one; a second opening of the same notice ("NOTICE TO OWNER", then
        # "Under the California Mechanics' Lien Law ...") continues it.
        nxt = next((s for s, heads, other in starts[i + 1:] if s > start and heads and other.key != notice.key), len(text))
        m = _END.search(text, line_end, min(len(text), start + SPAN_CAP))
        end = min(m.start() if m else min(len(text), start + SPAN_CAP), nxt)
        found.append((notice, start, max(end, line_end)))
    return found


__all__ = ["StatutoryNotice", "NOTICES", "find_notices", "SPAN_CAP"]
