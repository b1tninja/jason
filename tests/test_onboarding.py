"""The onboarding checklist: a made-up profile shows present, partial, and missing items, and the list names no
association."""

from types import SimpleNamespace

import pytest

from jason.community import Community, community
from jason.community.base import AccountPurpose, BankAccount, BoardRule
from jason.community.books import Book, BookEntry
from jason.community.boundary import instance_terms
from jason.community.onboarding import (
    ITEMS, Context, Group, InBook, Kinds, Method, OnboardingItem, Origin, Private, Record, Setting, Source, Status,
    Store, check, check_item, counts, items, report_dicts, report_markdown, request_markdown,
)
from jason.community.symbols import AssociationRecord, DocumentKind


def _stub_class():
    """A throwaway profile: every abstract member answers nothing; a few facts are filled in."""
    members = {name: (lambda self, *a, **k: ()) for name in Community.__abstractmethods__}
    members.update(
        name="Oakview Example Association", slug="oakview", org_id=0, root=None,
        document_sync_rules=lambda self: {"rules": [], "exclude": []},
        bank_accounts=lambda self: (BankAccount("0001", AccountPurpose.OPERATING, "Example Bank"),),
        board=lambda self: BoardRule(seats=3, minimum=3, maximum=3),
        book_entries=lambda self: (BookEntry("example-declaration", Book.DECL),),
        units=lambda self: ("100 MAIN ST", "102 MAIN ST"),
    )
    return type("Oakview", (Community,), members)


@pytest.fixture
def ctx():
    holding = SimpleNamespace(kind=AssociationRecord.MINUTES, pinned=True, documents=3, gap="")
    empty = SimpleNamespace(kind=AssociationRecord.TAX_RETURN, pinned=False, documents=0,
                            gap="nothing pinned and no classified file")
    stores = {("payhoa.db", "units"): 2, ("payhoa/board-members.json", ""): 3}
    return Context(
        community=_stub_class()(),
        library=({"kind": "declaration", "name": "decl.pdf"}, {"kind": "minutes", "name": "m.pdf"}),
        holdings=(holding, empty),
        count=lambda path, table="": stores.get((path, table), 0),
        private=lambda name: {"0001": {"number": "made-up"}} if name == "bank_accounts" else {},
        settings=SimpleNamespace(payhoa_record_uid="made-up-uid", google_oauth_record_uid=""),
    )


def _by_key(results):
    return {r.item.key: r for r in results}


def test_present_partial_and_missing_on_a_made_up_profile(ctx):
    found = _by_key(check(ctx))
    assert found["declaration"].status is Status.PRESENT          # the book row and a library file
    assert found["bank-accounts"].status is Status.PRESENT        # the spec row and the private numbers
    assert found["board-rule"].status is Status.PRESENT
    assert found["board-roster"].status is Status.PRESENT         # a store on disk
    assert found["minutes"].status is Status.PRESENT              # the 5200 holder has files, and the library one
    assert found["units"].status is Status.PARTIAL                # units and PayHOA units, but no building table
    assert found["management-software"].status is Status.PARTIAL  # the vault record, but no organization id
    assert found["tax-returns"].status is Status.MISSING          # no 5200 holder, no file
    assert found["policies"].status is Status.MISSING
    assert found["tax-id"].status is Status.MISSING and not found["tax-id"].findings
    assert found["tax-id"].evidence == "nothing in jason holds this yet"
    assert "no 5200 record tax_return: nothing pinned" in found["tax-returns"].evidence


def test_every_item_runs_against_a_profile_that_knows_nothing():
    results = check(Context(community=_stub_class()()))
    assert len(results) == len(ITEMS)
    assert all(r.status in (Status.MISSING, Status.PARTIAL, Status.PRESENT) for r in results)
    assert counts(results)["present"] <= 2                        # only what the stub class itself answers


