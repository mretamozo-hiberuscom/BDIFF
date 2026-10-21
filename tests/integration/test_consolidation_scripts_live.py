"""Generated consolidation scripts run against a real SQL Server.

Each test writes the scripts with `write_sql_scripts`, runs the profile's
file through sqlcmd in a fresh database and checks the schema it leaves.
Skipped without Docker (see `conftest.py`).
"""

import datetime
from pathlib import Path

import pytest

from schema_comparator.compare.consolidation import (
    ColumnDeletionResolution,
    ColumnResolution,
    TableDeletionResolution,
    TableResolution,
    write_sql_scripts,
)
from schema_comparator.compare.models import ColumnAttributes, NamedColumnAttributes
from schema_comparator.config.models import ConnectionProfile

_PROFILE = "destino"
_TIMESTAMP = datetime.datetime(2026, 10, 21, 12, 0, 0)


def _attrs(
    data_type: str,
    *,
    length: int | None = None,
    precision: int | None = None,
    scale: int | None = None,
    nullable: bool = True,
    default: str | None = None,
) -> ColumnAttributes:
    return ColumnAttributes(
        data_type=data_type,
        character_maximum_length=length,
        numeric_precision=precision,
        numeric_scale=scale,
        is_nullable=nullable,
        default_expression=default,
    )


def _script(tmp_path: Path, database: str, **resolutions) -> Path:
    """The profile's generated script file for `database`."""
    profile = ConnectionProfile(
        name=_PROFILE, connection_string=f"Server=localhost;Database={database};"
    )
    written = write_sql_scripts(
        resolutions.pop("columns", []),
        tmp_path,
        [profile],
        timestamp=_TIMESTAMP,
        **resolutions,
    )
    script = next(path for path in written if path.endswith(f"{_PROFILE}.sql"))
    return Path(script)


def _columns(server, database: str, table: str) -> dict[str, tuple[str, ...]]:
    rows = server.query(
        "SELECT COLUMN_NAME, DATA_TYPE, "
        "ISNULL(CAST(CHARACTER_MAXIMUM_LENGTH AS varchar(10)), ''), IS_NULLABLE "
        "FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'{table}'",
        database=database,
    )
    return {row[0]: row[1:] for row in rows}


def _tables(server, database: str) -> set[str]:
    rows = server.query(
        "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE = 'BASE TABLE'",
        database=database,
    )
    return {row[0] for row in rows}


def _setup(server, database: str, sql: str) -> None:
    result = server.run(f"{sql}\nGO\n", database=database)
    assert result.returncode == 0, result.stdout + result.stderr


def _apply(server, script: Path) -> None:
    result = server.run_file(script)
    assert result.returncode == 0, result.stdout + result.stderr


def test_creates_a_missing_table(mssql_server, mssql_db, tmp_path) -> None:
    script = _script(
        tmp_path,
        mssql_db,
        table_resolutions=[
            TableResolution(
                schema_name="dbo",
                table_name="clientes",
                columns=(
                    NamedColumnAttributes("id", _attrs("int", nullable=False)),
                    NamedColumnAttributes("nombre", _attrs("nvarchar", length=80)),
                ),
                profiles_to_update=(_PROFILE,),
            )
        ],
    )

    _apply(mssql_server, script)

    assert _columns(mssql_server, mssql_db, "clientes") == {
        "id": ("int", "", "NO"),
        "nombre": ("nvarchar", "80", "YES"),
    }


def test_escapes_quotes_brackets_and_accents_in_identifiers(
    mssql_server, mssql_db, tmp_path
) -> None:
    script = _script(
        tmp_path,
        mssql_db,
        table_resolutions=[
            TableResolution(
                schema_name="dbo",
                table_name="Año]x",
                columns=(NamedColumnAttributes("o'brien", _attrs("int")),),
                profiles_to_update=(_PROFILE,),
            )
        ],
    )

    _apply(mssql_server, script)

    assert _columns(mssql_server, mssql_db, "Año]x") == {"o'brien": ("int", "", "YES")}


