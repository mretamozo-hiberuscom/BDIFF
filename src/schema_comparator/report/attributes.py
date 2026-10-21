"""Shared column-attribute formatting for console/HTML/Excel/TUI text.

Kept as one function so `varchar(50), NULL` / `decimal(10,2), NOT NULL`
style formatting can never drift between report formats.
"""

import re

from schema_comparator.compare.models import ColumnAttributes

# Shared "not present in this profile" cell marker for HTML/Excel grids —
# a red-cross emoji reads as "missing/failed" at a glance, unlike a plain
# em dash, without depending on any report-specific CSS/fill color.
MISSING_MARKER = "\u274c"

_NON_PARAMETRIC_TYPES = {
    "int",
    "bigint",
    "smallint",
    "tinyint",
    "bit",
    "date",
    "datetime",
    "smalldatetime",
    "real",
    "money",
    "smallmoney",
    "uniqueidentifier",
    "xml",
    "text",
    "ntext",
    "image",
}


def format_attributes(attrs: ColumnAttributes) -> str:
    """`varchar(50), NULL` / `decimal(10,2), NOT NULL` style compact string."""
    clean_type = re.sub(r"\s*\(.*\)", "", attrs.data_type).strip()
    data_type_lower = clean_type.lower()

    if (
        attrs.character_maximum_length is not None
        and data_type_lower not in _NON_PARAMETRIC_TYPES
    ):
        size = f"({attrs.character_maximum_length})"
    elif attrs.numeric_precision is not None and data_type_lower in (
        "decimal",
        "numeric",
    ):
        scale = f",{attrs.numeric_scale}" if attrs.numeric_scale is not None else ""
        size = f"({attrs.numeric_precision}{scale})"
    elif attrs.datetime_precision is not None:
        size = f"({attrs.datetime_precision})"
    else:
        size = ""
    parts = [f"{clean_type}{size}", "NULL" if attrs.is_nullable else "NOT NULL"]
    # The rest only when set, so two variants never print the same.
    if attrs.is_identity:
        parts.append("IDENTITY")
    if attrs.default_expression:
        parts.append(f"DEFAULT {attrs.default_expression}")
    if attrs.collation:
        parts.append(f"COLLATE {attrs.collation}")
    return ", ".join(parts)
