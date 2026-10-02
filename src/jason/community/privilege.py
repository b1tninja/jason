"""Whether a document is likely privileged: a lead for counsel's review, never the determination.

California protects confidential communications between a client and its lawyer (Evid. Code 954) and a lawyer's work
product (Code Civ. Proc. 2018.030). A communication with the liability insurer or its claims administrator about the
defense can share the privilege under the insurer-insured-counsel relationship (Soltani-Rastegar v. Superior Court
(1989) 208 Cal.App.3d 424; Evid. Code 952), but routine claim handling may not. A document from the other side (the
plaintiff's counsel, a pleading) or from an outside party (the owner's own insurer, a vendor) is not privileged. An
executive session's recording is confidential from members (Civil Code 4935, 5215(a)(5)) but is not, for that alone,
privileged in the lawsuit.

``classify`` reads a document's parties (the email domains it came from or went to) against the specification's
``PrivilegeParty`` rows, then its name against ``PrivilegeNameRule`` rows, and returns a ``PrivilegeCall``: the kind,
why, and whether counsel should review it. A document with no party and no telling name is "none found", not "not
privileged".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class Role(Enum):
    COUNSEL = "the association's counsel"
    INSURER = "the association's insurer or claims administrator"
    BROKER = "the association's insurance broker"
    ADVERSE = "the other side"
    THIRD_PARTY = "an outside party"


class PrivilegeKind(Enum):
    ATTORNEY_CLIENT = "attorney-client"
    WORK_PRODUCT = "attorney-client; work product"
    INSURER_DEFENSE = "insurer-defense"
    TRANSMITTED = "sent through counsel"
    REVIEW = "review"
    NOT_PRIVILEGED = "not privileged"
    NONE_FOUND = "none found"


@dataclass(frozen=True)
class PrivilegeParty:
    domain: str
    role: Role
    name: str


@dataclass(frozen=True)
class PrivilegeNameRule:
    pattern: str
    kind: PrivilegeKind
    why: str

    def matches(self, name: str) -> bool:
        return bool(re.search(self.pattern, name, re.I))


@dataclass(frozen=True)
class PrivilegeCall:
    kind: PrivilegeKind
    basis: str                       # short: a domain, "via fmglaw.com", or a few words; it goes in the Drive label
    review: bool
    note: str = ""                   # the explanation, kept in the register

    def label(self) -> str:
        """A short label value: "attorney-client: fmglaw.com; review"."""
        return f"{self.kind.value}: {self.basis}" + ("; review" if self.review and self.kind is not PrivilegeKind.REVIEW else "")

    def record(self) -> dict[str, object]:
        return {"privilege": self.kind.value, "basis": self.basis, "counselReview": self.review, "note": self.note}


def classify(name: str, domains: list[str] | tuple[str, ...], parties: tuple[PrivilegeParty, ...],
             rules: tuple[PrivilegeNameRule, ...] = (), *, communication: bool = True) -> PrivilegeCall:
    """The strongest call the parties and the name support.

    A document that already existed (medical records, an invoice, photos, a police report) does not become privileged
    by being sent to counsel: with ``communication`` false, counsel or the insurer on the thread gives "sent through
    counsel", and the forwarding email, not the document, may be privileged. The other side on a thread, a court filing,
    and the association's own letter to an owner are not privileged whoever forwarded them. Counsel on a communication
    outranks the insurer."""
    by_domain = {p.domain: p for p in parties}
    present = [by_domain[d] for d in domains if d in by_domain]
    roles = {p.role for p in present}
    named = next((r for r in rules if r.matches(name)), None)
    if Role.ADVERSE in roles:
        who = next(p for p in present if p.role is Role.ADVERSE)
        return PrivilegeCall(PrivilegeKind.NOT_PRIVILEGED, f"exchanged with {who.name}", False)
    if named is not None and named.kind is PrivilegeKind.NOT_PRIVILEGED:
        return PrivilegeCall(named.kind, named.why, False)
    helper = next((p for p in present if p.role is Role.COUNSEL), None) or next((p for p in present if p.role is Role.INSURER), None)
    if helper is not None and not communication and not (named and named.kind is PrivilegeKind.WORK_PRODUCT):
        return PrivilegeCall(PrivilegeKind.TRANSMITTED, f"via {helper.domain}", True,
                             "a document that already existed; the forwarding email may be privileged, the document itself only "
                             "if counsel made it")
    if Role.COUNSEL in roles:
        who = next(p for p in present if p.role is Role.COUNSEL)
        kind = PrivilegeKind.WORK_PRODUCT if named and named.kind is PrivilegeKind.WORK_PRODUCT else PrivilegeKind.ATTORNEY_CLIENT
        return PrivilegeCall(kind, who.domain, True)
    if named is not None:
        return PrivilegeCall(named.kind, named.why, True)
    if Role.INSURER in roles:
        who = next(p for p in present if p.role is Role.INSURER)
        return PrivilegeCall(PrivilegeKind.INSURER_DEFENSE, who.domain, True)
    if Role.BROKER in roles or Role.THIRD_PARTY in roles:
        who = next(p for p in present if p.role in (Role.BROKER, Role.THIRD_PARTY))
        return PrivilegeCall(PrivilegeKind.NOT_PRIVILEGED, f"with {who.name}", Role.BROKER in roles)
    return PrivilegeCall(PrivilegeKind.NONE_FOUND, "no counsel, insurer, or telling name", False)


__all__ = ["PrivilegeCall", "PrivilegeKind", "PrivilegeNameRule", "PrivilegeParty", "Role", "classify"]
