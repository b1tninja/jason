"""What PayHOA holds for each owner, printed beside the blank owner-information form, and a returned form read against it.

Showing the record turns most answers into "confirmed": the owner writes only what is wrong. The mailed letter keeps the
form blank (a printed answer cannot be unchecked or corrected on paper) and adds a page, "What the Association has on
file for you" (``letter_pdf``): a line left blank on the form keeps what the page shows. ``fill_pdf`` instead fills the
form's fields, for an electronic copy sent to one owner. ``prefill`` builds one owner's values from PayHOA as it is now
(read live):

- the owner's name and the unit's address;
- the mailing address and email from the profile (the mailing address only when it is not the unit's own, as the form
  asks; the email shown on the owner's emailed copy, but left off a letter that goes to a rented unit, where a tenant
  may open it);
- delivery checked only where the owner chose it: "Notices by Email", or "Notices by Mail" on a unit whose "Paper
  Statements" tag the owner set (they held title before PayHOA's records began). The law's default, mail with no
  election, is left blank, so an owner never adopts it by signing;
- occupancy, a paper ballot, and the membership-list opt-out from their tags;
- the second address and the legal representative from the person records on the unit tagged for them.

``fingerprints`` keeps a SHA-256 of each printed value after ``normalize`` (addresses through
``postal.normalize_address``), so jason can tell a confirmed value from a changed one without keeping the value.
``compare`` reads a returned form's answers against them: unchanged (blank, or the same once normalized), changed,
added, or cleared (the owner wrote "none"). The letters are made when they are sent, and not kept.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from jason.community.forms import FormTemplate
from jason.community.postal import US_STATES, normalize_address
from jason.community.tags import PayhoaTag, TagPurpose, TagScope, owner_of_title, tag_names, tagged

ADDRESS_FIELDS = ("unit-address", "mailing-address", "second-mailing-address", "representative-mailing-address")
TEXT = "text"


@dataclass
class Prefill:
    unit_id: int
    unit: str
    membership_id: int
    name: str
    values: dict[str, Any] = field(default_factory=dict)      # field name to text, True for a box, an option for a radio
    withheld: list[str] = field(default_factory=list)          # on file, left off the mailed letter (a tenant may open it)
    mailing: str = ""                                          # where the profile's mailing address is (``place_of``)
    mailing_unit: str = ""                                     # the community unit it names, if any
    notes: list[str] = field(default_factory=list)


def _state_code(state: str) -> str:
    state = (state or "").strip()
    if state.upper() in US_STATES:
        return state.upper()
    return next((code for code, name in US_STATES.items() if name.casefold() == state.casefold()), state)


def postal_lines(line1: str, line2: str, city: str, state: str, zip_code: str) -> str:
    """An address as it is printed: the street lines, then "City, ST ZIP"."""
    tail = " ".join(x for x in (f"{city}," if city else "", _state_code(state), zip_code) if x).strip(" ,")
    return "\n".join(x for x in (line1.strip(), (line2 or "").strip(), tail) if x)


def unit_address(unit: dict[str, Any]) -> str:
    a = unit.get("address") or {}
    region = a.get("region")
    region = region.get("abbreviation") or region.get("region") if isinstance(region, dict) else region
    return postal_lines(str(a.get("line1") or unit.get("title") or ""), str(a.get("line2") or ""), str(a.get("city") or ""),
                        str(region or ""), str(a.get("postalCode") or ""))


def profile_address(person: dict[str, Any]) -> str:
    p = person.get("profile") or {}
    if not p.get("address1"):
        return ""
    region = p.get("region") if isinstance(p.get("region"), dict) else {}
    return postal_lines(str(p["address1"]), str(p.get("address2") or ""), str(p.get("city") or ""),
                        str(region.get("abbreviation") or p.get("state") or ""), str(p.get("zip") or ""))


def _name(person: dict[str, Any]) -> str:
    p = person.get("profile") or {}
    return " ".join(x for x in (p.get("givenNames"), p.get("familyName")) if x) or str(person.get("name") or "")


def _contact(person: dict[str, Any], *, with_name: bool) -> str:
    """A person record as one entry: the name (for a representative), the email, the phone, and the address."""
    p = person.get("profile") or {}
    parts = [_name(person)] if with_name else []
    parts += [str(person.get("email") or ""), str(p.get("phone") or ""), profile_address(person).replace("\n", ", ")]
    return "; ".join(x for x in parts if x)


def is_unit_address(text: str, unit_line: str) -> bool:
    """Whether a typed address is the unit's own, however written: the same address once normalized, or the same
    street number and street (``read_unit_address``, a typo allowed). The form asks for a mailing address "only if it
    is not your unit address", so such an answer means no separate mailing address: the unit's address is used."""
    from jason.community.base import read_unit_address

    first = re.split(r"[\n,]", str(text or "").strip())[0]
    if not first or not unit_line:
        return False
    if normalize_address(first) == normalize_address(unit_line):
        return True
    place = read_unit_address(first)
    return place[0] is not None and place == read_unit_address(unit_line)


