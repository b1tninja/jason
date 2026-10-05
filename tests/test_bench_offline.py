"""The offline benchmark script's scoring and page ranges, on made-up words."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bench_offline as bench  # noqa: E402


def test_a_word_missing_added_or_different_is_one_edit_each():
    total, where, blocks = bench.edits("a b c d e f g h".split(), "a b x d f g h h".split())
    assert total == 3
    assert blocks == [("c", "x"), ("e", ""), ("", "h")]
    assert [n for _, n in where] == [1, 1, 1]


def test_a_repeated_sentence_is_aligned_by_position_not_by_the_longest_run():
    sentence = "the quick brown fox jumps over the lazy dog".split()
    reference = sentence * 18
    reading = list(reference)
    for i in (5, 60, 140):
        reading[i] += "x"
    assert bench.edits(reference, reading)[0] == 3


def test_a_reading_that_loses_a_stretch_is_scored_by_the_words_lost():
    reference = [f"w{i}" for i in range(300)]
    reading = reference[:100] + reference[130:]
    assert bench.edits(reference, reading, band=20)[0] == 30


def test_character_edits_count_inside_the_differing_blocks_only():
    assert bench.char_edits([("cat", "cut"), ("", "ab")]) == 3


def test_pages_are_one_based_ranges_that_stop_at_the_end():
    assert bench.page_range("1-3,5", 4) == [0, 1, 2]
    assert bench.page_range("2-9", 4) == [1, 2, 3]
    assert bench.page_range("", 3) == [0, 1, 2]


def test_the_interval_is_zero_when_nothing_changed():
    assert bench.interval([(2, 2), (0, 0), (1, 1)], [100, 100, 100]) == (0.0, 0.0)