def test_each_check_kind():
    stub = _stub_class()()
    ctx = Context(community=stub, library=({"kind": "map"},), count=lambda p, t="": 5 if p == "x" else 0,
                  private=lambda name: {}, settings=SimpleNamespace(payhoa_record_uid="set"))
    assert Method("bank_accounts").run(ctx).passed
    assert not Method("bank_accounts", minimum=2).run(ctx).passed
    assert Method("bank_accounts", contains="operating").run(ctx).passed
    assert not Method("bank_accounts", contains="reserve").run(ctx).passed
    assert Method("board", field="seats").run(ctx).passed
    assert not Method("no_such_method").run(ctx).passed           # a profile that cannot answer is a miss
    assert Kinds((DocumentKind.MAP,)).run(ctx).passed
    assert not Kinds((DocumentKind.MAP,), minimum=2).run(ctx).passed
    assert not Record(AssociationRecord.MINUTES).run(ctx).passed  # no inventory read
    assert InBook(Book.DECL).run(ctx).passed and not InBook(Book.ARTS).run(ctx).passed
    assert Store("x").run(ctx).passed and not Store("y").run(ctx).passed
    assert not Private("bank_accounts").run(ctx).passed
    assert Setting("payhoa_record_uid").run(ctx).passed and not Setting("google_oauth_record_uid").run(ctx).passed


def test_evidence_never_carries_a_private_value(ctx):
    text = report_markdown(check(ctx), title="Onboarding checklist")
    assert "made-up" not in text and "made-up-uid" not in text
    assert "private facts bank_accounts: 1" in text


def test_items_are_well_formed():
    keys = [i.key for i in ITEMS]
    assert len(keys) == len(set(keys))
    for i in ITEMS:
        assert i.sources and i.origins and i.why and i.fills, i.key
    assert {i.group for i in ITEMS} == set(Group)
    assert {Origin.LAW, Origin.PROFILE, Origin.REQUEST, Origin.FOLLOW_UP, Origin.HANDOFF} <= {o for i in ITEMS for o in i.origins}
    assert all(i.by_person == (not i.fetch) for i in ITEMS)


def test_the_request_list_for_a_prior_manager():
    text = request_markdown(Source.PRIOR_MANAGER, title="Requested from the prior manager")
    assert "- [ ] Owners and tenants, with mailing addresses, email, and phone" in text
    assert "## Insurance" in text
    asked = [i for i in ITEMS if Source.PRIOR_MANAGER in i.sources]
    assert text.count("- [ ]") == len(asked)


def test_dicts_carry_status_and_origin(ctx):
    rows = report_dicts(check(ctx, items(Group.FINANCE)))
    assert {r["group"] for r in rows} == {"finance"}
    assert all(r["status"] in ("present", "partial", "missing") for r in rows)


def test_the_checklist_names_no_association():
    """General code: no term of the active profile (its names, streets, vendors, banks, ids) appears in an item."""
    text = " ".join(f"{i.title} {i.why} {i.fills} {i.note}" for i in ITEMS).casefold()
    named = [t.text for t in instance_terms(community()) if len(t.text) > 3 and t.text.casefold() in text]
    assert not named, named


def test_a_checklist_docs_smart_chips_are_kept_in_its_markdown():
    """A handoff Doc answers each item with linked files (smart chips); without them only the questions are left."""
    from jason.google.docs import document_markdown

    doc = {"title": "Handoff", "body": {"content": [{"paragraph": {"bullet": {}, "elements": [
        {"textRun": {"content": "Bylaws "}},
        {"richLink": {"richLinkProperties": {"title": "Bylaws.pdf", "uri": "https://example.com/x"}}},
        {"textRun": {"content": " / "}},
        {"person": {"personProperties": {"name": "A. Director", "email": "director@example.com"}}},
        {"textRun": {"content": "\n"}},
    ]}}]}}
    assert "- Bylaws [Bylaws.pdf] / A. Director" in document_markdown(doc)


def test_an_item_with_some_checks_passing_is_partial():
    item = OnboardingItem("x", Group.FINANCE, "x", "x", (Source.BOARD,), "x",
                          (Method("bank_accounts"), Method("legal_cases")), (Origin.PROFILE,))
    assert check_item(item, Context(community=_stub_class()())).status is Status.PARTIAL