def place_of(person: dict[str, Any], unit: dict[str, Any], community: dict[tuple[Any, Any], str]) -> tuple[str, str]:
    """Where an owner's profile mailing address is, and the community unit it names, if any:

    - "none": no mailing address on file (PayHOA mails the unit);
    - "unit": the unit's own address, as PayHOA writes it;
    - "unit, written differently": the unit's own address with a variation ("3007 Enchanted Wk", a misspelled street,
      a unit number, another ZIP): the same street number and street (``read_unit_address``, a typo allowed), and the
      unit's ZIP or city. It is treated as the unit's address;
    - "another unit": another unit in the community (an owner who lives in their other unit);
    - "elsewhere": any other address.

    ``community`` maps each unit's (street number, street) to its title."""
    from jason.community.base import read_unit_address

    profile = person.get("profile") or {}
    line1 = str(profile.get("address1") or "").strip()
    if not line1:
        return "none", ""
    a = unit.get("address") or {}
    unit_line = str(a.get("line1") or unit.get("title") or "")
    zip_code, city = str(profile.get("zip") or "")[:5], str(profile.get("city") or "").strip().casefold()
    same_area = (not zip_code and not city) or zip_code == str(a.get("postalCode") or "")[:5] \
        or city == str(a.get("city") or "").strip().casefold()
    if same_area and normalize_address(line1) == normalize_address(unit_line):
        return "unit", str(unit.get("title") or "")
    place = read_unit_address(line1)
    if same_area and place[0] is not None and place == read_unit_address(unit_line):
        return "unit, written differently", str(unit.get("title") or "")
    if place[0] is not None and place in community and community[place] != unit.get("title"):
        return "another unit", community[place]
    return "elsewhere", ""


def prefill(unit: dict[str, Any], owner_row: dict[str, Any], people: dict[int, dict[str, Any]], tags: Iterable[PayhoaTag],
            form: FormTemplate, *, deed: date | None = None, community: dict[tuple[Any, Any], str] | None = None) -> Prefill:
    """One owner's values for ``form`` (the owner-information form), from the unit and the people as PayHOA holds them.
    ``deed`` is the unit's latest recorded deed, to tell whether the owner set the unit's "Paper Statements" tag;
    ``community`` (each unit's street number and street to its title) tells a mailing address at another unit here."""
    tags = tuple(tags)
    mid = int(owner_row["membershipId"])
    person = people.get(mid, {})
    member, unit_tags = tag_names(person), tag_names(unit)
    label = str(unit.get("title") or "")
    out = Prefill(int(unit["id"]), label, mid, _name(person))
    v = out.values
    v["name"] = out.name
    v["unit-address"] = unit_address(unit).replace("\n", ", ")           # a one-line field
    mailing = profile_address(person)
    out.mailing, out.mailing_unit = place_of(person, unit, community or {})
    if out.mailing in ("elsewhere", "another unit"):
        v["mailing-address"] = mailing
    elif out.mailing == "unit, written differently":
        out.notes.append("the mailing address on file is the unit's own, written differently: the unit's address is used")
    rented = bool(tagged(tags, unit_tags, TagPurpose.OCCUPANCY, TagScope.UNIT)) and any(
        t.value == "Rented out" for t in tagged(tags, unit_tags, TagPurpose.OCCUPANCY, TagScope.UNIT))
    mailed_to_unit = "mailing-address" not in v
    email_ok = bool(person.get("email")) and "missing email address" not in member
    if email_ok:
        v["email"] = str(person["email"])
        if rented and mailed_to_unit:             # their own emailed copy shows it; the letter does not
            out.withheld.append("email")
            out.notes.append("email left off the letter: it goes to a rented unit")
    elected = {t.value for t in tagged(tags, member, TagPurpose.NOTICE_DELIVERY, TagScope.MEMBER)}
    if "email" in elected and email_ok:
        v["delivery.by-email"] = True
    statements = tagged(tags, unit_tags, TagPurpose.STATEMENTS, TagScope.UNIT)
    since = str(owner_row.get("createdAt") or "")[:10]
    if "mail" in elected and statements and (deed is None or (since and deed.isoformat() <= since)):
        v["delivery.by-mail"] = True
        out.notes.append("mail checked: the owner's 'Paper Statements' choice")
    for question in form.questions:
        key = question.field
        for tag in (t for t in tags if t.answer == key and t.value):
            names = unit_tags if tag.scope is TagScope.UNIT else member
            if tag.name.casefold() in names and tag.value in question.options:
                v[key] = tag.value
    on_unit = [people.get(int(o["membershipId"]), {}) for o in unit.get("owners") or []
               if not o.get("deletedAt") and o.get("membershipId") is not None]
    copies = [p for p in on_unit if tagged(tags, tag_names(p), TagPurpose.SECONDARY_CONTACT, TagScope.MEMBER)]
    reps = [p for p in on_unit if tagged(tags, tag_names(p), TagPurpose.LEGAL_REPRESENTATIVE, TagScope.MEMBER)]
    # one value a field: the first additional delivery's email and address, and the first representative's details
    # (a second of either is rare, and kept in PayHOA; the form shows what fits its fields)
    if copies:
        c = copies[0]
        if c.get("email"):
            v["second-email"] = str(c["email"])
        if profile_address(c):
            v["second-mailing-address"] = profile_address(c)
        if len(copies) > 1:
            out.notes.append(f"{len(copies)} additional deliveries on file; the form shows the first")
    if reps:
        r = reps[0]
        v["representative-name"] = _name(r)
        for key, value in (("representative-email", r.get("email")),
                           ("representative-phone", (r.get("profile") or {}).get("phone")),
                           ("representative-mailing-address", profile_address(r))):
            if value:
                v[key] = str(value)
        if len(reps) > 1:
            out.notes.append(f"{len(reps)} legal representatives on file; the form shows the first")
    return out


