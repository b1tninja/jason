"""Evidence that a scheduled duty was done, proposed for a person to confirm (``jason schedule-evidence``).

``jason schedule`` shows each occurrence overdue until a person records it done (``schedule.record_done``). Most of the
evidence is already on disk. ``propose`` takes every occurrence of every assignment in a window, applies the evidence
rules that serve it (``jason.community.schedule_evidence``: jason's, and the profile's own), and returns one
``Proposal`` per occurrence with what it found:

- **the minutes' text**: the minutes of the meeting the occurrence falls on (the readings in
  ``data/documents/readings.json``, and the meeting catalog's copies), searched for the rule's words, with the passage
  quoted from the text read;
- **a report the minutes name**: a stored reading (a treasurer's report) whose name the minutes carry, and the lines
  of it that hold the rule's words;
- **the meeting catalog** (``data/meetings/catalog.json``): the notice sent to members and how many days before the
  meeting; the minutes on file and the earliest date a copy carries; whether the meeting was held;
- **mailings**: PayHOA's communications log, jason's own sends, the Mailroom log, and the notice delivery ledger;
- **the library**: a file of the kind the duty produces, for the year;
- **payments**: the obligation rows' payments (``jason deadlines``), for a duty that covers a recurring deadline.

A proposal is never a completion. A person reads it and records the occurrence (``record``, which calls
``schedule.record_done`` with who confirmed it and the evidence). It reads disk only and calls nothing.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from jason.community.schedule import Adoption, Anchor, Assignment, Trigger, anchors_for, assignments, occurrences
from jason.community.schedule_evidence import EvidenceRule, EvidenceSource, Weight, rules_for

NEAR_CHARS = 200                     # a passage: this many characters either side of a hit
QUOTE_CHARS = 320
MEETING_SLACK_DAYS = 10              # an actual meeting this near the scheduled day is that month's meeting
HELD_KINDS = {"minutes", "draft minutes", "transcript", "attendance", "audio recording", "video recording",
              "AI summary"}           # the catalog's records that show a meeting was held, not only planned
CAVEATS = (
    "A proposal is evidence for a person to read, never a completion: nothing is recorded until a person confirms it.",
    "Words in the minutes are found as written; minutes that record the review in other words are a miss, and a "
    "miss is not proof the duty was not done.",
    "A report the minutes name shows what the board had before it, not that it reviewed each part.",
    "Confidential minutes (executive session) are not searched or quoted.",
)


@dataclass(frozen=True)
class Finding:
    rule: str
    weight: Weight
    source: EvidenceSource
    file: str                        # the record: its name and where it is kept
    day: date | None = None          # the record's date: the meeting, the day sent, the payment
    passage: str = ""                # quoted from the text read
    note: str = ""

    def row(self) -> dict[str, Any]:
        return {"rule": self.rule, "weight": self.weight.value, "source": self.source.value, "file": self.file,
                "date": self.day.isoformat() if self.day else None, "passage": self.passage, "note": self.note}


@dataclass
class Proposal:
    assignment: Assignment
    due: date
    findings: list[Finding] = field(default_factory=list)
    done: dict[str, Any] | None = None           # a completion already recorded for this occurrence

    @property
    def standing(self) -> str:
        """recorded, proposed (direct evidence), partial (supporting only), contrary (evidence against), or none."""
        if self.done:
            return "recorded"
        weights = {f.weight for f in self.findings}
        if Weight.AGAINST in weights:
            return "contrary"
        if Weight.DIRECT in weights:
            return "proposed"
        return "partial" if weights else "none"

    @property
    def done_on(self) -> date | None:
        """The day the evidence says it was done: the earliest direct finding's date, else any finding's."""
        for weight in (Weight.DIRECT, Weight.SUPPORTING):
            days = sorted(f.day for f in self.findings if f.weight is weight and f.day)
            if days:
                return days[0]
        return None

    def evidence_text(self, limit: int = 3) -> str:
        """The evidence as one line for the completion record: each finding's file, date, and passage or note."""
        parts = []
        for f in sorted(self.findings, key=lambda f: (f.weight is not Weight.DIRECT, f.weight is Weight.AGAINST))[:limit]:
            text = f.passage or f.note
            parts.append(f"{f.file}" + (f" ({f.day})" if f.day else "") + (f": \"{text[:160]}\"" if f.passage else
                                                                           f": {text[:160]}" if text else ""))
        return "; ".join(parts)

    def row(self) -> dict[str, Any]:
        a = self.assignment
        return {"key": a.key, "title": a.title, "role": a.role.value, "due": self.due.isoformat(),
                "standing": self.standing, "doneOn": self.done_on.isoformat() if self.done_on else None,
                "findings": [f.row() for f in self.findings], "recorded": self.done}


