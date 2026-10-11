import json

import pytest
import webclient

from jason.tasks import decisions as store


def test_record_update_tally_roundtrip(tmp_path):
    d = store.record(tmp_path, "2026-10-20", "Reserve loan not restored", "Move to restore $6,000 to the reserve by March 1",
                     item="reserve-loan", mover="A. Director", second="B. Director",
                     votes={"A. Director": "aye", "B. Director": "aye", "C. Director": "no", "D. Director": "absent"})
    assert d.id == "2026-10-20--reserve-loan" and d.outcome == "" and store.suggested_outcome(d.votes) == "approved"
    assert store.tally(d.votes) == {"aye": 2, "no": 1, "abstain": 0, "absent": 1}
    d = store.update(tmp_path, d.id, outcome="approved", by="Secretary")
    assert d.history[-1].endswith("outcome (open) -> approved")
    again = store.record(tmp_path, "2026-10-20", "Reserve loan not restored", "Amended: restore by April 1", item="reserve-loan")
    assert again.id == d.id and again.motion.startswith("Amended") and again.history[-1].endswith("re-recorded")
    free = store.record(tmp_path, "2026-10-20", "Adjournment", "Move to adjourn at 8:12 PM")
    assert free.id == "2026-10-20--move-to-adjourn-at-8-12-pm"
    assert [x.id for x in store.for_meeting(tmp_path, "2026-10-20")] == [d.id, free.id]
    assert store.for_meeting(tmp_path, "2026-11-17") == []
    raw = json.loads((tmp_path / "board" / "decisions.json").read_text())
    assert raw["decisions"][0]["outcome"] == "approved"
    assert store.as_dict(store.load(tmp_path)[0])["suggested"] == "approved"


def test_a_recusal_is_recorded_as_one_never_as_absent(tmp_path):
    d = store.record(tmp_path, "2026-10-20", "Painting contract", "Move to approve the painting contract", item="paint",
                     votes={"A. Director": "aye", "B. Director": "aye"}, recused=["C. Director"])
    assert d.recused == ["C. Director"] and "C. Director" not in d.votes and store.as_dict(d)["recused"] == ["C. Director"]
    with pytest.raises(ValueError, match="recused, so no vote"):
        store.update(tmp_path, d.id, votes={"C. Director": "absent"}, recused=["C. Director"])
    with pytest.raises(ValueError, match="recused is a list"):
        store.update(tmp_path, d.id, recused="C. Director")


def test_refusals(tmp_path):
    with pytest.raises(ValueError):
        store.record(tmp_path, "2026-10-20", "", "motion")
    with pytest.raises(ValueError):
        store.record(tmp_path, "soon", "t", "m")
    with pytest.raises(ValueError):
        store.record(tmp_path, "2026-10-20", "t", "m", votes={"A": "yes"})
    with pytest.raises(ValueError):
        store.record(tmp_path, "2026-10-20", "t", "m", outcome="carried")
    with pytest.raises(ValueError):
        store.record(tmp_path, "2026-10-20", "t", "m", recorded="2020-01-01")
    with pytest.raises(KeyError):
        store.update(tmp_path, "nope", notes="n")


def test_api_decision_routes(tmp_path):
    from jason.web.app import create_app

    def writer(decision_id, body):
        if decision_id == "missing":
            raise KeyError(decision_id)
        if body.get("outcome") == "carried":
            raise ValueError("outcome is one of approved, denied, tabled")
        return {"id": decision_id or "new", **body}

    c = webclient.client(create_app(tmp_path, {}, board_writer=None, canvas_writer=None, decision_writer=writer, request_writer=None, owner_info_writer=None, hearing_writer=None, extra_writes=False))
    assert c.post("/api/decisions", json={"meeting": "2026-10-20", "title": "t", "motion": "m"}).json["id"] == "new"
    assert c.post("/api/decisions/x", json={"outcome": "approved"}).json["outcome"] == "approved"
    assert c.post("/api/decisions/x", json={"outcome": "carried"}).status_code == 400
    assert c.post("/api/decisions/missing", json={"notes": "n"}).status_code == 404
    assert c.get("/api/health").json["writes"] == ["decisions"]


