"""How each owner-information response is handled: a policy of rules, applied in order, each with its outcome.

An answer can be complete and still not be something to write: it can speak for co-owners, give a co-owner's email
as a "second" address, report a rental the unit's tag does not, or leave the owner's mail going to a tenant. ``triage``
reads each response against the unit and its people as PayHOA has them now and gives every finding an ``Outcome``:

- **record**: jason writes it (``owner-info --apply``), under the cycle's rules (never over newer information);
- **person**: a person enters or removes something in PayHOA (an email, a mailing address, a record);
- **confirm**: ask the owner before relying on it;
- **board**: a question of policy, noted for the board, not acted on (the first cycle's open questions);
- **ignore**: not an owner's answer (a test account's).

The rules are rows (``RULES``); a new kind of surprise is a new row, not a branch in a task. Board questions go to the
board's working canvas (``mystique/notes/canvas``, private) and its action register, never to an owner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class Outcome(Enum):
    RECORD = "record"
    PERSON = "person"
    CONFIRM = "confirm"
    BOARD = "board"
    IGNORE = "ignore"


@dataclass
class Context:
    """One response with what PayHOA holds about its unit and people now."""
    submission: int
    unit: str
    unit_id: int
    membership_id: int
    answers: dict[str, Any]
    owners: list[dict[str, Any]]           # the unit's owner records (people rows), the answerer included
    records: list[dict[str, Any]]          # every person row on the unit (owners, additional deliveries, contacts)
    unit_tags: set[str]
    tags: Any                              # the specification's PayhoaTags
    tests: set[int]
    problems: list[str] = field(default_factory=list)   # the form's own check

    @property
    def me(self) -> dict[str, Any]:
        return next((p for p in self.records if int(p.get("id") or 0) == self.membership_id), {})


@dataclass(frozen=True)
class Finding:
    rule: str
    outcome: Outcome
    text: str
    board_item: str = ""                   # the action item a board question belongs to, if any


@dataclass(frozen=True)
class Rule:
    key: str
    outcome: Outcome
    why: str
    test: Callable[[Context], str]         # the finding's text when the rule applies, else ""
    stops: bool = False                    # no later rule applies (a test account's answer)
    board_item: str = ""


ALL_OWNERS = "All owners of this unit"
SAME_AS_UNIT = "Same as my unit address"
AWAY = ("Rented out", "Vacant (not occupied)")


def _norm(text: Any) -> str:
    from jason.community.postal import normalize_address

    return normalize_address(str(text or ""))


def _occupancy_tag(c: Context) -> str:
    from jason.community.tags import TagPurpose, TagScope, tagged

    found = tagged(c.tags, c.unit_tags, TagPurpose.OCCUPANCY, TagScope.UNIT)
    return found[0].value if found else ""


def _purpose_records(c: Context, purpose_name: str) -> list[dict[str, Any]]:
    from jason.community.tags import TagPurpose, TagScope, tag_names, tagged

    purpose = TagPurpose(purpose_name)
    return [p for p in c.records if tagged(c.tags, tag_names(p), purpose, TagScope.MEMBER)]


def _first(value: Any) -> str:
    return str(value[0] if isinstance(value, (list, tuple)) and value else value or "")


def _test_account(c: Context) -> str:
    return "a test account's submission, not an owner's" if c.membership_id in c.tests else ""


def _not_an_owner(c: Context) -> str:
    owners = {int(p.get("id") or 0) for p in c.owners}
    return "" if c.membership_id in owners else "the answer came from a member who is not an owner of this unit"


def _required_blank(c: Context) -> str:
    blank = [p for p in c.problems if "required" in p]
    return ("required answers left blank (" + "; ".join(blank) + "): noted, not asked, this cycle") if blank else ""


def _for_co_owners(c: Context) -> str:
    others = [p for p in c.owners if int(p.get("id") or 0) != c.membership_id]
    if _first(c.answers.get("answering-for")) != ALL_OWNERS or not others:
        return ""
    return (f"answers for all owners, and the unit has {len(others)} other owner record(s) of its own: recorded for "
            "the answerer; whether one owner's election (email delivery above all) binds a co-owner is the board's "
            "question (Civil Code 4041 asks each owner)")


def _second_is_co_owner(c: Context) -> str:
    second = str(c.answers.get("second-email") or "").strip().lower()
    if not second:
        return ""
    others = [p for p in c.records if int(p.get("id") or 0) != c.membership_id]
    if any(str(p.get("email") or "").lower() == second for p in others):
        return "the second email is a co-owner's own PayHOA email: their own preference, not a second delivery"
    local = "".join(ch for ch in second.split("@")[0] if ch.isalpha())
    for p in others:
        prof = p.get("profile") or {}
        given = "".join(ch for ch in str(prof.get("givenNames") or "").split(" ")[0].lower() if ch.isalpha())
        family = "".join(ch for ch in str(prof.get("familyName") or "").lower() if ch.isalpha())
        if given and family and given in local and family in local:
            has = "their record has none" if not p.get("email") else "their record has another"
            return (f"the second email looks like co-owner {given.title()} {family.title()}'s own ({has}): their own "
                    "email and preference, not a second delivery for this owner")
    return ""


def _occupancy_vs_tag(c: Context) -> str:
    said, tag = _first(c.answers.get("occupancy")), _occupancy_tag(c)
    if not said or said == tag:
        return ""
    return f"says {said.lower()}; the unit is tagged {tag or 'nothing'}"


def _rented_mail_at_unit(c: Context) -> str:
    said = _first(c.answers.get("occupancy"))
    if said not in AWAY:
        return ""
    given = str(c.answers.get("mailing-address") or "")
    profile = str((c.me.get("profile") or {}).get("address1") or "")
    at_unit = given == SAME_AS_UNIT or (given and _norm(given).startswith(_norm(c.unit)))
    profile_unit = not profile or _norm(profile).startswith(_norm(c.unit))
    if at_unit or (not given and profile_unit):
        return f"{said.lower()}, yet the owner's mail would go to the unit: ask for a mailing address"
    return ""


def _unconfirmed_record(c: Context) -> str:
    found = _purpose_records(c, "unconfirmed")
    return (f"the unit has {len(found)} Unconfirmed Address record(s), made for this notice only: the owner answered, "
            "so remove them") if found else ""


def _email_differs(c: Context) -> str:
    given = str(c.answers.get("email") or "").strip().lower()
    on_file = str(c.me.get("email") or "").lower()
    return f"the email given differs from PayHOA's ({on_file or 'none'})" if given and given != on_file else ""


def _mailing_elsewhere(c: Context) -> str:
    given = str(c.answers.get("mailing-address") or "")
    if not given or given == SAME_AS_UNIT or _norm(given).startswith(_norm(c.unit)):
        return ""
    return "a mailing address other than the unit: compare with PayHOA's profile and enter it"


def _delivery(c: Context) -> str:
    chosen = c.answers.get("delivery") or []
    return ("delivery " + " and ".join(str(d).replace("By ", "") for d in chosen) + ", and the cycle's tags") if chosen else ""


RULES: tuple[Rule, ...] = (
    Rule("test-account", Outcome.IGNORE, "A test account's answer is never an owner's.", _test_account, stops=True),
    Rule("not-an-owner", Outcome.PERSON, "Only an owner of the unit answers for it.", _not_an_owner),
    Rule("required-blank", Outcome.BOARD, "Paper cannot require an answer; the first cycle notes blanks for the board "
         "rather than asking.", _required_blank, board_item="rental-approvals-4-15"),
    Rule("for-co-owners", Outcome.BOARD, "4041 asks each owner; whether a co-owner's answer elects for the others "
         "(email above all, which needs consent) is policy.", _for_co_owners),
    Rule("second-is-co-owner", Outcome.CONFIRM, "A co-owner's own email is their own delivery choice, not a second "
         "address for this owner.", _second_is_co_owner),
    Rule("occupancy-vs-tag", Outcome.BOARD, "An occupancy the unit's tag does not show touches rental approvals.",
         _occupancy_vs_tag, board_item="rental-approvals-4-15"),
    Rule("rented-mail-at-unit", Outcome.CONFIRM, "An owner who does not live in the unit should not get notices "
         "there.", _rented_mail_at_unit),
    Rule("unconfirmed-record", Outcome.PERSON, "An Unconfirmed Address record exists only until the owner answers.",
         _unconfirmed_record),
    Rule("email-differs", Outcome.PERSON, "An email is entered by a person (the merge rule).", _email_differs),
    Rule("mailing-elsewhere", Outcome.PERSON, "A mailing address is entered by a person.", _mailing_elsewhere),
    Rule("delivery", Outcome.RECORD, "A signed-in delivery choice sets the delivery tags.", _delivery),
)


def triage(c: Context, rules: tuple[Rule, ...] = RULES) -> list[Finding]:
    """Every rule's finding for one response, in the rules' order."""
    out: list[Finding] = []
    for rule in rules:
        text = rule.test(c)
        if text:
            out.append(Finding(rule.key, rule.outcome, text, rule.board_item))
            if rule.stops:
                break
    return out


def contexts(client: Any, org_id: int, data_dir: Any, community: Any, forms: Any,
             live: tuple[list[dict[str, Any]], list[dict[str, Any]]] | None = None) -> list[Context]:
    """Every PayHOA response to the owner-information form, read live with its unit and people. ``live`` is the units
    and people a plan already read (``owner_info_apply.plan_apply``), so they are not read again."""
    from pathlib import Path

    from jason.community.forms import check
    from jason.tasks.owner_info_apply import live_read as _live
    from jason.community.tags import tag_names
    from jason.config import test_memberships
    from jason.tasks.payhoa_forms import fetch_submissions, record_for

    record = record_for(Path(data_dir), forms.OWNER_INFO.key.value)
    if record is None:
        return []
    units, people = live if live is not None else _live(client, org_id)
    by_id = {int(p["id"]): p for p in people}
    units_by_id = {int(u["id"]): u for u in units}
    tests = test_memberships()
    out = []
    for s in fetch_submissions(client, org_id, record, forms.OWNER_INFO):
        unit = units_by_id.get(int(s.unit_id or 0), {})
        owner_ids = [int(o["membershipId"]) for o in unit.get("owners") or [] if not o.get("deletedAt")]
        records = [by_id[i] for i in owner_ids if i in by_id]
        out.append(Context(int(str(s.source).split(":")[1]), str(unit.get("title") or s.answers.get("unit-address") or ""),
                           int(s.unit_id or 0), int(s.membership_id or 0), dict(s.answers),
                           [p for p in records if not _secondary(p, community)], records, tag_names(unit),
                           community.payhoa_tags(), tests, check(forms.OWNER_INFO, s.answers)))
    return out


def _secondary(person: dict[str, Any], community: Any) -> bool:
    """A record kept for an owner (additional deliveries, a representative, a manager), not an owner of title."""
    from jason.community.tags import owner_of_title, tag_names

    return not owner_of_title(tuple(community.payhoa_tags()), tag_names(person))


def report(found: list[tuple[Context, list[Finding]]]) -> list[str]:
    """The responses as Markdown: one section per outcome, then each response with its findings."""
    out = []
    for outcome in (Outcome.BOARD, Outcome.CONFIRM, Outcome.PERSON, Outcome.RECORD, Outcome.IGNORE):
        rows = [(c, f) for c, fs in found for f in fs if f.outcome is outcome]
        if not rows:
            continue
        out += [f"## {outcome.value.capitalize()} ({len(rows)})", ""]
        out += [f"- **{c.unit.title()}** (request {c.submission}): {f.text}"
                + (f" [board item {f.board_item}]" if f.board_item else "") for c, f in rows]
        out.append("")
    return out


__all__ = ["Context", "Finding", "Outcome", "RULES", "Rule", "contexts", "report", "triage"]
