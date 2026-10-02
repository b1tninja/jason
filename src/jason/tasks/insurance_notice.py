"""The Civil Code 5810 notice of a change in the association's insurance, generated from the policy records.

Section 5810 requires individual notice to every member, as soon as reasonably practicable, when a policy described in
the annual budget report (5300(b)(9)) has lapsed or been canceled and is not immediately renewed, restored, or
replaced, or when there is a significant change, "such as a reduction in coverage or limits or an increase in the
deductible". This module compares each such policy's term in force with the term before it (the records `jason
policies` reads from the declarations) and gives the base template `insurance-change-notice.html` its values. It
decides nothing: whether a change is significant beyond those named, and when to send, are the board's.

A past notice that was sent stays as it was; this generates the next one (docs/base-templates.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

from jason.tasks.packets import SUMMARY_LIMITS, long_date, money


# What a policy record says when coverage ended without a renewal; a term merely missing from the records is a gap.
LAPSE_STATUSES = ("canceled", "cancelled", "nonrenewed", "non-renewed", "lapsed")


class ChangeKind(Enum):
    LAPSED = "lapsed with no renewal on file"
    LIMIT_REDUCED = "limit reduced"
    DEDUCTIBLE_INCREASED = "deductible increased"
    LIMIT_INCREASED = "limit increased"
    DEDUCTIBLE_DECREASED = "deductible decreased"
    CARRIER_CHANGED = "insurer changed"
    NEW_POLICY = "new policy"

    @property
    def significant(self) -> bool:
        """The changes 5810 names: a lapse not replaced, a reduction in limits, an increase in the deductible."""
        return self in (ChangeKind.LAPSED, ChangeKind.LIMIT_REDUCED, ChangeKind.DEDUCTIBLE_INCREASED)


@dataclass(frozen=True)
class Change:
    policy: str
    kind: ChangeKind
    sentence: str


def _label(policy: dict[str, Any]) -> str:
    kinds = SUMMARY_LIMITS.get(str(policy.get("kind"))) or ()
    label = kinds[0][0] if kinds else str(policy.get("key") or "policy")
    if policy.get("kind") == "flood" and policy.get("building"):
        label = f"Flood (Building {policy['building']})"
    return label


def _terms(policy: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(policy.get("terms") or [], key=lambda t: str(t.get("start") or ""))


def current_and_prior(policy: dict[str, Any], on: date) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The term in force on ``on`` (else the next one already issued) and the term before it."""
    terms = _terms(policy)
    day = on.isoformat()
    for i, term in enumerate(terms):
        if str(term.get("start") or "") <= day < str(term.get("end") or ""):
            later = [t for t in terms[i + 1:] if str(t.get("start") or "") > day]
            if later:                                   # renewed ahead of time: the renewal is the one to report
                return later[0], term
            return term, terms[i - 1] if i else None
    upcoming = [t for t in terms if str(t.get("start") or "") > day]
    if upcoming:
        return upcoming[0], (terms[terms.index(upcoming[0]) - 1] if terms.index(upcoming[0]) else None)
    return None, terms[-1] if terms else None


