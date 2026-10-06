"""What each owner will be sent for the owner-information request, and what each copy will carry: the plan a person
reads before any batch runs.

For each owner of title and unit (``notice_delivery.plan``, the rule "owner-info-solicitation"):

- **email**: every owner with a working email gets their own copy of the form, filled from the record
  (``owner_prefill.prefill``) with the association's suggestions where they have made no choice
  (``owner_prefill.suggested``). For an owner who elected email it is the law's delivery; for the rest a courtesy.
- **letter**: every owner the law sends mail (no election, an election of mail, or no working email) gets the letter:
  the cover letter, the page of what is on file, and the blank form, to the mailing address on file or the unit.

The plan names owners and units and says which answers come from the record and which are suggested; it never prints
an address or an email.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable

from jason.community.forms import FormTemplate
from jason.community.postal import normalize_address
from jason.tasks.owner_prefill import Activity, Prefill, prefills, reads_email, suggested

LABELS = {
    "name": "name", "answering-for": "answering for", "unit-address": "unit", "mailing-address": "mailing address", "email": "email",
    "delivery.by-email": "email (their choice)", "delivery.by-mail": "mail (their choice)", "second-email": "second email", "second-mailing-address": "second mailing address",
    "representative-name": "representative", "representative-email": "representative's email",
    "representative-phone": "representative's phone", "representative-mailing-address": "representative's address", "occupancy": "occupancy", "ballots": "ballot", "membership-list":
    "membership list",
}


@dataclass
class SendRow:
    unit: str
    unit_id: int
    membership_id: int
    name: str
    email: bool = False                   # their own pre-filled copy by email
    email_is_delivery: bool = False       # the law's delivery (they elected email), not a courtesy
    letter: bool = False
    letter_to: str = ""                   # "mailing" or "unit"
    from_record: list[str] = field(default_factory=list)
    suggested: dict[str, Any] = field(default_factory=dict)
    on_page: list[str] = field(default_factory=list)      # what the letter's page shows as on file
    notes: list[str] = field(default_factory=list)
    prefill: Prefill | None = None


def send_plan(units: list[dict[str, Any]], people: list[dict[str, Any]], tags: Iterable[Any], form: FormTemplate,
              rule: Any, choices: Any, activity: dict[int, Activity], *, deeds: dict[str, date] | None = None,
              today: date) -> list[SendRow]:
    """Every owner's row: the channels from the notice rule and their tags, the values from the record, and the
    suggestions for their emailed copy."""
    from jason.tasks.notice_delivery import audience, plan

    tags = tuple(tags)
    who = audience(plan(units, people, tags), rule, tags)
    emailed = {(o.unit_id, o.membership_id) for o in who.email + who.courtesy}
    legal_email = {(o.unit_id, o.membership_id) for o in who.email}
    mailed = {(o.unit_id, o.membership_id): o.send_to for o in who.mail}
    out = []
    for p in prefills(units, people, tags, form, deeds=deeds):
        key = (p.unit_id, p.membership_id)
        row = SendRow(p.unit, p.unit_id, p.membership_id, p.name, prefill=p)
        row.email = key in emailed and bool(p.values.get("email"))
        row.email_is_delivery = key in legal_email
        row.letter, row.letter_to = key in mailed, mailed.get(key, "")
        row.from_record = [LABELS.get(k, k) for k, v in p.values.items() if v not in ("", None, False)
                           and k not in ("name", "unit-address")]
        if row.email:
            row.suggested = suggested(p, activity.get(p.membership_id), choices, today=today)
            if not row.suggested.get("delivery.by-email") and not (p.values.get("delivery.by-email") or
                                                                 p.values.get("delivery.by-mail")):
                why = reads_email(activity.get(p.membership_id), choices, today)
                row.notes.append("no email suggested" + ("" if why else ": no sign they read the association's email"))
        elif key in emailed:
            row.notes.append("emailed copy skipped: the email is not printed for this owner")
        row.notes += [n for n in p.notes if not n.startswith("suggested email")]
        out.append(row)
    # the rule's copies to secondary records (Additional Deliveries; unconfirmed ones when the rule says so): the same
    # letter, by mail to the record's own mailing address. No emailed copy: that copy is filled with the owner's record.
    from jason.community.tags import Channel

    for s in who.secondary:
        if Channel.MAIL in s.channels:
            unconfirmed = "unconfirmed" in " ".join(s.member_tags)
            out.append(SendRow(s.unit, s.unit_id, s.membership_id, s.name, letter=True, letter_to="mailing",
                               notes=["a copy to " + ("an address the owner has not confirmed" if unconfirmed
                                                       else "the owner's second mailing address")]))
    return out


@dataclass
class OccupancySignal:
    """One unit's occupancy tag beside the evidence of where its owners live: where PayHOA mails them, where the county
    mails the tax bill, the homeowners' exemption (claimed only for a principal residence), and who the latest deed
    names (a business entity usually holds an investment). The evidence is weighed into a reading; a reading that
    differs from the tag, and a deed that names none of PayHOA's owners, are leads to confirm, not findings."""

    unit: str
    unit_id: int
    tag: str                  # the unit's occupancy tag, or "" for none
    mail: str                 # "an owner at the unit", "every owner elsewhere", "some elsewhere, rest none", "none on file"
    county_mail: str = ""     # "property", "elsewhere", or "" when not read (or stale)
    county_since: date | None = None   # the deed the county's address was likely set with
    exemption: bool | None = None
    deed: date | None = None
    deed_names_owner: bool | None = None
    entity: bool = False
    reading: str = ""         # "owner-occupied", "not owner-occupied", or "unclear"
    evidence: list[str] = field(default_factory=list)
    stale: str = ""           # why county facts were left out (a deed since their date)
    finding: str = ""


