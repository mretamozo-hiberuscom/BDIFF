"""Plain-text console summary of a ComparisonResult (no HTML/PDF I/O)."""

from itertools import groupby

from schema_comparator.compare.models import (
    ColumnMismatch,
    ComparisonResult,
    MissingColumn,
    MissingTable,
)
from schema_comparator.report.attributes import format_attributes

_TYPE_LABELS = {
    MissingTable: "Tablas faltantes",
    MissingColumn: "Columnas faltantes",
    ColumnMismatch: "Discrepancias de columnas",
}


def render_console(result: ComparisonResult) -> str:
    """Render a human-readable console summary of `result`.

    Pure function of `ComparisonResult` only — never receives HTML/PDF
    output, so it is independent of whether those steps succeeded.
    """
    lines: list[str] = []
    lines.append("Reporte de Diferencias de Esquema - Resumen de Consola")
    lines.append(f"Perfiles comparados: {', '.join(result.compared_profiles)}")
    lines.append("")

    if not result.entries:
        lines.append("No se detectaron diferencias entre los perfiles comparados.")
        return "\n".join(lines)

    counts = dict.fromkeys(_TYPE_LABELS, 0)
    for entry in result.entries:
        counts[type(entry)] += 1
    lines.append("Hallazgos por categoría:")
    for entry_type, label in _TYPE_LABELS.items():
        lines.append(f"  {label}: {counts[entry_type]}")
    lines.append("")

    lines.append("Detalle por tabla:")
    for (schema, table), entries in groupby(result.entries, key=lambda e: e.qualified_name):
        table_entries = list(entries)
        lines.append(f"  {schema}.{table}: {len(table_entries)} hallazgo(s)")
        for entry in table_entries:
            if isinstance(entry, MissingTable):
                lines.append(f"    - tabla faltante (de {entry.missing_from_profile})")
            elif isinstance(entry, MissingColumn):
                present = ", ".join(
                    f"{profile}={format_attributes(attrs)}"
                    for profile, attrs in entry.present_attributes
                )
                suffix = f" (presente como {present})" if present else ""
                lines.append(
                    f"    - {entry.column_name}: columna faltante "
                    f"(de {entry.missing_from_profile}){suffix}"
                )
            else:
                profiles = ", ".join(p for p, _ in entry.values_by_profile)
                lines.append(
                    f"    - {entry.column_name}: discrepancia de atributos entre {profiles}"
                )

    return "\n".join(lines)
