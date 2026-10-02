"""Who receives a required notice how: every current owner, by their PayHOA tags, under Civil Code 4040 and 4045.

PayHOA is the record (``jason.community.tags``): an owner's member tags carry their 4041 election, their profile
carries the email and mailing address, and PayHOA marks an email it cannot deliver to. ``plan`` reads the units and
people (as the catalog stored them, or live) and gives each current owner their channels and the reason. A secondary
owner record (tagged "Additional Deliveries") is not an owner: it is kept apart, for the 4040(b) copies only, and its channels
are its fields: email when it has a deliverable email, mail when it has a mailing address.

``audience`` resolves one notice rule (``jason.community.notices``) to the exact recipients:

- an individual notice: the owners in reach by email or mail as each elected (mail without an election), plus the
  secondary contacts when the rule sends 4040(b) copies;
- a general notice: posted, plus individual delivery to the members who asked for general notices that way (4045(b));
- a rule whose reach is a unit tag (a building): only the owners of the units carrying it.

PayHOA's filters select anyone carrying any chosen tag and cannot select "no election". ``audience`` gives the ids the
sending tools take; ``filters`` says how a person picks the same people in PayHOA, true only once ``audit`` is clean:
every owner carries a delivery tag (mail until they elect otherwise), so "Notices by Mail" selects everyone the law sends
mail. Nothing is sent or changed from here; a send reads PayHOA live first.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable

from jason.community.notices import NoticeKind, NoticeRule
from jason.community.tags import Channel, PayhoaTag, TagPurpose, TagScope, delivery, owner_of_title, tag_names, tagged


@dataclass
class OwnerDelivery:
    unit_id: int
    unit: str
    membership_id: int
    name: str
    channels: tuple[Channel, ...]
    reason: str
    send_to: str = ""
    answered: bool = False
    unit_tags: list[str] = field(default_factory=list)      # the unit's occupancy, statements, and ballot tags
    unit_tag_names: set[str] = field(default_factory=set)   # every tag on the unit, case folded
    member_tags: set[str] = field(default_factory=set)      # every tag on the member, case folded
    email_ok: bool = False                                    # PayHOA has a deliverable email for them


@dataclass
class DeliveryPlan:
    owners: list[OwnerDelivery] = field(default_factory=list)
    secondary_contacts: list[OwnerDelivery] = field(default_factory=list)   # secondary owner records: 4040(b) copies by email or mail
    representatives: list[OwnerDelivery] = field(default_factory=list)      # legal representatives: never sent notices
    unit_contacts: dict[int, list[dict[str, Any]]] = field(default_factory=dict)  # a unit's other contacts: checked, never used for copies
    synced: str = ""

    @property
    def email_ids(self) -> list[int]:
        return sorted({o.membership_id for o in self.owners if Channel.EMAIL in o.channels})

    def mail(self, send_to: str | None = None) -> list[OwnerDelivery]:
        return [o for o in self.owners if Channel.MAIL in o.channels and (send_to is None or o.send_to == send_to)]

    def summary(self) -> dict[str, Any]:
        mail = self.mail()
        return {
            "currentOwners": len(self.owners),
            "units": len({o.unit_id for o in self.owners}),
            "email": len(self.email_ids),
            "mail": len(mail),
            "mailToMailingAddress": len(self.mail("mailing")),
            "mailToUnit": len(self.mail("unit")),
            "secondaryContacts": len(self.secondary_contacts),
            "unitContactsWithEmail": sum(1 for rows in self.unit_contacts.values() for c in rows if c.get("email")),
            "byReason": dict(Counter(o.reason for o in self.owners)),
            "answeredThisYear": sum(1 for o in self.owners if o.answered),
            "paperStatementsWithNoNoticeElection": len({o.unit_id for o in self.owners
                                                        if o.reason.startswith("no election")
                                                        and any(t.startswith("statements") for t in o.unit_tags)}),
            "catalogSynced": self.synced,
        }


def plan(units: Iterable[dict[str, Any]], people: Iterable[dict[str, Any]], tags: Iterable[PayhoaTag], *,
         synced: str = "", unit_contacts: dict[int, list[dict[str, Any]]] | None = None) -> DeliveryPlan:
    """Each current owner's delivery from the units (their owners and tags) and people (tags, email, profile); members
    tagged as secondary copy records kept apart; ``unit_contacts`` (unit id to its other contacts, read live) for the
    audit (a broadcast's "other contacts" reaches them; copies go to secondary owner records)."""
    tags = tuple(tags)
    members = {int(p["id"]): p for p in people if p.get("id") is not None}
    answered_tags = {t.name.casefold() for t in tags if t.purpose is TagPurpose.ANSWERED and t.scope is TagScope.MEMBER}
    shown = (TagPurpose.OCCUPANCY, TagPurpose.STATEMENTS, TagPurpose.BALLOT)
    out = DeliveryPlan(synced=synced, unit_contacts={int(k): list(v) for k, v in (unit_contacts or {}).items()})
    for unit in units:
        if unit.get("deletedAt"):
            continue
        unit_names = tag_names(unit)
        unit_tags = [f"{t.purpose.value}: {t.name}" for p in shown for t in tagged(tags, unit_names, p, TagScope.UNIT)]
        label = str(unit.get("title") or unit.get("streetAddress") or unit.get("id"))
        for owner in unit.get("owners") or []:
            if owner.get("deletedAt") or owner.get("membershipId") is None:
                continue
            mid = int(owner["membershipId"])
            person = members.get(mid, {})
            names = tag_names(person)
            profile = person.get("profile") or {}
            valid = bool(person.get("email")) and not owner.get("hasInvalidEmailAddress") \
                and "missing email address" not in names
            d = delivery(tags, names, valid_email=valid, mailing_address=bool(profile.get("address1")))
            name = " ".join(x for x in (profile.get("givenNames"), profile.get("familyName")) if x) or str(person.get("email") or mid)
            row = OwnerDelivery(int(unit["id"]), label, mid, name, d.channels, d.reason, d.send_to,
                                bool(names & answered_tags), unit_tags, unit_names, names, valid)
            if tagged(tags, names, TagPurpose.SECONDARY_CONTACT, TagScope.MEMBER):
                row.channels = tuple(c for c, has in ((Channel.EMAIL, valid), (Channel.MAIL, bool(profile.get("address1"))))
                                     if has)
                row.send_to = "mailing" if profile.get("address1") else ""
                row.reason = "secondary copies (4040(b)) only"
                out.secondary_contacts.append(row)
            elif not owner_of_title(tags, names):
                row.channels, row.reason = (), "legal representative (4041(a)(3)): a contact, not a recipient"
                out.representatives.append(row)
            else:
                out.owners.append(row)
    out.owners.sort(key=lambda o: (o.unit, o.name))
    return out


@dataclass
class NoticeAudience:
    rule: NoticeRule
    unit_tag: str = ""
    email: list[OwnerDelivery] = field(default_factory=list)
    mail: list[OwnerDelivery] = field(default_factory=list)
    secondary: list[OwnerDelivery] = field(default_factory=list)          # 4040(b) copies: secondary owner records
    courtesy: list[OwnerDelivery] = field(default_factory=list)            # emailed as a courtesy, not the law's delivery
    posted: bool = False

    @property
    def email_ids(self) -> list[int]:
        return sorted({o.membership_id for o in self.email + self.courtesy
                       + [s for s in self.secondary if Channel.EMAIL in s.channels]})

    def summary(self) -> dict[str, Any]:
        return {
            "notice": self.rule.title, "authority": self.rule.authority, "kind": self.rule.kind.value,
            "reach": self.unit_tag or self.rule.reach, "posted": self.posted,
            "ownersInReach": len({o.membership_id for o in self.email + self.mail}),
            "emails": len({o.membership_id for o in self.email}),
            "courtesyEmails": len({o.membership_id for o in self.courtesy}),
            "noDeliverableEmail": len({o.membership_id for o in self.email + self.mail if not o.email_ok}),
            "letters": len(self.mail),               # one a unit an owner holds; an owner of two units gets two
            "mailToMailingAddress": sum(1 for o in self.mail if o.send_to == "mailing"),
            "mailToUnit": sum(1 for o in self.mail if o.send_to == "unit"),
            "secondaryCopiesByMail": sum(1 for s in self.secondary if Channel.MAIL in s.channels),
            "secondaryCopiesByEmail": sum(1 for s in self.secondary if Channel.EMAIL in s.channels),
            "note": self.rule.note,
        }


def audience(found: DeliveryPlan, rule: NoticeRule, tags: Iterable[PayhoaTag], *, unit_tag: str = "") -> NoticeAudience:
    """The exact recipients of one notice. A rule whose reach is a unit tag needs ``unit_tag`` (a building's tag)."""
    if rule.reach == "unit tag" and not unit_tag:
        raise ValueError(f"{rule.key} reaches the owners of a unit tag: give one (a building's tag)")
    if rule.reach == "one owner":
        raise ValueError(f"{rule.key} goes to one owner at a time, not to a list")
    tags = tuple(tags)
    scope = unit_tag.casefold()
    owners = [o for o in found.owners if not scope or scope in o.unit_tag_names]
    out = NoticeAudience(rule, unit_tag)
    if rule.kind is NoticeKind.GENERAL:
        out.posted = True
        owners = [o for o in owners if tagged(tags, o.member_tags, TagPurpose.GENERAL_INDIVIDUALLY, TagScope.MEMBER)]
    out.email = [o for o in owners if Channel.EMAIL in o.channels]
    out.mail = [o for o in owners if Channel.MAIL in o.channels]
    if rule.courtesy_email:                               # a courtesy copy to every deliverable address, beside the law's
        out.courtesy = [o for o in owners if o.email_ok and Channel.EMAIL not in o.channels]
    if rule.secondary_copies:
        units = {o.unit_id for o in owners}
        out.secondary = [s for s in found.secondary_contacts if s.unit_id in units
                         and (rule.unconfirmed_copies
                              or not tagged(tags, s.member_tags, TagPurpose.UNCONFIRMED, TagScope.MEMBER))]
    return out


def filters(rule: NoticeRule, tags: Iterable[PayhoaTag], *, unit_tag: str = "") -> list[str]:
    """How a person selects the same recipients with PayHOA's own filters: true once ``audit`` finds nothing."""
    tags = tuple(tags)
    by = {(t.purpose, t.value): t.name for t in tags if t.purpose is TagPurpose.NOTICE_DELIVERY}
    email, mail = by.get((TagPurpose.NOTICE_DELIVERY, "email"), "?"), by.get((TagPurpose.NOTICE_DELIVERY, "mail"), "?")
    scope = f" and unit tag '{unit_tag}'" if unit_tag else ""
    lines = []
    if rule.kind is NoticeKind.GENERAL:
        general = next((t.name for t in tags if t.purpose is TagPurpose.GENERAL_INDIVIDUALLY), "?")
        lines.append("Post it at the posting location the annual policy statement names.")
        scope += f" and member tag '{general}'"
    copies = next((t.name for t in tags if t.purpose is TagPurpose.SECONDARY_CONTACT), "?")
    if rule.courtesy_email:
        lines.append(f"Broadcast (email) to every owner as two sends, member tag '{email}'{scope}, then '{mail}'{scope}: "
                     "every owner carries one, and the secondary owner records carry neither (an 'all owners' send would "
                     f"reach them). For owners tagged '{email}' it is the law's delivery; for the rest a courtesy copy.")
    else:
        lines.append(f"Broadcast (email): member tag '{email}'{scope}.")
    lines.append(f"Mailroom (first-class mail): member tag '{mail}'{scope}, to the mailing address (the unit when none). "
                 "The Mailroom lists every owner of each unit picked, secondary owner records included: uncheck them "
                 "(and any co-owner who elected email only), or send to jason's list (--ids).")
    if rule.secondary_copies:
        within = f" and unit tag {unit_tag!r}" if unit_tag else ""
        lines.append(f"Secondary copies by email (4040(b)): broadcast to member tag '{copies}'{within}; PayHOA emails the "
                     "records that have an email.")
        lines.append(f"Secondary copies by mail (4040(b)): Mailroom to member tag '{copies}'{within}, leaving out the "
                     "records with no mailing address (PayHOA would mail them at the unit), or send to jason's list (--ids).")
    if unit_tag:
        lines.append("A unit tag and a member tag together select what carries both, in the people list and the "
                     "Mailroom's unit picker alike (seen October 1, 2026).")
    return lines


def audit(found: DeliveryPlan, tags: Iterable[PayhoaTag]) -> list[dict[str, Any]]:
    """What keeps PayHOA's own filters from selecting the right people: an owner with no delivery tag (the law sends
    them mail, but no filter finds them), an email election with no deliverable email (they need mail too, so tag
    mail), an additional-deliveries record that reaches no one or carries an owners' delivery tag, and a unit contact
    with an email (a broadcast's "other contacts" would reach it)."""
    tags = tuple(tags)
    mail_tag = next((t for t in tags if t.purpose is TagPurpose.NOTICE_DELIVERY and t.value == "mail"), None)
    out = []
    for o in found.owners:
        elected = tagged(tags, o.member_tags, TagPurpose.NOTICE_DELIVERY, TagScope.MEMBER)
        if not elected and mail_tag:
            out.append({"unit": o.unit, "member": o.membership_id, "name": o.name,
                        "change": f"+{mail_tag.name}" + ("" if mail_tag.exists else " [create the tag]"),
                        "why": "no election on file: the law sends first-class mail (4040(a)(2)); the tag lets "
                               "PayHOA's filter find them"})
        elif "no valid email" in o.reason and mail_tag and mail_tag not in elected:
            out.append({"unit": o.unit, "member": o.membership_id, "name": o.name, "change": f"+{mail_tag.name}",
                        "why": "elected email, but PayHOA has no deliverable email: mail until one is on file"})
    for s in found.secondary_contacts:
        if not s.channels:
            out.append({"unit": s.unit, "member": s.membership_id, "name": s.name, "change": "add the email or address",
                        "why": "a copy record with neither a deliverable email nor a mailing address reaches no one"})
    for s in found.secondary_contacts + found.representatives:
        if tagged(tags, s.member_tags, TagPurpose.NOTICE_DELIVERY, TagScope.MEMBER):
            out.append({"unit": s.unit, "member": s.membership_id, "name": s.name, "change": "remove the delivery tag",
                        "why": "an owners' delivery tag on a record kept for an owner: the owners' filters would select it"})
    for unit_id, contacts in found.unit_contacts.items():
        for c in contacts:
            if c.get("email"):
                out.append({"unit": unit_id, "member": None, "name": c.get("name") or "", "change": "confirm",
                            "why": "a unit contact with an email: a broadcast that includes 'other contacts' reaches it; "
                                   "copies go to secondary owner records, not unit contacts"})
    return out


__all__ = ["DeliveryPlan", "NoticeAudience", "OwnerDelivery", "audience", "audit", "filters", "plan"]