def prefills(units: Iterable[dict[str, Any]], people: Iterable[dict[str, Any]], tags: Iterable[PayhoaTag],
             form: FormTemplate, *, deeds: dict[str, date] | None = None, only: Iterable[str] = ()) -> list[Prefill]:
    """Every owner of title's pre-filled values, one per owner and unit (as the letters go), or only the units whose
    title starts with one of ``only``."""
    from jason.community.base import read_unit_address

    tags, deeds = tuple(tags), {k.upper(): v for k, v in (deeds or {}).items()}
    units = list(units)
    community = {read_unit_address(str((u.get("address") or {}).get("line1") or u.get("title") or "")): str(u.get("title") or "")
                 for u in units if not u.get("deletedAt")}
    by_id = {int(p["id"]): p for p in people if p.get("id") is not None}
    wanted = [w.upper() for w in only]
    out = []
    for unit in units:
        label = str(unit.get("title") or "").upper()
        if unit.get("deletedAt") or (wanted and not any(label.startswith(w) for w in wanted)):
            continue
        for row in unit.get("owners") or []:
            if row.get("deletedAt") or row.get("membershipId") is None:
                continue
            if not owner_of_title(tags, tag_names(by_id.get(int(row["membershipId"]), {}))):
                continue
            out.append(prefill(unit, row, by_id, tags, form, deed=deeds.get(label), community=community))
    return sorted(out, key=lambda p: (p.unit, p.name))


# -- fingerprints and the comparison -----------------------------------------------------------------------------------

def normalize(key: str, value: Any) -> str:
    """A value as compared: a box as yes or no, an address through ``normalize_address``, any other text lower case
    with its spacing and punctuation collapsed."""
    if isinstance(value, bool):
        return "yes" if value else ""
    text = str(value or "")
    if key in ADDRESS_FIELDS:
        return normalize_address(text)
    text = re.sub(r"\.(?!\w)|(?<![\w])\.", " ", text.casefold())      # "St. John" is "St John"; an email keeps its dots
    return re.sub(r"\s+", " ", re.sub(r"[^\w@.+-]", " ", text)).strip()


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprints(p: Prefill) -> dict[str, Any]:
    """What jason keeps of a sent form: each printed field's hash after ``normalize``, the withheld fields, and who it
    went to. No value is kept."""
    return {"unitId": p.unit_id, "unit": p.unit, "membershipId": p.membership_id,
            "fields": {k: _hash(normalize(k, v)) for k, v in p.values.items() if normalize(k, v)},
            "withheld": list(p.withheld)}


NONE = {"none", "n a", "na", "remove", "delete", "no", "-"}       # written to clear a value on file


