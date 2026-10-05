"""The contract-terms reader: parties, sections, terms, deliverables, findings, the model review, and the ingest stage.

The contract below is made up; no real party, figure, or section of any association's contract appears here.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jason.community import contract_terms as ct
from jason.community.term_model import (
    BedrockBackend, ModelUnavailable, OllamaBackend, REVIEW_SCHEMA, backend_named, batches, merge, review,
)
from jason.tasks import contract_terms as task

CONTRACT = """MANAGEMENT SERVICE AGREEMENT
This Agreement is made and entered into by and between Acme Community Management, Inc., a California
corporation (hereinafter "MANAGER") and Sample Ridge Community Association (hereinafter "ASSOCIATION").

1.1 Term The term of this Agreement shall be one (1) year from the effective date and will be automatically
renewed unless one Party gives the other Party written notice of termination at least sixty (60) days
prior, but no more than one hundred and twenty (120) days prior, to the end of the term.

3.4 Log MANAGER shall maintain a log of complaints or service requests from members of the
ASSOCIATION, and shall record in the Log the action taken on each.

5.5 Monthly Statements MANAGER shall render to the Board, by the 20th day of each month, a written
statement of receipts and disbursements for the preceding month.

5.6 Transfers Manager is authorized to cause transfers of funds, without regard to dollar amount,
between the Association's accounts.

6.1 Indemnification The ASSOCIATION shall indemnify and hold harmless MANAGER from all claims arising
out of MANAGER'S performance of this Agreement.

6.2 Termination Either party may terminate this Agreement upon sixty (60) days prior written notice.

6.3 Records Within fourteen (14) days of any termination of this Agreement, MANAGER shall deliver to
the ASSOCIATION all records of the ASSOCIATION.

6.7 Claims Any claim must be asserted within twelve (12) months of the time the person knew or should have
known of such claim, otherwise the claim is forfeited.

6.8 Arbitration All disputes between the Association and Manager shall be decided by binding arbitration.

6.9 Attorneys Fees The prevailing party shall be entitled to recover its reasonable attorneys' fees.

