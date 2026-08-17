"""Three-page Streamlit interface; all scientific work remains in services."""

from __future__ import annotations

import base64
from html import escape
from time import sleep
from typing import Any

import pandas as pd
import streamlit as st

from inferential_safety_lab.core.configuration import RunConfig, ScenarioId
from inferential_safety_lab.reporting.charts import (
    completion_chart_spec,
    completion_rows,
    coverage_availability_rows,
    estimation_error_svg,
    paired_percentage_chart_spec,
)
from inferential_safety_lab.reporting.public import (
    GUARDED_CONDITIONAL_WARNING,
    WHY_AVAILABILITY_DIFFERS,
    interval_display,
    public_estimator_label,
    public_failure_label,
    public_method_label,
    public_preprocessing_label,
    show_number,
    show_percent,
)
from inferential_safety_lab.reporting.safety_card import render_safety_card
from inferential_safety_lab.reporting.theme import (
    CORAL,
    FAILURE,
    FONT_DISPLAY,
    FONT_MONO,
    FONT_SANS,
    INK,
    METHOD_IDENTITIES,
    MUTED,
    PAPER,
    PRIMARY_ACTION,
    RULE,
    SUCCESS,
    SURFACE,
    TECHNICAL_SURFACE,
    WHITE,
    WITHHELD,
    method_identity,
)
from inferential_safety_lab.services.presets import get_preset
from inferential_safety_lab.services.run_lab import (
    estimated_runtime_seconds,
    preview_scenario,
    run_lab,
    with_controls,
)
from inferential_safety_lab.ui.state import (
    has_stale_result,
    initialize_ui_state,
    mark_complete,
    mark_error,
    mark_running,
    store_draft,
    update_progress,
)

BOUNDARY = (
    "This educational simulator uses synthetic data with a known answer. It does not prove "
    "causal validity, choose a universally best method, or support decisions about real people."
)

SCENARIO_LABELS = {
    ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE: "Randomly missing measurements",
    ScenarioId.OUTCOME_DEPENDENT_MAR: "Missingness linked to observed outcomes",
    ScenarioId.GROSS_CONTAMINATION: "Extreme measurement errors",
}

SCENARIO_CAPTIONS = {
    ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE: (
        "MCAR: measurements are removed completely at random, reducing the effective sample."
    ),
    ScenarioId.OUTCOME_DEPENDENT_MAR: (
        "Outcome-dependent MAR: removal is linked to outcomes that remain observed."
    ),
    ScenarioId.GROSS_CONTAMINATION: (
        "Gross contamination: a share of measurements is shifted by an extreme amount."
    ),
}

_PAGES: dict[str, Any] = {}


