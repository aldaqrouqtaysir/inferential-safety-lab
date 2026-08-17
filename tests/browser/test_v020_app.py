from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).parents[2]
PORT = int(os.environ.get("ISL_BROWSER_PORT", "8520"))
URL = f"http://127.0.0.1:{PORT}"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

pytestmark = pytest.mark.skipif(
    os.environ.get("ISL_RUN_BROWSER_TESTS") != "1",
    reason="set ISL_RUN_BROWSER_TESTS=1 for the local Playwright acceptance matrix",
)


def _wait_for_port(process: subprocess.Popen[str], timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Streamlit exited before startup with code {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"Streamlit did not listen on port {PORT}")


@pytest.fixture(scope="session")
def app_server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    log_path = tmp_path_factory.mktemp("browser-server") / "streamlit.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "streamlit_app.py",
                "--server.headless=true",
                f"--server.port={PORT}",
                "--browser.gatherUsageStats=false",
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
        )
        try:
            _wait_for_port(process)
            yield
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture(scope="session")
def browser(app_server: None) -> Iterator[Browser]:
    del app_server
    with sync_playwright() as playwright:
        launch_options: dict[str, Any] = {"headless": True}
        if CHROME.exists():
            launch_options["executable_path"] = str(CHROME)
        instance = playwright.chromium.launch(**launch_options)
        try:
            yield instance
        finally:
            instance.close()


def _page(browser: Browser, **context_options: Any) -> tuple[Page, list[str], list[str]]:
    context = browser.new_context(**context_options)
    page = context.new_page()
    errors: list[str] = []
    warnings: list[str] = []

    def record(message: Any) -> None:
        if message.type == "error":
            location = message.location
            errors.append(f"{message.text} @ {location.get('url', '')}")
        elif message.type == "warning":
            warnings.append(message.text)

    page.on("console", record)
    return page, errors, warnings


def _open(page: Page, path: str = "") -> None:
    page.goto(f"{URL}{path}", wait_until="domcontentloaded", timeout=30_000)
    page.locator("[data-testid='stAppViewContainer']").wait_for(state="visible", timeout=30_000)


def _assert_no_document_overflow(page: Page) -> None:
    dimensions = page.evaluate(
        """() => ({
            scrollWidth: document.documentElement.scrollWidth,
            clientWidth: document.documentElement.clientWidth
        })"""
    )
    assert dimensions["scrollWidth"] <= dimensions["clientWidth"] + 1, dimensions


def _assert_heading_not_clipped(page: Page, name: str, *, maximum_font_size: float) -> None:
    values = page.get_by_role("heading", name=name, exact=True).evaluate(
        """element => ({
            clientWidth: element.clientWidth,
            scrollWidth: element.scrollWidth,
            clientHeight: element.clientHeight,
            scrollHeight: element.scrollHeight,
            fontSize: parseFloat(getComputedStyle(element).fontSize)
        })"""
    )
    assert values["scrollWidth"] <= values["clientWidth"] + 1, values
    assert values["scrollHeight"] <= values["clientHeight"] + 1, values
    assert values["fontSize"] <= maximum_font_size, values


def _assert_desktop_page_alignment(page: Page, heading_name: str, viewport_width: int) -> None:
    heading = page.get_by_role("heading", name=heading_name, exact=True)
    heading_box = heading.bounding_box()
    first_nav_box = page.locator("[data-testid='stTopNavLink']").first.bounding_box()
    shell_box = page.locator("[data-testid='stMainBlockContainer']").bounding_box()
    assert heading_box and first_nav_box and shell_box
    assert abs(shell_box["x"]) <= 1
    assert abs(shell_box["width"] - min(viewport_width, 1600)) <= 1
    assert 0 <= heading_box["x"] - first_nav_box["x"] <= 16
    vertical_gap = heading_box["y"] - (first_nav_box["y"] + first_nav_box["height"])
    assert 36 <= vertical_gap <= 56, vertical_gap


def _assert_console_clean(errors: list[str], warnings: list[str]) -> None:
    assert not errors
    vega_warnings = [
        warning
        for warning in warnings
        if "empty extent" in warning.lower()
        or "infinite extent" in warning.lower()
        or "fit-y" in warning.lower()
    ]
    assert not vega_warnings


