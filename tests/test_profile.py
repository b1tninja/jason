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
               "src/jason/tasks/mail_links.py", "src/jason/tasks/cross_checks.py", "src/jason/tasks/drive_labels.py",
               "src/jason/community/models/legal_letters.py", "src/jason/community/models/legal_liens.py"}
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


def test_a_counterparty_is_an_instance_term_and_a_reader_finds_it_through_the_sender_directory():
    from jason.community.boundary import COUNTERPARTY_KINDS
    from jason.community.sources import Sender, SourceKind, sender_in, sender_name

    senders = mystique().senders()
    terms = {t.text.casefold(): t.kind for t in instance_terms(mystique())}
    # Every counterparty of every kind is a term, under its kind: its name where it has more than one word, and the
    # words that recognize it.
    for kind in (SourceKind.LAW_FIRM, SourceKind.VENDOR, SourceKind.INSURER, SourceKind.BANK, SourceKind.TITLE_ESCROW,
                 SourceKind.ACCOUNTANT, SourceKind.MANAGER, SourceKind.PROPERTY_MANAGER):
        listed_kind = [s for s in senders if s.kind is kind and s.level is None]
        assert listed_kind, kind
        for s in listed_kind:
            if len(s.name.split()) > 1:
                assert terms.get(s.name.casefold()) in set(COUNTERPARTY_KINDS.values()), s.name
    firms = [s for s in senders if s.kind is SourceKind.LAW_FIRM]
    assert all(terms.get(s.name.casefold()) == "law firm" for s in firms)
    # A government agency, a public utility, and a platform are no association's fact.
    public = [s for s in senders if s.kind in (SourceKind.GOVERNMENT, SourceKind.PLATFORM) or s.level is not None]
    assert public and not any(s.name.casefold() in terms for s in public)

    listed = (Sender("Oak Ridge Management", SourceKind.MANAGER, ("OAK RIDGE MANAGEMENT",)),
              Sender("Elm & Birch LLP", SourceKind.LAW_FIRM, ("ELM & BIRCH",)),
              Sender("Oak Ridge Roofing", SourceKind.VENDOR, ("OAK RIDGE ROOFING",)))
    assert sender_in("ELM &\nBIRCH, LLP\nAttorneys at Law", listed, SourceKind.LAW_FIRM) is listed[1]   # OCR's breaks do not matter
    assert sender_in("Invoice from Oak Ridge Roofing", listed, SourceKind.LAW_FIRM) is None             # a vendor is not a law firm
    assert sender_in("Invoice from Oak Ridge Roofing", listed, SourceKind.LAW_FIRM, SourceKind.VENDOR) is listed[2]
    assert sender_in("Invoice from Oak Ridge Roofing", listed) is listed[2]                             # no kind: any sender
    assert sender_in("A letter from another firm", listed, SourceKind.LAW_FIRM) is None                 # not listed: a miss

    class Listed:
        def senders(self):
            return listed

    assert sender_name("Elm & Birch LLP", Listed(), SourceKind.LAW_FIRM) == "Elm & Birch LLP"
    assert sender_name("Elm & Birch LLP", object(), SourceKind.LAW_FIRM) == ""                          # no directory: a miss


def test_sender_terms_leave_out_public_sources_generic_words_and_ordinary_names():
    from jason.community.boundary import sender_terms
    from jason.community.sources import Level, Sender, SourceKind

    senders = (
        Sender("Elm & Birch LLP", SourceKind.LAW_FIRM, ("BIRCH", "ELM BIRCH", "12 MAIN STREET")),
        Sender("Gather", SourceKind.PROPERTY_MANAGER, ("GATHER HOMES INC",)),            # its name is an ordinary word
        Sender("OakPay", SourceKind.VENDOR, ("OAKPAY",)),                                # a one-word name the words list
        Sender("Oak County Water District", SourceKind.UTILITY, ("OAK COUNTY WATER",), Level.DISTRICT),
        Sender("Oak Valley Water Company", SourceKind.UTILITY, ("OAK VALLEY WATER", "WATER COMPANY")),
        Sender("Franchise Tax Board", SourceKind.GOVERNMENT, ("FRANCHISE TAX BOARD",), Level.STATE),
        Sender("PayHOA", SourceKind.PLATFORM, ("PAYHOA",)),
        Sender("An owner", SourceKind.OWNER, ("REGULAR ASSESSMENT",)),
    )
    found = {(text, kind) for text, kind, _ in sender_terms(senders)}
    assert found == {("Elm & Birch LLP", "law firm"), ("Birch", "law firm"), ("Elm Birch", "law firm"),   # no address
                     ("Gather Homes Inc", "property manager"),                                            # not "Gather"
                     ("OakPay", "vendor"), ("Oakpay", "vendor"),
                     ("Oak Valley Water Company", "utility"), ("Oak Valley Water", "utility")}            # not "Water Company"
    # A word shorter than five characters is left out when the terms are taken.
    assert {text: least for text, _, least in sender_terms(senders)}["Birch"] == 5


