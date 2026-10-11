"""The fee on a records request, read against Civil Code 5205(f) and (g).

What the stored statute says is recited, not paraphrased (``words``): 5205(f) lets the association bill "the direct and
actual cost of copying and mailing" and asks the member to agree to it first; 5205(g) lets it add an amount for the time
"actually and reasonably involved in redacting an enhanced association record", "not in excess of" a dollar rate "per
hour" and "not to exceed" a dollar total "per written request". The two figures are read out of the stored 5205(g)
(``bound``), never written here, so a restated statute changes the check and a shelf that lacks the section leaves no
figure to check against.

``check`` is pure. From a request's own figures it finds what the figures show against those two bounds:

- ``over_cap``: the redaction charge is more than the stated total, or more than the stated hourly rate for the minutes
  recorded. Only these are computable from the figures, and the writer (``records_requests.decide``) refuses them.
- ``warning``: a question jason cannot settle from the figures. The fee is accepted and recorded, and ``needsCounsel``
  says a person reads it: the statute's figures cannot be read, a redaction charge has no time recorded, or the request
  asks for no enhanced association record, or the total is more than the cap with no breakdown to show which part is
  redaction, or the parts do not add to the total. Copying and mailing carry no figure in the statute ("direct and
  actual"), so jason never checks that part against a number.
- ``ok``: nothing billed, or the figures sit within the bounds.

jason's reading is labeled as jason's (``reading``). It does not decide whether a redaction's time was "actually and
reasonably" spent, whether a record is an enhanced association record, or whether the member agreed first: a person does.
Amounts are integer cents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

COPY = "CIV 5205(f)"
REDACTION = "CIV 5205(g)"
ENHANCED = "CIV 5200(b)"
MEMBERSHIP_LIST = "CIV 5210(b)(6)"
MEMBERSHIP_LIST_LAW = "CORP 8330"

READING = "jason's reading, not the statute's: "


def words(citation: str) -> dict[str, Any]:
    """The stored statute's words for ``citation``: ``{citation, text, found, inForce}``. A shelf that lacks it, or cannot be
    read, answers ``found: False`` and no words. Nothing is kept between calls: the shelf's reader keeps its own index."""
    try:
        from jason.tasks.cite import resolve

        got = resolve(citation, text=True)
    except Exception as exc:  # noqa: BLE001 - an unreadable shelf is a miss, not a failed screen
        got = {"found": False, "reason": type(exc).__name__}
    return {"citation": citation, "text": str(got.get("text") or "") if got.get("found") else "", "found": bool(got.get("found")),
            "inForce": str(got.get("inForce") or ""), "reason": str(got.get("reason") or "")}


@dataclass(frozen=True)
class Bound:
    """The figures 5205(g) states, in cents, read from its stored words; ``None`` for one the words do not state."""

    hourly_cents: int | None
    cap_cents: int | None
    text: str = ""

    @property
    def stated(self) -> bool:
        return self.hourly_cents is not None or self.cap_cents is not None


def _dollars(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1).replace(",", "")) * 100 if m else None


def parse_bound(text: str) -> Bound:
    """The hourly rate and the total out of 5205(g)'s words: ``($10) per hour`` and ``($200) total``. A figure the words
    do not give in that form stays ``None``."""
    flat = " ".join(str(text or "").split())
    return Bound(hourly_cents=_dollars(flat, r"\(\$([\d,]+)\)\s+per hour"),
                 cap_cents=_dollars(flat, r"\(\$([\d,]+)\)\s+total per written request"), text=flat)


def bound() -> Bound:
    """The bounds in the stored 5205(g); none stated when the shelf lacks it."""
    return parse_bound(words(REDACTION)["text"])


