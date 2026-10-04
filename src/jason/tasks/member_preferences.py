"""Owners' notice preferences gathered elsewhere, matched to PayHOA's current owners: what to record in PayHOA, and
what is only a lead because it is old.

PayHOA is the record (``jason.community.tags``): the member profile holds contact details the owner keeps, and tags hold
the 4041 elections. Every other channel (a paper form, an emailed fillable PDF, a Google Form) is a convenience whose
answers a person enters in PayHOA. This module reads those answers (``FormAnswers``, from ``tasks.forms``) and sets each
beside the unit's current owners in the stored catalog (``data/payhoa.db``), with three dates that decide whether an
answer may still change anything:

- **the deed**: the unit's latest recorded conveyance (the county's index, ``PartyResolver.latest_deed``). An answer sent
  before it was the prior owner's, or the same owner's before re-titling (a trust); it changes nothing. PayHOA's own
  occupancy date is used only when there is no deed and it is not PayHOA's setup date;
- **the profile**: when the owner last updated their PayHOA profile. An email or mailing address the owner updated
  after the answer stands; the answer never overwrites it;
- **the answer's cycle**: Civil Code 4041 asks for the answers each year (``AnswerCycle``). Only this year's answer
  proposes tag changes; last year's and older answers become questions to confirm with the owner, with their age.

Only the latest answer for a unit counts. Nothing here writes to PayHOA or keeps an owner's address.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from jason.community.base import read_unit_address
from jason.community.forms import AnswerCycle, Freshness, age
from jason.community.tags import PayhoaTag, TagPurpose, TagScope, owner_of_title, tag_names


class Standing(Enum):
    CURRENT_OWNER = "a current owner"
    NOT_AN_OWNER = "names no current owner"          # a tenant, an agent, or a name PayHOA spells differently
    BEFORE_OWNERSHIP = "sent before the unit last changed hands"
    NO_UNIT = "no unit matches the address"


@dataclass
class Owner:
    membership_id: int
    name: str
    email: str
    tags: set[str] = field(default_factory=set)              # the member's PayHOA tags, case folded
    profile_updated: str = ""                                # when the owner's PayHOA profile last changed (ISO)
    mailing: str = ""                                        # the profile's mailing street line ("" when none)


@dataclass
class UnitOwners:
    unit_id: int
    label: str
    number: int | None
    street: Any
    since: str                     # when PayHOA's current occupancy began (ISO)
    owners: list[Owner] = field(default_factory=list)
    tags: set[str] = field(default_factory=set)              # the unit's PayHOA tags, case folded
    deeded: str = ""               # the latest recorded deed (ISO), when the county index has one


@dataclass
class Matched:
    source: str
    submitted: str
    unit: UnitOwners | None
    standing: Standing
    owner: Owner | None = None
    how: str = ""                  # "email" or "name"
    latest: bool = False
    freshness: Freshness = Freshness.STALE
    age: str = ""
    record: dict[str, str] = field(default_factory=dict)    # what the answer says to record
    notes: list[str] = field(default_factory=list)
    tag_changes: list[str] = field(default_factory=list)      # this year's answer: "+Notices by Email (member)"
    choices: dict[str, str] = field(default_factory=dict)     # question key to the option chosen, or "given" for text
    confirm: list[str] = field(default_factory=list)          # an older answer: what to ask the owner

    @property
    def actionable(self) -> bool:
        return bool(self.tag_changes or self.record.get("email"))


def unit_owners(units: Iterable[dict[str, Any]], people: Iterable[dict[str, Any]],
                deeds: dict[str, date] | None = None, tags: Iterable[PayhoaTag] = ()) -> list[UnitOwners]:
    """Each unit with its current owners (not deleted), their profiles' last update, when PayHOA's occupancy began, and,
    from ``deeds`` (unit label to the latest recorded deed), when it last changed hands. ``units`` and ``people`` are
    PayHOA's rows, read live or from the stored catalog. With ``tags``, a record kept for an owner (additional
    deliveries, a legal representative) is left out: an answer is never matched to it."""
    tags = tuple(tags)
    deeds = {k.upper(): v for k, v in (deeds or {}).items()}
    members: dict[int, tuple[str, str, set[str], str, str]] = {}
    for person in people:
        if person.get("id") is None:
            continue
        profile = person.get("profile") or {}
        name = person.get("name") or " ".join(x for x in (profile.get("givenNames"), profile.get("familyName")) if x)
        members[int(person["id"])] = (name or "", str(person.get("email") or "").casefold(), tag_names(person),
                                      str(profile.get("updatedAt") or ""), str(profile.get("address1") or ""))
    out = []
    for unit in units:
        if unit.get("deletedAt"):
            continue
        label = str(unit.get("label") or unit.get("title") or unit.get("streetAddress") or "")
        open_ = [o for o in unit.get("occupancies") or [] if not o.get("toDate")]
        since = (open_[-1].get("fromDate") or "") if open_ else str((unit.get("currentOccupancy") or {}).get("fromDate") or "")
        number, street = read_unit_address(label)
        owners = [Owner(int(o["membershipId"]), *members.get(int(o["membershipId"]), ("", "", set(), "", "")))
                  for o in unit.get("owners") or [] if not o.get("deletedAt") and o.get("membershipId") is not None]
        owners = [o for o in owners if owner_of_title(tags, o.tags)]
        deed = deeds.get(label.upper())
        out.append(UnitOwners(int(unit["id"]), label, number, street, since, owners, tag_names(unit),
                              deed.isoformat() if deed else ""))
    return out


def payhoa_owners(db: Path, deeds: dict[str, date] | None = None, tags: Iterable[PayhoaTag] = ()) -> list[UnitOwners]:
    """``unit_owners`` from the stored PayHOA catalog (``data/payhoa.db``)."""
    con = sqlite3.connect(db)
    try:
        columns = {row[1] for row in con.execute("pragma table_info(people)")}
        query = "select id, name, email, " + ("raw_json" if "raw_json" in columns else "null") + " from people"
        people = [{**(json.loads(raw) if raw else {}), "id": pid, "name": name, "email": email}
                  for pid, name, email, raw in con.execute(query)]
        units = [{**json.loads(raw), "id": uid, "label": label} for uid, label, raw in con.execute("select id, label, raw_json from units")]
    finally:
        con.close()
    return unit_owners(units, people, deeds, tags)


def _words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", name.casefold()) if len(w) > 1}


def _owner_for(contacts: Iterable[dict[str, str]], owners: list[Owner]) -> tuple[Owner | None, str]:
    """The current owner a response names: the same email, else a name sharing the family name and a given name."""
    contacts = [c for c in contacts if c.get("role") in ("owner", "")]
    for c in contacts:
        email = (c.get("email") or "").casefold().strip()
        hit = next((o for o in owners if email and o.email == email), None)
        if hit:
            return hit, "email"
    for c in contacts:
        words = _words(c.get("name") or "")
        for o in owners:
            theirs = _words(o.name)
            if len(words & theirs) >= 2 or (words and words == theirs) or _short_name(c.get("name") or "", o.name):
                return o, "name"
    return None, ""


def _short_name(a: str, b: str) -> bool:
    """The same family name, and a given name that is a short form of the other's ("Pat" and "Patricia")."""
    x, y = re.findall(r"[a-z]+", a.casefold()), re.findall(r"[a-z]+", b.casefold())
    if len(x) < 2 or len(y) < 2 or x[-1] != y[-1]:
        return False
    return any(min(len(g), len(h)) >= 3 and (g.startswith(h) or h.startswith(g)) for g in x[:-1] for h in y[:-1])


