"""Two throwaway communities on one disk, a sentinel in every store each reads, and the reads that must not cross.

Used by ``tests/test_tenancy.py`` (docs/tenancy.md, section 2). ``build_world(root)`` writes two profiles, ``alpha`` and
``beta``, with their private facts, data folders, library stores, outlines, intake questions, catalog rows, and a
file in each of the folders jason writes to. Every sentinel names its community (``SENT-alpha``), so a read that
returns the other's is found by looking for that word. ``PROBES`` are public reads, each labelled with the module that
would hold the state if it crossed; ``read_all`` runs them for the community that is active now.

Run as a script (``python tenancy_support.py KEY``), it prints the probes' answers as JSON: the separate-process shape.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import textwrap
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable

KEYS = ("alpha", "beta")

_PROFILE = '''
from datetime import date
from pathlib import Path

from jason.community.base import Community
from jason.community.lessons import Area, Lesson, Status


class Throwaway(Community):
    name = "{Key} SENT-{key} Association"
    slug = "{key}"
    org_id = {org}
    root = Path(__file__).parent

    def document_sync_rules(self):
        return {{"rules": [], "exclude": []}}

    def buildings(self):
        return ()

    def document_rules(self):
        return ()

    def transaction_rules(self):
        return ()

    def insurance_workbook_id(self):
        return "sheet-SENT-{key}"

    def lessons(self):
        return (Lesson("SENT-{key}-lesson", date(2026, 1, 1), (Area.FORMS,), "what SENT-{key}", "why", "change",
                       Status.OPEN),)
'''


def _stubs() -> str:
    from jason.community.base import Community

    keep = {"name", "slug", "org_id", "root", "document_sync_rules", "buildings", "document_rules",
            "transaction_rules", "insurance_workbook_id"}
    return "".join(f"\n    def {m}(self, *args, **kwargs):\n        return ()\n"
                   for m in sorted(Community.__abstractmethods__) if m not in keep)


@dataclass(frozen=True)
class World:
    root: Path
    packages: dict[str, Path]
    data_root: Path
    spec_dir: Path
    lock_dir: Path

    def data(self, key: str) -> Path:
        return self.data_root / key

    def env(self, key: str) -> dict[str, str]:
        """The environment of a process that serves ``key`` alone (the cell shape)."""
        return {"JASON_COMMUNITY": key, "JASON_PROFILE": key, "JASON_PROFILE_DIR": str(self.packages[key]),
                "JASON_DATA_DIR": str(self.data_root), "JASON_SPEC_DIR": str(self.spec_dir),
                "JASON_LOCK_DIR": str(self.lock_dir), "JASON_CONFIG": str(self.root / "no-user-config.env"),
                "JASON_COMMUNITY_NOTICED": "shim,alias", "JASON_OCR_OLLAMA": "0", "JASON_AUTHORITIES_FETCH": "0"}


def build_world(root: Path) -> World:
    root = Path(root)
    packages, data_root, spec_dir, lock_dir = {}, root / "data", root / "spec", root / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    for index, key in enumerate(KEYS):
        package = root / "profiles" / key
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            textwrap.dedent(_PROFILE.format(Key=key.title(), key=key, org=101 + index * 101)) + _stubs() +
            "\n\nPROFILE = Throwaway\n", encoding="utf-8")
        (package / "forms.py").write_text("OWNER_INFO = {}\n", encoding="utf-8")
        packages[key] = package
    world = World(root, packages, data_root, spec_dir, lock_dir)
    for index, key in enumerate(KEYS):
        _fill(world, key, 101 + index * 101)
    return world


def _fill(world: World, key: str, org: int) -> None:
    """A sentinel in each store ``key`` reads."""
    sent = f"SENT-{key}"
    # private facts: the profile's own file and a topic
    (world.spec_dir / key).mkdir(parents=True, exist_ok=True)
    (world.spec_dir / f"{key}.json").write_text(json.dumps({"facts": {"note": f"{sent}-own-facts"}}), encoding="utf-8")
    (world.spec_dir / key / "cases.json").write_text(json.dumps({"case": f"{sent}-case"}), encoding="utf-8")
    data = world.data(key)
    data.mkdir(parents=True, exist_ok=True)
    # the PayHOA catalog
    from jason.catalog import PayhoaCatalog

    with PayhoaCatalog(data / "payhoa.db") as catalog:
        catalog.upsert_documents(org, [{"id": org, "fileName": f"{sent}-minutes.pdf", "path": f"/{sent}", "directory": False,
                                        "public": False, "fileSize": 1}])
    # the classified library
    from jason.tasks import library

    store = data / library.STORE
    store.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(store) as conn:
        conn.execute(library.SCHEMA)
        conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (f"id-{sent}", "drive", f"Library/{sent}", f"{sent}-library.pdf", "minutes", "", "", "NAME_RULE",
                      "2026-01", 0, "evidence", 1.0, "2026-01-01T00:00:00+00:00", ""))
    # an outline
    from jason.community.outlines import DocumentOutline

    (data / "outlines").mkdir(exist_ok=True)
    (data / "outlines" / "decl.json").write_text(json.dumps(DocumentOutline(key="decl", title=f"Declaration {sent}").to_dict()),
                                                  encoding="utf-8")
    # intake questions, a draft, a job, a cache, and a scratch file: one file in each folder jason writes to
    from jason.community import intake

    intake.save(data, [intake.Ask(f"ask-{sent}", intake.AskKind.FACT, f"subject {sent}", f"What is {sent}?")])
    from jason import jobs

    jobs.add(data, ["lessons", "--area", "forms", f"--note={sent}"])
    for folder in ("drafts", "jobs", "cache", "tmp"):
        (data / folder).mkdir(exist_ok=True)
        (data / folder / f"{sent}-{folder}.txt").write_text(sent, encoding="utf-8")


# --- the reads ---------------------------------------------------------------------------------------------------------

def _active() -> str:
    from jason.community.profile import profile_name

    return profile_name()


def _profile_identity() -> Any:
    from jason.community import community

    c = community()
    return [c.name, c.org_id, c.slug, c.insurance_workbook_id()]


def _lessons() -> Any:
    from jason.community import community
    from jason.community.lessons import Area, for_area, lines

    return lines(for_area(Area.FORMS, community()))


def _private_facts() -> Any:
    from jason.community import private

    return [private.facts("cases"), private.facts(_active()), str(private.path_of("cases"))]


def _under_data(path: Path) -> str:
    """``path`` under the data root, its community folder written as that community's sentinel."""
    parts = Path(path).relative_to(Path(os.environ["JASON_DATA_DIR"])).parts
    return "/".join((f"SENT-{parts[0]}", *parts[1:]))


