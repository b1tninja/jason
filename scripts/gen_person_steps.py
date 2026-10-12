"""Write docs/workflows/person-steps-inventory.md: every person step of every general workflow definition.

Run from the repository root with the project's venv:

    .venv/Scripts/python scripts/gen_person_steps.py

A *person step* is a step a human does: kind ``person`` (an act jason cannot do) or ``decision`` (the board's, recorded by the
secretary). The page this feeds is docs/workflows/person-steps.md. The definitions are the source; this script only lays them
out, so the output is a pure function of the code (no clock, no data folder, no profile). tests/test_person_steps_inventory.py
fails when the committed file differs from ``render()``.

The definitions are built here from their builders and are not put in the registry, so the output does not depend on what a
test or a program registered earlier. What the script reads of a step: its kind, roles, command, why, clock, skip and
not-applicable outcome, record, SOP address (and what that procedure step carries), and the checks, jobs, and approvals kinds
its ``why`` says it is waiting for.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "workflows" / "person-steps-inventory.md"

TITLE_CHARS = 96

# What the "Missing" column can say. Each is a guidance field the step could carry from what the definition already holds; the
# fields the spec adds (docs/workflows/person-steps.md, section 4) are missing from every step until they are written, and are
# not repeated on every row.
MISSING = {
    "why": "no why sentence",
    "done": "no record named, so nothing says what done points to",
    "cmd": "a person step with no command (nothing to copy)",
    "sop": "no procedure step it was built from (no lesson, check, or reading to show)",
    "time": "no clock, so no date to remind from",
    "exit": "neither a skip rule nor a not-applicable outcome (a step that cannot be left must say how it is blocked)",
}

_CITE = re.compile(r"\b(?:CIV|CCP|CCR|HSC|GOV|BPC|CORP|RTC|INS)\s\d{2,5}(?:\.\d+)?(?:\([A-Za-z0-9]+\))*")
_TICKS = re.compile(r"`([^`]+)`")


def _wanted(why: str) -> list[str]:
    """The reads, jobs, and approvals kinds a step's ``why`` says it is waiting for, as ``check NAME`` / ``job NAME`` /
    ``plan NAME``. The definitions say it in a few fixed sentences (see the family modules); a sentence not matched here is
    simply not listed, and the family module's own ``WANTED`` stays the full list."""
    out: list[str] = []

    def add(kind: str, name: str) -> None:
        item = f"{kind} {name}".strip()
        if item not in out:
            out.append(item)

    for m in re.finditer(r"\(wanted: (check|job|plan|kind) ([\w./:-]+)\)", why):
        add("plan" if m[1] == "kind" else m[1], m[2])
    for m in re.finditer(r"This becomes (a check|a job|a plan under the approvals kind|a case) (\S+?) once built\.", why):
        add({"a check": "check", "a job": "job", "a plan under the approvals kind": "plan", "a case": "case"}[m[1]], m[2])
    for m in re.finditer(r"Becomes a (check|job|plan) step \(([^)]+)\) when", why):
        add(m[1], m[2])
    for m in re.finditer(r"Becomes (?:the jobs?|a job) ((?:`[^`]+`(?:,| and|,? and)? ?)+?)(?: and a plan of kind `([^`]+)`)? when it is registered", why):
        for name in _TICKS.findall(m[1]):
            add("job", name)
        if m[2]:
            add("plan", m[2])
    for m in re.finditer(r"Becomes a plan of kind `([^`]+)`(?:(?:,| and a `([^`]+)`) case `([^`]+)`)?", why):
        add("plan", m[1] + (f"/{m[3]}" if m[3] else ""))
    for m in re.finditer(r"\((plan|role|command|check|job):([\w./:-]+), wanted\)", why):
        add(m[1], m[2])
    for m in re.finditer(r"Becomes a (job|check) \(([\w-]+)\)", why):
        add(m[1], m[2])
    for m in re.finditer(r"(?i:becomes) a plan step when (?:the approvals kind )?([\w-]+?)(?: \([^)]*\))? is registered", why):
        add("plan", m[1])
    for m in re.finditer(r"becomes a plan step when an approvals kind for (.+?) is registered", why):
        add("plan", "for " + m[1])
    for m in re.finditer(r"a child ([\w-]+) run follows when that definition exists", why):
        add("run", m[1])
    for m in re.finditer(r"\(a ([\w-]+) case, wanted\)", why):
        add("case", m[1])
    for m in re.finditer(r"([\w-]+) base template \(wanted\)", why):
        add("template", m[1])
    return out


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ").strip()


