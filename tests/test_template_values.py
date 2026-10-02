"""Template values come in layers: the profile's identity and citations first, then the run's own facts."""

from jason.community import community
from jason.community.identity import Identity
from jason.community.template_values import (CitationPurpose, Layer, citation_values, lint, profile_values, resolve)


class _Stub:
    name = "Example Commons Owners Association"

    def __init__(self, citations=None):
        self._citations = citations or {}

    def identity(self):
        return Identity(self.name, official_email="board@example.org")

    def citations(self):
        return self._citations


def test_later_layers_win_and_empty_values_never_override():
    found = resolve(Layer("profile", {"A": "1", "B": "2"}), Layer("run", {"B": "3", "A": ""}))
    assert found.values == {"A": "1", "B": "3"}
    assert found.source == {"A": "profile", "B": "run"}


def test_an_uncited_purpose_prints_general_wording_never_a_guess():
    values = citation_values(_Stub({CitationPurpose.FINES_NOT_LIENS: "Declaration Section 9.1"}))
    assert values["CITE_FINES_NOT_LIENS"] == "Declaration Section 9.1"
    assert values["CITE_CONTINUING_FINES"] == "the association's governing documents"
    assert set(values) == {p.token for p in CitationPurpose}


def test_profile_values_carry_identity_and_citations():
    values = profile_values(_Stub())
    assert values["ASSOCIATION_NAME"] == "Example Commons Owners Association"
    assert values["OFFICIAL_EMAIL"] == "board@example.org"
    assert values["SIGNATURE"] == "Board of Directors\nExample Commons Owners Association"
    assert values["CITE_ELECTION_RULES"] == "the association's election rules"


def test_lint_sorts_tokens_by_where_they_come_from():
    found = lint("notice", ["ASSOCIATION_NAME", "CITE_FINES_NOT_LIENS", "CITE_CONTINUING_FINES", "OWNER_NAME"],
                 _Stub({CitationPurpose.FINES_NOT_LIENS: "Declaration Section 9.1"}))
    assert found.profile == ("ASSOCIATION_NAME", "CITE_FINES_NOT_LIENS")
    assert found.general == ("CITE_CONTINUING_FINES",)
    assert found.run == ("OWNER_NAME",)


def test_the_first_profile_cites_its_own_sections():
    values = profile_values(community())
    assert values["ASSOCIATION_NAME"] == community().name
    cited = community().citations()
    assert cited and all(values[purpose.token] == section for purpose, section in cited.items())


def test_fill_letter_uses_defaults_without_reporting_them_ignored():
    from jason.community.templates import DocumentTemplate, TemplateKind
    from jason.tasks.letters import fill_letter

    class Docs:
        def __init__(self):
            self.sent = []

        def batch_update(self, doc_id, requests):
            self.sent.extend(requests)

        def get(self, doc_id):
            return {"body": {"content": []}}

    class Drive:
        def copy(self, file_id, name, folder):
            return "copy"

    docs = Docs()
    template = DocumentTemplate(TemplateKind.LETTERHEAD, "Letter", "template-id")
    result = fill_letter(Drive(), docs, template, {"SUBJECT": "Pool hours", "NOT_A_TOKEN": "x"}, name="Letter",
                         folder_id="folder", defaults={"ASSOCIATION_NAME": "Example", "DATE": "May 1, 2026"})
    assert result["ignored"] == ["NOT_A_TOKEN"]
    replaced = {r["replaceAllText"]["containsText"]["text"] for r in docs.sent if "replaceAllText" in r}
    assert {"{SUBJECT}", "{DATE}"} <= replaced


def test_every_purpose_is_its_own_member_with_general_wording():
    assert len(list(CitationPurpose)) == len(CitationPurpose.__members__)
    assert all(purpose.general for purpose in CitationPurpose)


def _render(rows, values):
    text = "\n".join(t for _, t in rows)
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def test_the_letter_bodies_name_no_association():
    from jason.community.boundary import instance_terms
    from jason.community.templates import BODIES

    text = "\n".join(t for rows in BODIES.values() for _, t in rows)
    found = [term.text for term in instance_terms(community()) if term.pattern().search(text)]
    assert found == []


def test_a_hearing_notice_prints_each_profiles_own_sections_or_general_wording():
    from jason.community.templates import BODIES, TemplateKind

    rows = BODIES[TemplateKind.HEARING_NOTICE]
    first = _render(rows, profile_values(community()))
    for section in community().citations().values():
        if section in "\n".join(t for _, t in BODIES[TemplateKind.HEARING_NOTICE] + BODIES[TemplateKind.DECISION_NOTICE]):
            raise AssertionError(f"{section} is written into the body")
    assert community().name in first and "{CITE_" not in first
    other = _render(rows, profile_values(_Stub()))
    assert "Example Commons Owners Association" in other
    assert "(the association's governing documents)" in other and "(the association's enforcement policy)" in other


def test_a_packet_template_is_the_profiles_own_else_the_base(tmp_path, monkeypatch):
    from jason.community import profile as profiles
    from jason.tasks import packets

    assert packets.template_file("annual-budget-report.md") == packets.BASE_TEMPLATES / "annual-budget-report.md"
    assert packets.template_file("owner-information-cover.html").parent.name == "packet_templates"
    own = tmp_path / "packet_templates"
    own.mkdir()
    (own / "annual-budget-report.md").write_text("ours", encoding="utf-8")
    monkeypatch.setattr(profiles, "profile_root", lambda name=None: tmp_path)
    assert packets.template_file("annual-budget-report.md").read_text(encoding="utf-8") == "ours"
    assert packets.template_file("flood-notice.html") == packets.BASE_TEMPLATES / "flood-notice.html"
