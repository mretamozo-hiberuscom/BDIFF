"""T-SQL scripts that recompile routine metadata with sp_refreshsqlmodule.

BDIFF writes these files and never runs them (ADR 0005); a person reviews
and executes them. Each profile block selects its own database and owns
its summary temp table, so a profile file and the master script that
concatenates every block both run as they are.
"""

import datetime
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from schema_comparator.infrastructure.providers.sqlserver.sp_validator import (
    ModuleRefreshResult,
    RoutineIdentity,
    RoutineValidationResult,
    SignatureStatus,
)

# Placeholder result the routines screen records when a profile cannot
# connect; it is not a routine and never reaches a script.
CONNECTION_FAILURE_ROUTINE = RoutineIdentity(
    schema_name="SYSTEM", object_name="CONNECT"
)

_RULE = (
    "-- ============================================================================"
)
_PRINT_RULE = "PRINT '============================================================================';"


@dataclass(frozen=True)
class RepairScripts:
    per_profile: dict[str, str]
    master: str


def _literal(text: str) -> str:
    return text.replace("'", "''")


def _ident(text: str) -> str:
    return text.replace("]", "]]")


def _profile_block(
    profile_name: str,
    database: str | None,
    results: Sequence[RoutineValidationResult | ModuleRefreshResult],
) -> list[str]:
    if database:
        lines = [f"USE [{_ident(database)}];", "GO", ""]
    else:
        lines = [
            "-- AVISO: la cadena de conexión del perfil no indica la base de datos;",
            "-- este bloque se ejecuta en la base activa de la sesión.",
            "",
        ]
    lines += [
        "IF OBJECT_ID('tempdb..#RefreshSummary') IS NOT NULL DROP TABLE #RefreshSummary;",
        "CREATE TABLE #RefreshSummary (",
        "    Esquema NVARCHAR(128),",
        "    Objeto NVARCHAR(128),",
        "    Estado NVARCHAR(20),",
        "    ErrorDetalle NVARCHAR(MAX)",
        ");",
        "GO",
        "",
        _PRINT_RULE,
        f"PRINT N'  INICIANDO RECOMPILACIÓN DE RUTINAS EN PERFIL: {_literal(profile_name)}';",
        _PRINT_RULE,
        "GO",
        "",
    ]

    index = 0
    for result in results:
        routine = result.routine
        if routine == CONNECTION_FAILURE_ROUTINE:
            continue
        if result.signature_status != SignatureStatus.UNSIGNED:
            lines.append(f"-- OMITIDO (Firmado): {routine.qualified_name}")
            continue
        index += 1
        qname = _literal(routine.qualified_name)
        schema = _literal(routine.schema_name)
        name = _literal(routine.object_name)
        error_var = f"@err_{index}"
        lines += [
            f"PRINT N'Recompilando {qname}...';",
            "BEGIN TRY",
            f"    EXEC sys.sp_refreshsqlmodule @name = N'{qname}';",
            f"    INSERT INTO #RefreshSummary VALUES (N'{schema}', N'{name}', N'[OK]', NULL);",
            "    PRINT '  -> [OK] Recompilado correctamente.';",
            "END TRY",
            "BEGIN CATCH",
            f"    DECLARE {error_var} NVARCHAR(MAX) = ERROR_MESSAGE() + N' (Error ' + CAST(ERROR_NUMBER() AS NVARCHAR) + N')';",
            f"    INSERT INTO #RefreshSummary VALUES (N'{schema}', N'{name}', N'[ERROR]', {error_var});",
            f"    PRINT N'  -> [ERROR] en {qname}: ' + {error_var};",
            "END CATCH;",
            "GO",
            "",
        ]

    lines += [
        _PRINT_RULE,
        f"PRINT N'  RESUMEN FINAL DE RECOMPILACIÓN PARA PERFIL: {_literal(profile_name)}';",
        _PRINT_RULE,
        "SELECT ",
        "    Esquema AS [Esquema],",
        "    Objeto AS [Rutina / Objeto],",
        "    Estado AS [Resultado],",
        "    ISNULL(ErrorDetalle, '-') AS [Mensaje de Error / Diagnostico]",
        "FROM #RefreshSummary",
        "ORDER BY CASE WHEN Estado = '[ERROR]' THEN 0 ELSE 1 END, Esquema, Objeto;",
        "DROP TABLE #RefreshSummary;",
        "GO",
        "",
    ]
    return lines


def render_repair_scripts(
    results_by_profile: Mapping[
        str, Sequence[RoutineValidationResult | ModuleRefreshResult]
    ],
    database_by_profile: Mapping[str, str | None],
    timestamp: datetime.datetime,
) -> RepairScripts:
    """One script per profile plus a master script with every profile."""
    generated = f"-- Generado el {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    note = "-- NOTA: Excluye automáticamente objetos con firma digital criptográfica."
    master = [
        _RULE,
        "-- Script Maestro de Reparación y Recompilación de Procedimientos Almacenados y Vistas",
        generated,
        note,
        "-- NOTA: Cada perfil de base de datos dispone de su propio archivo en la carpeta 'repair_sps/'.",
        _RULE,
        "",
        "SET NOCOUNT ON;",
        "GO",
        "",
    ]
    per_profile: dict[str, str] = {}
    for profile_name, results in sorted(results_by_profile.items()):
        block = _profile_block(
            profile_name, database_by_profile.get(profile_name), results
        )
        per_profile[profile_name] = "\n".join(
            [
                _RULE,
                f"-- Script de Recompilación de Rutinas - Perfil / Base de Datos: {profile_name}",
                generated,
                note,
                _RULE,
                "",
                "SET NOCOUNT ON;",
                "GO",
                "",
                *block,
            ]
        )
        master += [_RULE, f"-- Perfil / Base de Datos: {profile_name}", _RULE, *block]
    return RepairScripts(per_profile=per_profile, master="\n".join(master))