def compare(sent: dict[str, Any], answers: dict[str, Any], form: FormTemplate) -> dict[str, str]:
    """Each question of a returned form against what was on file when it was sent: "unchanged" (left blank, or the
    same once normalized), "changed", "added" (nothing on file, an answer now), or "cleared" (the owner wrote "none",
    or, among boxes they did mark, left one on file unmarked). A question with no box marked keeps what is on file. A
    mailing address that is the unit's own, however written, is read as no separate mailing address."""
    from jason.community.forms import QuestionKind, option_key

    printed = sent.get("fields") or {}
    out = {}
    for question in form.questions:
        key = question.field
        given = answers.get(key)
        if question.kind is QuestionKind.CHECKBOX:           # one box an option: "delivery.by-mail"
            chosen = set(given or ())
            for o in question.options:
                k = f"{key}.{option_key(o)}"
                if not chosen:
                    if k in printed:
                        out[k] = "unchanged"
                elif o in chosen:
                    out[k] = "unchanged" if k in printed else "added"
                elif k in printed:
                    out[k] = "cleared"
            continue
        raw = (given[0] if given else "") if isinstance(given, (list, tuple)) else given
        if key == "mailing-address" and is_unit_address(str(raw or ""), str(sent.get("unit") or "")):
            raw = ""                                   # the unit's own address, written out: no separate mailing address
        now = normalize(key, raw)
        if not now:
            if key in printed or key in (sent.get("withheld") or []):
                out[key] = "unchanged"
        elif now in NONE:
            if key in printed:
                out[key] = "cleared"
        elif key in printed:
            out[key] = "unchanged" if _hash(now) == printed[key] else "changed"
        else:
            out[key] = "added"
    return out


def on_file(p: Prefill, form: FormTemplate) -> list[tuple[str, str]]:
    """Each question with what the Association has on file for it, as the owner reads it on the letter's own page."""
    from jason.community.forms import QuestionKind, option_key

    rows = []
    for number, question in enumerate(form.questions, 1):
        key = question.field
        if question.kind is QuestionKind.CHECKBOX:
            chosen = [o for o in question.options if p.values.get(f"{key}.{option_key(o)}")]
            shown = " and ".join(chosen) if chosen else "No choice on file"
            if key == "delivery" and not chosen:
                shown = "No choice on file: notices are mailed to the address on file (Civil Code §4040(a)(2))"
        elif key in p.withheld:
            shown = "On file (not printed, because this letter is addressed to the unit)"
        else:
            value = p.values.get(key)
            shown = str(value) if value else "Nothing on file"
        rows.append((f"{number}. {question.title}", shown))
    return rows


def letter_pdf(packet: Path, p: Prefill, out: Path, form: FormTemplate, *, as_of: date) -> Path:
    """The mailed letter for one owner: ``packet``'s cover letter, then a page of what is on file for this owner, then
    the blank form."""
    import html

    import pymupdf

    rows = "".join(f"<div class='row'><div class='q'>{html.escape(q)}</div>"
                   f"<div class='a'>{html.escape(v).replace(chr(10), '<br>')}</div></div>" for q, v in on_file(p, form))
    body = (
        "<h2>What the Association has on file for you</h2>"
        f"<p class='who'>{html.escape(p.name)} &middot; {html.escape(str(p.values.get('unit-address') or p.unit))}"
        f"<br>As of {as_of.strftime('%B')} {as_of.day}, {as_of.year}</p>"
        "<p>Compare this page with the enclosed form. <b>On the form, write only what is different.</b> A line you "
        "leave blank keeps what is shown here; write &ldquo;none&rdquo; to remove something. Mark how you want notices "
        "delivered (question 3) and your unit&rsquo;s occupancy (question 8) even if nothing has changed, then sign "
        "and date the form.</p>"
        f"{rows}"
    )
    css = ("body{font-family:sans-serif;font-size:10.5pt;line-height:1.35} h2{font-size:15pt;margin:0 0 6pt}"
           ".who{color:#444} .row{border-top:0.5pt solid #bbb;padding:5pt 0 4pt} .q{font-weight:bold;font-size:9.5pt}"
           ".a{margin-left:14pt}")
    with pymupdf.open(packet) as doc:
        width, height = doc[0].rect.width, doc[0].rect.height
        page = doc.new_page(1, width=width, height=height)
        page.insert_htmlbox(pymupdf.Rect(54, 54, width - 54, height - 54), body, css=css)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(out, garbage=3, deflate=True)
    return out


# -- the emailed copy: the association's suggestions where the owner has made no choice --------------------------------

