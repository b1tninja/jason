from datetime import date
from pathlib import Path

import pytest

from jason.community.property_report import Valuation, index_markdown, mermaid_tenure, parcel_markdown
from jason.tasks.equity_charts import market_index, sales_of, unit_paths, unit_values
from jason.tasks.market_report import market_markdown, quadrant_chart, valuations, xychart
from jason.tasks.property_history import write_markdown
from tests.test_equity_charts import CHARACTERISTICS, PLANS, TODAY, _parcel, _step, _units


def test_an_xychart_holds_one_value_per_category_and_names_its_palette():
    text = xychart("Sale price each year", [2020, 2021], [("line", [300000.0, None]), ("bar", [2, 0])], "Dollars", palette=("#1d4ed8", "#c2410c"))
    lines = text.splitlines()
    assert lines[0].startswith('%%{init: {"themeVariables": {"xyChart": {"plotColorPalette": "#1d4ed8, #c2410c"}}}}%%')
    assert lines[1] == "xychart-beta" and lines[3] == "    x-axis [2020, 2021]"
    assert lines[4] == '    y-axis "Dollars"'  # a bar series keeps the axis from zero
    assert lines[5] == "    line [300000, 0]" and lines[6] == "    bar [2, 0]"
    lifted = xychart("t", [2020, 2021], [("line", [100.0, 110.0])], "Index").splitlines()[4]
    assert lifted.startswith('    y-axis "Index" 9') and "-->" in lifted  # lines alone get a lifted floor


def test_the_quadrant_and_the_valuations_read_the_unit_values_rows():
    values = unit_values(_units(), today=TODAY, characteristics=CHARACTERISTICS, plans=PLANS)
    chart = quadrant_chart(values)
    assert chart.startswith("quadrantChart") and '"A St": [' in chart and "quadrant-1 Paid more, gained" in chart
    assert '"D St"' not in chart  # no measured area, so no price per foot
    worth = valuations(values)
    one = worth["A ST"]
    assert one.last_price == 40_000_000 and one.source == "deed" and one.comps == 45_000_000 and one.per_sqft == 26_667
    assert one.size_estimate == 67_500_000 and one.rank == 2 and one.building_units == 3 and one.appreciation_pct == 12.5
    assert worth["D ST"].per_sqft is None and worth["D ST"].size_estimate is None


def test_the_market_page_carries_the_yearly_charts_the_quadrant_and_the_tables():
    text = market_markdown(_units(), CHARACTERISTICS, PLANS, title="T", today=TODAY, images={"Trend": "charts/trend.svg"})
    assert text.startswith("# T\n\n6 sales from 2020-01-15 to 2025-02-15, 5 priced by the deed and 1 by the base")
    assert "## Sales each year" in text and "x-axis [2020, 2021, 2022, 2023, 2024, 2025]" in text
    assert "bar [3, 1, 0, 1, 0, 1]" in text
    assert "line [310000, 350000, 350000, 400000, 400000, 450000]" in text  # the median carries through empty years
    assert "## Price per square foot each year" in text
    assert "orange is 2 bedrooms" not in text  # one two-bedroom sale is below the line minimum
    assert "quadrantChart" in text and "## By building" in text and "## By plan" in text
    assert "| Plan 1 | Watt Communities at Mystique | 3 | 1500 | 2 |" in text
    assert "![Trend](charts/trend.svg)" in text


def test_the_tenure_gantt_marks_the_current_owner_a_foreclosure_and_a_milestone():
    item = _parcel("9", "E ST", 1, (
        _step(1, "202001150001", "developer closing", ("ONE",), price=30_000_000, developer="Watt"),
        _step(2, "202201150002", "foreclosure", ("BANK",), price=25_000_000),
        _step(3, "202301150003", "reo resale", ("TWO", "THREE"), price=32_000_000),
        _step(4, "202401150004", "restatement", ("TWO TR",), reassesses=False),
    ))
    text = mermaid_tenure(item, today=date(2025, 9, 1))
    assert text.splitlines()[0] == "gantt"
    assert "    ONE :crit, 2020-01-15, 2022-01-15" in text
    assert "    BANK :done, 2022-01-15, 2023-01-15" in text
    assert "    TWO +1 :active, 2023-01-15, 2025-09-01" in text
    assert "    section Other instruments" in text and "    restatement 202401150004 :milestone, 2024-01-15, 0d" in text