FRESH_YEARS = 3          # the county's mailing address counts fully this long after the deed it was set with


def _reading(s: OccupancySignal, today: date) -> None:
    """Weigh the evidence. The exemption and a business-entity owner count double; PayHOA's mail counts once. The
    county's mailing address is set when the owner buys (the deed's "mail tax statements to") and changes only when they
    file a change, so it says where they meant to live then: it counts once for a purchase in the last
    ``FRESH_YEARS``, and half after."""
    there = elsewhere = 0.0
    if s.exemption:
        there += 2
        s.evidence.append("homeowners' exemption")
    if s.mail == "an owner at the unit":
        there += 1
        s.evidence.append("an owner's mail goes to the unit")
    elif s.mail == "every owner elsewhere":
        elsewhere += 1
        s.evidence.append("every owner's mail goes elsewhere")
    if s.county_mail:
        fresh = s.county_since is not None and (today - s.county_since).days <= FRESH_YEARS * 365
        weight, since = (1.0 if fresh else 0.5), (f" since {s.county_since.year}" if s.county_since else "")
        if s.county_mail == "property":
            there += weight
            s.evidence.append(f"county mail to the unit{since}")
        else:
            elsewhere += weight
            s.evidence.append(f"county mail elsewhere{since}")
    if s.entity:
        elsewhere += 2
        s.evidence.append("deeded to a business entity")
    no_county = s.exemption is None and not s.county_mail      # PayHOA's addresses are all there is (or all current)
    if (elsewhere == 0 and (there >= 1.5 or (no_county and there >= 1))) or (there >= 2 and there > elsewhere):
        s.reading = "owner-occupied"
    elif there == 0 and (elsewhere >= 1.5 or (no_county and elsewhere >= 1)):
        s.reading = "not owner-occupied"
    else:
        s.reading = "unclear"


