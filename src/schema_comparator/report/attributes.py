"""Shared column-attribute formatting for console/HTML/Excel/TUI text.

Kept as one function so `varchar(50), NULL` / `decimal(10,2), NOT NULL`
style formatting can never drift between report formats.
"""

from schema_comparator.compare.models import ColumnAttributes

# Shared "not present in this profile" cell marker for HTML/Excel grids —
# a red-cross emoji reads as "missing/failed" at a glance, unlike a plain
# em dash, without depending on any report-specific CSS/fill color.
MISSING_MARKER = "\u274c"


def format_attributes(attrs: ColumnAttributes) -> str:
    """`varchar(50), NULL` / `decimal(10,2), NOT NULL` style compact string."""
    if attrs.character_maximum_length is not None:
        size = f"({attrs.character_maximum_length})"
    elif attrs.numeric_precision is not None:
        scale = f",{attrs.numeric_scale}" if attrs.numeric_scale is not None else ""
        size = f"({attrs.numeric_precision}{scale})"
    else:
        size = ""
    nullability = "NULL" if attrs.is_nullable else "NOT NULL"
    return f"{attrs.data_type}{size}, {nullability}"