def test_adds_columns_and_backfills_a_not_null_one(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.pedidos (id int NOT NULL); INSERT dbo.pedidos VALUES (1), (2);",
    )
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            ColumnResolution(
                schema_name="dbo",
                table_name="pedidos",
                column_name="nota",
                target_attributes=_attrs("varchar", length=50),
                profiles_to_update=(_PROFILE,),
                is_missing_column=True,
            ),
            ColumnResolution(
                schema_name="dbo",
                table_name="pedidos",
                column_name="estado",
                target_attributes=_attrs("int", nullable=False, default="((7))"),
                profiles_to_update=(_PROFILE,),
                is_missing_column=True,
            ),
        ],
    )

    _apply(mssql_server, script)

    assert _columns(mssql_server, mssql_db, "pedidos") == {
        "id": ("int", "", "NO"),
        "nota": ("varchar", "50", "YES"),
        "estado": ("int", "", "NO"),
    }
    assert mssql_server.query(
        "SELECT DISTINCT estado FROM dbo.pedidos", database=mssql_db
    ) == [("7",)]


def test_widens_a_column_and_makes_it_not_null(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.productos (codigo varchar(10) NULL);"
        " INSERT dbo.productos VALUES ('A1'), (NULL);",
    )
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            ColumnResolution(
                schema_name="dbo",
                table_name="productos",
                column_name="codigo",
                target_attributes=_attrs("varchar", length=40, nullable=False),
                profiles_to_update=(_PROFILE,),
                is_missing_column=False,
            )
        ],
    )

    _apply(mssql_server, script)

    assert _columns(mssql_server, mssql_db, "productos") == {
        "codigo": ("varchar", "40", "NO")
    }


def test_drops_a_column_with_its_index_check_and_default(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.stock (id int NOT NULL,"
        " cantidad int NOT NULL CONSTRAINT DF_stock_cantidad DEFAULT 0"
        " CONSTRAINT CK_stock_cantidad CHECK (cantidad >= 0));"
        " CREATE INDEX IX_stock_cantidad ON dbo.stock (cantidad);",
    )
    script = _script(
        tmp_path,
        mssql_db,
        column_deletions=[
            ColumnDeletionResolution(
                schema_name="dbo",
                table_name="stock",
                column_name="cantidad",
                profiles_to_update=(_PROFILE,),
            )
        ],
    )

    _apply(mssql_server, script)

    assert _columns(mssql_server, mssql_db, "stock") == {"id": ("int", "", "NO")}


def test_drops_a_table_referenced_by_a_foreign_key(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.paises (id int NOT NULL PRIMARY KEY);"
        " CREATE TABLE dbo.ciudades (id int NOT NULL,"
        " pais_id int NOT NULL CONSTRAINT FK_ciudades_paises REFERENCES dbo.paises (id));",
    )
    script = _script(
        tmp_path,
        mssql_db,
        table_deletions=[
            TableDeletionResolution(
                schema_name="dbo", table_name="paises", profiles_to_update=(_PROFILE,)
            )
        ],
    )

    _apply(mssql_server, script)

    assert _tables(mssql_server, mssql_db) == {"ciudades"}


def test_running_a_script_twice_changes_nothing_the_second_time(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(mssql_server, mssql_db, "CREATE TABLE dbo.lineas (id int NOT NULL);")
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            ColumnResolution(
                schema_name="dbo",
                table_name="lineas",
                column_name="importe",
                target_attributes=_attrs("decimal", precision=12, scale=2),
                profiles_to_update=(_PROFILE,),
                is_missing_column=True,
            )
        ],
        table_resolutions=[
            TableResolution(
                schema_name="dbo",
                table_name="facturas",
                columns=(NamedColumnAttributes("id", _attrs("int", nullable=False)),),
                profiles_to_update=(_PROFILE,),
            )
        ],
    )

    _apply(mssql_server, script)
    _apply(mssql_server, script)

    assert _tables(mssql_server, mssql_db) == {"lineas", "facturas"}
    assert _columns(mssql_server, mssql_db, "lineas") == {
        "id": ("int", "", "NO"),
        "importe": ("decimal", "", "YES"),
    }


