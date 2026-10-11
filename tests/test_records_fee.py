"""The fee on a records request against Civil Code 5205(f) and (g) (``jason.tasks.records_fee``), the writer that refuses
a redaction charge above the stated bound and records any other question for counsel, the membership-list clock's labeling,
and who the web writer names. The statute's words here are a made-up copy in the stored form; one test reads the real shelf
when it is on this checkout.
"""

from __future__ import annotations

import pytest
import webclient

from jason.tasks import records_fee as fee
from jason.tasks import records_requests as store

G = ("(g) In addition to the direct and actual costs of copying and mailing, the association may bill the requesting member an "
     "amount not in excess of ten dollars ($10) per hour, and not to exceed two hundred dollars ($200) total per written request, "
     "for the time actually and reasonably involved in redacting an enhanced association record.")
F = "(f) The association may bill the requesting member for the direct and actual cost of copying and mailing requested documents."
B = "(b) \"Enhanced association records\" means invoices, receipts, and canceled checks for payments made by the association."
WORDS = {fee.COPY: F, fee.REDACTION: G, fee.ENHANCED: B,
         fee.MEMBERSHIP_LIST: "(6) Membership list, within the timeframe specified in Section 8330 of the Corporations Code.",
         fee.MEMBERSHIP_LIST_LAW: "8330. (a) Subject to Sections 8331 and 8332, a member may inspect and copy the record of all the members."}
LIMITS = fee.Bound(hourly_cents=1000, cap_cents=20000)


def fake_words(citation):
    text = WORDS.get(citation, "")
    return {"citation": citation, "text": text, "found": bool(text), "inForce": "a test shelf", "reason": ""}


@pytest.fixture(autouse=True)
def shelf(monkeypatch):
    monkeypatch.setattr(fee, "words", fake_words)


def codes(result):
    return [f["code"] for f in result["findings"]]


# --- the pure check -----------------------------------------------------------------------------------------------------

def test_the_bounds_are_read_out_of_the_stored_words_never_written_here():
    b = fee.parse_bound(G)
    assert (b.hourly_cents, b.cap_cents) == (1000, 20000)
    assert fee.bound() == b
    assert fee.parse_bound("(g) a charge may be billed.") == fee.Bound(None, None, "(g) a charge may be billed.")
    assert not fee.parse_bound("").stated


def test_nothing_billed_is_ok_and_needs_no_statute():
    out = fee.check(0, limits=fee.Bound(None, None))
    assert out["status"] == "ok" and out["needsCounsel"] is False and out["findings"] == []


def test_a_redaction_charge_within_the_total_and_the_rate_is_ok_with_the_statutes_words_attached():
    out = fee.check(15000, 0, 15000, 900, limits=LIMITS)           # 15 hours at $10
    assert out["status"] == "ok" and out["needsCounsel"] is False
    assert out["capCents"] == 20000 and out["hourlyCents"] == 1000
    assert [w["citation"] for w in out["words"]] == [fee.COPY, fee.REDACTION, fee.ENHANCED]
    assert out["words"][1]["text"] == G                              # verbatim, as stored
    assert out["reading"].startswith(fee.READING)


def test_a_redaction_charge_above_the_stated_total_is_over_the_cap():
    out = fee.check(25000, 0, 25000, 1500, limits=LIMITS)
    assert out["status"] == "over_cap" and out["needsCounsel"] is True and "over-total" in codes(out)
    assert "$250.00" in out["findings"][0]["sentence"] and "$200.00" in out["findings"][0]["sentence"]
    assert 20000 == fee.check(20000, 0, 20000, 1200, limits=LIMITS)["capCents"] and fee.check(20000, 0, 20000, 1200, limits=LIMITS)["status"] == "ok"


def test_a_redaction_charge_above_the_stated_hourly_rate_is_over_the_cap():
    out = fee.check(5000, 0, 5000, 270, limits=LIMITS)               # 4.5 hours at $10 is $45; $50 is more
    assert out["status"] == "over_cap" and codes(out) == ["over-rate"]
    assert fee.check(4500, 0, 4500, 270, limits=LIMITS)["status"] == "ok"      # exactly the rate
    assert fee.check(1000, 0, 1000, 60, limits=LIMITS)["status"] == "ok"
    assert fee.check(1001, 0, 1001, 60, limits=LIMITS)["status"] == "over_cap"  # one cent over, by integer arithmetic