def _usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def check(fee_cents: int, copy_cents: int = 0, redaction_cents: int = 0, redaction_minutes: int = 0, *,
          enhanced: bool = True, limits: Bound | None = None) -> dict[str, Any]:
    """The fee against 5205(f) and (g): ``{status: ok|warning|over_cap, needsCounsel, findings: [{code, sentence}], words,
    capCents, hourlyCents, reading}``. ``fee_cents`` is the total the member agreed to; ``copy_cents`` and
    ``redaction_cents`` its parts when a person recorded them; ``redaction_minutes`` the time recorded for the redaction;
    ``enhanced`` whether the request asks for an enhanced association record (5200(b)). ``limits`` stands in for the
    stored statute's figures (a test)."""
    fee, copy_c, red, mins = int(fee_cents or 0), int(copy_cents or 0), int(redaction_cents or 0), int(redaction_minutes or 0)
    recited = [words(c) for c in (COPY, REDACTION, ENHANCED)]
    lim = limits if limits is not None else parse_bound(next((w["text"] for w in recited if w["citation"] == REDACTION), ""))
    findings: list[dict[str, str]] = []
    over = False

    def say(code: str, sentence: str, *, is_over: bool = False) -> None:
        nonlocal over
        findings.append({"code": code, "sentence": sentence})
        over = over or is_over

    parts = copy_c + red
    if fee or parts:
        if not lim.stated:
            say("statute-unread", "The stored text of CIV 5205(g) is not on this shelf, or states no figure jason can read, so the "
                "fee cannot be checked against it. Counsel reads the statute.")
        else:
            if red and lim.cap_cents is not None and red > lim.cap_cents:
                say("over-total", f"The redaction charge, {_usd(red)}, is more than the {_usd(lim.cap_cents)} total the stored "
                    f"CIV 5205(g) states per written request.", is_over=True)
            if red and mins and lim.hourly_cents is not None and red * 60 > mins * lim.hourly_cents:
                say("over-rate", f"The redaction charge, {_usd(red)} for {mins} minute(s), is more than the {_usd(lim.hourly_cents)} per "
                    "hour the stored CIV 5205(g) states.", is_over=True)
            if red and not mins:
                say("no-time", "A redaction charge is recorded with no time, so the hourly rate in CIV 5205(g) cannot be checked.")
            if red and not enhanced:
                say("not-enhanced", "A redaction charge is recorded, and the request asks for no enhanced association record "
                    "(CIV 5200(b)); CIV 5205(g) speaks of redacting an enhanced association record.")
            if parts and fee != parts:
                say("parts-differ", f"The total, {_usd(fee)}, is not the copying and mailing plus the redaction, {_usd(parts)}.")
            if not parts and enhanced and lim.cap_cents is not None and fee > lim.cap_cents:
                say("no-breakdown", f"The total, {_usd(fee)}, is more than the {_usd(lim.cap_cents)} the stored CIV 5205(g) states "
                    "for redaction alone, and no breakdown shows how much of it is copying and mailing, which carries no figure in "
                    "CIV 5205(f).")
    status = "over_cap" if over else ("warning" if findings else "ok")
    return {"status": status, "needsCounsel": status != "ok", "findings": findings,
            "capCents": lim.cap_cents, "hourlyCents": lim.hourly_cents,
            "words": [{"citation": w["citation"], "text": w["text"], "found": w["found"], "inForce": w["inForce"]} for w in recited],
            "reading": READING + ("the figures sit within what the stored statute states, and a person still decides whether the "
                                  "time was actually and reasonably spent and whether the member agreed first."
                                  if status == "ok" else
                                  "the findings above are jason's comparison of the request's own figures with the stored words; "
                                  "counsel reads the statute.")}


def refusal(result: dict[str, Any]) -> str:
    """The sentence a writer refuses an ``over_cap`` fee with: jason's finding, then the statute's own words."""
    said = " ".join(f["sentence"] for f in result["findings"])
    quoted = next((w["text"] for w in result["words"] if w["citation"] == REDACTION and w["text"]), "")
    return f"{said} {REDACTION} reads: \"{' '.join(quoted.split())}\"" if quoted else said


def rule() -> dict[str, Any]:
    """The words beside the fee field and the membership-list clock, for the loader: 5205(f), 5205(g), and the limits read
    from them; 5200(b); and the membership list's 5210(b)(6) with the law it points to, which stays with counsel."""
    limits = bound()
    return {"fee": {"words": [words(c) for c in (COPY, REDACTION, ENHANCED)], "capCents": limits.cap_cents, "hourlyCents": limits.hourly_cents,
                    "reading": READING + "5205(g) bounds only the redaction charge; copying and mailing are \"direct and actual\" "
                    "with no figure. The page lowers no figure."},
            "membershipList": {"words": [words(c) for c in (MEMBERSHIP_LIST, MEMBERSHIP_LIST_LAW)],
                               "reading": READING + "the date on the clock is jason's count of five business days from the day "
                               "received, computed for a person to check. The timeframe is the one the second section states, which "
                               "counsel reads."}}


__all__ = ["Bound", "COPY", "ENHANCED", "MEMBERSHIP_LIST", "REDACTION", "READING", "bound", "check", "parse_bound",
           "refusal", "rule", "words"]
