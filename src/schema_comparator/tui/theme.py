"""Symbols, wording and colours shared by every TUI screen.

One place decides how a kind of finding looks, so the tree, the summary,
the detail card and the decision screens never drift apart. Symbols are
plain Unicode, never emoji: they render the same in Windows Terminal and in
Linux terminals.
"""

from dataclasses import dataclass

from schema_comparator.compare.models import (
    ColumnMismatch,
    DiffEntry,
    ForeignKeyMismatch,
    IndexMismatch,
    MissingColumn,
    MissingProcedure,
    MissingTable,
    PrimaryKeyMismatch,
    ProcedureMismatch,
)

OK = "✔"
FAIL = "✖"
WARN = "!"
SEPARATOR = "·"


@dataclass(frozen=True, slots=True)
class KindStyle:
    """How one kind of finding is drawn: a symbol, its names and a Rich colour."""

    symbol: str
    singular: str
    plural: str
    color: str


_GENERIC = KindStyle("•", "hallazgo", "hallazgos", "white")

KIND_STYLES: dict[type, KindStyle] = {
    MissingTable: KindStyle("✖", "tabla faltante", "tablas faltantes", "red"),
    MissingColumn: KindStyle(
        "–", "columna faltante", "columnas faltantes", "dark_orange"
    ),
    ColumnMismatch: KindStyle(
        "≠", "discrepancia de columna", "discrepancias de columnas", "yellow"
    ),
    PrimaryKeyMismatch: KindStyle(
        "≠", "discrepancia de PK", "discrepancias de PK", "cyan"
    ),
    ForeignKeyMismatch: KindStyle(
        "≠", "discrepancia de FK", "discrepancias de FK", "cyan"
    ),
    IndexMismatch: KindStyle(
        "≠", "discrepancia de índice", "discrepancias de índices", "cyan"
    ),
    MissingProcedure: KindStyle(
        "ƒ", "rutina faltante", "rutinas faltantes", "dark_orange"
    ),
    ProcedureMismatch: KindStyle("ƒ", "rutina distinta", "rutinas distintas", "yellow"),
}


def kind_style(entry: DiffEntry | type) -> KindStyle:
    """The style of a finding or of a finding class."""
    kind = entry if isinstance(entry, type) else type(entry)
    return KIND_STYLES.get(kind, _GENERIC)


def count_label(count: int, style: KindStyle) -> str:
    """`1 tabla faltante` / `3 tablas faltantes`."""
    return f"{count} {style.singular if count == 1 else style.plural}"
