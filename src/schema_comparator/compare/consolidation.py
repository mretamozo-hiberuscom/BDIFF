"""Logic for schema consolidation decisions and SQL Server DDL generation (Enterprise-grade)."""

import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from schema_comparator.domain.comparison.models import ColumnAttributes, NamedColumnAttributes
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.infrastructure.providers.sqlserver.ddl_renderer import (
    extract_database_name,
    format_sql_column_definition,
    generate_ddl_for_profile,
)


@dataclass(frozen=True, slots=True)
class ColumnResolution:
    """Represents a decision to consolidate a single column mismatch or missing column."""

    schema_name: str
    table_name: str
    column_name: str
    target_attributes: ColumnAttributes
    profiles_to_update: tuple[str, ...]
    is_missing_column: bool


@dataclass(frozen=True, slots=True)
class TableResolution:
    """Represents a decision to create a missing table with the full column definition."""

    schema_name: str
    table_name: str
    columns: tuple[NamedColumnAttributes, ...]
    profiles_to_update: tuple[str, ...]


class TableAction(str, Enum):
    """Actions available for a table-level consolidation decision."""

    DROP = "drop"


@dataclass(frozen=True, slots=True)
class TableDeletionResolution:
    """Represents a decision to remove a table from selected profiles."""

    schema_name: str
    table_name: str
    profiles_to_update: tuple[str, ...]


class ColumnAction(str, Enum):
    """Actions available for a column-level consolidation decision."""

    DROP = "drop"


@dataclass(frozen=True, slots=True)
class ColumnDeletionResolution:
    """Represents a decision to remove a column from selected profiles."""

    schema_name: str
    table_name: str
    column_name: str
    profiles_to_update: tuple[str, ...]


def sanitize_profile_filename(profile_name: str) -> str:
    """Sanitize connection profile name for cross-platform filesystem use."""
    name = Path(profile_name).name
    sanitized = "".join(c if c not in r'\/:*?"<>|' else "_" for c in name).strip()
    return sanitized or "profile"


def generate_impact_report(
    resolutions: list[ColumnResolution],
    profiles_to_update: list[str],
    timestamp: datetime.datetime,
    table_resolutions: list[TableResolution] | None = None,
    table_deletions: list[TableDeletionResolution] | None = None,
    column_deletions: list[ColumnDeletionResolution] | None = None,
) -> str:
    """Generate an impact analysis report in Markdown detailing affected database objects,
    stored procedure check guidelines, and diagnostic T-SQL queries for each profile."""
    ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# Reporte de Impacto en Procedimientos Almacenados y Objetos DB",
        "",
        f"**Fecha de generación:** {ts_str}",
        "",
        "Este reporte analiza las modificaciones DDL generadas para cada base de datos / perfil,",
        "e identifica los procedimientos almacenados, vistas y triggers potencialmente afectados.",
        "",
        "---",
        "",
    ]

    for profile_name in sorted(profiles_to_update):
        lines.append(f"## Perfil / Base de Datos: `{profile_name}`")
        lines.append(f"**Archivo de Script SQL:** `{sanitize_profile_filename(profile_name)}.sql`\n")

        prof_table_creations = [t for t in (table_resolutions or []) if profile_name in t.profiles_to_update]
        prof_table_deletions = [t for t in (table_deletions or []) if profile_name in t.profiles_to_update]
        prof_col_changes = [c for c in resolutions if profile_name in c.profiles_to_update]
        prof_col_deletions = [c for c in (column_deletions or []) if profile_name in c.profiles_to_update]

        table_pairs = sorted({
            (t.schema_name, t.table_name)
            for t in (prof_table_creations + prof_table_deletions)
        } | {
            (c.schema_name, c.table_name)
            for c in (prof_col_changes + prof_col_deletions)
        })

        lines.append("### 1. Resumen de Cambios Estructurales")
        if prof_table_creations:
            lines.append("- **Tablas Creadas:**")
            for t in prof_table_creations:
                cols_str = ", ".join(f"`{c.name}`" for c in t.columns)
                lines.append(f"  - `{t.schema_name}.{t.table_name}` (Columnas: {cols_str})")
        if prof_table_deletions:
            lines.append("- **Tablas Eliminadas:**")
            for t in prof_table_deletions:
                lines.append(f"  - `{t.schema_name}.{t.table_name}`")
        if prof_col_changes:
            lines.append("- **Columnas Agregadas / Modificadas:**")
            for c in prof_col_changes:
                action = "Agregar columna" if c.is_missing_column else "Modificar atributos"
                lines.append(f"  - `{c.schema_name}.{c.table_name}.{c.column_name}` ({action} -> `{c.target_attributes.data_type}`)")
        if prof_col_deletions:
            lines.append("- **Columnas Eliminadas:**")
            for c in prof_col_deletions:
                lines.append(f"  - `{c.schema_name}.{c.table_name}.{c.column_name}`")
        if not (prof_table_creations or prof_table_deletions or prof_col_changes or prof_col_deletions):
            lines.append("- Sin cambios en este perfil.")

        lines.append("\n### 2. Qué Debemos Revisar en los Procedimientos Almacenados")
        if prof_table_deletions or prof_col_deletions:
            lines.append("- [ ] **Riesgo Crítico (Eliminación de Objetos/Columnas):**")
            lines.append("  - Revisar si existen procedimientos almacenados que hagan referencia a las tablas o columnas eliminadas (`SELECT`, `INSERT`, `UPDATE`, `JOIN`).")
            lines.append("  - **Efecto:** Error de ejecución `Invalid column name` o `Invalid object name` al invocar la rutina.")
        if prof_col_changes:
            lines.append("- [ ] **Riesgo Medio (Modificación de Atributos o Nuevas Columnas):**")
            lines.append("  - Procedimientos almacenados que utilicen `INSERT INTO [tabla] VALUES (...)` sin especificar lista explícita de columnas.")
            lines.append("  - Procedimientos que dependan del orden ordinal de `SELECT *`.")
            lines.append("  - Variables locales (`DECLARE @var ...`) o parámetros de procedimiento cuya precisión o longitud quede desalineada con el tipo en la BD.")
        if prof_table_creations:
            lines.append("- [ ] **Punto de Control (Nuevas Tablas):**")
            lines.append("  - Evaluar si se requieren nuevos procedimientos almacenados (CRUD/ETL) o si se deben actualizar flujos de integración existentes.")

        table_names_quoted = ", ".join(f"'{tbl.replace('\'', '\'\'')}'" for _, tbl in table_pairs)
        lines.append("\n### 3. Consulta T-SQL para Identificar Procedimientos Almacenados Afectados")
        lines.append(f"Ejecute la siguiente consulta directamente en la base de datos de `{profile_name}`:")
        lines.append("```sql")
        lines.append("SELECT DISTINCT")
        lines.append("    SCHEMA_NAME(o.schema_id) AS esquema,")
        lines.append("    o.name AS procedimiento_o_objeto_afectado,")
        lines.append("    o.type_desc AS tipo_objeto,")
        lines.append("    d.referenced_entity_name AS entidad_referenciada")
        lines.append("FROM sys.sql_expression_dependencies d")
        lines.append("JOIN sys.objects o ON d.referencing_id = o.object_id")
        if table_names_quoted:
            lines.append(f"WHERE d.referenced_entity_name IN ({table_names_quoted})")
            lines.append("  AND o.type IN ('P', 'FN', 'IF', 'TF', 'TR', 'V')")
        else:
            lines.append("WHERE o.type IN ('P', 'FN', 'IF', 'TF', 'TR', 'V')")
        lines.append("ORDER BY esquema, procedimiento_o_objeto_afectado;")
        lines.append("```\n")

        lines.append("### 4. Recomendación de Recompilación")
        lines.append("Una vez ejecutados los scripts DDL, ejecute `sp_recompile` en las tablas afectadas para invalidar la caché de planes de ejecución y detectar errores de compilación en los procedimientos almacenados:")
        lines.append("```sql")
        for sch, tbl in table_pairs:
            safe_sch = sch.replace("'", "''").replace("]", "]]")
            safe_tbl = tbl.replace("'", "''").replace("]", "]]")
            lines.append(f"EXEC sp_recompile '[{safe_sch}].[{safe_tbl}]';")
        lines.append("```\n")
        lines.append("---\n")

    return "\n".join(lines)