def live_signals(client: Any, org_id: int, community: Any, forms: Any, data_dir: Any, *,
                 activity: dict[int, Any] | None = None, today: date | None = None
                 ) -> tuple[list[SendRow], list["OccupancySignal"], list[dict[str, Any]]]:
    """The send plan and every unit's occupancy signal, read now: PayHOA live, the county roll and deeds on disk.
    ``jason owner-info --send-plan`` and the board packet's occupancy report both read it this way. Also returns the
    units as read."""
    from pathlib import Path

    from jason.commands.owner_info import _live
    from jason.mcp.rolls import _roll_path
    from jason.tasks.owner_county import read as county_facts
    from jason.tasks.parties import PartyResolver

    today = today or date.today()
    units, people = _live(client, org_id)
    rows = send_plan(units, people, community.payhoa_tags(), forms.OWNER_INFO,
                     community.notice_rule("owner-info-solicitation"), forms.SUGGESTED_CHOICES, activity or {},
                     deeds=PartyResolver(Path(data_dir)).latest_deed, today=today)
    roll = _roll_path(Path(data_dir), "")
    county = county_facts(Path(data_dir), roll=roll if roll.is_file() else None, parcels=community.parcels())
    return rows, occupancy_signals(units, rows, community.payhoa_tags(), county, today=today), units


def occupancy_signals(units: list[dict[str, Any]], rows: list[SendRow], tags: Iterable[Any],
                      county: dict[str, Any] | None = None, *, today: date | None = None) -> list[OccupancySignal]:
    """Each unit's ``OccupancySignal``. ``county`` is ``owner_county.read`` (the unit's title, upper case, to its
    deed, exemption, and county mail); without it only PayHOA's addresses are read."""
    from jason.community.tags import TagPurpose, TagScope, tag_names, tagged
    from jason.tasks.owner_county import names_match

    tags = tuple(tags)
    county = county or {}
    today = today or date.today()
    by_unit: dict[int, list[tuple[str, str]]] = {}
    names: dict[int, list[str]] = {}
    for r in rows:
        if r.prefill is not None:
            by_unit.setdefault(r.unit_id, []).append((r.prefill.mailing, r.prefill.mailing_unit))
            names.setdefault(r.unit_id, []).append(r.name)
    out = []
    for unit in sorted(units, key=lambda u: str(u.get("title") or "")):
        uid = int(unit["id"])
        if uid not in by_unit:
            continue
        # The unit's own address, however written, is the unit; an owner living in another unit here lives elsewhere.
        others = sorted({u for m, u in by_unit[uid] if m == "another unit"})
        found = {{"unit, written differently": "unit", "another unit": "elsewhere"}.get(m, m) for m, _ in by_unit[uid]}
        occupancy = tagged(tags, tag_names(unit), TagPurpose.OCCUPANCY, TagScope.UNIT)
        tag = occupancy[0].name if occupancy else ""
        value = occupancy[0].value if occupancy else ""
        if "unit" in found:
            mail = "an owner at the unit"
        elif found == {"elsewhere"}:
            mail = "every owner elsewhere"
        elif "elsewhere" in found:
            mail = "some elsewhere, rest none"
        else:
            mail = "none on file"
        s = OccupancySignal(str(unit.get("title") or ""), uid, tag, mail)
        facts = county.get(s.unit.upper())
        if facts is not None:                 # county facts count only while no deed has recorded since their date
            s.county_mail, s.exemption, s.deed, s.entity = facts.current_county_mail, facts.current_exemption, \
                facts.latest_deed, facts.entity
            s.county_since = facts.roll_deed or facts.latest_deed
            s.deed_names_owner = names_match(names.get(uid, []), facts.grantees)
            if facts.stale:
                s.stale = f"county data predates the {facts.latest_deed} deed: not used"
        _reading(s, today)
        notes = []
        since = f" (since {s.county_since.year})" if s.county_since else ""
        renting = value in ("Rented out", "Vacant (not occupied)")      # a move the tag already reflects says nothing new
        if s.county_mail == "property" and mail == "every owner elsewhere" and not renting:
            notes.append(f"the county still mails the unit{since}, but PayHOA's mail goes elsewhere: likely lived there "
                         "and moved out, so possibly rented now")
        elif s.county_mail == "elsewhere" and mail == "an owner at the unit" and value == "Rented out":
            notes.append(f"tagged Rental, but the county mails elsewhere{since} while PayHOA's mail goes to the unit: "
                         "likely moved in since")
        if s.deed is not None and value and (today - s.deed).days <= 365:
            notes.append(f"changed hands {s.deed}: the {tag} tag may describe the former owner")
        if s.reading == "not owner-occupied" and value == "Owner-occupied":
            notes.append("tagged Owner Occupied, but the evidence says the owners live elsewhere: confirm")
        elif s.reading == "not owner-occupied" and value not in ("Rented out", "Vacant (not occupied)"):
            notes.append("likely not owner-occupied: possibly a rental (or vacant, or a second home)")
        elif s.reading == "owner-occupied" and value == "Rented out":
            notes.append("tagged Rental, but the evidence says an owner lives there: confirm (moved back, or a stale tag)")
        if s.deed_names_owner is False:
            when = f" ({s.deed.isoformat()})" if s.deed else ""
            notes.append(f"the latest deed{when} names none of PayHOA's owners: check who owns it before mailing")
        if others:
            notes.append(f"an owner's mailing address is {', '.join(others)}")
        s.finding = "; ".join(notes)
        out.append(s)
    return out


