"""jason's base notice templates against their catalog requirements: every base readable, every unconditional element
shown, and the pre-lien notice reported as having no base."""

from __future__ import annotations

from jason.community.notice_elements import Status
from jason.tasks import notice_templates as nt


def test_every_base_names_a_catalog_requirement_and_reads():
    checks = nt.check_all()
    assert {c.base.requirement for c in checks} >= {"rule-change-proposed", "rule-change-adopted", "discipline-hearing",
                                                     "board-meeting", "annual-policy-statement", "insurance-change",
                                                     "pre-lien-notice"}
    for c in checks:
        assert not c.error or c.error == "no base template", (c.base.requirement, c.error)


def test_the_bases_carry_every_unconditional_element():
    for c in nt.check_all():
        if c.base.load is None:
            continue
        gaps = [f.element for f in c.missing if not f.applies]
        assert not gaps, (c.base.requirement, gaps)


def test_the_pre_lien_notice_has_no_base_yet():
    (c,) = nt.check_all(("pre-lien-notice",))
    assert c.error == "no base template" and all(f.status is Status.MISSING for f in c.findings)


def test_the_hearing_notice_states_the_law_and_names_its_sections():
    (c,) = nt.check_all(("discipline-hearing",))
    cited = {x for s in c.law for x in s.citations}
    assert {"CIV 5850(c)", "CIV 5855(c)", "CIV 5855(f)", "CIV 4935(b)"} <= cited
    assert all(t.startswith("{CITE:CIV#") for s in c.law for t in s.tokens)


def test_the_report_names_the_statute_token_extension():
    lines = nt.report_lines(nt.check_all(("insurance-change",)))
    assert any("statute target" in line for line in lines)


def test_a_rendered_notice_is_checked_by_file(tmp_path):
    path = tmp_path / "notice.md"
    path.write_text("Policy: Example Master Policy. What changed: the deductible went up to $5,000.\n", encoding="utf-8")
    c = nt.check_file(path, "insurance-change")
    assert all(f.status is Status.PRESENT for f in c.findings)
