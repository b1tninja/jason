from jason import api
from jason.community import intake
from jason.community.intake import Ask, AskKind
from jason.mcp import governance
from jason.mcp.server import ALL_TOOLS, tools_for


def test_the_governance_profile_serves_the_tools_and_the_api_exports_them():
    names = [t.__name__ for t in tools_for("governance")]
    assert names == [t.__name__ for t in governance.TOOLS]
    assert set(names) <= {t.__name__ for t in ALL_TOOLS}
    assert len(tools_for("board")) == 43                       # the board's set, with the two response tools
    assert set(api.__all__) == set(names) | {"read_record", "record_resources", "new_responses", "outstanding_responses", "response", "followups", "campaign_status"}   # the tools, and the resources
    assert api.member_requests is governance.member_requests


def test_an_intake_answer_needs_a_person_and_writes_only_the_queue(tmp_path):
    ask = Ask(intake.ask_id(AskKind.CLASSIFY, "library:x.pdf", ""), AskKind.CLASSIFY, "library:x.pdf", "Which kind?")
    intake.save(tmp_path, [ask])
    assert "error" in api.answer_intake_question(ask.id, "contract", by="", data_dir=tmp_path)
    done = api.answer_intake_question(ask.id, "contract", by="A Person", data_dir=tmp_path)
    assert done["status"] == "answered" and done["answeredBy"] == "A Person"
    assert api.intake_questions(status="answered", data_dir=tmp_path)["questions"][0]["answer"] == "contract"
    assert sorted(p.name for p in tmp_path.rglob("*") if p.is_file()) == ["asks.json"]


def test_a_completion_needs_a_person_evidence_and_a_known_assignment(tmp_path):
    assert "error" in api.record_completion("no-such-key", "2026-10-20", "A Person", "minutes", data_dir=tmp_path)
    assert "error" in api.record_completion("monthly-financial-review", "2026-10-20", "", "", data_dir=tmp_path)
    row = api.record_completion("monthly-financial-review", "2026-10-20", "A Person", "minutes 2026-10-20, item 4",
                                data_dir=tmp_path)["recorded"]
    assert row["key"] == "monthly-financial-review" and row["due"] == "2026-10-20"


def test_misses_are_reported_not_raised(tmp_path):
    assert "error" in api.living_document("no-such-document", data_dir=tmp_path)
    assert "error" in api.notice_requirements("no-such-notice")
    assert "error" in api.notice_delivery("no-such-notice", data_dir=tmp_path)
    assert "error" in api.document_conflicts(area="no-such-area")
    assert api.notice_requirements()["requirements"]
    assert "error" in api.request_kinds_measure(data_dir=tmp_path)          # no gold set here


def test_requests_carry_leads_only_when_asked(tmp_path):
    plain = api.member_requests(include_email=False, data_dir=tmp_path)
    led = api.member_requests(include_email=False, sources=True, data_dir=tmp_path)
    assert all("sources" not in r for r in plain["requests"])
    assert "lead" in led["caveat"] and "lead" not in plain["caveat"]