def _css() -> str:
    return f"""
<style>
:root{{color-scheme:light;--lab-paper:{PAPER};--lab-surface:{SURFACE};--lab-technical:{TECHNICAL_SURFACE};--lab-ink:{INK};--lab-muted:{MUTED};--lab-rule:{RULE};--lab-primary:{PRIMARY_ACTION};--lab-coral:{CORAL};--lab-known:{CORAL};--lab-success:{SUCCESS};--lab-withheld:{WITHHELD};--lab-failure:{FAILURE};--lab-white:{WHITE};--lab-method-a:{METHOD_IDENTITIES[0][1]};--lab-method-b:{METHOD_IDENTITIES[1][1]};--lab-method-c:{METHOD_IDENTITIES[2][1]};--lab-method-d:{METHOD_IDENTITIES[3][1]};--lab-display:{FONT_DISPLAY};--lab-sans:{FONT_SANS};--lab-mono:{FONT_MONO};--lab-control-radius:8px;--lab-panel-radius:20px}}
html,body,[data-testid="stAppViewContainer"]{{background:var(--lab-paper)!important;color:var(--lab-ink)!important;font-family:var(--lab-sans)!important;overflow-x:clip}}
.lab-page-shell{{--lab-page-text-width:760px}}
[data-testid="stMainBlockContainer"]:has(.lab-page-shell){{box-sizing:border-box;width:min(100%,1600px)!important;max-width:1600px!important;margin-left:0!important;margin-right:auto!important;padding:clamp(3.25rem,4vw,3.75rem) clamp(1.5rem,1.667vw,2rem) 5rem!important}}
[data-testid="stAppViewContainer"] h1,[data-testid="stAppViewContainer"] h2,[data-testid="stAppViewContainer"] h3{{font-family:var(--lab-display)!important;color:var(--lab-ink)!important;letter-spacing:-.024em}}
[data-testid="stAppViewContainer"] h1{{font-size:clamp(2.15rem,3.5vw,3rem)!important;line-height:1.02!important;font-weight:700!important}}
[data-testid="stAppViewContainer"] h2{{font-size:clamp(1.5rem,2.25vw,2rem)!important;line-height:1.12!important;font-weight:700!important;margin-top:2rem}}
[data-testid="stAppViewContainer"] h3{{font-size:1.18rem!important;font-weight:700!important}}
[data-testid="stAppViewContainer"] p,[data-testid="stAppViewContainer"] li,[data-testid="stAppViewContainer"] label{{color:var(--lab-ink);line-height:1.55}}
[data-testid="stButton"] button,[data-testid="stDownloadButton"] button{{min-height:44px!important;border-radius:var(--lab-control-radius)!important;font-family:var(--lab-sans)!important;font-weight:720!important;transition:background-color .14s ease,border-color .14s ease,transform .08s ease}}
[data-testid="stButton"] button:active,[data-testid="stDownloadButton"] button:active{{transform:translateY(1px)}}
[data-testid="stButton"] button[kind="primary"]{{background:var(--lab-primary)!important;border-color:var(--lab-primary)!important;color:var(--lab-white)!important}}
[data-testid="stButton"] button[kind="primary"]:hover{{background:var(--lab-failure)!important;border-color:var(--lab-failure)!important}}
[data-testid="stRadio"] label,[data-testid="stSelectbox"] [role="combobox"],[data-testid="stNumberInput"] input{{min-height:44px}}
[data-testid="stRadio"] [role="radiogroup"]>label{{border:1px solid transparent;border-radius:var(--lab-control-radius);padding:.42rem .5rem;transition:background-color .14s ease,border-color .14s ease}}
[data-testid="stRadio"] [role="radiogroup"]>label:has(input:checked){{background:var(--lab-surface);border-color:var(--lab-rule);box-shadow:inset 4px 0 0 var(--lab-primary)}}
[data-testid="stTopNavItems"] a[aria-current="page"],a[aria-current="page"]{{box-shadow:inset 0 -2px 0 var(--lab-primary)}}
[data-testid="stAppViewContainer"] button:focus-visible,[data-testid="stAppViewContainer"] input:focus-visible,[data-testid="stAppViewContainer"] [role="button"]:focus-visible,[data-testid="stAppViewContainer"] [role="radio"]:focus-visible,.lab-technical-scroll:focus-visible{{outline:3px solid var(--lab-primary)!important;outline-offset:3px!important}}
[data-testid="stHeader"]::after{{content:"Inferential Safety Lab";position:absolute;top:18px;right:1.5rem;font:650 .86rem/1.25 var(--lab-sans);letter-spacing:.035em;color:var(--lab-ink);opacity:.72;pointer-events:none}}
.lab-product-id{{position:absolute!important;width:1px!important;height:1px!important;padding:0!important;margin:-1px!important;overflow:hidden!important;clip:rect(0,0,0,0)!important;white-space:nowrap!important;border:0!important}}
.lab-intro{{max-width:660px;padding:.65rem 0 .35rem}}
.lab-intro h1{{font-size:clamp(2.3rem,3.8vw,2.85rem)!important;max-width:640px;margin:.1rem 0 .8rem!important}}
.lab-value{{max-width:610px;font-size:clamp(1.02rem,1.55vw,1.16rem);color:var(--lab-muted)!important;margin:0 0 1rem}}
.lab-explainer{{border-top:2px solid var(--lab-ink);border-bottom:1px solid var(--lab-rule);margin:.7rem 0 .25rem;padding:.55rem 0}}
.lab-explainer svg{{display:block;width:100%;height:auto;max-height:360px}}
.lab-understand-body{{--lab-step-gap:clamp(2rem,4vw,4rem);box-sizing:border-box;width:100%;max-width:1600px}}
.lab-sequence{{box-sizing:border-box;display:grid;grid-template-columns:repeat(2,minmax(0,40rem));justify-content:space-between;column-gap:var(--lab-step-gap);row-gap:1rem;width:100%;margin:2rem 0 1rem}}
.lab-moment{{box-sizing:border-box;display:block;min-width:0;min-height:8rem;width:100%;padding:1.15rem 1.4rem 1.25rem;border:1px solid var(--lab-rule);border-radius:var(--lab-panel-radius);background:var(--lab-white);box-shadow:0 10px 28px rgba(23,50,77,.045)}}
.lab-moment-number{{display:block;width:auto;height:auto;border:0;border-radius:0;background:transparent;font:700 .74rem/1.25 var(--lab-mono);letter-spacing:.12em;color:var(--lab-primary);margin:0 0 .7rem}}
.lab-moment strong{{display:block;margin:0 0 .25rem}}
.lab-moment p{{font-size:.94rem;line-height:1.45!important;margin:0;color:var(--lab-muted)!important}}
.lab-boundary{{box-sizing:border-box;width:min(40rem,calc((100% - var(--lab-step-gap))/2));border:1px solid var(--lab-rule);border-left:4px solid var(--lab-primary);border-radius:0 var(--lab-control-radius) var(--lab-control-radius) 0;background:var(--lab-white);padding:.75rem .9rem;margin:1.35rem 0 1.1rem}}
.lab-boundary p{{margin:0;font-size:.88rem}}
.lab-page-head{{padding:.5rem 0 .35rem;border-bottom:1px solid var(--lab-rule);margin-bottom:1rem}}
.lab-page-head h1{{font-size:clamp(2.05rem,3vw,2.55rem)!important;margin:.1rem 0 .35rem!important}}
.lab-page-head p{{max-width:760px;color:var(--lab-muted)!important;margin:0 0 .6rem}}
.lab-glance{{border-top:2px solid var(--lab-ink);border-bottom:1px solid var(--lab-rule);padding:.85rem 0;margin:.85rem 0 1rem}}
.lab-glance h2{{font-size:1.45rem!important;margin:0 0 .65rem!important}}
.lab-glance-row{{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:1rem;padding:.55rem 0;border-top:1px solid var(--lab-rule)}}
.lab-glance-row span{{font-size:.8rem;color:var(--lab-muted)}}
.lab-glance-row strong{{font-size:.9rem;text-align:right;max-width:13rem}}
.lab-scenario-preview{{border-top:1px solid var(--lab-rule);margin-top:.55rem;padding-top:.75rem}}
.lab-scenario-preview p{{font-size:.8rem;color:var(--lab-muted)!important;margin:.15rem 0 .5rem}}
.lab-scenario-preview svg{{display:block;width:100%;height:auto}}
.lab-run-summary{{display:grid;grid-template-columns:1.5fr repeat(3,1fr);border-top:2px solid var(--lab-ink);border-bottom:1px solid var(--lab-rule);margin:.65rem 0 1rem}}
.lab-summary-item{{padding:.75rem .9rem .78rem 0;min-width:0}}
.lab-summary-item+.lab-summary-item{{border-left:1px solid var(--lab-rule);padding-left:.9rem}}
.lab-summary-item span{{display:block;font:700 .69rem/1.3 var(--lab-mono);color:var(--lab-muted);margin-bottom:.24rem}}
.lab-summary-item strong{{display:block;font-size:.94rem;overflow-wrap:anywhere}}
.lab-answer-rail{{border-top:2px solid var(--lab-ink);border-bottom:1px solid var(--lab-rule);padding:.7rem 0 .6rem;margin:.2rem 0 .8rem}}
.lab-answer-rail-head{{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;margin-bottom:.4rem}}
.lab-answer-rail-head strong{{font-family:var(--lab-display);font-size:1.25rem}}
.lab-answer-rail-head span{{font:700 .78rem var(--lab-mono);color:var(--lab-known)}}
.lab-answer-row{{display:grid;grid-template-columns:minmax(230px,1.35fr) minmax(220px,1fr) minmax(120px,.55fr);gap:1rem;align-items:center;padding:.45rem 0}}
.lab-answer-track{{position:relative;height:18px;border-top:1px solid var(--lab-rule)}}
.lab-answer-known{{position:absolute;top:-6px;width:2px;height:12px;background:var(--lab-known);transform:translateX(-1px)}}
.lab-answer-estimate{{position:absolute;top:-5px;width:9px;height:9px;border:2px solid var(--lab-paper);background:var(--method-color);border-radius:50%;transform:translateX(-4px)}}
.lab-answer-value{{font:700 .76rem/1.35 var(--lab-mono);text-align:right}}
.lab-method-marker{{display:flex;align-items:flex-start;gap:.48rem;min-width:0}}
.lab-method-marker-line{{flex:0 0 18px;height:4px;margin-top:.5rem;background:var(--method-color)}}
.lab-method-marker-code{{font:700 .75rem/1.5 var(--lab-mono)}}
.lab-method-marker-text{{font-size:.9rem;line-height:1.35}}
.lab-narrative{{max-width:820px;font-size:1rem}}
.lab-evidence{{display:grid;grid-template-columns:1.5fr 1fr;border-top:2px solid var(--lab-ink);border-bottom:1px solid var(--lab-rule);margin:.8rem 0 1rem}}
.lab-evidence-primary{{padding:1rem 1.3rem 1rem 0}}
.lab-evidence-primary span,.lab-evidence-fact span{{display:block;font-size:.78rem;color:var(--lab-muted);margin-bottom:.35rem}}
.lab-evidence-primary strong{{display:block;font-family:var(--lab-display);font-size:1.28rem;line-height:1.28}}
.lab-evidence-primary p{{margin:.45rem 0 0;font-size:.9rem;color:var(--lab-muted)!important}}
.lab-evidence-support{{border-left:1px solid var(--lab-rule)}}
.lab-evidence-fact{{padding:.75rem 0 .75rem 1rem}}
.lab-evidence-fact+.lab-evidence-fact{{border-top:1px solid var(--lab-rule)}}
.lab-evidence-fact strong{{font-size:.94rem;line-height:1.35}}
.lab-evidence-fact em{{display:block;font:700 .76rem/1.4 var(--lab-mono);font-style:normal;margin-top:.3rem}}
.lab-condition-note{{border-left:4px solid var(--lab-primary);background:var(--lab-surface);padding:.65rem .85rem;margin:.65rem 0 1rem;font-size:.88rem}}
.lab-chart-description{{max-width:860px;color:var(--lab-muted)!important;font-size:.91rem;margin-top:-.35rem}}
.lab-method-key{{display:flex;flex-wrap:wrap;gap:.45rem 1rem;border-top:1px solid var(--lab-rule);padding:.55rem 0 .2rem;margin:.4rem 0}}
.lab-method-key .lab-method-marker{{flex:1 1 230px}}
.lab-method-list,.lab-data-list{{border-top:1px solid var(--lab-ink);margin:.7rem 0 1.6rem}}
.lab-method-row{{display:grid;grid-template-columns:1.45fr 1fr 1fr 1fr;gap:1rem;padding:.9rem 0;border-bottom:1px solid var(--lab-rule);align-items:start}}
.lab-method-row strong,.lab-data-row strong{{font-size:.96rem}}
.lab-method-cell span,.lab-data-cell span{{display:block;font-size:.74rem;color:var(--lab-muted);margin-bottom:.2rem}}
.lab-method-cell p,.lab-data-cell p{{font-size:.88rem;line-height:1.4!important;margin:0}}
.lab-data-row{{display:grid;grid-template-columns:1.45fr repeat(4,1fr);gap:1rem;padding:.85rem 0;border-bottom:1px solid var(--lab-rule);align-items:start}}
.lab-technical-scroll{{width:100%;overflow-x:auto;border:1px solid var(--lab-rule);margin:.65rem 0 1rem;background:var(--lab-white)}}
.lab-technical-scroll table{{border-collapse:collapse;min-width:1180px;width:100%;font-size:.78rem;line-height:1.4}}
.lab-technical-scroll th,.lab-technical-scroll td{{text-align:left;vertical-align:top;padding:.7rem;border-bottom:1px solid var(--lab-rule)}}
.lab-technical-scroll th{{background:var(--lab-technical);font-weight:800}}
.lab-technical-scroll code{{font-family:var(--lab-mono);font-size:.76rem}}
.lab-safety{{border-top:2px solid var(--lab-ink);padding-top:.8rem;margin-top:2rem}}
.lab-safety p{{max-width:780px}}
.lab-muted{{color:var(--lab-muted)!important}}
@media(max-width:760px){{[data-testid="stMainBlockContainer"]:has(.lab-page-shell){{padding:.8rem 1rem 4rem!important}}[data-testid="stHeader"]::after{{right:1rem;font-size:.82rem}}.lab-intro{{padding-top:.25rem}}.lab-intro h1{{font-size:clamp(2rem,10vw,2.55rem)!important}}.lab-page-head{{padding-top:.1rem}}.lab-sequence{{grid-template-columns:1fr;column-gap:0}}.lab-boundary{{width:100%}}.lab-glance{{margin-top:.8rem}}.lab-run-summary{{grid-template-columns:1fr 1fr}}.lab-summary-item{{padding:.7rem .55rem .72rem 0}}.lab-summary-item+.lab-summary-item{{padding-left:.55rem}}.lab-summary-item:nth-child(3){{border-left:0;border-top:1px solid var(--lab-rule);padding-left:0}}.lab-summary-item:nth-child(4){{border-top:1px solid var(--lab-rule)}}.lab-answer-rail-head{{align-items:flex-start;flex-direction:column;gap:.2rem}}.lab-answer-row{{grid-template-columns:1fr;gap:.25rem;padding:.65rem 0}}.lab-answer-track{{margin-top:.25rem}}.lab-answer-value{{text-align:left}}.lab-evidence{{grid-template-columns:1fr}}.lab-evidence-primary{{padding:1rem 0}}.lab-evidence-support{{border-left:0;border-top:1px solid var(--lab-rule)}}.lab-evidence-fact{{padding:.75rem 0}}.lab-method-row,.lab-data-row{{grid-template-columns:1fr;gap:.6rem}}.lab-method-key .lab-method-marker{{flex-basis:100%}}}}
@media(prefers-reduced-motion:reduce){{*{{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important}}}}
</style>
"""


