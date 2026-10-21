"""Logic for schema consolidation decisions and SQL Server DDL generation (Enterprise-grade)."""

import datetime
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from schema_comparator.domain.comparison.models import (
    ColumnAttributes,
    NamedColumnAttributes,
)
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.errors import SchemaComparatorError
from schema_comparator.infrastructure.providers.sqlserver.ddl_renderer import (
    BACKUP_SCHEMA,
    SQL_SCRIPT_ENCODING,
    backup_table_name,
    extract_database_name,
    generate_ddl_for_profile,
    journal_table_name,
)


class ConsolidationNotSupportedError(SchemaComparatorError):
    """Raised when consolidation is asked for profiles of an engine other
    than SQL Server: the scripts it renders are T-SQL only."""

    @classmethod
    def for_profiles(cls, names: list[str]) -> "ConsolidationNotSupportedError":
        return cls(
            "La consolidación genera T-SQL y solo está disponible para SQL "
            f"Server; perfiles de otros motores: {', '.join(names)}."
        )


class ConsolidationDatabaseUnknownError(SchemaComparatorError):
    """Raised when a profile's connection string names no database: its
    script would have to guess which database to change."""

    @classmethod
    def for_profiles(cls, names: list[str]) -> "ConsolidationDatabaseUnknownError":
        return cls(
            "No se generó ningún script: la cadena de conexión de estos "
            "perfiles no indica la base de datos (Database= o Initial "
            f"Catalog=): {', '.join(names)}. Añádela y vuelve a generar."
        )


def unsupported_consolidation_profiles(
    profiles: list[ConnectionProfile],
) -> list[str]:
    """Names of the profiles consolidation cannot render scripts for."""
    return sorted(p.name for p in profiles if p.provider.casefold() != "sqlserver")


@dataclass(frozen=True, slots=True)
class ColumnResolution:
    """Represents a decision to consolidate a single column mismatch or missing column."""

    schema_name: str
    table_name: str
    column_name: str
    target_attributes: ColumnAttributes
    profiles_to_update: tuple[str, ...]
    is_missing_column: bool
    # What each destination had when compared; its script aborts if the
    # column differs from it. A destination left out is checked only for
    # existence.
    observed_by_profile: tuple[tuple[str, ColumnAttributes], ...] = ()
    # Value for the rows left NULL when the column becomes NOT NULL without
    # a default; without one, the script aborts if there are such rows.
    backfill_value: str | None = None
    # The user accepted truncation, rounding or failed conversions for this
    # column; otherwise the script aborts when a value would be lost.
    accept_data_loss: bool = False


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


_WINDOWS_RESERVED_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


def sanitize_profile_filename(profile_name: str) -> str:
    """Sanitize connection profile name for cross-platform filesystem use:
    path separators and invalid characters become `_`, Windows strips
    trailing dots and spaces, and reserved device names get a `_` suffix."""
    sanitized = "".join(
        "_" if c in r'\/:*?"<>|' or ord(c) < 32 else c for c in profile_name
    )
    sanitized = sanitized.strip().rstrip(". ")
    if not sanitized:
        return "profile"
    if sanitized.split(".", 1)[0].casefold() in _WINDOWS_RESERVED_NAMES:
        sanitized += "_"
    return sanitized


def assign_script_filenames(profile_names: list[str]) -> dict[str, str]:
    """Map each profile to a script file stem, unique ignoring case (Windows
    file systems are case-insensitive); later duplicates get `_1`, `_2`..."""
    assigned: dict[str, str] = {}
    used: set[str] = set()
    for profile_name in sorted(profile_names):
        base = sanitize_profile_filename(profile_name)
        stem = base
        counter = 1
        while stem.casefold() in used:
            stem = f"{base}_{counter}"
            counter += 1
        used.add(stem.casefold())
        assigned[profile_name] = stem
    return assigned


