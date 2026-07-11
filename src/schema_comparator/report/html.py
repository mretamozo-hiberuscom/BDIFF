"""Render a self-contained HTML schema-drift report from a ComparisonResult."""

from jinja2 import Environment, PackageLoader, select_autoescape

from schema_comparator.compare.models import (
    ColumnMismatch,
    ComparisonResult,
    DiffEntry,
    MissingColumn,
    MissingTable,
)
from schema_comparator.report.attributes import MISSING_MARKER, format_attributes
from schema_comparator.report.rows import grouped_rows_by_table

_env = Environment(
    loader=PackageLoader("schema_comparator.report", "templates"),
    autoescape=select_autoescape(["html", "jinja"]),
)
_env.filters["lower_kebab"] = lambda value: "".join(
    "-" + c.lower() if c.isupper() else c for c in value
).lstrip("-")

def _read_pico_css() -> str:
    source, _, _ = _env.loader.get_source(_env, "pico.min.css")
    return source


_PICO_CSS_INLINE = _read_pico_css()


def _row_for_group(entries: list[DiffEntry], profiles: tuple[str, ...]) -> dict:
    """Build a {profile_name: cell_value_or_None} dict, plus row metadata,
    for one *group* of same-identity diff entries — typically one entry
    per profile the table/column is missing from, merged into a single
    row with one cell marked per missing profile."""
    first = entries[0]
    cells: dict[str, dict | None] = dict.fromkeys(profiles)
    row_label = None
    if isinstance(first, MissingTable):
        for entry in entries:
            cells[entry.missing_from_profile] = {"kind": "missing", "text": MISSING_MARKER}
    elif isinstance(first, MissingColumn):
        row_label = first.column_name
        for entry in entries:
            cells[entry.missing_from_profile] = {"kind": "missing", "text": MISSING_MARKER}
            for profile, attrs in entry.present_attributes:
                cells[profile] = {"kind": "value", "text": format_attributes(attrs)}
    elif isinstance(first, ColumnMismatch):
        row_label = first.column_name
        for profile, attrs in first.values_by_profile:
            cells[profile] = {"kind": "value", "text": format_attributes(attrs)}
    return {
        "diff_type": type(first).__name__,
        "column_name": row_label,
        "cells": cells,
    }


def build_context(result: ComparisonResult) -> dict:
    """Build the pure dict-shaped template context for `result` (no Jinja2
    involved). `result.entries` is consumed strictly in engine order — it
    is grouped via `grouped_rows_by_table` for display (by table, then by
    same-identity row), never re-sorted."""
    groups = []
    for (schema, table), rows_of_entries in grouped_rows_by_table(result):
        rows = [_row_for_group(group, result.compared_profiles) for group in rows_of_entries]
        groups.append({"schema_name": schema, "table_name": table, "rows": rows})
    return {
        "compared_profiles": result.compared_profiles,
        "groups": groups,
        "has_findings": bool(result.entries),
    }


def render_html(result: ComparisonResult) -> str:
    """Render `result` to a single self-contained HTML string (inline
    CSS only, no external asset loads)."""
    template = _env.get_template("report.html.jinja")
    return template.render(pico_css_inline=_PICO_CSS_INLINE, **build_context(result))
