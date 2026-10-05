"""The inbox of responses to a request: one place to ask "has anyone answered?" over every way an owner can answer
(docs/responses-design.md).

``check`` looks at each channel, live and read-only, for arrivals not yet kept, and keeps only jason's own inbox on disk
(``data/responses/``). ``read`` downloads an arrival's attachments and reads the form from them; ``confirm`` is a person
saying "this is what it says" (with corrections) and makes the same ``FormAnswers`` a PayHOA submission becomes, which
``owner_info_apply.gather_answers`` takes as one more channel. ``mark_recorded`` is what ``jason owner-info --apply
--yes`` calls (through ``observe_plan``) once the writes an arrival calls for are made.

```text
data/responses/
  inbox.json          arrivals by id, and per channel when it last succeeded and how it ended
  acts.jsonl          every act: who, when, what, why (append-only)
  files/<id>/         an arrival's attachments, downloaded by ``read`` (private; ``jason.web.access``: P3)
  readings/<id>.json  the reading of each (fields, confidence, how it was read)
  keyed/<id>.json     the confirmed answers, as ``FormAnswers``
```

An arrival's id is ``<channel>:<native id>``; on disk the colon is a hyphen. Writes take the store lock
``responses-<profile>``. Nothing here writes to Gmail, PayHOA, or Drive, sends anything, or stores a personal email
address on an arrival; a reading is evidence for a person, never an answer.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Mapping, NamedTuple

from jason.community.forms import CHOICE_KINDS, FormAnswers, FormKey, option_key
from jason.community.response_inbox import Arrival, Channel, ResponseRequest, State

ROOT = "responses"
INBOX = "inbox.json"
ACTS = "acts.jsonl"
FILES = "files"
READINGS = "readings"
KEYED = "keyed"
WITHDRAWN = "withdrawn"
OVERLAP = timedelta(days=1)                 # a check reads from a day before the last that succeeded
FORM_FILE_TYPES = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".heic")
# A signature's logo or an inline picture is not a returned form.
_INLINE = re.compile(r"(?i)^(image\d*|logo\w*|outlook-\w+|~wrd\d+|att\d+|unnamed)\.(png|jpe?g|gif)$")
SMALLEST_IMAGE = 15_000                     # bytes: a picture smaller than this is a logo, not a photographed form


class ResponseError(RuntimeError):
    """A response act refused: an unknown arrival, a state the act does not apply to, or a missing name or reason."""


class Ended(Enum):
    OK = "ok"
    SIGN_IN = "sign-in"         # the scheduler's sign-in pause, not a retry
    FAILED = "failed"
    SKIPPED = "skipped"         # no client, no request that uses the channel, or every window closed


# -- small helpers ------------------------------------------------------------------------------------------------------

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def when(value: Any) -> datetime | None:
    """A time as an aware UTC datetime: an ISO string (a trailing Z, or none: UTC), a datetime, or epoch milliseconds."""
    if value in (None, ""):
        return None
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, (int, float)):
        moment = datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    else:
        text = str(value).strip().replace("Z", "+00:00")
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            try:
                moment = datetime.fromisoformat(text[:10])
            except ValueError:
                return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def scrub(text: Any, limit: int = 160) -> str:
    """A subject or a name with each email address and phone number replaced: a personal address is never kept."""
    from jason.approvals.audit import mask

    return " ".join(str(mask(str(text or ""), addresses=False)).split())[:limit]


def responses_dir(data_dir: Path) -> Path:
    return Path(data_dir) / ROOT


def _safe(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "file"


@contextmanager
def locked(purpose: str = "") -> Iterator[None]:
    """The store lock ``responses-<profile>`` (re-entrant within a process)."""
    from jason.locks import Resource, account, hold

    with hold(Resource.STORE, f"responses-{account()}", purpose=purpose or "the responses inbox"):
        yield


def _write_json(path: Path, body: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(body, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# -- the inbox and its acts ---------------------------------------------------------------------------------------------

@dataclass
class Inbox:
    arrivals: dict[str, Arrival] = field(default_factory=dict)
    channels: dict[str, dict[str, Any]] = field(default_factory=dict)       # per channel: lastOk, lastTried, ended, reason...


def load_inbox(data_dir: Path) -> Inbox:
    path = responses_dir(data_dir) / INBOX
    if not path.is_file():
        return Inbox()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return Inbox({k: Arrival.from_json(v) for k, v in (raw.get("arrivals") or {}).items()}, dict(raw.get("channels") or {}))


def save_inbox(data_dir: Path, inbox: Inbox) -> None:
    _write_json(responses_dir(data_dir) / INBOX,
                {"version": 1, "channels": inbox.channels,
                 "arrivals": {k: a.to_json() for k, a in sorted(inbox.arrivals.items())}})


def log_act(data_dir: Path, act: str, arrival_id: str, by: str, why: str = "", **detail: Any) -> dict[str, Any]:
    """One line in ``acts.jsonl``: who, when, what, why. Never an answer's value: a field's name, not its text."""
    line = {"at": iso(now_utc()), "by": by, "act": act, "id": arrival_id, "why": why, **detail}
    path = responses_dir(data_dir) / ACTS
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def acts_for(data_dir: Path, arrival_id: str = "") -> list[dict[str, Any]]:
    path = responses_dir(data_dir) / ACTS
    if not path.is_file():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [r for r in rows if not arrival_id or r.get("id") == arrival_id]


# -- who an address belongs to (in memory only) --------------------------------------------------------------------------

class OwnerRef(NamedTuple):
    """The owner an address belongs to, as PayHOA's stored catalog knows it. The address is the key of a dictionary built
    for one run and dropped; only the unit and the name are ever kept."""
    unit: str
    name: str
    unit_id: int | None = None
    membership_id: int | None = None


def owner_directory(data_dir: Path, community: Any) -> dict[str, OwnerRef]:
    """Each current owner's email address (lower case) to the owner, from the stored PayHOA catalog on disk
    (``data/payhoa.db``); empty when there is none. Never written anywhere."""
    db = Path(data_dir) / "payhoa.db"
    if not db.is_file():
        return {}
    from jason.tasks.member_preferences import payhoa_owners

    try:
        units = payhoa_owners(db, tags=community.payhoa_tags())
    except Exception:  # noqa: BLE001 - a catalog that cannot be read is no directory
        return {}
    return {o.email.casefold(): OwnerRef(u.label, o.name, u.unit_id, o.membership_id)
            for u in units for o in u.owners if o.email}


# -- the channels -------------------------------------------------------------------------------------------------------

def is_form_file(part: Mapping[str, Any]) -> bool:
    """An attachment that could be a returned form: a PDF or an image, not a signature's logo or an inline picture."""
    name = str(part.get("name") or "")
    kind = str(part.get("type") or "").lower()
    pdf = kind == "application/pdf" or name.lower().endswith(".pdf")
    image = kind.startswith("image/") or name.lower().endswith(FORM_FILE_TYPES)
    if not (pdf or image):
        return False
    if pdf:
        return True
    if _INLINE.match(name) or kind == "image/gif":
        return False
    size = part.get("size")
    return not (isinstance(size, int) and size < SMALLEST_IMAGE)