@dataclass
class Activity:
    """How an owner deals with the association's email, from PayHOA (read live): the last sign-in, and over the window
    read, association emails delivered, opened, bounced, and unsubscribed, and the last one opened."""

    last_login: str = ""
    delivered: int = 0
    opened: int = 0
    bounced: int = 0
    unsubscribed: int = 0
    last_opened: str = ""


def read_activity(client: Any, org_id: int, people: dict[int, dict[str, Any]], *, today: date,
                  days: int = 365) -> dict[int, Activity]:
    """Each member's ``Activity`` over the last ``days``, by membership id, from PayHOA's communications log (newest
    first, so the read stops at the window's start) and the people's last sign-in."""
    from datetime import timedelta

    since = (today - timedelta(days=days)).isoformat()
    by_user = {int(p.get("userId") or 0): mid for mid, p in people.items()}
    out = {mid: Activity(last_login=str(p.get("lastLogin") or "")[:10]) for mid, p in people.items()}
    for row in client.iter_communications(org_id):
        if str(row.get("submittedAt") or row.get("createdAt") or "")[:10] < since:
            break
        mid = by_user.get(int(row.get("recipientId") or 0))
        if mid is None or row.get("type") != "email":
            continue
        a = out[mid]
        a.delivered += bool(row.get("deliveredAt"))
        a.opened += bool(row.get("openedAt"))
        a.bounced += bool(row.get("bouncedAt") or row.get("failedAt"))
        a.unsubscribed += bool(row.get("unsubscribedAt"))
        if row.get("openedAt"):
            a.last_opened = max(a.last_opened, str(row["openedAt"])[:10])
    return out


def reads_email(activity: Activity | None, rule: Any, today: date) -> str:
    """Why an owner counts as reading the association's email under ``rule`` (``SuggestedChoices``), or "" when not."""
    from datetime import timedelta

    if activity is None or activity.unsubscribed or (activity.bounced and not activity.opened):
        return ""
    since = (today - timedelta(days=rule.active_days)).isoformat()
    if activity.last_login >= since:
        return f"signed in to PayHOA {activity.last_login}"
    if rule.opens_count and activity.last_opened >= since:
        return f"opened the association's email {activity.last_opened}"
    return ""


def suggested(p: Prefill, activity: Activity | None, rule: Any, *, today: date) -> dict[str, Any]:
    """The association's suggestions for one owner's emailed form: "By email" where the owner has made no delivery
    choice, has a working email (it was printed), and reads the association's email; and a ballot method where they
    have none: paper for an owner who chose mail or paper, else electronic when they will have email. The owner's own
    choices are never changed."""
    if rule is None or not rule.apply:
        return {}
    out: dict[str, Any] = {}
    chose = p.values.get("delivery.by-email") or p.values.get("delivery.by-mail")
    why = reads_email(activity, rule, today) if p.values.get("email") else ""
    if not chose and why:
        out["delivery.by-email"] = True
        p.notes.append(f"suggested email: {why}")
    if rule.ballots and not p.values.get("ballots"):
        if p.values.get("delivery.by-mail"):
            out["ballots"] = "Paper ballot by mail"
        elif p.values.get("delivery.by-email") or out.get("delivery.by-email"):
            out["ballots"] = "Electronic ballot by email"
    return out


def fill_pdf(packet: Path, p: Prefill, out: Path, form: FormTemplate, *, extra: dict[str, Any] | None = None) -> Path:
    """One owner's fillable form (``packet``: the form alone for the emailed copy) with their values filled, and
    ``extra`` (the association's ``suggested`` choices) beside them. A choice is given to its radio group by the
    option's key."""
    from jason.community.forms import QuestionKind, option_key
    from jason.community.pdf_fields import fill

    choices = {q.field for q in form.questions if q.kind is QuestionKind.CHOICE}
    values = {k: option_key(v) if k in choices else v for k, v in {**p.values, **(extra or {})}.items()}
    # the usual answer's box checked where the record holds nothing else ("Same as my unit address": the owner's mail
    # goes to the unit), so the owner who has nothing to change has nothing to write
    for q in form.questions:
        if q.same_as and not values.get(q.field):
            values[q.same_as_field] = True
    out.parent.mkdir(parents=True, exist_ok=True)
    missing = fill(packet, values, out, multiline_size=form.style.typed_size)
    if missing:
        raise KeyError(f"no field for {', '.join(missing)} in {packet.name}")
    return out


__all__ = ["Activity", "Prefill", "compare", "place_of", "fill_pdf", "fingerprints", "letter_pdf", "normalize", "on_file",
           "postal_lines", "prefill", "prefills", "profile_address", "read_activity", "reads_email", "suggested",
           "unit_address"]
