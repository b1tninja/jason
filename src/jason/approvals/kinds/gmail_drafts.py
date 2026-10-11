"""The ``gmail-drafts`` kind: ``jason draft --yes`` as an approval. A prepared email is saved as a Gmail draft, never sent.

The kind composes the email with the functions ``jason draft`` calls, so the console and the CLI make the same email:

- ``proposal-request`` (key: a life safety system's key): ``proposal_request.request_for`` and ``proposal_request.draft``
  over ``inspections.review``;
- ``hearing`` (key: the unit address of a saved hearing): ``drafts.find_hearing`` and ``drafts.hearing_draft``, with the
  notice Doc exported as PDF when the scope says ``pdf``;
- ``meeting-notice`` (key: the meeting's ISO date): ``drafts.meeting_notice_draft``.

Scope: ``{"case", "key", "to": [...], "cc": [...], "signer", "horizon", "pdf"}``. The recipient is always the person's
choice. With no ``to`` the plan has no item: it is a preview, with the addresses the records suggest for a proposal
request. An address is checked (one address, no spaces, no header characters).

The planner reads disk (and, for a PDF, exports the notice Doc) and creates nothing. It makes one item: the message
(recipients, subject, attachment names, and the body, a line that gives a password or code withheld), with a basis that
hashes the composed email, so a changed source is a changed fingerprint. The applier composes the email again, saves
nothing when its hash differs from the plan's, and otherwise creates the draft (``GmailDrafts.create``). jason has no
send method: a person reads the draft in Gmail and sends it there.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from jason.approvals.engine import Live, Planned
from jason.approvals.model import Change, ChangeOp, Evidence, PlanItem, Result, digest, item_id

KEY = "gmail-drafts"
OP = "save Gmail draft"
TABLE = "gmail_drafts.CASES"                  # the rule rows (jason.tasks.rule_rows), one for each case
RULE = TABLE
MAX_ADDRESSES = 10
PLACEHOLDER = "(choose a recipient)"          # the composers take a recipient; a preview has none yet
WITHHELD = "[line withheld from the approval record: it gives a password or code]"


@dataclass(frozen=True)
class Case:
    """One email jason composes for a person to save as a draft: what the scope's key names and the function that
    composes it (the one ``jason draft`` calls)."""
    key: str
    key_is: str
    composer: str
    words: str


CASES: tuple[Case, ...] = (
    Case("proposal-request", "a life safety system's key (jason inspections)",
         "jason.tasks.proposal_request.draft", "Ask the servicer of one life safety system for a proposal and for the "
         "reports it holds, from what the inspection record shows is due. The recipient is the person's choice."),
    Case("hearing", "the unit address of a saved hearing (jason hearing)", "jason.tasks.drafts.hearing_draft",
         "Send the notice of a saved hearing, with the Zoom details and a link to the notice Doc or its PDF. The body "
         "names the unit; it goes to the recipient the person chose."),
    Case("meeting-notice", "the meeting's date (jason agenda)", "jason.tasks.drafts.meeting_notice_draft",
         "Send the meeting notice whose body is the drafted agenda of that date."),
)
SENT = "never: the draft is saved in the signed-in Gmail account, and a person sends it from Gmail"


@dataclass(frozen=True)
class Request:
    """A scope, checked: what to compose and for whom."""
    case: str
    key: str
    to: tuple[str, ...] = ()
    cc: tuple[str, ...] = ()
    signer: str = ""
    horizon: int = 120
    pdf: bool = False

    def scope(self) -> dict[str, Any]:
        return {"case": self.case, "key": self.key, "to": list(self.to), "cc": list(self.cc), "signer": self.signer,
                "horizon": self.horizon, "pdf": self.pdf}


@dataclass
class Composed:
    plan: Any                                          # drafts.DraftPlan, its message carrying the chosen to and cc
    suggested: list[Any] = field(default_factory=list)  # proposal_request.Recipient
    servicer: str = ""
    doc_id: str = ""                                   # the hearing's notice Doc, when it is attached as PDF


@dataclass
class Context:
    """The planner's own, in memory, for the applier."""
    request: Request


# --- the scope ----------------------------------------------------------------------------------------------------------

_ADDRESS = re.compile(r"^[^\s@<>,;:\"()\[\]\\]+@[^\s@<>,;:\"()\[\]\\]+\.[^\s@<>,;:\"()\[\]\\]+$")