class PayhoaChannel:
    """The form's submissions (``list_form_submissions``): a submission not yet kept, test accounts excluded. A
    submission PayHOA already marks complete is kept as seen: nothing waits on it."""

    channel = Channel.PAYHOA

    def __init__(self, client: Any, request: ResponseRequest, *, org_id: int, record: Mapping[str, Any] | None,
                 known: Iterable[str] = (), tests: Iterable[int] = ()) -> None:
        self.client, self.request, self.org_id, self.record = client, request, org_id, record
        self.known, self.tests = set(known), {int(t) for t in tests}
        self.statuses: dict[str, str] = {}          # every submission read: native id -> PayHOA's status
        self.looked = 0
        self.excluded = 0

    def check(self, since: datetime) -> list[Arrival]:
        if not self.record:
            raise ResponseError(f"no PayHOA form is recorded for {self.request.payhoa_form!r} (data/payhoa/forms.json)")
        out = []
        for row in self.client.list_form_submissions(int(self.record["formId"])):
            sid = str(row.get("id"))
            self.looked += 1
            status = str(row.get("status") or "")
            self.statuses[f"payhoa:{sid}"] = status
            if f"payhoa:{sid}" in self.known:
                continue
            detail = self.client.get_form_submission(self.org_id, int(row["id"]))
            sub = detail.get("submission") or detail
            membership = sub.get("membershipId", row.get("membershipId"))
            if membership is not None and int(membership) in self.tests:
                self.excluded += 1
                continue
            created = when(sub.get("createdAt") or row.get("createdAt") or row.get("created"))
            if created is not None and created < since:
                continue
            unit = sub.get("unit") or {}
            out.append(Arrival(
                f"payhoa:{sid}", self.request.key, Channel.PAYHOA, iso(created) if created else "", _person(sub, row),
                scrub(unit.get("title") or unit.get("streetAddress") or row.get("unit") or ""), self.request.form.title,
                (), State.SEEN if status == "complete" else State.NEW, "", note=f"PayHOA status: {status or 'unknown'}"))
        return out


