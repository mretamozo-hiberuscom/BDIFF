"""FindingView: Normalized intermediate representation of schema findings for all renderers."""

from collections.abc import Sequence
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
from schema_comparator.domain.schema.models import ProcedureSnapshot
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

    @property
    def display_detail(self) -> str:
        if self.detail_name:
            return self.detail_name
        return f"({self.object_kind.lower()})"


def _format_procedure_signature(p_snap: ProcedureSnapshot) -> str:
    param_parts = []
    for param in p_snap.parameters:
        if param.is_return_value:
            param_parts.append(f"RETURN {param.data_type}")
            continue
        out_str = " OUTPUT" if param.is_output else ""
        length_str = (
            f"({param.character_maximum_length})"
            if param.character_maximum_length and param.character_maximum_length > 0
            else ""
        )
        if (
            param.numeric_precision
            and param.numeric_scale is not None
            and param.numeric_precision > 0
        ):
            length_str = f"({param.numeric_precision},{param.numeric_scale})"
        param_parts.append(f"{param.name} {param.data_type}{length_str}{out_str}")
    params_str = ", ".join(param_parts) if param_parts else "sin parámetros"
    hash_str = f" [{p_snap.definition_hash[:8]}]" if p_snap.definition_hash else ""
    r_type = p_snap.routine_type or "PROCEDURE"
    return f"{r_type} ({params_str}){hash_str}"


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
        proc_dict: dict[str, ProcedureSnapshot] = {}
        for e in entries:
            if isinstance(e, MissingProcedure):
                proc_dict.update(dict(e.present_procedures))
        sample_snap = next(iter(proc_dict.values()), None)
        raw_kind = sample_snap.routine_type if sample_snap and sample_snap.routine_type else "PROCEDURE"
        kind = raw_kind.capitalize()
        for p in profiles:
            if p in missing_profiles:
                cells[p] = MISSING_MARKER
            else:
                p_snap = proc_dict.get(p)
                if p_snap:
                    cells[p] = _format_procedure_signature(p_snap)
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
        raw_kind = sample_snap.routine_type if sample_snap and sample_snap.routine_type else "PROCEDURE"
        kind = raw_kind.capitalize()
        for p in profiles:
            p_snap = values_dict.get(p)
            if p_snap:
                cells[p] = _format_procedure_signature(p_snap)
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
