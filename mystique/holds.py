"""Mystique's legal holds.

26CV016125: the June 5, 2025 dog attack. The plaintiff's evidence preservation letter is dated June 24, 2025, so the
duty to preserve runs from that day; the hold reaches back to April 1, 2025, when the notices of violation about the same
dogs began. Vault holds the association's Workspace account (Drive and Mail); board members' personal email accounts and
photos, and Zoom's cloud, are outside Vault and are kept by notice and export. While the hold stands the Decorum Rules'
deletion of the Secretary's recording is suspended, as is any Zoom cloud-recording auto-delete.

The hold's private facts are in data/spec/mystique/holds.json (jason.community.private), by the hold's key: the Workspace
accounts held, the unit's address among the search terms, the matter's Drive folder, the custodian of record, and
counsel's direct contact.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from jason.community.holds import LegalHoldSpec


# What the directors' packet adds after the count of meetings whose recordings or transcripts Drive holds
# (Community.recordings_note): two of them are filed with the matter above.
RECORDINGS_NOTE = "including the May 20 and June 17, 2025 recordings filed with the 26CV016125 matter"


def _with_private(spec: LegalHoldSpec) -> LegalHoldSpec:
    from jason.community.private import facts

    private = facts("holds", profile="mystique").get(spec.key) or {}
    return replace(spec, custodians=tuple(private.get("custodians", ())), terms=spec.terms + tuple(private.get("terms", ())),
                   drive_folders=tuple(private.get("drive_folders", ())),
                   custodian_of_record=private.get("custodian_of_record", ""),
                   counsel_attention=private.get("counsel_attention", ""), counsel_email=private.get("counsel_email", ""))


LEGAL_HOLDS: tuple[LegalHoldSpec, ...] = tuple(_with_private(spec) for spec in (
    LegalHoldSpec(
        key="26cv016125",
        case="sacramento-26cv016125",
        title="Mystique - 26CV016125 (dog attack, June 2025)",
        duty_from=date(2025, 6, 24),
        relevant_from=date(2025, 4, 1),
        custodians=(),
        # The unit's address joins these from the private facts; "Disciplinary Hearing" alone would sweep in other matters.
        terms=("26CV016125", "dog", "dogs", "bite", "attack", "leash", "AZ250773", "Ayala"),
        notice_to=("each director, current and since April 2025", "the Secretary", "the community manager, if any"),
        outside_vault=("directors' personal email and text messages", "directors' personal photo albums",
                       "Zoom cloud recordings, transcripts, chats, and AI summaries", "copies on personal devices"),
        suspends=("Decorum Rules: the Secretary's recording is deleted once the minutes are prepared",
                  "Zoom cloud-recording auto-delete and trash emptying", "emptying Gmail and Drive trash",
                  "removing or deleting a custodian's Workspace account or license"),
        counsel="Freeman Mathis & Gary (defense, through the general liability carrier)",
        board_discussed="executive session on August 18, 2026",
    ),
))
