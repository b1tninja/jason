"""A new association: its profile package scaffolded from jason's general templates, loaded as the active profile, and
run through the onboarding session; leads from a public lookup asked as FACT questions; and onboarding by conversation
over MCP (the prompts and the second person's confirmation). A made-up association throughout."""

import asyncio
import json
import sys
from datetime import date

import pytest

from asspy.core import IndexedInstrument
from jason import api
from jason.cli import build_parser
from jason.community import community, intake
from jason.community import profile as profiles
from jason.community.boundary import instance_terms
from jason.community.intake import Ask, AskKind, AskStatus
from jason.community.onboarding import LEADS, Status, counts
from jason.mcp import prompts
from jason.tasks import onboarding_lookup as lookup
from jason.tasks import onboarding_session as session
from jason.tasks import profile_scaffold as scaffold

KEY = "example_village"
NAME = "Example Village HOA"


def _forget(key: str) -> None:
    for module in [m for m in sys.modules if m == f"jason_{key}" or m.startswith(f"jason_{key}.")]:
        del sys.modules[module]
    profiles._LOADED.pop(key, None)


@pytest.fixture
def spec(tmp_path, monkeypatch):
    folder = tmp_path / "spec"
    monkeypatch.setenv("JASON_SPEC_DIR", str(folder))
    return folder


@pytest.fixture
def village(tmp_path, spec, monkeypatch):
    """The scaffold written into a temp folder and made the active profile, with its own empty data folder."""
    made = scaffold.write(KEY, NAME, county="Sacramento", directory=tmp_path / KEY, today=date(2099, 1, 1))
    monkeypatch.setenv("JASON_PROFILE", KEY)
    monkeypatch.setenv("JASON_PROFILE_DIR", str(made.package))
    monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "data" / "payhoa.db"))
    yield made
    _forget(KEY)


# --- The scaffold -------------------------------------------------------------------------------------------------------

def test_the_templates_name_no_association():
    terms = instance_terms(community())
    for path in sorted(scaffold.TEMPLATES.rglob(f"*{scaffold.SUFFIX}")):
        text = path.read_text(encoding="utf-8")
        named = [t.text for t in terms if t.pattern().search(text)]
        assert not named, f"{path.name} names the profile's facts: {named}"
        assert "mystique" not in text.lower()


def test_a_scaffold_loads_and_its_session_has_every_gate_closed(village, tmp_path):
    from jason.config import Settings, default_data_dir

    package = village.package
    rel = sorted(p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file())
    assert {"__init__.py", "community.py", "books.py", "governing.py", "forms.py", "docs/README.md",
            "notes/.gitignore", "notes/README.md"} <= set(rel)
    assert all(not p.endswith(".tmpl") for p in rel)
    assert (package / "notes" / ".gitignore").read_text(encoding="utf-8").splitlines()[-2:] == ["*", "!.gitignore"]
    assert json.loads(village.spec.read_text(encoding="utf-8")) == {"facts": {}}
    for path in package.rglob("*.py"):
        assert b"\x08" not in path.read_bytes()

    the = community()
    assert type(the).__name__ == "ExampleVillage" and the.name == NAME and the.slug == KEY
    assert the.region == "ca/sacramento" and the.org_id == 0 and the.units() == () and the.ccrs is None
    with pytest.raises(KeyError):
        the.library_folder(object())
    assert profiles.profile_module("forms").FORM_TEMPLATES == ()

    data = tmp_path / "data"
    assert Settings.load().payhoa_catalog.parent == data
    assert default_data_dir("mystique").name == "data" and default_data_dir(KEY).name == KEY

    s = session.build(the, data)
    assert not data.exists()                                  # the session reads: it makes no folder for the profile
    assert s.gates and all(not g.open for g in s.gates)
    total = counts(s.results)
    assert total["missing"] >= 0.9 * len(s.results), total
    assert s.questions() and all(r.ask.kind is AskKind.FACT for r in s.questions())
    assert not any(r.ask.subject.startswith("fact:lookup:") for r in s.questions())     # no lookup, no leads
    # the ingest stage shows the last jason ingest beside its checklist condition: none yet
    view = session.lines(s)
    at = next(i for i, line in enumerate(view) if line.strip().startswith("ingest "))
    assert any("nothing taken in yet" in line for line in view[at:at + 3])
    assert next(g for g in session.status_dict(s)["gates"] if g["stage"] == "ingest")["ingest"] is None


