"""Deterministic, accessible SVG charts for HTML reports and portfolio assets."""

from __future__ import annotations

from html import escape
from typing import Any

from .public import GUARD_FAILURE_LABEL, public_failure_label
from .theme import (
    BLUE,
    CORAL,
    FONT_DISPLAY,
    FONT_MONO,
    FONT_SANS,
    GRID,
    INK,
    METHOD_IDENTITIES,
    PAPER,
    SUCCESS,
    SURFACE,
    WITHHELD,
    method_identity,
    vega_config,
)


def _number(value: Any) -> float:
    return 0.0 if value is None else float(value)


def grouped_bar_svg(
    rows: list[dict[str, Any]],
    *,
    title: str,
    description: str,
    first_key: str,
    first_label: str,
    second_key: str,
    second_label: str,
    percentage: bool = False,
    first_numerator_key: str | None = None,
    first_denominator_key: str | None = None,
    second_numerator_key: str | None = None,
    second_denominator_key: str | None = None,
    integer: bool = False,
    first_color: str = BLUE,
    second_color: str = METHOD_IDENTITIES[2][1],
) -> str:
    """Render two values per method with text labels so color is never the only cue."""

    width, left, right = 1100, 400, 230
    row_height, top = 66, 82
    height = top + row_height * len(rows) + 54
    plot_width = width - left - right
    values = [_number(row.get(key)) for row in rows for key in (first_key, second_key)]
    maximum = max([*values, 1.0 if percentage else 0.0])

    def bar(
        row: dict[str, Any],
        value: float,
        y: float,
        color: str,
        label: str,
        numerator_key: str | None,
        denominator_key: str | None,
    ) -> str:
        length = 0.0 if maximum == 0 else plot_width * value / maximum
        shown = (
            f"{100 * value:.1f}%" if percentage else str(int(value)) if integer else f"{value:.3f}"
        )
        if numerator_key and denominator_key:
            shown += f" ({int(row[numerator_key])}/{int(row[denominator_key])})"
        return (
            f'<rect x="{left}" y="{y:.1f}" width="{length:.1f}" height="15" rx="3" fill="{color}"/>'
            f'<text x="{width - 16}" y="{y + 12:.1f}" text-anchor="end" class="value">{escape(label)} {escape(shown)}</text>'
        )

    elements: list[str] = []
    for index, row in enumerate(rows):
        y = top + index * row_height
        code, identity_color = method_identity(index)
        elements.append(
            f'<line x1="16" y1="{y + 18}" x2="34" y2="{y + 18}" '
            f'stroke="{identity_color}" stroke-width="4"/>'
            f'<text x="42" y="{y + 23}" class="method-code">{code}</text>'
            f'<text x="62" y="{y + 23}" class="method">'
            f"{escape(str(row['display_name']))}</text>"
        )
        elements.append(
            bar(
                row,
                _number(row.get(first_key)),
                y,
                first_color,
                first_label,
                first_numerator_key,
                first_denominator_key,
            )
        )
        elements.append(
            bar(
                row,
                _number(row.get(second_key)),
                y + 22,
                second_color,
                second_label,
                second_numerator_key,
                second_denominator_key,
            )
        )
    axis_labels = ""
    if percentage:
        axis_labels = (
            f'<text x="{left}" y="58" class="tick">0%</text>'
            f'<text x="{left + plot_width / 2}" y="58" text-anchor="middle" class="tick">50%</text>'
            f'<text x="{left + plot_width}" y="58" text-anchor="end" class="tick">100%</text>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="chart-title chart-desc" viewBox="0 0 {width} {height}">
<title id="chart-title">{escape(title)}</title><desc id="chart-desc">{escape(description)}</desc>
<style>.title{{font:700 22px {FONT_DISPLAY};fill:{INK}}}.method{{font:600 13px {FONT_SANS};fill:{INK}}}.method-code{{font:700 12px {FONT_MONO};fill:{INK}}}.value{{font:12px {FONT_MONO};fill:{INK}}}.tick{{font:11px {FONT_SANS};fill:{INK}}}.axis{{stroke:{GRID};stroke-width:1}}</style>
<rect width="100%" height="100%" fill="{SURFACE}"/><text x="16" y="35" class="title">{escape(title)}</text>
{axis_labels}<line x1="{left}" y1="64" x2="{left}" y2="{height - 25}" class="axis"/>{"".join(elements)}</svg>"""


def coverage_availability_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return paired chart rows only for scientifically applicable interval methods."""

    chart_rows: list[dict[str, Any]] = []
    for row in rows:
        if int(row["interval_applicable_attempts"]) == 0:
            continue
        if row["conditional_coverage"] is not None:
            chart_rows.append(
                {
                    "method": row["display_name"],
                    "metric": "Conditional coverage",
                    "rate": row["conditional_coverage"],
                    "numerator": row["conditional_coverage_numerator"],
                    "denominator": row["conditional_coverage_denominator"],
                }
            )
        chart_rows.append(
            {
                "method": row["display_name"],
                "metric": "Interval availability",
                "rate": row["interval_availability"],
                "numerator": row["interval_available_runs"],
                "denominator": row["attempted_runs"],
            }
        )
    return chart_rows


def estimation_error_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chart_rows: list[dict[str, Any]] = []
    for row in rows:
        if row["absolute_bias"] is not None:
            chart_rows.append(
                {
                    "method": row["display_name"],
                    "metric": "Absolute bias",
                    "error_value": row["absolute_bias"],
                }
            )
        if row["rmse"] is not None:
            chart_rows.append(
                {
                    "method": row["display_name"],
                    "metric": "RMSE",
                    "error_value": row["rmse"],
                }
            )
    return chart_rows


def completion_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chart_rows: list[dict[str, Any]] = []
    for row in rows:
        reported = int(row["point_estimate_available_runs"])
        attempted = int(row["attempted_runs"])
        failure_codes = row.get("failure_code_counts", {})
        reasons = [public_failure_label(code) for code in failure_codes]
        reason = ", ".join(reasons) if reasons else "No classified failures"
        chart_rows.extend(
            (
                {
                    "method": row["display_name"],
                    "status": "Reported",
                    "count": reported,
                    "attempted": attempted,
                    "reason": "Point estimate reported",
                },
                {
                    "method": row["display_name"],
                    "status": "Withheld or failed",
                    "count": attempted - reported,
                    "attempted": attempted,
                    "reason": reason,
                },
            )
        )
    return chart_rows


def paired_percentage_chart_spec(method_order: list[str]) -> dict[str, Any]:
    """Vega-Lite paired horizontal bars with an explicit non-stacked 0-100% scale."""

    return {
        "autosize": {"type": "fit-x", "contains": "padding", "resize": True},
        "height": max(180, 52 * len(method_order)),
        "mark": {"type": "bar", "cornerRadiusEnd": 3, "height": 14},
        "encoding": {
            "y": {
                "field": "method",
                "type": "nominal",
                "sort": method_order,
                "title": None,
                "axis": {"labelLimit": 520, "labelPadding": 8},
            },
            "yOffset": {
                "field": "metric",
                "sort": ["Conditional coverage", "Interval availability"],
            },
            "x": {
                "field": "rate",
                "type": "quantitative",
                "title": "Rate",
                "scale": {"domain": [0, 1]},
                "axis": {"format": ".0%", "values": [0, 0.25, 0.5, 0.75, 1]},
                "stack": None,
            },
            "color": {
                "field": "metric",
                "type": "nominal",
                "scale": {
                    "domain": ["Conditional coverage", "Interval availability"],
                    "range": [BLUE, METHOD_IDENTITIES[2][1]],
                },
                "legend": {"title": None, "orient": "top"},
            },
            "opacity": {
                "field": "metric",
                "type": "nominal",
                "sort": ["Conditional coverage", "Interval availability"],
                "scale": {
                    "domain": ["Conditional coverage", "Interval availability"],
                    "range": [1.0, 0.72],
                },
            },
            "tooltip": [
                {"field": "method", "type": "nominal", "title": "Method"},
                {"field": "metric", "type": "nominal", "title": "Metric"},
                {"field": "rate", "type": "quantitative", "title": "Rate", "format": ".1%"},
                {"field": "numerator", "type": "quantitative", "title": "Numerator"},
                {"field": "denominator", "type": "quantitative", "title": "Denominator"},
            ],
        },
        "config": vega_config(),
    }


def estimation_error_chart_spec(method_order: list[str]) -> dict[str, Any]:
    """Vega-Lite horizontal dot plot; absolute bias and RMSE remain separate."""

    return {
        "autosize": {"type": "fit-x", "contains": "padding", "resize": True},
        "height": max(210, 58 * len(method_order)),
        "mark": {"type": "point", "filled": True, "size": 120},
        "encoding": {
            "y": {
                "field": "method",
                "type": "nominal",
                "sort": method_order,
                "title": None,
                "axis": {"labelLimit": 520, "labelPadding": 8},
            },
            "yOffset": {"field": "metric", "sort": ["Absolute bias", "RMSE"]},
            "x": {
                "field": "error_value",
                "type": "quantitative",
                "title": "Error magnitude",
                "scale": {"zero": True},
                "stack": None,
            },
            "color": {
                "field": "metric",
                "type": "nominal",
                "scale": {
                    "domain": ["Absolute bias", "RMSE"],
                    "range": [BLUE, METHOD_IDENTITIES[2][1]],
                },
                "legend": {"title": None, "orient": "top"},
            },
            "shape": {
                "field": "metric",
                "type": "nominal",
                "sort": ["Absolute bias", "RMSE"],
                "scale": {"domain": ["Absolute bias", "RMSE"], "range": ["circle", "diamond"]},
            },
            "tooltip": [
                {"field": "method", "type": "nominal", "title": "Method"},
                {"field": "metric", "type": "nominal", "title": "Metric"},
                {
                    "field": "error_value",
                    "type": "quantitative",
                    "title": "Value",
                    "format": ".3f",
                },
            ],
        },
        "config": vega_config(),
    }


def completion_chart_spec(method_order: list[str], maximum_attempts: int) -> dict[str, Any]:
    """Vega-Lite completed-versus-failed bars without stacking the counts."""

    return {
        "autosize": {"type": "fit-x", "contains": "padding", "resize": True},
        "height": max(240, 72 * len(method_order)),
        "mark": {"type": "bar", "cornerRadiusEnd": 3, "height": 14},
        "encoding": {
            "y": {
                "field": "method",
                "type": "nominal",
                "sort": method_order,
                "title": None,
                "axis": {"labelLimit": 520, "labelPadding": 8},
            },
            "yOffset": {"field": "status", "sort": ["Reported", "Withheld or failed"]},
            "x": {
                "field": "count",
                "type": "quantitative",
                "title": "Attempts",
                "scale": {"domain": [0, maximum_attempts]},
                "stack": None,
            },
            "color": {
                "field": "status",
                "type": "nominal",
                "scale": {
                    "domain": ["Reported", "Withheld or failed"],
                    "range": [SUCCESS, WITHHELD],
                },
                "legend": {"title": None, "orient": "top"},
            },
            "opacity": {
                "field": "status",
                "type": "nominal",
                "sort": ["Reported", "Withheld or failed"],
                "scale": {
                    "domain": ["Reported", "Withheld or failed"],
                    "range": [1.0, 0.72],
                },
            },
            "tooltip": [
                {"field": "method", "type": "nominal", "title": "Method"},
                {"field": "status", "type": "nominal", "title": "Outcome"},
                {"field": "count", "type": "quantitative", "title": "Count"},
                {"field": "attempted", "type": "quantitative", "title": "Attempts"},
                {"field": "reason", "type": "nominal", "title": "Reason"},
            ],
        },
        "config": vega_config(),
    }


def coverage_availability_svg(rows: list[dict[str, Any]]) -> str:
    applicable = [row for row in rows if int(row["interval_applicable_attempts"]) > 0]
    return grouped_bar_svg(
        applicable,
        title="Coverage beside interval availability",
        description=(
            "Paired, non-stacked bars show conditional coverage and interval availability only "
            "for methods whose intervals are scientifically applicable."
        ),
        first_key="conditional_coverage",
        first_label="Coverage",
        second_key="interval_availability",
        second_label="Availability",
        percentage=True,
        first_numerator_key="conditional_coverage_numerator",
        first_denominator_key="conditional_coverage_denominator",
        second_numerator_key="interval_available_runs",
        second_denominator_key="attempted_runs",
        first_color=BLUE,
        second_color=METHOD_IDENTITIES[2][1],
    )


def estimation_error_svg(rows: list[dict[str, Any]]) -> str:
    return grouped_bar_svg(
        rows,
        title="Estimation error against the known answer",
        description=(
            "Paired, non-stacked bars show average directional miss and typical overall error "
            "against the known answer."
        ),
        first_key="absolute_bias",
        first_label="Absolute bias",
        second_key="rmse",
        second_label="RMSE",
        first_color=BLUE,
        second_color=METHOD_IDENTITIES[2][1],
    )


def completion_svg(rows: list[dict[str, Any]]) -> str:
    summary_rows: list[dict[str, Any]] = []
    for row in rows:
        reported = int(row["point_estimate_available_runs"])
        attempted = int(row["attempted_runs"])
        summary_rows.append(
            {
                "display_name": row["display_name"],
                "reported": reported,
                "withheld": attempted - reported,
            }
        )
    return grouped_bar_svg(
        summary_rows,
        title="Reported versus withheld or failed",
        description=(
            "Paired, non-stacked bars show reported point estimates and withheld or failed attempts. "
            f"The public guard label is {GUARD_FAILURE_LABEL}."
        ),
        first_key="reported",
        first_label="Reported",
        second_key="withheld",
        second_label="Withheld/failed",
        integer=True,
        first_color=SUCCESS,
        second_color=WITHHELD,
    )


def failure_svg(rows: list[dict[str, Any]]) -> str:
    """Backward-compatible alias for the corrected completion panel."""

    return completion_svg(rows)


def architecture_svg() -> str:
    """Return a deterministic repository architecture diagram."""

    boxes = [
        (35, 78, 190, 74, "Bounded JSON config", "Schema v1 + preset"),
        (275, 78, 190, 74, "Shared lab service", "UI and CLI entry"),
        (515, 28, 190, 74, "Evaluator truth", "Latent clean record"),
        (515, 128, 190, 74, "Observed analysis", "Only method capability"),
        (755, 78, 190, 74, "Fixed method panel", "Typed outcomes"),
        (995, 78, 190, 74, "Aggregate metrics", "No row-level export"),
        (1235, 28, 190, 74, "Canonical JSON", "Replay manifest"),
        (1235, 128, 190, 74, "Safety Card", "Self-contained HTML"),
    ]
    content = []
    for x, y, width, height, heading, sub in boxes:
        content.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="12" class="box"/>'
            f'<text x="{x + 14}" y="{y + 29}" class="heading">{heading}</text>'
            f'<text x="{x + 14}" y="{y + 52}" class="sub">{sub}</text>'
        )
    arrows = [
        (225, 115, 275, 115),
        (465, 115, 515, 65),
        (610, 102, 610, 128),
        (705, 165, 755, 115),
        (945, 115, 995, 115),
        (1185, 115, 1235, 65),
        (1185, 115, 1235, 165),
    ]
    lines = "".join(
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="arrow" marker-end="url(#arrow)"/>'
        for x1, y1, x2, y2 in arrows
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="a-title a-desc" viewBox="0 0 1460 230">
<title id="a-title">Inferential Safety Lab architecture</title><desc id="a-desc">Configuration enters one shared service. Evaluator truth is separated from observed analysis data. Methods return typed outcomes that become aggregate JSON and an HTML Safety Card.</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{CORAL}"/></marker></defs>
<style>.box{{fill:{SURFACE};stroke:{INK};stroke-width:1.4}}.heading{{font:700 15px {FONT_SANS};fill:{INK}}}.sub{{font:12px {FONT_SANS};fill:#536473}}.arrow{{stroke:{CORAL};stroke-width:2;fill:none}}</style>
<rect width="100%" height="100%" fill="{PAPER}"/>{lines}{"".join(content)}</svg>"""