def test_the_refusal_carries_the_statutes_words_after_jasons_finding():
    out = fee.check(25000, 0, 25000, 1500, limits=LIMITS)
    sentence = fee.refusal(out)
    assert sentence.startswith("The redaction charge, $250.00")
    assert f'{fee.REDACTION} reads: "{G}"' in sentence


def test_what_the_figures_cannot_settle_is_a_warning_for_counsel_and_never_a_refusal():
    no_time = fee.check(5000, 0, 5000, 0, limits=LIMITS)
    assert no_time["status"] == "warning" and codes(no_time) == ["no-time"] and no_time["needsCounsel"] is True
    not_enhanced = fee.check(1000, 0, 1000, 60, enhanced=False, limits=LIMITS)
    assert not_enhanced["status"] == "warning" and codes(not_enhanced) == ["not-enhanced"]
    differ = fee.check(9000, 2000, 5000, 300, limits=LIMITS)
    assert differ["status"] == "warning" and codes(differ) == ["parts-differ"]
    lump = fee.check(30000, limits=LIMITS)                           # more than the redaction total, no breakdown, enhanced asked
    assert lump["status"] == "warning" and codes(lump) == ["no-breakdown"]
    assert fee.check(30000, enhanced=False, limits=LIMITS)["status"] == "ok"   # copying and mailing carry no figure
    assert fee.check(30000, 30000, 0, 0, limits=LIMITS)["status"] == "ok"      # a person said it is all copying and mailing


def test_a_shelf_without_5205g_leaves_no_figure_so_the_fee_is_accepted_with_a_warning():
    out = fee.check(5000, limits=fee.Bound(None, None))
    assert out["status"] == "warning" and codes(out) == ["statute-unread"] and out["capCents"] is None
    assert "Counsel reads the statute" in out["findings"][0]["sentence"]


def test_the_rule_recites_the_stored_words_and_labels_the_membership_list_date_as_jasons_reading():
    out = fee.rule()
    assert [w["text"] for w in out["fee"]["words"]] == [F, G, B]
    assert out["fee"]["capCents"] == 20000 and out["fee"]["hourlyCents"] == 1000
    assert [w["citation"] for w in out["membershipList"]["words"]] == [fee.MEMBERSHIP_LIST, fee.MEMBERSHIP_LIST_LAW]
    assert out["membershipList"]["words"][0]["text"].endswith("of the Corporations Code.")
    assert out["membershipList"]["reading"].startswith(fee.READING) and "computed for a person to check" in out["membershipList"]["reading"]


# --- the store ----------------------------------------------------------------------------------------------------------

def opened(tmp_path, records=("enhanced", "minutes")):
    return store.open_request(tmp_path, "2026-10-02", "Unit 12", "email", list(records), by="Manager")


def test_the_store_refuses_a_redaction_charge_above_the_bound_and_keeps_the_words_in_the_error(tmp_path):
    r = opened(tmp_path)
    with pytest.raises(ValueError) as e:
        store.decide(tmp_path, r.id, feeCents=25000, redactionCents=25000, redactionMinutes=1500)
    assert "$200.00" in str(e.value) and G in str(e.value)
    assert store.get(tmp_path, r.id).decisions.feeCents == 0          # nothing was written
    with pytest.raises(ValueError):
        store.decide(tmp_path, r.id, feeCents=5000, redactionCents=5000, redactionMinutes=270)


def test_the_store_accepts_a_figure_within_the_bound_and_records_it(tmp_path):
    r = opened(tmp_path)
    d = store.decide(tmp_path, r.id, feeCents=18000, copyCents=3000, redactionCents=15000, redactionMinutes=900, by="Manager")
    assert (d.decisions.feeCents, d.decisions.copyCents, d.decisions.redactionCents, d.decisions.redactionMinutes) == (18000, 3000, 15000, 900)
    assert d.history[-1].endswith("fee $0.00 -> $180.00 (CIV 5205(f), (g))")
    out = store.as_dict(d)
    assert out["feeCheck"]["status"] == "ok" and out["feeCheck"]["words"][1]["text"] == G