def test_a_counterparty_in_a_general_pattern_is_found_unless_the_module_is_its_declared_adapter(tmp_path):
    from jason.community.adapters import Adapter

    code = tmp_path / "src" / "jason"
    code.mkdir(parents=True)
    source = "import re\n\ndef f(t):\n    return re.search(r'Oak Ridge Bank|Elm & Birch|Oakridge', t)\n"
    (code / "bank_statement.py").write_text(source, encoding="utf-8")
    (code / "letters.py").write_text(source, encoding="utf-8")
    terms = (Term("Oak Ridge Bank", "bank"), Term("Elm & Birch", "law firm"), Term("Oakridge", "name"))
    both = ["Elm & Birch", "Oak Ridge Bank", "Oakridge"]
    # Undeclared, the bank's name is a fact in both modules.
    assert scan_code(tmp_path, terms, adapters=()) == {"src/jason/bank_statement.py": both, "src/jason/letters.py": both}
    # Declared, it is the layout's signature in that module only. The declaration allows no other vendor, no other
    # kind of term, and the vendor nowhere else.
    declared = (Adapter("src/jason/bank_statement.py", "Oak Ridge Bank", "checking statements"),)
    assert scan_code(tmp_path, terms, adapters=declared) == {"src/jason/bank_statement.py": ["Elm & Birch", "Oakridge"],
                                                             "src/jason/letters.py": both}
    # A declaration cannot excuse the association's own name, whatever it calls its vendor.
    named = (Adapter("src/jason/bank_statement.py", "Oakridge", "anything"),)
    assert "Oakridge" in scan_code(tmp_path, terms, adapters=named)["src/jason/bank_statement.py"]


def test_a_document_names_a_vendor_only_in_a_code_span_that_points_at_its_adapter(tmp_path):
    from jason.community.adapters import Adapter

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "prose.md").write_text("The association banks at Oak Ridge Bank.\n", encoding="utf-8")
    (docs / "pointer.md").write_text("The `oak-statement` model reads the layout of `Oak Ridge Bank`.\n", encoding="utf-8")
    (docs / "firm.md").write_text("The reader looks for `Elm & Birch` in the head.\n", encoding="utf-8")
    terms = (Term("Oak Ridge Bank", "bank"), Term("Elm & Birch", "law firm"))
    declared = (Adapter("src/jason/bank_statement.py", "Oak Ridge Bank", "checking statements"),)
    # In prose the vendor is the association's fact. In a code span it points at the declared adapter. A counterparty
    # with no adapter is found in a code span too.
    assert scan(tmp_path, terms, adapters=declared) == {"docs/prose.md": ["Oak Ridge Bank"], "docs/firm.md": ["Elm & Birch"]}
    assert set(scan(tmp_path, terms, adapters=())) == {"docs/prose.md", "docs/pointer.md", "docs/firm.md"}


def test_every_adapter_is_listed_and_borne_out(tmp_path):
    from jason.community.adapters import ADAPTERS, Adapter, adapters, stale, unlisted
    from jason.community.boundary import adapter_problems

    # The declarations in the repository: each module exists and names its vendor, and docs/adapters.md lists each.
    assert adapter_problems(repo_root()) == []
    assert len(adapters()) > len(ADAPTERS)                      # the invoice layouts are declared by their own rows
    # A vendor's name is matched by whole words: part of a name is that vendor, part of a word is not.
    row = Adapter("src/jason/bank_statement.py", "Oak Ridge Bank", "checking statements", signature=("Oak Ridge Bank, N.A.",))
    assert row.names("Oak Ridge") and row.names("oak ridge bank") and not row.names("Ridgeline") and not row.names("Oak Ridge Roofing")
    # A declaration whose module is gone, or no longer names the vendor, is stale; one the document leaves out is unlisted.
    code = tmp_path / "src" / "jason"
    code.mkdir(parents=True)
    (code / "bank_statement.py").write_text("import re\n\nBANK = re.compile(r'Elm Bank')\n", encoding="utf-8")
    gone = Adapter("src/jason/missing.py", "Oak Ridge Bank", "checking statements")
    assert stale(tmp_path, (row, gone)) == ["src/jason/bank_statement.py: does not name Oak Ridge Bank",
                                             "src/jason/missing.py: no such module (adapter for Oak Ridge Bank)"]
    (code / "bank_statement.py").write_text("import re\n\nBANK = re.compile(r'Oak Ridge Bank')\n", encoding="utf-8")
    assert stale(tmp_path, (row,)) == []
    assert unlisted("| `Oak Ridge Bank` | `src/jason/bank_statement.py` | checking statements |", (row,)) == []
    assert unlisted("Oak Ridge Bank is read by src/jason/bank_statement.py.", (row,)) == ["Oak Ridge Bank (src/jason/bank_statement.py)"]
    assert adapter_problems(tmp_path, (row,)) == ["docs/adapters.md: does not list Oak Ridge Bank (src/jason/bank_statement.py)"]


def test_no_general_reader_names_a_law_firm():
    """The readers that named the association's law firms (2026-10-04) take them from the sender directory, and
    neither baseline holds a counterparty of any kind: a new one cannot hide among old entries."""
    import json

    from jason.community.boundary import ADAPTER_KINDS

    firms = tuple(t for t in instance_terms(community()) if t.kind == "law firm")
    assert firms
    assert scan_code(repo_root(), firms) == {} and scan(repo_root(), firms) == {}
    counterparties = {t.text.casefold() for t in instance_terms(community()) if t.kind in ADAPTER_KINDS}
    for path in (baseline_path(), code_baseline_path()):
        held = {term.casefold() for found in json.loads(path.read_text(encoding="utf-8")).values() for term in found}
        assert not held & counterparties, path.name


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