@pytest.mark.parametrize("stop_on_error", [True, False], ids=["sqlcmd-b", "ssms"])
def test_a_failing_step_leaves_the_database_unchanged(
    mssql_server, mssql_db, tmp_path, stop_on_error
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.ventas (codigo varchar(20) NOT NULL);"
        " INSERT dbo.ventas VALUES ('no-numerico');",
    )
    script = _script(
        tmp_path,
        mssql_db,
        table_resolutions=[
            TableResolution(
                schema_name="dbo",
                table_name="nueva",
                columns=(NamedColumnAttributes("id", _attrs("int")),),
                profiles_to_update=(_PROFILE,),
            )
        ],
        columns=[
            ColumnResolution(
                schema_name="dbo",
                table_name="ventas",
                column_name="extra",
                target_attributes=_attrs("int"),
                profiles_to_update=(_PROFILE,),
                is_missing_column=True,
            ),
            # 'no-numerico' cannot become an int: this step fails last.
            ColumnResolution(
                schema_name="dbo",
                table_name="ventas",
                column_name="codigo",
                target_attributes=_attrs("int", nullable=False),
                profiles_to_update=(_PROFILE,),
                is_missing_column=False,
            ),
        ],
    )

    result = mssql_server.run_file(script, stop_on_error=stop_on_error)

    assert "Transaccion abortada" in result.stdout
    if stop_on_error:
        assert result.returncode != 0
    assert _tables(mssql_server, mssql_db) == {"ventas"}
    assert _columns(mssql_server, mssql_db, "ventas") == {
        "codigo": ("varchar", "20", "NO")
    }
    assert mssql_server.query(
        "SELECT COUNT(*) FROM sys.dm_tran_active_transactions t"
        " JOIN sys.dm_tran_database_transactions d ON t.transaction_id = d.transaction_id"
        f" WHERE d.database_id = DB_ID(N'{mssql_db}')"
    ) == [("0",)]


@pytest.mark.parametrize("stop_on_error", [True, False], ids=["sqlcmd-b", "ssms"])
def test_changes_nothing_elsewhere_when_the_database_does_not_exist(
    mssql_server, tmp_path, stop_on_error
) -> None:
    table = f"huerfana_{'b' if stop_on_error else 's'}"
    script = _script(
        tmp_path,
        "bdiff_no_existe",
        table_resolutions=[
            TableResolution(
                schema_name="dbo",
                table_name=table,
                columns=(NamedColumnAttributes("id", _attrs("int")),),
                profiles_to_update=(_PROFILE,),
            )
        ],
    )

    try:
        result = mssql_server.run_file(script, stop_on_error=stop_on_error)

        if stop_on_error:
            assert result.returncode != 0
        assert table not in _tables(mssql_server, "master")
    finally:
        mssql_server.run(f"DROP TABLE IF EXISTS dbo.{table};\nGO\n")


def test_a_failure_reports_the_original_error_number(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.ventas (codigo varchar(20) NOT NULL);"
        " INSERT dbo.ventas VALUES ('no-numerico');",
    )
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            ColumnResolution(
                schema_name="dbo",
                table_name="ventas",
                column_name="codigo",
                target_attributes=_attrs("int", nullable=False),
                profiles_to_update=(_PROFILE,),
                is_missing_column=False,
            )
        ],
    )

    result = mssql_server.run_file(script)

    assert result.returncode != 0
    # 245: conversion failed; a re-raise through RAISERROR would say 50000.
    assert "Msg 245," in result.stdout


def test_modifies_a_column_whose_names_fall_outside_the_code_page(
    mssql_server, mssql_db, tmp_path
) -> None:
    # The database's default collation is Latin1: '注文' as a varchar
    # literal becomes '??' and would match nothing.
    _setup(mssql_server, mssql_db, "CREATE TABLE dbo.[注文] ([数量] varchar(10) NULL);")
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            ColumnResolution(
                schema_name="dbo",
                table_name="注文",
                column_name="数量",
                target_attributes=_attrs("varchar", length=40),
                profiles_to_update=(_PROFILE,),
                is_missing_column=False,
            )
        ],
    )

    _apply(mssql_server, script)

    assert _columns(mssql_server, mssql_db, "注文") == {
        "数量": ("varchar", "40", "YES")
    }


def test_drops_a_referenced_table_whose_name_has_a_bracket(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.[pa]]ises] (id int NOT NULL PRIMARY KEY);"
        " CREATE TABLE dbo.ciudades (pais_id int NOT NULL"
        " CONSTRAINT FK_ciudades_paises REFERENCES dbo.[pa]]ises] (id));",
    )
    script = _script(
        tmp_path,
        mssql_db,
        table_deletions=[
            TableDeletionResolution(
                schema_name="dbo", table_name="pa]ises", profiles_to_update=(_PROFILE,)
            )
        ],
    )

    _apply(mssql_server, script)

    assert _tables(mssql_server, mssql_db) == {"ciudades"}
