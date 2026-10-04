"""Profiles: jason loads one association's specification by name; the general docs name none of its facts."""

import sys
import textwrap

import pytest

from jason.community import Community, community, mystique, profile_name
from jason.community import profile as profiles
from jason.community.boundary import (
    Term,
    baseline_path,
    code_baseline_path,
    compare,
    instance_terms,
    profile_imports,
    repo_root,
    scan,
    scan_code,
)


def test_the_default_profile_is_mystique():
    assert profile_name() == "mystique"
    assert community() is mystique()
    assert community().slug == "mystique"
    assert profiles.package_name("mystique") == "jason_mystique"


def test_kind_rules_classify_through_the_base_class():
    assert community().kind_rules()
    assert community().classify_document("Minutes of 7_7_26.pdf").name == "MINUTES"
    assert community().classify_document("zz-no-rule-names-this.bin") is None


def _write_profile(root, name, body):
    package = root / name
    package.mkdir()
    (package / "__init__.py").write_text(textwrap.dedent(body), encoding="utf-8")
    (package / "forms.py").write_text("OWNER_INFO = {}\n", encoding="utf-8")
    return package


_SMALL = """
    from pathlib import Path

    from jason.community.base import Community


    class Small(Community):
        name = "Small Community Association"
        slug = "small"
        org_id = 1
        root = Path(__file__).parent

        def document_sync_rules(self):
            return {"rules": [], "exclude": []}

        def buildings(self):
            return ()

        def document_rules(self):
            return ()

        def transaction_rules(self):
            return ()

        def insurance_workbook_id(self):
            return ""
"""


def _abstract_stubs():
    """The rest of Community's abstract members, each returning nothing, so the stub profile can be built."""
    lines = []
    for member in sorted(Community.__abstractmethods__):
        if member in {"name", "slug", "org_id", "root", "document_sync_rules", "buildings", "document_rules",
                      "transaction_rules", "insurance_workbook_id"}:
            continue
        lines.append(f"\n        def {member}(self, *args, **kwargs):\n            return ()\n")
    return "".join(lines)


@pytest.fixture
def small_profile(tmp_path, monkeypatch):
    package = _write_profile(tmp_path, "small", _SMALL + _abstract_stubs() + "\n    PROFILE = Small\n")
    monkeypatch.setenv("JASON_PROFILE", "small")
    monkeypatch.setenv("JASON_PROFILE_DIR", str(package))
    yield package
    for module in [m for m in sys.modules if m == "jason_small" or m.startswith("jason_small.")]:
        del sys.modules[module]
    profiles._LOADED.pop("small", None)


def test_another_profile_loads_by_name_beside_mystique(small_profile):
    assert profile_name() == "small"
    small = community()
    assert small.name == "Small Community Association"
    assert small.org_id == 1
    assert small.kind_rules() == ()
    assert small.classify_document("Minutes of 7_7_26.pdf") is None
    assert profiles.profile_module("forms").OWNER_INFO == {}
    assert profiles.load_profile("mystique").slug == "mystique"


def test_settings_take_the_profiles_defaults(small_profile):
    from jason.config import Settings

    settings = Settings(keeper_username="", payhoa_record_uid="", smud_record_uid="", idoxs_record_uid="")
    assert settings.payhoa_org_id == 1
    assert settings.smud_category_id is None


def test_a_missing_profile_says_where_it_looked(monkeypatch):
    monkeypatch.delenv("JASON_PROFILE_DIR", raising=False)
    with pytest.raises(profiles.ProfileNotFound, match="profiles/nowhere"):
        profiles.load_profile("nowhere")
    with pytest.raises(profiles.ProfileNotFound):
        profiles.load_profile("Not A Name")


def test_instance_terms_come_from_the_profile():
    kinds = {term.kind for term in instance_terms(community())}
    assert {"name", "street", "drive id", "payhoa org id"} <= kinds