def _short(text: str, n: int = TITLE_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _clock(step) -> str:
    c = step.clock
    if c is None:
        return "-"
    when = ""
    if c.slot:
        when = c.slot + (f"{c.days:+d}" if c.days else "") + ("bd" if c.business_days and c.days else "")
    cite = f" {c.cite}" if c.cite else ""
    return f"{when + ' ' if when else ''}{c.basis.value}{cite}".strip()


def _exit(step) -> str:
    bits = []
    if step.is_legal:
        bits.append("legal")
    if step.skip is not None:
        bits.append("skip")
    if step.na is not None:
        bits.append("na")
    return ", ".join(bits) if bits else "-"


def _sop(step, find) -> tuple[str, str]:
    """The SOP address and what that procedure step carries (c = a check, l = lessons, r = readings)."""
    from jason.workflows.types import parse_sop

    if not step.sop:
        return "-", "-"
    parsed = parse_sop(step.sop)
    proc = find(parsed[0]) if parsed else None
    steps = getattr(proc, "steps", ()) or ()
    if not parsed or proc is None or not 1 <= parsed[1] <= len(steps):
        return step.sop, "gone"
    row = steps[parsed[1] - 1]
    got = "".join(letter for letter, has in (("c", row.check), ("l", row.lessons), ("r", row.refs)) if has)
    return step.sop, got or "-"


def _missing(step, sop_address: str) -> list[str]:
    from jason.workflows.types import StepKind

    out = []
    if not step.why.strip():
        out.append("why")
    if not step.record.strip():
        out.append("done")
    if step.kind is StepKind.PERSON and not step.command.strip():
        out.append("cmd")
    if sop_address == "-":
        out.append("sop")
    if step.clock is None:
        out.append("time")
    if step.skip is None and step.na is None:
        out.append("exit")
    return out


def _cites(step) -> str:
    found = []
    if step.clock is not None and step.clock.cite:
        found.append(step.clock.cite)
    if step.support is not None:
        found += [c.key for c in step.support.guides.cites]
    found += [" ".join(m.split()) for m in _CITE.findall(step.why)]
    return ", ".join(dict.fromkeys(found)) or "-"


def collect() -> list[dict]:
    """One dict per definition, in family order, with its person steps."""
    from jason.community.procedures import find
    from jason.workflows.definitions_general import GENERAL
    from jason.workflows.defs import FAMILIES, all_builders
    from jason.workflows.guide import coverage_words
    from jason.workflows.types import StepKind, Visibility

    built = [b() for b in (*GENERAL, *all_builders())]
    rank = {f: i for i, f in enumerate(FAMILIES)}
    built.sort(key=lambda w: rank.get(w.family, len(rank)))          # stable: the builders' own order inside a family
    out = []
    for w in built:
        rows = []
        for s in w.steps:
            if s.kind not in (StepKind.PERSON, StepKind.DECISION):
                continue
            address, carries = _sop(s, find)
            rows.append({
                "id": s.id, "title": s.title, "kind": s.kind.value,
                "roles": ", ".join(r.value for r in s.acting_roles), "cmd": bool(s.command.strip()), "why": bool(s.why.strip()),
                "clock": _clock(s), "exit": _exit(s), "sop": address, "carries": carries, "cites": _cites(s),
                "missing": _missing(s, address), "wanted": _wanted(s.why), "item": s.repeat.value == "per item",
                "slot": s.clock.slot if s.clock is not None else "", "legal": s.is_legal, "basis": s.clock.basis.value if s.clock else "",
                "guidance": coverage_words(s) if s.support is not None else "-",
            })
        human_edges = sum(1 for s in w.steps if (s.kind is StepKind.WAIT and s.ends_by_note) or
                          (s.kind is StepKind.BRANCH and s.role.value not in ("jason", "scheduler")))
        out.append({"key": w.key, "title": w.title, "family": w.family, "visibility": w.visibility.value, "steps": len(w.steps),
                    "dates": [d.name + ("*" if d.late else "") for d in w.dates], "rows": rows, "edges": human_edges})
    return out


def _count(items) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(items.items(), key=lambda kv: (-kv[1], kv[0])))