def match(responses: Iterable[Any], units: list[UnitOwners], tags: Iterable[PayhoaTag] = (), *,
          cycle: AnswerCycle | None = None, today: date | None = None) -> list[Matched]:
    """Each response beside its unit's current owners. A current owner's latest answer, sent this ``cycle`` and after
    the unit last changed hands, proposes tag changes and any contact detail newer than the owner's profile; every
    other current owner's latest answer becomes questions to confirm. Without a cycle nothing is taken as this year's."""
    today = today or date.today()
    tags = tuple(tags)
    by_address = {(u.number, u.street): u for u in units if u.number}
    by_id = {u.unit_id: u for u in units}
    # The earliest occupancy is the day the owners were entered in PayHOA: an occupancy that began then began before
    # PayHOA, on a date PayHOA does not know.
    setup = min((u.since[:10] for u in units if u.since), default="")
    out: list[Matched] = []
    for r in responses:
        if getattr(r, "unit_id", None) is not None:              # a signed-in submission names its unit
            unit = by_id.get(int(r.unit_id))
        else:
            number, street = read_unit_address(r.answers.get("unit-address", ""))
            unit = by_address.get((number, street))
        fresh = cycle.freshness(r.submitted) if cycle else Freshness.STALE
        if unit is None:
            out.append(Matched(r.source, r.submitted, None, Standing.NO_UNIT, freshness=fresh, age=age(r.submitted, today)))
            continue
        titled = unit.deeded or (unit.since[:10] if unit.since[:10] != setup else "")
        before_title = bool(titled and r.submitted and r.submitted[:10] < titled)
        signed = next((o for o in unit.owners if getattr(r, "membership_id", None) is not None
                        and o.membership_id == int(r.membership_id)), None)
        owner, how = (signed, "PayHOA sign-in") if signed else _owner_for(r.contacts, unit.owners)
        if owner is not None:
            standing = Standing.CURRENT_OWNER
        elif before_title:
            standing = Standing.BEFORE_OWNERSHIP
        else:
            standing = Standing.NOT_AN_OWNER
        m = Matched(r.source, r.submitted, unit, standing, owner, how, freshness=fresh, age=age(r.submitted, today))
        if before_title:
            m.notes.append(f"the unit's deed recorded {titled}, after this answer" if unit.deeded
                           else f"PayHOA's occupancy began {titled}, after this answer")
        if owner is not None:
            m.record, notes = _to_record(r.answers, owner, r.submitted)
            m.choices = _choices(r.answers)
            m.notes += notes
            from jason.tasks.owner_prefill import is_unit_address

            if m.record.get("mailing address") and is_unit_address(str(r.answers.get("mailing-address") or ""), unit.label):
                m.record.pop("mailing address")                # the unit's own address: the unit's is used
                m.notes.append("the mailing address given is the unit's own, written differently: the unit's is used")
            if before_title:
                m.notes.append("the same owner answered before the latest deed (a re-titling, such as to a trust, or a "
                               "purchase); the answer predates the current title")
        else:
            shared = max((len(_words(c.get("name") or "") & _words(o.name)) for c in r.contacts for o in unit.owners),
                         default=0)
            if shared:
                m.notes.append("shares a name with the PayHOA owner: a co-owner PayHOA lacks, a relative, or an agent; ask")
            if not unit.deeded and unit.since[:10] == setup:
                m.notes.append("no deed on file, and PayHOA's occupancy date is its setup date, not the date of title")
        out.append(m)
    latest: dict[int, Matched] = {}
    for m in out:
        if m.unit and m.standing is Standing.CURRENT_OWNER and (m.unit.unit_id not in latest or m.submitted > latest[m.unit.unit_id].submitted):
            latest[m.unit.unit_id] = m
    for m in latest.values():
        m.latest = True
        changes = propose_tags(m, tags)
        current = m.freshness is Freshness.CURRENT and not any("after this answer" in n for n in m.notes)
        if current:
            answered = [t for t in tags if t.purpose is TagPurpose.ANSWERED and t.scope is TagScope.MEMBER
                        and (cycle is None or t.value == str(cycle.year))]
            m.tag_changes = changes + [f"+{t.name} ({t.scope.value})" + ("" if t.exists else " [create the tag]")
                                       for t in answered if m.owner and t.name.casefold() not in m.owner.tags]
        else:
            when = f"answered {m.submitted[:10]}, {m.age} ago ({m.freshness.value})"
            m.confirm = [f"{c} ({when})" for c in changes]
            if m.record.get("email"):
                m.confirm.append(f"email {m.record.pop('email')} ({when})")
            for key in ("mailing address", "secondary delivery"):
                if m.record.get(key):
                    m.confirm.append(f"{key} {m.record[key]} ({when})")
    return out