def _person(sub: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    """The name PayHOA gives the member who sent a submission (a display name; no address)."""
    for holder in (sub.get("membership"), sub.get("member"), sub.get("owner"), row.get("membership"), row.get("member")):
        if isinstance(holder, Mapping):
            profile = holder.get("profile") or {}
            name = holder.get("name") or " ".join(x for x in (profile.get("givenNames") or holder.get("givenNames"),
                                                              profile.get("familyName") or holder.get("familyName")) if x)
            if name:
                return scrub(name, 80)
    return scrub(sub.get("memberName") or row.get("memberName") or "an owner signed in to PayHOA", 80)


class Message(NamedTuple):
    """One Gmail message as judged: whether it is a candidate, and why or why not. No address."""
    id: str
    at: str
    who: str
    subject: str
    attachments: tuple[str, ...]
    candidate: bool
    reason: str
    unit: str = ""


class GmailChannel:
    """Messages since the request opened that reached the association's own addresses or groups, from outside the
    association's domains, and carrying a PDF or an image or coming from an address PayHOA holds for a current owner.
    Headers and attachment names only; nothing is downloaded. A group-rewritten sender is read from ``X-Original-From``
    (``tasks.gmail._senders``). ``check(since, sender=ADDRESS)`` lists every message from that address (``listed``) and
    keeps only the candidates."""

    channel = Channel.GMAIL

    def __init__(self, gmail: Any, request: ResponseRequest, *, own: Iterable[str], owners: Mapping[str, OwnerRef] | None = None,
                 known: Iterable[str] = (), limit: int = 500) -> None:
        self.gmail, self.request = gmail, request
        self.own = {d.casefold() for d in own}
        self.owners = dict(owners or {})
        self.known, self.limit = set(known), limit
        self.listed: list[Message] = []
        self.looked = 0

    @staticmethod
    def headers() -> tuple[str, ...]:
        from jason.tasks.gmail import GROUP_HEADERS, ORIGINAL_SENDER

        return ("From", "To", "Cc", "Subject", "Date", *ORIGINAL_SENDER, *GROUP_HEADERS)

    def query(self, since: datetime, sender: str = "") -> str:
        who = re.sub(r'["\s]', "", sender)
        return f"after:{since.astimezone(timezone.utc):%Y/%m/%d} -in:sent" + (f' from:"{who}"' if who else "")

    def judge(self, meta: Mapping[str, Any]) -> Message:
        from jason.tasks.gmail import _groups, _header, _host, _people, _senders, _when

        head = meta.get("headers") or {}
        senders, via = _senders(head, self.own)
        name, address = senders[0] if senders else ("", "")
        files = tuple(p["name"] for p in meta.get("attachments") or [] if is_form_file(p))
        owner = self.owners.get(address)
        who = owner.name if owner else (name if name and "@" not in name else "")
        base = dict(id=str(meta.get("id")), at=_when(dict(meta)), who=scrub(who or "an unnamed sender", 80),
                    subject=scrub(head.get("Subject") or _header(head, "Subject")), attachments=files,
                    unit=owner.unit if owner else "")
        if "SENT" in (meta.get("labels") or []):
            return Message(**base, candidate=False, reason="sent by the association")
        if not address:
            return Message(**base, candidate=False, reason="no sender could be read")
        if _host(address) in self.own:
            return Message(**base, candidate=False, reason="from the association's own domain")
        recipients = _people(_header(head, "To")) + _people(_header(head, "Cc"))
        if not (any(_host(a) in self.own for _, a in recipients) or _groups(head, self.own, via)):
            return Message(**base, candidate=False, reason="did not reach an association address or group")
        if files:
            return Message(**base, candidate=True, reason="carries a PDF or an image")
        if owner:
            return Message(**base, candidate=True, reason="from an address PayHOA holds for a current owner")
        return Message(**base, candidate=False, reason="no PDF or image, and not from a current owner's address")

    def messages(self, since: datetime, *, sender: str = "") -> list[Message]:
        """Every message in the window (from ``sender`` when given) as judged. Without a sender, one already kept is not
        read again."""
        out = []
        for row in self.gmail.iter_messages(self.query(since, sender), limit=self.limit):
            if not sender and f"gmail:{row['id']}" in self.known:
                continue
            self.looked += 1
            meta = self.gmail.get_metadata(row["id"], headers=self.headers())
            at = when(meta.get("internalDate"))
            if at is not None and at < since:
                continue
            out.append(self.judge(meta))
        return out

    def check(self, since: datetime, *, sender: str = "") -> list[Arrival]:
        found = self.messages(since, sender=sender)
        if sender:
            self.listed = found
        return [Arrival(f"gmail:{m.id}", self.request.key, Channel.GMAIL, m.at, m.who, m.unit, m.subject, m.attachments)
                for m in found if m.candidate and f"gmail:{m.id}" not in self.known]


class DiskMail:
    """The mail service's items already on disk (``data/mail``): no service is called."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def items(self) -> dict[str, dict[str, Any]]:
        from jason.tasks.mail import load_items

        return load_items(self.data_dir)

    def text(self, mail_id: str) -> str:
        from jason.tasks.mail import mail_dir

        path = mail_dir(self.data_dir) / mail_id / "text.txt"
        return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""

    def scan(self, mail_id: str) -> Path:
        from jason.tasks.mail import SCAN, mail_dir

        return mail_dir(self.data_dir) / mail_id / SCAN


def campaigns_in(text: str) -> set[str]:
    """The campaigns of the form markers a scan's text carries (a marker one character off counts as a hint)."""
    from jason.community.form_refs import parse, repaired

    return {m.campaign for m in [*parse(text), *repaired(text)]}


class MailChannel:
    """A scan on disk whose text carries the request's form marker. A letter that holds a credential is never a
    candidate."""

    channel = Channel.MAIL

    def __init__(self, source: Any, request: ResponseRequest, *, known: Iterable[str] = ()) -> None:
        self.source, self.request, self.known = source, request, set(known)
        self.looked = 0

    def check(self, since: datetime) -> list[Arrival]:
        out = []
        for mail_id, row in self.source.items().items():
            received = when(row.get("received"))
            if row.get("credential") or received is None or received < since or f"mail:{mail_id}" in self.known:
                continue
            self.looked += 1
            text = self.source.text(mail_id)
            ours = sorted(c for c in campaigns_in(text) if self.request.names_campaign(c)) if text else []
            if not ours:
                continue
            out.append(Arrival(f"mail:{mail_id}", self.request.key, Channel.MAIL, iso(received),
                               scrub(row.get("sender") or "a mailed return", 60), "", f"Mailed return, marker {ours[0]}",
                               ("contents.pdf",)))
        return out


class SavedForms:
    """A Google Form's saved responses on disk (``data/forms/<form id>/responses.json``)."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)

    def responses(self, source: str) -> dict[str, Any] | None:
        from jason.tasks.forms import forms_dir

        path = forms_dir(self.data_dir) / source / "responses.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


class FormsChannel:
    """The saved responses of a Google Form (``ResponseRequest.imports``): a response id not yet kept."""

    channel = Channel.FORMS

    def __init__(self, saved: Any, request: ResponseRequest, *, known: Iterable[str] = ()) -> None:
        self.saved, self.request, self.known = saved, request, set(known)
        self.looked = 0

    def check(self, since: datetime) -> list[Arrival]:
        from jason.tasks.forms import import_responses

        out = []
        for rules in self.request.imports:
            saved = self.saved.responses(rules.source)
            for answers in import_responses(saved, rules) if saved else []:
                native = answers.source.split(":", 1)[-1]
                self.looked += 1
                sent = when(answers.submitted)
                if f"forms:{native}" in self.known or sent is None or sent < since:
                    continue
                out.append(Arrival(f"forms:{native}", self.request.key, Channel.FORMS, iso(sent),
                                   scrub(answers.answers.get("name") or "", 80),
                                   scrub(answers.answers.get("unit-address") or "", 80), rules.title))
        return out


# -- the check ----------------------------------------------------------------------------------------------------------

@dataclass
class ChannelReport:
    channel: Channel
    ended: Ended = Ended.OK
    reason: str = ""
    looked: int = 0
    kept: int = 0


@dataclass
class CheckReport:
    at: str
    by: str
    channels: list[ChannelReport] = field(default_factory=list)
    kept: list[Arrival] = field(default_factory=list)
    listed: list[Message] = field(default_factory=list)         # a ``sender`` search: every message, candidate or not

    @property
    def failed(self) -> list[ChannelReport]:
        return [c for c in self.channels if c.ended in (Ended.FAILED, Ended.SIGN_IN)]


def signed_out(exc: BaseException) -> bool:
    """Whether a failure is a missing sign-in (Keeper, Google, PayHOA): the scheduler's pause, not a retry."""
    from jason.integrations.checks import _SIGN_IN

    return bool(_SIGN_IN.search(f"{type(exc).__name__}: {exc}"))


def _reason(exc: BaseException) -> str:
    from jason.integrations.checks import _mask

    return _mask(f"{type(exc).__name__}: {exc}")


def uses(request: ResponseRequest, channel: Channel) -> bool:
    """Whether the request can be answered by the channel."""
    return {Channel.PAYHOA: bool(request.payhoa_form), Channel.GMAIL: True, Channel.MAIL: bool(request.marker_campaigns),
            Channel.FORMS: bool(request.imports)}[channel]


def check(data_dir: Path, community: Any, *, clients: Mapping[Channel, Callable[[], Any]], by: str,
          channels: Iterable[Channel] | None = None, since: date | None = None, sender: str = "",
          now: datetime | None = None, owners: Mapping[str, OwnerRef] | None = None, tests: Iterable[int] | None = None,
          requests: Iterable[ResponseRequest] | None = None) -> CheckReport:
    """Look at each channel, live and read-only, for arrivals not yet kept; keep the new ones in the inbox.

    ``clients`` maps a channel to a function that makes its client (PayHOA's, Gmail's), called only when the channel is
    checked, so a missing sign-in fails that channel alone and is reported with its reason; the mail and Google Form
    channels read disk and need none. ``since`` replaces the window (a person asked); ``sender`` searches Gmail for every
    message from an address in the window (``CheckReport.listed``) and keeps only the candidates. The window is the
    request's own (``ResponseRequest.window``); a check keeps the time each request last succeeded per channel and reads
    from a day before it. Test accounts (``jason.config.test_memberships``) are never an owner's answer."""
    data_dir = Path(data_dir)
    moment = now or now_utc()
    today = moment.date()
    todo = tuple(requests if requests is not None else community.response_requests())
    wanted = [c for c in Channel if not channels or c in set(channels)]
    if sender:
        wanted = [c for c in wanted if c is Channel.GMAIL]
    factories: dict[Channel, Callable[[], Any]] = {Channel.MAIL: lambda: DiskMail(data_dir),
                                                   Channel.FORMS: lambda: SavedForms(data_dir), **dict(clients)}
    snapshot = load_inbox(data_dir)
    known = set(snapshot.arrivals)
    report = CheckReport(iso(moment), by)
    found: list[Arrival] = []
    statuses: dict[str, str] = {}
    covered: dict[tuple[str, str], str] = {}
    for channel in wanted:
        rep = ChannelReport(channel)
        report.channels.append(rep)
        watched, closed = [], []
        for request in todo:
            if not uses(request, channel):
                continue
            (closed if request.window(since).closed(today) else watched).append(request)
        if not watched:
            rep.ended = Ended.SKIPPED
            rep.reason = ("the window is closed for " + ", ".join(r.key for r in closed) + " (past a week after the "
                          "return-by date; a person's --since reads on)") if closed else "no request is answered by this channel"
            continue
        try:
            client = factories[channel]() if channel in factories else None
            if client is None:
                rep.ended, rep.reason = Ended.SKIPPED, "no client was given for this channel"
                continue
            for request in watched:
                last = (snapshot.channels.get(channel.value) or {}).get("requests", {}).get(request.key)
                begin = datetime.combine(since or request.window().start, datetime.min.time(), tzinfo=timezone.utc)
                if since is None and last and when(last):
                    begin = max(begin, when(last) - OVERLAP)
                view = _channel_for(channel, client, request, data_dir, community, known, tests, owners)
                arrivals = view.check(begin, sender=sender) if channel is Channel.GMAIL else view.check(begin)
                found += arrivals
                rep.looked += view.looked
                report.listed += getattr(view, "listed", [])
                statuses.update(getattr(view, "statuses", {}))
                if since is None and not sender:
                    covered[(channel.value, request.key)] = report.at
        except Exception as exc:  # noqa: BLE001 - one channel failing never stops the others
            rep.ended = Ended.SIGN_IN if signed_out(exc) else Ended.FAILED
            rep.reason = _reason(exc)
    with locked("keep new arrivals"):
        inbox = load_inbox(data_dir)
        for a in found:
            if a.id in inbox.arrivals:
                continue
            a = replace(a, kept_at=report.at)
            inbox.arrivals[a.id] = a
            report.kept.append(a)
            next(r for r in report.channels if r.channel is a.channel).kept += 1
            log_act(data_dir, "kept", a.id, by, f"found by a check of {a.channel.value}")
            if a.state is State.SEEN:
                log_act(data_dir, "seen", a.id, "check", a.note)
        for aid, status in statuses.items():                 # a request completed in PayHOA since it was kept
            a = inbox.arrivals.get(aid)
            if a is not None and a.state is State.NEW and status == "complete":
                inbox.arrivals[aid] = replace(a, state=State.SEEN, note=f"PayHOA status: {status}")
                log_act(data_dir, "seen", aid, "check", "complete in PayHOA")
        for rep in report.channels:
            record = inbox.channels.setdefault(rep.channel.value, {})
            record.update(lastTried=report.at, ended=rep.ended.value, reason=rep.reason, looked=rep.looked, kept=rep.kept)
            if rep.ended is Ended.OK:
                record["lastOk"] = report.at
        for (channel_key, request_key), stamp in covered.items():
            if next(r for r in report.channels if r.channel.value == channel_key).ended is Ended.OK:
                inbox.channels[channel_key].setdefault("requests", {})[request_key] = stamp
        _supersede(data_dir, inbox, by)
        save_inbox(data_dir, inbox)
    return report


def _channel_for(channel: Channel, client: Any, request: ResponseRequest, data_dir: Path, community: Any,
                 known: set[str], tests: Iterable[int] | None, owners: Mapping[str, OwnerRef] | None) -> Any:
    if channel is Channel.PAYHOA:
        from jason.config import test_memberships
        from jason.tasks.payhoa_forms import record_for

        return PayhoaChannel(client, request, org_id=int(community.org_id), record=record_for(data_dir, request.payhoa_form),
                             known=known, tests=test_memberships() if tests is None else tests)
    if channel is Channel.GMAIL:
        return GmailChannel(client, request, own=community.email_domains(),
                            owners=owner_directory(data_dir, community) if owners is None else owners, known=known)
    if channel is Channel.MAIL:
        return MailChannel(client, request, known=known)
    return FormsChannel(client, request, known=known)


# -- the acts -----------------------------------------------------------------------------------------------------------

def _need(value: str, what: str) -> str:
    if not str(value or "").strip():
        raise ResponseError(f"{what} is required: an act names who did it")
    return value.strip()


def _get(inbox: Inbox, arrival_id: str) -> Arrival:
    try:
        return inbox.arrivals[arrival_id]
    except KeyError:
        raise ResponseError(f"no arrival {arrival_id!r} in the inbox (jason responses --list)") from None


def get(data_dir: Path, arrival_id: str) -> Arrival:
    return _get(load_inbox(data_dir), arrival_id)


def _set(inbox: Inbox, arrival_id: str, **changes: Any) -> Arrival:
    updated = replace(inbox.arrivals[arrival_id], **changes)
    inbox.arrivals[arrival_id] = updated
    return updated


def seen(data_dir: Path, ids: Iterable[str], *, by: str) -> list[str]:
    """Mark arrivals a person looked at and left. Only a new arrival moves; the ids that moved are returned."""
    _need(by, "--by")
    moved = []
    with locked("mark seen"):
        inbox = load_inbox(data_dir)
        ids = list(ids)
        for arrival_id in ids:
            _get(inbox, arrival_id)                 # every id is known before any is marked
        for arrival_id in ids:
            if inbox.arrivals[arrival_id].state is State.NEW:
                _set(inbox, arrival_id, state=State.SEEN)
                log_act(data_dir, "seen", arrival_id, by, "looked at and left")
                moved.append(arrival_id)
        save_inbox(data_dir, inbox)
    return moved


def seen_all(data_dir: Path, *, by: str, request: str = "") -> list[str]:
    ids = [a.id for a in load_inbox(data_dir).arrivals.values()
           if a.state is State.NEW and (not request or a.request == request)]
    return seen(data_dir, ids, by=by)


def dismiss(data_dir: Path, arrival_id: str, *, by: str, why: str) -> Arrival:
    """Not an answer (a question, a duplicate, not the form). A recorded arrival is not dismissed: PayHOA was written
    from it. Keyed answers it had are set aside, not deleted."""
    _need(by, "--by")
    _need(why, "--why")
    with locked("dismiss"):
        inbox = load_inbox(data_dir)
        a = _get(inbox, arrival_id)
        if a.state in (State.RECORDED, State.DISMISSED):
            raise ResponseError(f"{arrival_id} is {a.state.value}: it cannot be dismissed")
        keyed = keyed_path(data_dir, a)
        if keyed.is_file():
            aside = keyed.parent / WITHDRAWN / keyed.name
            aside.parent.mkdir(parents=True, exist_ok=True)
            keyed.replace(aside)
        updated = _set(inbox, arrival_id, state=State.DISMISSED)
        log_act(data_dir, "dismiss", arrival_id, by, why.strip())
        _supersede(data_dir, inbox, by)
        save_inbox(data_dir, inbox)
    return inbox.arrivals.get(arrival_id, updated)


def mark_recorded(data_dir: Path, arrival_id: str, *, by: str, why: str = "") -> bool:
    """The writes the arrival calls for were made in PayHOA. A keyed arrival, or a structured one (a PayHOA submission, a
    form response, which needs no reading), moves to ``recorded``; any other state is left, and False is returned."""
    with locked("mark recorded"):
        inbox = load_inbox(data_dir)
        a = inbox.arrivals.get(arrival_id)
        if a is None or a.state is State.RECORDED or a.state is State.DISMISSED:
            return False
        if not (a.state is State.KEYED or (a.structured and a.state in (State.NEW, State.SEEN))):
            return False
        _set(inbox, arrival_id, state=State.RECORDED)
        log_act(data_dir, "recorded", arrival_id, by, why or "the writes it calls for were made in PayHOA")
        save_inbox(data_dir, inbox)
    return True


def _supersede(data_dir: Path, inbox: Inbox, by: str) -> list[str]:
    """A later answer for the same unit in the same request supersedes an earlier one (``member_preferences.match`` keeps
    the latest a unit sent); the earlier arrival stays, marked. An answer whose unit is not yet known is left alone.
    Returns the ids whose mark changed."""
    groups: dict[tuple[str, str], list[Arrival]] = {}
    for a in inbox.arrivals.values():
        if a.unit.strip() and a.state is not State.DISMISSED:
            groups.setdefault((a.request, re.sub(r"\W+", " ", a.unit).casefold().strip()), []).append(a)
    changed = []
    for rows in groups.values():
        rows.sort(key=lambda a: (a.at, a.id))
        newest = rows[-1]
        for a in rows:
            want = "" if a is newest else newest.id
            if a.superseded_by != want:
                _set(inbox, a.id, superseded_by=want)
                log_act(data_dir, "superseded" if want else "restored", a.id, by,
                        f"a later answer for the unit: {want}" if want else "no later answer stands")
                changed.append(a.id)
    return changed


# -- reading an arrival -------------------------------------------------------------------------------------------------

@dataclass
class FileReading:
    """What was made of one file: ``how`` is "typed" (a filled PDF's fields), "scan" (the form reader), or "not the form"."""
    name: str
    how: str
    fields: dict[str, Any] = field(default_factory=dict)       # field -> FieldReading (value, how, confidence)
    answers: dict[str, Any] = field(default_factory=dict)
    reference: str = ""
    reference_how: str = ""
    notes: list[str] = field(default_factory=list)
    lines: int = 0
    residual: float = 0.0
    signature: str = ""
    signed: str = ""


Reader = Callable[[Path, ResponseRequest, Any, Any], FileReading]


def _typed(path: Path, form: Any) -> FileReading | None:
    """A filled fillable PDF read by its fields; None when it has none filled (a scan, or a blank form)."""
    from jason.community.fillable import read_answers
    from jason.community.form_reader import FieldReading
    from jason.community.pdf_fields import values

    try:
        raw = values(path)
    except Exception:  # noqa: BLE001 - not a PDF the fields can be read from
        return None
    names = {q.field for q in form.questions} | {f"{q.field}.{option_key(o)}" for q in form.questions for o in q.options}
    if not any(raw.get(n) not in (None, "", False) for n in names):
        return None
    read = read_answers(path, form, source=path.name)
    fields = {k: FieldReading(v, "typed", 0.95) for k, v in read.answers.items()}
    return FileReading(path.name, "typed", fields, dict(read.answers), read.reference, "text" if read.reference else "",
                       signature=read.signature, signed=read.signed)


def read_file(path: Path, request: ResponseRequest, layout: Any, model: Any) -> FileReading:
    """One file read against the request's form: typed fields first, else the scan reader (the form recognised by its
    printed lines, never by a marker). The local vision model reads handwriting only when ``model`` is given."""
    typed = _typed(path, request.form)
    if typed is not None:
        return typed
    if layout is None:
        return FileReading(path.name, "not the form", notes=["no blank form of the request is on disk to read a scan "
                                                             f"against ({request.blank or 'none named'})"])
    from jason.community import form_hints
    from jason.community.form_reader import identify_form, read_scan, scan_pages

    try:
        pages = scan_pages(path)
    except Exception as exc:  # noqa: BLE001 - a file that cannot be opened is reported, not raised
        return FileReading(path.name, "not the form", notes=[f"could not be opened: {type(exc).__name__}"])
    if not pages:
        return FileReading(path.name, "not the form", notes=["no pages"])
    found, _, matched = identify_form(pages[0], [layout])
    if found is None:
        return FileReading(path.name, "not the form", lines=matched,
                           notes=[f"its printed lines match the form's on {matched} line(s) only"])
    reading = form_hints.apply(read_scan(path, request.form, layout, model=model), request.form, form_hints.community_hints())
    return FileReading(path.name, "scan", dict(reading.fields), dict(reading.answers(request.form).answers), reading.reference,
                       reading.reference_how, list(reading.notes), matched, reading.residual)


def keyed_path(data_dir: Path, arrival: Arrival) -> Path:
    return responses_dir(data_dir) / KEYED / f"{arrival.stem}.json"


def reading_path(data_dir: Path, arrival: Arrival) -> Path:
    return responses_dir(data_dir) / READINGS / f"{arrival.stem}.json"


def _request(community: Any, key: str) -> ResponseRequest:
    for request in community.response_requests():
        if request.key == key:
            return request
    raise ResponseError(f"the profile has no request {key!r} (Community.response_requests)")


def _layout(data_dir: Path, request: ResponseRequest) -> Any:
    blank = Path(data_dir) / request.blank if request.blank else None
    if blank is None or not blank.is_file():
        return None
    from jason.community.form_layout import read_layout

    return read_layout(blank, request.form)


def _download(data_dir: Path, community: Any, a: Arrival, clients: Mapping[Channel, Callable[[], Any]],
              owners: Mapping[str, OwnerRef] | None) -> tuple[list[Path], OwnerRef | None]:
    """The arrival's files on disk and, for an email, the owner its sender's address belongs to (matched now, kept as a
    unit and a name only). Gmail is asked for the message's parts and each attachment (read-only)."""
    if a.channel is Channel.MAIL:
        scan = DiskMail(data_dir).scan(a.native)
        if not scan.is_file():
            raise ResponseError(f"the scan of mail {a.native} is not on disk ({scan}); `jason mail --sync` fetches it")
        return [scan], None
    if a.channel is not Channel.GMAIL:
        raise ResponseError(f"{a.id} came structured ({a.channel.value}); it needs no reading")
    if Channel.GMAIL not in clients:
        raise ResponseError("reading an email needs Gmail's client (no client was given)")
    from jason.tasks.gmail import _senders

    gmail = clients[Channel.GMAIL]()
    meta = gmail.get_metadata(a.native, headers=GmailChannel.headers())
    senders, _ = _senders(meta.get("headers") or {}, {d.casefold() for d in community.email_domains()})
    people = owners if owners is not None else owner_directory(data_dir, community)
    owner = people.get(senders[0][1]) if senders else None
    folder = responses_dir(data_dir) / FILES / a.stem
    folder.mkdir(parents=True, exist_ok=True)
    out, taken = [], set()
    for part in meta.get("attachments") or []:
        if not is_form_file(part) or not part.get("attachmentId"):
            continue
        name = _safe(part["name"])
        while name in taken:
            name = "_" + name
        taken.add(name)
        data = gmail.get_attachment(a.native, part["attachmentId"])
        (folder / name).write_bytes(data)
        out.append(folder / name)
    return out, owner


def read(data_dir: Path, community: Any, arrival_id: str, *, by: str, clients: Mapping[Channel, Callable[[], Any]],
         model: str = "", owners: Mapping[str, OwnerRef] | None = None, reader: Reader | None = None) -> dict[str, Any]:
    """Download an arrival's attachments to ``files/<id>/`` (an email's; a mailed scan is read where the mail service
    left it), find the form and its marker, and read the boxes and writing. The reading is kept in ``readings/<id>.json``
    with each field's confidence and how it was read; it is evidence for a person (``confirm``), never an answer. With
    ``model`` the local vision model also reads handwriting, after ``jason.local_ai.preflight``, holding the GPU lock.
    Returns the reading."""
    _need(by, "--by")
    a = get(data_dir, arrival_id)
    if a.state not in (State.NEW, State.SEEN, State.READ):
        raise ResponseError(f"{arrival_id} is {a.state.value}: it is not read again")
    request = _request(community, a.request)
    vision = None
    if model:
        from jason.community.form_reader import VisionReader
        from jason.local_ai import preflight

        preflight(model)
        vision = VisionReader(model)
    files, owner = _download(data_dir, community, a, clients, owners)
    layout = _layout(data_dir, request)
    do = reader or read_file
    if vision is not None:
        from jason.locks import Resource, hold

        with hold(Resource.GPU, purpose=f"reading {a.id} with {model}"):
            readings = [do(f, request, layout, vision) for f in files]
    else:
        readings = [do(f, request, layout, None) for f in files]
    chosen = next((r for r in readings if r.how != "not the form"), None)
    notes = [f"{r.name}: {n}" for r in readings for n in r.notes]
    if not files:
        notes.append("the message carries no PDF or image to read")
    campaign = ""
    if chosen is not None and chosen.reference:
        from jason.community.form_refs import parse

        markers = parse(chosen.reference)
        campaign = markers[0].campaign if markers else ""
        if campaign and not request.names_campaign(campaign):
            notes.append(f"the marker names another campaign ({campaign}), not this request's")
    reading = {
        "id": a.id, "request": a.request, "readAt": iso(now_utc()), "by": by, "model": model,
        "how": chosen.how if chosen else "not the form", "form": chosen is not None,
        "files": [{"name": r.name, "how": r.how, "linesMatched": r.lines,
                   "sha256": hashlib.sha256(f.read_bytes()).hexdigest()} for r, f in zip(readings, files)],
        "reference": chosen.reference if chosen else "", "referenceHow": chosen.reference_how if chosen else "",
        "campaign": campaign, "campaignMatches": bool(campaign and request.names_campaign(campaign)),
        "residual": chosen.residual if chosen else 0.0, "notes": notes,
        "owner": ({"unit": owner.unit, "unitId": owner.unit_id, "name": owner.name, "matchedBy": "the sender's address"}
                  if owner else {}),
        "signature": chosen.signature if chosen else "", "signed": chosen.signed if chosen else "",
        "fields": {k: {"value": v.value, "how": v.how, "confidence": round(float(v.confidence), 2)}
                   for k, v in sorted((chosen.fields if chosen else {}).items())},
        "answers": dict(chosen.answers) if chosen else {},
    }
    with locked("keep a reading"):
        _write_json(reading_path(data_dir, a), reading)
        inbox = load_inbox(data_dir)
        _get(inbox, arrival_id)
        changes: dict[str, Any] = {"state": State.READ}
        if owner:
            changes["unit"] = owner.unit
        _set(inbox, arrival_id, **changes)
        log_act(data_dir, "read", arrival_id, by, f"{len(files)} file(s) read: {reading['how']}",
                model=model, fields=len(reading["fields"]))
        _supersede(data_dir, inbox, by)
        save_inbox(data_dir, inbox)
    return reading


def load_reading(data_dir: Path, arrival_id: str) -> dict[str, Any] | None:
    path = reading_path(data_dir, get(data_dir, arrival_id))
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


# -- confirming ---------------------------------------------------------------------------------------------------------

@dataclass
class Keyed:
    answers: FormAnswers
    problems: list[str]             # what ``forms.check`` finds in the answers: informational, a person decides
    corrected: list[str]            # the fields a person set or cleared


def _coerce(request: ResponseRequest, name: str, value: Any) -> Any:
    """A correction as the answer a field holds: a choice question's options (a list; a checkbox's joined with ";"),
    else the text. None clears the answer."""
    question = next((q for q in request.form.questions if q.field == name), None)
    if question is None:
        raise ResponseError(f"{name!r} is not a question of {request.form.title} (its fields: "
                            f"{', '.join(q.field for q in request.form.questions)})")
    if question.kind in CHOICE_KINDS:
        parts = [str(v) for v in value] if isinstance(value, (list, tuple)) else str(value or "").split(";")
        chosen = [p.strip() if p.strip() in question.options else question.option_for(option_key(p.strip()))
                  for p in parts if p.strip()]
        return chosen or None
    text = str(value or "").strip()
    return text or None


def answers_to_json(a: FormAnswers) -> dict[str, Any]:
    return {"form": a.form.value, "answers": a.answers, "source": a.source, "signature": a.signature, "signed": a.signed,
            "submitted": a.submitted, "contacts": a.contacts, "membership_id": a.membership_id, "unit_id": a.unit_id,
            "reference": a.reference}


def answers_from_json(raw: Mapping[str, Any]) -> FormAnswers:
    return FormAnswers(FormKey(raw["form"]), dict(raw.get("answers") or {}), raw.get("source", ""), raw.get("signature", ""),
                       raw.get("signed", ""), raw.get("submitted", ""), [dict(c) for c in raw.get("contacts") or []],
                       raw.get("membership_id"), raw.get("unit_id"), raw.get("reference", ""))


SOURCES = {Channel.GMAIL: "email", Channel.MAIL: "mail"}         # the answers' source prefix by channel


def confirm(data_dir: Path, community: Any, arrival_id: str, *, by: str, corrections: Mapping[str, Any] | None = None,
            why: str = "") -> Keyed:
    """A person says "this is what it says": the reading, with ``corrections`` (field to value; empty clears), kept as
    the same ``FormAnswers`` a PayHOA submission becomes (``keyed/<id>.json``). The source is ``email:<message id>`` (or
    ``mail:<mail id>``); ``submitted`` and ``signed`` come from the arrival. The owner is matched by the unit and name the
    reading kept, else by the form's own unit address and name, as any answer is (``member_preferences.match``)."""
    from jason.community.forms import check as problems_of

    _need(by, "--by")
    a = get(data_dir, arrival_id)
    if a.state is not State.READ:
        raise ResponseError(f"{arrival_id} is {a.state.value}: only a read arrival is confirmed (jason responses --read)")
    reading = load_reading(data_dir, arrival_id)
    if not reading or not reading.get("form"):
        raise ResponseError(f"the reading of {arrival_id} found no form: dismiss it, or read it again")
    request = _request(community, a.request)
    answers = dict(reading.get("answers") or {})
    corrected = []
    for name, value in (corrections or {}).items():
        fixed = _coerce(request, name, value)
        if fixed is None:
            answers.pop(name, None)
        else:
            answers[name] = fixed
        corrected.append(name)
    owner = reading.get("owner") or {}
    person = owner.get("name") or str(answers.get("name") or "")
    contact = {k: v for k, v in {"role": "owner", "name": person, "email": str(answers.get("email") or "")}.items() if v}
    keyed = FormAnswers(request.form.key, answers, source=f"{SOURCES[a.channel]}:{a.native}",
                        signature=str(reading.get("signature") or ""), signed=str(reading.get("signed") or a.at[:10]),
                        submitted=a.at, contacts=[contact] if person else [], unit_id=owner.get("unitId"),
                        reference=str(reading.get("reference") or ""))
    problems = problems_of(request.form, answers)
    with locked("keep confirmed answers"):
        _write_json(keyed_path(data_dir, a), {"id": a.id, "request": a.request, "by": by, "at": iso(now_utc()),
                                              "corrected": corrected, "problems": problems, **answers_to_json(keyed)})
        inbox = load_inbox(data_dir)
        changes: dict[str, Any] = {"state": State.KEYED}
        if not inbox.arrivals[arrival_id].unit and answers.get("unit-address"):
            changes["unit"] = scrub(answers["unit-address"], 80)
        _set(inbox, arrival_id, **changes)
        log_act(data_dir, "confirm", arrival_id, by, why or "the reading is what the form says",
                corrected=corrected, problems=len(problems))
        _supersede(data_dir, inbox, by)
        save_inbox(data_dir, inbox)
    return Keyed(keyed, problems, corrected)


def keyed_answers(data_dir: Path, form: FormKey | None = None) -> list[FormAnswers]:
    """Every answer a person confirmed, as the ``FormAnswers`` a PayHOA submission becomes, for ``gather_answers``. An
    arrival dismissed after keying has its file set aside (``dismiss``) and is not here."""
    folder = responses_dir(data_dir) / KEYED
    out = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        answers = answers_from_json(json.loads(path.read_text(encoding="utf-8")))
        if form is None or answers.form is form:
            out.append(answers)
    return out


# -- recording: what `jason owner-info --apply --yes` tells the inbox ------------------------------------------------------

_SOURCE_CHANNELS = {"payhoa": "payhoa", "google": "forms", "email": "gmail", "mail": "mail"}


def arrival_id_for(source: str) -> str:
    """The inbox id of the arrival an answer came from (``email:abc`` is ``gmail:abc``); "" for a source the inbox does
    not know."""
    prefix, _, native = str(source or "").partition(":")
    channel = _SOURCE_CHANNELS.get(prefix)
    return f"{channel}:{native}" if channel and native else ""


@dataclass
class _Expectation:
    arrival: str
    writes: list[Any]
    blockers: list[str]
    done: bool = False


class RecordedObserver:
    """Hears the results of ``owner_info_apply.execute_each`` for the writes of one plan and marks an arrival recorded when
    every write it calls for is made and nothing is left for the board or a person. It writes only the inbox."""

    def __init__(self, data_dir: Path, expected: list[_Expectation], by: str = "") -> None:
        from jason.approvals.audit import os_actor

        self.data_dir, self.expected, self.by = Path(data_dir), expected, by or os_actor()
        self.made: set[int] = set()

    def heard(self, results: Iterable[Any]) -> list[str]:
        self.made |= {id(r.write) for r in results if r.satisfied}
        marked = []
        for exp in self.expected:
            if exp.done or exp.blockers or not all(id(w) in self.made for w in exp.writes):
                continue
            exp.done = True
            kinds = sorted({w.kind for w in exp.writes})
            why = (f"{len(exp.writes)} PayHOA write(s) made ({', '.join(kinds)})" if exp.writes
                   else "nothing to write: PayHOA already shows it")
            try:
                if mark_recorded(self.data_dir, exp.arrival, by=self.by, why=why):
                    marked.append(exp.arrival)
            except Exception:  # noqa: BLE001 - the inbox failing never stops the PayHOA writes
                continue
        return marked


def observe_plan(plan: Any, data_dir: Path, *, by: str = "") -> RecordedObserver | None:
    """Watch ``plan``'s writes (``owner_info_apply.ApplyPlan``) for the arrivals in the inbox: for each owner's latest
    answer this cycle that came from an arrival, the writes it calls for, and what keeps it from being recorded (a write
    the response policy holds for the board, something a person enters, a finding but "record"). None when the inbox
    holds none of them. The observer is attached to the writes (``owner_info_apply.observe``)."""
    from jason.tasks.owner_info import FOR_A_PERSON, PERSON_FIELDS, OwnerStatus
    from jason.tasks.owner_info_apply import observe

    inbox = load_inbox(data_dir)
    if not inbox.arrivals:
        return None
    from jason.tasks.owner_responses import Outcome

    held = [h for h in getattr(plan, "held", [])]
    expected = []
    for row in plan.rows:
        answer = row.answer
        if answer is None or not answer.latest or row.status is not OwnerStatus.ANSWERED:
            continue
        arrival = arrival_id_for(answer.source)
        if arrival not in inbox.arrivals:
            continue

        def mine(w: Any) -> bool:
            return (w.kind.startswith("member") and w.target == row.membership_id) or \
                   (w.kind.startswith("unit") and w.target == row.unit_id)

        blockers = [f"held for the board ({h.rule})" for h in held if mine(h.write)]
        blockers += [f"a person enters the {k}" for k in FOR_A_PERSON if answer.record.get(k)]
        blockers += ["a person enters the legal representative"] if any(answer.choices.get(f) for f in PERSON_FIELDS) else []
        if answer.source.startswith("payhoa:"):
            blockers += [f"{f.outcome.value}: {f.rule}" for f in getattr(plan, "findings", {}).get(
                int(answer.source.split(":", 1)[1]), []) if f.outcome is not Outcome.RECORD]
        expected.append(_Expectation(arrival, [w for w in plan.writes if mine(w)], blockers))
    if not expected:
        return None
    observer = RecordedObserver(data_dir, expected, by)
    observe(plan.writes, observer)
    return observer


# -- looking at the inbox (the command and the tools read these) ----------------------------------------------------------

def list_arrivals(data_dir: Path, *, state: str = "", request: str = "", unit: str = "", channel: str = "",
                  new: bool = False, days: int = 0, now: datetime | None = None) -> list[Arrival]:
    """The inbox, newest first, filtered. ``new`` is the state "new"; ``days`` keeps arrivals from the last so many days."""
    want = "new" if new else state
    since = (now or now_utc()) - timedelta(days=days) if days else None
    rows = [a for a in load_inbox(data_dir).arrivals.values()
            if (not want or a.state.value == want) and (not request or a.request == request)
            and (not channel or a.channel.value == channel) and (not unit or unit.casefold() in a.unit.casefold())
            and (since is None or (when(a.at) or since) >= since)]
    return sorted(rows, key=lambda a: (a.at, a.id), reverse=True)


def channel_status(data_dir: Path, *, now: datetime | None = None) -> list[dict[str, Any]]:
    """Each channel checked so far: when it last succeeded, how the last try ended, and how old the last success is."""
    moment = now or now_utc()
    out = []
    for name, record in sorted(load_inbox(data_dir).channels.items()):
        ok = when(record.get("lastOk"))
        out.append({"channel": name, "lastOk": record.get("lastOk", ""), "lastTried": record.get("lastTried", ""),
                    "ended": record.get("ended", ""), "reason": record.get("reason", ""),
                    "ageHours": round((moment - ok).total_seconds() / 3600, 1) if ok else None})
    return out


def show(data_dir: Path, arrival_id: str) -> dict[str, Any]:
    """One arrival: its facts, its reading, its keyed answers' file, and its acts (nothing masked: the command's caller
    masks what it prints)."""
    a = get(data_dir, arrival_id)
    keyed = keyed_path(data_dir, a)
    folder = responses_dir(data_dir) / FILES / a.stem
    return {"arrival": a.to_json(), "reading": load_reading(data_dir, arrival_id),
            "keyed": json.loads(keyed.read_text(encoding="utf-8")) if keyed.is_file() else None,
            "files": sorted(p.name for p in folder.glob("*")) if folder.is_dir() else [],
            "acts": acts_for(data_dir, arrival_id)}


def clear_files(data_dir: Path, arrival_id: str) -> None:
    """Remove an arrival's downloaded attachments (a person's housekeeping; the reading is kept)."""
    folder = responses_dir(data_dir) / FILES / get(data_dir, arrival_id).stem
    if folder.is_dir():
        shutil.rmtree(folder)


__all__ = ["ChannelReport", "CheckReport", "DiskMail", "Ended", "FileReading", "FormsChannel", "GmailChannel", "Inbox", "Keyed",
           "MailChannel", "Message", "OwnerRef", "PayhoaChannel", "RecordedObserver", "ResponseError", "SavedForms",
           "acts_for", "answers_from_json", "answers_to_json", "arrival_id_for", "channel_status", "check", "confirm",
           "dismiss", "get", "is_form_file", "keyed_answers", "list_arrivals", "load_inbox", "load_reading", "log_act",
           "mark_recorded", "observe_plan", "owner_directory", "read", "read_file", "save_inbox", "seen", "seen_all",
           "show", "signed_out", "uses"]
