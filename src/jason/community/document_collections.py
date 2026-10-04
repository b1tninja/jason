"""A collection: a set of documents reviewed together, with what holds for all of them.

A review judges a document against something outside it (docs/ingestion-and-review.md). A ``Collection`` is the
"outside" that several documents share: a legal case's file, and later a vendor's file, a meeting's packet, or a
building system's records. It holds:

- **members**: an index ``Scope`` (``passage_index``), so the collection is whatever the index holds under that scope
  today, never a list kept by hand;
- **context**: the lines that hold for the whole collection. For a legal case they are its record in the specification
  (``LegalCase``): its title, forum, role, and status, each event with its date, and each duty with whether the record
  shows it met. Nothing is added that the record does not hold, and nothing is read from the case file to write them;
- **label**: what its material is, said to whoever reads a pack ("evidence gathered for this matter: neither the
  record nor the law");
- **confidential**: the strictest of its members' and its matter's. A legal case's catalog is confidential in the
  index whatever the board has disclosed of the case, so its collection is too.

``collections`` gives one per legal case with a case file; ``collection`` finds one by the case's key or its catalog's
name; ``ad_hoc`` builds one from the filters a person names. ``context_pack.assemble(..., collection=)`` gives a
collection's passages their own tier. A collection is a scope and a context: it pins no fact and decides nothing.

(``jason.community.collections`` is another thing: assessment collections, the ledger beside the liens.)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from jason.community.passage_index import Scope


class CollectionKind(Enum):
    LEGAL_CASE = "legal case"
    AD_HOC = "ad hoc"
    # A vendor's file, a meeting's packet, and a building system's records are collections too. Each becomes a member
    # here, with its rows in LABELS and CONTEXT_TITLES, when it is built.


# What a collection's passages are, said on every one of them in a pack.
LABELS: dict[CollectionKind, str] = {
    CollectionKind.LEGAL_CASE: "evidence gathered for this matter: neither the record nor the law",
    CollectionKind.AD_HOC: "passages from a scope a person named: each is read by the standing in its note",
}
# What a collection's context lines are, said where a pack carries them.
CONTEXT_TITLES: dict[CollectionKind, str] = {
    CollectionKind.LEGAL_CASE: "the specification's record of the matter",
    CollectionKind.AD_HOC: "what was said of the scope when it was named",
}


@dataclass(frozen=True)
class Collection:
    key: str
    title: str
    kind: CollectionKind
    scope: Scope
    context: tuple[str, ...] = ()
    confidential: bool = False

    @property
    def label(self) -> str:
        return LABELS[self.kind]

    @property
    def context_title(self) -> str:
        return CONTEXT_TITLES[self.kind]


def _duty_line(duty: Any) -> str:
    if not duty.applies:
        standing = "It does not apply: the statute's condition has not arisen."
    elif duty.met is True:
        standing = "The record shows it met."
    elif duty.met is False:
        standing = "The record shows it not met."
    else:
        standing = "The record does not show it either way."
    due = f", due {duty.due.isoformat()}" if duty.due else ""
    evidence = f" ({duty.evidence})" if duty.evidence else ""
    return f"Duty ({duty.statute}){due}: {duty.requirement}. {standing}{evidence}"


def case_context(case: Any) -> tuple[str, ...]:
    """A legal case's record in the specification as lines: what it is, then its events in order, then its duties."""
    lines = [f"Matter: {case.title}", f"Forum: {case.forum.value}", f"The association's role: {case.role.value}",
             f"Status: {case.status.value}"]
    for event in sorted(case.events, key=lambda e: e.day):
        lines.append(f"{event.day.isoformat()}: {event.step}" + (f" (recorded: {event.source})" if event.source else ""))
    lines.extend(_duty_line(duty) for duty in case.duties)
    return tuple(lines)


def of_case(case: Any) -> Collection:
    """A legal case's collection: its confidential catalog in the index, and its record in the specification."""
    from jason.tasks.case_files import catalog_name

    name = catalog_name(case)
    # Every file of a case's catalog is confidential in the index (``case_files.index_sources``), so the collection is,
    # whatever the case's own flag says: the strictest of its members' and the matter's.
    return Collection(case.key, case.title, CollectionKind.LEGAL_CASE, Scope(catalogs=(name,), confidential_in=(name,)),
                      case_context(case), confidential=True)


def collections(community: Any) -> tuple[Collection, ...]:
    """One collection per legal case with a case file (a Drive folder); none until the specification sets a case."""
    return tuple(of_case(case) for case in community.legal_cases() if getattr(case, "drive_folder", ""))


def collection(community: Any, key: str) -> Collection | None:
    """The collection a person names, by its case's key or its catalog's name (case-<key>). A miss is None."""
    wanted = key.strip().lower()
    if not wanted:
        return None
    for found in collections(community):
        if wanted in (found.key.lower(), *(name.lower() for name in found.scope.catalogs)):
            return found
    return None


def _words(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(getattr(v, "value", v)).strip() for v in values if str(getattr(v, "value", v)).strip()))


def ad_hoc(*, catalogs: Iterable[str] = (), kinds: Iterable[Any] = (), folders: Iterable[str] = (), title: str = "",
           confidential: bool = False) -> Collection:
    """A collection from the filters a person names: index catalogs, document kinds, and folders under the data
    directory. A legal case's catalog named here opens that case's files, as naming it in a search does, and makes the
    collection confidential. ``confidential`` adds the held files of the other catalogs named (and no catalog that is
    not named), and makes it confidential too. With no filter there is no collection."""
    from jason.tasks.case_files import is_case_catalog

    names, kind_words, places = _words(catalogs), _words(kinds), _words(folders)
    if not (names or kind_words or places):
        raise ValueError("an ad hoc collection needs a catalog, a kind, or a folder")
    if confidential and not names:
        raise ValueError("name the catalogs whose held files the collection includes")
    held = tuple(name for name in names if confidential or is_case_catalog(name))
    parts = [("catalogs", names), ("kinds", kind_words), ("folders", places)]
    said = "; ".join(f"{label} {', '.join(values)}" for label, values in parts if values)
    stamp = hashlib.sha256(repr((names, kind_words, places, bool(held))).encode("utf-8")).hexdigest()[:10]
    return Collection(f"ad-hoc-{stamp}", title.strip() or said, CollectionKind.AD_HOC,
                      Scope(catalogs=names, kinds=kind_words, folders=places, confidential_in=held),
                      confidential=bool(held))


__all__ = ["CONTEXT_TITLES", "Collection", "CollectionKind", "LABELS", "ad_hoc", "case_context", "collection",
           "collections", "of_case"]
