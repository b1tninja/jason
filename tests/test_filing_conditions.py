"""A filing rule's test as an applicability condition: the same answers as before, and a filing that explains itself.

Every sender and rule here is made up ("Acme Fire", "Example Law"); none is an association's.
"""

from __future__ import annotations

import itertools

from jason.community.applicability import ALWAYS, AllOf, Answer, Fact, In, Is, Source, facts_tested, filing_facts
from jason.community.base import EmailFiling, FilingRule
from jason.community.sources import Sender, SourceKind
from jason.community.symbols import DocumentKind

FIRE = Sender("Acme Fire", SourceKind.VENDOR, ("ACME FIRE",))
ROOF = Sender("Acme Roofing", SourceKind.VENDOR, ("ACME ROOFING",))
LAW = Sender("Example Law", SourceKind.LAW_FIRM, ("EXAMPLE LAW",))
CPA = Sender("Example CPA", SourceKind.ACCOUNTANT, ("EXAMPLE CPA",))
SENDERS = (FIRE, ROOF, LAW, CPA)
KINDS = (DocumentKind.INSPECTION_REPORT, DocumentKind.INVOICE, DocumentKind.PROPOSAL, None)

RULES = (
    FilingRule(DocumentKind.INSPECTION_REPORT, ("Reports", "Fire"), senders=("Acme Fire",)),
    FilingRule(DocumentKind.INSPECTION_REPORT, ("Reports", "Roofs"), senders=("Acme Roofing", "Acme Fire")),
    FilingRule(DocumentKind.INVOICE, ("Financials", "{year}", "Invoices", "{vendor}")),
    FilingRule(None, ("Legal", "{vendor}"), source_kinds=(SourceKind.LAW_FIRM,)),
    FilingRule(None, ("Advisers", "{vendor}"), source_kinds=(SourceKind.LAW_FIRM, SourceKind.ACCOUNTANT)),
    FilingRule(DocumentKind.PROPOSAL, ("Proposals",), senders=("Acme Fire",), source_kinds=(SourceKind.VENDOR,)),
    FilingRule(None, ("Everything",)),
)
FILING = EmailFiling(root="ROOT", rules=RULES)


def _plain(rule: FilingRule, sender: Sender, kind) -> bool:
    """The test as it was written before it became a condition."""
    if rule.kind is not None and rule.kind is not kind:
        return False
    if rule.senders and sender.name not in rule.senders:
        return False
    return not rule.source_kinds or sender.kind in rule.source_kinds


def test_takes_answers_as_the_plain_test_did_for_every_rule_sender_and_kind():
    for rule, sender, kind in itertools.product(RULES, SENDERS, KINDS):
        assert rule.takes(sender, kind) is _plain(rule, sender, kind), (rule, sender.name, kind)


def test_the_condition_names_the_kind_the_sender_and_the_source():
    by_name, either, any_invoice, law, advisers, both, anything = (r.condition() for r in RULES)
    assert by_name == AllOf(Is(Fact.DOCUMENT_KIND, DocumentKind.INSPECTION_REPORT), Is(Fact.SENDER, "Acme Fire"))
    assert by_name.describe() == "the document is an inspection report and the sender is Acme Fire"
    assert either.parts[1] == In(Fact.SENDER, frozenset({"Acme Roofing", "Acme Fire"}))
    assert any_invoice == Is(Fact.DOCUMENT_KIND, DocumentKind.INVOICE)
    assert law == Is(Fact.SOURCE_KIND, SourceKind.LAW_FIRM)
    assert law.describe() == "the sender's kind of source is law firm"
    assert advisers.describe() == "the sender's kind of source is one of: accountant, law firm"
    assert facts_tested(both) == {Fact.DOCUMENT_KIND, Fact.SENDER, Fact.SOURCE_KIND}
    assert anything is ALWAYS and RULES[-1].takes(CPA, None)


