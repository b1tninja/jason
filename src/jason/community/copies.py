"""Copies of one document: the same invoice or bill as it reached the association by different channels.

An invoice can arrive as the issuer's own record (the i-doxs or SMUD portal PDF, the vendor portal's invoice), as an
email attachment, as a PDF someone attached to a PayHOA payment, and as a paper letter PostScanMail scanned. Each is a
``DocumentCopy``: where it is, how it came, and what identifies it (issuer, number, account, date, amount, content hash).
The catalog keeps every copy as it is; ``group`` joins the copies that are one document, and each join records the rule
that made it. ``best`` picks the copy to read by the association's channel priority.

The identity rules, in order (the first that holds joins two copies):

1. the same file (content hash);
2. the same issuer and the same document number;
3. the same issuer, account, and date;
4. the same issuer and amount, dated within three days, when neither copy prints a number;
5. the same issuer and amount when one copy has neither a date nor a number of its own: a letter that arrived up to
   21 days after the other copy's date (the post takes that long).

Copies with no issuer never join on rules 2 to 4: a number or an amount alone is not an identity. A miss stays a miss.

Each copy carries its stage (``Stage`` from the repair paperwork: proposal, contract, change order, invoice). A vendor
quotes, the board accepts, the work is done, and the invoice follows, often for the same amount. So a bid and an invoice
are two documents: across those stages only the same file joins. ``fulfilments`` links each proposal to the invoice that
followed it (same issuer, on or after the proposal, the same amount or within ``NEAR_SHARE``), and the invoice, not the
proposal, is what a payment pays.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum

from jason.community.incidents import Stage

ARRIVAL_DAYS = 21
# The stages that come before the work: a quote, an estimate, a bid, a signed proposal, a change order.
BEFORE_WORK = frozenset({Stage.PROPOSAL, Stage.CONTRACT, Stage.CHANGE_ORDER})
# An invoice within this share of the proposal's amount fulfils it when none matches exactly (a final bill moves a little).
NEAR_SHARE = 0.10
# How long after a proposal its invoice may come.
FULFIL_DAYS = 365


class Channel(Enum):
    ISSUER_PORTAL = "issuer's portal"
    EMAIL = "email attachment"
    PAYHOA = "PayHOA attachment"
    PAPER = "paper mail scan"
    LIBRARY = "document library"


class JoinRule(Enum):
    SAME_FILE = "same file"
    SAME_NUMBER = "same issuer and number"
    SAME_ACCOUNT_DATE = "same issuer, account, and date"
    SAME_AMOUNT_DATE = "same issuer and amount within three days"
    SAME_AMOUNT_ARRIVAL = "same issuer and amount; the letter arrived within 21 days"


@dataclass(frozen=True)
class DocumentCopy:
    channel: Channel
    ref: str
    issuer: str = ""
    number: str = ""
    account: str = ""
    issued: date | None = None
    total_cents: int | None = None
    sha256: str = ""
    received: date | None = None
    readable: bool = True
    # The PayHOA transaction a PayHOA attachment hangs on.
    payhoa_tx: int | None = None
    title: str = ""
    stage: Stage | None = None


def norm_number(number: str) -> str:
    """A document number as issuers and OCR vary it: letters and digits only, upper case, leading zeros dropped."""
    return re.sub(r"[^A-Z0-9]", "", number.upper()).lstrip("0")


def norm_account(account: str) -> str:
    return re.sub(r"\D", "", account).lstrip("0")


def join_rule(a: DocumentCopy, b: DocumentCopy) -> JoinRule | None:
    """The first identity rule under which two copies are one document, or None."""
    if a.sha256 and a.sha256 == b.sha256:
        return JoinRule.SAME_FILE
    if not a.issuer or a.issuer != b.issuer:
        return None
    # A bid and the invoice that followed it are two documents, however alike their amounts.
    if a.stage and b.stage and (a.stage in BEFORE_WORK) != (b.stage in BEFORE_WORK):
        return None
    # Two accounts' bills are two documents: SMUD billed 6906859 and 6906880 $77.43 each on October 24, 2024.
    if a.account and b.account and norm_account(a.account) != norm_account(b.account):
        return None
    na, nb = norm_number(a.number), norm_number(b.number)
    if na and nb:
        # A vendor can reuse a number: All Year Pressure Washing printed "1-5MS" on its May 2024 invoice ($1,200) and its
        # September 2024 one ($850). Other amounts a month or more apart are two documents.
        if (na == nb and a.total_cents and b.total_cents and a.total_cents != b.total_cents and a.issued and b.issued
                and abs((a.issued - b.issued).days) > 30):
            return None
        return JoinRule.SAME_NUMBER if na == nb else None
    if a.account and b.account and a.issued and a.issued == b.issued and norm_account(a.account) == norm_account(b.account):
        return JoinRule.SAME_ACCOUNT_DATE
    if (not na and not nb and a.total_cents and a.total_cents == b.total_cents and a.issued and b.issued
            and abs((a.issued - b.issued).days) <= 3):
        return JoinRule.SAME_AMOUNT_DATE
    if a.total_cents and a.total_cents == b.total_cents:
        for dated, letter in ((a, b), (b, a)):
            if (dated.issued and not letter.issued and not norm_number(letter.number) and letter.received
                    and 0 <= (letter.received - dated.issued).days <= ARRIVAL_DAYS):
                return JoinRule.SAME_AMOUNT_ARRIVAL
    return None


@dataclass
class LogicalDocument:
    copies: list[DocumentCopy]
    joins: list[tuple[int, int, JoinRule]] = field(default_factory=list)

    @property
    def issuer(self) -> str:
        return next((c.issuer for c in self.copies if c.issuer), "")

    @property
    def number(self) -> str:
        return next((c.number for c in self.copies if c.number), "")

    @property
    def issued(self) -> date | None:
        return min((c.issued for c in self.copies if c.issued), default=None)

    @property
    def total_cents(self) -> int | None:
        return next((c.total_cents for c in self.copies if c.total_cents), None)

    @property
    def channels(self) -> tuple[Channel, ...]:
        return tuple(dict.fromkeys(c.channel for c in self.copies))

    @property
    def stage(self) -> Stage | None:
        """An invoice when any copy reads as one; else the before-work stage a copy reads as; else the first stage."""
        stages = [c.stage for c in self.copies if c.stage]
        if Stage.INVOICE in stages:
            return Stage.INVOICE
        return next((s for s in stages if s in BEFORE_WORK), stages[0] if stages else None)

    @property
    def before_work(self) -> bool:
        return self.stage in BEFORE_WORK


def group(copies: list[DocumentCopy]) -> list[LogicalDocument]:
    """Join the copies that are one document (union of every pair a rule joins); each join keeps its rule."""
    parent = list(range(len(copies)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    joins: list[tuple[int, int, JoinRule]] = []
    by_issuer: dict[str, list[int]] = {}
    by_hash: dict[str, list[int]] = {}
    for i, c in enumerate(copies):
        by_issuer.setdefault(c.issuer, []).append(i)
        if c.sha256:
            by_hash.setdefault(c.sha256, []).append(i)
    candidates: set[tuple[int, int]] = set()
    for members in by_hash.values():
        candidates.update((members[0], m) for m in members[1:])
    for issuer, members in by_issuer.items():
        if not issuer:
            continue
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                candidates.add((members[x], members[y]))
    # The strongest rules join first, so each recorded join names the best evidence that made it.
    strength = {rule: n for n, rule in enumerate(JoinRule)}
    ruled = [(strength[rule], i, j, rule) for i, j in sorted(candidates) if (rule := join_rule(copies[i], copies[j])) is not None]
    for _n, i, j, rule in sorted(ruled, key=lambda r: r[:3]):
        ri, rj = root(i), root(j)
        if ri != rj:
            parent[rj] = ri
            joins.append((i, j, rule))
    groups: dict[int, LogicalDocument] = {}
    index: dict[int, dict[int, int]] = {}
    for i, c in enumerate(copies):
        r = root(i)
        doc = groups.setdefault(r, LogicalDocument([]))
        index.setdefault(r, {})[i] = len(doc.copies)
        doc.copies.append(c)
    for i, j, rule in joins:
        r = root(i)
        groups[r].joins.append((index[r][i], index[r][j], rule))
    return list(groups.values())


class Fulfilment(Enum):
    SAME_AMOUNT = "same issuer and amount, invoiced on or after the proposal"
    NEAR_AMOUNT = "same issuer, invoiced on or after the proposal within 10% of its amount"


def fulfilments(documents: list[LogicalDocument]) -> dict[int, tuple[int, Fulfilment]]:
    """Each before-work document (by index) linked to the invoice (by index) that followed it: the same issuer, issued
    on or after it within ``FULFIL_DAYS``, the same amount, else within ``NEAR_SHARE``. The nearest invoice after the
    proposal wins, and an invoice fulfils one proposal. A proposal with no such invoice was declined, is still open, or
    was billed in parts; a miss stays a miss."""
    invoices = [(i, d) for i, d in enumerate(documents) if d.stage is Stage.INVOICE and d.issuer and d.issued and d.total_cents]
    taken: set[int] = set()
    out: dict[int, tuple[int, Fulfilment]] = {}
    proposals = sorted(((i, d) for i, d in enumerate(documents) if d.before_work and d.issuer and d.issued and d.total_cents),
                       key=lambda p: p[1].issued)
    for kind in (Fulfilment.SAME_AMOUNT, Fulfilment.NEAR_AMOUNT):
        for i, p in proposals:
            if i in out:
                continue
            fits = [(j, inv) for j, inv in invoices if j not in taken and inv.issuer == p.issuer
                    and 0 <= (inv.issued - p.issued).days <= FULFIL_DAYS
                    and (inv.total_cents == p.total_cents if kind is Fulfilment.SAME_AMOUNT
                         else abs(inv.total_cents - p.total_cents) <= NEAR_SHARE * p.total_cents)]
            if fits:
                j, _inv = min(fits, key=lambda f: f[1].issued)
                taken.add(j)
                out[i] = (j, kind)
    return out


def best(doc: LogicalDocument, priority: tuple[Channel, ...]) -> DocumentCopy:
    """The copy to read: a readable one first, then by channel priority, then the earliest to arrive."""
    rank = {channel: n for n, channel in enumerate(priority)}
    return min(doc.copies, key=lambda c: (not c.readable, rank.get(c.channel, len(rank)), c.received or date.max, c.ref))


__all__ = ["Channel", "JoinRule", "DocumentCopy", "LogicalDocument", "join_rule", "group", "best", "norm_number", "norm_account",
           "Fulfilment", "fulfilments", "BEFORE_WORK"]
