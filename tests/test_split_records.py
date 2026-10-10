"""The PDF splitter's records (docs/pdf-splitter.md, section 2): boundaries, segments, the nested stack, labels, undo and redo, and
suggestions kept apart from a person's marks. Pure: no file, no model, no profile."""

import json
import random

import pytest

from jason.community.split_session import (HISTORY_CAP, Boundary, PageFact, Signal, Source, SplitSession, Suggestion, band, new_id)

BY = "Jane Example"


def make(pages=40, status="draft"):
    s = SplitSession(new_id(), Source("ab" * 32, 1000, pages), "draft", "2026-10-01T00:00:00+00:00", "2026-10-01T00:00:00+00:00", BY)
    s.mark(1, by=BY)
    s.undo, s.version, s.status = [], 1, status
    return s


def starts(s):
    return [g.start for g in s.top_segments()]


def test_the_first_page_always_starts_a_segment_and_cannot_be_removed_or_moved():
    s = make()
    with pytest.raises(ValueError, match="first page always starts"):
        s.unmark(1)
    with pytest.raises(ValueError, match="cannot be moved"):
        s.move(1, 5, by=BY)
    with pytest.raises(ValueError, match="level 0"):
        s.mark(1, level=1, by=BY)
    s.set_boundaries([(10, 0)], by=BY)                       # a set that forgets page 1 still has it
    assert starts(s) == [1, 10]
    assert s.clear(by=BY) == 1 and starts(s) == [1]


def test_boundaries_make_ranges_that_cover_the_file():
    s = make(40)
    s.set_boundaries([(1, 0), (15, 0), (23, 0)], by=BY)
    segs = s.top_segments()
    assert [(g.key, g.start, g.end, g.pages) for g in segs] == [("s1", 1, 14, 14), ("s2", 15, 22, 8), ("s3", 23, 40, 18)]
    assert sum(g.pages for g in segs) == 40
    with pytest.raises(ValueError, match="not in a file of 40 pages"):
        s.mark(41, by=BY)
    with pytest.raises(ValueError, match="not in a file"):
        s.mark(0, by=BY)


def test_the_nested_stack_keeps_a_child_inside_its_parent():
    s = make(40)
    s.set_boundaries([(1, 0), (10, 0), (14, 1), (18, 1), (25, 0)], by=BY)
    segs = {g.key: g for g in s.segments()}
    assert (segs["s2"].start, segs["s2"].end) == (10, 24)                    # the parent still holds its children's pages
    assert (segs["s2.1"].start, segs["s2.1"].end, segs["s2.1"].parent) == (14, 17, "s2")
    assert (segs["s2.2"].start, segs["s2.2"].end) == (18, 24) and segs["s2.2"].path == "s2/s2.2"
    assert [g.key for g in s.top_segments()] == ["s1", "s2", "s3"] and s.counts()["nested"] == 2
    s.mark(30, level=2, by=BY)                                                # a level cannot skip one: 2 after a level 0 becomes 1
    assert s.boundary_at(30).level == 1
    with pytest.raises(ValueError, match="level is 0"):
        s.mark(31, level=9, by=BY)


def test_a_nested_choice_is_inside_or_file_and_taking_out_waits_for_a_later_phase():
    s = make(40)
    s.set_boundaries([(1, 0), (10, 0), (14, 1)], by=BY)
    s.label(14, "nested", "file", by=BY)
    s.label(10, "title", "A guess", by=BY)
    assert s.label_of(14) == {"nested": "file"} and s.label_of(10) == {"title": "A guess"}
    with pytest.raises(ValueError, match="taking it out comes later"):
        s.label(14, "nested", "take-out", by=BY)
    with pytest.raises(ValueError, match="does not start a segment"):
        s.label(12, "title", "x", by=BY)
    s.unmark(14, by=BY)
    assert s.label_of(14) == {}                                               # a label goes with its start


def test_every_change_is_one_command_and_undo_and_redo_work_after_a_reload():
    s = make(100)
    v0 = s.version
    s.mark(10, by=BY)
    s.mark_range(20, 60, every=10, by=BY)                                     # 20, 30, 40, 50, 60: a bulk act is one step
    assert s.version == v0 + 2 and len(s.undo) == 2
    assert starts(s) == [1, 10, 20, 30, 40, 50, 60]
    s = SplitSession.from_dict(json.loads(json.dumps(s.to_dict())))            # a reload
    assert s.do_undo() and starts(s) == [1, 10]
    assert s.do_undo() and starts(s) == [1]
    assert not s.do_undo()
    assert s.do_redo() and starts(s) == [1, 10]
    s.mark(70, by=BY)
    assert not s.do_redo()                                                    # a new change clears redo
    assert s.version > v0


