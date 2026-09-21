"""Offline study comparisons without pooling runs or ranking methods."""

from __future__ import annotations

from html import escape
from pathlib import PurePosixPath
from textwrap import wrap
from typing import Any
from urllib.parse import quote

from .html import table
from .public import (
    GUARDED_CONDITIONAL_WARNING,
    interval_display,
    public_failure_label,
    public_method_label,
    public_scenario_name,
    show_number,
    show_percent,
)
from .theme import BLUE, CORAL, FONT_DISPLAY, FONT_MONO, FONT_SANS, INK, MUTED, PAPER, RULE, SURFACE


def _method_name(row: dict[str, Any]) -> str:
    return public_method_label(str(row["method_id"]), str(row["display_name"]))


def _intensity(config: dict[str, Any]) -> str:
    if config["scenario_id"] == "GROSS_CONTAMINATION":
        return (
            f"contamination {show_percent(config['contamination_fraction'])}, "
            f"displacement {show_number(config['contamination_displacement'])}"
        )
    return f"missingness {show_percent(config['missingness_rate'])}"


def _cell_label(row: dict[str, Any]) -> str:
    return f"{row['run_id']} | n={row['sample_size']} | {_intensity(row)}"


def _svg_text(x: int, y: int, value: str, *, size: int = 13, weight: int = 400) -> str:
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}">{escape(value)}</text>'


