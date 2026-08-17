"""Small HTML helpers with no external-resource dependency."""

from __future__ import annotations

from html import escape
from typing import Any


def show(value: Any, *, percent: bool = False, digits: int = 3) -> str:
    if value is None:
        return "Not available"
    number = float(value)
    return f"{100 * number:.1f}%" if percent else f"{number:.{digits}f}"


def table(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> str:
    head = "".join(f"<th scope='col'>{escape(header)}</th>" for header in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(cell))}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