def propose_tags(m: Matched, tags: tuple[PayhoaTag, ...]) -> list[str]:
    """The tag changes a current owner's answers make: the member's notice-delivery tags, and every tag that names the
    form question it follows (``PayhoaTag.answer``: occupancy, a legal representative on file, the membership-list
    opt-out, a paper ballot). A second address is an additional owner record, not a tag. A tag the association has not created yet is marked so."""
    if m.owner is None or m.unit is None:
        return []
    changes: list[str] = []

    def change(sign: str, tag: PayhoaTag) -> None:
        changes.append(f"{sign}{tag.name} ({tag.scope.value})" + ("" if tag.exists else " [create the tag]"))

    elected = set(re.findall(r"email|mail", m.record.get("delivery", "")))
    if elected:
        for tag in (t for t in tags if t.purpose is TagPurpose.NOTICE_DELIVERY and t.scope is TagScope.MEMBER):
            has = tag.name.casefold() in m.owner.tags
            if tag.value in elected and not has:
                change("+", tag)
            elif tag.value not in elected and has:
                change("-", tag)
    for tag in (t for t in tags if t.answer and t.answer in m.choices):
        chosen = m.choices[tag.answer]
        has = tag.name.casefold() in (m.unit.tags if tag.scope is TagScope.UNIT else m.owner.tags)
        applies = chosen == tag.value if tag.value else bool(chosen)
        if applies and not has:
            change("+", tag)
        elif not applies and has and chosen:
            change("-", tag)
    return changes


