from types import SimpleNamespace

from jason import batches
from jason.tasks import notice_ledger as nl
from jason.tasks.notice_ledger import Attempt, Delivery


def _email(status, *events, subject="Owner information [ref ABC123]", member=700001, activity=1):
    return {"type": "email", "status": status, "subject": subject, "activityId": activity,
            "createdAt": "2026-10-01T16:00:00Z", "recipientUnitTitle": "3000 EXAMPLE WALK",
            "recipientMemberships": [{"id": member}], "statusData": {"events": list(events)}}


def test_outcome_reads_the_log_rows():
    assert nl.outcome(_email("opened"))[0] is Delivery.OPENED
    assert nl.outcome(_email("delivered"))[0] is Delivery.DELIVERED
    bounced = nl.outcome(_email("bounced", {"source": "sendgrid", "occurredAt": "t1",
                                            "details": {"reason": "550 mailbox unavailable"}}))
    assert bounced == (Delivery.BOUNCED, "t1", "550 mailbox unavailable")
    skipped = nl.outcome(_email("failed", {"source": "email-skip", "details": {"reason": "No email on file"}}))
    assert skipped[0] is Delivery.SKIPPED
    silent = nl.outcome(_email("failed", {"source": "email-failure",
                                          "details": {"reason": "No follow-up event after 24 hours"}}))
    assert silent[0] is Delivery.UNKNOWN
    assert nl.outcome(_email("failed", {"source": "internal"}))[0] is Delivery.FAILED


def test_letter_outcome_takes_the_most_telling_event():
    assert nl.letter_outcome([{"event": "Submitted", "createdAt": "a"}])[0] is Delivery.PENDING
    assert nl.letter_outcome([{"event": "Submitted"}, {"event": "In local area"}])[0] is Delivery.MAILED
    assert nl.letter_outcome([{"event": "Delivered"}, {"event": "Re-routed"}])[0] is Delivery.REROUTED
    assert nl.letter_outcome([])[0] is Delivery.PENDING


def _a(member, channel, status, unit="3000 EXAMPLE WALK", key="k"):
    return Attempt("n", member, 0, unit, channel, "b", f"{key}{member}{channel}{status.value}", status=status)


def test_a_bounce_owes_mail_and_a_reached_member_owes_no_resend():
    found = {s.membership_id: s for s in nl.standing([
        _a(1, "email", Delivery.BOUNCED),
        _a(2, "email", Delivery.SKIPPED), _a(2, "letter", Delivery.MAILED),
        _a(3, "email", Delivery.SKIPPED),
        _a(4, "email", Delivery.OPENED),
    ])}
    assert [f.key for f, _ in found[1].follow_ups] == ["email-bounced"]
    assert found[2].follow_ups == []                       # the letter reached the member
    assert [f.key for f, _ in found[3].follow_ups] == ["email-skipped"]
    assert found[4].follow_ups == [] and found[4].reached


def test_once_a_letter_reaches_the_member_a_bounce_only_asks_for_an_email():
    (s,) = nl.standing([_a(1, "email", Delivery.BOUNCED), _a(1, "letter", Delivery.MAILED)])
    assert [f for f, _ in s.follow_ups] == [nl.ASK_EMAIL]
    assert nl.lines([s])[0] == "1 members; 1 reached; 0 owed a resend; 1 to ask for an address."


def test_a_returned_letter_owes_a_resend_unless_the_email_arrived():
    (alone,) = nl.standing([_a(1, "letter", Delivery.RETURNED)])
    assert [f.key for f, _ in alone.follow_ups] == ["letter-returned"]
    (both,) = nl.standing([_a(1, "letter", Delivery.RETURNED), _a(1, "email", Delivery.OPENED)])
    assert [f for f, _ in both.follow_ups] == [nl.ASK_ADDRESS]


def test_a_full_mailbox_is_a_temporary_bounce():
    a = _a(1, "email", Delivery.BOUNCED)
    a.reason = "452 4.2.2 The recipient's inbox is out of storage space."
    assert nl.temporary(a)
    a.reason = "550 5.1.1 No such user"
    assert not nl.temporary(a)


def test_each_follow_up_is_owed_once():
    (s,) = nl.standing([_a(1, "email", Delivery.SKIPPED, key="x"), _a(1, "email", Delivery.SKIPPED, key="y")])
    assert [f.key for f, _ in s.follow_ups] == ["email-skipped"]


def test_a_general_notice_notes_a_failure_unless_the_member_asked_for_individual_delivery():
    attempts = [_a(1, "email", Delivery.SKIPPED), _a(1, "email", Delivery.BOUNCED), _a(2, "email", Delivery.SKIPPED)]
    found = {s.membership_id: s for s in nl.standing(attempts, general=True, individual={2})}
    assert [f for f, _ in found[1].follow_ups] == [nl.GENERAL_NOTE, nl.ASK_EMAIL]
    assert [f.key for f, _ in found[2].follow_ups] == ["email-skipped"]
    text = nl.lines(list(found.values()))
    assert text[0] == "2 members; 0 reached; 1 owed a resend; 1 to ask for an address; 1 not reached by this message, noted."
    assert any("CIV 4045" in line for line in text)


def test_a_posted_general_notice_is_remembered(tmp_path):
    assert nl.is_general(tmp_path, "meeting-x") is False          # nothing recorded: no db is made
    assert not (tmp_path / "notices").exists()
    nl.set_general(tmp_path, "meeting-x", True, posted="the website, 2026-09-10", by="A Person")
    assert nl.is_general(tmp_path, "meeting-x") is True and nl.is_general(tmp_path, "other") is False


def test_sync_matches_emails_by_reference_and_letters_by_communication(tmp_path, monkeypatch):
    items = {"owner-info-x-email": [SimpleNamespace(status=batches.ItemStatus.SENT, result={"reference": "ABC123"},
                                                     payload={"membershipId": 700001, "unitId": 800001})],
             "owner-info-x-mail": [SimpleNamespace(status=batches.ItemStatus.SENT, result={"mailBatches": [55]},
                                                    payload={})]}
    monkeypatch.setattr(batches, "items", lambda data_dir, bid: items[bid])
    letter = {"type": "letter", "status": "processing", "activityId": 900, "createdAt": "2026-10-01T15:00:00Z",
              "recipientUnitTitle": "3001 EXAMPLE WALK", "recipientMemberships": [{"id": 700002}],
              "statusData": {"events": [{"source": "lob-init"}]}}
    rows = [_email("bounced", {"source": "sendgrid", "details": {"reason": "550"}}), letter,
            _email("opened", subject="Something else"), {"type": "email", "createdAt": "2026-09-01T00:00:00Z"}]
    client = SimpleNamespace(
        mail_batch=lambda org, mb: [{"id": 1}],
        mail_letters=lambda org, kind: [{"id": 1, "commActivityId": 900}],
        mail_events=lambda org, comm: [{"event": "Submitted"}, {"event": "Processed for delivery"}],
        iter_communications=lambda org: iter(rows))
    counts = nl.sync(client, 1, tmp_path, "owner-info-x", items, since="2026-09-30")
    assert counts == {"email bounced": 1, "letter mailed": 1}
    found = {a.channel: a for a in nl.load(tmp_path, "owner-info-x")}
    assert found["email"].membership_id == 700001 and found["email"].reason == "550"
    assert found["letter"].membership_id == 700002 and found["letter"].status is Delivery.MAILED
    assert nl.notices(tmp_path)[0][:2] == ("owner-info-x", 2)
