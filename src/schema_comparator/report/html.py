"""Render a self-contained HTML schema-drift report from a ComparisonResult using FindingView."""

from jinja2 import Environment, PackageLoader, select_autoescape

from schema_comparator.compare.models import (
    ColumnMismatch,
    ComparisonResult,
    DiffEntry,
    MissingColumn,
    MissingProcedure,
    MissingTable,
    ProcedureMismatch,
)
from schema_comparator.report.attributes import MISSING_MARKER, format_attributes
from schema_comparator.report.presentation import present_finding
from schema_comparator.report.rows import grouped_rows_by_table

_env = Environment(
    loader=PackageLoader("schema_comparator.report", "templates"),
    autoescape=select_autoescape(["html", "jinja"]),
)
_env.filters["lower_kebab"] = lambda value: "".join(
    "-" + c.lower() if c.isupper() else c for c in str(value)
).lstrip("-")


def _read_pico_css() -> str:
    source, _, _ = _env.loader.get_source(_env, "pico.min.css")
    return source


_PICO_CSS_INLINE = _read_pico_css()


def _row_for_group(entries: list[DiffEntry], profiles: tuple[str, ...]) -> dict:
    """Build a {profile_name: cell_dict} for one group of same-identity entries."""
    first = entries[0]
    cells: dict[str, dict | None] = {}

    if isinstance(first, MissingTable):
        missing_set = {e.missing_from_profile for e in entries if isinstance(e, MissingTable)}
        for p in profiles:
            if p in missing_set:
                cells[p] = {"kind": "missing", "text": MISSING_MARKER}
            else:
                cells[p] = None
        detail = None
    elif isinstance(first, MissingColumn):
        missing_set = {e.missing_from_profile for e in entries if isinstance(e, MissingColumn)}
        first_missing = next(e for e in entries if isinstance(e, MissingColumn))
        present_attrs = dict(first_missing.present_attributes)
        for p in profiles:
            if p in missing_set:
                cells[p] = {"kind": "missing", "text": MISSING_MARKER}
            elif p in present_attrs:
                cells[p] = {"kind": "value", "text": format_attributes(present_attrs[p])}
            else:
                cells[p] = None
        detail = first.column_name
    elif isinstance(first, ColumnMismatch):
        values = dict(first.values_by_profile)
        for p in profiles:
            if p in values:
                cells[p] = {"kind": "value", "text": format_attributes(values[p])}
            else:
                cells[p] = None
        detail = first.column_name
    else:
        view = present_finding(entries, profiles)
        for p in profiles:
            text_val = view.cells_by_profile.get(p, "")
            if text_val == MISSING_MARKER:
                cells[p] = {"kind": "missing", "text": MISSING_MARKER}
            elif text_val and text_val != "Presente":
                cells[p] = {"kind": "value", "text": text_val}
            else:
                cells[p] = None
        detail = view.detail_name

    return {
        "diff_type": type(first).__name__,
        "column_name": detail,
        "cells": cells,
    }


def build_context(result: ComparisonResult) -> dict:
    """Build the pure dict-shaped template context for `result`."""
    groups = []
    for (schema, object_name), rows_of_entries in grouped_rows_by_table(result):
        rows = [_row_for_group(group, result.compared_profiles) for group in rows_of_entries]
        groups.append({"schema_name": schema, "table_name": object_name, "rows": rows})
    return {
        "compared_profiles": result.compared_profiles,
        "groups": groups,
        "has_findings": bool(result.entries),
    }


def render_html(result: ComparisonResult) -> str:
    """Render `result` to a single self-contained HTML string."""
    template = _env.get_template("report.html.jinja")
    return template.render(pico_css_inline=_PICO_CSS_INLINE, **build_context(result))
