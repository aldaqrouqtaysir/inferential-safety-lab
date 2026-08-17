"""Self-contained, print-ready Inferential Safety Card."""

from __future__ import annotations

from html import escape
from typing import Any

from .charts import completion_svg, coverage_availability_svg, estimation_error_svg
from .html import table
from .public import (
    GUARDED_CONDITIONAL_WARNING,
    SEVERE_STRESS_EXPLANATION,
    SEVERE_STRESS_LABEL,
    WHY_AVAILABILITY_DIFFERS,
    interval_display,
    public_estimator_label,
    public_failure_label,
    public_method_label,
    public_preprocessing_label,
    public_scenario_name,
    show_number,
    show_percent,
)
from .theme import (
    CORAL,
    FAILURE,
    FONT_DISPLAY,
    FONT_MONO,
    FONT_SANS,
    GRID,
    INK,
    METHOD_IDENTITIES,
    MUTED,
    PAPER,
    SUCCESS,
    SURFACE,
    TECHNICAL_SURFACE,
    WHITE,
    WITHHELD,
    method_identity,
)


def render_safety_card(aggregate: dict[str, Any]) -> str:
    metrics = aggregate["method_metrics"]
    config = aggregate["configuration"]
    truth = aggregate["known_truth"]
    contracts = aggregate["method_contracts"]
    environment = aggregate["environment"]
    scenario_name = public_scenario_name(aggregate["scenario_id"])

    def method_name(row: dict[str, Any]) -> str:
        return public_method_label(str(row["method_id"]), str(row["display_name"]))

    def labeled_method(row: dict[str, Any], index: int) -> str:
        code, _ = method_identity(index)
        return f"{code}  {method_name(row)}"

    metric_rows = [
        (
            labeled_method(row, index),
            f"{row['point_estimate_available_runs']}/{row['attempted_runs']}",
            show_number(row["absolute_bias"]),
            show_number(row["rmse"]),
            interval_display(row)["status"],
            interval_display(row)["conditional_coverage"],
            interval_display(row)["interval_availability"],
            show_percent(row["mean_row_retention"]),
        )
        for index, row in enumerate(metrics)
    ]
    intervention_rows = [
        (
            labeled_method(row, index),
            show_percent(row["mean_row_retention"]),
            show_percent(row["mean_filled_missing_fraction"]),
            show_percent(row["mean_changed_observed_fraction"]),
            show_percent(row["mean_explicit_deletion_fraction"]),
        )
        for index, row in enumerate(metrics)
    ]
    contract_rows = [
        (
            (
                f"{method_identity(index)[0]}  "
                f"{public_method_label(str(contract['method_id']), str(contract['display_name']))}"
            ),
            public_preprocessing_label(contract["preprocessing_id"]),
            public_estimator_label(contract["estimator_id"]),
            "Applicable" if contract["interval_scientifically_applicable"] else "Not applicable",
            contract["limitations"],
        )
        for index, contract in enumerate(contracts)
    ]
    failures = [
        (
            labeled_method(row, index),
            ", ".join(
                f"{public_failure_label(key)}: {value}"
                for key, value in row["failure_code_counts"].items()
            )
            or "None observed",
        )
        for index, row in enumerate(metrics)
    ]
    interval_status_rows = [
        (
            (
                f"{method_identity(index)[0]}  "
                f"{public_method_label(str(contract['method_id']), str(contract['display_name']))}"
            ),
            "Not applicable",
            contract["interval_unavailability_reason"],
        )
        for index, contract in enumerate(contracts)
        if not contract["interval_scientifically_applicable"]
    ]
    chart_metrics = [{**row, "display_name": method_name(row)} for row in metrics]
    coverage_chart = coverage_availability_svg(chart_metrics)
    error_chart = estimation_error_svg(chart_metrics)
    method_key = (
        '<div class="method-key" aria-label="Method identity key">'
        + "".join(
            f'<span class="method-item" style="--method-color:{method_identity(index)[1]}">'
            f'<i aria-hidden="true"></i><code>{method_identity(index)[0]}</code>'
            f"{escape(method_name(row))}</span>"
            for index, row in enumerate(metrics)
        )
        + "</div>"
    )
    truth_value = float(truth["value"])
    estimates = [truth_value + float(row["bias"]) for row in metrics if row.get("bias") is not None]
    lower = min([truth_value, *estimates])
    upper = max([truth_value, *estimates])
    spread = max(upper - lower, 0.05)
    lower -= spread * 0.15
    upper += spread * 0.15

    def position(value: float) -> float:
        return max(1.5, min(98.5, 100 * (value - lower) / (upper - lower)))

    known_position = position(truth_value)
    answer_rows = []
    answer_description = [f"Known answer {truth_value:.3f}."]
    for index, row in enumerate(metrics):
        estimate = None if row.get("bias") is None else truth_value + float(row["bias"])
        reported = int(row["point_estimate_available_runs"])
        attempted = int(row["attempted_runs"])
        code, color = method_identity(index)
        estimate_mark = (
            f'<span class="answer-estimate" aria-hidden="true" '
            f'style="left:{position(estimate):.2f}%;--method-color:{color}"></span>'
            if estimate is not None
            else ""
        )
        shown = f"Average {estimate:.3f}" if estimate is not None else "Average not available"
        answer_description.append(
            f"Method {code}, {method_name(row)}, {shown.lower()}, reported on "
            f"{reported} of {attempted} runs."
        )
        answer_rows.append(
            f'<div class="answer-row"><span class="method-item" '
            f'style="--method-color:{color}"><i aria-hidden="true"></i><code>{code}</code>'
            f'{escape(method_name(row))}</span><span class="answer-track" aria-hidden="true">'
            f'<span class="answer-known" style="left:{known_position:.2f}%"></span>'
            f'{estimate_mark}</span><span class="answer-value">{escape(shown)}<br>'
            f"{reported}/{attempted} runs</span></div>"
        )
    answer_rail = (
        f'<section class="answer-rail" role="img" '
        f'aria-label="{escape(" ".join(answer_description))}">'
        f'<div class="answer-head"><strong>Average estimates against the known answer</strong>'
        f"<span>Known answer {truth_value:.3f}</span></div>{''.join(answer_rows)}</section>"
    )
    css = f"""
:root{{--paper:{PAPER};--surface:{SURFACE};--technical:{TECHNICAL_SURFACE};--ink:{INK};--muted:{MUTED};--primary:{CORAL};--known:{CORAL};--line:{GRID};--success:{SUCCESS};--withheld:{WITHHELD};--failure:{FAILURE};--white:{WHITE};--method-a:{METHOD_IDENTITIES[0][1]};--method-b:{METHOD_IDENTITIES[1][1]};--method-c:{METHOD_IDENTITIES[2][1]};--method-d:{METHOD_IDENTITIES[3][1]};--display:{FONT_DISPLAY};--sans:{FONT_SANS};--mono:{FONT_MONO}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 var(--sans)}}main{{max-width:1180px;margin:auto;padding:42px}}
h1,h2,h3{{font-family:var(--display);line-height:1.12;letter-spacing:-.02em}}h1{{font-size:40px;margin:0 0 8px}}h2{{font-size:24px;margin-top:34px;border-bottom:1px solid var(--line);padding-bottom:7px}}
.record-meta{{font:700 12px/1.5 var(--mono);color:var(--primary);margin:0 0 8px}}.subtitle{{font-size:19px;color:var(--muted);max-width:760px}}.boundary{{padding:14px 17px;border-left:4px solid var(--primary);background:var(--surface)}}
.facts{{display:grid;grid-template-columns:repeat(4,1fr);margin:24px 0 14px;border-top:2px solid var(--ink);border-bottom:1px solid var(--line)}}.fact{{padding:14px 13px 15px 0}}.fact+.fact{{border-left:1px solid var(--line);padding-left:13px}}.fact b{{display:block;font:12px var(--mono);color:var(--muted);margin-bottom:4px}}
.method-key{{display:flex;flex-wrap:wrap;gap:8px 18px;border-top:1px solid var(--line);padding:9px 0 3px;margin:10px 0}}.method-item{{display:flex;align-items:flex-start;gap:7px;flex:1 1 230px;font-size:13px;line-height:1.4}}.method-item i{{flex:0 0 18px;height:4px;margin-top:7px;background:var(--method-color)}}.method-item code{{font:700 12px/1.5 var(--mono)}}
.answer-rail{{border-top:2px solid var(--ink);border-bottom:1px solid var(--line);padding:11px 0 9px;margin:12px 0 18px}}.answer-head{{display:flex;align-items:baseline;justify-content:space-between;gap:16px;margin-bottom:5px}}.answer-head strong{{font:700 20px/1.25 var(--display)}}.answer-head span{{font:700 12px var(--mono);color:var(--known)}}.answer-row{{display:grid;grid-template-columns:minmax(245px,1.35fr) minmax(220px,1fr) minmax(120px,.55fr);gap:16px;align-items:center;padding:7px 0}}.answer-track{{position:relative;height:18px;border-top:1px solid var(--line)}}.answer-known{{position:absolute;top:-6px;width:2px;height:12px;background:var(--known);transform:translateX(-1px)}}.answer-estimate{{position:absolute;top:-5px;width:9px;height:9px;border:2px solid var(--paper);background:var(--method-color);border-radius:50%;transform:translateX(-4px)}}.answer-value{{font:700 12px/1.4 var(--mono);text-align:right}}
.table-wrap{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;font-size:13px}}th,td{{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}}th{{background:var(--technical);font-weight:700}}
.chart{{margin:16px 0}}.chart svg{{width:100%;height:auto}}.hash{{font:13px var(--mono);overflow-wrap:anywhere;background:var(--technical);padding:14px}}.conclusion{{font:18px/1.55 var(--sans);padding:18px;border:1px solid var(--ink);border-radius:8px}}.stress{{display:inline-block;background:var(--ink);color:var(--white);font:700 12px var(--mono);padding:8px 10px;border-radius:5px}}.reporting-note{{border-left:4px solid var(--primary);padding:10px 14px;background:var(--surface);margin:12px 0}}
@media(max-width:760px){{main{{padding:22px}}.facts{{grid-template-columns:1fr 1fr}}.fact:nth-child(3){{border-left:0;border-top:1px solid var(--line)}}.fact:nth-child(4){{border-top:1px solid var(--line)}}h1{{font-size:32px}}.answer-head{{align-items:flex-start;flex-direction:column;gap:4px}}.answer-row{{grid-template-columns:1fr;gap:4px;padding:10px 0}}.answer-value{{text-align:left}}.method-item{{flex-basis:100%}}}}@page{{size:auto;margin:12mm}}@media print{{body{{background:white}}main{{max-width:none;padding:0}}.no-print{{display:none}}h2{{break-after:avoid}}.chart,.table-wrap,.reporting-note,.answer-rail{{break-inside:avoid}}thead{{display:table-header-group}}}}
"""
    dependencies = ", ".join(
        f"{name} {version}" for name, version in environment["dependencies"].items()
    )
    stress_context = (
        f'<p class="stress">{escape(SEVERE_STRESS_LABEL)}</p>'
        f"<p>{escape(SEVERE_STRESS_EXPLANATION)}</p>"
        if aggregate["scenario_id"] == "MCAR_SMALL_EFFECTIVE_SAMPLE"
        and float(config["missingness_rate"]) == 0.60
        else ""
    )
    interval_status_table = (
        table(("Method", "Interval status", "Reason"), interval_status_rows)
        if interval_status_rows
        else "<p>All methods in this panel have scientifically applicable intervals.</p>"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Inferential Safety Card - {escape(scenario_name)}</title><style>{css}</style></head>
<body><main><header><p class="record-meta">Audit-ready run record<br>Software version {escape(aggregate["software_version"])}</p><h1>Inferential Safety Card</h1><p class="subtitle">A self-contained record of what the experiment ran, reported, withheld, changed, and found.</p><p class="boundary"><strong>Scientific boundary.</strong> This educational simulator uses synthetic data with a known answer. It does not prove causal validity, choose a universally best method, or support decisions about real people.</p></header>
<section class="facts"><div class="fact"><b>Scenario</b>{escape(scenario_name)}</div><div class="fact" aria-label="Known average effect"><b>Known answer</b>{show_number(truth["value"])}</div><div class="fact"><b>Sample size and repetitions</b>{config["sample_size"]} x {config["repetitions"]}</div><div class="fact"><b>Master seed</b>{config["master_seed"]}</div></section>
{answer_rail}
{stress_context}<p>{escape(aggregate["scenario_mechanism"])}</p><p><strong>Estimand:</strong> {escape(truth["estimand"])}. <strong>Formula:</strong> <code>{escape(truth["formula"])}</code>.</p>
<h2>Headline observation</h2><p class="conclusion">{escape(aggregate["headline_observation"])}</p>
<p class="reporting-note">{escape(WHY_AVAILABILITY_DIFFERS)}</p><p class="reporting-note">{escape(GUARDED_CONDITIONAL_WARNING)}</p>
<h2>Method metrics</h2>{method_key}{table(("Method", "Point estimates", "Absolute bias", "RMSE", "Interval status", "Conditional coverage", "Interval availability", "Retained data"), metric_rows)}
<h3>Interval applicability</h3>{interval_status_table}<p>For a scientifically inapplicable interval, conditional coverage, interval availability, and valid-and-cover rate are N/A, not 0%, method failure, or an unavailable applicable interval.</p>
<p><strong>Denominators:</strong> conditional coverage is covered usable applicable intervals / usable applicable intervals. Interval availability is usable applicable intervals / all attempts. Valid-and-cover is covered usable applicable intervals / all attempts. Attempted runs are shown in every applicable ratio.</p>
<div class="chart">{coverage_chart}</div><div class="chart">{error_chart}</div>
<h2>Intervention burden</h2>{table(("Method", "Row retention", "Filled missing", "Changed observed", "Explicit deletion"), intervention_rows)}
<h2>Reported and withheld results</h2>{table(("Method", "Public reason and count"), failures)}<div class="chart">{completion_svg(chart_metrics)}</div>
<h2>Method contracts</h2>{table(("Method", "Preprocessing", "Estimator", "Interval status", "Limitation"), contract_rows)}
<h2>Reproducibility</h2><p><strong>Scenario machine ID:</strong> <code>{escape(aggregate["scenario_id"])}</code>. <strong>Software:</strong> {escape(aggregate["software_version"])}; <strong>Python:</strong> {escape(environment["python"])}; <strong>platform:</strong> {escape(environment["platform"])}; <strong>dependencies:</strong> {escape(dependencies)}.</p><p><strong>Replay hash</strong></p><div class="hash">{escape(aggregate["replay_hash"])}</div><p><strong>Exact CLI replay command</strong></p><div class="hash">{escape(aggregate["replay_command"])}</div>
<h2>Scientific limitations</h2><ul><li>Results are conditional on this synthetic mechanism, configuration, and estimand.</li><li>Deterministic single-imputation uncertainty was not propagated, so those interval metrics are not applicable.</li><li>Complete-case results can describe a selected-data projection when the fitting population changes.</li><li>Huber point estimation does not generally correct covariate measurement error or establish causal validity.</li><li>The clean-data reference is evaluator-only, not selectable, and never a declared winner.</li><li>No row-level data are included in this card or its aggregate manifest.</li></ul>
<h2>Conclusion</h2><p class="conclusion">{escape(aggregate["conclusion"])}</p></main></body></html>"""