# ---------------------------------------------------------------------------------------------------------------
# The stores, read once.


def _clean(text: str) -> str:
    return " ".join(text.replace("​", " ").replace(" ", " ").split())


def _norm(text: str) -> str:
    """For matching a file's name in text: lower case, plain apostrophes, the extension a word of its own (so a short
    name is not found inside a longer one), one space for runs of space, underscores, or dashes."""
    text = text.lower().replace("’", "'").replace("​", " ")
    text = re.sub(r"\.(pdf|docx?|xlsx?)\b", r" \1", text)
    return " ".join(re.sub(r"[_\s\-]+", " ", text).split())


def _date(value: Any) -> date | None:
    text = str(value or "")
    try:
        return date.fromisoformat(text[:10]) if len(text) >= 10 else None
    except ValueError:
        return None


@dataclass(frozen=True)
class Minutes:
    id: str
    name: str
    day: date
    where: str
    confidential: bool = False

    @property
    def label(self) -> str:
        return f"{self.name} ({self.where} {self.id})"


class Stores:
    """What jason keeps on disk that can show a duty done, read lazily and once."""

    def __init__(self, data_dir: Path, community: Any = None) -> None:
        self.root = Path(data_dir)
        self.community = community
        self._cache: dict[str, Any] = {}

    def _once(self, key: str, make: Any) -> Any:
        if key not in self._cache:
            self._cache[key] = make()
        return self._cache[key]

    @property
    def tz(self) -> str:
        policy = getattr(self.community, "hearing_policy", lambda: None)() if self.community is not None else None
        return getattr(policy, "timezone", "") or "America/Los_Angeles"

    def local_day(self, stamp: str) -> date | None:
        try:
            moment = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
        except ValueError:
            return None
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        from zoneinfo import ZoneInfo

        return moment.astimezone(ZoneInfo(self.tz)).date()

    def catalog(self) -> dict[str, Any]:
        def make() -> dict[str, Any]:
            path = self.root / "meetings" / "catalog.json"
            return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        return self._once("catalog", make)

    def meetings(self) -> dict[date, dict[str, Any]]:
        """The catalog's meetings by day; a day with only jason's drafts was not held."""
        def make() -> dict[date, dict[str, Any]]:
            out = {}
            for m in self.catalog().get("meetings", []):
                day = _date(m.get("date"))
                if day and any(r.get("where") != "jason draft" for r in m.get("records", [])):
                    out[day] = m
            return out
        return self._once("meetings", make)

    def readings(self) -> list[dict[str, Any]]:
        def make() -> list[dict[str, Any]]:
            path = self.root / "documents" / "readings.json"
            return json.loads(path.read_text(encoding="utf-8")).get("readings", []) if path.is_file() else []
        return self._once("readings", make)

    def text(self, doc_id: str) -> str:
        def make() -> str:
            from jason.tasks.library import text_for

            return text_for(self.root, doc_id)
        return self._once(f"text:{doc_id}", make)

    def minutes(self) -> dict[date, list[Minutes]]:
        """Every set of minutes with text, by its meeting's day: the readings (their period, else the meeting date the
        minutes model read), then the catalog's library and Drive copies no reading covers."""
        def make() -> dict[date, list[Minutes]]:
            out: dict[date, list[Minutes]] = {}
            seen: set[str] = set()
            for r in self.readings():
                if r.get("kind") != "minutes" or not r.get("hasText"):
                    continue
                day = _date(r.get("period")) or _date((r.get("fields") or {}).get("meeting_date"))
                if day is None:
                    continue
                rid = str(r["id"])
                where = "Drive" if rid.startswith("drive-") else "PayHOA library"
                out.setdefault(day, []).append(Minutes(rid, str(r.get("name") or ""), day, where,
                                                       bool(r.get("confidential"))))
                seen.add(rid)
            for day, m in self.meetings().items():
                for rec in m.get("records", []):
                    if rec.get("kind") != "minutes":
                        continue
                    rid = {"PayHOA library": str(rec.get("ref") or ""), "Drive": f"drive-{rec.get('ref')}"}.get(
                        str(rec.get("where")), "")
                    same = any(_norm(x.name) == _norm(str(rec.get("name") or "")) for x in out.get(day, []))
                    if not rid or rid in seen or same or not self.text(rid).strip():
                        continue
                    seen.add(rid)
                    out.setdefault(day, []).append(Minutes(rid, str(rec.get("name") or ""), day, str(rec["where"]),
                                                           bool(rec.get("confidential"))))
            return out
        return self._once("minutes", make)

    def held(self) -> list[date]:
        """The days a meeting is on record: its minutes, its notice to members, or its call (a file alone, such as an
        agenda, can be another body's meeting)."""
        days = {d for d, m in self.meetings().items() if set(m.get("has") or {}) & (HELD_KINDS | {"meeting notice"})}
        return sorted(days | set(self.minutes()))

    def drive_files(self) -> dict[str, dict[str, Any]]:
        def make() -> dict[str, dict[str, Any]]:
            path = self.root / "drive" / "files.json"
            if not path.is_file():
                return {}
            raw = json.loads(path.read_text(encoding="utf-8"))
            return {r["id"]: r for r in (raw if isinstance(raw, list) else raw.get("files", [])) if r.get("id")}
        return self._once("drive", make)

    def library(self) -> tuple[dict[str, Any], ...]:
        def make() -> tuple[dict[str, Any], ...]:
            from jason.tasks.library import load

            return load(self.root)
        return self._once("library", make)

    def mailings(self) -> list[tuple[date, str, str]]:
        """Every mailing on disk as (day, what it was, where it is kept): PayHOA's communications log, jason's own
        sends, the Mailroom log, and the notice delivery ledger."""
        def make() -> list[tuple[date, str, str]]:
            out: list[tuple[date, str, str]] = []
            comms = self.root / "payhoa" / "communications.json"
            if comms.is_file():
                for n in json.loads(comms.read_text(encoding="utf-8")).get("notices", []):
                    day = self.local_day(n.get("sent") or "")
                    if day:
                        out.append((day, str(n.get("subject") or ""), "PayHOA communications"))
            sends = self.root / "payhoa" / "notices.json"
            if sends.is_file():
                raw = json.loads(sends.read_text(encoding="utf-8"))
                for n in raw if isinstance(raw, list) else raw.get("notices", []):
                    day = self.local_day(n.get("sentAt") or "")
                    if day:
                        out.append((day, f"{n.get('notice') or ''}: {n.get('subject') or ''}", "jason's sends"))
            mailroom = self.root / "mailroom" / "sent.jsonl"
            if mailroom.is_file():
                for line in mailroom.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    n = json.loads(line)
                    day = self.local_day(n.get("sent") or "")
                    pdf = Path(str(n.get("pdf") or "").replace("\\", "/"))
                    if day:
                        out.append((day, f"{pdf.parent.name}/{pdf.name}", "Mailroom"))
            for key, sent in self.ledger().items():
                day = self.local_day(sent)
                if day:
                    out.append((day, key, "notice ledger"))
            return out
        return self._once("mailings", make)

    def ledger(self) -> dict[str, str]:
        """Each notice in the delivery ledger with its first attempt's time (read only)."""
        def make() -> dict[str, str]:
            path = self.root / "notices" / "deliveries.db"
            if not path.is_file():
                return {}
            con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
            try:
                return {str(k): str(s) for k, s in con.execute(
                    "select notice, min(sent_at) from attempts where sent_at != '' group by notice")}
            except sqlite3.Error:
                return {}
            finally:
                con.close()
        return self._once("ledger", make)

    def obligations(self) -> list[dict[str, Any]]:
        def make() -> list[dict[str, Any]]:
            if self.community is None or not tuple(getattr(self.community, "obligations", lambda: ())()):
                return []
            from jason.tasks.deadlines import calendar

            return calendar(self.root, self.community).get("obligations", [])
        return self._once("obligations", make)


