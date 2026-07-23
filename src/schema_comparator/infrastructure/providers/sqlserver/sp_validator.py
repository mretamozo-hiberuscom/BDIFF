"""SP dependency checking, read-only routine validation, and signature-safe module refresh."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
import re
import pyodbc

from schema_comparator.domain.errors import (
    ModuleEnumerationError,
    SignatureInspectionError,
)


def clean_sql_error_message(err: Exception | str | None) -> str:
    """Clean verbose pyodbc/ODBC exception strings into concise, human-readable diagnostics."""
    if err is None:
        return "Error desconocido"
    raw = str(err)
    if isinstance(err, Exception) and hasattr(err, "args") and err.args:
        for arg in err.args:
            if isinstance(arg, str) and "[SQL Server]" in arg:
                raw = arg
                break
            elif isinstance(arg, str) and len(arg) > len(raw):
                raw = arg

    if "[SQL Server]" in raw:
        raw = raw.split("[SQL Server]")[-1].strip()

    raw = re.sub(r"\s*\((?:SQLExecDirectW|SQLExecute|SQLPrepare)\)", "", raw).strip()
    raw = re.sub(r'["\']\)?$', "", raw).strip()
    raw = re.sub(r"\((\d+)\)$", r"(Error \1)", raw)

    return raw if raw else str(err)


@dataclass(frozen=True, slots=True)
class RoutineIdentity:
    """Qualified identity of a database routine or view."""

    schema_name: str
    object_name: str

    @property
    def qualified_name(self) -> str:
        safe_sch = self.schema_name.replace("]", "]]")
        safe_obj = self.object_name.replace("]", "]]")
        return f"[{safe_sch}].[{safe_obj}]"


@dataclass(frozen=True, slots=True)
class DependentObject:
    """A database routine or view that depends on a table being consolidated."""

    schema_name: str
    object_name: str
    object_type: str
    referenced_table: str


class SignatureStatus(str, Enum):
    SIGNED = "signed"
    UNSIGNED = "unsigned"
    UNKNOWN = "unknown"


class RoutineValidationStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True, slots=True)
class RoutineValidationResult:
    """The outcome of validating routine dependencies without mutating metadata."""

    routine: RoutineIdentity
    status: RoutineValidationStatus
    signature_status: SignatureStatus
    error_message: str | None = None
    broken_entities: tuple[str, ...] = ()

    @property
    def is_success(self) -> bool:
        return self.status == RoutineValidationStatus.VALID


@dataclass(frozen=True, slots=True)
class ModuleRefreshResult:
    """The outcome of executing sp_refreshsqlmodule on a procedure or view."""

    routine: RoutineIdentity
    is_success: bool
    signature_status: SignatureStatus
    error_message: str | None = None

    @classmethod
    def success(
        cls,
        routine: RoutineIdentity,
        signature_status: SignatureStatus = SignatureStatus.UNSIGNED,
    ) -> "ModuleRefreshResult":
        return cls(
            routine=routine,
            is_success=True,
            signature_status=signature_status,
        )

    @classmethod
    def failure(
        cls,
        routine: RoutineIdentity,
        error_message: str,
        signature_status: SignatureStatus = SignatureStatus.UNSIGNED,
    ) -> "ModuleRefreshResult":
        return cls(
            routine=routine,
            is_success=False,
            signature_status=signature_status,
            error_message=error_message,
        )


def find_dependent_objects(
    conn: pyodbc.Connection,
    table_names: set[str],
) -> tuple[DependentObject, ...]:
    """Query sys.sql_expression_dependencies for routines depending on table_names."""
    if not table_names:
        return ()

    table_list = list(table_names)
    results: list[DependentObject] = []
    cursor = conn.cursor()

    chunk_size = 1000
    try:
        for i in range(0, len(table_list), chunk_size):
            chunk = table_list[i : i + chunk_size]
            placeholders = ", ".join("?" for _ in chunk)
            sql = f"""
            SELECT DISTINCT
                s.name AS schema_name,
                o.name AS object_name,
                o.type_desc AS object_type,
                d.referenced_entity_name AS referenced_table
            FROM sys.sql_expression_dependencies d
            JOIN sys.objects o ON d.referencing_id = o.object_id
            JOIN sys.schemas s ON o.schema_id = s.schema_id
            WHERE d.referenced_entity_name IN ({placeholders})
              AND o.type IN ('P', 'FN', 'IF', 'TF', 'TR', 'V')
            ORDER BY schema_name, object_name
            """.strip()

            cursor.execute(sql, chunk)
            for sch, obj, obj_type, ref_tbl in cursor.fetchall():
                results.append(
                    DependentObject(
                        schema_name=sch,
                        object_name=obj,
                        object_type=obj_type,
                        referenced_table=ref_tbl,
                    )
                )
    except pyodbc.Error as exc:
        raise ModuleEnumerationError(
            f"Error enumerando dependencias para las tablas: {table_names}"
        ) from exc
    finally:
        cursor.close()

    return tuple(results)


def get_signature_status(
    conn: pyodbc.Connection, schema_name: str, object_name: str
) -> SignatureStatus:
    """Check sys.crypt_properties for cryptographic signatures on an object."""
    sql = """
    SELECT COUNT(*)
    FROM sys.crypt_properties cp
    JOIN sys.objects o ON cp.major_id = o.object_id
    JOIN sys.schemas s ON o.schema_id = s.schema_id
    WHERE s.name = ? AND o.name = ?
    """
    cursor = conn.cursor()
    try:
        cursor.execute(sql, (schema_name, object_name))
        row = cursor.fetchone()
        if row and row[0] > 0:
            return SignatureStatus.SIGNED
        return SignatureStatus.UNSIGNED
    except pyodbc.Error as exc:
        raise SignatureInspectionError(
            f"No se pudo comprobar la firma de [{schema_name}].[{object_name}]"
        ) from exc
    finally:
        cursor.close()


def is_object_signed(
    conn: pyodbc.Connection, schema_name: str, object_name: str
) -> bool:
    """Fail-closed helper checking if an object is signed."""
    try:
        return (
            get_signature_status(conn, schema_name, object_name)
            != SignatureStatus.UNSIGNED
        )
    except SignatureInspectionError:
        return True


def enumerate_routines(conn: pyodbc.Connection) -> tuple[RoutineIdentity, ...]:
    """Enumerate all user procedures, functions, and views in the database."""
    sql = """
    SELECT s.name, o.name
    FROM sys.objects o
    JOIN sys.schemas s ON o.schema_id = s.schema_id
    WHERE o.type IN ('P', 'FN', 'IF', 'TF', 'V') AND o.is_ms_shipped = 0
    ORDER BY s.name, o.name
    """
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        rows = cursor.fetchall()
        return tuple(RoutineIdentity(schema_name=r[0], object_name=r[1]) for r in rows)
    except pyodbc.Error as exc:
        raise ModuleEnumerationError(
            "Error enumerando rutinas de la base de datos"
        ) from exc
    finally:
        cursor.close()


def validate_routines_read_only(
    conn: pyodbc.Connection,
    objects_to_validate: Sequence[RoutineIdentity],
) -> tuple[RoutineValidationResult, ...]:
    """Read-only dependency resolution using sys.dm_sql_referenced_entities without mutating metadata."""
    if not objects_to_validate:
        return ()

    cursor = conn.cursor()
    results: list[RoutineValidationResult] = []

    for target in objects_to_validate:
        try:
            signed_status = get_signature_status(
                conn, target.schema_name, target.object_name
            )
        except SignatureInspectionError as exc:
            try:
                conn.rollback()
            except pyodbc.Error:
                pass
            results.append(
                RoutineValidationResult(
                    routine=target,
                    status=RoutineValidationStatus.UNVERIFIABLE,
                    signature_status=SignatureStatus.UNKNOWN,
                    error_message=str(exc),
                )
            )
            continue

        ref_sql = "SELECT referenced_entity_name, is_incomplete, is_all_columns_found FROM sys.dm_sql_referenced_entities(?, 'OBJECT')"
        try:
            cursor.execute(ref_sql, (target.qualified_name,))
            rows = cursor.fetchall()
            broken: list[str] = []
            for ref_entity, is_inc, is_all_cols in rows:
                if is_inc == 1 or is_all_cols == 0 or is_all_cols is None:
                    broken.append(str(ref_entity or "entidad_desconocida"))

            if broken:
                results.append(
                    RoutineValidationResult(
                        routine=target,
                        status=RoutineValidationStatus.INVALID,
                        signature_status=signed_status,
                        error_message=f"Dependencias con referencias no resueltas: {', '.join(broken)}",
                        broken_entities=tuple(broken),
                    )
                )
            else:
                results.append(
                    RoutineValidationResult(
                        routine=target,
                        status=RoutineValidationStatus.VALID,
                        signature_status=signed_status,
                    )
                )
        except pyodbc.Error as exc:
            try:
                conn.rollback()
            except pyodbc.Error:
                pass
            results.append(
                RoutineValidationResult(
                    routine=target,
                    status=RoutineValidationStatus.INVALID,
                    signature_status=signed_status,
                    error_message=clean_sql_error_message(exc),
                )
            )

    cursor.close()
    return tuple(results)


def refresh_modules_mutating(
    conn: pyodbc.Connection,
    objects_to_refresh: Sequence[RoutineIdentity],
) -> tuple[ModuleRefreshResult, ...]:
    """Execute sp_refreshsqlmodule per object with explicit commit() per success and rollback() on failure.

    Strictly requires objects_to_refresh parameter and rejects signed/unknown modules (fail-closed).
    """
    if not objects_to_refresh:
        return ()

    cursor = conn.cursor()
    results: list[ModuleRefreshResult] = []

    for target in objects_to_refresh:
        try:
            sig_status = get_signature_status(
                conn, target.schema_name, target.object_name
            )
        except SignatureInspectionError as exc:
            try:
                conn.rollback()
            except pyodbc.Error:
                pass
            results.append(
                ModuleRefreshResult.failure(
                    target,
                    error_message=f"Falló la inspección de firmas: {exc}",
                    signature_status=SignatureStatus.UNKNOWN,
                )
            )
            continue

        if sig_status != SignatureStatus.UNSIGNED:
            results.append(
                ModuleRefreshResult.failure(
                    target,
                    error_message="Objeto firmado criptográficamente o firma no verificable — sp_refreshsqlmodule rechazado para evitar pérdida de firma.",
                    signature_status=sig_status,
                )
            )
            continue

        try:
            cursor.execute(
                "EXEC sys.sp_refreshsqlmodule @name = ?", (target.qualified_name,)
            )
            conn.commit()
            results.append(
                ModuleRefreshResult.success(target, signature_status=sig_status)
            )
        except pyodbc.Error as exc:
            try:
                conn.rollback()
            except pyodbc.Error:
                pass
            results.append(
                ModuleRefreshResult.failure(
                    target,
                    error_message=clean_sql_error_message(exc),
                    signature_status=sig_status,
                )
            )

    cursor.close()
    return tuple(results)
