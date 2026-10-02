"""Markdown reports for deed succession and assessor name candidates.

A table lists the instruments. A mermaid diagram draws both ends of the
succession, earlier deed to later deed. A gap is a deed with no earlier
document whose grantor is not a developer, and the diagram draws that missing
deed as an unknown. A cited number that was never loaded is an unknown too.
The follow-up section lists the same gaps and unknowns.
"""

from __future__ import annotations

from jason.community.recorder import (
    ChainStep,
    Conveyance,
    NameCandidate,
    OwnershipHistory,
    merge_candidates,
    name_candidates,
)


def slice_history(
    history: OwnershipHistory,
    number: str,
    *,
    stop: frozenset[str] = frozenset(),
    depth: int = 5,
) -> OwnershipHistory:
    """Deeds reached by walking back from ``number``.

    A document in ``stop`` is included and its earlier deeds are not. That
    keeps one unit's owners on the diagram and leaves the shared land chain
    for the community report.
    """
    if history.step(number) is None:
        return OwnershipHistory(history.apn, (), history.developers)
    kept: dict[str, ChainStep] = {}

    def walk(current: str, level: int) -> None:
        if current in kept or level > depth:
            return
        item = history.step(current)
        if item is None:
            return
        priors = () if current in stop and current != number else item.priors
        kept[current] = ChainStep(item.conveyance, priors, item.cited)
        if current in stop and current != number:
            return
        for prior in priors:
            walk(prior, level + 1)

    walk(number, 0)
    steps = tuple(kept[item] for item in history.numbers if item in kept)
    return OwnershipHistory(history.apn, steps, history.developers)


def sections_markdown(
    title: str,
    sections: tuple[tuple[str, OwnershipHistory], ...],
    *,
    note: str = "",
) -> str:
    """One summary table, then a deed table and diagram for each section."""
    lines = [f"# {title}", ""]
    if note:
        lines.extend([note, ""])
    lines.extend(
        [
            "| Chain | Documents | Reaches a developer | Gap |",
            "| --- | ---: | --- | --- |",
        ]
    )
    for heading, history in sections:
        gaps = ", ".join(history.gaps) or ""
        reached = "yes" if history.reached_developer else ""
        lines.append(
            f"| {_cell(heading)} | {len(history.steps)} | {reached} | {_cell(gaps)} |"
        )
    if not sections:
        lines.append("| | 0 | | |")
    for heading, history in sections:
        lines.extend(["", f"## {_cell(heading)}", ""])
        lines.extend(_table(history))
        if history.steps:
            lines.extend(["", "```mermaid", mermaid_succession(history), "```"])
    lines.extend(_follow_section(sections))
    lines.append("")
    return "\n".join(lines)


def history_markdown(title: str, history: OwnershipHistory, *, note: str = "") -> str:
    """A heading, the deed table, and a mermaid succession diagram."""
    lines = [f"# {title}", ""]
    if note:
        lines.extend([note, ""])
    lines.extend(_table(history))
    if history.steps:
        lines.extend(["", "```mermaid", mermaid_succession(history), "```"])
    lines.extend(_follow_section(((title, history),)))
    lines.append("")
    return "\n".join(lines)


def mermaid_succession(history: OwnershipHistory) -> str:
    """Flowchart from the earlier end to the later end.

    A solid arrow is a loaded prior. A gap draws an unknown node into that
    deed with a dotted arrow. A cited number that was not loaded is an
    unknown node with a dotted arrow into the deed that cites it.
    """
    rows = ["flowchart TD"]
    seen: set[str] = set()
    for step in history.steps:
        number = step.conveyance.number
        if number in seen:
            continue
        seen.add(number)
        rows.append(f"    {_node(number)}[\"{_label(step, history)}\"]")
    gaps = set(history.gaps)
    for step in history.steps:
        later = step.conveyance.number
        for prior in step.priors:
            if prior in seen:
                rows.append(f"    {_node(prior)} --> {_node(later)}")
        if later in gaps:
            rows.append(f"    {_gap_node(later)}[\"{_gap_label(step)}\"]")
            rows.append(f"    {_gap_node(later)} -.-> {_node(later)}")
        for cited in step.cited:
            if cited in seen:
                continue
            seen.add(cited)
            rows.append(f"    {_node(cited)}[\"{cited}<br/>unknown\"]")
            rows.append(f"    {_node(cited)} -.-> {_node(later)}")
    return "\n".join(rows)