# ---------------------------------------------------------------------------------------------------------------
# Which meetings an occurrence falls on.


def _anchor_day(a: Assignment, due: date) -> date:
    return due - timedelta(days=a.offset_days) if a.trigger is Trigger.ANCHORED else due


def meeting_days(a: Assignment, due: date, rule: EvidenceRule, stores: Stores) -> list[date]:
    """The meetings an occurrence falls on. One anchored on a meeting takes the meetings held in the scheduled
    meeting's month, or within ten days of its day (a meeting moved or a special meeting in its place); any other
    takes the meetings inside the rule's window from the due date."""
    held = stores.held()
    if a.trigger is Trigger.ANCHORED and a.anchor in (Anchor.BOARD_MEETING, Anchor.ANNUAL_MEETING):
        anchor = _anchor_day(a, due)
        return [d for d in held if (d.year, d.month) == (anchor.year, anchor.month)
                or abs((d - anchor).days) <= MEETING_SLACK_DAYS]
    lo, hi = rule.window if rule.window != (0, 0) else (-MEETING_SLACK_DAYS, MEETING_SLACK_DAYS)
    return [d for d in held if due + timedelta(days=lo) <= d <= due + timedelta(days=hi)]


# ---------------------------------------------------------------------------------------------------------------
# The sources.


