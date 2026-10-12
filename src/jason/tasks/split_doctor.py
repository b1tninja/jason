"""``jason split --doctor``: list the PDF splitter's inconsistent states, and fix the safe ones (docs/pdf-splitter-failure-modes.md section 6).

**Read-only by default.** ``diagnose`` takes no write lock, changes nothing, and runs while the server is up. A finding has a stable id
(``DR-NN:subject``), a class, what it is, why it matters, and the command that fixes it. It names no file and quotes no page's text.

========  =========================================================================================================
class     meaning
========  =========================================================================================================
A         derived or scratch, rebuildable: leftover temporary files, copies and caches no draft needs
B         re-queue derived work: missing facts; cancel a job whose subject is gone
C         touches a record: an unfinished apply, an orphan pin, a damaged session: a person's act, named
D         jason cannot fix it: a damaged copy, a pin whose file is gone: reported with what to do
========  =========================================================================================================

``fix`` repairs class A and B only, each by its finding id (or ``safe`` for all of them), with ``by`` and a confirmation, and leaves one
history line (``split-doctor``) with ids and counts. Class C is a person's act: ``jason split ID --finish`` or ``--rollback``. Nothing is
deleted that is not derived: a copy, a cache, a temporary file, a queued job. A session, a pin, a part file, and a journal are never
removed here.

The checks (the ids of section 6.3): DR-01 a session file that does not read; DR-02 a draft whose copy is missing; DR-03 a copy or cache
no draft needs (older than a day); DR-04 a copy whose size differs from its session's; DR-05 page facts missing or short; DR-06 temporary
files left by a cut-short write; DR-08 an applied part whose file is missing; DR-09 a pin made by a split that no session lists (an orphan
pin); DR-10 a part file nothing refers to; DR-11 a pin whose file is missing; DR-12 a queued job whose subject is gone; DR-14 an apply
that did not finish (a journal with no commit, or a confirmed draft with no journal); DR-16 two live drafts on one file's bytes; DR-18
the sweep's record is ahead of the clock; DR-19 a
committed apply whose jobs were never queued.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from jason.tasks import record_slots as rs
from jason.tasks import split_journal as sj
from jason.tasks import split_session as ss

DAY = 86400
CLASSES = {"A": "scratch", "B": "re-queue", "C": "a person's act", "D": "report"}
SAFE = ("A", "B")


def _finding(check: str, subject: str, cls: str, what: str, why: str, fix: str, *, session: str = "", count: int = 1) -> dict[str, Any]:
    return {"id": f"{check}:{subject}" if subject else check, "check": check, "class": cls, "what": what, "why": why, "fix": fix,
            "session": session, "count": count}


def _old(path: Path, now: float, age: float) -> bool:
    try:
        return now - path.stat().st_mtime >= age
    except OSError:
        return False


def _sessions_raw(root: Path) -> tuple[list[ss.SplitSession], list[tuple[str, bool]]]:
    """The sessions that read, and the files that do not (id, whether the previous save reads)."""
    good: list[ss.SplitSession] = []
    bad: list[tuple[str, bool]] = []
    folder = ss.split_dir(root) / "sessions"
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else ():
        try:
            good.append(ss.SplitSession.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            continue
        except (OSError, ValueError, KeyError, TypeError):
            pass
        try:
            ss.SplitSession.from_dict(json.loads(ss._bak(path).read_text(encoding="utf-8")))
            bad.append((path.stem, True))
        except (OSError, ValueError, KeyError, TypeError):
            bad.append((path.stem, False))
    return good, bad


def _store_pins(profile: str) -> list[dict[str, Any]]:
    try:
        return list(rs.load_store(profile).get("pins") or ())
    except Exception:  # noqa: BLE001 - an unreadable store is a finding of its own elsewhere; the doctor goes on without it
        return []


def diagnose(root: Path | None = None, *, community: Any = None, profile: str | None = None, now: float | None = None,
             min_age: float = DAY) -> dict[str, Any]:
    """Every inconsistent state the splitter can find in its own stores. Reads only."""
    root = Path(ss._root(root))
    profile = rs._profile(profile, community)
    clock = time.time() if now is None else now
    out: list[dict[str, Any]] = []
    good, bad = _sessions_raw(root)
    live = [s for s in good if s.status in ("draft", "confirmed")]

    for sid, restorable in bad:
        out.append(_finding("DR-01", sid, "C", "A split draft's file does not read" + (" (the previous save reads)" if restorable else ""),
                            "the draft cannot be opened; it is not lost while its previous save or its copy remains",
                            "the previous save is read automatically in its place; make a fresh save by changing the draft" if restorable
                            else "open the file again to start a new draft", session=sid))

    pins = _store_pins(profile)
    by_sha: dict[str, list[str]] = {}
    for s in live:
        by_sha.setdefault(s.source.sha256, []).append(s.id)
        copy = ss.source_file(root, s.source.sha256)
        if not copy.is_file():
            out.append(_finding("DR-02", s.id, "D", "A draft's copy of its file is missing", "its pictures and its apply cannot work",
                                "open the file again (the draft is kept as a note of the marks)", session=s.id))
        else:
            try:
                if copy.stat().st_size != s.source.size:
                    out.append(_finding("DR-04", s.id, "D", "A draft's copy is not the size it had when it was opened",
                                        "the copy may be damaged; an apply checks its hash and refuses a changed copy",
                                        "open the file again to start a new draft", session=s.id))
            except OSError:
                pass
            facts = ss.read_facts(root, s.source.sha256)
            if len(facts) < s.pages or ss._facts_version(root, s.source.sha256) < ss.FACTS_VERSION:
                out.append(_finding("DR-05", s.id, "B", f"Page facts are missing or short ({len(facts)} of {s.pages} pages)",
                                    "the grid shows pages as not yet measured and suggestions are fewer",
                                    f"jason split {s.id} --facts --yes --by NAME (a background job)", session=s.id))
        pend = ss.pending_apply(root, s)
        if pend is not None:
            said = sj.describe(pend)
            out.append(_finding("DR-14", s.id, "C", said["words"], "the files it wrote are partly in the stores; "
                                "nothing is lost, and a person chooses",
                                f"jason split {s.id} --finish --yes --by NAME, or --rollback", session=s.id))
        elif s.status == "confirmed":
            out.append(_finding("DR-14", s.id, "C", "A draft is confirmed but its apply has no commit (an apply from before the journal)",
                                "some parts may be written; running the apply again with the same choices finishes it",
                                f"jason split {s.id} --apply --yes --by NAME (the same --part and --drop choices)", session=s.id))
    for s in good:
        if s.status == "applied":
            st = sj.state(root, s.id)
            if st["state"] != "none" and not st.get("queued"):
                out.append(_finding("DR-19", s.id, "B", "An applied split's journal never recorded that its read-back and OCR jobs were queued",
                                    "the new files may not be read back yet (a kill came after the commit)",
                                    f"jason split --doctor --fix DR-19:{s.id} --yes --by NAME (queues what is missing, once)", session=s.id))
    for sha, ids in by_sha.items():
        if len(ids) > 1:
            out.append(_finding("DR-16", sha[:12], "C", f"{len(ids)} live drafts are on the same file's bytes", "marks are split between them",
                                "keep one and decline the others: jason split ID --decline --yes --by NAME", count=len(ids)))

    # temporary files a cut-short write leaves, and caches no draft needs
    stale: list[Path] = []
    split = ss.split_dir(root)
    for pattern in ("sessions/*.tmp", "facts/*/*.tmp", "journal/*.tmp", "sources/_incoming/*", "sources/*/*.tmp", "*.tmp"):
        stale += [p for p in split.glob(pattern) if p.is_file() and _old(p, clock, min_age)]
    intake = Path(root) / "record-intake" / profile / "files"
    stale += [p for p in intake.glob("*/*.tmp") if _old(p, clock, min_age)] if intake.is_dir() else []
    if stale:
        out.append(_finding("DR-06", "", "A", f"{len(stale)} temporary files were left by a write that was cut short",
                            "they take room and mean nothing", "jason split --doctor --fix DR-06 --yes --by NAME", count=len(stale)))
    needed = {s.source.sha256 for s in live}
    orphan_copies = [f for shard in ((split / "sources").iterdir() if (split / "sources").is_dir() else ()) if shard.is_dir()
                     and shard.name != "_incoming" for f in shard.glob("*.pdf") if f.stem not in needed and _old(f, clock, min_age)]
    orphan_pictures = []
    try:
        from jason.tasks import split_thumbs as th

        cache = th.cache_root(root)
        orphan_pictures = [d for shard in (cache.iterdir() if cache.is_dir() else ()) if shard.is_dir() for d in shard.iterdir()
                           if d.is_dir() and d.name not in needed and _old(d, clock, min_age)]
    except Exception:  # noqa: BLE001 - no picture cache yet is no orphan pictures
        orphan_pictures = []
    facts_only = [f for shard in ((split / "facts").iterdir() if (split / "facts").is_dir() else ()) if shard.is_dir()
                  for f in shard.glob("*.json") if f.stem not in needed and _old(f, clock, min_age)]
    if orphan_copies or orphan_pictures or facts_only:
        out.append(_finding("DR-03", "", "A", f"{len(orphan_copies)} copies, {len(facts_only)} fact files, and {len(orphan_pictures)} picture "
                            "folders belong to no live draft", "they take room; an applied split's leftovers are here too",
                            "jason split --doctor --fix DR-03 --yes --by NAME", count=len(orphan_copies) + len(facts_only) + len(orphan_pictures)))

    # the records: applied parts, pins, and the files under them
    claimed_pins: set[str] = set()
    claimed_refs: set[str] = set()
    for s in good:
        for part in (s.applied.get("parts") or ()):
            if part.get("pin"):
                claimed_pins.add(str(part["pin"]))
            if part.get("ref"):
                claimed_refs.add(str(part["ref"]))
        for ev in sj.read(root, s.id):
            d = ev.get("detail") or {}
            if ev.get("kind") in ("part", "library"):
                for part in ([d] if ev["kind"] == "part" else d.get("parts") or ()):
                    if part.get("pin"):
                        claimed_pins.add(str(part["pin"]))
                    if part.get("ref"):
                        claimed_refs.add(str(part["ref"]))
            if ev.get("kind") == "intent":
                claimed_pins |= {str(p.get("pin")) for p in d.get("parts") or () if p.get("pin")}
        for part in (s.applied.get("parts") or ()):
            ref = part.get("ref")
            if ref and part.get("action") in ("held",) and not (Path(root) / ref).is_file():
                out.append(_finding("DR-08", f"{s.id}:{part.get('ordinal', '')}", "D", "An applied part's file is missing from the held store",
                                    "the part cannot be read back", "restore the data folder, or open the original and split it again",
                                    session=s.id))
    sessions_by_id = {s.id for s in good}
    for pin in pins:
        origin = str(pin.get("splitFrom") or "")
        if not origin.startswith("session:") or pin.get("unpinned"):
            continue
        sid = origin.split(":", 1)[1]
        if pin.get("ref") and not (Path(root) / str(pin["ref"])).is_file():
            out.append(_finding("DR-11", str(pin.get("id")), "D", "A pin made by a split points at a file that is not there",
                                "the slot shows a holder that cannot be opened", "restore the file, or unpin it: jason records --unpin SLOT --pin ID",
                                session=sid))
        if sid in sessions_by_id and str(pin.get("id")) not in claimed_pins:
            out.append(_finding("DR-09", str(pin.get("id")), "C", "A pin made by a split is not listed by the session that made it",
                                "an apply was cut short between the pin and the session's record; the slot holds a file the split does not know",
                                "a person looks: if the file is wrong, unpin it (jason records --unpin SLOT --pin ID --yes --by NAME)",
                                session=sid))
    if intake.is_dir():
        pinned_refs = {str(p.get("ref")) for p in pins if p.get("ref")}
        loose = []
        for f in intake.glob("*/Part-*-pages-*.pdf"):
            ref = f.relative_to(Path(root)).as_posix()
            if ref not in pinned_refs and ref not in claimed_refs:
                loose.append(f)
        if loose:
            out.append(_finding("DR-10", "", "C", f"{len(loose)} part files in the held store are referred to by no pin, no session, and no journal",
                                "a cut-short apply, or a rolled back one, leaves them; they are harmless and take room",
                                "reported only; a person looks before anything is removed", count=len(loose)))

    # queued jobs whose subject is gone
    out += _job_findings(root, profile, pins, sessions_by_id)

    last = ss._sweep_clock(root)
    if last is not None and last.timestamp() - clock > DAY:
        out.append(_finding("DR-18", "", "D", "The sweep's last recorded time is ahead of the clock",
                            "the next sweep will refuse until the clock passes it", "set the clock right"))
    out.sort(key=lambda f: (f["class"], f["id"]))
    return {"findings": out, "clean": not out, "counts": {c: sum(1 for f in out if f["class"] == c) for c in CLASSES},
            "caveats": ["Read only: nothing was changed.", "A class C finding is a person's act; a class D finding jason cannot fix."]}


def _job_findings(root: Path, profile: str, pins: list[dict[str, Any]], sessions_by_id: set[str]) -> list[dict[str, Any]]:
    from jason import jobs

    try:
        queued = [j for j in jobs.jobs(Path(root), limit=1000) if j.status.value == "queued"]
    except Exception:  # noqa: BLE001 - no job database yet is no jobs
        return []
    live = {str(p.get("id")) for p in pins if not p.get("unpinned")}
    gone: list[int] = []
    for j in queued:
        a = j.argv
        if a[:2] == ["records", "--read"] and "--pin" in a:
            pin = a[a.index("--pin") + 1]
            if pin.startswith("p-") and pin not in live:
                gone.append(j.id)
        elif a[:1] == ["split"] and len(a) > 1 and "--facts" in a and a[1] not in sessions_by_id:
            gone.append(j.id)
        elif a[:1] == ["library"] and "--ocr-doc" in a:
            if ss._library_row(Path(root), a[a.index("--ocr-doc") + 1]) is None:
                gone.append(j.id)
    if not gone:
        return []
    return [_finding("DR-12", "", "B", f"{len(gone)} queued jobs have nothing left to work on (their pin, draft, or library file is gone)",
                     "a worker would run them to no purpose", "jason split --doctor --fix DR-12 --yes --by NAME (cancels them)", count=len(gone))]


def fix(which: list[str] | str, *, by: str, confirm: bool = False, root: Path | None = None, community: Any = None,
        profile: str | None = None, now: float | None = None, min_age: float = DAY) -> dict[str, Any]:
    """Repair findings of class A and B. ``which`` is finding ids (``DR-06``, or the full id), or ``safe`` for every class A and B
    finding. Without ``confirm`` it says what it would do. Class C and D findings are refused by name. One history line, ids and counts."""
    root = Path(ss._root(root))
    profile = rs._profile(profile, community)
    person = rs._who(by)
    report = diagnose(root, community=community, profile=profile, now=now, min_age=min_age)
    found = report["findings"]
    wanted = [f for f in found if f["class"] in SAFE] if which == "safe" else [
        f for f in found if f["id"] in set(which) or f["check"] in set(which)]
    refused = [f["id"] for f in wanted if f["class"] not in SAFE]
    wanted = [f for f in wanted if f["class"] in SAFE]
    unknown = [w for w in ([] if which == "safe" else which) if not any(f["id"] == w or f["check"] == w for f in found)]
    plan = [{"id": f["id"], "class": f["class"], "what": f["what"]} for f in wanted]
    if not confirm:
        return {"dryRun": True, "would": {"act": "doctor-fix", "findings": plan, "by": person}, "refused": refused, "notFound": unknown,
                "note": "A dry run: nothing was changed. Add --yes (with --by NAME) to repair class A and B findings."}
    done: list[dict[str, Any]] = []
    clock = time.time() if now is None else now
    for f in wanted:
        n = _repair(root, profile, f, clock, min_age, person)
        done.append({"id": f["id"], "class": f["class"], "repaired": n})
    ss._history(root, {"profile": profile, "act": "split-doctor", "by": person, "fixed": [d["id"] for d in done],
                       "count": sum(d["repaired"] for d in done)})
    return {"dryRun": False, "ok": True, "fixed": done, "refused": refused, "notFound": unknown}


def _repair(root: Path, profile: str, finding: dict[str, Any], clock: float, min_age: float, person: str) -> int:
    check = finding["check"]
    split = ss.split_dir(root)
    if check == "DR-06":
        n = 0
        patterns = ("sessions/*.tmp", "facts/*/*.tmp", "journal/*.tmp", "sources/_incoming/*", "sources/*/*.tmp", "*.tmp")
        for pattern in patterns:
            for p in split.glob(pattern):
                if p.is_file() and _old(p, clock, min_age):
                    p.unlink(missing_ok=True)
                    n += 1
        intake = Path(root) / "record-intake" / profile / "files"
        for p in (intake.glob("*/*.tmp") if intake.is_dir() else ()):
            if _old(p, clock, min_age):
                p.unlink(missing_ok=True)
                n += 1
        return n
    if check == "DR-03":
        before = _count_cache(root)
        ss._unreferenced(root, set(), min_age=min_age)
        return max(0, before - _count_cache(root))
    if check == "DR-12":
        from jason import jobs

        pins = _store_pins(profile)
        gone = {j.id for j in _job_objects(root, pins)}
        n = 0
        for job_id in gone:
            try:
                jobs.cancel(Path(root), job_id)
                n += 1
            except jobs.JobRefused:
                pass
        return n
    if check == "DR-19":
        return 1 if ss.requeue_after_commit(root, finding["session"], person).get("requeued") else 0
    if check == "DR-05":
        ss.queue_facts(root, finding["session"], person)          # a background job in this person's name; nothing is measured here
        return 1
    return 0


def _count_cache(root: Path) -> int:
    split = ss.split_dir(root)
    return sum(1 for _ in split.rglob("*") if _.is_file()) if split.is_dir() else 0


def _job_objects(root: Path, pins: list[dict[str, Any]]) -> list[Any]:
    from jason import jobs

    sessions_by_id = {s.id for s in ss.sessions(root)}
    live = {str(p.get("id")) for p in pins if not p.get("unpinned")}
    out = []
    for j in jobs.jobs(Path(root), limit=1000):
        a = j.argv
        if j.status.value != "queued":
            continue
        if a[:2] == ["records", "--read"] and "--pin" in a and a[a.index("--pin") + 1].startswith("p-") and a[a.index("--pin") + 1] not in live:
            out.append(j)
        elif a[:1] == ["split"] and len(a) > 1 and "--facts" in a and a[1] not in sessions_by_id:
            out.append(j)
        elif a[:1] == ["library"] and "--ocr-doc" in a and ss._library_row(Path(root), a[a.index("--ocr-doc") + 1]) is None:
            out.append(j)
    return out


__all__ = ["CLASSES", "diagnose", "fix"]