def test_the_command_writes_the_package_and_the_session_runs_on_it(tmp_path, spec, monkeypatch, capsys):
    package = tmp_path / "pkg" / KEY
    args = build_parser().parse_args(["onboard", "--new", KEY, "--name", NAME, "--dir", str(package)])
    assert args.func(args) == 0
    out = capsys.readouterr().out
    assert f"JASON_PROFILE={KEY}" in out and f"JASON_PROFILE_DIR={package}" in out
    again = build_parser().parse_args(["onboard", "--new", KEY, "--name", NAME, "--dir", str(package)])
    assert again.func(again) == 2
    assert "never overwrites" in capsys.readouterr().err
    try:
        monkeypatch.setenv("JASON_PROFILE", KEY)
        monkeypatch.setenv("JASON_PROFILE_DIR", str(package))
        monkeypatch.setenv("PAYHOA_CATALOG", str(tmp_path / "data" / "payhoa.db"))
        args = build_parser().parse_args(["onboard"])
        assert args.func(args) == 0
        view = capsys.readouterr().out
        assert view.startswith(f"Onboarding: {NAME}")
        assert view.count(" closed: ") == 5 and " open: " not in view
    finally:
        _forget(KEY)


def test_a_key_that_collides_or_an_existing_package_is_refused_and_nothing_is_written(tmp_path, spec):
    for key, words in (("decl", "book"), ("ccrs", "alias"), ("board", "tool set"), ("mystique", "default profile"),
                       ("Not A Key", "not a profile name"), ("community", "base class")):
        with pytest.raises(scaffold.ScaffoldRefused, match=words):
            scaffold.write(key, NAME, directory=tmp_path / "x")
    with pytest.raises(scaffold.ScaffoldRefused, match="name"):
        scaffold.write(KEY, "", directory=tmp_path / "x")
    assert not (tmp_path / "x").exists() and not spec.exists()
    taken = tmp_path / "taken"
    taken.mkdir()
    (taken / "__init__.py").write_text("", encoding="utf-8")
    with pytest.raises(scaffold.ScaffoldRefused, match="never overwrites a profile"):
        scaffold.write(KEY, NAME, directory=taken)
    spec.mkdir()
    (spec / f"{KEY}.json").write_text('{"facts": {"x": 1}}', encoding="utf-8")
    with pytest.raises(scaffold.ScaffoldRefused, match="never overwrites private facts"):
        scaffold.write(KEY, NAME, directory=tmp_path / "fresh")
    assert json.loads((spec / f"{KEY}.json").read_text(encoding="utf-8")) == {"facts": {"x": 1}}


# --- Leads from a public lookup -----------------------------------------------------------------------------------------

class _Index:
    """A made-up county index: the rows a name search returns."""

    def __init__(self, rows):
        self.rows, self.asked = rows, []

    def search(self, *, name, limit):
        self.asked.append(name)
        return self.rows


def _row(number, day, filing, *names):
    return IndexedInstrument(number, date.fromisoformat(day), "", "", filing, names)