def _switch_page(name: str) -> None:
    st.switch_page(_PAGES[name])


def _public_method_name(row: dict[str, Any]) -> str:
    return public_method_label(str(row["method_id"]), str(row["display_name"]))


def _method_marker(row: dict[str, Any], index: int) -> str:
    code, color = method_identity(index)
    return f"""
<span class="lab-method-marker" style="--method-color:{color}">
  <span class="lab-method-marker-line" aria-hidden="true"></span>
  <span class="lab-method-marker-code">{code}</span>
  <span class="lab-method-marker-text">{escape(_public_method_name(row))}</span>
</span>"""


def _method_key(metrics: list[dict[str, Any]]) -> str:
    return (
        '<div class="lab-method-key" aria-label="Method identity key">'
        + "".join(_method_marker(row, index) for index, row in enumerate(metrics))
        + "</div>"
    )


def _chart_method_name(row: dict[str, Any], index: int) -> str:
    code, _ = method_identity(index)
    return f"{code}  {_public_method_name(row)}"


def _plain_chart_rows(
    rows: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    labels = {
        str(row["display_name"]): _chart_method_name(row, index)
        for index, row in enumerate(metrics)
    }
    return [{**row, "method": labels.get(str(row["method"]), str(row["method"]))} for row in rows]


def _understand_visual() -> str:
    return f"""
<figure class="lab-explainer">
<svg viewBox="0 0 620 300" role="img" aria-labelledby="lab-flow-title lab-flow-desc">
  <title id="lab-flow-title">How the controlled experiment compares analysis approaches</title>
  <desc id="lab-flow-desc">A known answer is fixed, measurements are removed or distorted, the same damaged data are sent to four approaches, and the results are compared for accuracy, uncertainty, failures, and data changes.</desc>
  <style>
    .flow-label{{font:700 14px {FONT_SANS};fill:{INK}}}
    .flow-note{{font:12px {FONT_SANS};fill:{MUTED}}}
    .flow-code{{font:700 12px {FONT_MONO};fill:{INK}}}
    .flow-line{{stroke:{RULE};stroke-width:1.5;fill:none}}
  </style>
  <line x1="112" y1="92" x2="188" y2="92" class="flow-line"/>
  <line x1="300" y1="92" x2="352" y2="92" class="flow-line"/>
  <line x1="352" y1="92" x2="352" y2="226" class="flow-line"/>
  <line x1="352" y1="112" x2="390" y2="112" class="flow-line"/>
  <line x1="352" y1="150" x2="390" y2="150" class="flow-line"/>
  <line x1="352" y1="188" x2="390" y2="188" class="flow-line"/>
  <line x1="352" y1="226" x2="390" y2="226" class="flow-line"/>
  <line x1="455" y1="169" x2="505" y2="169" class="flow-line"/>
  <text x="20" y="28" class="flow-label">Known answer</text>
  <line x1="70" y1="52" x2="70" y2="128" stroke="{CORAL}" stroke-width="3"/>
  <text x="82" y="82" class="flow-code">0.25</text>
  <text x="20" y="148" class="flow-note">Fixed before damage</text>
  <text x="184" y="28" class="flow-label">Damage data</text>
  <g fill="{INK}">
    <circle cx="205" cy="72" r="5"/><circle cx="235" cy="72" r="5"/><circle cx="265" cy="72" r="5"/>
    <circle cx="205" cy="102" r="5"/><circle cx="265" cy="102" r="5"/>
    <circle cx="205" cy="132" r="5"/><circle cx="235" cy="132" r="5"/>
  </g>
  <g fill="none" stroke="{FAILURE}" stroke-width="2" stroke-dasharray="3 3">
    <circle cx="235" cy="102" r="6"/><circle cx="265" cy="132" r="6"/>
  </g>
  <line x1="238" y1="99" x2="253" y2="84" stroke="{FAILURE}" stroke-width="2"/>
  <text x="184" y="158" class="flow-note">Removed or distorted</text>
  <text x="352" y="26" class="flow-label">Same data</text>
  <text x="352" y="44" class="flow-label">four approaches</text>
  <g>
    <line x1="390" y1="112" x2="408" y2="112" stroke="{METHOD_IDENTITIES[0][1]}" stroke-width="4"/><text x="416" y="116" class="flow-code">A</text>
    <line x1="390" y1="150" x2="408" y2="150" stroke="{METHOD_IDENTITIES[1][1]}" stroke-width="4"/><text x="416" y="154" class="flow-code">B</text>
    <line x1="390" y1="188" x2="408" y2="188" stroke="{METHOD_IDENTITIES[2][1]}" stroke-width="4"/><text x="416" y="192" class="flow-code">C</text>
    <line x1="390" y1="226" x2="408" y2="226" stroke="{METHOD_IDENTITIES[3][1]}" stroke-width="4"/><text x="416" y="230" class="flow-code">D</text>
  </g>
  <text x="505" y="26" class="flow-label">Compare</text>
  <text x="505" y="44" class="flow-label">evidence</text>
  <text x="505" y="82" class="flow-note">Accuracy</text>
  <text x="505" y="112" class="flow-note">Uncertainty</text>
  <text x="505" y="142" class="flow-note">Failures</text>
  <text x="505" y="172" class="flow-note">Data changes</text>
  <line x1="505" y1="194" x2="590" y2="194" stroke="{RULE}" stroke-width="1"/>
  <line x1="548" y1="184" x2="548" y2="204" stroke="{CORAL}" stroke-width="3"/>
  <circle cx="532" cy="194" r="5" fill="{METHOD_IDENTITIES[0][1]}" stroke="{PAPER}" stroke-width="2"/>
</svg>
</figure>"""


def _scenario_preview(scenario: ScenarioId) -> str:
    if scenario is ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE:
        marks = "".join(
            (
                f'<circle cx="{26 + (index % 8) * 24}" cy="{28 + (index // 8) * 26}" r="5" '
                f'fill="none" stroke="{WITHHELD}" stroke-width="2" stroke-dasharray="3 2"/>'
                if index in {2, 5, 8, 11, 14}
                else f'<circle cx="{26 + (index % 8) * 24}" cy="{28 + (index // 8) * 26}" r="5" fill="{INK}"/>'
            )
            for index in range(16)
        )
        title = "Randomly missing measurements"
        description = "A fixed dot field with missing positions spread across the sample."
    elif scenario is ScenarioId.OUTCOME_DEPENDENT_MAR:
        points = (
            (28, 72),
            (50, 64),
            (72, 58),
            (94, 52),
            (116, 45),
            (138, 38),
            (160, 30),
            (182, 22),
        )
        marks = "".join(
            (
                f'<circle cx="{x}" cy="{y}" r="5" fill="none" stroke="{WITHHELD}" stroke-width="2" stroke-dasharray="3 2"/>'
                if index in {4, 6, 7}
                else f'<circle cx="{x}" cy="{y}" r="5" fill="{INK}"/>'
            )
            for index, (x, y) in enumerate(points)
        )
        title = "Outcome-linked missingness pattern"
        description = "Missing positions become more common as the displayed outcome rises."
    else:
        points = ((28, 54), (50, 47), (72, 58), (94, 43), (116, 52), (138, 46))
        regular = "".join(f'<circle cx="{x}" cy="{y}" r="5" fill="{INK}"/>' for x, y in points)
        displaced = (
            f'<circle cx="178" cy="26" r="6" fill="{FAILURE}"/>'
            f'<circle cx="194" cy="74" r="6" fill="{FAILURE}"/>'
            f'<line x1="142" y1="46" x2="174" y2="29" stroke="{FAILURE}" stroke-width="2"/>'
            f'<line x1="142" y1="55" x2="190" y2="71" stroke="{FAILURE}" stroke-width="2"/>'
        )
        marks = regular + displaced
        title = "Displaced extreme measurements"
        description = (
            "Most observations remain together while two are displaced far from the group."
        )
    return f"""
<div class="lab-scenario-preview">
  <p>Deterministic presentation preview. It is not a scientific output.</p>
  <svg viewBox="0 0 220 96" role="img" aria-label="{escape(title)}: {escape(description)}">
    <line x1="14" y1="84" x2="208" y2="84" stroke="{RULE}" stroke-width="1"/>
    {marks}
  </svg>
</div>"""


def _problem_intensity(config: RunConfig) -> str:
    if config.scenario_id is ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE:
        return f"{config.missingness_rate:.0%} measurements removed"
    if config.scenario_id is ScenarioId.OUTCOME_DEPENDENT_MAR:
        return f"{config.missingness_rate:.0%} expected removed"
    return (
        f"{config.contamination_fraction:.0%} extreme; "
        f"{config.contamination_displacement:.0f}-unit displacement"
    )


def _sync_widgets(config: RunConfig, *, force: bool = False) -> None:
    values: dict[str, Any] = {
        "lab_scenario": config.scenario_id,
        "lab_run_effort": ("Quick, recommended" if config.repetitions <= 160 else "More precise"),
        "lab_mcar_rate": config.missingness_rate,
        "lab_mar_rate": config.missingness_rate,
        "lab_contamination_fraction": config.contamination_fraction,
        "lab_contamination_displacement": config.contamination_displacement,
        "lab_sample_size": config.sample_size,
        "lab_tau": config.tau,
        "lab_repetitions": config.repetitions,
        "lab_seed": config.master_seed,
        "lab_confidence": config.confidence_level,
        "lab_winsor": config.winsorization_limits,
    }
    for key, value in values.items():
        if force or key not in st.session_state:
            st.session_state[key] = value


def _on_scenario_change() -> None:
    selected = ScenarioId(st.session_state["lab_scenario"])
    _sync_widgets(get_preset(selected), force=True)


def _on_effort_change() -> None:
    st.session_state["lab_repetitions"] = (
        160 if st.session_state["lab_run_effort"] == "Quick, recommended" else 300
    )


def _restore_recommended() -> None:
    selected = ScenarioId(
        st.session_state.get("lab_scenario", ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE)
    )
    recommended = get_preset(selected)
    _sync_widgets(recommended, force=True)
    store_draft(st.session_state, recommended)
    st.session_state["status"] = "idle"
    st.session_state["error_message"] = None


def _build_config() -> RunConfig:
    scenario = ScenarioId(st.session_state["lab_scenario"])
    preset = get_preset(scenario)
    if scenario is ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE:
        missingness_rate = float(st.session_state["lab_mcar_rate"])
        contamination_fraction = preset.contamination_fraction
        contamination_displacement = preset.contamination_displacement
    elif scenario is ScenarioId.OUTCOME_DEPENDENT_MAR:
        missingness_rate = float(st.session_state["lab_mar_rate"])
        contamination_fraction = preset.contamination_fraction
        contamination_displacement = preset.contamination_displacement
    else:
        missingness_rate = preset.missingness_rate
        contamination_fraction = float(st.session_state["lab_contamination_fraction"])
        contamination_displacement = float(st.session_state["lab_contamination_displacement"])
    winsor = st.session_state["lab_winsor"]
    return with_controls(
        preset,
        sample_size=int(st.session_state["lab_sample_size"]),
        tau=float(st.session_state["lab_tau"]),
        repetitions=int(st.session_state["lab_repetitions"]),
        master_seed=int(st.session_state["lab_seed"]),
        missingness_rate=missingness_rate,
        contamination_fraction=contamination_fraction,
        contamination_displacement=contamination_displacement,
        confidence_level=float(st.session_state["lab_confidence"]),
        winsorization_limits=(float(winsor[0]), float(winsor[1])),
    )


def _render_understand() -> None:
    hero = st.columns([0.85, 1.15], gap="large")
    with hero[0]:
        st.markdown(
            """
<section class="lab-intro lab-page-shell">
  <div class="lab-product-id">Inferential Safety Lab</div>
  <h1>See how analysis choices behave when data go wrong</h1>
  <p class="lab-value">Run a synthetic experiment with a known answer, then compare accuracy, usable uncertainty, failures, and how much data each method changes.</p>
</section>
""",
            unsafe_allow_html=True,
        )
        if st.button("Set up an experiment", type="primary", key="understand-setup"):
            _switch_page("experiment")
    with hero[1]:
        st.markdown(_understand_visual(), unsafe_allow_html=True)
    st.markdown(
        """
<div class="lab-understand-body">
<section class="lab-sequence" aria-label="Four moments in the experiment">
  <div class="lab-moment"><span class="lab-moment-number">01</span><div><strong>Start with a known answer</strong><p>The simulator creates data where the correct result is known in advance.</p></div></div>
  <div class="lab-moment"><span class="lab-moment-number">02</span><div><strong>Introduce a data problem</strong><p>Measurements are removed or distorted in a controlled way.</p></div></div>
  <div class="lab-moment"><span class="lab-moment-number">03</span><div><strong>Apply several approaches</strong><p>Each approach receives the same damaged version of every synthetic dataset.</p></div></div>
  <div class="lab-moment"><span class="lab-moment-number">04</span><div><strong>Compare what happened</strong><p>Look for closeness to the known answer, usable uncertainty, withheld results, failures, and data changes.</p></div></div>
</section>
<div class="lab-boundary"><p><strong>Scientific boundary.</strong> This is a controlled teaching experiment, not evidence about a real population or a recommendation of one universally best method.</p></div>
</div>
""",
        unsafe_allow_html=True,
    )


def _render_scenario_intensity(scenario: ScenarioId, *, disabled: bool) -> None:
    if scenario is ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE:
        st.select_slider(
            "Measurements removed",
            options=(0.50, 0.60, 0.70),
            format_func=lambda value: f"{value:.0%}",
            key="lab_mcar_rate",
            disabled=disabled,
            help="The recommended setting is intentionally severe so reporting tradeoffs are visible.",
        )
    elif scenario is ScenarioId.OUTCOME_DEPENDENT_MAR:
        st.slider(
            "Expected measurements removed",
            min_value=0.15,
            max_value=0.45,
            step=0.05,
            format="%.0f%%",
            key="lab_mar_rate",
            disabled=disabled,
        )
    else:
        columns = st.columns(2)
        with columns[0]:
            st.slider(
                "Measurements made extreme",
                min_value=0.01,
                max_value=0.15,
                step=0.01,
                format="%.0f%%",
                key="lab_contamination_fraction",
                disabled=disabled,
            )
        with columns[1]:
            st.slider(
                "Size of the measurement error",
                min_value=4.0,
                max_value=12.0,
                step=1.0,
                key="lab_contamination_displacement",
                disabled=disabled,
            )


def _allowed_repetitions() -> tuple[int, ...]:
    effort = st.session_state["lab_run_effort"]
    return (80, 100, 120, 140, 160) if effort == "Quick, recommended" else (300, 350, 400, 450, 500)


def _normalize_repetitions() -> None:
    effort = st.session_state["lab_run_effort"]
    allowed_repetitions = _allowed_repetitions()
    if st.session_state["lab_repetitions"] not in allowed_repetitions:
        st.session_state["lab_repetitions"] = allowed_repetitions[
            -1 if effort.startswith("Quick") else 0
        ]


def _render_advanced_settings(*, disabled: bool) -> None:
    allowed_repetitions = _allowed_repetitions()
    with st.expander("Advanced settings", expanded=False):
        top = st.columns(3)
        with top[0]:
            st.selectbox(
                "Sample size",
                options=(100, 150, 300, 500),
                key="lab_sample_size",
                disabled=disabled,
            )
        with top[1]:
            st.selectbox(
                "Known effect",
                options=(0.0, 0.25, 0.5),
                key="lab_tau",
                disabled=disabled,
            )
        with top[2]:
            st.selectbox(
                "Exact simulated-dataset count",
                options=allowed_repetitions,
                key="lab_repetitions",
                disabled=disabled,
            )
        bottom = st.columns(3)
        with bottom[0]:
            st.number_input(
                "Seed",
                min_value=0,
                step=1,
                key="lab_seed",
                disabled=disabled,
            )
        with bottom[1]:
            st.selectbox(
                "Confidence",
                options=(0.90, 0.95, 0.99),
                key="lab_confidence",
                disabled=disabled,
            )
        with bottom[2]:
            st.slider(
                "Winsorization limits",
                min_value=-6.0,
                max_value=6.0,
                step=0.5,
                key="lab_winsor",
                disabled=disabled,
            )


def _render_preview(config: RunConfig) -> None:
    with st.expander("Preview generated data", expanded=False):
        preview = preview_scenario(config)
        frame = pd.DataFrame(preview["rows"]).rename(
            columns={
                "row": "Row",
                "treatment": "Group",
                "outcome": "Outcome",
                "clean_z": "Original measurement",
                "observed_z": "Measurement after problem",
                "status": "What changed",
            }
        )
        st.dataframe(frame, hide_index=True, width="stretch")
        st.caption(
            "This small preview is generated from the current settings and is not included in results or downloads."
        )


def _execute_pending_run() -> None:
    if st.session_state.get("_lab_run_requested") is not True:
        return
    config = st.session_state["draft_config"]
    status = st.status("Preparing synthetic samples…", expanded=False, state="running")
    progress = st.progress(0.0, text="Preparing synthetic samples…")
    sleep(0.1)

    def announce(completed: int, total: int) -> None:
        message = f"Simulating sample {completed} of {total}…"
        update_progress(
            st.session_state,
            completed=completed,
            total=total,
            message=message,
        )
        progress.progress(completed / total, text=message)
        status.update(label=message, state="running")

    try:
        run = run_lab(config, progress=announce)
        summary = "Summarizing the comparison…"
        update_progress(
            st.session_state,
            completed=config.repetitions,
            total=config.repetitions,
            message=summary,
        )
        progress.progress(1.0, text=summary)
        status.update(label=summary, state="running")
        sleep(0.15)
        mark_complete(st.session_state, run, config)
        st.session_state["_lab_run_requested"] = False
        st.session_state.pop("_lab_safety_card_html", None)
        st.session_state.pop("_lab_safety_card_fingerprint", None)
        st.session_state.pop("_lab_safety_card_preview", None)
        status.update(label="Experiment complete. Your results are ready.", state="complete")
        st.rerun()
    except Exception as exc:  # pragma: no cover - browser-level recoverable state
        st.session_state["_lab_run_requested"] = False
        mark_error(st.session_state, f"{type(exc).__name__}: {exc}")
        status.update(label="The experiment stopped before a new result was saved.", state="error")
        st.rerun()


def _render_experiment() -> None:
    initialize_ui_state(
        st.session_state,
        get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE),
    )
    _sync_widgets(st.session_state["draft_config"])
    running = st.session_state["status"] == "running"
    st.markdown(
        """
<header class="lab-page-head lab-page-shell">
  <div class="lab-product-id">Inferential Safety Lab</div>
  <h1>Set up an experiment</h1>
  <p>Choose one data problem, decide how much simulation effort to use, and run the same fixed comparison across synthetic datasets.</p>
</header>
""",
        unsafe_allow_html=True,
    )
    layout = st.columns([1.62, 0.98], gap="large", vertical_alignment="top")
    config: RunConfig | None = None
    validation_error: str | None = None
    with layout[0]:
        scenario = st.radio(
            "Choose a data problem",
            options=list(ScenarioId),
            format_func=lambda item: SCENARIO_LABELS[item],
            captions=[SCENARIO_CAPTIONS[item] for item in ScenarioId],
            key="lab_scenario",
            on_change=_on_scenario_change,
            disabled=running,
            width="stretch",
        )
        st.radio(
            "Run effort",
            options=("Quick, recommended", "More precise"),
            captions=(
                "Faster feedback with a bounded set of simulated datasets.",
                "More simulated datasets for a steadier comparison and a longer run time.",
            ),
            key="lab_run_effort",
            on_change=_on_effort_change,
            horizontal=True,
            disabled=running,
            width="stretch",
        )
        _render_scenario_intensity(ScenarioId(scenario), disabled=running)
        _normalize_repetitions()

        try:
            config = _build_config()
            store_draft(st.session_state, config)
        except ValueError as exc:
            validation_error = str(exc)
            st.error(f"Check these settings: {validation_error}")

        if config is not None and has_stale_result(st.session_state):
            st.warning("Settings changed. Run again to replace the saved result.")

        run_clicked = st.button(
            "Run experiment",
            type="primary",
            key="run-experiment",
            disabled=running or validation_error is not None,
            width="stretch",
        )
        st.button(
            "Restore recommended settings",
            key="restore-settings",
            on_click=_restore_recommended,
            disabled=running,
            width="stretch",
        )
        if run_clicked and config is not None:
            mark_running(st.session_state, config)
            st.session_state["_lab_run_requested"] = True
            st.rerun()

        _render_advanced_settings(disabled=running)
        if config is not None:
            _render_preview(config)

        if st.session_state["status"] == "complete":
            st.success("Experiment complete. Your results are ready.")
            if st.button("View results", type="primary", key="view-results"):
                _switch_page("results")
        elif st.session_state["status"] == "error":
            st.error(
                "The experiment could not finish, and the previous completed result was kept. "
                f"Details: {st.session_state['error_message']}"
            )

    with layout[1]:
        if config is not None:
            estimate = estimated_runtime_seconds(config)
            st.markdown(
                f"""
<aside class="lab-glance" aria-label="Experiment at a glance">
  <h2>Experiment at a glance</h2>
  <div class="lab-glance-row"><span>Data problem</span><strong>{escape(SCENARIO_LABELS[config.scenario_id])}</strong></div>
  <div class="lab-glance-row"><span>Known answer</span><strong>{config.tau:.2f}</strong></div>
  <div class="lab-glance-row"><span>Sample size</span><strong>{config.sample_size}</strong></div>
  <div class="lab-glance-row"><span>Simulated datasets</span><strong>{config.repetitions}</strong></div>
  <div class="lab-glance-row"><span>Problem intensity</span><strong>{escape(_problem_intensity(config))}</strong></div>
  <div class="lab-glance-row"><span>Practical approaches</span><strong>4</strong></div>
  <div class="lab-glance-row"><span>Estimated runtime</span><strong>{estimate:.1f} seconds</strong></div>
  {_scenario_preview(config.scenario_id)}
</aside>
""",
                unsafe_allow_html=True,
            )

    _execute_pending_run()


