"""A parcel's recorded document processes as Markdown with Mermaid DAGs, from an instrument bundle.

Reads the county-neutral bundle (``InstrumentBundle.as_dict``, what ``jason placer-history`` saves as
``<apn>.json``) and draws, without calling the county:

1. the chain of title as a DAG: each deed, the process it is read as, and its priors. The step's own ``prior`` (the
   strongest hand-off, ``ChainStep.priors[0]``) is a solid arrow; another deed that only shares a name is dotted. The
   parcel's own strand, from the newest deed back through each ``prior``, is drawn thick: a chain joined by party
   names is a braid when a seller sold several units;
2. the tenures as a Gantt chart, with a table of each deed's seats;
3. the builder's first deed with the instruments recorded beside it, and the first sales;
4. the busiest loan lifecycles (opens, advances, escalates, closes);
5. REO resales with the trustee's deed the reading expects;
6. a probate transfer (letters recorded beside the estate's deed);
7. every loan's transitions as a state machine with counts;
8. the other liens against the owners.

Private persons and family trusts are shown by role ("Owner A"; a prime marks the same people re-titling) unless
``names`` is true; businesses, lenders, trustees, and agencies are named (``party_kind``). Owners' names are P1:
the report belongs under ``data/`` and is never committed. Every join is a reading of the index, a lead for a person
to confirm from the recorded copies, not a pin.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Any, Iterable

from jason.community.instrument_graph import PartyKind, party_kind

__all__ = ("process_markdown", "Names")

_ABC = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_PROCESS_CLASS = {"resale": "resale", "restatement": "restatement", "reo resale": "reo", "excluded transfer": "excluded"}
_WORDS = (
    ("CONSTRUCTION", "construction deed of trust"), ("DEED OF TRUST", "deed of trust"), ("TRUST DEED", "deed of trust"),
    ("ASSIGNMENT", "assignment"), ("SUBSTITUTION", "substitution of trustee"), ("SUBORDINATION", "subordination"),
    ("RECONVEYANCE", "reconveyance"), ("NOTICE OF DEFAULT", "notice of default"), ("RESCISSION", "rescission"),
    ("TRUSTEE", "trustee's sale"), ("MODIFICATION", "modification"),
)
_EFFECT_CLASSES = (
    "  classDef opens fill:#e8f0fe,stroke:#3b6fd8;",
    "  classDef advances fill:#f3f3f3,stroke:#888;",
    "  classDef closes fill:#e6f4ea,stroke:#2e7d32;",
    "  classDef escalates fill:#fdecea,stroke:#c0392b;",
    "  classDef lapses fill:#fff7e0,stroke:#c99a00;",
)


class Names:
    """Labels for parties: businesses by name; private persons by role, in order of appearance, unless shown."""

    def __init__(self, *, show: bool = False) -> None:
        self.show = show
        self._labels: dict[str, str] = {}
        self._next = iter([*_ABC, *(a + b for a in _ABC for b in _ABC)])

    @staticmethod
    def private(name: str) -> bool:
        return party_kind(name) is PartyKind.PRIVATE

    def __call__(self, names: Iterable[str]) -> str:
        names = sorted({str(n).replace("\\'", "'") for n in names if n})
        people = [n for n in names if self.private(n)]
        others = [n for n in names if not self.private(n)]
        parts: list[str] = []
        if people:
            if self.show:
                parts.append("; ".join(people))
            else:
                key = "|".join(people)
                if key not in self._labels:
                    # A group sharing a person with an earlier one is the same people re-titling: its letter, primed.
                    earlier = next((v for k, v in self._labels.items() if set(k.split("|")) & set(people)), None)
                    self._labels[key] = (earlier.rstrip("′") + "′") if earlier else f"Owner {next(self._next)}"
                count = len(people)
                parts.append(f"{self._labels[key]} ({count} persons)" if count > 1 else self._labels[key])
        parts.extend(others)
        return " + ".join(parts) or "(none indexed)"


def _esc(text: str) -> str:
    return str(text).replace('"', "'").replace("<", "‹").replace(">", "›")


def _nid(number: str) -> str:
    return "d" + re.sub(r"\W", "", str(number))


def _word(filing: str) -> str:
    upper = str(filing).upper()
    return next((w for k, w in _WORDS if k in upper), re.sub(r"^\d+\s*", "", str(filing)).lower())


def _apn(apn: str) -> str:
    return f"{apn[:3]}-{apn[3:6]}-{apn[6:9]}-{apn[9:]}" if len(apn) == 12 and apn.isdigit() else apn


def process_markdown(bundle: dict[str, Any], *, address: str = "", names: bool = False, today: date | None = None) -> str:
    """The report for one parcel bundle (``InstrumentBundle.as_dict``)."""
    today = today or date.today()
    who = Names(show=names)
    ins = {i["number"]: i for i in bundle.get("instruments", [])}
    history = (bundle.get("histories") or [{}])[0]
    steps = sorted(history.get("steps", []), key=lambda s: (s["recorded"], s["number"]))
    readings = {r["number"]: r for r in bundle.get("readings", [])}
    liens = bundle.get("liens", [])
    loans = [l for l in liens if l.get("process") == "loan" and l.get("steps")]
    parcel = (bundle.get("parcels") or [{"apn": bundle.get("label", ""), "newest": ""}])[0]
    by_number = {s["number"]: s for s in steps}
    for s in steps:                       # letters follow time
        who(s["grantors"])
        who(s["grantees"])

    def lender(number: str) -> str:
        item = ins.get(number)
        found = [n for n in (item["grantees"] + item["grantors"] if item else []) if not Names.private(n)]
        return _esc(found[0]) if found else ""

    md: list[str] = []
    add = md.append
    add(f"# Recorded document processes: {address or _apn(parcel['apn'])}")
    add("")
    add(f"{bundle.get('county', '').title()} County, APN **{_apn(parcel['apn'])}**. Read from the county recorder's public "
        f"index: **{len(ins)} instruments**, a chain of **{len(steps)} deeds**, **{len(bundle.get('formations', []))} "
        f"closings** read as bundles, and **{len(liens)} lien lifecycles** across the owners. Drawn {today:%B} {today.day}, "
        f"{today.year}.")
    add("")
    if names:
        add("Owners are shown by name (a person asked for them): keep this copy with the people who work with them.")
    else:
        add("Owners and family trusts are shown by role (Owner A, Owner B, ...; a prime marks the same people re-titling); "
            "lenders, trustees, builders, and agencies are named.")
    add("Every join is a reading of the index (numbers, dates, filing types, and party names), a lead for a person to "
        "confirm from the recorded copies, not a pin.")
    add("")
    for note in bundle.get("notes", []):
        add(f"> {note}")
        add("")

    # 1. the chain of title -------------------------------------------------------------------------------------
    line: list[str] = []
    current = parcel.get("newest") or (steps[-1]["number"] if steps else "")
    while current in by_number and current not in line:
        line.append(current)
        priors = by_number[current].get("priors") or []
        current = priors[0] if priors else ""
    on_line = set(line)
    gaps = set(history.get("gaps", []))
    add("## 1. Chain of title as a DAG")
    add("")
    add("Each box is a deed: its number, date, the process it is read as, and who took title. A solid arrow runs from "
        "a deed's own prior (the deed that put the most of its grantors in title) to it; a dotted link is another "
        "earlier deed that only shares a name with a grantor. Thick boxes are this parcel's own strand; a dashed box "
        "is a prior the index walk did not find.")
    add("")
    add("```mermaid")
    add("flowchart TB")
    add("  classDef resale fill:#e8f0fe,stroke:#3b6fd8;")
    add("  classDef restatement fill:#f3f3f3,stroke:#888;")
    add("  classDef reo fill:#fdecea,stroke:#c0392b;")
    add("  classDef excluded fill:#fff7e0,stroke:#c99a00;")
    add("  classDef gap fill:#fff,stroke:#999,stroke-dasharray:4 3;")
    add("  classDef line stroke:#111,stroke-width:3px;")
    for s in steps:
        process = readings.get(s["number"], {}).get("process", "")
        add(f'  {_nid(s["number"])}["{s["number"]}<br/>{s["recorded"]}<br/><b>{_esc(process or "deed")}</b><br/>'
            f'to {_esc(who(s["grantees"]))}"]:::{_PROCESS_CLASS.get(process, "resale")}')
    if on_line:
        add(f"  class {','.join(_nid(n) for n in sorted(on_line))} line;")
    for s in steps:
        priors = [p for p in s.get("priors", []) if p in by_number]
        for rank, p in enumerate(priors):
            if rank == 0:
                add(f"  {_nid(p)} {'==>' if s['number'] in on_line else '-->'} {_nid(s['number'])}")
            else:
                add(f"  {_nid(p)} -.-|shares a name| {_nid(s['number'])}")
        if s["number"] in gaps and not priors:
            add(f'  g{_nid(s["number"])}["prior deed not found"]:::gap -.-> {_nid(s["number"])}')
    add("```")
    add("")
    if line:
        add(f"**This parcel's strand** runs through {len(line)} deeds back to **{line[-1]}**: "
            f"{' → '.join(reversed(line))}. The other {len(steps) - len(line)} deeds are side strands the walk joined by "
            "party name: the same sellers' other units (a half-plex's twin, the builder's other lots), or a co-owner's other "
            "title.")
        add("")

    # 2. tenures --------------------------------------------------------------------------------------------------
    add("## 2. Who held title, when")
    add("")
    add("```mermaid")
    add("gantt")
    add("  title Tenures by deed (start: the deed in; end: the next deed in the chain)")
    add("  dateFormat YYYY-MM-DD")
    add("  axisFormat %Y")
    for i, s in enumerate(steps):
        end = steps[i + 1]["recorded"] if i + 1 < len(steps) else today.isoformat()
        process = readings.get(s["number"], {}).get("process", "")
        tag = "crit, " if process == "reo resale" else ("done, " if process == "restatement" else "")
        add(f"  section {_esc(who(s['grantees']))[:40]}")
        add(f"  {s['number']} {_esc(process)} :{tag}{_nid(s['number'])}, {s['recorded']}, {max(end, s['recorded'])}")
    add("```")
    add("")
    add("| Deed | Recorded | Read as | From | To | Seats |")
    add("|---|---|---|---|---|---|")
    for s in steps:
        r = readings.get(s["number"], {})
        missing = [slot["role"] for slot in r.get("slots", []) if slot.get("reason") == "missing"]
        add(f"| {s['number']}{' **(strand)**' if s['number'] in on_line else ''} | {s['recorded']} | {r.get('process', '')} | "
            f"{who(s['grantors'])} | {who(s['grantees'])} | {'all present' if r.get('complete') else 'missing: ' + ', '.join(missing)} |")
    add("")

    # 3. the builder's first deed and the first sales --------------------------------------------------------------
    if steps:
        first = steps[0]
        year = first["recorded"][:4]
        formations = [f for f in bundle.get("formations", []) if f.get("recorded", "")[:4] == year]
        add(f"## 3. The first deed ({year}) and what was recorded beside it")
        add("")
        add(f"The earliest deed the walk reached, **{first['number']}**, with the instruments recorded beside it and the "
            "sales that followed that year. Construction deeds of trust beside a land deed are the builder's loans, one "
            "per dwelling; a reconveyance on a sale's day releases one, and the buyer's deed of trust finances the sale.")
        add("")
        add("```mermaid")
        add("flowchart LR")
        add("\n".join(_EFFECT_CLASSES))
        add("  classDef deed fill:#fff,stroke:#333,stroke-width:2px;")
        add(f'  {_nid(first["number"])}["{first["number"]}<br/>{first["recorded"]}<br/><b>deed</b><br/>to {_esc(who(first["grantees"]))}"]:::deed')
        drawn: set[str] = {first["number"]}
        for f in formations:
            anchor = f["anchor"]
            if anchor not in drawn:
                a = ins.get(anchor, {})
                add(f'  {_nid(anchor)}["{anchor}<br/>{a.get("recorded", "")}<br/><b>sale deed</b><br/>to {_esc(who(a.get("grantees", [])))}"]:::deed')
                drawn.add(anchor)
            for m in f.get("members", []):
                n = m["number"]
                if m["role"] == "prior deed":
                    if n in drawn:
                        add(f"  {_nid(n)} -->|prior| {_nid(anchor)}")
                    continue
                if n not in drawn:
                    add(f'  {_nid(n)}["{n}<br/><b>{_esc(_word(ins.get(n, {}).get("filingName", m["role"])))}</b>'
                        f'{"<br/>" + lender(n) if lender(n) else ""}"]')
                    drawn.add(n)
                add(f"  {_nid(anchor)} {'-->|same day|' if anchor == first['number'] else '-.->|' + _esc(m['role']) + '|'} {_nid(n)}")
        for l in loans:
            if "CONSTRUCTION" in l["steps"][0]["filing"].upper() and l["steps"][0]["number"] in drawn:
                for st in l["steps"][1:]:
                    if st["effect"] == "closes":
                        if st["number"] not in drawn:
                            add(f'  {_nid(st["number"])}["{st["number"]}<br/>{st["recorded"]}<br/><b>reconveyance</b>"]:::closes')
                            drawn.add(st["number"])
                        add(f"  {_nid(st['number'])} ==>|releases| {_nid(l['steps'][0]['number'])}")
        add("```")
        add("")

    # 4. loan lifecycles ------------------------------------------------------------------------------------------
    def lifecycle(l: dict, prefix: str) -> list[str]:
        out, prev = [], ""
        for st in l["steps"]:
            node = f"{prefix}{_nid(st['number'])}"
            by = lender(st["number"]) if st["effect"] == "opens" else ""
            out.append(f'  {node}["{st["number"]}<br/>{st["recorded"]}<br/><b>{_esc(_word(st["filing"]))}</b>'
                       f'{"<br/>" + by if by else ""}"]:::{st["effect"]}')
            if prev:
                out.append(f"  {prev} -->|{st['effect']}| {node}")
            prev = node
        if l.get("status") == "open":
            out.append(f'  {prev} -.-> {prefix}open(("still open"))')
        return out

    if loans:
        add("## 4. Loan lifecycles")
        add("")
        add("A deed of trust *opens* a loan; an assignment, a substitution of trustee, or a subordination *advances* it; a "
            "notice of default *escalates* it; a reconveyance *closes* it (paid off), and a trustee's deed would close it "
            "by sale. The busiest loans on this parcel's owners during their tenure, then any that defaulted:")
        add("")
        busiest = sorted((l for l in loans if l.get("duringTenure")), key=lambda l: (-len(l["steps"]), l["steps"][0]["number"]))[:4]
        defaulted = [l for l in loans if any(s["effect"] == "escalates" for s in l["steps"])]
        for i, l in enumerate(busiest + [d for d in defaulted if d not in busiest][:2]):
            opened = l["steps"][0]
            add(f"**{opened['number']}** ({opened['recorded']}), {_word(opened['filing'])} from {lender(opened['number']) or 'a lender'}, "
                f"{'during the tenure' if l.get('duringTenure') else 'outside the tenure'}: {l.get('status', '')}.")
            add("")
            add("```mermaid")
            add("flowchart LR")
            add("\n".join(_EFFECT_CLASSES))
            add("\n".join(lifecycle(l, f"l{i}")))
            add("```")
            add("")

    # 5. REO resales ------------------------------------------------------------------------------------------------
    reo = [s for s in steps if readings.get(s["number"], {}).get("process") == "reo resale"]
    if reo:
        add("## 5. Foreclosure and the REO resales")
        add("")
        add("A deed read as an **REO resale** has a lender (often a securitization trustee) selling a house it took back at "
            "a trustee's sale, with the buyer's financing beside it. The reading expects a **trustee's deed** before it; "
            "where the walk did not find one under the owners' names, the box is dashed: the trustee's deed names the "
            "foreclosing trustee and the lender, so that is where to look.")
        add("")
        add("```mermaid")
        add("flowchart LR")
        add("  classDef missing fill:#fff,stroke:#c0392b,stroke-dasharray:4 3;")
        add("  classDef reo fill:#fdecea,stroke:#c0392b;")
        add("  classDef loan fill:#e8f0fe,stroke:#3b6fd8;")
        for s in reo:
            n = _nid(s["number"])
            slots = {slot["role"]: slot for slot in readings[s["number"]].get("slots", [])}
            deed = slots.get("trustee's deed", {})
            if deed.get("reason") == "missing" or not deed.get("number"):
                add(f'  t{n}["trustee\'s deed<br/>(not found)"]:::missing -.->|lender takes title| {n}')
            else:
                add(f'  t{n}["{deed["number"]}<br/><b>trustee\'s deed</b>"] -->|lender takes title| {n}')
            add(f'  {n}["{s["number"]}<br/>{s["recorded"]}<br/><b>REO resale</b><br/>from {_esc(who(s["grantors"]))}<br/>'
                f'to {_esc(who(s["grantees"]))}"]:::reo')
            for c in readings[s["number"]].get("companions", []):
                add(f'  {n} -->|same day| {_nid(c)}["{c}<br/><b>{_esc(_word(ins.get(c, {}).get("filingName", "")))}</b><br/>{lender(c)}"]:::loan')
        add("```")
        add("")

    # 6. probate ----------------------------------------------------------------------------------------------------
    probate = [f for f in bundle.get("formations", []) if any("letters" in m["role"] or "affidavit" in m["role"] for m in f.get("members", []))]
    if probate:
        add("## 6. Probate: the court's authority recorded beside the estate's deed")
        add("")
        add("Letters of administration (or testamentary) are recorded with the deed they authorize: the representative's "
            "power to convey sits beside the conveyance. The next deed in the chain is what the heirs or trust did with it.")
        add("")
        add("```mermaid")
        add("flowchart LR")
        add("  classDef court fill:#f3e8fd,stroke:#7b3fb8;")
        add("  classDef deed fill:#fff,stroke:#333,stroke-width:2px;")
        add("\n".join(_EFFECT_CLASSES))
        for f in probate:
            anchor = f["anchor"]
            a = ins.get(anchor, {})
            add(f'  {_nid(anchor)}["{anchor}<br/>{a.get("recorded", "")}<br/><b>estate deed</b><br/>from {_esc(who(a.get("grantors", [])))}'
                f'<br/>to {_esc(who(a.get("grantees", [])))}"]:::deed')
            for m in f["members"]:
                n = m["number"]
                if "letters" in m["role"] or "affidavit" in m["role"]:
                    add(f'  {_nid(n)}["{n}<br/>{ins.get(n, {}).get("recorded", "")}<br/><b>{_esc(m["role"])}</b>"]:::court -->|authorizes| {_nid(anchor)}')
                elif m["role"] == "prior deed":
                    p = ins.get(n, {})
                    add(f'  {_nid(n)}["{n}<br/>{p.get("recorded", "")}<br/>prior deed<br/>to {_esc(who(p.get("grantees", [])))}"] -->|decedent\'s title| {_nid(anchor)}')
            following = next((s for s in steps if (s.get("priors") or [""])[0] == anchor), None)
            if following:
                n = following["number"]
                add(f'  {_nid(anchor)} --> {_nid(n)}["{n}<br/>{following["recorded"]}<br/><b>{_esc(readings.get(n, {}).get("process", "deed"))}</b>'
                    f'<br/>to {_esc(who(following["grantees"]))}"]:::deed')
                for c in readings.get(n, {}).get("companions", []):
                    add(f'  {_nid(n)} -->|same day| {_nid(c)}["{c}<br/><b>{_esc(_word(ins.get(c, {}).get("filingName", "")))}</b><br/>{lender(c)}"]:::opens')
        add("```")
        add("")

    # 7. the lifecycle as a state machine ------------------------------------------------------------------------------
    if loans:
        add("## 7. The deed-of-trust lifecycle, counted")
        add("")
        add(f"Every step-to-step transition across the **{len(loans)} loan lifecycles** the walk read for this parcel's "
            "owners (during and outside their tenure here).")
        add("")
        transitions: Counter = Counter()
        ends: Counter = Counter()
        for l in loans:
            seq = ["[*]"] + [re.sub(r"\W+", "_", _word(s["filing"])).strip("_") for s in l["steps"]]
            for a, b in zip(seq, seq[1:]):
                transitions[(a, b)] += 1
            if l.get("status") != "open":
                ends[seq[-1]] += 1
        add("```mermaid")
        add("stateDiagram-v2")
        for (a, b), n in sorted(transitions.items(), key=lambda x: (-x[1], x[0])):
            add(f"  {a} --> {b} : {n}")
        for e, n in sorted(ends.items()):
            add(f"  {e} --> [*] : {n}")
        add("```")
        add("")

    # 8. other liens ----------------------------------------------------------------------------------------------------
    others = [l for l in liens if l.get("process") != "loan"]
    if others:
        add("## 8. Other liens against the owners")
        add("")
        add("Tax liens and judgments attach to what an owner holds in the county, so they bear on this parcel only while "
            "the owner held it.")
        add("")
        add("| Lien | Against | Status | During their tenure here | Steps |")
        add("|---|---|---|---|---|")
        for l in sorted(others, key=lambda l: l["steps"][0]["recorded"] if l.get("steps") else ""):
            trail = " → ".join(f"{s['number']} {_word(s['filing'])} ({s['effect']})" for s in l.get("steps", []))
            add(f"| {l['process']} | {who(l.get('debtor', []))} | {l.get('status', '')} | {'yes' if l.get('duringTenure') else 'no'} | {trail} |")
        add("")

    add("## How the readings are made")
    add("")
    add("```mermaid")
    add("flowchart TB")
    add('  idx[("county index<br/>numbers · dates · filing types · parties")] --> chain["deed chain<br/>(priors by party hand-off, strongest first)"]')
    add('  idx --> bundle["same-day bundles<br/>(adjacent numbers sharing a party)"]')
    add('  idx --> owners["each owner\'s other filings<br/>(one name search each)"]')
    add('  chain --> strand["the parcel\'s strand<br/>(newest deed back through each prior)"]')
    add('  chain --> proc["process reading per deed<br/>resale · restatement · REO resale · excluded transfer"]')
    add("  bundle --> proc")
    add('  owners --> life["lien lifecycles<br/>opens → advances → escalates → closes"]')
    add('  proc --> seats{"seats filled?<br/>grant · prior deed · buyer lien · trustee\'s deed"}')
    add('  seats -->|all present| done["complete"]')
    add('  seats -->|one missing| gap["a gap: where to look next"]')
    add("```")
    add("")
    add("Sources: the county recorder's public index, read through asspy, and the assessor's parcel record. Nothing was "
        "written to the county.")
    return "\n".join(md) + "\n"
