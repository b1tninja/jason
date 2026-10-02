"""The owner information cycle: each owner's standing, and the PayHOA tag writes planned and performed, never over an
election already in PayHOA."""

from datetime import date

from jason.community.forms import AnswerCycle, FormAnswers, FormKey
from jason.community.tags import PayhoaTag, TagPurpose, TagScope
from jason.tasks.member_preferences import match, unit_owners
from jason.tasks.notice_delivery import plan
from jason.tasks.owner_info import OwnerStatus, execute, ledger, plan_writes, summary

M, U = TagScope.MEMBER, TagScope.UNIT
TAGS = (PayhoaTag("Notices by Email", M, TagPurpose.NOTICE_DELIVERY, "email"),
        PayhoaTag("Notices by Mail", M, TagPurpose.NOTICE_DELIVERY, "mail"),
        PayhoaTag("Owner Info 2027", M, TagPurpose.ANSWERED, "2027"),
        PayhoaTag("Rental", U, TagPurpose.OCCUPANCY, "Rented out", answer="occupancy"))
CYCLE = AnswerCycle(2027, date(2026, 10, 1), return_by=date(2026, 10, 23), reports_mailed=date(2026, 12, 1))
TODAY = date(2026, 10, 10)


def _unit(uid, label, members, tags=()):
    return {"id": uid, "label": label, "title": label, "tags": [{"tag": t} for t in tags],
            "owners": [{"membershipId": m, "deletedAt": None} for m in members]}


def _person(pid, name, tags=(), email=""):
    given, family = name.split(" ", 1)
    return {"id": pid, "email": email, "tags": [{"tag": t, "id": 9000 + pid} for t in tags],
            "profile": {"givenNames": given, "familyName": family, "updatedAt": "2024-01-14T00:00:00Z"}}


UNITS = [_unit(1, "3007 ENCHANTED WALK", [10]), _unit(2, "3009 ENCHANTED WALK", [11], ["Rental"]),
         _unit(3, "3011 ENCHANTED WALK", [12]), _unit(4, "3013 ENCHANTED WALK", [13])]
PEOPLE = [_person(10, "Pat Lee"), _person(11, "Sam Roe", ["Notices by Email"], "sam@example.com"),
          _person(12, "Ann Doe"), _person(13, "Bo Kim")]
ANSWERS = [
    # an earlier answer (2025) from a current owner: recorded, not applied
    FormAnswers(FormKey.OWNER_INFO, {"unit-address": "3007 Enchanted Walk", "delivery": ["By email"],
                                     "occupancy": ["Owner-occupied"], "mailing-address": "PO Box 1"},
                source="google:a", submitted="2025-06-01T00:00:00Z",
                contacts=[{"role": "owner", "name": "Pat Lee"}]),
    # this cycle, signed in through PayHOA: applied
    FormAnswers(FormKey.OWNER_INFO, {"delivery": ["By mail"], "occupancy": ["Owner-occupied"]}, source="payhoa:77",
                submitted="2026-10-05T00:00:00Z", membership_id=11, unit_id=2),
]


def _setup():
    owners = unit_owners(UNITS, PEOPLE)
    matched = match(ANSWERS, owners, TAGS, cycle=CYCLE, today=TODAY)
    found = plan(UNITS, PEOPLE, TAGS)
    return found, ledger(found, matched, TAGS, CYCLE)


def test_each_owner_stands_where_the_record_puts_them():
    found, rows = _setup()
    status = {r.membership_id: r.status for r in rows}
    assert status == {10: OwnerStatus.EARLIER_ANSWER, 11: OwnerStatus.ANSWERED, 12: OwnerStatus.NO_ELECTION,
                      13: OwnerStatus.NO_ELECTION}
    sam = next(r for r in rows if r.membership_id == 11)
    assert {"+Notices by Mail (member)", "-Notices by Email (member)", "-Rental (unit)",
            "+Owner Info 2027 (member)"} <= set(sam.actions)                     # this cycle's answer, applied in full
    report = summary(rows, CYCLE, TODAY)
    assert [d["daysLeft"] for d in report["deadlines"]] == [-9, 13, 22, 52]      # entry deadline: November 1


def test_the_writes_follow_the_ledger_and_are_tags_only():
    found, rows = _setup()
    writes = plan_writes(rows, found, TAGS)
    kinds = {(w.kind, w.target, w.value.split(".")[0]) for w in writes}
    assert ("member tag +", 12, "Notices by Mail") in kinds and ("member tag +", 13, "Notices by Mail") in kinds
    assert ("member tag +", 10, "Notices by Mail") in kinds                     # an earlier answer is not an election
    assert ("member tag -", 11, "Notices by Email") in kinds and ("unit tag -", 2, "Rental") in kinds
    assert {w.kind for w in writes} <= {"member tag +", "member tag -", "unit tag +", "unit tag -"}   # tags only