def _technical_comparison_table(metrics: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for index, row in enumerate(metrics):
        interval = interval_display(row)
        code, _ = method_identity(index)
        rows.append(
            {
                "Method": f"{code}  {_public_method_name(row)}",
                "Valid fits": f"{row['valid_fits']}/{row['attempted_runs']}",
                "Bias": show_number(row["bias"]),
                "Absolute bias": show_number(row["absolute_bias"]),
                "RMSE": show_number(row["rmse"]),
                "Interval status": interval["status"],
                "Conditional coverage": interval["conditional_coverage"],
                "Interval availability": interval["interval_availability"],
                "Valid-and-cover rate": interval["valid_and_cover"],
                "Row retention": show_percent(row["mean_row_retention"]),
                "Filled missing": show_percent(row["mean_filled_missing_fraction"]),
                "Changed observed": show_percent(row["mean_changed_observed_fraction"]),
                "Explicit deletion": show_percent(row["mean_explicit_deletion_fraction"]),
            }
        )
    return pd.DataFrame(rows)


def _technical_contract_table(contracts: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Method": (
                    f"{method_identity(index)[0]}  "
                    f"{public_method_label(str(contract['method_id']), str(contract['display_name']))}"
                ),
                "Preprocessing": public_preprocessing_label(contract["preprocessing_id"]),
                "Estimator": public_estimator_label(contract["estimator_id"]),
                "Interval scientifically applicable": (
                    "Yes" if contract["interval_scientifically_applicable"] else "No"
                ),
                "Interval limitation": contract["interval_unavailability_reason"] or "None",
                "Method limitation": contract["limitations"],
            }
            for index, contract in enumerate(contracts)
        ]
    )