def passages(text: str, words: Iterable[str], near: Iterable[str] = ()) -> list[str]:
    """Passages of ``text`` that carry one of ``words`` (and one of ``near`` within the passage, when given), quoted
    as written with the spacing collapsed."""
    text = text.replace("​", " ")
    near = tuple(near)
    out: list[str] = []
    for pattern in words:
        for m in re.finditer(pattern, text, re.I):
            lo, hi = max(0, m.start() - NEAR_CHARS), min(len(text), m.end() + NEAR_CHARS)
            window = text[lo:hi]
            if near and not any(re.search(n, window, re.I) for n in near):
                continue
            # Quote around the hit, at word boundaries.
            half = QUOTE_CHARS // 2
            qlo, qhi = max(0, m.start() - half), min(len(text), m.end() + half)
            quote = _clean(text[qlo:qhi])
            if qlo > 0:
                quote = "..." + quote.split(" ", 1)[-1]
            if qhi < len(text):
                quote = quote.rsplit(" ", 1)[0] + "..."
            if quote not in out:
                out.append(quote)
    return out


def _minutes_text(a: Assignment, due: date, rule: EvidenceRule, stores: Stores) -> list[Finding]:
    out = []
    for day in meeting_days(a, due, rule, stores):
        for m in stores.minutes().get(day, []):
            if m.confidential:
                continue
            found = passages(stores.text(m.id), rule.words, rule.near)
            if found:
                out.append(Finding(rule.key, rule.weight, rule.source, m.label, day, found[0], rule.note))
    return out


