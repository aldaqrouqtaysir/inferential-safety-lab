from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).parents[2]


def test_v020_uses_bounded_three_page_navigation_and_light_theme() -> None:
    app = (ROOT / "src" / "inferential_safety_lab" / "ui" / "app.py").read_text(encoding="utf-8")
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'url_path=""' in app and "default=True" in app
    assert 'url_path="experiment"' in app
    assert 'url_path="results"' in app
    assert 'position="top"' in app
    assert 'title="Understand"' in app
    assert 'title="Experiment"' in app
    assert 'title="Results"' in app
    assert "prefers-color-scheme:dark" not in app.replace(" ", "")
    assert 'toolbarMode = "minimal"' in config


def test_primary_journey_contains_required_plain_language_and_hides_technical_terms() -> None:
    app = (ROOT / "src" / "inferential_safety_lab" / "ui" / "app.py").read_text(encoding="utf-8")
    for required in (
        "See how analysis choices behave when data go wrong",
        "Run a synthetic experiment with a known answer",
        "Randomly missing measurements",
        "Missingness linked to observed outcomes",
        "Extreme measurement errors",
        "Settings changed. Run again to replace the saved result.",
        "No results yet. Set up and run an experiment to see the comparison.",
        "Change settings",
        "Start another experiment",
        "Inferential Safety Card",
    ):
        assert required in app
    primary_results = app.split("def _render_results", maxsplit=1)[1].split(
        'with st.expander("Technical details and exact records"', maxsplit=1
    )[0]
    assert "HC3" not in primary_results
    assert "valid-and-cover" not in primary_results
    assert "replay_hash" not in primary_results


def test_safety_card_is_not_generated_or_encoded_until_requested() -> None:
    app = (ROOT / "src" / "inferential_safety_lab" / "ui" / "app.py").read_text(encoding="utf-8")
    results_source = app.split("def _render_results", maxsplit=1)[1]
    request_position = results_source.index("if prepare or preview:")
    render_position = results_source.index("_ensure_safety_card(run)")
    encode_position = results_source.index("base64.b64encode")
    assert request_position < render_position < encode_position


def test_v021_presentation_contract_is_bounded_and_semantic() -> None:
    app = (ROOT / "src" / "inferential_safety_lab" / "ui" / "app.py").read_text(encoding="utf-8")
    theme = (ROOT / "src" / "inferential_safety_lab" / "reporting" / "theme.py").read_text(
        encoding="utf-8"
    )
    version = (ROOT / "src" / "inferential_safety_lab" / "__init__.py").read_text(encoding="utf-8")
    for semantic in (
        "PAPER",
        "INK",
        "MUTED",
        "RULE",
        "PRIMARY_ACTION",
        "KNOWN_ANSWER",
        "METHOD_IDENTITIES",
        "SUCCESS",
        "WITHHELD",
        "FAILURE",
        "TECHNICAL_SURFACE",
        "FONT_DISPLAY",
        "FONT_SANS",
    ):
        assert semantic in theme
    for visual_contract in (
        "lab-explainer",
        "lab-glance",
        "lab-scenario-preview",
        "lab-answer-rail",
        "lab-evidence",
        "Inferential Safety Lab",
        "prefers-reduced-motion:reduce",
    ):
        assert visual_contract in app
    assert "linear-gradient" not in app
    assert "radial-gradient" not in app
    assert '__version__ = "0.2.1"' in version