def valid_address(text: str) -> bool:
    """One plain address: no name part, no spaces or line breaks (a header cannot be injected), one at-sign."""
    return bool(_ADDRESS.match(text or "")) and len(text) <= 254


def _addresses(value: Any, what: str) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    rows = [value] if isinstance(value, str) else list(value)
    out: list[str] = []
    for raw in rows:
        text = str(raw).strip()
        if not valid_address(text):
            raise ValueError(f"{what}: {text!r} is not an email address (one plain address each, such as "
                             "name@example.org)")
        if text.casefold() not in {a.casefold() for a in out}:
            out.append(text)
    if len(out) > MAX_ADDRESSES:
        raise ValueError(f"{what}: {len(out)} addresses; at most {MAX_ADDRESSES}")
    return tuple(out)


def parse_scope(scope: dict[str, Any]) -> Request:
    """The scope as a ``Request``, or a ``ValueError`` saying what is wrong. Nothing is read."""
    case = str(scope.get("case") or "").strip()
    if case not in {c.key for c in CASES}:
        raise ValueError(f"case is one of {', '.join(c.key for c in CASES)}")
    key = str(scope.get("key") or "").strip()
    if not key or "\n" in key or "\r" in key:
        raise ValueError(f"key names {next(c.key_is for c in CASES if c.key == case)}")
    if case == "meeting-notice":
        try:
            key = date.fromisoformat(key).isoformat()
        except ValueError as exc:
            raise ValueError("key is the meeting's date, such as 2026-10-20") from exc
    to = _addresses(scope.get("to"), "to")
    taken = {a.casefold() for a in to}
    cc = tuple(a for a in _addresses(scope.get("cc"), "cc") if a.casefold() not in taken)
    signer = str(scope.get("signer") or "").strip()
    if len(signer) > 120 or re.search(r"[\r\n]", signer):
        raise ValueError("signer is one line of at most 120 characters")
    try:
        horizon = 120 if scope.get("horizon") in (None, "") else int(scope["horizon"])
    except (TypeError, ValueError) as exc:
        raise ValueError("horizon is a number of days") from exc
    if not 1 <= horizon <= 730:
        raise ValueError("horizon is between 1 and 730 days")
    pdf = scope.get("pdf") in (True, "true", "1", 1, "yes")
    if pdf and case != "hearing":
        raise ValueError("pdf attaches a hearing's notice Doc; it applies to the hearing case only")
    return Request(case, key, to, cc, signer, horizon, pdf)


# --- the composition (the functions `jason draft` calls) --------------------------------------------------------------------

def _data_dir(live: Live) -> Path:
    if live.data_dir is not None:
        return Path(live.data_dir)
    from jason.config import data_dir

    return Path(data_dir(live.env))


def compose(req: Request, live: Live) -> Composed:
    """The email for ``req``, composed as ``jason draft`` composes it, carrying the chosen recipients. Reads disk; for
    a hearing's PDF, exports the notice Doc through ``live.client`` (a ``GoogleDrive``) into the data folder."""
    from jason.community import community as active
    from jason.tasks import drafts

    data_dir = _data_dir(live)
    community = active()
    first = req.to[0] if req.to else PLACEHOLDER
    suggested: list[Any] = []
    servicer = doc_id = ""
    if req.case == "proposal-request":
        from jason.tasks import proposal_request as pr
        from jason.tasks.contacts import directory
        from jason.tasks.inspections import review

        records = review(data_dir, community)
        request = pr.request_for(records, req.key, horizon=req.horizon)
        if request is None:
            keys = ", ".join(s.system.key for s in records.systems) or "none listed"
            raise LookupError(f"no system {req.key!r}; the systems are: {keys}")
        plan = pr.draft(request, first, signer=req.signer, waiting=pr.waiting_threads(data_dir, community,
                                                                                       request.servicer),
                        agreements=pr.agreements_on_file(data_dir, request.servicer))
        servicer = request.servicer
        suggested = pr.recipients(directory(data_dir, community), request.servicer)
    elif req.case == "hearing":
        hearing = drafts.find_hearing(data_dir, req.key, today=live.today)
        pdf = None
        if req.pdf:
            doc = hearing.get("noticeDoc") or {}
            doc_id = str(doc.get("id") or "")
            if not doc_id:
                raise LookupError("the hearing has no notice Doc to export; run `jason hearing --doc` first")
            pdf = data_dir / "zoom" / "hearings" / f"Notice of Hearing {hearing['start'][:10]}.pdf"
            if req.to:                                  # a preview with no recipient exports nothing
                live.client.docs().export_pdf(doc_id, pdf)
        plan = drafts.hearing_draft(hearing, first, community.name, pdf=pdf)
    else:
        plan = drafts.meeting_notice_draft(data_dir, date.fromisoformat(req.key), first, community.name)
    plan.message = dataclasses.replace(plan.message, to=req.to, cc=req.cc)
    return Composed(plan, suggested, servicer, doc_id)


