"""Shared presentation tokens for the app, charts, and Safety Card."""

from __future__ import annotations

PAPER = "#FFFDF8"
INK = "#17324D"
MUTED = "#526777"
RULE = "#CFC6B8"
PRIMARY_ACTION = "#A64237"
KNOWN_ANSWER = PRIMARY_ACTION
SUCCESS = "#28674F"
WITHHELD = "#7A4D0C"
FAILURE = "#8F342D"
TECHNICAL_SURFACE = "#E8E0D3"
SURFACE = "#F3EEE4"
WHITE = "#FFFFFF"

METHOD_IDENTITIES: tuple[tuple[str, str], ...] = (
    ("A", "#2F6F8F"),
    ("B", "#356B5A"),
    ("C", "#675779"),
    ("D", "#78602E"),
)

FONT_DISPLAY = '"Iowan Old Style", "Palatino Linotype", "Book Antiqua", Georgia, serif'
FONT_SANS = '"Aptos", "Segoe UI", system-ui, sans-serif'
FONT_MONO = '"Cascadia Mono", "SFMono-Regular", Consolas, monospace'

# Backward-compatible aliases for presentation-only callers.
CORAL = PRIMARY_ACTION
CORAL_SOFT = "#C85A4D"
BLUE = METHOD_IDENTITIES[0][1]
GREEN = SUCCESS
WARNING = WITHHELD
GRID = RULE
SURFACE_STRONG = TECHNICAL_SURFACE


def method_identity(index: int) -> tuple[str, str]:
    """Return the stable visible code and color for a method's run-order position."""

    return METHOD_IDENTITIES[index % len(METHOD_IDENTITIES)]


def vega_config() -> dict[str, object]:
    """Return shared deterministic Vega-Lite typography and color settings."""

    return {
        "background": PAPER,
        "font": "Aptos, Segoe UI, sans-serif",
        "view": {"stroke": None},
        "axis": {
            "domainColor": GRID,
            "gridColor": SURFACE_STRONG,
            "labelColor": INK,
            "titleColor": INK,
            "labelFontSize": 12,
            "titleFontSize": 13,
        },
        "legend": {
            "labelColor": INK,
            "titleColor": INK,
            "labelFontSize": 12,
        },
    }
