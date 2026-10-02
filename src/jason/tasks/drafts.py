"""Email drafts jason prepares for a person to review and send from Gmail.

A hearing notice is drafted from the plan in ``data/zoom/hearings.json``: the date and time, the Zoom link, and the
notice Doc (linked, or attached as its exported PDF). The subject names no owner or address. Email is individual
delivery only when the member has consented to receive notices by email (Civil Code 4040(b), 4041); that reminder is
printed for the person and is not in the email.

A meeting notice is drafted from the next agenda, ``data/board/agenda-<date>.md``: the Markdown is the body.

Nothing is sent. ``save`` creates a Gmail draft only when the person passed ``--yes``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from jason.google.gmail_drafts import DraftMessage, GmailDrafts

CONSENT_REMINDER = ("Email is individual delivery only if the member consented to receive notices by email "
                    "(Civil Code 4040(b), 4041); otherwise deliver the notice by first-class mail or in person.")


@dataclass
class DraftPlan:
    """A draft and the notes a person reads before creating it."""

    message: DraftMessage
    source: str
    reminders: list[str] = field(default_factory=list)

    def lines(self) -> list[str]:
        m = self.message
        out = [f"Draft from {self.source}", f"  To: {', '.join(m.to)}"]
        if m.cc:
            out.append(f"  Cc: {', '.join(m.cc)}")
        out.append(f"  Subject: {m.subject}")
        out.extend(f"  Attachment: {p}" for p in m.attachments)
        out.append("  ---")
        out.extend(f"  {line}" for line in m.text.splitlines())
        out.append("  ---")
        out.extend(f"Reminder: {r}" for r in self.reminders)
        return out


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def find_hearing(data_dir: Path, address: str, *, today: date | None = None) -> dict[str, Any]:
    """The saved hearing for ``address``: the next one on or after today, else the latest."""
    path = Path(data_dir) / "zoom" / "hearings.json"
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; plan the hearing with `jason hearing` first")
    rows = [r for r in json.loads(path.read_text(encoding="utf-8")).get("hearings", [])
            if _norm(r.get("address", "")) == _norm(address)]
    if not rows:
        raise LookupError(f"no saved hearing for {address}")
    today = today or date.today()
    rows.sort(key=lambda r: r["start"])
    upcoming = [r for r in rows if r["start"][:10] >= today.isoformat()]
    return upcoming[0] if upcoming else rows[-1]


def hearing_draft(hearing: dict[str, Any], to: str, association: str, *, pdf: Path | None = None) -> DraftPlan:
    """The hearing notice email. The subject and greeting name no owner; the address appears only in the body."""
    start = datetime.fromisoformat(hearing["start"])
    when = f"{start:%A, %B} {start.day}, {start:%Y} at {start:%I:%M %p}".replace(" 0", " ")
    zoom = hearing.get("zoom") or {}
    doc = hearing.get("noticeDoc") or {}
    lines = [
        "Dear Member,",
        "",
        f"The Board of Directors of {association} will hold a hearing on {when} ({hearing.get('timezone', '')}) "
        f"about the property at {hearing['address']}. The attached written notice states the alleged violation and "
        "your right to attend, to address the board, and to ask that the hearing be held in executive session "
        "(Civil Code 5855).",
        "",
    ]
    if zoom.get("joinUrl"):
        lines.append(f"Join by Zoom: {zoom['joinUrl']}")
        if zoom.get("passcode"):
            lines.append(f"Passcode: {zoom['passcode']}")
        lines.extend(f"Dial in: {n}" for n in zoom.get("dialIn") or [])
        lines.append("")
    if pdf is None and doc.get("url"):
        lines.extend([f"Written notice: {doc['url']}", ""])
    lines.extend(["Sincerely,", f"Board of Directors, {association}"])
    reminders = [CONSENT_REMINDER, f"The notice must be delivered by {hearing.get('noticeBy')} (Civil Code 5855(a))."]
    if not zoom.get("joinUrl"):
        reminders.append("The hearing has no Zoom meeting yet; schedule it before sending.")
    if pdf is None and not doc.get("url"):
        reminders.append("No notice Doc is saved with the hearing; attach the written notice before sending.")
    if doc.get("unfilled"):
        reminders.append(f"The notice Doc still has unfilled fields: {', '.join(map(str, doc['unfilled']))}.")
    message = DraftMessage(
        to=(to,),
        subject=f"Notice of Hearing, Board of Directors, {start.date().isoformat()}",
        text="\n".join(lines),
        attachments=(pdf,) if pdf else (),
    )
    return DraftPlan(message, f"hearing {hearing['start']}", reminders)


def agenda_path(data_dir: Path, meeting: date) -> Path:
    return Path(data_dir) / "board" / f"agenda-{meeting.isoformat()}.md"


def meeting_notice_draft(data_dir: Path, meeting: date, to: str, association: str) -> DraftPlan:
    """The meeting notice email: the agenda Markdown is the body."""
    path = agenda_path(data_dir, meeting)
    if not path.is_file():
        raise FileNotFoundError(f"{path} not found; draft the agenda with `jason agenda` first")
    text = path.read_text(encoding="utf-8")
    reminders: list[str] = []
    heading = next((line for line in text.splitlines() if line.startswith("#")), "")
    if "DRAFT" in heading.upper():
        reminders.append("The agenda heading still says DRAFT; the board approves the agenda before notice goes out.")
    due = re.search(r"_Notice with this agenda must go out by ([^(]+?) \(", text)
    reminders.append(f"Notice must go out by {due.group(1)} (Civil Code 4920(a))." if due else
                     "Notice goes out at least four days before the meeting (Civil Code 4920(a)).")
    reminders.append("Post the agenda where the association posts notices as well (Civil Code 4920(a), 4045).")
    when = f"{meeting:%A, %B} {meeting.day}, {meeting:%Y}"
    message = DraftMessage(to=(to,), subject=f"Notice of Board Meeting, {association}, {when}", text=text)
    return DraftPlan(message, str(path).replace("\\", "/"), reminders)


def save(plan: DraftPlan, drafts: GmailDrafts) -> dict[str, Any]:
    """Create the Gmail draft. The draft is not sent."""
    return drafts.create(plan.message)


__all__ = ["CONSENT_REMINDER", "DraftPlan", "agenda_path", "find_hearing", "hearing_draft", "meeting_notice_draft", "save"]