def _report_lines(text: str, words: Iterable[str]) -> list[str]:
    """The short lines of a report that carry the words (its contents list, its section titles)."""
    out = []
    for line in text.splitlines():
        line = _clean(line)
        if 0 < len(line) <= 90 and any(re.search(w, line, re.I) for w in words) and line not in out:
            out.append(line)
    return out[:4]


def _named_in(name: str, text_norm: str, text_raw: str, period_of: str = "") -> str:
    """How the minutes name a file (normalized): its whole name; its title through its period (another copy of the
    same report); or (as a linked file's title often is) its name cut short with an ellipsis. Empty when not named."""
    n = _norm(name)
    if len(n) < 12:
        return ""
    if n in text_norm:
        return n
    # Another copy of the same report: its title through its period ("treasurer's report 2025 08"), whatever follows.
    parts = re.findall(r"\d+", str(period_of or ""))
    period = " ".join(parts)
    if period and period in n:
        title = n[: n.index(period)]
        # The period as the name has it, or month first ("06 2024"), as a link's title may.
        for stub in (title + period, title + " ".join(reversed(parts))):
            if len(stub) >= 15 and re.search(re.escape(stub) + r"(?!\d)", text_norm):
                return stub
    if "…" in text_raw:
        for cut in re.finditer(r"([^\n…]{20,90})…", text_raw):
            stub = _norm(cut.group(1)).strip()
            for k in range(len(stub)):
                tail = stub[k:]
                if len(tail) >= 20 and n.startswith(tail):
                    return tail
    return ""


def _as_written(normalized: str) -> str:
    """A pattern that finds a normalized name in the text as written."""
    out = []
    for ch in normalized:
        out.append(r"[\s_\-.]+" if ch == " " else "['’]" if ch == "'" else re.escape(ch))
    return "".join(out)


def _minutes_report(a: Assignment, due: date, rule: EvidenceRule, stores: Stores) -> list[Finding]:
    reports = [r for r in stores.readings() if r.get("kind") in rule.kinds and r.get("hasText")]
    out = []
    for day in meeting_days(a, due, rule, stores):
        for m in stores.minutes().get(day, []):
            if m.confidential:
                continue
            raw = stores.text(m.id).replace("​", " ")
            text_norm = _norm(raw)
            # One report per period: the copy the minutes name most fully (the one the board was given), then one
            # not confidential. The words must be in that copy, not only in another.
            named: dict[str, tuple[tuple[int, int, bool], str, dict[str, Any]]] = {}
            for r in reports:
                name = _norm(str(r.get("name") or ""))
                how = _named_in(str(r.get("name") or ""), text_norm, raw, str(r.get("period") or ""))
                if not how:
                    continue
                key = str(r.get("period") or r.get("name"))
                rank = (-int(how == name), -len(how), bool(r.get("confidential")))
                if key not in named or rank < named[key][0]:
                    named[key] = (rank, how, r)
            for _, how, r in sorted(named.values(), key=lambda x: text_norm.find(x[1])):
                lines = _report_lines(stores.text(str(r["id"])), rule.words)
                if not lines:
                    continue
                quoted = passages(raw, [_as_written(how)])
                out.append(Finding(rule.key, rule.weight, rule.source, m.label, day, quoted[0] if quoted else "",
                                   f"names {r.get('name')} (period {r.get('period')}), which holds: "
                                   f"{'; '.join(lines)}. {rule.note}"))
    return out