def _settings_paths() -> Any:
    from jason.config import Settings

    s = Settings.load()
    return [_under_data(s.payhoa_catalog), _under_data(s.ownership_db), _under_data(s.tax_db), s.payhoa_org_id]


def _catalog_search() -> Any:
    from jason.mcp.server import search_documents

    return search_documents(name_contains="SENT")


def _library() -> Any:
    from jason.mcp.county import library_search, library_status

    return [library_search(), library_status()]


def _outline() -> Any:
    from jason.config import data_dir
    from jason.tasks.manual import load_outline

    return load_outline(data_dir(), "decl").title


def _intake() -> Any:
    from jason.mcp.governance import intake_questions

    return intake_questions()


def _jobs() -> Any:
    from jason.mcp.county import jobs_status

    return jobs_status()


def _data_listing() -> Any:
    from jason.config import data_dir

    root = data_dir()
    made = ("payhoa.db", "decl.json", "asks.json", "library.db")      # what the world wrote; a read may add caches
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.is_file() and ("SENT" in p.name or p.name in made))


def _lock_names() -> Any:
    from jason.locks import Resource, _name, account

    return [account(), _name(Resource.PAYHOA, account()), _name(Resource.GOOGLE, account())]


def _web_community_profile() -> Any:
    from jason.web.extra.community_profile import community_profile

    return community_profile({})


def _web_onboarding() -> Any:
    from jason.web.extra.onboarding_setup import onboarding_session

    return onboarding_session({})


def _web_key_documents() -> Any:
    from jason.web.extra.key_documents import key_documents

    return key_documents({})


# probe name -> (the module that would hold the state, the read)
PROBES: dict[str, tuple[str, Callable[[], Any]]] = {
    "profile_identity": ("jason.community.profile", _profile_identity),
    "lessons": ("jason.community.lessons", _lessons),
    "private_facts": ("jason.community.private", _private_facts),
    "settings_paths": ("jason.config", _settings_paths),
    "catalog_search": ("jason.mcp.server", _catalog_search),
    "library": ("jason.mcp.county", _library),
    "outline": ("jason.tasks.manual", _outline),
    "intake": ("jason.mcp.governance", _intake),
    "jobs": ("jason.mcp.county", _jobs),
    "data_listing": ("jason.config", _data_listing),
    "lock_names": ("jason.locks", _lock_names),
    "web_community_profile": ("jason.web.extra.community_profile", _web_community_profile),
    "web_onboarding": ("jason.web.extra.onboarding_setup", _web_onboarding),
    "web_key_documents": ("jason.web.extra.key_documents", _web_key_documents),
}


_TIME = re.compile(r"\d{4}-\d\d-\d\d[T ]\d\d:\d\d(:\d\d)?(\.\d+)?([+-]\d\d:\d\d|Z)?")


def read_all() -> dict[str, str]:
    """Every probe, run for the community that is active now, as text. A probe that raises is its error text, so a
    failure reads as a difference and not a crash."""
    out: dict[str, str] = {}
    for name, (_, fn) in PROBES.items():
        try:
            out[name] = _TIME.sub("<time>", json.dumps(fn(), default=str, sort_keys=True))
        except Exception as exc:  # noqa: BLE001
            out[name] = f"ERROR {type(exc).__name__}: {exc}"
    return out


def main() -> None:
    here = Path(__file__).resolve().parent
    sys.meta_path[:] = [f for f in sys.meta_path if "editable" not in type(f).__module__.lower()
                        and "editable" not in getattr(f, "__name__", "").lower()]
    sys.path[:0] = [str(here.parent / "src")]
    print(json.dumps(read_all()))


if __name__ == "__main__":
    main()