def test_the_parcel_page_states_the_home_the_value_and_counts_far_liens():
    item = _units()[0]
    value = Valuation(last_price=40_000_000, source="deed", comps=45_000_000, comps_basis="community, 12 months, 1 sales",
                      indexed=45_000_000, size_estimate=67_500_000, size_basis="community, 12 months, 1 sales", per_sqft=26_667,
                      community_per_sqft=45_000, appreciation_pct=12.5, annual_pct=4.6, rank=2, building_units=3, percentile=50, assessed=41_000_000)
    text = parcel_markdown(item, unit=CHARACTERISTICS["1"], plan=PLANS[0], value=value, chart="charts/1.svg", today=TODAY)
    assert "- **Home** 3 bedrooms, 2.5 baths, 1,500 sq ft, built 2020; Plan 1 of Watt Communities at Mystique" in text
    assert "## Who held it" in text and "    TWO :active, 2023-01-15, 2025-09-01" in text
    assert "- **Last price** $400,000 on 2023-01-15, which the deed states, $266 a square foot" in text
    assert "- **Recent comps** $450,000, the trailing median for community, 12 months, 1 sales" in text
    assert "- **Size-adjusted comps** $675,000, the measured area at the trailing median per square foot for community, 12 months, 1 sales at $450 a foot" in text
    assert "- **Appreciation** +12.5% against the last price, +4.6% a year; ranks 2 of 3 in the building and sits at the 50th percentile of the community" in text
    assert "![This unit's indexed value, its sales, and the community and building medians](charts/1.svg)" in text
    index = index_markdown(_units(), links=(("The market", "market.md"),), homes={"1": "3 bd, 2.5 ba, 1,500 sf, Plan 1"})
    assert "- [The market](market.md)" in index and "| Watt Communities at Mystique | 3 bd, 2.5 ba, 1,500 sf, Plan 1 | 2020-01-15 |" in index


def test_write_markdown_draws_the_market_page_and_the_charts(tmp_path: Path):
    pytest.importorskip("matplotlib")
    written = write_markdown(_units(), tmp_path, title="T", characteristics=CHARACTERISTICS, plans=PLANS, today=TODAY)
    names = sorted(path.relative_to(tmp_path).as_posix() for path in written)
    assert "market.md" in names and "README.md" in names and "1.md" in names
    assert "charts/trend.svg" in names and "charts/per-sqft.svg" in names and "charts/size.svg" in names and "charts/1.svg" in names
    page = (tmp_path / "1.md").read_text(encoding="utf-8")
    assert "![This unit's indexed value, its sales, and the community and building medians](charts/1.svg)" in page
    assert "<svg" in (tmp_path / "charts" / "1.svg").read_text(encoding="utf-8")[:300]
    market = (tmp_path / "market.md").read_text(encoding="utf-8")
    assert "![Sale prices by building over time, with the community 12-month median (solid) and mean (dashed)](charts/trend.svg)" in market
    index = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "- [The market: prices by year, per square foot, and where each unit stands](market.md)" in index
    without = write_markdown(_units(), tmp_path / "plain", title="T", charts=False, today=TODAY)
    assert not any("charts/" in path.as_posix() for path in without)
    assert "## Value" in (tmp_path / "plain" / "1.md").read_text(encoding="utf-8")


def test_unit_paths_feed_the_unit_chart():
    sales = sales_of(_units(), CHARACTERISTICS, PLANS)
    values = unit_values(_units(), today=TODAY, characteristics=CHARACTERISTICS, plans=PLANS)
    rows = unit_paths(sales, values, today=TODAY)
    index_rows = market_index(sales, (1, 2), today=TODAY)
    assert len(rows) == len(index_rows)  # one row per month on both, so the chart reads them side by side


def test_the_building_page_lists_units_tenures_and_sales_by_year():
    from jason.community.property_report import building_markdown, mermaid_building_tenure
    from jason.community.reports import PublicReport
    from jason.community.symbols import Building

    report = PublicReport("154410SA", Building.BLDG_1, 3, 7, date(2020, 2, 28), "Watt Communities at Mystique", annexation=date(2019, 12, 20))
    text = building_markdown(1, _units(), title="T: building 1", report=report, homes={"1": "3 bd, 2.5 ba, 1,500 sf, Plan 1", "2": "3 bd, 2.5 ba, 1,500 sf, Plan 1"}, today=TODAY)
    assert text.startswith("# T: building 1\n\n- **Units** 3\n- **Phase** 3, Bureau file 154410SA")
    assert "- **Plans** 2 × Plan 1" in text and "- **Sales on record** 5, 5 priced, median $320,000" in text
    assert "| [A ST](1.md) | 3 bd, 2.5 ba, 1,500 sf, Plan 1 | TWO | 2023-01-15 | $400,000 | 0 |" in text
    assert "    section A St" in text and "    TWO :active, 2023-01-15, 2025-09-01" in text and "    ONE :done, 2020-01-15, 2023-01-15" in text
    assert "xychart-beta" in text and "x-axis [2020, 2021, 2022, 2023, 2024, 2025]" in text and "line [310000.0, 310000.0, 310000.0, 400000.0, 400000.0, 450000.0]" in text
    assert mermaid_building_tenure(()).endswith("axisFormat %Y")