def test_an_earlier_written_election_from_the_owners_own_email_sets_the_tags():
    from jason.community.forms import EarlierElections

    people = [_person(10, "Pat Lee", email="pat@example.com"), *PEOPLE[1:]]
    earlier = FormAnswers(FormKey.OWNER_INFO, {"unit-address": "3007 Enchanted Walk", "delivery": ["By email"]},
                          source="google:a", submitted="2025-06-01T00:00:00Z",
                          contacts=[{"role": "owner", "name": "P Lee", "email": "PAT@example.com"}])
    rule = EarlierElections(max_age_days=730)

    def rows_for(people_rows, answer, today=TODAY, rule=rule):
        matched = match([answer], unit_owners(UNITS, people_rows), TAGS, cycle=CYCLE, today=today)
        found = plan(UNITS, people_rows, TAGS)
        return found, ledger(found, matched, TAGS, CYCLE, earlier=rule, today=today)

    found, rows = rows_for(people, earlier)
    pat = next(r for r in rows if r.membership_id == 10)
    assert pat.status is OwnerStatus.EARLIER_ELECTION
    writes = plan_writes(rows, found, TAGS, earlier=rule, today=TODAY)
    mine = {(w.kind, w.value.split(".")[0]) for w in writes if w.target == 10}
    assert ("member tag +", "Notices by Email") in mine and ("member tag +", "Notices by Mail") not in mine
    assert not any(w.value == "Owner Info 2027" for w in writes)                   # not answered until confirmed

    _, by_name = rows_for(PEOPLE, ANSWERS[0])                                      # matched by name only
    assert next(r for r in by_name if r.membership_id == 10).status is OwnerStatus.EARLIER_ANSWER
    _, too_old = rows_for(people, earlier, today=date(2027, 7, 1))                 # past two years
    assert next(r for r in too_old if r.membership_id == 10).status is OwnerStatus.EARLIER_ANSWER
    tagged_people = [_person(10, "Pat Lee", ["Notices by Mail"], email="pat@example.com"), *PEOPLE[1:]]
    _, newer = rows_for(tagged_people, earlier)                                     # an election already in PayHOA
    assert next(r for r in newer if r.membership_id == 10).status is OwnerStatus.ELECTED
    _, off = rows_for(people, earlier, rule=EarlierElections(apply=False))
    assert next(r for r in off if r.membership_id == 10).status is OwnerStatus.EARLIER_ANSWER


class _Client:
    def __init__(self):
        self.calls = []

    def update_member_tags(self, org, ids, *, add=(), remove=()):
        self.calls.append(("member", tuple(ids), tuple(add), tuple(remove)))

    def add_unit_tag(self, org, ids, tag):
        self.calls.append(("unit +", tuple(ids), tag))

    def remove_unit_tag(self, org, ids, tag):
        self.calls.append(("unit -", tuple(ids), tag))



def test_execute_batches_adds_and_removes_by_row():
    found, rows = _setup()
    writes = plan_writes(rows, found, TAGS)
    client = _Client()
    tag_rows = {int(p["id"]): p["tags"] for p in PEOPLE}
    done = execute(client, 27889, writes, member_tag_rows=tag_rows, batch=2)
    assert ("member", (11,), (), (9011,)) in client.calls                             # removed by the member's tag row
    assert ("unit -", (2,), "Rental") in client.calls
    adds = [c for c in client.calls if c[0] == "member" and c[2] == ("Notices by Mail",)]
    assert all(len(c[1]) <= 2 for c in adds)                                          # batched
    assert done["member tag -"] == 1 and "field" not in done


def test_this_cycles_text_and_choice_answers_set_tags_not_fields():
    tags = TAGS + (PayhoaTag("Legal Representative", M, TagPurpose.LEGAL_REPRESENTATIVE),
                   PayhoaTag("Membership List Opt-Out", M, TagPurpose.MEMBERSHIP_LIST, "Opt me out", answer="membership-list"))
    answer = FormAnswers(FormKey.OWNER_INFO, {"delivery": ["By mail"], "representative-name": "A. Agent",
                                              "representative-phone": "555-0100",
                                              "membership-list": ["Opt me out"], "second-email": "b@example.com"},
                         source="payhoa:78", submitted="2026-10-05T00:00:00Z", membership_id=12, unit_id=3)
    matched = match([answer], unit_owners(UNITS, PEOPLE), tags, cycle=CYCLE, today=TODAY)
    found = plan(UNITS, PEOPLE, tags)
    ann = next(r for r in ledger(found, matched, tags, CYCLE) if r.membership_id == 12)
    assert "+Membership List Opt-Out (member)" in ann.actions
    assert not any(a.startswith("+Legal Representative") for a in ann.actions)     # not a tag on the owner
    assert any("legal representative as a person record" in a for a in ann.actions)  # their own record, by a person
    assert any("additional owner record" in a for a in ann.actions)                 # a second address: a record, by a person
    assert not any("A. Agent" in a for a in ann.actions)                            # the text stays in the submission
    again = FormAnswers(FormKey.OWNER_INFO, {"membership-list": ["Include me"]}, source="payhoa:79",
                        submitted="2026-10-06T00:00:00Z", membership_id=11, unit_id=2)
    people = [*PEOPLE[:1], _person(11, "Sam Roe", ["Notices by Email", "Membership List Opt-Out"], "sam@example.com"), *PEOPLE[2:]]
    m = next(x for x in match([again], unit_owners(UNITS, people), tags, cycle=CYCLE, today=TODAY) if x.latest)
    assert "-Membership List Opt-Out (member)" in m.tag_changes                      # another option takes it off