def summary(rows: list[SendRow]) -> dict[str, int]:
    return {
        "owners": len(rows),
        "emailedCopies": sum(r.email for r in rows),
        "emailIsTheLawsDelivery": sum(r.email_is_delivery for r in rows),
        "letters": sum(r.letter for r in rows),
        "lettersToMailingAddress": sum(r.letter_to == "mailing" for r in rows),
        "lettersToUnit": sum(r.letter_to == "unit" for r in rows),
        "emailAndLetter": sum(r.email and r.letter for r in rows),
        "letterOnly": sum(r.letter and not r.email for r in rows),
        "suggestedEmail": sum(bool(r.suggested.get("delivery.by-email")) for r in rows),
        "suggestedElectronicBallot": sum(r.suggested.get("ballots") == "Electronic ballot by email" for r in rows),
        "suggestedPaperBallot": sum(r.suggested.get("ballots") == "Paper ballot by mail" for r in rows),
    }


def markdown(rows: list[SendRow], *, today: date, source: str, signals: Iterable[OccupancySignal] = ()) -> str:
    s = summary(rows)
    lines = [
        f"# Owner information request: what each owner will be sent ({today.isoformat()})", "",
        f"Read from {source}. Nothing has been sent. Names and units only: no address or email appears here.", "",
        "| | Count |", "|---|---|",
        f"| Owner records (one per owner and unit) | {s['owners']} |",
        f"| **Task 1, the Mailroom:** the same letter (cover letter and blank form) | {s['letters']} owners ({s['lettersToMailingAddress']} to a mailing address, {s['lettersToUnit']} to the unit; PayHOA sends one letter to co-owners at one address) |",
        f"| **Task 2, the email supplement:** each owner's own filled copy | {s['emailedCopies']} (the law's delivery for {s['emailIsTheLawsDelivery']}; a courtesy for the rest) |",
        f"| Both email and letter | {s['emailAndLetter']} |",
        f"| Letter only | {s['letterOnly']} |",
        f"| Suggested on the emailed copy: by email | {s['suggestedEmail']} |",
        f"| Suggested: electronic ballot / paper ballot | {s['suggestedElectronicBallot']} / {s['suggestedPaperBallot']} |",
        "",
        "Filled from the record: what PayHOA holds (name and unit on every form). Suggested: the association's choice "
        "where the owner has made none, on the emailed copy only; the owner keeps or changes it, and nothing is "
        "recorded until the form comes back.", "",
        "| Unit | Owner | Email | Letter | Filled from the record | Suggested (emailed copy) | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda r: (r.unit, r.name)):
        email = ("yes, delivery" if r.email_is_delivery else "yes, courtesy") if r.email else "no"
        letter = f"yes, to {'mailing address' if r.letter_to == 'mailing' else 'unit'}" if r.letter else "no"
        sug = ", ".join(("by email" if k == "delivery.by-email" else str(v).lower()) for k, v in r.suggested.items()) or "-"
        lines.append(f"| {r.unit} | {r.name} | {email} | {letter} | {', '.join(r.from_record) or '-'} | {sug} | "
                     f"{'; '.join(r.notes) or ''} |")
    signals = list(signals)
    if signals:
        def tally(key):
            counts: dict[str, int] = {}
            for x in signals:
                counts[key(x)] = counts.get(key(x), 0) + 1
            return counts

        by_reading = tally(lambda x: (x.reading, x.tag or "no tag"))
        lines += ["", "## Occupancy and title, from PayHOA and the county", "",
                  "Evidence of where each unit's owners live:", "",
                  "- where PayHOA mails them;",
                  "- where the county mails the tax bill (the secured roll);",
                  "- the homeowners' exemption, which is claimed only for a principal residence and counts double;",
                  "- a business entity named on the latest grant deed, which counts double toward living elsewhere.", "",
                  "Few owners claim the exemption, so no claim proves little. The county's facts describe its lien date "
                  "(the roll: January 1 of its year): on a unit that changed hands since, they describe the former owner "
                  "and are not used (\"stale\"), and the unit's own occupancy tag may be the former owner's too. The deed "
                  "check asks whether the latest deed names any of PayHOA's owners. Each finding is a lead to confirm "
                  "(this year's form asks the owners), not a change to the tags.", "",
                  "| Reading | Occupancy tag | Units |", "|---|---|---|"]
        lines += [f"| {r} | {t} | {n} |" for (r, t), n in sorted(by_reading.items())]
        flagged = [x for x in signals if x.finding]
        lines += ["", f"### Findings ({len(flagged)})", "",
                  "| Unit | Tag | Reading | Evidence | Latest deed | Finding |", "|---|---|---|---|---|---|"]
        lines += [f"| {x.unit} | {x.tag or '-'} | {x.reading} | {'; '.join(x.evidence) or '-'} | "
                  f"{x.deed.isoformat() if x.deed else '-'} | {x.finding} |" for x in flagged] or ["| - | | | | | none |"]
        lines += ["", "### Every unit", "",
                  "| Unit | Tag | Owners' mail (PayHOA) | County mail | Exemption | Latest deed | Deed names an owner | Reading |",
                  "|---|---|---|---|---|---|---|---|"]
        yes_no = {True: "yes", False: "no", None: "-"}
        lines += [f"| {x.unit} | {x.tag or '-'} | {x.mail} | {x.county_mail or ('stale' if x.stale else '-')} | "
                  f"{yes_no[x.exemption] if not (x.stale and x.exemption is None) else 'stale'} | "
                  f"{x.deed.isoformat() if x.deed else '-'}{' (entity)' if x.entity else ''} | {yes_no[x.deed_names_owner]} | "
                  f"{x.reading} |" for x in signals]
    return "\n".join(lines) + "\n"


# -- the emailed copies, as a batch (``jason.batches``) ----------------------------------------------------------------

def batch_items(rows: list[SendRow]) -> list[tuple[str, str, dict[str, Any]]]:
    """One batch item per emailed copy: the key (membership and unit), a label, and the ids the handler needs. No
    address or email goes in the ledger; the copy is made from PayHOA when it is sent."""
    return [(f"{r.membership_id}-{r.unit_id}", f"{r.unit}: {r.name}", {"membershipId": r.membership_id, "unitId": r.unit_id})
            for r in sorted(rows, key=lambda r: (r.unit, r.name)) if r.email]


def street_line(unit: str) -> str:
    """A unit's street line as a person writes it: "5651 WHIMSICAL LN" → "5651 Whimsical Ln"."""
    return " ".join(w if any(ch.isdigit() for ch in w) else w.capitalize() for w in (unit or "").split())


class EmailHandler:
    """Sends one owner their own copy: the form filled from the record with the suggestions (made fresh from the rows
    read when the run began), uploaded as a broadcast attachment, then an email to that one membership through the
    unit (PayHOA fills ``{first name}`` and ``{unit address}``). Each copy carries its reference number
    (``form_refs.make``): in the PDF (``fillable.stamp_reference``), the subject, and the message; once sent, it is
    recorded with the fingerprints of what was filled in (``form_references``), so a reply or a returned copy is read
    against exactly what that owner was sent. ``verify`` reads PayHOA's communications log for an email with this
    copy's upload (or its subject) to that owner since the batch began."""

    def __init__(self, client: Any, org_id: int, rows: list[SendRow], *, form: FormTemplate, form_pdf: Any,
                 subject: str, message: str, sender: str, since: str, filename: str, choices: Any,
                 activity: dict[int, Activity], people: list[dict[str, Any]], today: date, data_dir: Any = None,
                 year: int = 0, google_form: dict[str, Any] | None = None, google_reference: str = "",
                 attachment: Any = None) -> None:
        self.data_dir, self.year = data_dir, year or today.year + 1
        # a follow-up (a correction) attaches this one file instead of the owner's filled form, and records no copy
        self.attachment = attachment
        # the Google Form (as the Forms API reads it) whose personal link ``{GOOGLE_FORM_LINK}`` gives each owner,
        # filled with their copy's reference in the question ``google_reference``
        self.google_form, self.google_reference = google_form, google_reference
        self.client, self.org_id, self.form, self.form_pdf = client, org_id, form, form_pdf
        self.subject, self.message, self.sender, self.since, self.filename = subject, message, sender, since, filename
        self.choices, self.activity, self.today = choices, activity, today
        self.rows = {(r.membership_id, r.unit_id): r for r in rows}
        self.users = {int(p["id"]): int(p.get("userId") or 0) for p in people if p.get("id") is not None}

    def send(self, item: Any, checkpoint: Any, step: Any) -> dict[str, Any]:
        import tempfile
        from datetime import datetime, timezone
        from pathlib import Path

        from payhoa.exceptions import PayhoaApiError

        from jason.community.fillable import stamp_reference
        from jason.tasks.owner_prefill import fill_pdf

        mid, uid = int(item.payload["membershipId"]), int(item.payload["unitId"])
        row = self.rows.get((mid, uid))
        if row is None or row.prefill is None:
            raise PayhoaApiError(f"{item.label} is no longer a current owner with an email", status_code=410)
        reference = self.reference(mid, uid)
        file_id = item.result.get("fileId")
        if not file_id and self.attachment is not None:
            made = self.client.upload_file(Path(self.attachment), filename=Path(self.attachment).name,
                                           content_type="application/pdf", context="communication")
            file_id = int(made["id"])
            checkpoint(fileId=file_id)
            step()
        if not file_id:                                    # a retry after the upload reuses it
            with tempfile.TemporaryDirectory() as tmp:
                pdf = fill_pdf(Path(self.form_pdf), row.prefill, Path(tmp) / self.filename, self.form,
                               extra=row.suggested)
                stamp_reference(pdf, reference)
                self.link_form(pdf, uid)
                made = self.client.upload_file(pdf, filename=self.filename, content_type="application/pdf",
                                               context="communication")
            file_id = int(made["id"])
            checkpoint(fileId=file_id)
            step()
        sent = self.client.send_email(self.org_id, subject=self.subject_for(reference, row.unit),
                                      message=self.message_for(reference, row.unit, uid), from_email=self.sender,
                                      to=[mid], unit_ids=[uid], attachments=[file_id],
                                      scheduled_date=datetime.now(timezone.utc).isoformat())
        data = (sent or {}).get("data") or sent or {}
        if data.get("failure"):
            raise PayhoaApiError(f"PayHOA did not send it: {data['failure']}", status_code=422)
        if self.data_dir is not None and self.attachment is None:
            from jason.tasks.campaigns import stamp
            from jason.tasks.form_references import record
            from jason.tasks.owner_prefill import fingerprints

            record(self.data_dir, reference, form=self.form.key.value, year=self.year, membershipId=mid, unitId=uid,
                   unit=row.unit, channel="email", sent=fingerprints(row.prefill),
                   suggested=sorted(row.suggested), fileId=file_id, **stamp(self.data_dir, reference))   # its campaign
        return {"fileId": file_id, "reference": reference,
                "bulkActionBatchId": data.get("bulkActionBatchId") or (sent or {}).get("bulkActionBatchId")}

    def reference(self, membership_id: int, unit_id: int) -> str:
        from jason.community.form_refs import Channel, make

        return make(self.form.code, self.year, Channel.EMAIL, membership_id=membership_id, unit_id=unit_id).text

    def link_form(self, pdf: Any, unit_id: int) -> None:
        """The copy's way online made its unit's link: the printed "online in PayHOA" becomes a link to the PayHOA
        form for this unit, and any form link already in the PDF gets the unit."""
        from jason.community.fillable import link_phrase
        from jason.tasks.packets import ONLINE_PHRASE
        from jason.tasks.payhoa_forms import owner_link, record_for, with_unit

        record = record_for(self.data_dir, self.form.key.value) if self.data_dir is not None else None
        if record is None:
            return
        link_phrase(pdf, ONLINE_PHRASE, owner_link(int(record["formId"]), unit_id),
                    rewrite=lambda uri: with_unit(uri, unit_id))

    def subject_for(self, reference: str, unit: str = "") -> str:
        """The subject with this copy's reference; ``{unit address}`` in it becomes the unit's street line (an owner or
        manager with several units tells the emails apart in the inbox)."""
        subject = self.subject.replace("{unit address}", street_line(unit)) if unit else self.subject
        return f"{subject} [Ref {reference}]"

    def message_for(self, reference: str, unit: str = "", unit_id: int = 0) -> str:
        message = self.message
        if unit_id:
            # a PayHOA form opens for an owner only with the unit: each form link gets this copy's unit
            from jason.tasks.payhoa_forms import with_unit

            message = with_unit(message, unit_id)
        if unit:
            # the unit's street line, filled here: PayHOA's ``{unit address}`` adds the city, state, and ZIP, and a mail
            # reader makes a full address a map search, the first link in the message
            message = re.sub(r'<span class="placeholder">\{unit address\}</span>|\{unit address\}',
                             html.escape(street_line(unit)), message)
        # a reply by the message's email link comes back with this copy's reference, as from the attached form
        from jason.community.fillable import with_reference

        message = re.sub(r'href="(mailto:[^"]+)"',
                         lambda m: f'href="{html.escape(with_reference(html.unescape(m.group(1)), reference))}"', message)
        if "{GOOGLE_FORM_LINK}" in message:
            from jason.google.forms import prefill_url

            link = prefill_url(self.google_form, {self.google_reference: reference}) if self.google_form else ""
            if not link:
                raise ValueError("the message names {GOOGLE_FORM_LINK} and no Google Form is set (GOOGLE_FORMS)")
            message = message.replace("{GOOGLE_FORM_LINK}", link)
        return (message + f'<p style="color:#666;font-size:12px">Reference {reference}. Please keep it in your reply, '
                "or on the form if you print it, so we match your answers to your record.</p>")

    def verify(self, item: Any) -> bool | None:
        """Sent when the owner's communications show an email carrying this item's upload (or, failing that, this
        subject since the batch began, in UTC as PayHOA keeps it). No upload recorded means no send: the upload comes
        first."""
        file_id = item.result.get("fileId")
        if not file_id:
            return False
        user = self.users.get(int(item.payload["membershipId"]))
        if not user:
            return None
        rows = (self.client.list_communications(self.org_id, recipient_id=user, per_page=25).get("data") or [])
        emails = [r for r in rows if r.get("type") == "email"]
        if any(int(f.get("id") or 0) == int(file_id) for r in emails for f in r.get("fileAttachments") or []):
            return True
        since = self.since[:19].replace("T", " ")
        row = self.rows.get((int(item.payload["membershipId"]), int(item.payload["unitId"])))
        subject = self.subject_for(self.reference(int(item.payload["membershipId"]), int(item.payload["unitId"])),
                                   row.unit if row is not None else "")
        return any((r.get("subject") or "").strip() == subject.strip() and str(r.get("submittedAt") or "") >= since
                   and not r.get("fileAttachments") for r in emails)


# -- the letters, as a batch: one Mailroom send per building -------------------------------------------------------------

def mail_items(rows: list[SendRow], units: list[dict[str, Any]], tags: Iterable[Any]) -> list[tuple[str, str, dict[str, Any]]]:
    """One batch item per building: its units with an owner the law sends mail, and those owners' PayHOA owner-row
    ids (the Mailroom's ``ownerId``). Everyone gets the same letter, so a building goes in one send."""
    from jason.community.tags import TagPurpose, TagScope, tag_names, tagged

    tags = tuple(tags)
    mailed = {(r.unit_id, r.membership_id) for r in rows if r.letter}
    groups: dict[str, dict[str, Any]] = {}
    members_in: dict[str, set[int]] = {}               # a send's owners: PayHOA folds one owner's two units into one
    for unit in units:
        owners = [o for o in unit.get("owners") or [] if not o.get("deletedAt")
                  and (int(unit["id"]), int(o.get("membershipId") or 0)) in mailed]
        owner_rows = [int(o["id"]) for o in owners]
        if not owner_rows:
            continue
        building = tagged(tags, tag_names(unit), TagPurpose.BUILDING, TagScope.UNIT)
        name = building[0].name if building else "No building tag"
        members = {int(o["membershipId"]) for o in owners}
        while members & members_in.get(name, set()):   # an owner of another unit in this send: a send of its own
            name = f"{name} (another unit)"
        members_in.setdefault(name, set()).update(members)
        g = groups.setdefault(name, {"unitIds": [], "ownerIds": []})
        g["unitIds"].append(int(unit["id"]))
        g["ownerIds"] += owner_rows
    return [(name.lower().replace(" ", "-"), f"{name}: {len(g['unitIds'])} units", g)
            for name, g in sorted(groups.items(), key=lambda kv: (len(kv[0]), kv[0]))]


class MailHandler:
    """Mails one building's letters through PayHOA's Mailroom (USPS by Lob; it prints, mails, and charges the
    association). PayHOA is asked whom the letter reaches; only the owners the item names are kept, one letter an
    address; the Mailroom's batches are checkpointed before the send, so ``verify`` can tell whether a new batch
    appeared. Each send is logged in ``data/mailroom/sent.jsonl``."""

    def __init__(self, client: Any, org_id: int, data_dir: Any, *, pdf: Any, double_sided: bool = False) -> None:
        from jason.tasks.mailroom import page_count

        self.client, self.org_id, self.data_dir, self.pdf, self.double_sided = client, org_id, data_dir, pdf, double_sided
        self.pages = page_count(pdf)

    def recipients(self, item: Any) -> list[int]:
        """The owner-row ids this item mails: one letter a unit and address (co-owners of a unit at one address get one
        letter; an owner of two units gets one for each, since the form is a unit's)."""
        wanted = {int(o) for o in item.payload["ownerIds"]}
        rows = self.client.mail_recipients(self.org_id, item.payload["unitIds"], send_to="mailing")
        seen, out = set(), []
        for r in rows:
            owner = int(r.get("ownerId") or 0)
            key = (tuple(sorted(int(u) for u in r.get("unitIds") or [])), normalize_address(str(r.get("address") or "")))
            if owner in wanted and key not in seen:
                seen.add(key)
                out.append(owner)
        return out

    def send(self, item: Any, checkpoint: Any, step: Any) -> dict[str, Any]:
        from pathlib import Path

        from jason.tasks.mailroom import Prepared, send

        owners = self.recipients(item)
        if not owners:
            return {"letters": 0, "note": "no one to mail"}
        step()
        checkpoint(before=[b.get("id") for b in self.client.mail_pdf_batches(self.org_id)], letters=len(owners))
        step()
        prepared = Prepared(str(self.pdf), self.pages, "mailing", [{"id": u} for u in item.payload["unitIds"]],
                            [{"ownerId": o, "isIncluded": True} for o in owners], "")
        record = send(self.client, self.org_id, Path(self.data_dir), prepared, double_sided=self.double_sided)
        return {"letters": len(owners), "mailBatches": [b.get("id") for b in record.get("batches") or []]}

    def verify(self, item: Any) -> bool | None:
        """Sent when the Mailroom has a batch that was not there before this item's send. No checkpoint means the
        send never started."""
        before = item.result.get("before")
        if before is None:
            return False
        return any(b.get("id") not in set(before) for b in self.client.mail_pdf_batches(self.org_id))


__all__ = ["EmailHandler", "MailHandler", "OccupancySignal", "SendRow", "batch_items", "mail_items", "markdown",
           "occupancy_signals", "send_plan", "summary"]