6.11 Notices Any notices shall be given in writing and shall be delivered personally or by certified mail.
"""


@pytest.fixture()
def body() -> str:
    return ct.unwrap(CONTRACT)


def test_unwrap_joins_lines_and_keeps_headings(body):
    assert "at least sixty (60) days prior, but no more than one hundred and twenty (120) days prior" in body
    assert "\n3.4 Log MANAGER shall maintain a log of complaints or service requests from members of the ASSOCIATION" in body


def test_parties_from_the_contracts_own_definitions(body):
    parties = ct.defined_parties(body)
    assert parties.names.get("MANAGER", "").startswith("Acme Community Management, Inc.")
    assert parties.party_of("MANAGER") is ct.Party.COUNTERPARTY
    assert parties.party_of("the Board") is ct.Party.ASSOCIATION
    assert parties.party_of("Either party") is ct.Party.EITHER
    assert ct.counterparty_name(body, parties).startswith("Acme Community Management, Inc")


def test_sections_and_list_items():
    text = "3.7 Services The following:\n1 Notice of Meeting\n2 Agenda\n(a) Lettered item\n4.1 Next One here"
    nums = [s.number for s in ct.split_sections(text)]
    assert nums == ["3.7", "3.7[1]", "3.7[2]", "3.7(a)", "4.1"]


def test_the_log_is_a_deliverable_of_the_counterparty(body):
    terms = ct.read_terms(body, source="t")
    log = [t for t in terms if t.section == "3.4"]
    assert log and log[0].topic is ct.Topic.LOGS and log[0].party is ct.Party.COUNTERPARTY and log[0].deliverable
    records = [t for t in terms if t.section == "6.3"][0]
    assert records.deliverable and records.deadline is not None and records.deadline.amount == 14
    statement = [t for t in terms if t.section == "5.5"][0]
    assert statement.deliverable and statement.topic is ct.Topic.REPORTS


def test_findings_name_the_statutes(body):
    codes = {f.code: f for f in ct.findings(ct.read_terms(body, source="t"))}
    assert "notice-window" in codes and "60" in codes["notice-window"].message and "120" in codes["notice-window"].message
    assert codes["transfers-without-limit"].authority == "CIV 5380(b)(6)"
    assert codes["shortened-limitations"].authority == "CCP 337"
    assert codes["arbitration"].authority == "CCP 1281"
    assert codes["fee-shifting"].authority == "CIV 1717"
    assert "one-way-indemnity" in codes
    assert "certified mail" in codes["notice-delivery"].message
    assert "no-dispute-clause" not in codes


def test_window_and_particulars():
    assert ct.window_of("at least sixty (60) days prior, but no more than one hundred and twenty (120) days") == (60, 120)
    assert ct.window_of("not less than 10 nor more than 90 days before") == (10, 90)
    assert ct.window_of("within thirty (30) days") is None
    assert ct.amounts("a fee of $1,250.50 and $75") == (125050, 7500)
    assert "certified mail" in ct.deliveries("sent by certified mail, return receipt requested")


def test_term_round_trips(body):
    term = ct.read_terms(body, source="t")[0]
    assert ct.ContractTerm.from_dict(json.loads(json.dumps(term.to_dict()))).id == term.id


def test_schema_is_closed_for_structured_outputs():
    def walk(s):
        if s.get("type") == "object":
            assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
            for v in s["properties"].values():
                walk(v)
        elif s.get("type") == "array":
            walk(s["items"])
    walk(REVIEW_SCHEMA)


def _sections(body):
    return [(s.start, s.end, s.number, s.caption) for s in ct.split_sections(body)]


def test_merge_keeps_only_grounded_terms(body):
    terms = ct.read_terms(body, source="t")
    answer = {"candidates": [{"n": 1, "term": False, "kind": "statement", "party": "unstated", "topic": "term",
                              "deliverable": False}],
              "missed": [{"quote": "a log of complaints or service requests", "kind": "duty", "party": "counterparty",
                          "topic": "logs", "action": "keep a log", "deadline": "", "recurrence": "", "deliverable": True},
                         {"quote": "words that are not in the contract at all", "kind": "duty", "party": "counterparty",
                          "topic": "logs", "action": "", "deadline": "", "recurrence": "", "deliverable": True}]}
    kept, dropped = merge(json.dumps(answer), terms, body, base=0, source="t", backend="fake", sections=_sections(body),
                          trust="full")
    whys = [d["why"] for d in dropped]
    assert "the model calls it no term" in whys and "its quote is not in the text" in whys
    assert len(kept) == len(terms) - 1           # the log quote overlaps the grammar's own term: not added twice


def test_fill_keeps_the_grammars_reading_and_only_fills_and_adds(body):
    terms = ct.read_terms(body, source="t")
    duty = next(n for n, t in enumerate(terms, 1) if t.kind is ct.TermKind.DUTY and t.party is ct.Party.COUNTERPARTY)
    unstated = next((n for n, t in enumerate(terms, 1) if t.party is ct.Party.UNSTATED), None)
    verdicts = [{"n": duty, "term": False, "kind": "permission", "party": "association", "topic": "fees",
                 "deliverable": False}]
    if unstated:
        verdicts.append({"n": unstated, "term": True, "kind": "statement", "party": "either", "topic": "term",
                         "deliverable": False})
    answer = {"candidates": verdicts, "missed": []}
    kept, dropped = merge(json.dumps(answer), terms, body, base=0, source="t", backend="fake", sections=_sections(body))
    before = terms[duty - 1]
    after = next(t for t in kept if (t.start, t.end) == (before.start, before.end))
    assert (after.kind, after.party, after.topic, after.deliverable) == (before.kind, before.party, before.topic,
                                                                        before.deliverable)
    assert not dropped                            # a modal term is never dropped on the model's word in fill
    if unstated:
        filled = next(t for t in kept if (t.start, t.end) == (terms[unstated - 1].start, terms[unstated - 1].end))
        assert filled.party is ct.Party.EITHER and filled.method == "hybrid:fake"


def test_review_asks_again_when_the_answer_is_not_json(body):
    answers = iter(["not json at all", json.dumps({"candidates": [], "missed": []})] * 10)
    backend = OllamaBackend("tiny", fetch=lambda url, payload: {"message": {"content": next(answers)}})
    terms = ct.read_terms(body, source="t")
    out, dropped = review(body, terms, backend, source="t", sections=_sections(body))
    assert len(out) == len(terms) and not dropped


def test_review_with_a_fake_ollama(body):
    seen = []

    def fetch(url, payload):
        seen.append(payload)
        assert url.endswith("/api/chat") and payload["format"] == REVIEW_SCHEMA and payload["options"]["temperature"] == 0
        return {"message": {"content": json.dumps({"candidates": [], "missed": []})}}

    backend = OllamaBackend("tiny", fetch=fetch)
    terms = ct.read_terms(body, source="t")
    out, dropped = review(body, terms, backend, source="t", sections=_sections(body))
    assert seen and len(out) == len(terms) and not dropped


def test_ollama_backend_is_local_only():
    with pytest.raises(ValueError):
        OllamaBackend("tiny", base_url="http://models.example.com:11434")


def test_bedrock_request_shape_and_refusal():
    calls = []

    class Messages:
        def __init__(self, stop="end_turn"):
            self.stop = stop

        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(stop_reason=self.stop, stop_details=SimpleNamespace(category="cyber"),
                                   content=[SimpleNamespace(type="text", text='{"candidates": [], "missed": []}')])

    ok = BedrockBackend("anthropic.example-model", client=SimpleNamespace(messages=Messages()))
    assert ok.remote and ok.name == "bedrock:anthropic.example-model"
    assert json.loads(ok.ask("prompt", REVIEW_SCHEMA)) == {"candidates": [], "missed": []}
    sent = calls[0]
    assert sent["output_config"]["format"] == {"type": "json_schema", "schema": REVIEW_SCHEMA}
    assert sent["messages"] == [{"role": "user", "content": "prompt"}]
    declined = BedrockBackend("m", client=SimpleNamespace(messages=Messages("refusal")))
    with pytest.raises(ModelUnavailable):
        declined.ask("prompt", REVIEW_SCHEMA)


def test_bedrock_needs_a_region(monkeypatch):
    monkeypatch.delenv("JASON_BEDROCK_REGION", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    with pytest.raises(ModelUnavailable):
        BedrockBackend("m").ask("p", REVIEW_SCHEMA)


def test_backend_named():
    assert isinstance(backend_named("bedrock", model="m", region="us-west-2"), BedrockBackend)
    with pytest.raises(ValueError):
        backend_named("other")


def test_batches_are_whole_sections():
    secs = [(0, 5000, "1", ""), (5000, 9500, "2", ""), (9500, 30000, "3", ""), (30000, 30100, "4", "")]
    assert batches(secs, limit=9000) == [(0, 5000), (5000, 9500), (9500, 30000), (30000, 30100)]
    assert batches([(0, 100, "1", ""), (100, 200, "2", "")], limit=9000) == [(0, 200)]


def test_a_remote_backend_refuses_a_confidential_file(tmp_path):
    remote = BedrockBackend("m", client=SimpleNamespace(messages=None))
    with pytest.raises(task.RemoteRefused):
        task.read(CONTRACT, key="k", backend=remote, confidential=True)


def test_task_read_save_and_markdown(tmp_path):
    reading = task.read(CONTRACT, key="file-sample", name="sample.pdf")
    path = task.save(tmp_path, reading)
    assert path.is_file() and task.load(tmp_path)[0]["counts"]["deliverables"] == len(reading.deliverables) > 0
    text = task.markdown(reading)
    assert "## What the counterparty must produce" in text and "log of complaints" in text
    assert task.summary(reading)["method"] == "grammar"


def test_ingest_stage_reads_contracts_only(tmp_path):
    from jason.tasks.ingest import FileItem, read_terms

    def item(sha, kind):
        return FileItem(source="folder", origin=f"/{sha}", rel=f"box/{sha}.pdf", local=Path(f"/{sha}.pdf"), sha256=sha * 16,
                        size=1, type="application/pdf", kind=kind)

    contract, minutes = item("a", "contract"), item("b", "minutes")
    notes = read_terms([contract, minutes], {contract.sha256: CONTRACT, minutes.sha256: CONTRACT}, tmp_path)
    assert not notes and contract.terms["terms"] > 0 and not minutes.terms
    assert (tmp_path / task.STORE / f"ingest-{contract.key}.json").is_file()