def render_study_chart(summary: dict[str, Any]) -> str:
    """Return an accessible SVG with separate 0-100% coverage and availability bars."""

    groups: dict[str, list[dict[str, Any]]] = {}
    for row in summary["comparisons"]:
        groups.setdefault(str(row["method_id"]), []).append(row)
    body: list[str] = []
    row_descriptions: list[str] = []
    y = 124
    plot_x, plot_width = 420, 480
    for rows in groups.values():
        title_lines = wrap(_method_name(rows[0]), width=105) or [""]
        body.append(
            f'<rect x="20" y="{y - 23}" width="1200" height="{len(title_lines) * 22 + 10}" fill="{SURFACE}"/>'
        )
        for line in title_lines:
            body.append(_svg_text(32, y, line, size=17, weight=700))
            y += 22
        y += 12
        for tick in (0, 25, 50, 75, 100):
            body.append(_svg_text(plot_x + tick * plot_width // 100, y, f"{tick}%", size=11))
        y += 24
        for row in rows:
            label_lines = wrap(_cell_label(row), width=53) + wrap(
                f"Seed {row['master_seed']}", width=53
            )
            row_height = max(62, len(label_lines) * 17 + 12)
            status = interval_display(row)
            description = (
                f"{_cell_label(row)}; seed {row['master_seed']}; {_method_name(row)}. "
                f"{status['status']}. Interval availability: {status['interval_availability']}. "
                f"Conditional coverage: {status['conditional_coverage']}."
            )
            row_descriptions.append(description)
            body.append(f"<g><title>{escape(description)}</title>")
            for index, line in enumerate(label_lines):
                body.append(_svg_text(32, y + 10 + index * 17, line, size=12))
            if not row["interval_scientifically_applicable"]:
                body.append(
                    _svg_text(plot_x, y + 23, "N/A - scientifically inapplicable", weight=700)
                )
            else:
                values = (
                    ("interval_availability", "interval_available_runs", "attempted_runs", BLUE),
                    (
                        "conditional_coverage",
                        "conditional_coverage_numerator",
                        "conditional_coverage_denominator",
                        CORAL,
                    ),
                )
                for index, (key, numerator, denominator, color) in enumerate(values):
                    bar_y = y + index * 25
                    body.append(
                        f'<rect x="{plot_x}" y="{bar_y}" width="{plot_width}" height="13" fill="{SURFACE}"/>'
                    )
                    value = row[key]
                    if value is not None:
                        width = float(value) * plot_width
                        body.append(
                            f'<rect x="{plot_x}" y="{bar_y}" width="{width:.3f}" height="13" fill="{color}"/>'
                        )
                    label = f"{show_percent(value)} | {row[numerator]}/{row[denominator]}"
                    body.append(_svg_text(plot_x + plot_width + 16, bar_y + 11, label, size=12))
            body.append(
                f'<line x1="32" y1="{y + row_height - 8}" x2="1208" y2="{y + row_height - 8}" stroke="{RULE}"/></g>'
            )
            y += row_height
        y += 30
    if not groups:
        body.append(_svg_text(32, y, "No completed comparison rows are available."))
        y += 32
    description = (
        "Methods are grouped in their declared order, not ranked. Each row is one configuration "
        "and seed. The upper blue bar is interval availability over all attempts; the lower "
        "coral bar is coverage conditional on usable applicable intervals. Both use a fixed "
        "zero to one hundred percent scale. Counts appear beside every applicable bar. "
        "Scientifically inapplicable intervals are N/A, not zero. "
    ) + " ".join(row_descriptions)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1240 {y + 12}" '
        f'role="img" aria-labelledby="study-chart-title study-chart-description">'
        f'<title id="study-chart-title">Interval availability and conditional coverage</title>'
        f'<desc id="study-chart-description">{escape(description)}</desc>'
        f'<rect width="1240" height="{y + 12}" fill="{PAPER}"/>'
        f'<g fill="{INK}" font-family="Segoe UI, sans-serif">'
        + _svg_text(
            32,
            38,
            "How often were intervals available, and when did they cover?",
            size=23,
            weight=700,
        )
        + _svg_text(32, 63, "One row per configuration and seed. No pooling, scoring, or ranking.")
        + f'<rect x="32" y="81" width="20" height="12" fill="{BLUE}"/>'
        + _svg_text(60, 92, "Available / all attempts (upper bar)", size=12)
        + f'<rect x="420" y="81" width="20" height="12" fill="{CORAL}"/>'
        + _svg_text(448, 92, "Covered / usable applicable intervals (lower bar)", size=12)
        + "".join(body)
        + "</g></svg>"
    )


def _artifact_link(directory: str, filename: str, label: str) -> str:
    path = PurePosixPath(directory)
    if path.is_absolute() or ".." in path.parts or ":" in directory or "\\" in directory:
        return escape(label) + " (link unavailable)"
    href = quote(str(path / filename), safe="/")
    return f'<a href="{escape(href, quote=True)}">{escape(label)}</a>'


def _wilson(row: dict[str, Any], key: str) -> str:
    bounds = row[key]
    if bounds["lower"] is None or bounds["upper"] is None:
        return "Not available"
    return f"{show_percent(bounds['lower'])} to {show_percent(bounds['upper'])}"


def render_study_report(summary: dict[str, Any]) -> str:
    """Render an offline report with cell-level metrics, contracts, and replay links."""

    comparisons = summary["comparisons"]
    runs = summary["runs"]
    base = summary["configuration"]["base_config"]
    scenario = public_scenario_name(str(base["scenario_id"]))
    metric_rows = []
    uncertainty_rows = []
    for row in comparisons:
        status = interval_display(row)
        failures = (
            "; ".join(
                f"{public_failure_label(code)} ({code}): {count}"
                for code, count in sorted(row["failure_code_counts"].items())
            )
            or "None observed"
        )
        metric_rows.append(
            (
                row["run_id"],
                _method_name(row),
                f"{row['point_estimate_available_runs']}/{row['attempted_runs']}",
                show_number(row["bias"]),
                show_number(row["bias_mcse"]),
                show_number(row["rmse"]),
                status["status"],
                status["conditional_coverage"],
                status["interval_availability"],
                status["valid_and_cover"],
                failures,
            )
        )
        applicable = row["interval_scientifically_applicable"]
        uncertainty_rows.append(
            (
                row["run_id"],
                _method_name(row),
                _wilson(row, "conditional_coverage_wilson") if applicable else "N/A",
                _wilson(row, "interval_availability_wilson") if applicable else "N/A",
                row["interval_unavailability_reason"] or "Applicable; availability shown above",
            )
        )
    run_rows = [
        (
            run["run_id"],
            run["configuration"]["sample_size"],
            _intensity(run["configuration"]),
            run["configuration"]["master_seed"],
            run["configuration"]["repetitions"],
            show_number(run["configuration"]["tau"]),
        )
        for run in runs
    ]
    replay_items = []
    for run in runs:
        directory = str(run["artifact_directory"])
        links = " · ".join(
            _artifact_link(directory, filename, label)
            for filename, label in (
                ("run-config.json", "Configuration"),
                ("aggregate.canonical.json", "Canonical result"),
                ("inferential-safety-card.html", "Safety Card"),
            )
        )
        replay_items.append(
            f"<li><h3>{escape(str(run['run_id']))}</h3><p>{links}</p>"
            f"<p>Replay identity <code>{escape(str(run['replay_hash']))}</code><br>"
            f"Aggregate SHA-256 <code>{escape(str(run['aggregate_sha256']))}</code></p></li>"
        )
    css = f"""
:root{{--paper:{PAPER};--ink:{INK};--muted:{MUTED};--rule:{RULE};--surface:{SURFACE};--accent:{CORAL}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.6 {FONT_SANS}}}
main{{max-width:1320px;margin:auto;padding:40px 32px;min-width:0}}h1,h2,h3{{font-family:{FONT_DISPLAY};line-height:1.2}}
h1{{font-size:42px;margin:8px 0 16px}}h2{{font-size:28px;margin:38px 0 14px}}h3{{font-size:19px;margin:12px 0}}
.eyebrow{{font:700 12px {FONT_MONO};color:var(--accent);letter-spacing:.06em;text-transform:uppercase}}
.lead{{font-size:20px;max-width:850px;color:var(--muted)}}.note{{padding:16px 20px;background:var(--surface);border-left:4px solid var(--accent)}}
.facts{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;border-block:1px solid var(--rule);padding:18px 0;margin:24px 0}}
.facts strong{{display:block;font-size:22px}}.facts span{{color:var(--muted)}}
.chart-wrap,.table-wrap{{max-width:100%;overflow-x:auto;margin:16px 0}}.chart-wrap svg{{display:block;width:100%;min-width:1000px;height:auto}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid var(--rule)}}
th{{background:var(--surface)}}td{{font-variant-numeric:tabular-nums}}th:first-child,td:first-child{{white-space:nowrap}}
.metrics table{{min-width:1500px}}code{{font:12px {FONT_MONO};overflow-wrap:anywhere}}a{{color:var(--ink);text-underline-offset:3px}}
a:focus-visible,[tabindex]:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}}.replay{{list-style:none;padding:0}}
.replay li{{padding:10px 0;border-bottom:1px solid var(--rule)}}.id{{overflow-wrap:anywhere}}footer{{color:var(--muted);border-top:1px solid var(--rule);margin-top:32px;padding-top:16px}}
@media(max-width:650px){{main{{padding:24px 16px}}h1{{font-size:34px}}.facts{{grid-template-columns:1fr;gap:12px}}}}
@media print{{main{{max-width:none;padding:0}}body{{font-size:11px}}.chart-wrap svg{{min-width:0}}.table-wrap{{overflow:visible}}.metrics table{{min-width:0;font-size:8px}}th,td{{padding:5px}}thead{{display:table-header-group}}h2,h3{{break-after:avoid}}}}
"""
    metrics_table = table(
        (
            "Run",
            "Method",
            "Point estimates / attempts",
            "Bias",
            "Bias Monte Carlo SE",
            "RMSE",
            "Interval status",
            "Conditional coverage",
            "Interval availability",
            "Valid-and-cover",
            "Withheld / failed attempts: reason and count",
        ),
        metric_rows,
    )
    uncertainty_table = table(
        (
            "Run",
            "Method",
            "Coverage: 95% Wilson range",
            "Availability: 95% Wilson range",
            "Interval contract",
        ),
        uncertainty_rows,
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Experiment comparison - {escape(scenario)}</title><style>{css}</style></head><body><main>
<header><p class="eyebrow">Inferential Safety Lab · Reproducible study</p><h1>What changes across experiments?</h1>
<p class="lead">{escape(scenario)}. Compare estimation error, interval reporting, and coverage across declared configurations and seeds.</p>
<p class="note">Synthetic experiments with a known answer. Every comparison remains conditional on its configuration; no overall score, leaderboard, or universally best method is computed.</p></header>
<div class="facts"><div><strong>{len(runs)} configurations and seeds</strong><span>Each run remains separate</span></div>
<div><strong>{len(comparisons)} method results</strong><span>No pooling across cells</span></div>
<div><strong>{show_number(base["tau"])} known answer</strong><span>Original-population average effect</span></div></div>
<section aria-labelledby="configurations"><h2 id="configurations">Declared experiments</h2>
{table(("Run", "Sample size", "Data problem", "Master seed", "Attempts per method", "Known answer"), run_rows)}
<p>Repeated seeds reuse deterministic streams where the engine supports it. These cells are not independent evidence blocks; no paired significance test or pooled estimate is reported.</p></section>
<section aria-labelledby="intervals"><h2 id="intervals">Availability and coverage together</h2>
<p>The upper bar uses all attempts. The lower bar uses only usable, scientifically applicable intervals. A high conditional coverage rate can coexist with many withheld results.</p>
<div class="chart-wrap" tabindex="0" role="region" aria-label="Scrollable interval comparison chart">{render_study_chart(summary)}</div>
<p>N/A means the method does not provide scientifically applicable uncertainty. An applicable method with no usable intervals has 0% availability and undefined conditional coverage.</p></section>
<section aria-labelledby="metrics"><h2 id="metrics">Exact results by run and method</h2>
<p class="note">{escape(GUARDED_CONDITIONAL_WARNING)}</p>
<p>Bias and RMSE use available point estimates; the point count is shown. Conditional coverage uses covered / usable applicable intervals. Interval availability uses usable applicable intervals / all attempts. Valid-and-cover uses covered / all attempts. Failures stay in all-attempt denominators.</p>
<div class="metrics">{metrics_table}</div>
<h3>Monte Carlo uncertainty and interval contracts</h3>{uncertainty_table}
<p>Wilson ranges describe Monte Carlo uncertainty in each cell's coverage and availability rates. They are not effect intervals or tests of differences between methods. The effect interval confidence level is {show_percent(base["confidence_level"])}.</p></section>
<section aria-labelledby="replay"><h2 id="replay">Inspect and replay a run</h2>
<p class="id">Study identity: <code>{escape(str(summary["study_id"]))}</code><br>Result schema: <code>{escape(str(summary["schema_version"]))}</code></p>
<p>Relative links point to this study's exported run files. For each configuration, replay with <code>inferential-safety run --config &lt;run-config.json&gt; --output &lt;new-directory&gt;</code>. Canonical results record the dependency environment. Exact bytes require the same environment; runtime measurements remain separate.</p>
<ul class="replay">{"".join(replay_items)}</ul></section>
<footer>This comparison does not replace the frozen demonstration or its calibration evidence. The clean-data reference is evaluator-only and is not ranked. Only aggregate synthetic results are included; this report needs no scripts, external assets, or network.</footer>
</main></body></html>"""