def _table_region(frame: pd.DataFrame, label: str) -> str:
    return (
        f'<div class="lab-technical-scroll" role="region" aria-label="{escape(label)}" '
        f'tabindex="0">{frame.to_html(index=False, border=0)}</div>'
    )


def _selected_finding(metrics: list[dict[str, Any]]) -> str:
    candidates = [
        row
        for row in metrics
        if row["rmse"] is not None and int(row["point_estimate_available_runs"]) > 0
    ]
    if not candidates:
        return "No method reported enough point estimates for an error comparison in this run."
    selected = min(candidates, key=lambda row: float(row["rmse"]))
    return (
        f"{_public_method_name(selected)} was closest among reported results by typical estimate "
        f"error. It produced a point estimate for "
        f"{selected['point_estimate_available_runs']} of {selected['attempted_runs']} simulated "
        "datasets, so read that error together with reporting availability."
    )


def _known_answer_rail(metrics: list[dict[str, Any]], truth_value: float) -> str:
    estimates = [truth_value + float(row["bias"]) for row in metrics if row.get("bias") is not None]
    lower = min([truth_value, *estimates])
    upper = max([truth_value, *estimates])
    spread = upper - lower
    if spread < 0.05:
        spread = 0.05
    lower -= spread * 0.15
    upper += spread * 0.15

    def position(value: float) -> float:
        return max(1.5, min(98.5, 100 * (value - lower) / (upper - lower)))

    known_position = position(truth_value)
    rows = []
    accessible = [f"Known answer {truth_value:.3f}."]
    for index, row in enumerate(metrics):
        estimate = None if row.get("bias") is None else truth_value + float(row["bias"])
        reported = int(row["point_estimate_available_runs"])
        attempted = int(row["attempted_runs"])
        code, color = method_identity(index)
        estimate_mark = (
            f'<span class="lab-answer-estimate" aria-hidden="true" '
            f'style="left:{position(estimate):.2f}%;--method-color:{color}"></span>'
            if estimate is not None
            else ""
        )
        shown = f"Average {estimate:.3f}" if estimate is not None else "Average not available"
        accessible.append(
            f"Method {code}, {_public_method_name(row)}, {shown.lower()}, reported on "
            f"{reported} of {attempted} runs."
        )
        rows.append(
            f"""
<div class="lab-answer-row">
  {_method_marker(row, index)}
  <div class="lab-answer-track" aria-hidden="true">
    <span class="lab-answer-known" style="left:{known_position:.2f}%"></span>
    {estimate_mark}
  </div>
  <div class="lab-answer-value">{escape(shown)}<br>{reported}/{attempted} runs</div>
</div>"""
        )
    return f"""
<section class="lab-answer-rail" role="img" aria-label="{escape(" ".join(accessible))}">
  <div class="lab-answer-rail-head"><strong>Average estimates against the known answer</strong><span>Known answer {truth_value:.3f}</span></div>
  {"".join(rows)}
</section>"""