def test_the_store_accepts_a_question_it_cannot_settle_and_records_the_flag(tmp_path):
    r = opened(tmp_path)
    d = store.decide(tmp_path, r.id, feeCents=5000, redactionCents=5000)       # no time recorded
    assert d.decisions.feeCents == 5000
    assert d.history[-1].endswith("A redaction charge is recorded with no time, so the hourly rate in CIV 5205(g) cannot be checked.")
    assert "fee needs counsel's reading (CIV 5205(g))" in d.history[-1]
    out = store.as_dict(d)
    assert out["feeCheck"]["status"] == "warning" and out["feeCheck"]["needsCounsel"] is True
    assert store.as_dict(opened(tmp_path))["feeCheck"] is None                   # no fee, no check


def test_a_note_alone_does_not_re_judge_a_fee_already_recorded(tmp_path):
    r = opened(tmp_path)
    store.decide(tmp_path, r.id, feeCents=5000, redactionCents=5000)
    before = len(store.get(tmp_path, r.id).history)
    store.decide(tmp_path, r.id, note="called the member")
    assert len(store.get(tmp_path, r.id).history) == before


def test_a_fee_figure_is_whole_cents_zero_or_more(tmp_path):
    r = opened(tmp_path)
    for name in ("feeCents", "copyCents", "redactionCents", "redactionMinutes"):
        for bad in (-1, True, "10", 1.5):
            with pytest.raises(ValueError, match=name):
                store.decide(tmp_path, r.id, **{name: bad})


def test_an_old_row_without_the_new_figures_still_loads(tmp_path):
    import json

    (tmp_path / "records-requests").mkdir()
    (tmp_path / "records-requests" / "requests.json").write_text(json.dumps({"requests": [{
        "id": "2026-09-01--unit-1", "receivedOn": "2026-09-01", "unit": "Unit 1", "via": "mail", "records": ["minutes"],
        "decisions": {"feeCents": 1250, "note": "mailed"}}]}), encoding="utf-8")
    d = store.get(tmp_path, "2026-09-01--unit-1").decisions
    assert d.feeCents == 1250 and d.copyCents == 0 and d.redactionCents == 0 and d.redactionMinutes == 0


# --- the membership-list clock ------------------------------------------------------------------------------------------

def test_the_membership_list_date_is_labeled_as_jasons_computed_date_and_its_count_is_unchanged():
    stage = next(s for s in store.deadlines("2026-10-02", ["membership_list"]) if s["key"] == "membershipList")
    assert stage["date"] == "2026-10-09"                                          # five business days from Friday, as before
    assert stage["label"] == "Membership list: jason's computed date, for a person to check"
    assert stage["authority"] == "CIV 5210(b)(6), CORP 8330" and stage["computed"] is True
    assert stage["who"] == "counsel reads the statute"
    other = next(s for s in store.deadlines("2026-10-02", ["minutes"]) if s["key"] == "currentYear")
    assert "computed" not in other and other["authority"] == "CIV 5210(b)(1)"


# --- the real shelf -----------------------------------------------------------------------------------------------------

def test_the_real_5205g_states_the_figures_the_check_uses(monkeypatch):
    monkeypatch.undo()
    got = fee.words(fee.REDACTION)
    if not got["found"]:
        pytest.skip("CIV 5205 is not on this checkout's authorities shelf")
    b = fee.bound()
    assert (b.hourly_cents, b.cap_cents) == (1000, 20000)
    assert "not in excess of ten dollars ($10) per hour" in got["text"] and "two hundred dollars ($200) total per written request" in got["text"]


# --- who the web writer names -------------------------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path, monkeypatch):
    from jason.web.app import create_app

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: tmp_path)
    monkeypatch.setattr("jason.mcp.county.records_inventory", lambda *a, **k: {"records": []})
    dist = tmp_path / "dist"
    dist.mkdir()
    return create_app(dist, {}, approvals_live=None, extra_writes=True, sign_in=webclient.roster_sign_in(dev=True))