def render() -> str:
    defs = collect()
    rows = [r for d in defs for r in d["rows"]]
    kinds = Counter(r["kind"] for r in rows)
    roles = Counter(role for r in rows for role in r["roles"].split(", "))
    missing = Counter(code for r in rows for code in r["missing"])
    wanted = Counter(w.split(" ")[0] for r in rows for w in r["wanted"])
    lines = [
        "# Person steps: the inventory",
        "",
        "Generated by `scripts/gen_person_steps.py` from the registered general definitions. Do not edit it: run the script and "
        "commit its output. `tests/test_person_steps_inventory.py` fails when this file differs from the script's output. The "
        "page that says what to do with it is [person-steps.md](person-steps.md).",
        "",
        "A **person step** is a step a human does: kind `person` or `decision`. A wait that only a person's note ends, and a branch "
        "a person answers, are human edges of other kinds and are only counted (section 10 of the page).",
        "",
        "## Totals",
        "",
        f"- {len(defs)} definitions, {sum(d['steps'] for d in defs)} steps, **{len(rows)} person steps** ({_count(kinds)}).",
        f"- Acting roles across them (a step with two roles counts once for each): {_count(roles)}.",
        f"- With a command: {sum(r['cmd'] for r in rows)}. With a why sentence: {sum(r['why'] for r in rows)}. "
        f"With a clock: {sum(r['clock'] != '-' for r in rows)} (a legal one: {sum(r['legal'] for r in rows)}). "
        f"Built from a procedure step: {sum(r['sop'] != '-' for r in rows)}. Repeating per item: {sum(r['item'] for r in rows)}.",
        f"- With a guidance record written by a person (`Support`): {sum(r['guidance'] != '-' for r in rows)}; the others show what the panel derives.",
        f"- Guidance each step could already carry, and does not (the codes in the last-but-one column): {_count(missing) or 'none'}.",
        f"- Waiting to be replaced by a check, a job, a plan, or a template (read from the step's why): {_count(wanted) or 'none'}; "
        f"{sum(bool(r['wanted']) for r in rows)} steps name at least one.",
        f"- Human edges of other kinds (a wait a note ends, a branch a person answers): "
        f"{sum(d['edges'] for d in defs)} steps in all.",
        "",
        "## How to read a row",
        "",
        "| Column | Says |",
        "|---|---|",
        "| Step | the step's id (`definition.N`); a step is never renumbered |",
        "| Kind | `person` or `decision` (the board's, recorded by the secretary) |",
        "| Roles | every office that may act, the primary first; `anyone` is any signed-in person |",
        "| Cmd, Why | `Y` when the step has a command to copy, a why sentence; `-` when not |",
        "| Clock | the date slot and its offset, and the basis (`law`, `documents`, `counterparty`, `provider`, `proposed policy`, "
        "`person`), with a cited section; `bd` after an offset is business days; `-` is no clock |",
        "| Exit | `legal` (a law clock: no skip), `skip` (a skip rule), `na` (a not-applicable outcome); `-` is none |",
        "| SOP | the procedure step it was built from; the letters after it say what that step carries: `c` a check, "
        "`l` lessons, `r` readings; `gone` is a drifted address |",
        "| Cites | the sections its clock or why names (in prose, except a law clock's `cite` and a `Support` cite) |",
        "| Guidance | the parts of its `Support` record a person wrote, in the panel's order; `-` when it has none and the panel derives them |",
        "| Missing | codes, from the list below, for guidance the step could already carry |",
        "| Wanted | what the step is waiting to become (`check`, `job`, `plan`, `case`, `template`, `run`, `role`) |",
        "",
        "Missing codes:",
        "",
        *[f"- `{code}`: {text}." for code, text in MISSING.items()],
        "",
        "A repeating step is marked `*` after its id (one clock and one nudge for each item). A date slot marked `*` in a "
        "definition's heading is set after the run starts.",
        "",
    ]
    for family in dict.fromkeys(d["family"] for d in defs):
        lines += [f"## Family: {family}", ""]
        for d in (x for x in defs if x["family"] == family):
            flag = {"held": " (held)", "admin": " (administrator)"}.get(d["visibility"], "")
            dates = ", ".join(f"`{x}`" for x in d["dates"]) or "none"
            lines += [f"### `{d['key']}`{flag}: {_cell(d['title'])}", "",
                      f"{len(d['rows'])} person steps of {d['steps']}. Dates: {dates}. Human edges of other kinds: {d['edges']}.", ""]
            if not d["rows"]:
                lines += ["No person step.", ""]
                continue
            lines += ["| Step | Title | Kind | Roles | Cmd | Why | Clock | Exit | SOP | Cites | Guidance | Missing | Wanted |",
                      "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
            for r in d["rows"]:
                sop = r["sop"] if r["sop"] == "-" else f"{r['sop']} ({r['carries']})"
                lines.append("| " + " | ".join((
                    f"`{r['id']}`" + ("*" if r["item"] else ""), _cell(_short(r["title"])), r["kind"], _cell(r["roles"]),
                    "Y" if r["cmd"] else "-", "Y" if r["why"] else "-", _cell(r["clock"]), r["exit"], _cell(sop), _cell(r["cites"]),
                    _cell(r["guidance"]), ", ".join(r["missing"]) or "-", _cell("; ".join(r["wanted"])) or "-")) + " |")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    OUT.write_text(render(), encoding="utf-8", newline="\n")
    defs = collect()
    print(f"{OUT.relative_to(ROOT).as_posix()}: {len(defs)} definitions, {sum(len(d['rows']) for d in defs)} person steps")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "src"))
    raise SystemExit(main())