def _headline_comparisons(metrics: list[dict[str, Any]]) -> str:
    reported = [
        row
        for row in metrics
        if row["rmse"] is not None and int(row["point_estimate_available_runs"]) > 0
    ]
    closest = min(reported, key=lambda row: float(row["rmse"])) if reported else None
    applicable = [row for row in metrics if int(row["interval_applicable_attempts"]) > 0]
    uncertainty = (
        max(applicable, key=lambda row: float(row["interval_availability"])) if applicable else None
    )
    result = max(metrics, key=lambda row: float(row["point_estimate_availability"]))
    closest_index = metrics.index(closest) if closest else 0
    uncertainty_index = metrics.index(uncertainty) if uncertainty else 0
    result_index = metrics.index(result)
    primary_marker = (
        _method_marker(closest, closest_index)
        if closest
        else "<strong>No result available</strong>"
    )
    uncertainty_marker = (
        _method_marker(uncertainty, uncertainty_index)
        if uncertainty
        else "<strong>No usable ranges</strong>"
    )
    uncertainty_value = (
        show_percent(uncertainty["interval_availability"]) if uncertainty else "Not available"
    )
    return f"""
<div class="lab-evidence" aria-label="One primary observation and two supporting facts">
  <div class="lab-evidence-primary"><span>One finding from this run</span>{primary_marker}<p>{escape(_selected_finding(metrics))}</p></div>
  <div class="lab-evidence-support">
    <div class="lab-evidence-fact"><span>Usable uncertainty most often</span>{uncertainty_marker}<em>{escape(uncertainty_value)} of attempts</em></div>
    <div class="lab-evidence-fact"><span>Point estimate most often</span>{_method_marker(result, result_index)}<em>{escape(show_percent(result["point_estimate_availability"]))} of attempts</em></div>
  </div>
</div>
"""