def body_hash(message: Any) -> str:
    """sha256 of what the draft would say: recipients, subject, text, and attachment names."""
    return digest({"to": list(message.to), "cc": list(message.cc), "subject": message.subject, "text": message.text,
                   "html": message.html or "", "attachments": [Path(p).name for p in message.attachments]})


# "Civil Code 5855" reads to ``intake.secret_reason`` as a code given with its digits. A statute's name (the California
# codes) is set apart from its number in the preview ("Civil Code § 5855") so a notice that cites one is not withheld; any
# other "Code 123456" is still flagged. The email itself is not changed.
_STATUTE = re.compile(r"\b((?:Civil|Government|Business and Professions|Corporations|Health and Safety|Penal|Evidence|"
                      r"Insurance|Probate|Labor|Revenue and Taxation|Vehicle|Water|Public Resources|Streets and "
                      r"Highways) Code)\s+(?=\d)")


def preview(message: Any) -> str:
    """The message as the approval keeps it: the header, then the body with each line that gives a password or code
    withheld (a Zoom passcode), so the record never carries what ``intake.secret_reason`` flags."""
    from jason.community.intake import secret_reason

    head = [f"To: {', '.join(message.to)}"]
    if message.cc:
        head.append(f"Cc: {', '.join(message.cc)}")
    head.append(f"Subject: {message.subject}")
    head += [f"Attachment: {Path(p).name}" for p in message.attachments]
    lines = [_STATUTE.sub(r"\1 § ", line) for line in message.text.splitlines()]
    body = [WITHHELD if secret_reason(line) else line for line in lines]
    out = "\n".join([*head, "---", *body])
    if secret_reason(out):
        out = "\n".join([*head, "---", "[body withheld from the approval record: it looks like it holds a secret]"])
    return out


def _command(req: Request) -> str:
    flag = {"proposal-request": "--proposal-request", "hearing": "--hearing", "meeting-notice": "--meeting-notice"}
    key = f'"{req.key}"' if " " in req.key else req.key
    return f"jason draft {flag[req.case]} {key}"


def plan(live: Live, scope: dict[str, Any]) -> Planned:
    """Compose the email and make one item to save it as a draft. Creates nothing. With no ``to`` there is no item:
    the plan says so and, for a proposal request, lists the addresses the records suggest."""
    from datetime import datetime, timezone

    req = parse_scope(scope)
    read_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    composed = compose(req, live)
    return build(req, composed, read_at=read_at)


