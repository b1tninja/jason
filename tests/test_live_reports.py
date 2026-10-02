from datetime import datetime

from jason.tasks import live_reports
from jason.tasks.live_reports import Report, embed, expand, refresh, snapshot


def _demo(monkeypatch, run):
    monkeypatch.setitem(live_reports.REPORTS, "demo", Report("demo", "Demo signals", "jason report demo", "the demo store", run))


def test_a_note_names_a_report_and_shows_its_last_run_with_its_command_and_time(monkeypatch, tmp_path):
    calls = []

    def rows(data_dir, community, params, context):
        calls.append(data_dir)
        return ["- **1 Example Walk**: unclear."]

    _demo(monkeypatch, rows)
    lines = expand("Before the facts: {REPORT:demo} After: the board's comment.", tmp_path, None,
                   now=datetime(2026, 10, 20, 9, 5))
    assert lines[0] == "Before the facts:"
    assert lines[2] == ("**Demo signals**, as of October 20, 2026 09:05 (`jason report demo`; reads the demo store). "
                        "A lead to confirm, not a finding.")
    assert "- **1 Example Walk**: unclear." in lines and lines[-1] == "After: the board's comment."
    # a report never run is run once; after that the document shows the saved run without running it again
    expand("{REPORT:demo}", tmp_path, None)
    assert calls == [tmp_path]
    assert (tmp_path / "reports" / "live" / "demo.md").read_text(encoding="utf-8").startswith("# Demo signals")


def test_refreshing_one_report_changes_what_every_document_shows(monkeypatch, tmp_path):
    answers = iter([["- first run."], ["- second run."]])
    _demo(monkeypatch, lambda d, c, p, x: next(answers))
    refresh("demo", tmp_path, None, now=datetime(2026, 10, 2, 8, 0))
    assert "- first run." in embed("demo", tmp_path, None, now=datetime(2026, 10, 3))
    refresh("demo", tmp_path, None, now=datetime(2026, 10, 19, 8, 0))
    assert "- second run." in embed("demo", tmp_path, None, now=datetime(2026, 10, 19, 9))


def test_a_stale_or_failed_refresh_keeps_the_last_rows_and_says_so(monkeypatch, tmp_path):
    _demo(monkeypatch, lambda d, c, p, x: ["- good rows."])
    refresh("demo", tmp_path, None, now=datetime(2026, 10, 1, 8, 0))

    def broken(data_dir, community, params, context):
        raise RuntimeError("Keeper login needed")

    _demo(monkeypatch, broken)
    snap = refresh("demo", tmp_path, None, now=datetime(2026, 10, 19, 8, 0))
    assert snap.error == "Keeper login needed" and snap.ran_at.startswith("2026-10-01")
    lines = embed("demo", tmp_path, None, now=datetime(2026, 10, 19, 9))
    assert "- good rows." in lines
    assert any("18 days old" in l and "`jason report demo`" in l for l in lines)
    assert any("could not run (Keeper login needed)" in l for l in lines)
    assert snapshot("demo", tmp_path).rows == ["- good rows."]
    assert "no report named nope" in expand("{REPORT:nope}", tmp_path, None)[0]


def test_a_packet_run_already_built_is_included_by_its_period_and_never_rebuilt(tmp_path):
    import json
    from datetime import date

    runs = [{"id": 2, "name": "Treasurer's Report - 2026-09", "packet": "Treasurer's Report", "period": "2026-09",
             "completedAt": "2026-10-08 14:02:00", "pages": 23, "sections": ["Balance Sheet", "Aging of Accounts"],
             "fileName": "Treasurer's Report - 2026-09.pdf", "sha256": "ab", "library": None, "pdf": "",
             "driveId": "DRIVE1", "notes": []},
            {"id": 1, "name": "Treasurer's Report - 2026-08", "packet": "Treasurer's Report", "period": "2026-08",
             "completedAt": "2026-09-11 00:16:39", "pages": 22, "sections": ["Balance Sheet"], "fileName": "x.pdf",
             "sha256": "cd", "library": {"id": 7, "path": "Financials/Treasurer's Report - 2026-08.pdf"}, "pdf": "",
             "driveId": "", "notes": []}]
    (tmp_path / "payhoa").mkdir()
    (tmp_path / "payhoa" / "report-runs.json").write_text(json.dumps({"indexedAt": "2026-10-09T00:00:00", "runs": runs}))
    october = {"on": date(2026, 10, 20)}
    lines = expand("Last month: {REPORT:treasurers-report period=previous-month}", tmp_path, None, context=october)
    assert any("Treasurer's Report, September 2026: PayHOA's packet run of 2026-10-08 14:02, 23 pages" in l for l in lines)
    assert any("https://drive.google.com/file/d/DRIVE1/view" in l for l in lines)
    august = expand("{REPORT:treasurers-report period=2026-08}", tmp_path, None, context=october)
    assert any("The library holds the same file" in l for l in august)
    november = expand("{REPORT:treasurers-report period=previous-month}", tmp_path, None, context={"on": date(2026, 11, 17)})
    assert any("PayHOA has no Treasurer's Report run for October 2026" in l and "the newest is September 2026" in l
               and "jason does not build packets" in l for l in november)
    # each setting is its own snapshot
    assert (tmp_path / "reports" / "live" / "treasurers-report--period-2026-08.md").is_file()