def test_records_kept_for_an_owner_are_never_owners():
    tags = TAGS + (PayhoaTag("Legal Representative", M, TagPurpose.LEGAL_REPRESENTATIVE),)
    units = [_unit(1, "3007 ENCHANTED WALK", [10, 30])]
    people = [_person(10, "Pat Lee", email="pat@example.com"),
              _person(30, "Rae Agent", ["Legal Representative", "Notices by Mail"], "pat@example.com")]
    assert [o.membership_id for u in unit_owners(units, people, tags=tags) for o in u.owners] == [10]   # not matched
    found = plan(units, people, tags)
    assert [o.membership_id for o in found.owners] == [10] and [r.membership_id for r in found.representatives] == [30]
    from jason.tasks.notice_delivery import audit

    assert any(row["member"] == 30 and row["change"] == "remove the delivery tag" for row in audit(found, tags))


def test_the_email_names_the_unit_by_its_street_line_not_a_full_address():
    from jason.tasks.owner_send import EmailHandler

    handler = EmailHandler.__new__(EmailHandler)
    handler.message = '<p>Please answer for <span class="placeholder">{unit address}</span> by Friday.</p>'
    handler.google_form = None
    out = handler.message_for("NP27E-XXXXX-XX", "5651 WHIMSICAL LN")
    assert "for 5651 Whimsical Ln by" in out and "{unit address}" not in out and "placeholder" not in out
    # without a unit, PayHOA's own placeholder is left for it to fill
    assert "{unit address}" in handler.message_for("NP27E-XXXXX-XX")


def test_the_subject_names_the_unit_for_owners_and_managers_of_several():
    from jason.tasks.owner_send import EmailHandler

    handler = EmailHandler.__new__(EmailHandler)
    handler.subject = "Owner information request for {unit address}"
    assert handler.subject_for("NP27E-XXXXX-XX", "5651 WHIMSICAL LN") == \
        "Owner information request for 5651 Whimsical Ln [Ref NP27E-XXXXX-XX]"
    handler.subject = "Owner information request"
    assert handler.subject_for("NP27E-XXXXX-XX", "5651 WHIMSICAL LN") == "Owner information request [Ref NP27E-XXXXX-XX]"


def test_a_reply_by_the_messages_email_link_carries_the_copys_reference():
    from jason.tasks.owner_send import EmailHandler

    handler = EmailHandler.__new__(EmailHandler)
    handler.message = '<a href="mailto:hoa@example.com?subject=Owner%20Information%20Form%202027">hoa@example.com</a>'
    handler.google_form = None
    out = handler.message_for("NP27E-XXXXX-XX")
    assert 'href="mailto:hoa@example.com?subject=Owner%20Information%20Form%202027%20%5BRef%20NP27E-XXXXX-XX%5D"' in out


def test_each_emailed_copy_links_to_the_form_with_its_own_unit():
    from jason.tasks.owner_send import EmailHandler

    handler = EmailHandler.__new__(EmailHandler)
    handler.message = ('<a href="https://app.payhoa.com/app/forms/114542">Answer</a> or '
                       '<a href="https://app.payhoa.com/app/forms/114542">again</a>')
    handler.google_form = None
    out = handler.message_for("NP27E-XXXXX-XX", "5651 WHIMSICAL LN", 700001)
    assert out.count("https://app.payhoa.com/app/forms/114542;unitId=700001") == 2
    assert 'forms/114542"' not in out


