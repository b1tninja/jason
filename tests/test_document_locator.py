"""The document locator: an association's recorded documents found by name, beside its first instruments, and in its
builder's filings; asked of the board as leads, never written as pins."""

from datetime import date

from asspy.core import IndexedInstrument
from asspy.placer.recorder import DocumentType

from jason.community.locator import Tie, rule_for
from jason.tasks.document_locator import locate

ASSOCIATION = "EXAMPLE CREEK HOMEOWNERS ASSOCIATION"
BUILDER = "EXAMPLE BUILDERS LLC"
OWNER = "PRIVATE OWNER"


def _row(number, day, filing, *names):
    return IndexedInstrument(number, date.fromisoformat(day), "", "", filing, names)


ROWS = (
    _row("2001-0000010", "2001-03-01", "DECLARATION OF RESTRICTIONS", f"(R) {BUILDER}"),
    _row("2001-0000011", "2001-03-01", "DEED", f"(R) {BUILDER}", f"(E) {ASSOCIATION}"),
    _row("2001-0000012", "2001-03-01", "SUBDIVISION MAP", f"(R) {BUILDER}"),
    _row("2001-0000013", "2001-03-01", "DEED OF TRUST", f"(R) {OWNER}", "(E) EXAMPLE BANK NA"),
    _row("2001-0000014", "2001-03-01", "DEED", f"(R) {BUILDER}", f"(E) {OWNER}"),
    _row("2003-0000050", "2003-06-01", "DECLARATION ANNEX SUBDV", f"(R) {BUILDER}"),
    _row("2010-0000100", "2010-02-01", "MODIFICATION OF RESTRICTIONS", f"(R) {ASSOCIATION}"),
    _row("2012-0000200", "2012-05-01", "NOTICE OF DELINQUENT ASSESSMENT - HOMEOWNERS ASSOCIATION", f"(R) {OWNER}", f"(E) {ASSOCIATION}"),
)
TYPES = {name: f"T{i}" for i, name in enumerate(sorted({row.filing_name for row in ROWS}))}


class _County:
    """A made-up county index with Placer's surface: a type catalog, typed name searches, number ranges."""

    def __init__(self):
        self.asked = []

    def open_session(self):
        return "session"

    def document_types(self):
        return tuple(DocumentType(i, name, "") for name, i in TYPES.items())

    def nearby(self, number, *, before, after):
        year, seq = number.split("-")
        return tuple(f"{year}-{n:07d}" for n in range(int(seq) - before, int(seq) + after + 1) if n != int(seq) and n > 0)

    def search_page(self, *, session=None, rows=1000, name="", number="", number_to="", types=()):
        self.asked.append((name, number, number_to, len(types)))
        if number:
            found = tuple(r for r in ROWS if number <= r.number <= (number_to or number))
        else:
            wanted = {n for n, i in TYPES.items() if i in types} if types else None
            found = tuple(r for r in ROWS if any(p[4:] == name for p in r.names) and (wanted is None or r.filing_name in wanted))
        return len(found), found


def test_the_filing_rules_read_the_filing_names():
    assert rule_for("DECLARATION ANNEX SUBDV").item == "annexations"
    assert rule_for("DECLARATION OF RESTRICTIONS").item == "declaration"
    assert rule_for("DECLARATION OF TRUST") is None and rule_for("DEED OF TRUST") is None
    assert rule_for("MODIFICATION OF RESTRICTIONS").item == "amendments"
    assert rule_for("DEED").item == "common-area-deeds" and rule_for("SUBDIVISION MAP").item == "maps"