def _method_summary(metrics: list[dict[str, Any]]) -> str:
    rows = []
    for index, row in enumerate(metrics):
        interval = (
            f"{row['interval_available_runs']} of {row['attempted_runs']} datasets"
            if int(row["interval_applicable_attempts"]) > 0
            else "Not designed to report usable uncertainty here"
        )
        rows.append(
            f"""
<div class="lab-method-row">
  {_method_marker(row, index)}
  <div class="lab-method-cell"><span>Estimate error</span><p>Average miss {escape(show_number(row["absolute_bias"]))}<br>Typical error {escape(show_number(row["rmse"]))}</p></div>
  <div class="lab-method-cell"><span>Usable uncertainty</span><p>{escape(interval)}</p></div>
  <div class="lab-method-cell"><span>Result reported</span><p>{row["point_estimate_available_runs"]} of {row["attempted_runs"]} datasets</p></div>
</div>"""
        )
    return '<div class="lab-method-list">' + "".join(rows) + "</div>"


def _data_change_summary(metrics: list[dict[str, Any]]) -> str:
    rows = []
    for index, row in enumerate(metrics):
        rows.append(
            f"""
<div class="lab-data-row">
  {_method_marker(row, index)}
  <div class="lab-data-cell"><span>Rows used</span><p>{escape(show_percent(row["mean_row_retention"]))}</p></div>
  <div class="lab-data-cell"><span>Missing values filled</span><p>{escape(show_percent(row["mean_filled_missing_fraction"]))}</p></div>
  <div class="lab-data-cell"><span>Observed values changed</span><p>{escape(show_percent(row["mean_changed_observed_fraction"]))}</p></div>
  <div class="lab-data-cell"><span>Rows explicitly removed</span><p>{escape(show_percent(row["mean_explicit_deletion_fraction"]))}</p></div>
</div>"""
        )
    return '<div class="lab-data-list">' + "".join(rows) + "</div>"


def _render_technical_details(run: Any) -> None:
    aggregate = run.aggregate
    metrics = aggregate["method_metrics"]
    st.markdown("#### Full method table")
    st.html(_table_region(_technical_comparison_table(metrics), "Full technical method table"))
    st.markdown("#### Known estimand and formulas")
    st.markdown(
        f"""
**Exact estimand:** {aggregate["known_truth"]["estimand"]}

**Known-truth formula:** `{aggregate["known_truth"]["formula"]}`

```text
Z ~ Normal(0,1)
T | Z ~ Bernoulli(expit(-0.2 + 0.6 Z))
Y = 1 + tau T + 0.8 Z + 0.5 T Z + epsilon, with epsilon ~ Normal(0,1)
```
"""
    )
    st.markdown("#### Exact denominators")
    st.markdown(
        """
- Conditional coverage = covered usable applicable intervals / usable applicable intervals.
- Interval availability = usable applicable intervals / all attempted runs.
- Valid-and-cover rate = covered usable applicable intervals / all attempted runs.
- Point availability, fit validity, interval applicability, and interval availability remain distinct.
"""
    )
    st.markdown("#### Method contracts")
    st.html(
        _table_region(
            _technical_contract_table(aggregate["method_contracts"]),
            "Technical method contracts",
        )
    )
    st.markdown("#### Replay and canonical record")
    st.code(aggregate["replay_command"], language="powershell")
    st.markdown(f"**Run fingerprint:** `{aggregate['replay_hash']}`")
    st.code(run.canonical_json, language="json", line_numbers=True)


def _ensure_safety_card(run: Any) -> str:
    fingerprint = str(st.session_state["last_run_fingerprint"])
    if st.session_state.get("_lab_safety_card_fingerprint") != fingerprint:
        st.session_state["_lab_safety_card_html"] = render_safety_card(run.aggregate)
        st.session_state["_lab_safety_card_fingerprint"] = fingerprint
    return str(st.session_state["_lab_safety_card_html"])


def _start_another_experiment(config: RunConfig) -> None:
    recommended = get_preset(config.scenario_id)
    _sync_widgets(recommended, force=True)
    store_draft(st.session_state, recommended)
    st.session_state["status"] = "idle"
    st.session_state["error_message"] = None
    _switch_page("experiment")


