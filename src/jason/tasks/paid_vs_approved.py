"""What the board approved against what the association paid: each approval in the minutes followed to its payments.

An approval is a decision the minutes record with a dollar amount (``data/documents/readings.json``, library and Drive
minutes): the meeting's date, the amount, its words, and any proposal or estimate number they cite. A payment is one
the invoice review read (``data/payhoa/invoice-review.json``): its date, amount, payee, its invoices' numbers, and the
proposal, estimate, purchase order, or contract its invoice cites (``InvoiceRecord.reference``).

A payment answers an approval when its invoice cites the approval's proposal number (the strong link), or when the
approval's words name the payee and the payment falls within nine months after the meeting. The payments are summed
against the approved amount. The leads, each with its evidence:

- **paid more than approved**: more than 5% over (a change order the minutes may not show);
- **approved, nothing paid yet**: no payment found (the work may be pending, or paid under another name);
- **paid without an approval**: a one-off payment of $5,000 or more to a vendor the association does not pay monthly,
  that no approval in the read minutes accounts for (the minutes of that time may not be read).

An approval about insurance (``Community.premium_rules()``: "insurance", "premium", "umbrella", "D&O", "crime",
"flood"; "renewal", "policy", "package" only when nothing else links it) is followed to premiums instead: payments whose
payee or bank line names an insurer, program, agent, or premium finance company (the policies' carriers, programs, and
agents, the insurer senders, and the rules' payees), or whose PayHOA category is a policy's premium category or another
insurance category, paid from 60 days before the meeting to 300 days after. Installments are summed. The coverages are
the ones the words name; an approval that names none ("a $29,137 insurance renewal") is the package (master, umbrella,
D&O, crime), since each flood policy renews on its own date. A payment split across categories counts each split row
toward its own coverage.

The ``insurance`` section puts each policy term beside its money: the premium per the declarations the document models
read (``readings.json`` kind ``insurance_policy``), else the board's policy sheet (``data/insurance/sheet.json``); the
approvals that bought it; what was paid, to whom, in how many installments. A flood payment is placed on a building by
the NFIP number or building its line or files name, else by a premium amount only one building's terms carry.

A link is a rule's reading; whether a payment was authorized is the board's to say.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

OUT = Path("meetings") / "paid-vs-approved.json"
WINDOW_DAYS = 270
MIN_APPROVAL = 50_000             # $500: smaller approvals (a bulb, a key box) are not followed
LARGE_PAYMENT = 500_000           # $5,000
OVER = 1.05
_GENERIC = {"inc", "llc", "company", "co", "corp", "the", "and", "services", "service", "group", "construction", "control",
            "pest", "roofing", "landscape", "landscaping", "plumbing", "electric", "association", "community", "mystique",
            "insurance", "solutions", "systems", "repair", "repairs", "pro", "active", "city", "county", "sacramento",
            "california", "builder", "window", "gutter", "door", "doors", "wildlife", "tree", "trees"}
_PROPOSAL_NO = re.compile(r"\b(?:Proposal|Estimate|Quote|Contract|P\.?O\.?|Work Order)\s*(?:#|No\.?|Number)?\s*:?\s*"
                          r"((?=[A-Z0-9-]*\d)[A-Z]{0,4}-?\d[\w-]{1,})\b", re.I)


_NOT_SPENDING = re.compile(r"\binvest|\bcertificate of deposit\b|\bCD\b|\bborrow|\bloan\b|reserve (?:account|funds?) to|"
                           r"\bforeclos|\bdelinquen|\bbalance\b|\bowed\b|\bowes\b|\bfine\b|\bpayment plan\b|\bassessment\b|"
                           r"\bbudget of\b|\bannual budget\b|\bdeductible\b|operating account|too expensive|might consider|decided against|"
                           r"\bdeclined\b|\brejected\b", re.I)


def _item_context(items: list[dict[str, Any]], sentence: str) -> str:
    """The title, notes, and attachment names of the minutes item whose words hold the sentence, "Estimate - 000865.pdf"
    read as "Estimate 000865"; empty when no item holds it."""
    probe = re.sub(r"\s+", " ", sentence)[:40].lower()
    stack = list(items)
    while stack:
        item = stack.pop(0)
        stack.extend(item.get("subitems") or [])
        parts = [str(item.get("title") or ""), str(item.get("notes") or ""), *map(str, item.get("attachments") or [])]
        blob = re.sub(r"\s+", " ", " ".join(parts))
        if probe and probe in blob.lower():
            return re.sub(r"\s*-\s*(?=\d)", " ", blob)
    return ""


def _day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _key_words(payee: str) -> set[str]:
    # Five letters or more: "fire" in a sentence about a fire hazard is not The Fire Sprinkler Company.
    return {w for w in re.findall(r"[a-z0-9]{5,}", (payee or "").lower()) if w not in _GENERIC}


def approvals(data_dir: Path) -> list[dict[str, Any]]:
    store = json.loads((Path(data_dir) / "documents" / "readings.json").read_text(encoding="utf-8")).get("readings", [])
    out = []
    for r in store:
        if r.get("kind") != "minutes" or r.get("confidential"):
            continue
        fields = r.get("fields") or {}
        day = _day(fields.get("meeting_date") or r.get("period"))
        for a in fields.get("actions") or []:
            amount = a.get("amount")
            text = str(a.get("text") or "")
            cited = {m.group(1).upper() for m in _PROPOSAL_NO.finditer(text)}
            context = ""
            if not cited and not amount:
                # "The board accepted the proposal" names neither vendor nor number; the item it sits under attaches the
                # estimate ("HighClass Gutter and Glass ... Estimate - 000865.pdf"), which names both.
                context = _item_context(fields.get("items") or [], text)
                cited = {m.group(1).upper() for m in _PROPOSAL_NO.finditer(context)}
            # An approval with no dollar figure is followed when it, or its item, cites a proposal or estimate.
            if day is None or a.get("outcome") != "approved" or ((not amount or amount < MIN_APPROVAL) and not cited):
                continue
            if _NOT_SPENDING.search(text):
                continue                      # an investment, a reserve loan, a delinquency, a fine: no vendor is paid
            out.append({"date": day.isoformat(), "amountCents": int(amount or 0), "text": text[:400], "minutes": r.get("name"),
                        "proposals": sorted(cited), "context": context[:4000]})
    # The model's grounded answer to "each dollar amount the board approved" (jason models --ask --kind minutes): the rules
    # miss an amount stated in another sentence than the approval ("approves the tree pruning plan" ... "$9,871").
    asked = Path(data_dir) / "documents" / "questions-minutes.json"
    days = {r["id"]: _day((r.get("fields") or {}).get("meeting_date") or r.get("period")) for r in store if r.get("kind") == "minutes"}
    if asked.is_file():
        for f in json.loads(asked.read_text(encoding="utf-8")).get("files", []):
            day = days.get(f["id"])
            if day is None or f.get("confidential"):
                continue
            for ans in f.get("answers", []):
                if ans.get("key") != "amounts_approved" or ans.get("verdict") in ("ungrounded", "gap"):
                    continue
                for entry in ans.get("model") or []:
                    m = re.search(r"\$\s?([\d,]+(?:\.\d\d)?)", str(entry))
                    if not m or _NOT_SPENDING.search(str(entry)):
                        continue
                    cents_ = round(float(m.group(1).replace(",", "")) * 100)
                    if cents_ >= MIN_APPROVAL:
                        out.append({"date": day.isoformat(), "amountCents": cents_, "text": f"(model) {entry}", "minutes": f.get("name"),
                                    "proposals": sorted({p.group(1).upper() for p in _PROPOSAL_NO.finditer(str(entry))})})
    # One decision retold in two copies of the same minutes is one approval.
    seen, unique = set(), []
    for a in sorted(out, key=lambda a: (a["date"], a["amountCents"])):
        k = (a["date"], a["amountCents"] or a["text"][:40])
        if k not in seen:
            seen.add(k)
            unique.append(a)
    return unique


def payments(data_dir: Path) -> list[dict[str, Any]]:
    """The reviewed payments with the references their invoices cite (read from the cached attachment text)."""
    review = json.loads((Path(data_dir) / "payhoa" / "invoice-review.json").read_text(encoding="utf-8"))
    root = Path(data_dir) / "payhoa" / "attachments"
    texts = Path(data_dir) / "payhoa" / "attachment-text"
    by_name: dict[str, Path] = {p.name: p for p in root.rglob("*") if p.is_file()} if root.is_dir() else {}
    out = []
    import hashlib

    for p in review.get("payments", []):
        refs: set[str] = set()
        numbers = []
        for d in p.get("documents") or []:
            inv = d.get("invoice") or {}
            if inv.get("number"):
                numbers.append(str(inv["number"]))
            path = by_name.get(d.get("filename", ""))
            if path is not None:
                cache = texts / f"{hashlib.sha256(path.read_bytes()).hexdigest()}.txt"
                if cache.is_file():
                    refs |= {m.group(1).upper() for m in _PROPOSAL_NO.finditer(cache.read_text(encoding="utf-8", errors="ignore"))}
        out.append({"key": p.get("key"), "date": p.get("date"), "amountCents": int(p.get("amountCents") or 0), "payee": p.get("payee") or "",
                    "utility": bool(p.get("utility")), "categories": p.get("categories") or [], "invoices": numbers,
                    "references": sorted(refs), "description": str(p.get("description") or ""),
                    "filenames": sorted({str(d.get("filename") or "") for d in p.get("documents") or []} - {""})})
    return out


def _splits(data_dir: Path) -> dict[Any, list[tuple[str, int]]]:
    """Each payment's split rows as (category, cents), from the PayHOA snapshot (one parent, several category rows)."""
    path = Path(data_dir) / "payhoa" / "transactions.json"
    if not path.is_file():
        return {}
    snap = json.loads(path.read_text(encoding="utf-8"))
    names = {int(k): v.get("name", "") for k, v in snap.get("categories", {}).items()}
    out: dict[Any, list[tuple[str, int]]] = defaultdict(list)
    for tx in snap.get("transactions", []):
        if tx.get("deletedAt"):
            continue
        out[int(tx.get("parentId") or tx["id"])].append((names.get(int(tx.get("categoryId") or 0), ""), int(tx.get("amount") or 0)))
    return dict(out)


