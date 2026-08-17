"""Capture V0.2.1 release screenshots and browser matrix evidence from the real app."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, ConsoleMessage, Page, sync_playwright

URL = os.environ.get("ISL_APP_URL", "http://127.0.0.1:8501")
MATRIX = (
    (1920, 1080, "light", 1.0),
    (1920, 1080, "dark", 1.0),
    (1600, 900, "light", 1.0),
    (1600, 900, "dark", 1.0),
    (1440, 1000, "light", 1.0),
    (1440, 1000, "dark", 1.0),
    (1366, 768, "light", 1.0),
    (1366, 768, "dark", 1.0),
    (1024, 768, "light", 1.0),
    (1024, 768, "dark", 1.0),
    (390, 844, "light", 1.0),
    (390, 844, "dark", 1.0),
    (1152, 800, "dark", 1.25),
)


def _wait_for_understand(page: Page) -> None:
    page.get_by_role(
        "heading", name="See how analysis choices behave when data go wrong", exact=True
    ).wait_for(state="visible", timeout=30_000)


def _record_console(page: Page, messages: list[dict[str, str]], *, context: str) -> None:
    def record(message: ConsoleMessage) -> None:
        location = message.location
        messages.append(
            {
                "context": context,
                "type": message.type,
                "text": message.text,
                "url": str(location.get("url", "")),
            }
        )

    page.on("console", record)


def _matrix_row(browser: Browser, case: tuple[int, int, str, float]) -> dict[str, Any]:
    width, height, color_scheme, scale = case
    context = browser.new_context(
        viewport={"width": width, "height": height},
        color_scheme=color_scheme,
        device_scale_factor=scale,
    )
    page = context.new_page()
    errors: list[str] = []

    def record(message: ConsoleMessage) -> None:
        if message.type == "error":
            errors.append(message.text)

    page.on("console", record)
    page.goto(URL, wait_until="domcontentloaded", timeout=30_000)
    _wait_for_understand(page)
    values = page.evaluate(
        """() => ({
          background: getComputedStyle(document.querySelector('[data-testid="stAppViewContainer"]')).backgroundColor,
          scrollWidth: document.documentElement.scrollWidth,
          clientWidth: document.documentElement.clientWidth
        })"""
    )
    context.close()
    return {
        "viewport": f"{width}x{height}",
        "os_preference": color_scheme,
        "device_scale_factor": scale,
        "zoom_equivalent": "125%" if scale == 1.25 else "100%",
        "computed_background": values["background"],
        "document_overflow": values["scrollWidth"] > values["clientWidth"] + 1,
        "console_errors": errors,
        "status": (
            "passed"
            if values["background"] == "rgb(255, 253, 248)"
            and values["scrollWidth"] <= values["clientWidth"] + 1
            and not errors
            else "failed"
        ),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    images = root / "docs" / "images"
    demo = root / "artifacts" / "demo"
    images.mkdir(parents=True, exist_ok=True)
    messages: list[dict[str, str]] = []
    chrome = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if not chrome.exists():
        raise RuntimeError("Local Chrome executable not found")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(chrome))
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000}, color_scheme="light"
        )
        page = context.new_page()
        _record_console(page, messages, context="release-screenshots")
        page.goto(URL, wait_until="domcontentloaded", timeout=30_000)
        _wait_for_understand(page)
        page.screenshot(path=images / "01-understand.png", full_page=False)
        page.set_viewport_size({"width": 1920, "height": 1080})
        page.wait_for_timeout(300)
        page.screenshot(path=demo / "understand-1920x1080-internal.png", full_page=False)
        page.set_viewport_size({"width": 1440, "height": 1000})
        page.wait_for_timeout(300)

        page.get_by_text("Experiment", exact=True).first.click()
        page.wait_for_url(f"{URL}/experiment", timeout=30_000)
        page.get_by_role("heading", name="Set up an experiment", exact=True).wait_for(
            timeout=30_000
        )
        page.get_by_role("button", name="Run experiment", exact=True).wait_for(timeout=30_000)
        page.get_by_text("Randomly missing measurements", exact=True).first.wait_for(timeout=30_000)
        page.wait_for_function(
            "Array.from(document.querySelectorAll('[data-testid=\"stSkeleton\"]')).every(element => element.getClientRects().length === 0)",
            timeout=30_000,
        )
        page.wait_for_timeout(500)
        page.screenshot(path=images / "02-experiment.png", full_page=False)

        page.get_by_role("button", name="Run experiment", exact=True).click()
        page.get_by_text("Experiment complete. Your results are ready.", exact=True).wait_for(
            timeout=60_000
        )
        page.get_by_role("button", name="View results", exact=True).click()
        page.wait_for_url(f"{URL}/results", timeout=30_000)
        page.get_by_role("heading", name="Method summary", exact=True).wait_for(timeout=30_000)
        page.set_viewport_size({"width": 1440, "height": 1000})
        availability = page.get_by_role(
            "heading", name="How often was usable uncertainty reported?", exact=True
        )
        availability.scroll_into_view_if_needed()
        page.locator("[data-testid='stVegaLiteChart'] svg").first.wait_for(timeout=30_000)
        page.wait_for_timeout(800)
        page.locator("section[data-testid='stMain']").evaluate("element => element.scrollTop = 0")
        page.locator(".lab-answer-rail").wait_for(timeout=30_000)
        page.wait_for_timeout(300)
        page.screenshot(path=images / "03-results-summary.png", full_page=False)

        availability.evaluate(
            """element => {
              const main = element.closest('section[data-testid="stMain"]');
              main.scrollTop += element.getBoundingClientRect().top
                - main.getBoundingClientRect().top - 64;
            }"""
        )
        page.wait_for_timeout(500)
        page.screenshot(path=images / "04-results-charts.png", full_page=False)

        page.set_viewport_size({"width": 390, "height": 844})
        page.locator("section[data-testid='stMain']").evaluate("element => element.scrollTop = 0")
        page.wait_for_timeout(400)
        page.screenshot(path=images / "07-results-mobile.png", full_page=False)

        page.set_viewport_size({"width": 1440, "height": 1000})
        page.get_by_role("button", name="Change settings", exact=True).click()
        page.wait_for_url(f"{URL}/experiment", timeout=30_000)
        page.get_by_role("heading", name="Set up an experiment", exact=True).wait_for(
            timeout=30_000
        )
        page.get_by_role("button", name="Restore recommended settings", exact=True).click()
        page.get_by_role("heading", name="Set up an experiment", exact=True).wait_for(
            timeout=30_000
        )
        page.get_by_text("Experiment complete. Your results are ready.", exact=True).wait_for(
            state="hidden", timeout=30_000
        )
        page.get_by_text("Randomly missing measurements", exact=True).first.wait_for(timeout=30_000)
        page.wait_for_function(
            "Array.from(document.querySelectorAll('[data-testid=\"stSkeleton\"]')).every(element => element.getClientRects().length === 0)",
            timeout=30_000,
        )
        page.set_viewport_size({"width": 390, "height": 844})
        page.get_by_role("button", name="Run experiment", exact=True).evaluate(
            """element => {
              const main = element.closest('section[data-testid="stMain"]');
              main.scrollTop += element.getBoundingClientRect().top
                - main.getBoundingClientRect().top - 420;
            }"""
        )
        page.wait_for_timeout(400)
        page.screenshot(path=images / "06-experiment-mobile.png", full_page=False)
        context.close()

        card_context = browser.new_context(viewport={"width": 1440, "height": 1000})
        card_page = card_context.new_page()
        _record_console(card_page, messages, context="safety-card")
        card_path = (demo / "inferential-safety-card.html").resolve()
        card_page.goto(card_path.as_uri(), wait_until="load", timeout=30_000)
        card_page.get_by_role("heading", name="Inferential Safety Card", exact=True).wait_for(
            timeout=30_000
        )
        card_page.screenshot(path=images / "05-safety-card.png", full_page=False)
        card_context.close()

        matrix = [_matrix_row(browser, case) for case in MATRIX]
        browser.close()

    (demo / "browser-console.json").write_text(
        json.dumps(messages, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (demo / "browser-matrix.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    errors = [message for message in messages if message["type"] == "error"]
    vega_warnings = [
        message
        for message in messages
        if message["type"] == "warning"
        and any(
            token in message["text"].lower()
            for token in ("empty extent", "infinite extent", "fit-y")
        )
    ]
    failed_matrix = [row for row in matrix if row["status"] != "passed"]
    print(
        f"captured=7 wide_review=1 console_errors={len(errors)} "
        f"vega_warnings={len(vega_warnings)} matrix_failures={len(failed_matrix)}"
    )
    if errors or vega_warnings or failed_matrix:
        raise RuntimeError(
            f"Browser evidence failed: errors={errors}, "
            f"vega_warnings={vega_warnings}, matrix={failed_matrix}"
        )


if __name__ == "__main__":
    main()