def generate_impact_report(
    resolutions: list[ColumnResolution],
    profiles_to_update: list[str],
    timestamp: datetime.datetime,
    table_resolutions: list[TableResolution] | None = None,
    table_deletions: list[TableDeletionResolution] | None = None,
    column_deletions: list[ColumnDeletionResolution] | None = None,
    script_filenames: dict[str, str] | None = None,
) -> str:
    """Generate an impact analysis report in Markdown detailing affected database objects,
    stored procedure check guidelines, and diagnostic T-SQL queries for each profile."""
    if script_filenames is None:
        script_filenames = assign_script_filenames(list(profiles_to_update))
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
        lines.append(
            f"**Archivo de Script SQL:** `{script_filenames[profile_name]}.sql`\n"
        )

        prof_table_creations = [
            t for t in (table_resolutions or []) if profile_name in t.profiles_to_update
        ]
        prof_table_deletions = [
            t for t in (table_deletions or []) if profile_name in t.profiles_to_update
        ]
        prof_col_changes = [
            c for c in resolutions if profile_name in c.profiles_to_update
        ]
        prof_col_deletions = [
            c for c in (column_deletions or []) if profile_name in c.profiles_to_update
        ]

        table_pairs = sorted(
            {
                (t.schema_name, t.table_name)
                for t in (prof_table_creations + prof_table_deletions)
            }
            | {
                (c.schema_name, c.table_name)
                for c in (prof_col_changes + prof_col_deletions)
            }
        )

        lines.append("### 1. Resumen de Cambios Estructurales")
        if prof_table_creations:
            lines.append("- **Tablas Creadas:**")
            for t in prof_table_creations:
                cols_str = ", ".join(f"`{c.name}`" for c in t.columns)
                lines.append(
                    f"  - `{t.schema_name}.{t.table_name}` (Columnas: {cols_str})"
                )
        if prof_table_deletions:
            lines.append("- **Tablas Eliminadas:**")
            for t in prof_table_deletions:
                lines.append(f"  - `{t.schema_name}.{t.table_name}`")
        if prof_col_changes:
            lines.append("- **Columnas Agregadas / Modificadas:**")
            for c in prof_col_changes:
                action = (
                    "Agregar columna" if c.is_missing_column else "Modificar atributos"
                )
                lines.append(
                    f"  - `{c.schema_name}.{c.table_name}.{c.column_name}` ({action} -> `{c.target_attributes.data_type}`)"
                )
        if prof_col_deletions:
            lines.append("- **Columnas Eliminadas:**")
            for c in prof_col_deletions:
                lines.append(f"  - `{c.schema_name}.{c.table_name}.{c.column_name}`")
        if not (
            prof_table_creations
            or prof_table_deletions
            or prof_col_changes
            or prof_col_deletions
        ):
            lines.append("- Sin cambios en este perfil.")

        lines.append("\n### 2. Qué Debemos Revisar en los Procedimientos Almacenados")
        if prof_table_deletions or prof_col_deletions:
            lines.append("- [ ] **Riesgo Crítico (Eliminación de Objetos/Columnas):**")
            lines.append(
                "  - Revisar si existen procedimientos almacenados que hagan referencia a las tablas o columnas eliminadas (`SELECT`, `INSERT`, `UPDATE`, `JOIN`)."
            )
            lines.append(
                "  - **Efecto:** Error de ejecución `Invalid column name` o `Invalid object name` al invocar la rutina."
            )
        if prof_col_changes:
            lines.append(
                "- [ ] **Riesgo Medio (Modificación de Atributos o Nuevas Columnas):**"
            )
            lines.append(
                "  - Procedimientos almacenados que utilicen `INSERT INTO [tabla] VALUES (...)` sin especificar lista explícita de columnas."
            )
            lines.append(
                "  - Procedimientos que dependan del orden ordinal de `SELECT *`."
            )
            lines.append(
                "  - Variables locales (`DECLARE @var ...`) o parámetros de procedimiento cuya precisión o longitud quede desalineada con el tipo en la BD."
            )
            lines.append(
                "- [ ] **Tiempo de ejecución (Columnas Modificadas):** el script elimina y recrea los índices, PK/UNIQUE, FK, estadísticas, DEFAULT y CHECK que dependen de cada columna modificada. Si la columna forma parte del índice clustered o de la PK, recrearlo reconstruye la tabla completa: lento y con bloqueo en tablas grandes; planifique una ventana de mantenimiento."
            )
        if prof_table_creations:
            lines.append("- [ ] **Punto de Control (Nuevas Tablas):**")
            lines.append(
                "  - Evaluar si se requieren nuevos procedimientos almacenados (CRUD/ETL) o si se deben actualizar flujos de integración existentes."
            )

        def _quote_tbl(name: str) -> str:
            return "'" + name.replace("'", "''") + "'"

        table_names_quoted = ", ".join(_quote_tbl(tbl) for _, tbl in table_pairs)
        lines.append(
            "\n### 3. Consulta T-SQL para Identificar Procedimientos Almacenados Afectados"
        )
        lines.append(
            f"Ejecute la siguiente consulta directamente en la base de datos de `{profile_name}`:"
        )
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
        lines.append(
            "Una vez ejecutados los scripts DDL, ejecute `sp_recompile` en las tablas afectadas para invalidar la caché de planes de ejecución y detectar errores de compilación en los procedimientos almacenados:"
        )
        lines.append("```sql")
        for sch, tbl in table_pairs:
            safe_sch = sch.replace("'", "''").replace("]", "]]")
            safe_tbl = tbl.replace("'", "''").replace("]", "]]")
            lines.append(f"EXEC sp_recompile '[{safe_sch}].[{safe_tbl}]';")
        lines.append("```\n")

        if prof_table_deletions or prof_col_deletions:
            backups = [
                backup_table_name(timestamp, t.table_name) for t in prof_table_deletions
            ] + [
                backup_table_name(timestamp, c.table_name, c.column_name)
                for c in prof_col_deletions
            ]
            journal = journal_table_name(timestamp)
            lines.append(f"### 5. Respaldos en el esquema `{BACKUP_SCHEMA}`")
            lines.append(
                "Antes de cada eliminación el script copia los datos (la PK y la columna"
                " al eliminar una columna) y anota en el diario la definición de cada"
                " índice y restricción que elimina. BDIFF no los borra: tras validar el"
                " cambio, elimínelos así:"
            )
            lines.append("```sql")
            for name in [*backups, journal]:
                quoted = name.replace("]", "]]")
                lines.append(f"DROP TABLE [{BACKUP_SCHEMA}].[{quoted}];")
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
    unsupported = unsupported_consolidation_profiles(profiles)
    if unsupported:
        raise ConsolidationNotSupportedError.for_profiles(unsupported)
    root_path = Path(repo_root)
    ts = timestamp or datetime.datetime.now()
    profile_map = {p.name: p for p in profiles}

    all_profiles_names = set()
    for res in resolutions:
        all_profiles_names.update(res.profiles_to_update)
    for tres in table_resolutions or []:
        all_profiles_names.update(tres.profiles_to_update)
    for deletion in table_deletions or []:
        all_profiles_names.update(deletion.profiles_to_update)
    for deletion in column_deletions or []:
        all_profiles_names.update(deletion.profiles_to_update)

    sorted_profiles = sorted(all_profiles_names)
    unknown_database = [
        name
        for name in sorted_profiles
        if name not in profile_map
        or not extract_database_name(profile_map[name].connection_string)
    ]
    if unknown_database:
        raise ConsolidationDatabaseUnknownError.for_profiles(unknown_database)

    # Render every script before writing any, so a failure leaves no
    # partial set of files behind.
    script_filenames = assign_script_filenames(sorted_profiles)
    scripts = {
        profile_name: generate_ddl_for_profile(
            resolutions,
            profile_map[profile_name],
            timestamp=ts,
            table_resolutions=table_resolutions,
            table_deletions=table_deletions,
            column_deletions=column_deletions,
        )
        for profile_name in sorted_profiles
    }

    output_dir = root_path / "scripts-db" / ts.strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)
    written_files = []
    for profile_name, ddl in scripts.items():
        file_path = output_dir / f"{script_filenames[profile_name]}.sql"
        file_path.write_text(ddl, encoding=SQL_SCRIPT_ENCODING)
        written_files.append(str(file_path.resolve()))

    if sorted_profiles:
        report_content = generate_impact_report(
            resolutions,
            sorted_profiles,
            timestamp=ts,
            table_resolutions=table_resolutions,
            table_deletions=table_deletions,
            column_deletions=column_deletions,
            script_filenames=script_filenames,
        )
        report_path = output_dir / "impact_report.md"
        report_path.write_text(report_content, encoding="utf-8")
        written_files.append(str(report_path.resolve()))

    return written_files