def candidates_markdown(
    rows: tuple[tuple[str, str, str, tuple[NameCandidate, ...]], ...],
) -> str:
    """Assessor and recorder spellings, then one row per abbreviation candidate.

    Each tuple is an APN, the assessor's owner, the recorder parties, and the
    candidates those two spellings suggested.
    """
    found: list[NameCandidate] = []
    for _apn, _owner, _recorder, candidates in rows:
        found.extend(candidates)
    merged = merge_candidates(found)
    lines = [
        "# Name candidates",
        "",
        "The assessor's secured-roll owner is set beside the recorder parties on the current deed. A shorter token is a candidate for one longer word. Those candidates make two spellings one owner when they account for every remaining word.",
        "",
        "| Short | Long | Owners |",
        "| --- | --- | ---: |",
    ]
    for item in merged:
        lines.append(f"| {_cell(item.short)} | {_cell(item.long)} | {item.count} |")
    if not merged:
        lines.append("| | | 0 |")
    lines.extend(["", "## Parcels", "", "| APN | Assessor | Recorder | Candidates |", "| --- | --- | --- | --- |"])
    for apn, owner, recorder, candidates in rows:
        if not candidates:
            continue
        pairs = ", ".join(f"{item.short} = {item.long}" for item in candidates)
        lines.append(
            f"| {_cell(apn)} | {_cell(owner)} | {_cell(recorder)} | {_cell(pairs)} |"
        )
    lines.append("")
    return "\n".join(lines)


def followups(history: OwnershipHistory) -> tuple[tuple[str, str, str], ...]:
    """What this chain still needs before the search can continue.

    Each row is a kind, a document number, and the next search. ``gap`` is a
    deed with no earlier document whose grantor is not a pinned developer;
    the next search is that grantor. ``unknown`` is a cited number that is
    not in the chain, or a chain that has no documents.
    """
    rows: list[tuple[str, str, str]] = []
    if not history.steps:
        rows.append(("unknown", "", "no document in this chain"))
    known = set(history.numbers)
    for number in history.gaps:
        step = history.step(number)
        grantor = ", ".join(step.conveyance.grantors) if step is not None else ""
        rows.append(("gap", number, grantor))
    seen: set[str] = set()
    for step in history.steps:
        for cited in step.cited:
            if cited in known or cited in seen:
                continue
            seen.add(cited)
            rows.append(("unknown", cited, step.conveyance.number))
    return tuple(rows)


def parcel_candidates(owner: str, *recorder: str) -> tuple[NameCandidate, ...]:
    """Candidates for one parcel. Empty recorder text yields none."""
    if not owner.strip() or not any(name.strip() for name in recorder):
        return ()
    return name_candidates(owner, *recorder)


def _follow_section(sections: tuple[tuple[str, OwnershipHistory], ...]) -> list[str]:
    lines = [
        "",
        "## Follow-ups",
        "",
        "A gap has no earlier deed, and the grantor is not a pinned developer. Search that grantor. An unknown is a cited document that is not in the chain, or a chain with no documents. Load that number before walking further.",
        "",
        "| Chain | Kind | Document | Next search |",
        "| --- | --- | --- | --- |",
    ]
    found = False
    for heading, history in sections:
        for kind, number, detail in followups(history):
            found = True
            if kind == "gap":
                nxt = f"search {detail}" if detail else "search the grantor"
            elif number:
                nxt = f"load the document cited by {detail}"
            else:
                nxt = detail
            lines.append(
                f"| {_cell(heading)} | {kind} | {_cell(number)} | {_cell(nxt)} |"
            )
    if not found:
        lines.append("| | | | |")
    return lines


def _table(history: OwnershipHistory) -> list[str]:
    lines = [
        "| Document | Date | Grantors | Grantees | Comes from | Developer |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not history.steps:
        lines.append("| | | | | | |")
        return lines
    gaps = set(history.gaps)
    for step in history.steps:
        item = step.conveyance
        developer = _developer(history, item)
        comes = ", ".join(step.priors)
        if item.number in gaps:
            comes = comes or "gap"
        lines.append(
            "| "
            + " | ".join(
                (
                    _cell(item.number),
                    _cell(item.recorded.isoformat() if item.recorded else ""),
                    _cell(", ".join(item.grantors)),
                    _cell(", ".join(item.grantees)),
                    _cell(comes),
                    _cell(developer),
                )
            )
            + " |"
        )
    return lines


def _developer(history: OwnershipHistory, item: Conveyance) -> str:
    if not history.from_developer(item):
        return ""
    from jason.community.recorder import developer_for

    for name in item.grantors:
        found = developer_for(name, history.developers)
        if found is not None:
            return found.name
    return ""


def _label(step: ChainStep, history: OwnershipHistory) -> str:
    item = step.conveyance
    when = item.recorded.isoformat() if item.recorded else ""
    grantor = _brief(item.grantors)
    grantee = _brief(item.grantees)
    developer = _developer(history, item)
    tail = f"<br/>{developer}" if developer else ""
    text = f"{item.number}<br/>{when}<br/>{grantor} to {grantee}{tail}"
    return text.replace('"', "'")


def _brief(names: tuple[str, ...]) -> str:
    if not names:
        return ""
    first = names[0]
    if len(first) > 42:
        first = first[:41] + "…"
    if len(names) == 1:
        return first
    return f"{first} +{len(names) - 1}"


def _gap_label(step: ChainStep) -> str:
    grantor = _brief(step.conveyance.grantors)
    if grantor:
        return f"unknown<br/>{grantor}"
    return "unknown"


def _gap_node(number: str) -> str:
    return "g" + "".join(ch for ch in number if ch.isalnum())


def _node(number: str) -> str:
    return "d" + "".join(ch for ch in number if ch.isalnum())


def _cell(text: str) -> str:
    return " ".join(text.replace("|", "/").split())
