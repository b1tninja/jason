"""Profiles: jason loads one association's specification by name; the general docs name none of its facts."""

import sys
import textwrap

import pytest

from jason.community import Community, community, mystique, profile_name
from jason.community import profile as profiles
from jason.community.boundary import Term, baseline_path, compare, instance_terms, repo_root, scan


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