# --- Insurance premiums -------------------------------------------------------------------------------------------


def _fold(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


def _premium_parties(community: Any, rules: Any) -> list[tuple[str, str, Any]]:
    """(folded words, display name, the coverage it implies or None): who a premium is paid to."""
    out: list[tuple[str, str, Any]] = []
    from jason.community.symbols import PolicyKind

    for s in rules.payees:
        kind = PolicyKind.FLOOD if "NFIP" in s.role.upper() else None
        out.extend((_fold(w), s.name, kind) for w in s.words)
    for pol in community.insurance().policies:
        # A carrier or program names its own coverage; the agent places every policy, so it implies none.
        for name in (pol.carrier, pol.program):
            if name:
                out.append((_fold(re.sub(r"\(.*?\)", "", name)), name, pol.kind))
        if pol.agent:
            out.append((_fold(pol.agent), pol.agent, None))
    from jason.community.sources import SourceKind

    for s in community.senders():
        if s.kind is SourceKind.INSURER and "claim" not in s.role:
            out.extend((_fold(w), s.name, None) for w in (*s.words, s.payhoa_vendor) if w)
    # A carrier that writes several coverages (Accelerant, Federal) implies the one policy only when it is the only one.
    implied: dict[str, set] = defaultdict(set)
    for words, _name, kind in out:
        if kind is not None:
            implied[words].add(kind)
    return [(w, n, k if k is None or len(implied[w]) == 1 else None) for w, n, k in out if len(w) >= 4]


def _readings_premiums(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / "documents" / "readings.json"
    if not path.is_file():
        return []
    out = []
    for r in json.loads(path.read_text(encoding="utf-8")).get("readings", []):
        f = r.get("fields") or {}
        if r.get("kind") != "insurance_policy" or not f.get("premium") or not _day(f.get("term_start")):
            continue
        out.append({"number": _fold(str(f.get("policy_number") or "")).replace("O", "0"), "start": _day(f["term_start"]),
                    "end": _day(f.get("term_end")), "premiumCents": int(f["premium"]), "file": r.get("name")})
    return out


def _sheet_premiums(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / "insurance" / "sheet.json"
    if not path.is_file():
        return []
    rows = json.loads(path.read_text(encoding="utf-8"))
    return rows if isinstance(rows, list) else []


def _sheet_row_for(policy: Any, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    for row in rows:
        kind = str(row.get("kind") or "")
        if policy.building is not None:
            if kind.lower() == "flood" and str(row.get("building") or "") == str(policy.building.value):
                return row
        elif kind in policy.premium_categories or kind.lower().replace(" ", "_") == policy.kind.value:
            return row
    return None


def _shift(day: date, year: int) -> date:
    try:
        return day.replace(year=year)
    except ValueError:
        return day.replace(year=year, day=28)


def _policy_terms(policy: Any, readings: list[dict[str, Any]], sheet: list[dict[str, Any]], first_year: int) -> list[dict[str, Any]]:
    """The policy's terms from the first payment year to the next term: start, end, and the expected premium."""
    numbers = {_fold(n).replace("O", "0") for n in policy.numbers}
    read = {}
    for r in readings:
        if r["number"] in numbers and r["start"] not in read:
            read[r["start"]] = r
    starts = set(read)
    if policy.renewal:
        for y in range(first_year - 1, policy.renewal.year + 1):
            s = _shift(policy.renewal, y)
            if not any(abs((s - r).days) <= 45 for r in read):
                starts.add(s)
    row = _sheet_row_for(policy, sheet)
    sheet_premiums = {int(y): int(c) for y, c in ((row or {}).get("premiums") or {}).items() if c}
    terms = []
    for s in sorted(starts):
        r = read.get(s)
        term = {"start": s, "end": (r or {}).get("end") or _shift(s, s.year + 1), "premiumCents": None, "premiumSource": None}
        if r:
            term.update(premiumCents=r["premiumCents"], premiumSource=f"declarations ({r['file']})")
        elif s.year in sheet_premiums:
            term.update(premiumCents=sheet_premiums[s.year], premiumSource="policy sheet")
        terms.append(term)
    return terms


def _in_term(day: date, start: date) -> bool:
    # A premium is often paid ahead and financed after: 90 days before the term to 275 days in (as jason.tasks.insurance).
    return start - timedelta(days=90) <= day < start + timedelta(days=275)


def insurance_payments(paid: list[dict[str, Any]], community: Any, splits: dict[Any, list[tuple[str, int]]],
                       terms: dict[Any, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """The premium payments, each split into portions by coverage (and building, for flood), with the payee it names."""
    from jason.community.symbols import PolicyKind
    from jason.tasks.insurance import flood_policy_named

    rules = community.premium_rules()
    policies = list(community.insurance().policies)
    parties = _premium_parties(community, rules)
    by_category = {c: p.kind for p in policies for c in p.premium_categories}
    other = set(rules.categories)
    floods = [p for p in policies if p.kind is PolicyKind.FLOOD]
    out = []
    for p in paid:
        said = " ".join([p["payee"], p.get("description", ""), *p.get("filenames", [])])
        folded = _fold(" ".join([p["payee"], p.get("description", "")]))
        hit = next(((n, k) for w, n, k in parties if w in folded), None)
        cats = set(p["categories"])
        if hit is None and not (cats & (set(by_category) | other)):
            continue
        rows = splits.get(p["key"]) or ([(p["categories"][0], p["amountCents"])] if len(cats) == 1 else
                                        [(c, None) for c in dict.fromkeys(p["categories"])] or [("", p["amountCents"])])
        mapped = {by_category[c] for c, _ in rows if c in by_category}
        payee_kind = hit[1] if hit else None
        portions = []
        for cat, cents in rows:
            kind = by_category.get(cat) or (next(iter(mapped)) if len(mapped) == 1 else None) or (payee_kind if not mapped else None)
            portions.append({"kind": kind, "category": cat, "amountCents": cents})
        # Rows without amounts (no snapshot): one coverage takes it all; several share it as their premiums do.
        if any(x["amountCents"] is None for x in portions):
            kinds = list(dict.fromkeys(x["kind"] for x in portions))
            portions = [{"kind": k, "category": "", "amountCents": p["amountCents"] // len(kinds) + (p["amountCents"] % len(kinds) if i == 0 else 0)}
                        for i, k in enumerate(kinds)]
        for x in portions:
            x["policy"] = None
            if x["kind"] is PolicyKind.FLOOD:
                key = flood_policy_named(said, policies)
                pol = next((f for f in floods if key and key.startswith(f.number + "|")), None)
                if pol is None:
                    # A premium amount only one building's terms carry.
                    owners = {f for f in floods for t in terms.get(f, []) if t["premiumCents"] == x["amountCents"]}
                    pol = owners.pop() if len(owners) == 1 else None
                x["policy"] = pol
            elif x["kind"] is not None:
                x["policy"] = next((q for q in policies if q.kind is x["kind"]), None)
        label = hit[0] if hit else (p["payee"] or p.get("description", "")[:40])
        out.append({**p, "premiumPayee": label, "payeeKnown": hit is not None, "portions": portions})
    return out


def _kinds_named(text: str, rules: Any) -> tuple[Any, ...]:
    named = tuple(k for k, pattern in rules.coverage_words if re.search(pattern, text, re.I))
    return named or tuple(rules.package)


def link_insurance(approval: dict[str, Any], premiums: list[dict[str, Any]], rules: Any, used: set) -> tuple[list[dict[str, Any]], int, tuple]:
    """The premium payments an insurance approval bought: its coverages, paid 60 days before to 300 days after."""
    start = _day(approval["date"])
    kinds = _kinds_named(approval["text"], rules)
    generic = tuple(kinds) == tuple(rules.package)
    linked, total = [], 0
    for p in premiums:
        d = _day(p["date"])
        if p["key"] in used or d is None or start is None:
            continue
        if not start - timedelta(days=rules.lead_days) <= d <= start + timedelta(days=rules.follow_days):
            continue
        share = sum(x["amountCents"] for x in p["portions"] if x["kind"] in kinds or (x["kind"] is None and generic and p["payeeKnown"]))
        if share:
            linked.append(p)
            total += share
    return linked, total, kinds


def insurance_terms(community: Any, data_dir: Path, premiums: list[dict[str, Any]], terms: dict[Any, list[dict[str, Any]]],
                    approved: list[dict[str, Any]], today: date, first_paid: date | None) -> dict[str, Any]:
    """Per policy and term: the premium per the declarations or sheet, the approvals, what was paid, to whom, how often."""
    expected_payees = {}
    for pol in community.insurance().policies:
        expected_payees[pol] = {_fold(n) for n in (pol.carrier, pol.program, pol.agent) if n}
    placed: set[tuple[Any, int]] = set()
    rows = []
    for pol, pol_terms in terms.items():
        out_terms = []
        for t in pol_terms:
            pays = []
            for p in premiums:
                d = _day(p["date"])
                for i, x in enumerate(p["portions"]):
                    if x["policy"] is pol and d is not None and _in_term(d, t["start"]):
                        pays.append({"date": p["date"], "amountCents": x["amountCents"], "paymentCents": p["amountCents"],
                                     "payee": p["premiumPayee"], "category": x["category"], "key": p["key"]})
                        placed.add((p["key"], i))
            paid_cents = sum(x["amountCents"] for x in pays)
            if not pays and t["premiumCents"] is None:
                continue
            if first_paid and t["start"] - timedelta(days=90) < first_paid and not pays:
                continue                          # its premium was due before the payments jason holds: nothing to compare
            if t["start"] > today + timedelta(days=120) and not pays:
                continue
            approvals_ = [{"date": a["date"], "amountCents": a["amountCents"], "minutes": a.get("minutes"), "coverages": a.get("coverages")}
                          for a in approved if a.get("insuranceKeys") and set(a["insuranceKeys"]) & {x["key"] for x in pays}]
            premium = t["premiumCents"]
            findings = []
            if not pays:
                findings.append("not paid" if t["start"] <= today else "next term not paid yet")
            elif premium is not None:
                if paid_cents >= premium * 1.9:
                    findings.append("paid about twice the premium (a term paid twice?)")
                elif paid_cents > premium * 1.05:
                    findings.append("paid more than the premium")
                elif paid_cents < premium * 0.95:
                    findings.append("paid less than the premium so far")
            amounts = Counter(x["amountCents"] for x in pays)
            if premium and amounts.get(premium, 0) >= 2:
                findings.append("the premium's amount paid twice")
            odd = sorted({x["payee"] for x in pays if not any(w and w in _fold(x["payee"]) for w in expected_payees.get(pol, set()))
                          and not any(p["key"] == x["key"] and p["payeeKnown"] for p in premiums)})
            if odd:
                findings.append("paid to a payee the specification does not name: " + ", ".join(odd))
            out_terms.append({"start": t["start"].isoformat(), "end": t["end"].isoformat() if t["end"] else None,
                              "premiumCents": premium, "premiumSource": t["premiumSource"], "approved": approvals_,
                              "paidCents": paid_cents, "payees": sorted({x["payee"] for x in pays}), "installments": len({x["key"] for x in pays}),
                              "payments": [{k: v for k, v in x.items() if k != "key"} for x in pays], "findings": findings})
        if out_terms:
            rows.append({"coverage": pol.kind.value, "building": int(pol.building.value) if pol.building else None,
                         "number": pol.number, "carrier": pol.carrier, "program": pol.program, "agent": pol.agent, "terms": out_terms})
    unplaced = [{"date": p["date"], "amountCents": x["amountCents"], "payee": p["premiumPayee"], "category": x["category"],
                 "coverage": x["kind"].value if x["kind"] else None}
                for p in premiums for i, x in enumerate(p["portions"]) if (p["key"], i) not in placed]
    return {"policies": rows, "unplaced": unplaced,
            "caveats": ["A premium is what PayHOA paid to an insurer, program, agent, or premium finance company, or booked to an "
                        "insurance category; a premium the agent paid or booked elsewhere is not seen.",
                        "The premium per policy is the declarations' as the document model read it, else the board's policy sheet."]}


def build(data_dir: Path, *, community: Any = None, today: date | None = None) -> dict[str, Any]:
    if community is None:
        from jason.community.spec import load_mystique

        community = load_mystique()
    today = today or date.today()
    approved = approvals(data_dir)
    paid = payments(data_dir)
    rules = community.premium_rules()
    premiums: list[dict[str, Any]] = []
    terms: dict[Any, list[dict[str, Any]]] = {}
    days = sorted(d for p in paid if (d := _day(p["date"])))
    if rules is not None:
        readings, sheet = _readings_premiums(data_dir), _sheet_premiums(data_dir)
        first_year = days[0].year if days else today.year
        terms = {pol: _policy_terms(pol, readings, sheet, first_year) for pol in community.insurance().policies}
        premiums = insurance_payments(paid, community, _splits(data_dir), terms)
    premium_keys: set = set()
    per_year: Counter = Counter()
    for p in paid:
        per_year[(p["payee"], (p["date"] or "")[:4])] += 1
    recurring = {payee for (payee, _y), n in per_year.items() if n >= 6}
    used: dict[Any, str] = {}
    results = []
    for a in approved:
        start = _day(a["date"])
        # The approval's own words name a payee; its item's context speaks only through the estimate's vendor (below).
        words = set(re.findall(r"[a-z0-9]{4,}", a["text"].lower()))
        linked, how = [], ""
        extra: dict[str, Any] = {}
        about_insurance = rules is not None and bool(re.search(rules.words, a["text"], re.I))
        weak = rules is not None and not about_insurance and bool(re.search(rules.weak_words, a["text"], re.I))
        numbers = {n for n in a["proposals"] if len(n) >= 4}           # "24" from "Proposal 24-25" is not a number
        if numbers:
            # A short estimate number ("000858") repeats across vendors: it links only to a payee the approval or its item
            # names. A long one (a contract or policy number) links alone.
            linked = [p for p in paid if (set(p["references"]) & numbers)
                      and (any(len(n) >= 8 for n in set(p["references"]) & numbers) or _key_words(p["payee"]) & words)]
            how = "the invoice cites the approved proposal" if linked else ""
            if not linked and not a["amountCents"]:
                # The item names the vendor and attaches its estimate; the vendor's invoice need not repeat the number. The
                # vendor is the name printed just before the estimate's number, not any name the item mentions.
                # The item may name several vendors (the proposals it weighed); of those not paid monthly, the one paid
                # in the window is the accepted proposal's vendor, when there is exactly one.
                near = set(re.findall(r"[a-z0-9]{4,}", a.get("context", "").lower()))
                candidates = [p for p in paid if _key_words(p["payee"]) & near and p["payee"] not in recurring and not p["utility"]
                              and p["key"] not in used                     # one payment answers one approval
                              and start is not None and _day(p["date"]) and start <= _day(p["date"]) <= start + timedelta(days=WINDOW_DAYS)]
                if len({p["payee"] for p in candidates}) == 1:
                    linked = sorted(candidates, key=lambda p: p["date"])[:1]
                    how = "the one vendor the approved item names that was paid within nine months"
        if not linked and about_insurance:
            linked, total, kinds = link_insurance(a, premiums, rules, premium_keys)
            extra = {"coverages": [k.value for k in kinds], "insuranceKeys": [p["key"] for p in linked], "paidCents": total}
            how = (f"insurance: premiums for {', '.join(k.value for k in kinds)} to insurers, programs, agents, or premium finance "
                   f"companies, {rules.lead_days} days before to {rules.follow_days} after; installments summed") if linked else ""
            premium_keys |= set(extra["insuranceKeys"])
        if not linked and start is not None:
            def within(p: dict[str, Any]) -> bool:
                d = _day(p["date"])
                return d is not None and start <= d <= start + timedelta(days=WINDOW_DAYS)

            linked = [p for p in paid if _key_words(p["payee"]) & words and within(p)]
            how = "the approval names the payee; paid within nine months" if linked else ""
            if not linked:
                # The minutes often name the work, not the vendor ("$9,871 tree pruning"): a payment of the same amount
                # (within 1%) in the window, to a vendor not paid monthly, is the likely payment.
                same = [p for p in paid if within(p) and not p["utility"] and p["key"] not in used
                        and abs(p["amountCents"] - a["amountCents"]) <= a["amountCents"] * 0.01]
                if len(same) == 1:
                    linked, how = same, "a payment of the approved amount within nine months"
        if not linked and weak:
            linked, total, kinds = link_insurance(a, premiums, rules, premium_keys)
            if linked:
                extra = {"coverages": [k.value for k in kinds], "insuranceKeys": [p["key"] for p in linked], "paidCents": total}
                how = f"insurance (by 'renewal', 'policy', or 'package'): premiums for {', '.join(k.value for k in kinds)}"
                premium_keys |= set(extra["insuranceKeys"])
        total = extra.get("paidCents", sum(p["amountCents"] for p in linked))
        if extra.get("insuranceKeys"):
            # What the policies' terms that these payments bought cost, per the declarations or the sheet.
            bought = {(id(x["policy"]), t["start"]): t["premiumCents"] or 0 for p in linked for x in p["portions"]
                      if x["policy"] is not None and x["kind"].value in extra["coverages"]
                      for t in terms.get(x["policy"], []) if _in_term(_day(p["date"]), t["start"])}
            extra["premiumsCents"] = sum(bought.values())
        for p in linked:
            used.setdefault(p["key"], a["date"])
        if not linked and not a["amountCents"]:
            outcome = "approved with no amount; no payment found"
        elif not linked:
            outcome = "approved, nothing paid yet"
        elif not a["amountCents"]:
            outcome = "paid against the approved proposal (the minutes state no amount)"
        elif total > a["amountCents"] * OVER:
            outcome = "paid more than approved"
        elif total < a["amountCents"] * 0.5:
            outcome = "paid less than half so far"
        else:
            outcome = "paid within the approval"
        results.append({**a, **extra, "outcome": outcome, "how": how, "paidCents": total,
                        "payments": [{k: p[k] for k in ("date", "amountCents", "payee", "invoices", "references")}
                                     | ({"payee": p["premiumPayee"]} if "premiumPayee" in p else {}) for p in linked[:12]]})
    unapproved = [{k: v for k, v in p.items() if k not in ("description", "filenames")} for p in paid
                  if p["key"] not in used and p["amountCents"] >= LARGE_PAYMENT and not p["utility"] and p["payee"] not in recurring]
    insurance = (insurance_terms(community, data_dir, premiums, terms, results, today, days[0] if days else None)
                 if rules is not None else {"policies": [], "unplaced": [], "caveats": []})
    result = {"builtAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "caveats": ["A link is a rule's reading; whether a payment was authorized is the board's to say.",
                          "Minutes not yet read cannot account for a payment; an unapproved payment may be approved in them."],
              "approvals": results, "unapprovedLarge": unapproved, "insurance": insurance,
              "counts": dict(Counter(r["outcome"] for r in results)) | {"paid without an approval ($5,000+)": len(unapproved)}}
    out = Path(data_dir) / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


def _money(c: int) -> str:
    return f"${c / 100:,.2f}"


def summary_lines(result: dict[str, Any], *, limit: int = 12) -> list[str]:
    lines = [", ".join(f"{v} {k}" for k, v in result["counts"].items()), ""]
    for outcome in ("paid more than approved", "approved, nothing paid yet"):
        rows = [r for r in result["approvals"] if r["outcome"] == outcome]
        if rows:
            lines.append(f"{outcome}:")
            for r in rows[:limit]:
                lines.append(f"- {r['date']} approved {_money(r['amountCents'])}, paid {_money(r['paidCents'])}: {r['text'][:100]}")
    if result["unapprovedLarge"]:
        lines.append("paid without an approval in the read minutes ($5,000+, not a monthly vendor):")
        for p in sorted(result["unapprovedLarge"], key=lambda p: -p["amountCents"])[:limit]:
            lines.append(f"- {p['date']} {_money(p['amountCents'])} to {p['payee']}" + (f" (cites {', '.join(p['references'])})" if p["references"] else ""))
    ins = result.get("insurance") or {}
    if ins.get("policies"):
        lines += ["", "insurance premiums by policy term (premium per the declarations or sheet; approved; paid):"]
        for pol in ins["policies"]:
            label = pol["coverage"] + (f" bldg {pol['building']}" if pol["building"] else "")
            for t in pol["terms"]:
                premium = _money(t["premiumCents"]) if t["premiumCents"] is not None else "?"
                approved = "; ".join(f"approved {_money(a['amountCents'])} {a['date']}" for a in t["approved"])
                paid = (f"paid {_money(t['paidCents'])} in {t['installments']} to {', '.join(t['payees'])}" if t["installments"] else "nothing paid")
                note = f" ! {'; '.join(t['findings'])}" if t["findings"] else ""
                lines.append(f"- {label} {t['start']}..{t['end']}: premium {premium}" + (f", {approved}" if approved else "") + f", {paid}{note}")
        if ins.get("unplaced"):
            lines.append(f"insurance payments placed on no term: {len(ins['unplaced'])}")
            for u in ins["unplaced"][:limit]:
                lines.append(f"- {u['date']} {_money(u['amountCents'])} to {u['payee']} ({u['category'] or u['coverage'] or 'no category'})")
    return lines


__all__ = ["approvals", "build", "payments", "summary_lines"]
