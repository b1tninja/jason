from datetime import date

import pytest

from jason.community.authority_order import Clarity, Conflict, ConflictStatus, Tier, conflict_lines, conflicts
from jason.community.lessons import Area
from jason.community.procedures import Procedure, Step, lines


def _row(key="cap", status=ConflictStatus.BOARD, areas=(Area.RENTALS,), **kw):
    fields = dict(provision="CC&Rs 1.1(a)", tier=Tier.DECLARATION, says="Caps something at 10.",
                  authority="CIV 1234(b)", authority_tier=Tier.STATUTE, since=date(2021, 1, 1),
                  extent="A cap below 25 may not be enforced.", apply="Hold nothing against the cap.",
                  clarity=Clarity.PLAIN, status=status, areas=areas, board_item="item-1")
    fields.update(kw)
    return Conflict(key, **fields)


class _Community:
    def __init__(self, *rows):
        self.rows = rows

    def conflicts(self):
        return self.rows


def test_a_conflict_names_a_higher_authority():
    with pytest.raises(ValueError, match="does not rank above"):
        _row(authority_tier=Tier.OPERATING_RULES)
    with pytest.raises(ValueError, match="names what resolved it"):
        _row(status=ConflictStatus.RESOLVED)
    assert not _row(status=ConflictStatus.RESOLVED, resolved_by="the 2027 amendment").open


def test_conflicts_by_area_and_standing():
    done = _row("done", status=ConflictStatus.RESOLVED, resolved_by="an amendment")
    other = _row("other", areas=(Area.ENFORCEMENT,))
    c = _Community(_row(), done, other)
    assert [x.key for x in conflicts(c, Area.RENTALS)] == ["cap", "done"]
    assert [x.key for x in conflicts(c, Area.RENTALS, open_only=True)] == ["cap"]
    assert conflicts(None) == () and conflicts(object()) == ()


def test_a_conflict_reads_as_what_still_governs():
    (line,) = conflict_lines([_row()])
    assert line.startswith("- **CC&Rs 1.1(a)** yields to CIV 1234(b), since January 1, 2021 [plain; board (board item item-1)]")
    assert "Meanwhile: Hold nothing against the cap." in line


def test_a_procedure_shows_the_open_conflicts_in_its_areas():
    proc = Procedure("p", "A procedure", "now", (Area.RENTALS,), "Purpose.", (Step("Do it."),))
    text = "\n".join(lines(proc, _Community(_row(), _row("elsewhere", areas=(Area.EMAIL,)))))
    assert "follow it only that far" in text and "CC&Rs 1.1(a)" in text
    assert text.count("** yields to") == 1


def test_the_profile_records_its_conflicts_by_area():
    from jason.community import community

    rows = conflicts(community())
    assert all(c.authority_tier < c.tier for c in rows)
    assert len({c.key for c in rows}) == len(rows)