def _meeting_notice(a: Assignment, due: date, rule: EvidenceRule, stores: Stores) -> list[Finding]:
    out = []
    for day in meeting_days(a, due, rule, stores):
        # The notice to members (PayHOA's log, its Gmail copy, the delivery ledger); an agenda emailed on its own
        # only when no notice is on record.
        notices: list[tuple[date, str, str]] = []
        agendas: list[tuple[date, str, str]] = []
        for rec in stores.meetings().get(day, {}).get("records", []):
            if rec.get("kind") in ("meeting notice", "agenda") and rec.get("sent"):
                d = stores.local_day(rec["sent"])
                if d and d <= day:
                    (notices if rec["kind"] == "meeting notice" else agendas).append(
                        (d, f"{rec.get('name')} ({rec.get('where')})", rec.get("note") or ""))
        for key, stamp in stores.ledger().items():
            d = stores.local_day(stamp)
            if day.isoformat() in key and d and d <= day:
                notices.append((d, f"{key} (notice ledger)", ""))
        sent = notices or agendas
        if not sent:
            continue
        first = min(sent, key=lambda s: (s[0], "preview" in s[1].lower(), s[1]))
        lead = (day - first[0]).days
        if lead >= rule.days:
            out.append(Finding(rule.key, rule.weight, rule.source, first[1], first[0], "",
                               f"sent {lead} days before the meeting of {day}" + (f"; {first[2]}" if first[2] else "")))
        else:
            out.append(Finding(rule.key, Weight.AGAINST, rule.source, first[1], first[0], "",
                               f"sent only {lead} day{'s' if lead != 1 else ''} before the meeting of {day}; "
                               f"at least {rule.days} are required"))
    return out


def _minutes_filed(a: Assignment, due: date, rule: EvidenceRule, stores: Stores) -> list[Finding]:
    out = []
    meeting = _anchor_day(a, due)
    days = [d for d in stores.held() if (d.year, d.month) == (meeting.year, meeting.month)
            or abs((d - meeting).days) <= MEETING_SLACK_DAYS]
    drive = stores.drive_files()
    for day in days:
        records = [r for r in stores.meetings().get(day, {}).get("records", []) if r.get("kind") == "minutes"]
        dated: list[tuple[date, str]] = []
        undated: list[str] = []
        for r in records:
            label = f"{r.get('name')} ({r.get('where')})"
            d = None
            if r.get("sent"):
                d = stores.local_day(r["sent"])
            elif r.get("where") == "Drive" and r.get("ref") in drive:
                d = stores.local_day(drive[r["ref"]].get("created") or "")
            (dated.append((d, label)) if d else undated.append(label))
        if not records:
            undated += [m.label for m in stores.minutes().get(day, [])]
        if dated:
            first = min(dated)
            late = (first[0] - day).days
            if late <= rule.days:
                out.append(Finding(rule.key, rule.weight, rule.source, first[1], first[0], "",
                                   f"the earliest dated copy is {late} days after the meeting of {day}. {rule.note}"))
            else:
                out.append(Finding(rule.key, Weight.AGAINST, rule.source, first[1], first[0], "",
                                   f"the earliest dated copy is {late} days after the meeting of {day}, past "
                                   f"{rule.days}; an earlier copy may be where jason does not look"))
        elif undated:
            out.append(Finding(rule.key, Weight.SUPPORTING, rule.source, undated[0], day, "",
                               f"minutes of {day} on file, undated. {rule.note}"))
    return out


def _meeting_held(a: Assignment, due: date, rule: EvidenceRule, stores: Stores) -> list[Finding]:
    out = []
    for day in meeting_days(a, due, rule, stores):
        minutes = stores.minutes().get(day, [])
        if minutes:
            out.append(Finding(rule.key, rule.weight, rule.source, minutes[0].label, day, "",
                               f"minutes of the meeting of {day}"))
            continue
        m = stores.meetings().get(day, {})
        kinds = sorted(k for k in m.get("has", {}) if k not in ("correspondence",))
        if not kinds:
            continue
        held = bool(set(kinds) & HELD_KINDS)
        out.append(Finding(rule.key, rule.weight if held else Weight.SUPPORTING, rule.source,
                           "; ".join(m.get("titles") or []) or "meeting catalog", day, "",
                           f"on record: {', '.join(kinds)}" + ("" if held else "; noticed, but its holding is not shown")))
    return out


