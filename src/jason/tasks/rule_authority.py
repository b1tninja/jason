"""Find the provisions that give the power to make rules, and set them beside the rules on file (``jason rules``).

Ingestion reads the outlines on disk (``data/outlines``) with ``jason.community.rule_authority``: the candidates by rule,
the rules' reading of each, and, when asked, the local model's. The authority rows are written to
``data/rules/authority.json`` with a person's reviews kept by id, and the model's answers are cached beside them so a
rerun does not ask again. The subject report and the measurement read the stores and the outlines; nothing here writes to
PayHOA, Google, or anywhere but ``data/rules``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Iterable

from jason.community import rule_authority as ra
from jason.community.outlines import DocumentOutline

# The documents that can give or limit the power: the recorded instruments, the bylaws, and the board's own rules and
# policies (a rule can limit how the next one is made). Resolutions and annexations record acts, not powers.
SEARCH_KINDS = ("declaration", "bylaws", "articles", "amendment", "operating_rules", "election_rules", "policy")


def outlines_of(data_dir: Path, keys: Iterable[str] = ()) -> list[DocumentOutline]:
    from jason.tasks.outlines import load

    wanted = list(keys)
    found = [o for o in load(Path(data_dir)) if (o.key in wanted if wanted else o.kind in SEARCH_KINDS)]
    missing = [k for k in wanted if k not in {o.key for o in found}]
    if missing:
        raise KeyError(f"no outline {', '.join(missing)} in {Path(data_dir) / 'outlines'} (jason outlines)")
    return found


def duties_of(data_dir: Path, outlines: Iterable[DocumentOutline]) -> dict[str, list[Any]]:
    """Each outline's duty readings: the stored ones (with a person's corrections) when ``jason duties --documents`` has
    read it, else the grammar's, computed now."""
    from jason.community.deontic import read_outline
    from jason.tasks import document_duties as dd

    out = {}
    for o in outlines:
        out[o.key] = dd.stored(Path(data_dir), o.key) if dd.store_path(Path(data_dir), o.key).is_file() else read_outline(o)
    return out


def manual_parts(data_dir: Path, community: Any = None) -> list[ra.RulePart]:
    """The parts of the owner's manual (its rules, its guidance, the policies bound in), from ``jason manual``'s
    classification. Empty when the profile has no manual rows or the manual's outline is not on disk."""
    try:
        from jason.tasks import manual as task

        result, outline, _ = task.classify(Path(data_dir), community)
    except Exception:  # noqa: BLE001 - no manual rows, or no outline: no parts, and every document is read whole
        return []
    return ra.parts_from_manual(outline.key, result)


def run(data_dir: Path, keys: Iterable[str] = (), *, community: Any = None, model: ra.RuleModel | None = None, samples: int = 3,
        again: bool = False, save: bool = True, log: Callable[[str], None] = lambda s: None) -> dict[str, Any]:
    """Read the chosen documents (every searchable one by default) and store the authority rows."""
    data_dir = Path(data_dir)
    outlines = outlines_of(data_dir, keys)
    duties = duties_of(data_dir, outlines)
    parts = manual_parts(data_dir, community)
    cache = {} if again else ra.load_answers(data_dir)
    try:
        found = ra.find(outlines, model=model, duties=duties, parts=parts, samples=samples, cache=cache, log=log)
    finally:
        if model is not None:
            model.release()
        if model is not None and save:
            ra.save_answers(data_dir, cache)
    found["parts"] = parts
    if save:
        ra.save(data_dir, found["authorities"], reader="rules+model" if model else "rules", model=model.model if model else "",
                candidates_read=len(found["candidates"]), references=sum(1 for r in found["rules"].values() if r.answer is ra.Answer.REFERS))
    return found


def subjects(data_dir: Path, community: Any = None, *, authorities: list[ra.RuleAuthority] | None = None) -> list[ra.SubjectRow]:
    """Each subject's standing: the stored grants, the rules on file, and the restrictions the documents state."""
    data_dir = Path(data_dir)
    everything = outlines_of(data_dir)
    duties = duties_of(data_dir, everything)
    parts = manual_parts(data_dir, community)
    held = authorities if authorities is not None else ra.stored(data_dir)
    return ra.by_subject([a for a in held if a.review is not ra.Review.REJECTED],
                         ra.rules_on_file(everything, duties=duties, parts=parts),
                         ra.restrictions(everything, duties=duties))


def gold(data_dir: Path) -> list[dict[str, Any]]:
    path = Path(data_dir) / "rules" / "gold.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    return list(raw["items"] if isinstance(raw, dict) else raw)


# ---------------------------------------------------------------------------------------------------------------------
# Lines for a person


def _cite(a: ra.RuleAuthority) -> str:
    return f"{a.source} {a.section}".strip()


def authority_lines(rows: Iterable[ra.RuleAuthority], *, answers: Iterable[ra.Answer] = (ra.Answer.GRANT,)) -> list[str]:
    """Each row as the words recite it, then its reading: holder, subjects, conditions with their words, procedure."""
    wanted = set(answers)
    out = []
    for a in rows:
        if a.answer not in wanted:
            continue
        subjects = ", ".join([s.value for s in a.subjects] + [f"other: {w}" for w in a.other_subjects]) or "none named"
        out.append(f"{_cite(a)}  [{a.tier.value}; read by {' and '.join(a.readers)}"
                   + (f"; self-consistent {a.consistency:.0%}" if a.consistency is not None else "") + f"; {a.review.value}]")
        out.append(f"  words: \"{a.words}\"")
        out.append(f"  reading (a labeled reading): the {a.holder.value} holds it; subjects: {subjects}")
        for c in a.conditions:
            out.append(f"  {c.kind.value}: \"{c.quote}\"" + (" (elsewhere in the section)" if c.elsewhere else ""))
        if a.procedure:
            out.append(f"  procedure: \"{a.procedure}\"")
        if a.related:
            out.append(f"  related: {', '.join(a.related)}")
    return out


def subject_lines(rows: Iterable[ra.SubjectRow], *, authorities: Iterable[ra.RuleAuthority] = ()) -> list[str]:
    by_id = {a.id: a for a in authorities}
    out = []
    for r in rows:
        out.append(f"{r.subject.value}: {r.standing.value}")
        if r.grants:
            out.append("  authority named: " + ", ".join(sorted({_cite(by_id[i]) + ("" if by_id[i].tier is ra.Tier.LIKELY else f" [{by_id[i].tier.value}]")
                                                                   if i in by_id else i for i in r.grants})))
        if r.general:
            out.append("  general power: " + ", ".join(sorted({_cite(by_id[i]) if i in by_id else i for i in r.general})))
        if r.in_guidance:
            out.append("  stated in guidance only (not counted): " + ", ".join(sorted({_cite(by_id[i]) if i in by_id else i for i in r.in_guidance})))
        if r.rules:
            out.append("  rules on file: " + "; ".join(sorted({f"{x.source} {x.section}".strip() for x in r.rules}))[:300])
        if r.restrictions:
            out.append("  stated in the documents themselves: " + "; ".join(sorted({f"{x.source} {x.section}".strip() for x in r.restrictions}))[:300])
        out.append(f"  Civil Code 4355 (a labeled reading): {r.reading.reach.value}; {r.reading.note}"
                   + (f" [{', '.join(r.reading.cites)}]" if r.reading.cites else ""))
    return out