OPEN = {"receivedOn": "2026-10-02", "unit": "Unit 12", "via": "email", "records": ["enhanced"], "purpose": "", "years": []}


def test_a_decision_is_the_signed_in_persons_even_when_the_body_carries_no_by(app, tmp_path):
    c = webclient.sign_in(webclient.client(app), "Pat Example")
    made = c.post("/api/write/records-requests/new", json={**OPEN})                     # no by: the old record kept no one
    assert made.status_code == 200 and made.json["by"] == "Pat Example"
    ident = made.json["id"]
    assert webclient.sign_in(webclient.client(app), "Dana Director").post(f"/api/write/records-requests/{ident}", json={"note": "n"}).json["by"] == "Dana Director"
    assert c.post(f"/api/write/records-requests/{ident}", json={"note": "m", "by": "pat example"}).json["by"] == "Pat Example"
    # the app's own guard refuses a by that names someone else; the writer never sees it
    assert c.post(f"/api/write/records-requests/{ident}", json={"note": "x", "by": "Jordan Example"}).status_code == 403


def test_a_decision_needs_a_sign_in_and_the_offices_that_open_p2_where_sign_in_is_set_up(app):
    ident = webclient.sign_in(webclient.client(app), "Pat Example").post("/api/write/records-requests/new", json=OPEN).json["id"]
    assert webclient.client(app).post(f"/api/write/records-requests/{ident}", json={"note": "n", "by": "Pat Example"}).status_code == 401
    assert webclient.sign_in(webclient.client(app), "Ada Admin").post(f"/api/write/records-requests/{ident}", json={"note": "n"}).status_code == 403


def test_a_members_own_request_names_no_person_when_nobody_is_signed_in(app):
    out = webclient.client(app).post("/api/write/records-requests/new", json={**OPEN, "by": "Jordan Example"})
    assert out.status_code == 200 and out.json["by"] == "the member, through the owner view"


def test_the_web_writer_refuses_a_redaction_charge_over_the_bound_with_the_statutes_words(app):
    c = webclient.sign_in(webclient.client(app), "Pat Example")
    ident = c.post("/api/write/records-requests/new", json=OPEN).json["id"]
    url = f"/api/write/records-requests/{ident}"
    over = c.post(url, json={"feeCents": 25000, "redactionCents": 25000, "redactionMinutes": 1500})
    assert over.status_code == 400 and G in over.json["error"]
    warn = c.post(url, json={"feeCents": 5000, "redactionCents": 5000})
    assert warn.status_code == 200 and warn.json["feeCheck"]["status"] == "warning" and warn.json["feeCheck"]["needsCounsel"] is True


def test_the_read_carries_the_rule_and_the_loopback_default_keeps_the_typed_by(tmp_path, monkeypatch):
    from jason.web.app import create_app

    monkeypatch.setattr("jason.mcp.county._data_dir", lambda d: tmp_path)
    monkeypatch.setattr("jason.mcp.county.records_inventory", lambda *a, **k: {"records": []})
    dist = tmp_path / "dist"
    dist.mkdir()
    loop = create_app(dist, {}, approvals_live=None, extra_writes=True, sign_in=webclient.roster_sign_in(configured=False))
    c = webclient.client(loop)
    made = c.post("/api/write/records-requests/new", json={**OPEN, "by": "Manager"})
    assert made.status_code == 200 and made.json["by"] == "Manager"
    assert c.post(f"/api/write/records-requests/{made.json['id']}", json={"note": "n", "by": "Treasurer"}).json["by"] == "Treasurer"
    from jason.web.extra import records_requests as web

    out = web.records_requests({})
    assert out["rule"]["fee"]["capCents"] == 20000 and out["rule"]["fee"]["words"][1]["text"] == G
    assert out["rule"]["membershipList"]["words"][0]["citation"] == "CIV 5210(b)(6)"
    assert any("computed for a person to check" in c for c in out["caveats"])
    assert web.records_requests({"id": made.json["id"]})["rule"] == out["rule"]