def test_the_locator_ties_the_declaration_by_its_neighbor_and_asks_about_the_builders_other_filings():
    county = _County()
    known = {"name": ASSOCIATION, "spellings": [ASSOCIATION], "evidence": {"assessment lien": 1}}
    found = locate(ASSOCIATION, "Placer County", recorder=county, known=known)
    by = {x.number: x for x in found.found}
    assert by["2001-0000011"].item == "common-area-deeds" and by["2001-0000011"].tie is Tie.NAMED
    assert by["2001-0000010"].item == "declaration" and by["2001-0000010"].tie is Tie.BESIDE   # beside the first deed
    assert by["2001-0000012"].item == "maps" and by["2001-0000012"].tie is Tie.BESIDE
    assert by["2010-0000100"].item == "amendments" and by["2010-0000100"].tie is Tie.NAMED
    assert by["2003-0000050"].item == "annexations" and by["2003-0000050"].tie is Tie.DECLARANT
    assert "2001-0000014" not in by and "2001-0000013" not in by                  # the builder's sale to an owner, a loan
    assert found.liens == 1
    assert all(OWNER not in " ".join(x.parties) for x in found.found)             # an owner is never kept

    leads = {lead["item"]: lead for lead in found.leads(source="the index", found="2099-01-01")}
    assert leads["declaration"]["stakes"] and leads["declaration"]["suggestion"].startswith("2001-0000010")
    assert leads["annexations"]["suggestion"] == ""                               # a builder's filing is asked, not suggested
    assert any("2003-0000050" in choice for choice in leads["annexations"]["choices"])
    report = found.markdown()
    assert "**Ask:**" in report and "2001-0000010" in report and OWNER not in report
    assert "## Not located" not in report or "Annexations" not in report.split("## Not located")[-1]


def test_the_command_keeps_the_leads_and_writes_the_boards_list(tmp_path, monkeypatch, capsys):
    import json

    from jason.cli import build_parser
    from jason.community import profile as profiles
    from jason.community.onboarding import LEADS
    from jason.tasks import onboarding_lookup, profile_scaffold as scaffold

    key = "example_creek"
    monkeypatch.setenv("JASON_SPEC_DIR", str(tmp_path / "spec"))
    made = scaffold.write(key, ASSOCIATION.title(), county="Placer", directory=tmp_path / key, today=date(2099, 1, 1))
    monkeypatch.setenv("JASON_PROFILE", key)
    monkeypatch.setenv("JASON_PROFILE_DIR", str(made.package))
    monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "data" / "payhoa.db"))
    monkeypatch.setattr(onboarding_lookup, "reader_for", lambda county: _County())
    monkeypatch.setattr(onboarding_lookup, "directory_match", lambda name, county: {
        "name": ASSOCIATION, "spellings": [ASSOCIATION], "evidence": {"assessment lien": 1}})
    try:
        args = build_parser().parse_args(["onboard", "--locate"])
        assert args.func(args) == 0
        out = capsys.readouterr().out
        assert f"documents located for {ASSOCIATION}" in out and "declaration:" in out
        stored = json.loads((tmp_path / "spec" / f"{key}.json").read_text(encoding="utf-8"))
        assert {lead["key"] for lead in stored[LEADS]} >= {"located-declaration", "located-annexations"}
        report = tmp_path / "data" / "onboarding" / f"{key}-documents-located.md"
        assert "2001-0000010" in report.read_text(encoding="utf-8") and OWNER not in report.read_text(encoding="utf-8")
        # the result as data beside it, for the console and jason-mcp
        saved = json.loads(report.with_suffix(".json").read_text(encoding="utf-8"))
        assert saved["located_at"] and saved["association"] == ASSOCIATION and OWNER not in json.dumps(saved)
        assert {i["item"] for i in saved["items"]} >= {"declaration", "annexations", "maps", "common-area-deeds"}
        assert not list((tmp_path / "data" / "onboarding").glob(".*.tmp"))          # replaced whole

        # another association by --name: its own files, and nothing enters this profile's leads
        before = (tmp_path / "spec" / f"{key}.json").read_text(encoding="utf-8")
        args = build_parser().parse_args(["onboard", "--locate", "--name", "Example Oaks Owners Assn"])
        assert args.func(args) == 0
        assert "no lead was kept" in capsys.readouterr().out
        assert (tmp_path / "spec" / f"{key}.json").read_text(encoding="utf-8") == before
        assert (tmp_path / "data" / "onboarding" / "placer-example-oaks-owners-association-documents-located.json").is_file()
    finally:
        import sys

        for module in [m for m in sys.modules if m == f"jason_{key}" or m.startswith(f"jason_{key}.")]:
            del sys.modules[module]
        profiles._LOADED.pop(key, None)