def build(req: Request, composed: Composed, *, read_at: str = "") -> Planned:
    """The plan from a composed email. Pure: reads nothing."""
    message = composed.plan.message
    reminders = list(composed.plan.reminders)
    evidence = (Evidence("The same email as jason draft", _command(req)),
                Evidence("jason's rule row for this email", f"{TABLE}: {req.case}"))
    notes = [f"Reminder: {r}" for r in reminders]
    notes.append("The email is saved as a draft in the Gmail account jason is signed in to. It is not sent: a person "
                 "reads it in Gmail and sends it there. Deleting the draft in Gmail undoes this.")
    if composed.suggested:
        notes.append(f"Addresses on file for {composed.servicer} (a suggestion; the recipient is the person's choice):")
        notes += [f"  {r.address}" + (f" ({r.name})" if r.name else "") + f": {r.why}" for r in composed.suggested[:10]]
    summary = {"case": req.case, "key": req.key, "subject": message.subject, "to": len(req.to), "cc": len(req.cc),
               "attachments": len(message.attachments),
               "cost": "No charge: a draft in Gmail; nothing is sent"}
    if not req.to:
        notes.insert(0, "No recipient chosen, so there is nothing to approve: jason never picks who an email goes to. "
                        "Plan again with the recipient's address (to).")
        notes.insert(1, f"Subject it would carry: {message.subject}")
        return Planned([], scope=req.scope(), title=f"Gmail draft: {message.subject}", summary=summary,
                       evidence=evidence, notes=notes, read_at=read_at)
    whole = body_hash(message)
    if req.case == "hearing":
        notes.append("The body names a unit (a hearing is a matter for directors and counsel) and carries the Zoom "
                     "details; it goes to the recipient you chose. A line that gives a passcode is withheld from this "
                     "record; the draft in Gmail has it.")
    if req.pdf:
        notes.append("The notice Doc is exported as PDF and attached; the record keeps the Doc's id, not the PDF's "
                     "bytes.")
    item = PlanItem(
        item_id(KEY, OP, f"{req.case}:{req.key}",
                digest([sorted(a.casefold() for a in req.to), sorted(a.casefold() for a in req.cc), message.subject,
                        hashlib.sha256(message.text.encode("utf-8")).hexdigest()])),
        OP, f"{req.case}:{req.key}", message.subject, preview(message),
        f"jason composed this email from {composed.plan.source}, as `{_command(req)}` does. Approving saves it as a "
        f"draft in Gmail for {len(req.to)} recipient(s) you chose"
        + (f" and {len(req.cc)} cc" if req.cc else "") + "; it sends nothing. The reading that this is the email to "
        "send is the plan's: a person reads the draft in Gmail before sending it.",
        group=req.case, change=Change(ChangeOp.ADD, "Gmail drafts", "1 draft", "none", "1 draft"), rule=f"{TABLE}: {req.case}",
        evidence=evidence,
        basis=digest({"case": req.case, "key": req.key, "message": whole, "doc": composed.doc_id}))
    return Planned([item], scope=req.scope(), title=f"Gmail draft: {message.subject}", summary=summary,
                   evidence=evidence, notes=notes, context=Context(req), read_at=read_at)


# --- apply --------------------------------------------------------------------------------------------------------------

def _uncertain(exc: BaseException) -> bool:
    """A request that went out with no answer back (a timeout, a dropped connection): Gmail may have saved it."""
    from jason.google.errors import GoogleError

    if isinstance(exc, GoogleError):
        return False                                    # Gmail answered, and refused
    name = type(exc).__name__.lower()
    return "timeout" in name or "connection" in name


def apply(live: Live, planned: Planned, items: list[PlanItem], recorder: Any) -> None:
    """Save the approved item as a Gmail draft, and nothing else. The email is composed again first: when it no longer
    hashes to the plan's, nothing is saved. Never sends."""
    from jason.google.errors import GoogleError
    from jason.google.gmail_drafts import GmailDrafts
    from jason.tasks import drafts

    ctx: Context | None = planned.context
    for item in items:
        if ctx is None:
            recorder.done(item.id, Result.FAILED, "not an email in the plan read just now")
            continue
        creating = False
        try:
            composed = compose(ctx.request, live)
            now = digest({"case": ctx.request.case, "key": ctx.request.key, "message": body_hash(composed.plan.message),
                          "doc": composed.doc_id})
            if now != item.basis:
                recorder.done(item.id, Result.FAILED, "the source changed since the plan; nothing saved")
                continue
            recorder.applying([item.id])
            creating = True
            created = drafts.save(composed.plan, GmailDrafts.on(live.client))
        except GoogleError as exc:
            recorder.done(item.id, Result.FAILED, f"{type(exc).__name__}: {exc}; nothing saved")
            continue
        except Exception as exc:  # noqa: BLE001 - recorded on the item
            result = Result.UNCERTAIN if creating and _uncertain(exc) else Result.FAILED
            detail = f"{type(exc).__name__}: {exc}"
            if result is Result.UNCERTAIN:
                detail += "; Gmail may have saved the draft: look in Gmail's drafts before planning again"
            recorder.done(item.id, result, detail)
            continue
        recorder.done(item.id, Result.APPLIED,
                      f"saved as Gmail draft {created.get('id')}; review it and send it from Gmail")


__all__ = ["CASES", "Case", "Composed", "Context", "KEY", "OP", "RULE", "Request", "TABLE", "apply", "body_hash", "build",
           "compose", "parse_scope", "plan", "preview", "valid_address"]