def _hex_luminance(value: str) -> float:
    rgb = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in rgb
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    lighter, darker = sorted((_hex_luminance(first), _hex_luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_understand_navigation_empty_results_and_keyboard_focus(browser: Browser) -> None:
    page, errors, warnings = _page(browser, viewport={"width": 1440, "height": 1000})
    _open(page)
    page.get_by_role(
        "heading", name="See how analysis choices behave when data go wrong", exact=True
    ).wait_for(timeout=30_000)
    _assert_heading_not_clipped(
        page,
        "See how analysis choices behave when data go wrong",
        maximum_font_size=46,
    )
    primary_text = page.locator("section[data-testid='stMain']").inner_text()
    for answer in (
        "The simulator creates data where the correct result is known in advance.",
        "Measurements are removed or distorted in a controlled way.",
        "Each approach receives the same damaged version of every synthetic dataset.",
        "Look for closeness to the known answer",
        "Set up an experiment",
    ):
        assert answer in primary_text

    visual = page.locator(".lab-explainer svg")
    assert visual.count() == 1
    assert visual.get_attribute("role") == "img"
    assert "known answer is fixed" in (visual.locator("desc").text_content() or "").lower()
    assert visual.locator("animate, animateTransform").count() == 0

    sequence_box = page.locator(".lab-sequence").bounding_box()
    moment_boxes = page.locator(".lab-moment").evaluate_all(
        "elements => elements.map(element => { const box = element.getBoundingClientRect(); return {x: box.x, y: box.y, width: box.width, height: box.height}; })"
    )
    boundary_box = page.locator(".lab-boundary").bounding_box()
    assert sequence_box and boundary_box and len(moment_boxes) == 4
    assert abs(moment_boxes[0]["x"] - moment_boxes[2]["x"]) <= 1
    assert abs(moment_boxes[1]["x"] - moment_boxes[3]["x"]) <= 1
    assert abs(moment_boxes[0]["y"] - moment_boxes[1]["y"]) <= 1
    assert abs(moment_boxes[2]["y"] - moment_boxes[3]["y"]) <= 1
    assert moment_boxes[1]["x"] >= moment_boxes[0]["x"] + moment_boxes[0]["width"] + 96
    assert moment_boxes[2]["y"] >= moment_boxes[0]["y"] + moment_boxes[0]["height"] - 1
    assert (
        max(box["width"] for box in moment_boxes) - min(box["width"] for box in moment_boxes) <= 1
    )
    assert abs(moment_boxes[0]["x"] - sequence_box["x"]) <= 1
    assert (
        abs(
            moment_boxes[1]["x"]
            + moment_boxes[1]["width"]
            - (sequence_box["x"] + sequence_box["width"])
        )
        <= 1
    )
    assert abs(boundary_box["x"] - moment_boxes[2]["x"]) <= 1
    assert abs(boundary_box["width"] - moment_boxes[2]["width"]) <= 1
    assert boundary_box["y"] >= moment_boxes[2]["y"] + moment_boxes[2]["height"]
    sequence_style = page.locator(".lab-sequence").evaluate(
        "element => ({borderTopWidth:getComputedStyle(element).borderTopWidth})"
    )
    moment_style = page.locator(".lab-moment").first.evaluate(
        "element => ({borderTopWidth:getComputedStyle(element).borderTopWidth, borderRightWidth:getComputedStyle(element).borderRightWidth, borderBottomWidth:getComputedStyle(element).borderBottomWidth, borderLeftWidth:getComputedStyle(element).borderLeftWidth, borderRadius:getComputedStyle(element).borderRadius, backgroundColor:getComputedStyle(element).backgroundColor, boxShadow:getComputedStyle(element).boxShadow})"
    )
    number_style = page.locator(".lab-moment-number").first.evaluate(
        "element => ({borderTopWidth:getComputedStyle(element).borderTopWidth,borderRightWidth:getComputedStyle(element).borderRightWidth,borderBottomWidth:getComputedStyle(element).borderBottomWidth,borderLeftWidth:getComputedStyle(element).borderLeftWidth,backgroundColor:getComputedStyle(element).backgroundColor,letterSpacing:parseFloat(getComputedStyle(element).letterSpacing)})"
    )
    boundary_style = page.locator(".lab-boundary").evaluate(
        "element => ({borderTopWidth:getComputedStyle(element).borderTopWidth,borderLeftWidth:getComputedStyle(element).borderLeftWidth,backgroundColor:getComputedStyle(element).backgroundColor})"
    )
    assert sequence_style["borderTopWidth"] == "0px"
    assert {
        moment_style["borderTopWidth"],
        moment_style["borderRightWidth"],
        moment_style["borderBottomWidth"],
        moment_style["borderLeftWidth"],
    } == {"1px"}
    assert moment_style["borderRadius"] == "20px"
    assert moment_style["backgroundColor"] == "rgb(255, 255, 255)"
    assert moment_style["boxShadow"] != "none"
    assert {
        number_style["borderTopWidth"],
        number_style["borderRightWidth"],
        number_style["borderBottomWidth"],
        number_style["borderLeftWidth"],
    } == {"0px"}
    assert number_style["backgroundColor"] == "rgba(0, 0, 0, 0)"
    assert number_style["letterSpacing"] > 1
    assert boundary_style == {
        "borderTopWidth": "1px",
        "borderLeftWidth": "4px",
        "backgroundColor": "rgb(255, 255, 255)",
    }
    _assert_desktop_page_alignment(
        page,
        "See how analysis choices behave when data go wrong",
        1440,
    )

    product_id = page.locator(".lab-product-id")
    assert product_id.inner_text().strip() == "Inferential Safety Lab"
    visible_product_id = page.locator("[data-testid='stHeader']").evaluate(
        "element => getComputedStyle(element, '::after').content"
    )
    assert "Inferential Safety Lab" in visible_product_id

    active = page.locator("a[aria-current='page']")
    assert active.count() == 1
    assert active.inner_text().strip() == "Understand"

    cta = page.get_by_role("button", name="Set up an experiment", exact=True)
    cta_box = cta.bounding_box()
    assert cta_box and cta_box["y"] + cta_box["height"] <= 1000
    for _ in range(20):
        page.keyboard.press("Tab")
        if cta.evaluate("element => element === document.activeElement"):
            break
    assert cta.evaluate("element => element === document.activeElement")
    focus = cta.evaluate(
        "element => ({style:getComputedStyle(element).outlineStyle,width:getComputedStyle(element).outlineWidth})"
    )
    assert focus["style"] != "none" and focus["width"] != "0px"

    page.get_by_text("Results", exact=True).first.click()
    page.wait_for_url(f"{URL}/results", timeout=30_000)
    page.get_by_text(
        "No results yet. Set up and run an experiment to see the comparison.", exact=True
    ).wait_for(timeout=30_000)
    _assert_desktop_page_alignment(page, "Results", 1440)
    _assert_no_document_overflow(page)
    _assert_console_clean(errors, warnings)
    page.context.close()


def test_successful_run_progress_saved_result_and_stale_prevention(browser: Browser) -> None:
    page, errors, warnings = _page(browser, viewport={"width": 1366, "height": 768})
    _open(page)
    page.get_by_text("Experiment", exact=True).first.click()
    page.wait_for_url(f"{URL}/experiment", timeout=30_000)
    page.get_by_role("heading", name="Set up an experiment", exact=True).wait_for(timeout=30_000)
    glance = page.locator(".lab-glance")
    glance.wait_for(timeout=30_000)
    glance_text = glance.inner_text()
    for label in (
        "Data problem",
        "Known answer",
        "Sample size",
        "Simulated datasets",
        "Problem intensity",
        "Practical approaches",
        "Estimated runtime",
    ):
        assert label in glance_text
    scenario_preview = glance.locator("svg[role='img']")
    assert scenario_preview.count() == 1
    assert "Randomly missing measurements" in (scenario_preview.get_attribute("aria-label") or "")
    assert scenario_preview.locator("animate, animateTransform").count() == 0
    page.evaluate(
        """() => {
            window.__labAnnouncements = [];
            const phrases = [
              'Preparing synthetic samples…',
              'Summarizing the comparison…',
              'Experiment complete. Your results are ready.'
            ];
            const capture = () => {
              const text = document.body.innerText;
              for (const phrase of phrases) {
                if (text.includes(phrase) && !window.__labAnnouncements.includes(phrase)) {
                  window.__labAnnouncements.push(phrase);
                }
              }
              if (/Simulating sample [0-9]+ of [0-9]+…/.test(text) &&
                  !window.__labAnnouncements.includes('Simulating sample X of Y…')) {
                window.__labAnnouncements.push('Simulating sample X of Y…');
              }
            };
            new MutationObserver(capture).observe(document.body, {
              subtree: true, childList: true, characterData: true
            });
            capture();
        }"""
    )
    page.get_by_role("button", name="Run experiment", exact=True).click()
    page.get_by_text("Experiment complete. Your results are ready.", exact=True).wait_for(
        timeout=60_000
    )
    announcements = page.evaluate("window.__labAnnouncements")
    assert "Preparing synthetic samples…" in announcements
    assert "Simulating sample X of Y…" in announcements
    assert "Summarizing the comparison…" in announcements
    assert "Experiment complete. Your results are ready." in announcements

    page.get_by_role("button", name="View results", exact=True).click()
    page.wait_for_url(f"{URL}/results", timeout=30_000)
    page.get_by_role("heading", name="Method summary", exact=True).wait_for(timeout=30_000)
    answer_rail = page.locator(".lab-answer-rail")
    answer_rail.wait_for(timeout=30_000)
    answer_text = answer_rail.inner_text()
    assert "Known answer 0.250" in answer_text
    assert "Average" in answer_text
    assert "runs" in answer_text
    assert answer_rail.locator(".lab-method-marker").count() == 4
    primary_comparison = page.locator(".lab-primary-comparison")
    primary_box = primary_comparison.bounding_box()
    assert primary_box and primary_box["y"] < 768
    results_heading_box = page.get_by_role("heading", name="Results", exact=True).bounding_box()
    answer_box = answer_rail.bounding_box()
    assert results_heading_box and answer_box
    assert abs(answer_box["x"] - results_heading_box["x"]) <= 1
    assert abs(primary_box["x"] - results_heading_box["x"]) <= 1
    visible_results = page.locator("section[data-testid='stMain']").inner_text()
    assert "Randomly missing measurements" in visible_results
    assert "This comparison shows tradeoffs, not a winner." in visible_results
    assert "A method can appear good only on the datasets where it reports." in visible_results
    assert "HC3" not in visible_results
    assert "valid-and-cover" not in visible_results
    assert "replay hash" not in visible_results.lower()
    for accessible_chart_text in (
        "How often was usable uncertainty reported?",
        "Interval availability means how often a method reported",
        "How far were estimates from the known answer?",
        "Lower values are closer to the known answer.",
        "Reported, withheld, or failed",
        "A withheld result can be an intentional safety behavior.",
    ):
        assert accessible_chart_text in visible_results
    assert "conditional on runs that passed the guard" in visible_results

    page.get_by_role("button", name="Change settings", exact=True).click()
    page.wait_for_url(f"{URL}/experiment", timeout=30_000)
    page.get_by_text("Extreme measurement errors", exact=True).click()
    page.get_by_text(
        "Settings changed. Run again to replace the saved result.", exact=True
    ).wait_for(timeout=30_000)
    page.get_by_text("Results", exact=True).first.click()
    page.wait_for_url(f"{URL}/results", timeout=30_000)
    page.get_by_text(
        "Settings changed. Run again to replace the saved result.", exact=True
    ).wait_for(timeout=30_000)
    summary = page.locator(".lab-run-summary").inner_text()
    assert "Randomly missing measurements" in summary
    assert "Extreme measurement errors" not in summary
    _assert_no_document_overflow(page)
    _assert_console_clean(errors, warnings)
    page.context.close()


@pytest.mark.parametrize(
    ("width", "height", "expect_columns"),
    [(1366, 768, True), (390, 844, False)],
)
def test_experiment_desktop_and_mobile_composition(
    browser: Browser, width: int, height: int, expect_columns: bool
) -> None:
    initial_viewport = (
        {"width": width, "height": height} if expect_columns else {"width": 1366, "height": 768}
    )
    page, errors, warnings = _page(browser, viewport=initial_viewport)
    _open(page)
    page.get_by_text("Experiment", exact=True).first.click()
    page.wait_for_url(f"{URL}/experiment", timeout=30_000)
    if not expect_columns:
        page.set_viewport_size({"width": width, "height": height})
    page.get_by_role("heading", name="Set up an experiment", exact=True).wait_for(timeout=30_000)
    control = page.get_by_text("Choose a data problem", exact=True).first
    glance = page.locator(".lab-glance")
    run = page.get_by_role("button", name="Run experiment", exact=True)
    control_box = control.bounding_box()
    glance_box = glance.bounding_box()
    run_box = run.bounding_box()
    assert control_box and glance_box and run_box
    if expect_columns:
        assert glance_box["x"] > control_box["x"] + 300
        assert abs(glance_box["y"] - control_box["y"]) < 24
        control_column = control.evaluate(
            "element => { const box = element.closest('[data-testid=stColumn]').getBoundingClientRect(); return {x:box.x,y:box.y,width:box.width}; }"
        )
        glance_column = glance.evaluate(
            "element => { const box = element.closest('[data-testid=stColumn]').getBoundingClientRect(); return {x:box.x,y:box.y,width:box.width}; }"
        )
        control_ratio = control_column["width"] / (control_column["width"] + glance_column["width"])
        assert 0.60 <= control_ratio <= 0.65, control_ratio
        assert abs(control_column["y"] - glance_column["y"]) <= 1
        _assert_desktop_page_alignment(page, "Set up an experiment", width)
    else:
        assert abs(glance_box["x"] - control_box["x"]) < 12
        assert glance_box["y"] > run_box["y"] + run_box["height"]
        assert run_box["width"] >= width - 48
    _assert_heading_not_clipped(page, "Set up an experiment", maximum_font_size=42)
    _assert_no_document_overflow(page)
    _assert_console_clean(errors, warnings)
    page.context.close()


def test_restore_recommended_settings_preserves_the_selected_scenario(browser: Browser) -> None:
    page, errors, warnings = _page(browser, viewport={"width": 1366, "height": 768})
    _open(page)
    page.get_by_text("Experiment", exact=True).first.click()
    page.wait_for_url(f"{URL}/experiment", timeout=30_000)
    page.get_by_text("Extreme measurement errors", exact=True).click()
    selected = page.locator("[data-testid='stRadio'] [role='radiogroup']").first.locator(
        "label:has(input:checked)"
    )
    assert "Extreme measurement errors" in selected.inner_text()
    page.get_by_role("button", name="Restore recommended settings", exact=True).click()
    page.get_by_role("heading", name="Set up an experiment", exact=True).wait_for(timeout=30_000)
    selected = page.locator("[data-testid='stRadio'] [role='radiogroup']").first.locator(
        "label:has(input:checked)"
    )
    assert "Extreme measurement errors" in selected.inner_text()
    glance = page.locator(".lab-glance")
    glance.get_by_text("Extreme measurement errors", exact=True).wait_for(timeout=30_000)
    assert "Extreme measurement errors" in glance.inner_text()
    _assert_no_document_overflow(page)
    _assert_console_clean(errors, warnings)
    page.context.close()


@pytest.mark.parametrize("color_scheme", ["light", "dark"])
@pytest.mark.parametrize(
    ("width", "height"),
    [
        (1920, 1080),
        (1600, 900),
        (1440, 1000),
        (1366, 768),
        (1024, 768),
        (390, 844),
    ],
)
def test_intentionally_light_responsive_matrix(
    browser: Browser, color_scheme: str, width: int, height: int
) -> None:
    page, errors, warnings = _page(
        browser,
        viewport={"width": width, "height": height},
        color_scheme=color_scheme,
    )
    _open(page)
    page.get_by_role(
        "heading", name="See how analysis choices behave when data go wrong", exact=True
    ).wait_for(timeout=30_000)
    background = page.locator("[data-testid='stAppViewContainer']").evaluate(
        "element => getComputedStyle(element).backgroundColor"
    )
    assert background == "rgb(255, 253, 248)"
    moment_boxes = page.locator(".lab-moment").evaluate_all(
        "elements => elements.map(element => { const box = element.getBoundingClientRect(); return {x:box.x,y:box.y,width:box.width,height:box.height}; })"
    )
    assert len(moment_boxes) == 4
    if width > 760:
        _assert_desktop_page_alignment(
            page,
            "See how analysis choices behave when data go wrong",
            width,
        )
        assert abs(moment_boxes[0]["y"] - moment_boxes[1]["y"]) <= 1
        assert abs(moment_boxes[0]["x"] - moment_boxes[2]["x"]) <= 1
        assert moment_boxes[1]["x"] > moment_boxes[0]["x"] + moment_boxes[0]["width"]
        boundary_box = page.locator(".lab-boundary").bounding_box()
        assert boundary_box
        assert abs(boundary_box["x"] - moment_boxes[2]["x"]) <= 1
        assert abs(boundary_box["width"] - moment_boxes[2]["width"]) <= 1
    else:
        assert max(box["x"] for box in moment_boxes) - min(box["x"] for box in moment_boxes) <= 1
        assert all(
            current["y"] >= previous["y"] + previous["height"] - 1
            for previous, current in pairwise(moment_boxes)
        )
        boundary_box = page.locator(".lab-boundary").bounding_box()
        assert boundary_box and boundary_box["y"] >= (
            moment_boxes[-1]["y"] + moment_boxes[-1]["height"]
        )
        assert abs(boundary_box["x"] - moment_boxes[-1]["x"]) <= 1
        assert abs(boundary_box["width"] - moment_boxes[-1]["width"]) <= 1
    _assert_no_document_overflow(page)
    _assert_console_clean(errors, warnings)
    page.context.close()


def test_zoom_equivalent_layout_targets_and_contrast(browser: Browser) -> None:
    page, errors, warnings = _page(
        browser,
        viewport={"width": 1152, "height": 800},
        device_scale_factor=1.25,
        color_scheme="dark",
    )
    _open(page)
    page.get_by_text("Experiment", exact=True).first.click()
    page.wait_for_url(f"{URL}/experiment", timeout=30_000)
    page.get_by_role("heading", name="Set up an experiment", exact=True).wait_for(timeout=30_000)
    _assert_no_document_overflow(page)
    targets = page.locator("button:visible, [data-testid='stRadio'] label:visible")
    undersized = []
    for index in range(targets.count()):
        if not targets.nth(index).inner_text().strip():
            continue
        box = targets.nth(index).bounding_box()
        if box and (box["width"] < 44 or box["height"] < 44):
            undersized.append(box)
    assert not undersized

    tokens = page.locator("[data-testid='stAppViewContainer']").evaluate(
        """element => {
          const style = getComputedStyle(element);
          return {
            paper: style.getPropertyValue('--lab-paper').trim(),
            surface: style.getPropertyValue('--lab-surface').trim(),
            ink: style.getPropertyValue('--lab-ink').trim(),
            muted: style.getPropertyValue('--lab-muted').trim(),
            coral: style.getPropertyValue('--lab-coral').trim(),
            white: style.getPropertyValue('--lab-white').trim(),
            success: style.getPropertyValue('--lab-success').trim(),
            withheld: style.getPropertyValue('--lab-withheld').trim(),
            failure: style.getPropertyValue('--lab-failure').trim(),
            methodA: style.getPropertyValue('--lab-method-a').trim(),
            methodB: style.getPropertyValue('--lab-method-b').trim(),
            methodC: style.getPropertyValue('--lab-method-c').trim(),
            methodD: style.getPropertyValue('--lab-method-d').trim()
          };
        }"""
    )
    assert _contrast(tokens["ink"], tokens["paper"]) >= 4.5
    assert _contrast(tokens["muted"], tokens["paper"]) >= 4.5
    assert _contrast(tokens["muted"], tokens["surface"]) >= 4.5
    assert _contrast(tokens["white"], tokens["coral"]) >= 4.5
    for semantic in (
        "success",
        "withheld",
        "failure",
        "methodA",
        "methodB",
        "methodC",
        "methodD",
    ):
        assert _contrast(tokens[semantic], tokens["paper"]) >= 4.5, semantic

    heading_levels = page.locator("h1:visible, h2:visible, h3:visible").evaluate_all(
        "elements => elements.map(element => Number(element.tagName.slice(1)))"
    )
    assert heading_levels and heading_levels[0] == 1
    assert all(current <= previous + 1 for previous, current in pairwise(heading_levels))
    _assert_console_clean(errors, warnings)
    page.context.close()


def test_reduced_motion_keeps_interactions_static(browser: Browser) -> None:
    page, errors, warnings = _page(
        browser,
        viewport={"width": 1366, "height": 768},
        reduced_motion="reduce",
    )
    _open(page)
    page.get_by_text("Experiment", exact=True).first.click()
    page.wait_for_url(f"{URL}/experiment", timeout=30_000)
    button = page.get_by_role("button", name="Run experiment", exact=True)
    button.wait_for(timeout=30_000)
    motion = button.evaluate(
        """element => ({
            animationDuration: getComputedStyle(element).animationDuration,
            transitionDuration: getComputedStyle(element).transitionDuration
        })"""
    )
    assert motion["animationDuration"] in ("0s", "1e-06s")
    assert motion["transitionDuration"] in ("0s", "1e-06s")
    assert page.locator("animate, animateTransform").count() == 0
    _assert_no_document_overflow(page)
    _assert_console_clean(errors, warnings)
    page.context.close()