def test_an_unconfirmed_address_gets_the_owner_information_request_and_nothing_else():
    from jason.community.notices import NoticeKind, NoticeRule
    from jason.tasks.notice_delivery import audience

    tags = TAGS + (PayhoaTag("Additional Deliveries", M, TagPurpose.SECONDARY_CONTACT),
                   PayhoaTag("Unconfirmed Address", M, TagPurpose.UNCONFIRMED))
    units = [_unit(1, "3007 ENCHANTED WALK", [10, 20, 21])]
    county = _person(20, "Pat Lee", ["Additional Deliveries", "Unconfirmed Address"])
    county["profile"]["address1"] = "12 Elm St"
    second = _person(21, "Pat Lee", ["Additional Deliveries"])
    second["profile"]["address1"] = "PO Box 1"
    found = plan(units, [_person(10, "Pat Lee"), county, second], tags)
    request = NoticeRule("owner-info-solicitation", "x", "CIV 4041(b)", NoticeKind.INDIVIDUAL, courtesy_email=True,
                         secondary_copies=True, unconfirmed_copies=True)
    report = NoticeRule("annual-budget-report", "x", "CIV 5300", NoticeKind.INDIVIDUAL, secondary_copies=True)
    assert sorted(s.membership_id for s in audience(found, request, tags).secondary) == [20, 21]
    assert [s.membership_id for s in audience(found, report, tags).secondary] == [21]        # the confirmed one only
    assert [o.membership_id for o in found.owners] == [10]                                    # neither is an owner


def test_a_payhoa_request_is_completed_only_once_jason_has_recorded_all_of_it():
    from types import SimpleNamespace

    from jason.tasks.owner_info import OwnerInfo, OwnerStatus, ToComplete, Write, complete, to_complete

    def row(mid, uid, source, record=None, choices=None, latest=True):
        answer = SimpleNamespace(source=source, latest=latest, record=record or {}, choices=choices or {})
        return OwnerInfo(uid, f"unit {uid}", mid, f"owner {mid}", OwnerStatus.ANSWERED, "mail", answer)

    rows = [row(10, 1, "payhoa:501"),                                        # tags only: complete
            row(11, 2, "payhoa:502"),                                        # its tag not yet written: open
            row(12, 3, "payhoa:503", record={"secondary delivery": "given"}),   # a person enters it: open
            row(13, 4, "payhoa:504", choices={"representative-name": "given"}),
            row(14, 5, "google:x"),                                          # not a PayHOA request
            row(15, 6, "payhoa:506", latest=False)]                          # superseded by a later answer
    writes = [Write("member tag +", 11, "unit 2: owner 11", "Notices by Email", "this year's answer")]
    items = {i.submission_id: i.left for i in to_complete(rows, writes)}
    assert items[501] == [] and items[502] == ["member tag + Notices by Email"]
    assert items[503] == ["a person enters the secondary delivery"]
    assert items[504] == ["a person enters the legal representative"] and set(items) == {501, 502, 503, 504}

    calls = []
    client = SimpleNamespace(set_submission_complete=lambda org, sid: calls.append(("complete", sid)),
                             add_submission_comment=lambda sid, msg, **kw: calls.append(("comment", sid, kw)))
    complete(client, 27889, ToComplete(501, "unit 1", "owner 10", 10), "<p>Thank you.</p>")
    assert calls == [("complete", 501), ("comment", 501, {"notify_admins": False, "recipient_member_ids": [10]})]


def test_same_as_my_unit_needs_a_person_only_when_payhoa_mails_elsewhere():
    from jason.tasks.member_preferences import Owner, _same_as, _to_record

    answers = {"mailing-address": _same_as("mailing-address"), "unit-address": "3010 EXAMPLE WALK"}
    at_unit = Owner(1, "A", "a@example.com", mailing="3010 Example Walk")
    record, notes = _to_record(answers, at_unit, "2026-10-02")
    assert "mailing address" not in record and any("as PayHOA has it" in n for n in notes)
    record, _ = _to_record(answers, Owner(1, "A", "a@example.com"), "2026-10-02")          # no address on file
    assert "mailing address" not in record
    record, _ = _to_record(answers, Owner(1, "A", "a@example.com", mailing="1 Other St"), "2026-10-02")
    assert "a person changes it" in record["mailing address"]


def test_only_me_is_the_operators_unit_from_env_and_an_address_start_still_works(monkeypatch):
    from types import SimpleNamespace

    from jason.commands import owner_info
    from jason.config import Settings

    monkeypatch.setattr(Settings, "load", classmethod(lambda cls, env=None: SimpleNamespace(payhoa_my_unit_id=700001)))
    row = lambda uid, unit: SimpleNamespace(unit_id=uid, unit=unit)
    args = SimpleNamespace(only=["me"], env=None)
    assert owner_info._only(row(700001, "1 EXAMPLE WALK"), args)
    assert not owner_info._only(row(700002, "2 EXAMPLE WALK"), args)
    assert owner_info._only(row(700002, "2 EXAMPLE WALK"), SimpleNamespace(only=["2 ex"], env=None))