def test_a_lookup_finds_leads_that_become_fact_questions_never_rows(village, tmp_path):
    index = _Index([
        _row("209901010001", "2099-01-01", "DECLARATION", "EXAMPLE VILLAGE HOMEOWNERS ASSN", "A DEVELOPER LLC"),
        _row("209906010002", "2099-06-01", "AMENDMENT", "EXAMPLE VILLAGE HOMEOWNERS ASSN"),
        _row("209907010003", "2099-07-01", "DECLARATION OF ANNEXATION", "EXAMPLE VILLAGE HOMEOWNERS ASSN"),
        _row("209908010004", "2099-08-01", "NOTICE OF ASSOCIATION LIEN", "EXAMPLE VILLAGE HOMEOWNERS ASSN",
             "AN OWNER"),
    ])
    found = lookup.lookup(NAME, "Sacramento County", recorder=index, today=date(2099, 9, 1))
    assert index.asked == ["EXAMPLE VILLAGE"]
    keys = {lead["key"]: lead for lead in found.leads}
    assert set(keys) == {"declaration", "amendments", "annexations", "indexed-name"}
    assert keys["declaration"]["suggestion"].startswith("209901010001 (2099-01-01")
    assert keys["declaration"]["stakes"] is True and keys["annexations"]["stakes"] is False
    assert keys["indexed-name"]["suggestion"] == "EXAMPLE VILLAGE HOMEOWNERS ASSN"
    assert "AN OWNER" not in json.dumps(found.leads)                 # another party's name is never kept
    assert any("Secretary of State" in n for n in found.notes)

    path = lookup.save_leads(KEY, found.leads)
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["facts"] == {} and len(stored[LEADS]) == 4
    lookup.save_leads(KEY, found.leads[:1])                           # a new lookup replaces its own lead only
    assert len(json.loads(path.read_text(encoding="utf-8"))[LEADS]) == 4

    s = session.build(community(), tmp_path / "data")
    asked = {r.ask.subject: r.ask for r in s.questions()}
    decl = asked["fact:lookup:declaration"]
    assert decl.kind is AskKind.FACT and decl.suggestion == keys["declaration"]["suggestion"]
    assert decl.serves == "declaration" and intake.high_stakes(decl)
    assert decl.detail["record"] == "profile change" and decl.detail["method"] == "ccrs"
    assert any("public index" in e for e in decl.evidence)
    # the package is untouched: a lead is a question, not a row
    assert "DECLARATION = None" in (village.package / "governing.py").read_text(encoding="utf-8")


def test_a_surveyed_countys_associations_are_a_list_to_choose_from_and_feed_the_lookup(tmp_path, monkeypatch, capsys):
    from asspy.associations import Directory, Sighting, key

    monkeypatch.setenv("ASSPY_HOME", str(tmp_path / "asspy"))
    assert lookup.directory_for("Placer County") is None                   # not surveyed: nothing is created
    assert not (tmp_path / "asspy").exists()
    lien = "NOTICE OF DELINQUENT ASSESSMENT - HOMEOWNERS ASSOCIATION"
    with Directory(tmp_path / "asspy" / "counties" / "placer" / "associations.db") as directory:
        directory.store((
            Sighting(key("EXAMPLE VILLAGE HOMEOWNERS ASSN"), "EXAMPLE VILLAGE HOMEOWNERS ASSN", "2020-0000001", lien, date(2020, 1, 2)),
            Sighting(key("EXAMPLE VILLAGE HOA"), "EXAMPLE VILLAGE HOA", "2005-0000001", lien, date(2005, 1, 2)),
            Sighting(key("EXAMPLE BANK NATIONAL ASSOCIATION"), "EXAMPLE BANK NATIONAL ASSOCIATION", "2020-0000002", "DEED OF TRUST", date(2020, 1, 2)),
        ))
    rows = lookup.known_associations("Placer County")
    assert [r["name"] for r in rows] == ["EXAMPLE VILLAGE HOMEOWNERS ASSN"]   # the older HOA spelling folds into it; the bank is not listed
    assert rows[0]["standing"] == "confirmed" and set(rows[0]["spellings"]) == {"EXAMPLE VILLAGE HOMEOWNERS ASSN", "EXAMPLE VILLAGE HOA"}
    assert lookup.known_associations("Placer County", "bank") == []

    index = _Index([_row("2005-0000003", "2005-03-01", "DECLARATION", "EXAMPLE VILLAGE HOA", "A DEVELOPER LLC")])
    found = lookup.lookup(NAME, "Placer County", recorder=index, today=date(2099, 9, 1), directory=True)
    assert index.asked[0] == "EXAMPLE VILLAGE" and set(index.asked[1:]) == {"EXAMPLE VILLAGE HOMEOWNERS ASSN", "EXAMPLE VILLAGE HOA"}
    spelling = next(lead for lead in found.leads if lead["key"] == "indexed-name")
    assert set(spelling["choices"][:2]) == {"EXAMPLE VILLAGE HOMEOWNERS ASSN", "EXAMPLE VILLAGE HOA"}
    assert any("association directory" in note for note in found.notes)

    args = build_parser().parse_args(["onboard", "--associations", "--county", "Placer County", "--find", "village"])
    assert args.func(args) == 0
    assert "EXAMPLE VILLAGE HOMEOWNERS ASSN  [homeowners, confirmed, 2005-2020]" in capsys.readouterr().out