def _choices(answers: dict[str, Any]) -> dict[str, str]:
    """Each answered question's choice: a choice's option, or "given" for text (the text itself stays in the
    submission). An empty answer is left out, so it changes no tag."""
    out = {}
    for key, value in answers.items():
        if isinstance(value, (list, tuple)):
            if value:
                out[key] = str(value[0])
        elif str(value or "").strip():
            out[key] = "given"
    return out


def _to_record(answers: dict[str, Any], owner: Owner, submitted: str) -> tuple[dict[str, str], list[str]]:
    """What the answer says to record. An email or mailing address is dropped when the owner's PayHOA profile changed
    after the answer: the owner's own later update stands."""
    record: dict[str, str] = {}
    notes: list[str] = []
    newer_profile = bool(owner.profile_updated and submitted and owner.profile_updated[:10] > submitted[:10])
    delivery = answers.get("delivery") or []
    if delivery:
        record["delivery"] = " and ".join(d.replace("By ", "") for d in delivery)
    else:
        notes.append("no delivery preference given (the question was not on the form, or not answered)")
    email = (answers.get("email") or "").strip()
    gave_contact = (email and email.casefold() != owner.email) or answers.get("mailing-address")
    if newer_profile and gave_contact:
        notes.append(f"the owner's PayHOA profile changed {owner.profile_updated[:10]}, after this answer: PayHOA's email "
                     "and mailing address stand")
    elif email and email.casefold() != owner.email:
        record["email"] = email
        notes.append("the form's email differs from PayHOA's" if owner.email else "PayHOA has no email for this owner")
    same = _same_as("mailing-address")
    if same and answers.get("mailing-address") == same and not newer_profile:
        from jason.community.postal import normalize_address

        unit = str(answers.get("unit-address") or "")
        on_file = normalize_address(owner.mailing)
        if not on_file or (unit and on_file == normalize_address(unit)):
            # PayHOA already mails to the unit: nothing for a person to enter
            notes.append("mailing address: the unit (the box: same as my unit address), as PayHOA has it")
        else:
            record["mailing address"] = ("the unit (the box: same as my unit address), but PayHOA's profile has "
                                         "another address: a person changes it")
    elif answers.get("mailing-address") and not newer_profile:
        from jason.community import community as active
        from jason.community.postal import read_mailing_address

        found, how = read_mailing_address(str(answers["mailing-address"]), active().unit_city_state_zip())
        record["mailing address"] = ("given on the form: compare with PayHOA's profile" if found is not None
                                     else "given on the form, but it does not read as an address: a person enters it")
        if how:
            notes.append(f"the mailing address is a street line here: {how}")
    parts = [answers.get(k) or "" for k in ("second-email", "second-mailing-address", "second-address")]
    second = " ".join(p if isinstance(p, str) else " ".join(p) for p in parts)
    known = {e for e in (owner.email, email.casefold()) if e}
    emails = [e.casefold() for e in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", second)]
    if emails and all(e in known for e in emails) and not re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|[\s,;/]", "", second):
        # the owner's own email again (often in other capitals): no second delivery, or they'd get two copies
        notes.append("the second address given is the owner's own email: no second delivery")
    elif second.strip():
        record["secondary delivery"] = "given on the form"
    if answers.get("occupancy"):
        record["occupancy"] = answers["occupancy"][0]
    manager, manager_notes = _manager(answers, known)
    if manager:
        record["property manager"] = manager
    notes += manager_notes
    return record, notes


def _same_as(field_name: str) -> str:
    """The owner-information form's box for a question's usual answer ("Same as my unit address"), or ""."""
    from jason.community.spec import spec_module

    try:
        return spec_module("forms").OWNER_INFO.question(field_name).same_as
    except (KeyError, AttributeError, ValueError):
        return ""


# What the owner lets the Association do with their property manager's contact (the form's manager-role options).
MANAGER_COPIES, MANAGER_CONTACT = "Send my manager copies of Association notices", "Contact my manager if I can't be reached"


def _manager(answers: dict[str, Any], owner_emails: set[str]) -> tuple[str, list[str]]:
    """The owner's property manager as the record it becomes: a person record tagged Property Manager with the role
    the owner chose (copies of notices: Additional Deliveries, 4041(a)(2); contact in the owner's absence: Legal
    Representative, 4041(a)(3)), or, with neither, an other contact kept on file. Nothing without a name or contact."""
    name = str(answers.get("manager-name") or "").strip()
    email = str(answers.get("manager-email") or "").strip()
    phone = str(answers.get("manager-phone") or "").strip()
    roles = answers.get("manager-role") or []
    roles = [roles] if isinstance(roles, str) else list(roles)
    notes: list[str] = []
    if not (name or email or phone):
        if roles:
            notes.append("a manager role is checked but no manager is named: a person asks the owner")
        return "", notes
    if email and email.casefold() in owner_emails:
        notes.append("the manager's email is the owner's own: kept on file only")
        roles = []
    tags = []
    if MANAGER_COPIES in roles:
        tags.append("Additional Deliveries")
        if not email:
            notes.append("copies to the manager asked for, but no manager email: a person asks the owner for one")
    if MANAGER_CONTACT in roles:
        tags.append("Legal Representative")
        if str(answers.get("representative-name") or "").strip():
            notes.append("a legal representative and a manager to contact are both named: a person confirms which")
    if not tags:
        return "other contact (on file only; no notices)", notes
    return "person record, no invitation, tagged Property Manager and " + " and ".join(tags), notes


def summary(matched: list[Matched]) -> dict[str, Any]:
    from collections import Counter

    latest = [m for m in matched if m.latest]
    return {
        "responses": len(matched),
        "byStanding": dict(Counter(m.standing.value for m in matched)),
        "byAge": dict(Counter(m.freshness.value for m in matched)),
        "unitsWithACurrentOwnerAnswer": len(latest),
        "toApply": sum(1 for m in latest if m.tag_changes or m.record.get("email")),
        "toConfirmWithTheOwner": sum(1 for m in latest if m.confirm),
        "profileUpdatedSince": sum(1 for m in latest if any("profile changed" in n for n in m.notes)),
        "answeredBeforeTheLatestDeed": sum(1 for m in matched if any("after this answer" in n for n in m.notes)),
    }


REVIEW_HEADER = ["unit", "PayHOA owner", "matched by", "sent", "age", "cycle", "standing", "latest for the unit",
                 "deed recorded", "profile updated", "delivery", "email to record", "tag changes (this year's answer)",
                 "to confirm with the owner (older answer)", "notes"]


def review_rows(matched: list[Matched]) -> list[list[str]]:
    """One row a response, for the person entering preferences in PayHOA. Names and emails are PayHOA's own or the
    owner's own answer; no mailing address is written."""
    rows = []
    for m in sorted(matched, key=lambda m: ((m.unit.label if m.unit else "~"), m.submitted)):
        rows.append([m.unit.label if m.unit else "(no unit)", m.owner.name if m.owner else "", m.how, m.submitted[:10],
                     m.age, m.freshness.value, m.standing.value, "yes" if m.latest else "",
                     m.unit.deeded if m.unit else "", (m.owner.profile_updated[:10] if m.owner else ""),
                     m.record.get("delivery", ""), m.record.get("email", ""), "; ".join(m.tag_changes),
                     "; ".join(m.confirm), "; ".join(m.notes)])
    return rows


__all__ = ["Matched", "Owner", "REVIEW_HEADER", "Standing", "UnitOwners", "match", "payhoa_owners", "review_rows", "summary",
           "unit_owners"]
