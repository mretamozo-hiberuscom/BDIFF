"""SP dependency checking, read-only routine validation, and signature-safe module refresh."""

from dataclasses import dataclass
import pyodbc

from schema_comparator.domain.errors import ModuleEnumerationError, ModuleRefreshError


@dataclass(frozen=True, slots=True)
class DependentObject:
    """A database routine or view that depends on a table being consolidated."""

    schema_name: str
    object_name: str
    object_type: str
    referenced_table: str


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """The outcome of validating or refreshing a procedure or view."""

    schema_name: str
    object_name: str
    is_success: bool
    error_message: str | None = None
    is_signed: bool = False


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
        raise ModuleEnumerationError(f"Error enumerando dependencias para las tablas: {table_names}") from exc
    finally:
        cursor.close()

    return tuple(results)


def is_object_signed(conn: pyodbc.Connection, schema_name: str, object_name: str) -> bool:
    """Check sys.crypt_properties to see if an object has cryptographic signatures."""
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
        return bool(row and row[0] > 0)
    except pyodbc.Error:
        return False
    finally:
        cursor.close()


def validate_routines_read_only(
    conn: pyodbc.Connection,
    objects_to_validate: tuple[tuple[str, str], ...] | None = None,
) -> tuple[RefreshResult, ...]:
    """Read-only routine validation checking dependency expression completeness without executing sp_refreshsqlmodule."""
    cursor = conn.cursor()
    targets: list[tuple[str, str]] = []

    if objects_to_validate is None:
        sql = """
        SELECT s.name, o.name
        FROM sys.objects o
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        WHERE o.type IN ('P', 'FN', 'IF', 'TF', 'V') AND o.is_ms_shipped = 0
        ORDER BY s.name, o.name
        """
        try:
            cursor.execute(sql)
            targets = cursor.fetchall()
        except pyodbc.Error as exc:
            raise ModuleEnumerationError("Error consultando la lista de rutinas para validación") from exc
    else:
        targets = list(objects_to_validate)

    results: list[RefreshResult] = []
    for schema_name, object_name in targets:
        signed = is_object_signed(conn, schema_name, object_name)
        # Non-mutating dependency check
        dep_sql = """
        SELECT COUNT(*)
        FROM sys.sql_expression_dependencies d
        JOIN sys.objects o ON d.referencing_id = o.object_id
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        WHERE s.name = ? AND o.name = ? AND d.is_ambiguous = 1
        """
        try:
            cursor.execute(dep_sql, (schema_name, object_name))
            row = cursor.fetchone()
            ambiguous_cnt = row[0] if row else 0
            if ambiguous_cnt > 0:
                results.append(
                    RefreshResult(
                        schema_name=schema_name,
                        object_name=object_name,
                        is_success=False,
                        error_message=f"Se detectaron {ambiguous_cnt} referencia(s) ambiguas o no resueltas.",
                        is_signed=signed,
                    )
                )
            else:
                results.append(
                    RefreshResult(
                        schema_name=schema_name,
                        object_name=object_name,
                        is_success=True,
                        is_signed=signed,
                    )
                )
        except pyodbc.Error as exc:
            results.append(
                RefreshResult(
                    schema_name=schema_name,
                    object_name=object_name,
                    is_success=False,
                    error_message=str(exc),
                    is_signed=signed,
                )
            )

    cursor.close()
    return tuple(results)


def refresh_modules_mutating(
    conn: pyodbc.Connection,
    objects_to_refresh: tuple[tuple[str, str], ...] | None = None,
) -> tuple[RefreshResult, ...]:
    """Execute sp_refreshsqlmodule for routines and views, strictly rejecting signed objects to prevent signature loss."""
    targets: list[tuple[str, str]] = []
    cursor = conn.cursor()

    if objects_to_refresh is None:
        sql = """
        SELECT s.name, o.name
        FROM sys.objects o
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        WHERE o.type IN ('P', 'FN', 'IF', 'TF', 'V') AND o.is_ms_shipped = 0
        ORDER BY s.name, o.name
        """
        try:
            cursor.execute(sql)
            targets = cursor.fetchall()
        except pyodbc.Error as exc:
            raise ModuleEnumerationError("Error al enumerar módulos para recompilación") from exc
    else:
        targets = list(objects_to_refresh)

    results: list[RefreshResult] = []
    for schema_name, object_name in targets:
        if is_object_signed(conn, schema_name, object_name):
            results.append(
                RefreshResult(
                    schema_name=schema_name,
                    object_name=object_name,
                    is_success=False,
                    error_message="Objeto firmado criptográficamente — sp_refreshsqlmodule rechazado para evitar pérdida de firma.",
                    is_signed=True,
                )
            )
            continue

        safe_sch = schema_name.replace("]", "]]")
        safe_obj = object_name.replace("]", "]]")
        qualified = f"[{safe_sch}].[{safe_obj}]"
        try:
            cursor.execute("EXEC sp_refreshsqlmodule @name = ?", (qualified,))
            results.append(
                RefreshResult(
                    schema_name=schema_name,
                    object_name=object_name,
                    is_success=True,
                    is_signed=False,
                )
            )
        except pyodbc.Error as exc:
            results.append(
                RefreshResult(
                    schema_name=schema_name,
                    object_name=object_name,
                    is_success=False,
                    error_message=str(exc),
                    is_signed=False,
                )
            )

    cursor.close()
    return tuple(results)


# Backward compatibility alias
verify_sps_with_refresh = refresh_modules_mutating
