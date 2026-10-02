"""SVG charts for the Markdown reports, drawn with matplotlib.

Mermaid draws no scatter with lines through it, so these are images the
pages link: sale prices by building over time with the community moving
averages, the same per square foot, price against living area, and each
unit's indexed value path with its sales and the medians. matplotlib is an
optional extra; without it ``available()`` is false and nothing is drawn.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from jason.tasks.equity_charts import (
    BUILDING_COLORS,
    BUILDING_MINIMUM,
    RECENT_YEARS,
    Sale,
    _months,
    trailing,
)

MARKET_CHARTS = {
    "trend": "Sale prices by building over time, with the community 12-month median (solid) and mean (dashed)",
    "per-sqft": "Price per square foot by building over time, with the community 12-month median",
    "size": "Sale price against living area, by bedroom count; a black edge marks the last five years",
}


def available() -> bool:
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        return False
    return True


def render_market_charts(sales: tuple[Sale, ...], out_dir: Path, *, today: date | None = None) -> dict[str, Path]:
    """Write the three market images under ``out_dir`` and return them by name."""
    if not sales or not available():
        return {}
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    today = today or date.today()
    out_dir.mkdir(parents=True, exist_ok=True)
    buildings = sorted({sale.building for sale in sales})
    months = _months(sales[0].recorded, today)
    month_days = [date(int(m[:4]), int(m[5:7]), 1) for m in months]
    written: dict[str, Path] = {}

    def averages(per_sqft: bool):
        med, mean = [], []
        for month in months:
            _c, m, a = trailing(sales, month, per_sqft=per_sqft)
            med.append(m / 100 if m is not None else float("nan"))
            mean.append(a / 100 if a is not None else float("nan"))
        return med, mean

    for name, per_sqft in (("trend", False), ("per-sqft", True)):
        fig, ax = plt.subplots(figsize=(11, 5.5))
        for building in buildings:
            points = [(s.recorded, (s.per_sqft if per_sqft else s.price)) for s in sales if s.building == building]
            points = [(d, v / 100) for d, v in points if v]
            if not points:
                continue
            ax.scatter([d for d, _ in points], [v for _, v in points], s=28, color=_color(building), label=f"Building {building}", zorder=3)
        med, mean = averages(per_sqft)
        ax.plot(month_days, med, color="#111827", linewidth=2, label="Community 12-month median", zorder=4)
        if not per_sqft:
            ax.plot(month_days, mean, color="#6b7280", linewidth=1.5, linestyle="--", label="Community 12-month mean", zorder=4)
        ax.set_title(MARKET_CHARTS[name].split(",")[0])
        ax.set_ylabel("Dollars per sq ft" if per_sqft else "Dollars")
        ax.xaxis.set_major_locator(mdates.YearLocator(2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.yaxis.set_major_formatter(_money)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8, ncol=3, loc="upper left")
        written[name] = _save(fig, out_dir / f"{name}.svg")

    sized = [s for s in sales if s.living_sqft]
    if sized:
        fig, ax = plt.subplots(figsize=(9, 5.5))
        cutoff = date(today.year - RECENT_YEARS, today.month, 1)
        beds = sorted({s.bedrooms for s in sized if s.bedrooms})
        palette = ["#1d4ed8", "#c2410c", "#15803d", "#b91c1c"]
        for index, count in enumerate(beds):
            group = [s for s in sized if s.bedrooms == count]
            ax.scatter(
                [s.living_sqft for s in group], [s.price / 100 for s in group], s=30, color=palette[index % len(palette)],
                edgecolors=["black" if s.recorded >= cutoff else "none" for s in group], linewidths=1.2,
                label=f"{count} bedrooms", zorder=3,
            )
        rest = [s for s in sized if not s.bedrooms]
        if rest:
            ax.scatter([s.living_sqft for s in rest], [s.price / 100 for s in rest], s=30, color="#9ca3af", label="bedrooms unknown", zorder=3)
        ax.set_title("Sale price against living area")
        ax.set_xlabel("Living sq ft")
        ax.set_ylabel("Dollars")
        ax.yaxis.set_major_formatter(_money)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        written["size"] = _save(fig, out_dir / "size.svg")
    return written


def render_unit_chart(
    address: str,
    building: int | None,
    sales: tuple[Sale, ...],
    index_rows: list[list[Any]],
    path_rows: list[list[Any]],
    out: Path,
) -> Path | None:
    """One unit's indexed value path, its sales, and the community and building 12-month medians."""
    if not available() or len(index_rows) < 2 or not path_rows or address not in path_rows[0]:
        return None
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    column = path_rows[0].index(address)
    header = index_rows[0]
    building_col = header.index(f"Building {building} median (12 mo)") if building and f"Building {building} median (12 mo)" in header else None
    days, community, mine, own = [], [], [], []
    by_month = {str(row[0]).lstrip("'"): row for row in path_rows[1:]}
    for row in index_rows[1:]:
        month = str(row[0]).lstrip("'")
        days.append(date(int(month[:4]), int(month[5:7]), 1))
        community.append(float(row[2]) if row[2] not in ("", None) else float("nan"))
        mine.append(float(row[building_col]) if building_col is not None and row[building_col] not in ("", None) else float("nan"))
        path = by_month.get(month)
        own.append(float(path[column]) if path is not None and column < len(path) and path[column] not in ("", None) else float("nan"))
    unit_sales = [s for s in sales if s.address == address]
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(days, community, color="#111827", linewidth=1.5, label="Community 12-month median")
    if building_col is not None:
        ax.plot(days, mine, color=_color(building), linewidth=1.5, linestyle="--", label=f"Building {building} 12-month median ({BUILDING_MINIMUM}+ sales)")
    ax.plot(days, own, color="#b91c1c", linewidth=2.2, label="This unit, indexed from its last price")
    if unit_sales:
        ax.scatter([s.recorded for s in unit_sales], [s.price / 100 for s in unit_sales], s=70, color="#b91c1c", edgecolors="black", zorder=5, label="This unit's sales")
        for s in unit_sales:
            ax.annotate(f"${s.price // 100:,}" + ("" if s.source == "deed" else " (base)"), (s.recorded, s.price / 100), textcoords="offset points", xytext=(4, 8), fontsize=8)
    ax.set_title(address.title())
    ax.set_ylabel("Dollars")
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.yaxis.set_major_formatter(_money)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="upper left")
    return _save(fig, out)


def _color(building: int | None) -> tuple[float, float, float]:
    return BUILDING_COLORS.get(building or 0, (0.5, 0.5, 0.5))


def _money(value: float, _position: Any = None) -> str:
    return f"${value:,.0f}"


def _save(fig: Any, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, format="svg", metadata={"Date": None})
    import matplotlib.pyplot as plt

    plt.close(fig)
    return path