def _mailing(a: Assignment, due: date, rule: EvidenceRule, stores: Stores) -> list[Finding]:
    lo, hi = due + timedelta(days=rule.window[0]), due + timedelta(days=rule.window[1])
    out, seen = [], set()
    for day, what, where in sorted(stores.mailings()):
        if not lo <= day <= hi or not any(re.search(w, what, re.I) for w in rule.words):
            continue
        if (day, what) in seen:
            continue
        seen.add((day, what))
        out.append(Finding(rule.key, rule.weight, rule.source, f"{what} ({where})", day, "", rule.note))
    return out[:3]


def _library_file(a: Assignment, due: date, rule: EvidenceRule, stores: Stores) -> list[Finding]:
    year = str(_anchor_day(a, due).year + rule.year_offset)
    out = []
    for r in stores.library():
        if r.get("kind") not in rule.kinds or not str(r.get("period") or "").startswith(year):
            continue
        if rule.words and not any(re.search(w, str(r.get("name") or ""), re.I) for w in rule.words):
            continue
        out.append(Finding(rule.key, rule.weight, rule.source, f"{r.get('path') or r.get('name')} (PayHOA library "
                           f"{r.get('id')})", None, "", rule.note))
    return out[:3]


SOURCES = {
    EvidenceSource.MINUTES_TEXT: _minutes_text,
    EvidenceSource.MINUTES_REPORT: _minutes_report,
    EvidenceSource.MEETING_NOTICE: _meeting_notice,
    EvidenceSource.MINUTES_FILED: _minutes_filed,
    EvidenceSource.MEETING_HELD: _meeting_held,
    EvidenceSource.MAILING: _mailing,
    EvidenceSource.LIBRARY_FILE: _library_file,
}


def _obligation_proposals(a: Assignment, rule: EvidenceRule, stores: Stores, start: date, end: date
                          ) -> list[tuple[date, list[Finding]]]:
    """A duty that covers recurring deadlines: each fixed deadline in the window that PayHOA shows paid (on time, or
    late), with its payments. A deadline with no payment is not proposed."""
    names = {c.split(":", 1)[1] for c in a.covers if c.startswith("obligation:")}
    out = []
    for row in stores.obligations():
        if row.get("name") not in names:
            continue
        for h in row.get("history") or []:
            due = _date(h.get("deadline")) if isinstance(h, dict) else None
            if due is None or not start <= due <= end or not h.get("evidence"):
                continue
            late = h.get("daysLate")
            findings = [Finding(rule.key, Weight.AGAINST if late else rule.weight, rule.source,
                                f"{p.get('payee')} ({p.get('category') or 'no category'}), "
                                f"${int(p.get('amountCents') or 0) / 100:,.2f} (PayHOA payment)",
                                _date(p.get("date")), "",
                                f"{row['name']}: " + (f"paid {late} days after the deadline" if late else rule.note))
                        for p in h["evidence"][:3]]
            out.append((due, findings))
    return out


# ---------------------------------------------------------------------------------------------------------------


def propose(community: Any, data_dir: Path, *, start: date, end: date, keys: Iterable[str] = (),
            stores: Stores | None = None) -> list[Proposal]:
    """Every occurrence from ``start`` to ``end`` of every assignment an evidence rule serves (or only ``keys``), with
    the evidence found for it. Declined and not-applicable assignments are left out."""
    from jason.tasks.schedule import completions

    stores = stores or Stores(data_dir, community)
    wanted = set(keys)
    done = {(r["key"], r["due"]): r for r in completions(data_dir)}
    # Anchors well beyond the window, so a clock that runs from a meeting outside it still lands inside it.
    anchors = anchors_for(community, start - timedelta(days=400), end + timedelta(days=400))
    out: list[Proposal] = []
    for a in assignments(community):
        if a.adoption in (Adoption.DECLINED, Adoption.NOT_APPLICABLE) or (wanted and a.key not in wanted):
            continue
        rules = rules_for(a, community)
        if not rules:
            continue
        by_due: dict[date, Proposal] = {}
        for due in occurrences(a, start, end, anchors):
            p = by_due.setdefault(due, Proposal(a, due, done=done.get((a.key, due.isoformat()))))
            for rule in rules:
                if rule.source in SOURCES:
                    p.findings += SOURCES[rule.source](a, due, rule, stores)
        for rule in rules:
            if rule.source is EvidenceSource.PAYMENTS:
                for due, findings in _obligation_proposals(a, rule, stores, start, end):
                    p = by_due.setdefault(due, Proposal(a, due, done=done.get((a.key, due.isoformat()))))
                    p.findings += findings
        out += by_due.values()
    return sorted(out, key=lambda p: (p.due, p.assignment.key))