def write_sql_scripts(
    resolutions: list[ColumnResolution],
    repo_root: str | Path,
    profiles: list[ConnectionProfile],
    timestamp: datetime.datetime | None = None,
    table_resolutions: list[TableResolution] | None = None,
    table_deletions: list[TableDeletionResolution] | None = None,
    column_deletions: list[ColumnDeletionResolution] | None = None,
) -> list[str]:
    """Create a timestamped directory inside 'scripts-db' and write transactional DDL files and impact report for all affected profiles."""
    root_path = Path(repo_root)
    ts = timestamp or datetime.datetime.now()
    folder_name = ts.strftime("%Y%m%d_%H%M%S")
    output_dir = root_path / "scripts-db" / folder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    profile_map = {p.name: p for p in profiles}
    
    all_profiles_names = set()
    for res in resolutions:
        all_profiles_names.update(res.profiles_to_update)
    for tres in (table_resolutions or []):
        all_profiles_names.update(tres.profiles_to_update)
    for deletion in (table_deletions or []):
        all_profiles_names.update(deletion.profiles_to_update)
    for deletion in (column_deletions or []):
        all_profiles_names.update(deletion.profiles_to_update)
        
    written_files = []
    used_filenames: set[str] = set()
    sorted_profiles = sorted(all_profiles_names)
    for profile_name in sorted_profiles:
        profile = profile_map.get(
            profile_name, 
            ConnectionProfile(name=profile_name, connection_string=f"Database={profile_name};")
        )
        ddl = generate_ddl_for_profile(
            resolutions,
            profile,
            timestamp=ts,
            table_resolutions=table_resolutions,
            table_deletions=table_deletions,
            column_deletions=column_deletions,
        )
        base_filename = sanitize_profile_filename(profile_name)
        safe_profile = base_filename
        counter = 1
        while safe_profile in used_filenames:
            safe_profile = f"{base_filename}_{counter}"
            counter += 1
        used_filenames.add(safe_profile)

        file_path = output_dir / f"{safe_profile}.sql"
        file_path.write_text(ddl, encoding="utf-8")
        written_files.append(str(file_path.resolve()))
        
    if sorted_profiles:
        report_content = generate_impact_report(
            resolutions,
            sorted_profiles,
            timestamp=ts,
            table_resolutions=table_resolutions,
            table_deletions=table_deletions,
            column_deletions=column_deletions,
        )
        report_path = output_dir / "impact_report.md"
        report_path.write_text(report_content, encoding="utf-8")
        written_files.append(str(report_path.resolve()))

    return written_files
