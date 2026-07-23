"""Plain-text console summary of a ComparisonResult (no HTML/PDF I/O)."""

from schema_comparator.compare.models import (
    ColumnMismatch,
    ComparisonResult,
    ForeignKeyMismatch,
    IndexMismatch,
    MissingColumn,
    MissingProcedure,
    MissingTable,
    PrimaryKeyMismatch,
    ProcedureMismatch,
)
from schema_comparator.report.presentation import present_finding
from schema_comparator.report.rows import grouped_rows_by_table

_TYPE_LABELS = {
    MissingTable: "Tablas faltantes",
    MissingColumn: "Columnas faltantes",
    ColumnMismatch: "Discrepancias de columnas",
    PrimaryKeyMismatch: "Discrepancias de PK",
    ForeignKeyMismatch: "Discrepancias de FK",
    IndexMismatch: "Discrepancias de índices",
    MissingProcedure: "Procedimientos/Rutinas faltantes",
    ProcedureMismatch: "Discrepancias de procedimientos/rutinas",
}


def render_console(result: ComparisonResult) -> str:
    """Render a human-readable console summary of `result` consuming FindingView.

    Pure function of `ComparisonResult` only.
    """
    lines: list[str] = []
    lines.append("Reporte de Diferencias de Esquema - Resumen de Consola")
    lines.append(f"Perfiles comparados: {', '.join(result.compared_profiles)}")
    lines.append("")

    if not result.entries:
        lines.append("No se detectaron diferencias entre los perfiles comparados.")
        return "\n".join(lines)

    counts = {t: 0 for t in _TYPE_LABELS}
    for entry in result.entries:
        if type(entry) in counts:
            counts[type(entry)] += 1
    lines.append("Hallazgos por categoría:")
    for entry_type, label in _TYPE_LABELS.items():
        if counts[entry_type] > 0 or entry_type in (MissingTable, MissingColumn, ColumnMismatch):
            lines.append(f"  {label}: {counts[entry_type]}")
    lines.append("")

    lines.append("Detalle por objeto/tabla/procedimiento:")
    for (schema, object_name), rows_of_entries in grouped_rows_by_table(result):
        lines.append(f"  {schema}.{object_name}: {len(rows_of_entries)} hallazgo(s)")
        for entries in rows_of_entries:
            view = present_finding(entries, result.compared_profiles)
            detail_str = f" [{view.detail_name}]" if view.detail_name else ""
            profile_summary = ", ".join(f"{p}={val}" for p, val in view.cells_by_profile.items())
            lines.append(f"    - [{view.object_kind}] {view.finding_type}{detail_str}: {profile_summary}")

    return "\n".join(lines)
