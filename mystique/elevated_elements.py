"""Mystique's per-building records of the exterior elevated elements inspection (Civil Code 5551).

The rows are private facts, ``data/spec/mystique/elevated_elements.json`` (the inspector is a person and the report a
file), one row a building, and a missing file means none: each building is then a question for a person in
``jason applies`` and a "date not on record" row in ``jason deadlines``, never a date jason guesses. A row's words
(``responsibility``, ``license``) become symbols in the general loader (``jason.community.elevated_inspections``).

Each row::

    {"building": 3, "label": "building 3", "attached_units": 12, "responsibility": "association_responsible",
     "elements": 4, "inspected_on": "2023-11-17", "inspector": "NAME", "license": "architect",
     "license_number": "C-00000", "report": "the report on file, by its Drive name or library id",
     "permit_application_on": "2006-05-01", "occupancy_certificate_on": "2007-11-01", "note": ""}

A date is entered from the record that states it: the inspection's from the report's first page (5551(e)(5)(A)), the
permit application's and the certificate's from the City's records. The association's own obligation row stays in
obligations.py; these rows feed the (k) and (l) answers for each building.
"""

from __future__ import annotations

from jason.community.elevated_inspections import ElevatedElementsInspection, from_rows
from jason.community.private import facts
from jason.community.symbols import Building


def inspections() -> tuple[ElevatedElementsInspection, ...]:
    return from_rows(facts("elevated_elements", [], profile="mystique"), building_of=lambda n: Building(int(n)))


__all__ = ["inspections"]