def test_a_county_without_a_reader_or_none_given_is_a_note():
    assert lookup.lookup(NAME, "").leads == []
    nowhere = lookup.lookup(NAME, "Nowhere County")
    assert nowhere.leads == [] and any("no reader for 'Nowhere County'" in n for n in nowhere.notes)
    assert lookup.region_for("San Luis Obispo County") == "ca/san-luis-obispo"


# --- Onboarding by conversation -------------------------------------------------------------------------------------------

def test_the_prompts_are_served_with_the_onboarding_tools_and_the_board_set_is_unchanged():
    from jason.mcp.server import build, tools_for

    assert [t.__name__ for t in tools_for("onboarding")] == [
        "onboarding_status", "next_questions", "intake_questions", "answer_intake_question", "onboarding_confirm",
        "association_directory", "documents_located"]
    assert len(tools_for("board")) == 45

    async def listed(profile):
        return [p.name for p in await build(profile).list_prompts()]

    assert asyncio.run(listed("onboarding")) == ["onboard", "onboard_review"]
    assert asyncio.run(listed("governance")) == ["onboard", "onboard_review"]
    assert asyncio.run(listed("board")) == []
    got = asyncio.run(build("onboarding").get_prompt("onboard", {"person": "A Person", "stage": "operate"}))
    text = got.messages[0].content.text
    for words in ("onboarding_status", "next_questions", "answer_intake_question", "A Person", "Keeper",
                  "second person", "stage 'operate'", "jason onboard --apply"):
        assert words in text
    review = prompts.onboard_review("B Person")
    assert "awaiting_confirmation" in review and "onboarding_confirm" in review and "own answer" in review


def test_the_docs_carry_the_system_prompt_for_a_client_without_prompts():
    from jason.community.boundary import repo_root

    doc = (repo_root() / "docs" / "onboarding.md").read_text(encoding="utf-8")
    assert "## Onboarding by conversation" in doc
    assert prompts.system_prompt() in doc


def test_a_high_stakes_answer_is_confirmed_only_by_a_different_person(tmp_path):
    ask = Ask(intake.ask_id(AskKind.FACT, "fact:signers", ""), AskKind.FACT, "fact:signers", "Who signs?",
              serves="signers", stakes=True)
    intake.save(tmp_path, [ask])
    assert "error" in api.onboarding_confirm(ask.id, "B Person", data_dir=tmp_path)        # nothing answered yet
    done = api.answer_intake_question(ask.id, "two board officers", by="A Person", data_dir=tmp_path)
    assert done["highStakes"] is True and "second person" in done["next"]
    waiting = api.intake_questions(awaiting_confirmation=True, data_dir=tmp_path)["questions"]
    assert [q["id"] for q in waiting] == [ask.id] and waiting[0]["answeredBy"] == "A Person"
    assert "error" in api.onboarding_confirm(ask.id, "", data_dir=tmp_path)
    same = api.onboarding_confirm(ask.id, " a person ", data_dir=tmp_path)
    assert "a second person confirms" in same["error"]
    ok = api.onboarding_confirm(ask.id, "B Person", data_dir=tmp_path)
    assert ok["confirmedBy"] == "B Person" and ok["answeredBy"] == "A Person"
    assert api.intake_questions(awaiting_confirmation=True, data_dir=tmp_path)["count"] == 0
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["asks.json"]


def test_an_answer_to_a_listed_question_parks_it_first(tmp_path):
    listed = api.next_questions(limit=50, data_dir=tmp_path)["questions"]
    fact = next(q for q in listed if q["kind"] == "fact" and not q["highStakes"] and not q["inQueue"])
    done = api.answer_intake_question(fact["id"], "kept by the treasurer", by="A Person", data_dir=tmp_path)
    assert done["status"] == "answered" and "highStakes" not in done
    stored = {a.id: a for a in intake.load(tmp_path)}
    assert stored[fact["id"]].status is AskStatus.ANSWERED
    assert "error" in api.answer_intake_question("no-such-id", "x", by="A Person", data_dir=tmp_path)
    secret = next(q for q in listed if q["kind"] == "fact" and q["id"] != fact["id"])
    refused = api.answer_intake_question(secret["id"], "password: hunter22", by="A Person", data_dir=tmp_path)
    assert "error" in refused and "Keeper" in refused["error"]