def test_the_undo_stack_is_capped_and_a_change_that_changes_nothing_is_not_a_step():
    s = make(500)
    for p in range(2, 2 + HISTORY_CAP + 30):
        s.mark(p, by=BY)
    assert len(s.undo) == HISTORY_CAP
    v = s.version
    s.mark(5, by=BY)                                                          # already a start at level 0
    assert s.version == v


def test_the_autosave_replaces_the_set_in_one_step_and_keeps_accepted_records():
    s = make(100)
    s.replace_suggestions([Suggestion("g20", 20, 0, 0.9, "suggested", [Signal("page-one", 1.5, "x")], "Page 20.")])
    s.accept("g20", by=BY)
    n = len(s.undo)
    s.set_boundaries([(1, 0), (20, 0), (50, 0)], by=BY)
    assert len(s.undo) == n + 1 and s.boundary_at(20).source == "accepted" and s.boundary_at(50).source == "person"


def test_a_suggestion_is_never_a_boundary_until_a_person_accepts_it():
    s = make(100)
    s.set_boundaries([(1, 0), (40, 0)], by=BY)
    mine = [b.to_dict() for b in s.boundaries]
    sug = [Suggestion(f"g{p}", p, 0, 0.5 + p / 300, "suggested", [Signal("title-block", 1.0, "T")], f"Page {p}.") for p in (10, 40, 70)]
    s.replace_suggestions(sug)
    assert [b.to_dict() for b in s.boundaries] == mine                         # unchanged
    assert [x.state for x in s.suggestions] == ["open", "accepted", "open"]   # page 40 is already a start
    s.accept("g10", by=BY)
    assert s.boundary_at(10).source == "accepted" and s.boundary_at(10).suggestion == "g10"
    s.reject("g70", by=BY)
    s.replace_suggestions([Suggestion("g70", 70, 0, 0.9, "suggested", [], "Page 70.")])
    assert s.suggestions[0].state == "rejected"                               # a rejected page stays rejected when jason suggests again


def test_whatever_suggestions_arrive_a_persons_boundaries_are_never_moved_or_removed():
    rng = random.Random(7)
    for _ in range(25):
        s = make(80)
        mine = sorted(rng.sample(range(2, 81), rng.randint(0, 12)))
        s.set_boundaries([(1, 0)] + [(p, 0) for p in mine], by=BY)
        kept = {b.page: b.to_dict() for b in s.boundaries}
        for _round in range(3):
            fresh = [Suggestion(f"g{p}", p, 0, rng.random(), "suggested", [], "") for p in rng.sample(range(2, 81), 15)]
            s.replace_suggestions(fresh)
        assert {b.page: b.to_dict() for b in s.boundaries} == kept


def test_accept_all_takes_high_and_better_never_a_model_only_guess_and_is_one_step():
    s = make(100)
    s.replace_suggestions([Suggestion("g10", 10, 0, 0.95, "suggested", [], "a"), Suggestion("g20", 20, 0, 0.9, "likely", [], "b", "model"),
                           Suggestion("g30", 30, 0, 0.5, "suggested", [], "c"), Suggestion("g40", 40, 0, 0.86, "suggested", [], "d")])
    n = len(s.undo)
    assert s.accept_all(by=BY) == 2 and starts(s) == [1, 10, 40] and len(s.undo) == n + 1
    assert s.do_undo() and starts(s) == [1]
    assert [x.state for x in s.suggestions] == ["open"] * 4                   # undo puts the suggestions back too
    assert band(0.9) == "High" and band(0.7) == "Medium" and band(0.2) == "Low"


def test_only_a_draft_can_be_changed():
    for status in ("confirmed", "applied", "declined", "stale"):
        s = make(status=status)
        with pytest.raises(ValueError, match=f"this split is {status}"):
            s.mark(5, by=BY)
        with pytest.raises(ValueError, match="only a draft"):
            s.do_undo()


def test_the_view_names_no_file_and_hides_a_confidential_reference():
    s = SplitSession(new_id(), Source("cd" * 32, 5, 10, "library", "9001", True, "5:1"), "draft", "t", "t", BY)
    s.mark(1, by=BY)
    plain = s.view()
    assert plain["source"]["ref"] == "9001"
    assert s.view(mask=True)["source"]["ref"] == ""
    assert "name" not in json.dumps(plain).lower().replace("filename", "")


def test_a_page_fact_round_trips_and_a_pending_page_is_only_its_number():
    f = PageFact(3, 612, 792, 0, "content", True, 80, 400, 300, "bilevel", "CCITTFaxDecode", "A header", "A footer", (2, 7), "A title", "2026-03-01")
    assert PageFact.from_dict(json.loads(json.dumps(f.to_dict()))) == f
    assert PageFact(5, pending=True).to_dict()["pending"] is True
    assert isinstance(Boundary(2).to_dict(), dict)