def test_a_code_pointer_names_the_profile_but_prose_does_not(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("The rules are in `mystique/meetings.py`.\n", encoding="utf-8")
    (docs / "b.md").write_text("Mystique's board meets monthly.\n", encoding="utf-8")
    found = scan(tmp_path, (Term("Mystique", "name"),))
    assert found == {"docs/b.md": ["Mystique"]}


def test_the_general_docs_name_no_new_instance_facts():
    """A new term in a general doc belongs in the profile's docs (mystique/docs) or private notes (mystique/notes).
    A cleared one is removed from the baseline with ``python -m jason.community.boundary --update``."""
    import json

    baseline = json.loads(baseline_path().read_text(encoding="utf-8"))
    drift = compare(scan(repo_root(), instance_terms(community())), baseline)
    assert not drift.new, f"instance facts in general docs: {drift.new}"
    assert not drift.cleared, f"cleared from the docs; update the baseline: {drift.cleared}"


def test_general_code_names_no_new_instance_facts():
    """A fact in a pattern, a word list, or a default argument of general code belongs in the profile behind a
    ``Community`` method with an empty default. A cleared one is removed from the baseline with
    ``python -m jason.community.boundary --update``."""
    import json

    baseline = json.loads(code_baseline_path().read_text(encoding="utf-8"))
    drift = compare(scan_code(repo_root(), instance_terms(community())), baseline)
    assert not drift.new, f"instance facts in general code; move them into the profile: {drift.new}"
    assert not drift.cleared, f"cleared from the code; update the baseline: {drift.cleared}"


def test_the_cleared_modules_stay_cleared():
    """The modules whose street and name patterns moved into the profile (2026-10-04) are not in the baseline."""
    import json

    baseline = json.loads(code_baseline_path().read_text(encoding="utf-8"))
    cleared = {"src/jason/community/incidents.py", "src/jason/community/models/invoices.py",
               "src/jason/community/models/insurance_claims.py", "src/jason/community/models/correspondence.py",
               "src/jason/community/sources.py", "src/jason/postscanmail/models.py", "src/jason/tasks/mail.py",
               "src/jason/tasks/mail_links.py", "src/jason/tasks/cross_checks.py", "src/jason/tasks/drive_labels.py"}
    assert not cleared & set(baseline)


def test_general_code_never_imports_the_profile():
    assert profile_imports(repo_root(), community().slug) == []


def test_a_fact_in_a_pattern_a_word_list_or_a_default_is_found(tmp_path):
    code = tmp_path / "src" / "jason"
    code.mkdir(parents=True)
    (code / "patterns.py").write_text(textwrap.dedent('''
        """Reads Main Street addresses."""  # a docstring and a comment name it on purpose
        import re

        ADDRESS = re.compile(r"\\b(\\d{4})\\s+(Main|Elm)\\s+St")
        STOP = frozenset("board owner oakridge".split())


        def own(text, name="OAKRIDGE"):
            print("Oakridge")
            return re.search(rf"(?i){name}", text)
    '''), encoding="utf-8")
    (code / "clean.py").write_text('MESSAGE = "Oakridge"\n', encoding="utf-8")
    terms = (Term("Oakridge", "name"), Term("Main", "street"), Term("Elm", "street"), Term("Birch", "street"))
    assert scan_code(tmp_path, terms) == {"src/jason/patterns.py": ["Elm", "Main", "Oakridge"]}


def test_an_import_of_the_profile_is_found(tmp_path):
    code = tmp_path / "src" / "jason"
    code.mkdir(parents=True)
    (code / "a.py").write_text("import importlib\n\nimportlib.import_module('oakridge.labels')\n", encoding="utf-8")
    (code / "b.py").write_text("from jason_oakridge import forms\nfrom jason.community import community\n", encoding="utf-8")
    (code / "c.py").write_text("import importlib\n\nimportlib.import_module(f'oakridge.{1}')\n", encoding="utf-8")
    assert profile_imports(tmp_path, "oakridge") == ["src/jason/a.py:3", "src/jason/b.py:1", "src/jason/c.py:3"]


def test_a_manager_is_an_instance_term_and_a_reader_finds_it_through_the_sender_directory():
    from jason.community.sources import Sender, SourceKind, manager_in, manager_name

    kinds = {t.text: t.kind for t in instance_terms(mystique())}
    managers = [s for s in mystique().senders() if s.kind is SourceKind.MANAGER]
    assert managers and all(kinds.get(s.name) == "manager" for s in managers)
    listed = (Sender("Oak Ridge Management", SourceKind.MANAGER, ("OAK RIDGE MANAGEMENT",)),
              Sender("Oak Ridge Roofing", SourceKind.VENDOR, ("OAK RIDGE ROOFING",)))
    assert manager_in("Prepared by Oak Ridge Management, Inc.", listed) is listed[0]
    assert manager_in("Invoice from Oak Ridge Roofing", listed) is None            # a vendor is not a manager
    assert manager_name("Prepared by Oak Ridge Management", object()) == ""        # no directory: a miss


def test_a_manager_named_in_a_general_pattern_is_found(tmp_path):
    code = tmp_path / "src" / "jason"
    code.mkdir(parents=True)
    (code / "reader.py").write_text("import re\n\ndef f(t):\n    return re.search(r'Oak Ridge Management', t)\n", encoding="utf-8")
    assert scan_code(tmp_path, (Term("Oak Ridge Management", "manager"),)) == {"src/jason/reader.py": ["Oak Ridge Management"]}


def test_the_lesson_names_its_guard():
    from jason.community.lessons import LESSONS, lesson

    row = lesson("facts-in-general-patterns")
    assert row is not None and any("code_boundary.json" in g for g in row.guards)
    assert len({r.key for r in LESSONS}) == len(LESSONS)


def test_a_profile_without_streets_or_a_name_pattern_reads_none(small_profile):
    from jason.community.document_models import ModelContext
    from jason.community.incidents import places_in
    from jason.community.models.invoices import service_address
    from jason.community.sources import other_associations
    from jason.postscanmail.models import AddressKind, MailAddress, address_of, letter_facts
    from jason.tasks.drive_labels import schema

    small = community()
    assert small.streets() == () and small.name_pattern() == "" and schema() == ()
    letter = "Small Community Association\nc/o Oak Ridge Homeowners Association\n3021 Enchanted Walk"
    assert letter_facts(letter, small.streets()).addresses == ()
    assert places_in(letter, (), streets=small.streets()) == ()
    assert service_address(letter, ModelContext(community=small)) == ("", None)
    box = (MailAddress(AddressKind.CURRENT, "box", ("ENCHANTED",)),)
    assert address_of(letter, box, name=small.name_pattern())[0] is AddressKind.UNREAD
    # Without a pattern even its own name is not known as its own: it is listed for a person to look at.
    assert other_associations(letter, own_name=small.name_pattern()) == ("Small Community Association",
                                                                         "Oak Ridge Homeowners Association")
    # The default profile reads the same letter.
    mine = profiles.load_profile("mystique")
    assert letter_facts(letter, mine.streets()).addresses == ("3021 ENCHANTED WALK",)


def test_a_profile_without_systems_is_asked_which_it_has(small_profile):
    from jason.community.fire_protection import NFPA_25_SPRINKLERS
    from jason.community.life_safety import applicable
    from jason.community.obligations import Obligation

    small = community()
    assert small.life_safety_systems() == () and small.applicability_facts() == ()
    nothing = applicable(small)
    assert not (nothing.applies or nothing.does_not_apply or nothing.undetermined or nothing.questions())
    row = Obligation("Sprinkler annual inspection", "a made-up row", every_years=1, applies=NFPA_25_SPRINKLERS)
    result = applicable(small, rows=(row,))
    assert not result.applies and not result.does_not_apply          # a miss stays a miss: a question, not a "no"
    assert result.questions()[0].text.startswith("Which life safety systems does the association have?")
    # The default profile lists its systems.
    assert profiles.load_profile("mystique").life_safety_systems()


def test_the_profile_names_itself_for_templates():
    identity = community().identity()
    values = identity.values()
    assert values["ASSOCIATION_NAME"] == community().name
    assert values["SIGNATURE"].endswith(community().name)
    assert identity.official_address and identity.official_email
    head = community().letterhead()
    assert head.doc_id and head.footer == identity.official_address
    assert community().email_letterhead().name == head.name_line
    assert community().drive_home().templates


def test_a_profile_without_identity_gets_the_name_and_no_letterhead_doc(small_profile):
    small = community()
    assert small.identity().values() == {"ASSOCIATION_NAME": "Small Community Association", "SIGNER": "Board of Directors",
                                         "SIGNATURE": "Board of Directors\nSmall Community Association"}
    head = small.letterhead()
    assert head.name_line == "SMALL COMMUNITY ASSOCIATION" and not head.doc_id
    assert small.email_letterhead().name == head.name_line
    assert small.drive_home().templates == ""


def test_the_logo_falls_back_to_the_data_folder(tmp_path):
    from jason.community.identity import LetterheadSpec

    head = LetterheadSpec("NAME")
    assert head.logo_path(tmp_path) is None
    (tmp_path / "brand").mkdir()
    (tmp_path / "brand" / "letterhead-logo.png").write_bytes(b"png")
    assert head.logo_path(tmp_path) == tmp_path / "brand" / "letterhead-logo.png"
    own = tmp_path / "own.png"
    own.write_bytes(b"png")
    assert LetterheadSpec("NAME", logo=own).logo_path(tmp_path) == own


def test_general_code_reads_the_letterhead_and_folders_through_the_interface():
    source = repo_root() / "src" / "jason"
    readers = [p.relative_to(source).as_posix() for p in source.rglob("*.py")
               if 'spec_module("templates")' in p.read_text(encoding="utf-8")]
    assert readers == []


def test_jasons_own_subpackages_are_never_a_profile():
    from jason.community.profile import profile_root

    assert profile_root("tasks") is None and profile_root("community") is None
