"""The splitter's suggestion pass on a made-up gold set (docs/pdf-splitter.md, 4.7): each archetype with the starts it truly has, the
reason in words, confidence that falls as the evidence goes, and the time it takes."""

import time

import pytest

from jason.community import document_segments as ds
from jason.community import split_gold as g
from jason.community import split_suggest as sg
from jason.community.split_session import PageFact
from jason.tasks import split_session as ss

TEXT_ARCHETYPES = ("letters", "numbered", "blank-separated", "duplex", "sizes")


def read(pdf, tmp_path):
    path = tmp_path / "gold.pdf"
    path.write_bytes(pdf)
    facts, infos = ss.scan(path)
    return facts, infos, sg.suggest(facts, infos)


@pytest.mark.parametrize("name", TEXT_ARCHETYPES)
def test_a_text_archetype_is_recovered_at_medium_or_better_with_no_false_start(name, tmp_path):
    gold = g.ARCHETYPES[name]()
    _facts, _infos, found = read(gold.pdf, tmp_path)
    shown = [s.page for s in found if s.confidence >= 0.6]
    score = g.prf(shown, gold.starts)
    assert score["precision"] == 1.0 and score["recall"] == 1.0, (name, gold.starts, shown)
    assert g.taps_saved(shown, gold.starts)["withSuggestions"] == 0
    for s in found:
        assert s.page != 1 and s.reader == "rules" and s.tier == "suggested" and s.state == "open"
        assert s.why.startswith(f"Page {s.page}. ") and s.signals and all(sig.said.endswith(".") for sig in s.signals)
        assert s.band in ("High", "Medium", "Low")


def test_an_image_only_scan_gets_only_low_suggestions_from_the_scan_itself(tmp_path):
    gold = g.mixed_dpi()
    facts, infos, found = read(gold.pdf, tmp_path)
    assert [f.has_text for f in facts] == [False] * gold.pages and [f.dpi for f in facts][:4] == [200, 200, 200, 300]
    assert [s.page for s in found] == [4, 7] and all(s.band == "Low" for s in found)
    assert {sig.signal for s in found for sig in s.signals} == {"dpi-change", "colour-change"}
    assert "scan resolution changes" in found[0].why and "colour mode changes" in found[0].why


def test_a_blank_separator_is_a_signal_only_where_blanks_are_rare(tmp_path):
    _f, _i, rare = read(g.blank_separated().pdf, tmp_path)
    assert {sig.signal for s in rare for sig in s.signals} >= {"blank-before"}
    facts, _infos, backs = read(g.duplex().pdf, tmp_path)
    assert sum(f.blank == "blank" for f in facts) / len(facts) > ds.DUPLEX
    assert "blank-before" not in {sig.signal for s in backs for sig in s.signals}      # a duplex scan's blanks are backs
    assert all(f.blank != "blank" or s.page != f.n for s in backs for f in facts)       # a blank page is never itself a start


def test_taking_the_text_layer_away_lowers_confidence_never_raises_it(tmp_path):
    gold = g.numbered()
    _f, _i, with_text = read(gold.pdf, tmp_path)
    _f2, _i2, without = read(g.strip_text(gold.pdf), tmp_path)
    top_with = max(s.confidence for s in with_text)
    top_without = max((s.confidence for s in without), default=0.0)
    assert top_with > 0.9 and top_without < top_with
    by_page = {s.page: s.confidence for s in without}
    assert all(by_page.get(s.page, 0.0) <= s.confidence for s in with_text)


def test_the_confidence_is_a_logistic_of_the_summed_weights_and_is_monotonic():
    values = [sg.confidence(x / 10) for x in range(0, 30)]
    assert values == sorted(values) and 0.0 < values[0] < 0.5 < values[-1] < 1.0
    assert abs(sg.confidence(sg.MIDPOINT) - 0.5) < 1e-9
    assert sg.confidence(ds.THRESHOLD) > 0.6                         # a page the rule pass would start a document at is at least Medium


def test_the_rule_pass_over_two_thousand_pages_takes_a_few_seconds(tmp_path):
    pages, facts = [], []
    for n in range(1, 2001):
        top = n % 7 == 1
        lines = [ds.Line(f"Page {1 if top else n % 7} of 7", 0.95, 0.97, 0.4, 0.6, 9.0)]
        if top:
            lines.insert(0, ds.Line("REPORT", 0.08, 0.1, 0.4, 0.6, 18.0, True))
        lines.append(ds.Line("Body text of the page goes on for some time here." * 2, 0.3, 0.32, 0.1, 0.9, 10.0))
        pages.append(ds.build_page(n, 612, 792, lines))
        facts.append(PageFact(n, 612, 792))
    t = time.perf_counter()
    found = sg.suggest(facts, pages)
    took = time.perf_counter() - t
    assert took < 5.0, took
    assert len(found) >= 280 and all(s.page % 7 == 1 for s in found if s.confidence > 0.9)


def test_facts_come_from_the_page_rows_without_a_second_measuring_code(tmp_path):
    gold = g.numbered()
    facts, infos, _found = read(gold.pdf, tmp_path)
    assert [f.label for f in facts[:4]] == [(1, 3), (2, 3), (3, 3), (1, 2)]
    assert all(f.has_text and f.blank == "content" and f.width == 612 for f in facts)
    assert facts[3].title.startswith("REPORT") and len(facts[0].lqip) == 512
    assert facts[0].words == infos[0].words


def test_the_scores_and_the_calibration_table_report_precision_recall_taps_and_bands():
    assert g.prf([4, 6, 9], [1, 4, 6, 10]) == {"precision": 0.667, "recall": 0.667, "f1": 0.667, "tp": 2, "fp": 1, "fn": 1}
    assert g.taps_saved([4, 6, 9], [1, 4, 6, 10]) == {"withoutSuggestions": 3, "withSuggestions": 2, "saved": 1}
    table = g.calibration([(0.95, True), (0.9, True), (0.7, False), (0.4, False)])
    assert [(r["band"], r["count"], r["realShare"]) for r in table] == [("High", 2, 1.0), ("Medium", 1, 0.0), ("Low", 1, 0.0)]


def test_the_fuzz_script_builds_degrades_recovers_and_reports(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = Path(__file__).resolve().parent.parent / "scripts" / "split_fuzz.py"
    env = {**os.environ, "PYTHONPATH": str(script.parent.parent / "src")}

    def run(*argv):
        done = subprocess.run([sys.executable, str(script), *argv], capture_output=True, text=True, env=env)
        assert done.returncode == 0, done.stderr
        return done.stdout

    cache = str(tmp_path / "cache")
    run("gold", "--cache", cache, "--only", "numbered,sizes")
    run("variants", "--cache", cache, "--only", "numbered,sizes")
    run("recover", "--cache", cache, "--without", "size-change")
    out = run("score", "--cache", cache)
    assert "numbered" in out and "sizes" in out
    report = run("report", "--cache", cache, "--out", str(tmp_path / "report.md"))
    text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "precision" in text.lower() and "calibration" in text.lower() and report is not None