def test_a_verdict_names_the_facts_and_where_each_comes_from():
    verdict = RULES[0].verdict(FIRE, DocumentKind.INSPECTION_REPORT)
    assert verdict.answer is Answer.APPLIES
    assert [(v.fact, v.source) for v in verdict.deciding] == [(Fact.DOCUMENT_KIND, Source.DOCUMENT),
                                                              (Fact.SENDER, Source.PROFILE)]
    assert verdict.explain().splitlines() == [
        "applies: the document is an inspection report and the sender is Acme Fire",
        "  decided by the document: inspection report (document, the classifier)",
        "  decided by the sender: Acme Fire (profile, Community.senders())"]
    other = RULES[0].verdict(ROOF, DocumentKind.INSPECTION_REPORT)
    assert other.answer is Answer.DOES_NOT_APPLY and [v.fact for v in other.deciding] == [Fact.SENDER]


def test_an_unclassified_document_is_a_miss_for_a_rule_that_names_a_kind():
    assert Fact.DOCUMENT_KIND not in filing_facts(FIRE, None)
    verdict = RULES[2].verdict(FIRE, None)                                  # any sender's invoice
    assert verdict.answer is Answer.UNDETERMINED and verdict.missing == (Fact.DOCUMENT_KIND,)
    assert not RULES[2].takes(FIRE, None)                                   # undetermined is not taken
    assert RULES[3].takes(LAW, None)                                        # a rule with no kind takes it by its source


def test_a_senders_name_is_matched_as_written():
    shouting = Sender("ACME FIRE", SourceKind.VENDOR, ("ACME FIRE",))
    assert not RULES[0].takes(shouting, DocumentKind.INSPECTION_REPORT)


def test_the_filing_explains_where_a_document_went_and_why():
    path, rule = FILING.path_for(ROOF, DocumentKind.INSPECTION_REPORT, 2026)
    assert path == ("Reports", "Roofs") and rule is RULES[1]
    assert FILING.explain(ROOF, DocumentKind.INSPECTION_REPORT).splitlines() == [
        "applies: the document is an inspection report and the sender is one of: Acme Fire, Acme Roofing",
        "  decided by the document: inspection report (document, the classifier)",
        "  decided by the sender: Acme Roofing (profile, Community.senders())"]
    none = EmailFiling(root="ROOT", rules=RULES[:3])
    path, rule = none.path_for(LAW, None, 2026)
    assert rule is None and path == ("Vendors", "Example Law", "2026")
    assert none.explain(LAW, None).splitlines() == [
        "no rule applies (3 asked, in order): the fallback folder",
        "  known: the sender: Example Law (profile, Community.senders()); the sender's kind of source: law firm "
        "(profile, Community.senders())",
        "  missing: the document's kind (the classifier gave none)"]


def test_the_plan_carries_the_explanation_and_prints_it_only_when_asked():
    from jason.tasks.vendor_files import Attachment, VendorPlan, plan_lines

    att = Attachment("Acme Fire", "m1", "2026-03-01T00:00:00+00:00", "Acme <a@acme.test>", "Report", "report.pdf", "s", "m",
                     10, kind="inspection_report", action="file", where="Reports/Fire",
                     rule="inspection_report from Acme Fire", why=FILING.explain(FIRE, DocumentKind.INSPECTION_REPORT))
    plan = VendorPlan("Acme Fire", "from:acme.test", 1, [att])
    plain = plan_lines(plan)
    assert len(plain) == 2 and plain[1].endswith("[inspection_report from Acme Fire]")
    told = plan_lines(plan, why=True)
    assert told[:2] == plain and told[2] == "      applies: the document is an inspection report and the sender is Acme Fire"
    assert told[3].startswith("        decided by the document: inspection report")


def test_the_profiles_rows_are_conditions_too():
    from jason.community import community

    filing = community().email_filing()
    assert filing is not None and filing.rules
    for rule in filing.rules:
        assert facts_tested(rule.condition()) <= {Fact.DOCUMENT_KIND, Fact.SENDER, Fact.SOURCE_KIND}
        assert rule.condition().describe()