def policy_changes(policies: list[dict[str, Any]], on: date) -> tuple[list[Change], list[str]]:
    """Each annual-budget-report policy's changes from its prior term, as of ``on``; gaps where a term is missing."""
    changes: list[Change] = []
    gaps: list[str] = []
    for policy in policies:
        kinds = SUMMARY_LIMITS.get(str(policy.get("kind")))
        if not kinds:
            continue
        label = _label(policy)
        term, prior = current_and_prior(policy, on)
        if term is None:
            # A term missing from the records is not a lapse: the renewal may simply not have been read yet. Only a
            # record that says the policy was canceled or not renewed is reported as one.
            status = str(policy.get("status") or "").casefold()
            if prior is not None and status in LAPSE_STATUSES:
                changes.append(Change(label, ChangeKind.LAPSED,
                                      f"{label}: {status} effective {long_date(prior.get('end'))}; no replacement is on file."))
            elif prior is not None:
                gaps.append(f"insurance notice: {label}'s term on file ended {prior.get('end')}; read the renewed "
                            "declarations (jason policies) before this notice is generated")
            else:
                gaps.append(f"insurance notice: {label} has no term on file")
            continue
        if prior is None:
            changes.append(Change(label, ChangeKind.NEW_POLICY, f"{label}: a new policy, {_span(term)}."))
            continue
        carrier, before = str(term.get("carrier") or ""), str(prior.get("carrier") or "")
        if carrier and before and carrier.casefold() != before.casefold():
            changes.append(Change(label, ChangeKind.CARRIER_CHANGED, f"{label}: now insured by {carrier} (was {before})."))
        for name, key in kinds:
            new, old = (term.get("limits") or {}).get(key), (prior.get("limits") or {}).get(key)
            if isinstance(new, (int, float)) and isinstance(old, (int, float)) and new != old:
                kind = ChangeKind.LIMIT_REDUCED if new < old else ChangeKind.LIMIT_INCREASED
                what = name if len(kinds) > 1 else "limit"
                verb = "reduced" if new < old else "raised"
                changes.append(Change(label, kind, f"{label}: {what} {verb} from {money(old)} to {money(new)}."))
        new, old = term.get("deductible"), prior.get("deductible")
        if isinstance(new, (int, float)) and isinstance(old, (int, float)) and new != old:
            kind = ChangeKind.DEDUCTIBLE_INCREASED if new > old else ChangeKind.DEDUCTIBLE_DECREASED
            verb = "raised" if new > old else "lowered"
            changes.append(Change(label, kind, f"{label}: deductible {verb} from {money(old)} to {money(new)}."))
    changes.sort(key=lambda c: (not c.kind.significant, c.policy))
    return changes, gaps


def _span(term: dict[str, Any]) -> str:
    return f"{long_date(term.get('start'))} through {long_date(term.get('end'))}"


def policy_lines(policies: list[dict[str, Any]], on: date) -> list[str]:
    """One line per policy as it stands: insurer, number, term, limit, and deductible."""
    lines = []
    for policy in policies:
        kinds = SUMMARY_LIMITS.get(str(policy.get("kind")))
        if not kinds:
            continue
        term, _ = current_and_prior(policy, on)
        if term is None:
            continue
        limits = term.get("limits") or {}
        shown = "; ".join(f"{name} {money(limits.get(key))}" for name, key in kinds if limits.get(key))
        carrier = str(term.get("carrier") or policy.get("carrier") or "")
        number = str(term.get("number") or "")
        deductible = term.get("deductible")
        lines.append(f"{_label(policy)}: {carrier}{', ' + number if number else ''}, {_span(term)}"
                     + (f"; {shown}" if shown else "")
                     + (f"; deductible {money(deductible)}" if isinstance(deductible, (int, float)) and deductible else "")
                     + ".")
    return lines


def notice_values(policies: list[dict[str, Any]], community: Any, *, on: date | None = None) -> tuple[dict[str, str], list[str]]:
    """The tokens of ``insurance-change-notice.html`` as of ``on``, and the gaps. When nothing on file is a change
    5810 names, the gaps say so: the board decides whether a notice is still worth sending."""
    on = on or date.today()
    changes, gaps = policy_changes(policies, on)
    significant = [c for c in changes if c.kind.significant]
    if significant:
        reason = ("This notice is sent under Civil Code section 5810 because of the following change"
                  + ("s" if len(significant) > 1 else "") + " in the Association's insurance.")
    else:
        reason = "This notice describes the Association's insurance as it now stands."
        gaps.append("insurance notice: no lapse, reduced limit, or higher deductible is on file; Civil Code 5810 "
                    "does not require this notice for the other changes")
    master = next((p for p in policies if p.get("kind") == "master"), None)
    master_term = current_and_prior(master, on)[0] if master else None
    not_carried = tuple(getattr(community, "coverages_not_carried", lambda: ())() or ())
    values = {
        "NOTICE_REASON": reason,
        "CHANGES_LIST": "\n".join(c.sentence for c in changes) or "No change from the prior terms is on file.",
        "POLICY_LIST": "\n".join(policy_lines(policies, on)
                                 + [f"{coverage.capitalize()}: the Association does not carry {coverage} insurance."
                                    for coverage in not_carried]),
        "MASTER_DEDUCTIBLE": money((master_term or {}).get("deductible")) if master_term else "",
    }
    return {k: v for k, v in values.items() if v and v != "—"}, gaps