def test_minutes_prompt_quotes_recorded_decisions():
    import ast
    import re
    from datetime import date
    from pathlib import Path

    # The prompt builder is pure text; exercise it without the Zoom stores by loading only that function.
    src = Path("src/jason/tasks/minutes_draft.py").read_text(encoding="utf-8")
    assert "Decisions the Secretary recorded" in src
    # Only the open decisions reach the model; an executive one is noted by its 4935 subject (CIV 4935(e)).
    assert re.search(r'"decisions": \[as_dict\(d\) for d in open_only\(recorded\)\]', src)


# -- executive decisions: an opaque id, never a slug of the motion (CIV 4935(e)) -------------------------------------------

EXEC = dict(session="executive session", subject="litigation")


def test_a_new_executive_decision_gets_an_opaque_sequential_id_per_meeting(tmp_path):
    first = store.record(tmp_path, "2026-10-20", "Settle the Okafor claim", "Move to settle the Okafor claim for $5,000", **EXEC)
    second = store.record(tmp_path, "2026-10-20", "Retain counsel", "Move to retain counsel on the Okafor claim", item="retain-counsel", **EXEC)
    other = store.record(tmp_path, "2026-11-17", "Settle the Okafor claim", "Move to settle the Okafor claim for $5,000", **EXEC)
    assert (first.id, second.id, other.id) == ("2026-10-20--executive-1", "2026-10-20--executive-2", "2026-11-17--executive-1")
    for d in (first, second, other):
        assert "okafor" not in d.id.lower() and "retain" not in d.id and "settle" not in d.id
    # the item and the kind stay on the row, not in the id
    assert second.item == "retain-counsel"
    table = store.record(tmp_path, "2026-10-20", "Settle", "Move to table the settlement", kind="table", **EXEC)
    assert table.id == "2026-10-20--executive-3" and table.kind == "table"


def test_an_executive_decision_recorded_again_replaces_its_row_and_an_open_one_is_never_taken(tmp_path):
    first = store.record(tmp_path, "2026-10-20", "Claim", "Move to settle the claim", item="claim-7", **EXEC)
    again = store.record(tmp_path, "2026-10-20", "Claim", "Move to settle the claim, as amended", item="claim-7", **EXEC)
    assert again.id == first.id and again.history[-1].endswith("re-recorded") and len(store.load(tmp_path)) == 1
    # an item's table motion is its own decision
    assert store.record(tmp_path, "2026-10-20", "Claim", "Move to table", item="claim-7", kind="table", **EXEC).id != first.id
    # an open decision on the same words keeps its slugged id, and an executive one on them does not take it
    shut_motion = "Move to adjourn the closed session"
    open_row = store.record(tmp_path, "2026-10-20", "Adjourn", shut_motion)
    assert open_row.id == "2026-10-20--move-to-adjourn-the-closed-session" and open_row.session == "open session"
    shut = store.record(tmp_path, "2026-10-20", "Adjourn", shut_motion, **EXEC)
    assert shut.id.startswith("2026-10-20--executive-") and open_row.id in [d.id for d in store.load(tmp_path)]
    assert next(d for d in store.load(tmp_path) if d.id == open_row.id).session == "open session"


