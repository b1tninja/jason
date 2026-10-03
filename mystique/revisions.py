"""The documents whose versions ``jason revisions`` compares, and the file names their older versions went by.

Each document's title and aliases (outlines.py) already find most copies ("Owner's Manual and Rules.pdf"). These rows
add the names an older copy went by: a first printing scanned as a "Community Manual", a prior manager's "owners
manual", a proposal letter that carried a draft policy. A candidate found by its name is a version only if it shares
its words with the current text (``revision_detection.VERSION_MIN``), so a name here is a place to look, not a finding.
"""

from __future__ import annotations

from jason.community.revision_detection import RevisionSeries

_NOT_A_COPY = (r"\bnotice of\b", r"\bnotice to owners\b", r"\btransmittal\b", r"\bcover letter\b", r"\.mp3$",
               r"\.zip$", r"\baudio\b")

REVISION_SERIES = (
    RevisionSeries(
        "owners-manual",
        names=(r"\bowners?\W*s? manual\b", r"\bcommunity manual\b", r"\bcomm manual\b"),
        exclude=_NOT_A_COPY + (r"\bassociation manual\b", r"\bmaintenance manual\b", r"\buser manual\b",
                               r"\bpump manual\b"),
        note="The first printing is a scan of a hardcopy; the prior managers kept copies under their own names."),
    RevisionSeries(
        "election-rules",
        names=(r"\belection rules\b",),
        exclude=_NOT_A_COPY + (r"\bresults\b", r"\bproposal\b", r"\bballot\b", r"\bnomination\b")),
    RevisionSeries(
        "enforcement-policy",
        names=(r"\benforcement (and fine )?(procedures )?polic", r"\bfine (enforcement )?policy\b",
               r"\benforcement fine policy\b", r"\bfine schedule\b"),
        exclude=_NOT_A_COPY + (r"\bdefense\b", r"\bprotocol\b")),
    RevisionSeries(
        "collection-policy",
        names=(r"\bcollection policy\b",),
        exclude=_NOT_A_COPY + (r"\bnotices to members\b",)),
    RevisionSeries(
        "parking-rules",
        names=(r"\bparking rules\b",),
        exclude=_NOT_A_COPY + (r"\bapplica",)),
    RevisionSeries(
        "bylaws",
        names=(r"\bbylaws\b",),
        exclude=_NOT_A_COPY + (r"\bgrant deed\b",)),
)

__all__ = ["REVISION_SERIES"]
