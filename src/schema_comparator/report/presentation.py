"""FindingView: Normalized intermediate representation of schema findings for all renderers."""

from dataclasses import dataclass
from collections.abc import Sequence, Mapping

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
from schema_comparator.report.attributes import MISSING_MARKER, format_attributes

FINDING_TYPE_LABELS: dict[type, str] = {
    MissingTable: "Tabla faltante",
    MissingColumn: "Columna faltante",
    ColumnMismatch: "Discrepancia de atributos",
    PrimaryKeyMismatch: "Discrepancia de clave primaria",
    ForeignKeyMismatch: "Discrepancia de clave foránea",
    IndexMismatch: "Discrepancia de índice",
    MissingProcedure: "Procedimiento/Rutina faltante",
    ProcedureMismatch: "Discrepancia de procedimiento/rutina",
}


@dataclass(frozen=True, slots=True)
class FindingView:
    """Standardized finding view representation consumed by Console, HTML, Excel, PDF, and TUI."""

    schema_name: str
    object_name: str
    object_kind: str
    detail_name: str | None
    finding_type: str
    cells_by_profile: dict[str, str]

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.object_name}"


def present_finding(entries: Sequence[DiffEntry], profiles: tuple[str, ...]) -> FindingView:
    """Convert one group of sibling DiffEntry objects for an identity into a FindingView."""
    first = entries[0]
    schema_name, object_name = first.qualified_name
    finding_type = FINDING_TYPE_LABELS.get(type(first), type(first).__name__)
    cells: dict[str, str] = {}

    if isinstance(first, MissingTable):
        missing_profiles = {e.missing_from_profile for e in entries if isinstance(e, MissingTable)}
        for p in profiles:
            cells[p] = MISSING_MARKER if p in missing_profiles else "Presente"
        return FindingView(
            schema_name=schema_name,
            object_name=object_name,
            object_kind="Tabla",
            detail_name=None,
            finding_type=finding_type,
            cells_by_profile=cells,
        )

    if isinstance(first, MissingColumn):
        missing_profiles = {e.missing_from_profile for e in entries if isinstance(e, MissingColumn)}
        for p in profiles:
            if p in missing_profiles:
                cells[p] = MISSING_MARKER
            else:
                attrs = dict(first.present_attributes).get(p)
                cells[p] = format_attributes(attrs) if attrs else "Presente"
        return FindingView(
            schema_name=schema_name,
            object_name=object_name,
            object_kind="Tabla",
            detail_name=first.column_name,
            finding_type=finding_type,
            cells_by_profile=cells,
        )

    if isinstance(first, ColumnMismatch):
        values_dict = dict(first.values_by_profile)
        for p in profiles:
            attrs = values_dict.get(p)
            cells[p] = format_attributes(attrs) if attrs else MISSING_MARKER
        return FindingView(
            schema_name=schema_name,
            object_name=object_name,
            object_kind="Tabla",
            detail_name=first.column_name,
            finding_type=finding_type,
            cells_by_profile=cells,
        )

    if isinstance(first, MissingProcedure):
        missing_profiles = {e.missing_from_profile for e in entries if isinstance(e, MissingProcedure)}
        proc_dict = dict(first.present_procedures)
        sample_snap = next(iter(proc_dict.values()), None)
        kind = sample_snap.routine_type.capitalize() if sample_snap else "Procedimiento"
        for p in profiles:
            if p in missing_profiles:
                cells[p] = MISSING_MARKER
            else:
                p_snap = proc_dict.get(p)
                if p_snap:
                    params_str = ", ".join(f"{param.name} {param.data_type}" for param in p_snap.parameters) or "sin parámetros"
                    hash_str = p_snap.definition_hash[:8] if p_snap.definition_hash else ""
                    cells[p] = f"{p_snap.routine_type} ({params_str}) [{hash_str}]"
                else:
                    cells[p] = "Presente"
        return FindingView(
            schema_name=schema_name,
            object_name=object_name,
            object_kind=kind,
            detail_name=None,
            finding_type=finding_type,
            cells_by_profile=cells,
        )

    if isinstance(first, ProcedureMismatch):
        values_dict = dict(first.values_by_profile)
        sample_snap = next(iter(values_dict.values()), None)
        kind = sample_snap.routine_type.capitalize() if sample_snap else "Procedimiento"
        for p in profiles:
            p_snap = values_dict.get(p)
            if p_snap:
                params_str = ", ".join(f"{param.name} {param.data_type}" for param in p_snap.parameters) or "sin parámetros"
                hash_str = p_snap.definition_hash[:8] if p_snap.definition_hash else ""
                cells[p] = f"{p_snap.routine_type} ({params_str}) [{hash_str}]"
            else:
                cells[p] = MISSING_MARKER
        return FindingView(
            schema_name=schema_name,
            object_name=object_name,
            object_kind=kind,
            detail_name=None,
            finding_type=finding_type,
            cells_by_profile=cells,
        )

    # Generic fallback for PK, FK, Index mismatches
    for p in profiles:
        cells[p] = f"Discrepancia en {type(first).__name__}"
    return FindingView(
        schema_name=schema_name,
        object_name=object_name,
        object_kind="Objeto",
        detail_name=getattr(first, "name", None),
        finding_type=finding_type,
        cells_by_profile=cells,
    )