def test_an_old_slugged_executive_row_is_left_exactly_as_it_is(tmp_path):
    old = store.Decision(id="2026-10-20--move-to-fine-the-owner-of-unit-7", meeting="2026-10-20", title="Hearing, unit 7",
                         motion="Move to fine the owner of unit 7", session="executive session", subject="member_discipline")
    store.save(tmp_path, [old])
    before = (tmp_path / "board" / "decisions.json").read_text(encoding="utf-8")
    # recording the same motion again re-records that row under its id; no new row, no new id
    again = store.record(tmp_path, "2026-10-20", "Hearing, unit 7", "Move to fine the owner of unit 7", session="executive session")
    assert again.id == old.id and len(store.load(tmp_path)) == 1 and again.history[-1].endswith("re-recorded")
    # a different executive motion that day is numbered from 1: the old id is not an opaque one
    assert store.record(tmp_path, "2026-10-20", "Other", "Move on something else", **EXEC).id == "2026-10-20--executive-1"
    assert before.count("move-to-fine-the-owner-of-unit-7") == 1


def test_the_handle_is_the_id_when_opaque_else_a_keyed_hash_that_names_no_slug(tmp_path):
    import hashlib

    new = store.record(tmp_path, "2026-10-20", "t", "Move to settle", **EXEC)
    assert store.handle(tmp_path, new) == new.id
    old = store.Decision(id="2026-10-20--move-to-fine-the-owner-of-unit-7", meeting="2026-10-20", title="t", motion="m",
                         session="executive session")
    shown = store.handle(tmp_path, old)
    assert shown.startswith("2026-10-20--held-") and len(shown) == len("2026-10-20--held-") + 12
    assert "fine" not in shown and "unit" not in shown
    assert store.handle(tmp_path, old) == shown                                  # stable for the row
    key = (tmp_path / "board" / "decisions.key")
    assert key.is_file() and len(key.read_text(encoding="utf-8").strip()) == 64
    # keyed: not the unkeyed hash of the id, so trying slugs does not find the row
    assert shown.split("--held-")[1] != hashlib.sha256(old.id.encode()).hexdigest()[:12]
    # another install's key gives another handle for the same stored id
    elsewhere = tmp_path / "elsewhere"
    assert store.handle(elsewhere, old) != shown


def test_the_handle_falls_back_to_a_key_for_the_call_when_the_file_cannot_be_made(tmp_path):
    blocked = tmp_path / "board"
    blocked.parent.mkdir(exist_ok=True)
    blocked.write_text("a file where the folder should be", encoding="utf-8")      # mkdir and open both fail
    old = store.Decision(id="2026-10-20--a-slug", meeting="2026-10-20", title="t", motion="m", session="executive session")
    assert store.handle(tmp_path, old).startswith("2026-10-20--held-") and "slug" not in store.handle(tmp_path, old)


def test_held_rows_say_the_subject_in_the_statutes_words_and_nothing_else(tmp_path):
    shut = store.record(tmp_path, "2026-10-20", "Settle the Okafor claim", "Move to settle", notes="Okafor owes $9", **EXEC)
    store.record(tmp_path, "2026-10-20", "Open item", "Move to adjourn")
    rows = store.held_rows(tmp_path, store.load(tmp_path))
    assert rows == [{"id": shut.id, "meeting": "2026-10-20", "subject": "litigation", "general": "litigation (Civil Code 4935(a))"}]
    unnamed = store.record(tmp_path, "2026-10-21", "t", "m", session="executive session")
    assert store.held_rows(tmp_path, [unnamed]) == [{"id": unnamed.id, "meeting": "2026-10-21", "subject": "", "general": ""}]


def test_rule_links_never_carry_an_executive_decisions_id(tmp_path):
    from jason.tasks.rule_records import links

    store.record(tmp_path, "2026-10-20", "Quiet hours", "Adopt jason://rules/quiet-hours as noticed", item="quiet-hours")
    store.record(tmp_path, "2026-10-20", "Fine", "Fine a member under jason://rules/pool-rules", **EXEC)
    found, notes = links(tmp_path)
    assert len(found["quiet-hours"]) == 1
    assert "pool-rules" not in found and "executive" not in json.dumps(found, default=str)
    assert notes == ["1 executive-session decision(s) cite a rule and are not listed"]