def unserved(community: Any) -> list[str]:
    """The assignments with occurrences (a cadence or an anchored clock) that no evidence rule serves."""
    out = []
    for a in assignments(community):
        if a.adoption in (Adoption.DECLINED, Adoption.NOT_APPLICABLE) or a.trigger not in (Trigger.CADENCE,
                                                                                             Trigger.ANCHORED):
            continue
        if not rules_for(a, community):
            out.append(a.key)
    return out


def summary(proposals: list[Proposal]) -> dict[str, dict[str, int]]:
    """Per assignment: how many occurrences stand recorded, proposed, partial, contrary, or with none."""
    out: dict[str, dict[str, int]] = {}
    for p in proposals:
        row = out.setdefault(p.assignment.key, {"occurrences": 0, "recorded": 0, "proposed": 0, "partial": 0,
                                                 "contrary": 0, "none": 0})
        row["occurrences"] += 1
        row[p.standing] += 1
    return out


def find(proposals: list[Proposal], key: str, due: date) -> Proposal | None:
    return next((p for p in proposals if p.assignment.key == key and p.due == due), None)


def record(data_dir: Path, proposal: Proposal, by: str, *, on: date | None = None, evidence: str = "") -> dict[str, Any]:
    """A person's confirmation of a proposal: recorded as done (``schedule.record_done``) with their name and the
    evidence they confirmed. A proposal with no evidence needs the person's own."""
    from jason.tasks.schedule import record_done

    text = evidence or proposal.evidence_text()
    if not text:
        raise ValueError("nothing was found for this occurrence; give the evidence with --evidence")
    return record_done(data_dir, proposal.assignment.key, proposal.due, on or proposal.done_on or date.today(), by, text)


def store_path(data_dir: Path) -> Path:
    return Path(data_dir) / "schedule" / "evidence.json"


def write(data_dir: Path, proposals: list[Proposal], *, start: date, end: date) -> Path:
    """The proposals as built (``data/schedule/evidence.json``), for the packet and the tools; private like the
    completions."""
    path = store_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "from": start.isoformat(), "to": end.isoformat(),
                                "summary": summary(proposals), "proposals": [p.row() for p in proposals],
                                "caveats": list(CAVEATS)}, indent=1), encoding="utf-8")
    return path


def lines(proposals: list[Proposal], *, show_none: bool = False) -> list[str]:
    out = []
    for p in proposals:
        if p.standing == "none" and not show_none:
            continue
        a = p.assignment
        tail = f" (recorded {p.done['done']} by {p.done['by']})" if p.done else ""
        out.append(f"{p.due}  {p.standing:9} {a.key} [{a.role.value}]: {a.title}{tail}")
        for f in p.findings:
            when = f" {f.day}" if f.day else ""
            out.append(f"    [{f.weight.value}] {f.source.value}: {f.file}{when}")
            if f.passage:
                out.append(f"        \"{f.passage}\"")
            if f.note:
                out.append(f"        {f.note}")
    return out


__all__ = ["CAVEATS", "Finding", "Proposal", "Stores", "find", "lines", "meeting_days", "passages", "propose",
           "record", "store_path", "summary", "unserved", "write"]
