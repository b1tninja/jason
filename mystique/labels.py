"""The labels jason stores on the association's Drive files as appProperties.

Each row is one key. A key and its value together fit in 124 bytes of UTF-8; ``fit`` trims by the row's rule. A value
is written only for a file in the association's Drive listing (``data/drive/files.json``); a Google Photos album or a
web page has no Drive id and carries no label. ``jason_hold`` is reserved: ``jason drive-labels`` never writes or
removes it, and it stays empty until a legal hold sets it.
"""

from __future__ import annotations

from jason.community.drive_labels import Fit, Label, LabelProperty, LabelSource, LabelWriter

APP_PROPERTIES: tuple[LabelProperty, ...] = (
    LabelProperty(
        Label.KIND,
        "the document kind (a DocumentKind value, e.g. minutes, proposal)",
        "the Drive holdings row's kind by the library rules; else the kind the agenda link's name suggests",
        LabelSource.DRIVE_HOLDINGS,
        fit=Fit.EXACT,
    ),
    LabelProperty(
        Label.RECORDS,
        "the Civil Code 5200 records the kind is, comma separated",
        "the Drive holdings row's records, in its order",
        LabelSource.DRIVE_HOLDINGS,
        fit=Fit.LIST,
    ),
    LabelProperty(
        Label.MEETINGS,
        "the meeting dates that linked or hold the file, latest first (YYYY-MM-DD, comma separated)",
        "every agenda label's date and every meeting record's date, distinct, newest first; older dates drop off",
        LabelSource.AGENDA_LINKS,
        fit=Fit.LIST,
    ),
    LabelProperty(
        Label.ITEM,
        "the latest agenda item that linked the file, with its sub-item after ' / '",
        "the agenda label with the latest date (first listed on a tie)",
        LabelSource.AGENDA_LINKS,
        fit=Fit.TEXT,
    ),
    LabelProperty(
        Label.TOPICS,
        "the topics the agenda labels name, as Topic member names in lower case, comma separated",
        "the agenda link's topics in the order the topic rules found them",
        LabelSource.AGENDA_LINKS,
        fit=Fit.LIST,
    ),
    LabelProperty(
        Label.INCIDENT,
        "the likeliest incident: its first date, then its addresses or buildings, then its causes",
        "the first incident the agenda link marks likely (the file itself, then files linked beside it)",
        LabelSource.AGENDA_LINKS,
        fit=Fit.TEXT,
    ),
    LabelProperty(
        Label.CLAIMS,
        "the insurance claim numbers of the likely incidents, comma separated",
        "every likely incident's claims, distinct, in incident order",
        LabelSource.AGENDA_LINKS,
        fit=Fit.LIST,
    ),
    LabelProperty(
        Label.CONFIDENTIAL,
        "'1' when a rule marks the file confidential; absent otherwise",
        "the Drive holdings row's confidential flag or a confidential meeting record (an executive session)",
        LabelSource.DRIVE_HOLDINGS,
        fit=Fit.EXACT,
    ),
    LabelProperty(
        Label.LABELED_AT,
        "the date jason last changed this file's labels (YYYY-MM-DD)",
        "set by the apply run whenever another jason key on the file changes",
        LabelSource.APPLY,
        fit=Fit.EXACT,
    ),
    LabelProperty(
        Label.HOLD,
        "reserved for a legal hold's matter; empty until a hold sets it",
        "written only by the legal hold command, never by drive-labels",
        LabelSource.LEGAL_HOLD,
        writer=LabelWriter.LEGAL_HOLD,
        fit=Fit.EXACT,
    ),
    LabelProperty(
        Label.PRIVILEGE,
        "a held file's likely privilege and its basis: 'attorney-client: fmglaw.com; review', 'insurer-defense: esis.com; review', "
        "'not privileged: exchanged with the plaintiff's counsel'",
        "the legal hold command, from the file's email parties (privilege.py) and its name; a lead for counsel, never the determination",
        LabelSource.LEGAL_HOLD,
        writer=LabelWriter.LEGAL_HOLD,
        fit=Fit.TEXT,
    ),
)

__all__ = ["APP_PROPERTIES"]
