"""Which of the association's documents fills which book (``jason.community.books``).

A record address reads through these rows: ``jason://decl/4.15(a)`` is the CC&Rs, ``jason://rules/B-12(j)`` the rule
sections of the Owner's Manual. The document keys stay aliases (``jason://ccrs/4.15(a)``). Each row's ``note`` says
why it is here; a row is the place to change a mapping (docs/record-addresses.md).

- ``rules`` is the official Rules and Regulations. Until that document is extracted from the Owner's Manual, ``rules``
  resolves to the manual's outline, its rule sections under their own numbers (B-12(j) stays B-12(j)). When the
  extracted document exists, its row takes ``Book.RULES`` and the manual keeps only ``Book.MANUAL``.
- ``manual`` is the Owner's Manual as a whole: a guide for owners, not a governing document.
- The Parking Rules and the ALPR Policy are parts of ``rules``: each is a regulation the board adopted that applies
  generally (CIV 4340(a)), on the use of the common area (4355(a)(1)), and each numbers its own sections. Either row
  may move to its own book (``arch``, ``disc``) by changing the row.
- The Enforcement Policy (with its fine schedule) is ``disc`` (CIV 5850(a)); the Assessment Collection Policy is
  ``coll`` (5310(a)(6), 5730).
- A resolution stays in ``res`` by its number, the Fiscal Management Resolution too: it is the board's act, and whether
  it is also an operating rule (4340(a), "the conduct of the business and affairs of the association") is a reading for
  the board and counsel, not a filing decision.
- The amendments are versions of ``decl``, not parts; the annexations are supplements to it, each a part named by its
  phase.
"""

from __future__ import annotations

from jason.community.books import Book, BookEntry, Role

_RULES_NOTE = ("the rule sections of the Owner's Manual, under their own numbers, until the official Rules and "
               "Regulations are extracted (then that document's row takes rules)")

BOOK_ENTRIES: tuple[BookEntry, ...] = (
    BookEntry("ccrs", Book.DECL, note="the Restated Declaration", cite_as="CC&Rs"),
    BookEntry("ccrs-2nd-amendment", Book.DECL, role=Role.AMENDMENT, note="a recorded amendment: a version of decl"),
    BookEntry("ccrs-3rd-amendment", Book.DECL, role=Role.AMENDMENT, note="a draft amendment: a stage, never in force"),
    BookEntry("bylaws", Book.BYLAWS, cite_as="Bylaws"),
    BookEntry("owners-manual", Book.RULES, note=_RULES_NOTE),
    BookEntry("owners-manual", Book.MANUAL, note="the manual as a whole: a guide, not a governing document"),
    BookEntry("parking-rules", Book.RULES, part="parking", note="a separately adopted operating rule (4340(a)) on "
                                                               "common area use (4355(a)(1))"),
    BookEntry("alpr-policy", Book.RULES, part="alpr", note="the plate-reader policy: an operating rule on common area "
                                                         "use; not one of the Act's named policies"),
    BookEntry("election-rules", Book.ELEC),
    BookEntry("enforcement-policy", Book.DISC, note="the enforcement policy and its fine schedule (5850(a))"),
    BookEntry("collection-policy", Book.COLL),
    *(BookEntry(f"annexation-annexation-{phase}", Book.DECL, part=phase, role=Role.SUPPLEMENT,
                note="a supplementary declaration annexing a phase")
      for phase in ("phase-2", "phase-3", "phase-3-amended", "phase-4", "phase-4-amended", "phase-5", "phase-6",
                    "phase-7", "phase-8")),
)