def _render_results() -> None:
    initialize_ui_state(
        st.session_state,
        get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE),
    )
    st.markdown(
        """
<header class="lab-page-head lab-page-shell">
  <div class="lab-product-id">Inferential Safety Lab</div>
  <h1>Results</h1>
  <p>Compare what each method reported, withheld, changed, or got wrong against the known answer.</p>
</header>
""",
        unsafe_allow_html=True,
    )
    run = st.session_state["last_run"]
    saved_config = st.session_state["last_run_config"]
    if run is None or saved_config is None:
        st.info("No results yet. Set up and run an experiment to see the comparison.")
        if st.button("Set up an experiment", type="primary", key="empty-results-setup"):
            _switch_page("experiment")
        return

    aggregate = run.aggregate
    metrics = aggregate["method_metrics"]
    effort = "Quick, recommended" if saved_config.repetitions <= 160 else "More precise"
    st.html(_known_answer_rail(metrics, float(aggregate["known_truth"]["value"])))
    run_summary = f"""
<div class="lab-run-summary" aria-label="Saved run summary">
  <div class="lab-summary-item"><span>DATA PROBLEM</span><strong>{escape(SCENARIO_LABELS[saved_config.scenario_id])}</strong></div>
  <div class="lab-summary-item"><span>KNOWN ANSWER</span><strong>{saved_config.tau:.2f}</strong></div>
  <div class="lab-summary-item"><span>SIMULATED DATASETS</span><strong>{saved_config.repetitions}</strong></div>
  <div class="lab-summary-item"><span>RUN EFFORT</span><strong>{escape(effort)}</strong></div>
</div>
"""

    st.header("How far were estimates from the known answer?")
    st.markdown(
        "<p class='lab-chart-description'>Lower values are closer to the known answer. The chart keeps average directional miss and typical overall error as separate measures.</p>",
        unsafe_allow_html=True,
    )
    st.html(_method_key(metrics))
    if any(row["absolute_bias"] is not None or row["rmse"] is not None for row in metrics):
        plain_metrics = [{**row, "display_name": _public_method_name(row)} for row in metrics]
        error_svg = estimation_error_svg(plain_metrics).replace(
            "<svg ",
            '<svg class="lab-primary-comparison" style="display:block;width:100%;height:auto;margin:.4rem 0 1rem" ',
            1,
        )
        st.markdown(error_svg, unsafe_allow_html=True)
    else:
        st.info("No reported estimates were available for an error comparison.")

    st.markdown(run_summary, unsafe_allow_html=True)
    if has_stale_result(st.session_state):
        st.warning("Settings changed. Run again to replace the saved result.")

    st.markdown(
        "<p class='lab-narrative'>This comparison shows tradeoffs, not a winner. Read estimate error together with how often a method reported, whether it supplied usable uncertainty, and how much data it changed or removed.</p>",
        unsafe_allow_html=True,
    )
    st.html(_headline_comparisons(metrics))
    st.markdown(
        f"<div class='lab-condition-note'>{escape(GUARDED_CONDITIONAL_WARNING)}</div>",
        unsafe_allow_html=True,
    )

    st.header("How often was usable uncertainty reported?")
    st.markdown(
        "<p class='lab-chart-description'>Interval availability means how often a method reported a scientifically usable uncertainty range. Coverage asks how often reported ranges included the known answer. Methods not designed to report usable ranges here are omitted.</p>",
        unsafe_allow_html=True,
    )
    method_order = [_chart_method_name(row, index) for index, row in enumerate(metrics)]
    availability_rows = _plain_chart_rows(coverage_availability_rows(metrics), metrics)
    if availability_rows:
        st.vega_lite_chart(
            pd.DataFrame(availability_rows),
            spec=paired_percentage_chart_spec(method_order),
            width="stretch",
            theme=None,
        )
    else:
        st.info("No method reported a scientifically usable uncertainty range in this run.")

    st.header("Method summary")
    st.markdown(
        "<p class='lab-chart-description'>A method can appear good only on the datasets where it reports. Compare all three columns before drawing a conclusion.</p>",
        unsafe_allow_html=True,
    )
    st.html(_method_summary(metrics))

    st.header("Data changed or discarded")
    st.markdown(
        "<p class='lab-chart-description'>These values show what each approach used, filled, changed, or explicitly removed before estimating the answer.</p>",
        unsafe_allow_html=True,
    )
    st.html(_data_change_summary(metrics))

    st.header("Reported, withheld, or failed")
    st.markdown(
        "<p class='lab-chart-description'>A withheld result can be an intentional safety behavior. It is shown separately from a reported result so low availability is never mistaken for zero error.</p>",
        unsafe_allow_html=True,
    )
    completions = _plain_chart_rows(completion_rows(metrics), metrics)
    st.vega_lite_chart(
        pd.DataFrame(completions),
        spec=completion_chart_spec(
            method_order, max(int(row["attempted_runs"]) for row in metrics)
        ),
        width="stretch",
        theme=None,
    )
    failure_lines = []
    for row in metrics:
        for code, count in row["failure_code_counts"].items():
            failure_lines.append(
                f"**{_public_method_name(row)}:** {count} withheld or failed because the "
                f"{public_failure_label(code).lower()}."
            )
    if failure_lines:
        st.markdown("  \n".join(failure_lines))

    action_columns = st.columns([1, 1.35, 3])
    with action_columns[0]:
        if st.button("Change settings", key="change-settings", width="stretch"):
            _switch_page("experiment")
    with action_columns[1]:
        if st.button(
            "Start another experiment",
            type="primary",
            key="start-another",
            width="stretch",
        ):
            _start_another_experiment(saved_config)

    with st.expander("Technical details and exact records", expanded=False):
        st.markdown(f"{WHY_AVAILABILITY_DIFFERS}  \n\n{GUARDED_CONDITIONAL_WARNING}")
        _render_technical_details(run)

    st.markdown(
        """
<section class="lab-safety">
  <h2>Inferential Safety Card</h2>
  <p>The Safety Card is an audit-ready, self-contained record of this saved run. It includes the exact configuration, method contracts, denominators, charts, limitations, replay details, and canonical fingerprint.</p>
</section>
""",
        unsafe_allow_html=True,
    )
    card_actions = st.columns([1, 1, 2.6])
    prepare = False
    preview = False
    with card_actions[0]:
        prepare = st.button("Prepare download", key="prepare-card", width="stretch")
    with card_actions[1]:
        preview = st.button("Preview Safety Card", key="preview-card", width="stretch")
    if prepare or preview:
        card = _ensure_safety_card(run)
        if preview:
            st.session_state["_lab_safety_card_preview"] = True
    else:
        card = st.session_state.get("_lab_safety_card_html")
    if card is not None:
        st.download_button(
            "Download Safety Card",
            data=card,
            file_name="inferential-safety-card.html",
            mime="text/html",
            key="download-card",
        )
    if card is not None and st.session_state.get("_lab_safety_card_preview"):
        encoded = base64.b64encode(str(card).encode("utf-8")).decode("ascii")
        st.iframe(
            f"data:text/html;base64,{encoded}",
            height=720,
            tab_index=0,
        )


def main() -> None:
    st.set_page_config(
        page_title="Inferential Safety Lab",
        page_icon="🧪",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown(_css(), unsafe_allow_html=True)
    initialize_ui_state(
        st.session_state,
        get_preset(ScenarioId.MCAR_SMALL_EFFECTIVE_SAMPLE),
    )
    _PAGES.clear()
    _PAGES.update(
        understand=st.Page(
            _render_understand,
            title="Understand",
            url_path="",
            default=True,
        ),
        experiment=st.Page(
            _render_experiment,
            title="Experiment",
            url_path="experiment",
        ),
        results=st.Page(
            _render_results,
            title="Results",
            url_path="results",
        ),
    )
    navigation = st.navigation(list(_PAGES.values()), position="top")
    navigation.run()


if __name__ == "__main__":
    main()
