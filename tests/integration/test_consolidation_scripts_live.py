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
                backfill_value="SIN-CODIGO",
            )
        ],
    )

    _apply(mssql_server, script)

    assert _columns(mssql_server, mssql_db, "productos") == {
        "codigo": ("varchar", "40", "NO")
    }
    assert mssql_server.query(
        "SELECT codigo FROM dbo.productos ORDER BY codigo", database=mssql_db
    ) == [("A1",), ("SIN-CODIGO",)]


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
            # 'no-numerico' cannot become an int: with the loss accepted the
            # check lets it through and the ALTER fails after earlier steps.
            ColumnResolution(
                schema_name="dbo",
                table_name="ventas",
                column_name="codigo",
                target_attributes=_attrs("int", nullable=False),
                profiles_to_update=(_PROFILE,),
                is_missing_column=False,
                accept_data_loss=True,
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
                accept_data_loss=True,
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


def _modify(table: str, column: str, target: ColumnAttributes, observed=None):
    return ColumnResolution(
        schema_name="dbo",
        table_name=table,
        column_name=column,
        target_attributes=target,
        profiles_to_update=(_PROFILE,),
        is_missing_column=False,
        observed_by_profile=((_PROFILE, observed),) if observed else (),
    )


def _new_table(table: str) -> TableResolution:
    return TableResolution(
        schema_name="dbo",
        table_name=table,
        columns=(NamedColumnAttributes("id", _attrs("int", nullable=False)),),
        profiles_to_update=(_PROFILE,),
    )


def _assert_aborted(result, *fragments: str) -> None:
    assert result.returncode != 0, result.stdout
    for fragment in fragments:
        assert fragment in result.stdout, result.stdout


def test_aborts_before_any_change_when_a_column_to_modify_is_missing(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(mssql_server, mssql_db, "CREATE TABLE dbo.clientes (id int NOT NULL);")
    script = _script(
        tmp_path,
        mssql_db,
        table_resolutions=[_new_table("auditoria")],
        columns=[_modify("clientes", "email", _attrs("varchar", length=200))],
    )

    result = mssql_server.run_file(script)

    _assert_aborted(result, "[dbo].[clientes].[email]", "no existe")
    assert _tables(mssql_server, mssql_db) == {"clientes"}


def test_aborts_when_a_table_to_create_exists_with_another_definition(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(mssql_server, mssql_db, "CREATE TABLE dbo.auditoria (id bigint NULL);")
    script = _script(tmp_path, mssql_db, table_resolutions=[_new_table("auditoria")])

    result = mssql_server.run_file(script)

    _assert_aborted(result, "[dbo].[auditoria]", "otra definicion")
    assert _columns(mssql_server, mssql_db, "auditoria") == {
        "id": ("bigint", "", "YES")
    }


def test_aborts_when_a_column_changed_since_the_comparison(
    mssql_server, mssql_db, tmp_path
) -> None:
    # Compared as varchar(10); someone widened it to varchar(15) since.
    _setup(
        mssql_server, mssql_db, "CREATE TABLE dbo.productos (codigo varchar(15) NULL);"
    )
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            _modify(
                "productos",
                "codigo",
                _attrs("varchar", length=40),
                observed=_attrs("varchar", length=10),
            )
        ],
    )

    result = mssql_server.run_file(script)

    _assert_aborted(result, "[dbo].[productos].[codigo]", "difiere de lo comparado")
    assert _columns(mssql_server, mssql_db, "productos") == {
        "codigo": ("varchar", "15", "YES")
    }


def test_aborts_when_a_column_to_add_exists_with_another_definition(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(mssql_server, mssql_db, "CREATE TABLE dbo.pedidos (nota varchar(5) NULL);")
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
            )
        ],
    )

    result = mssql_server.run_file(script)

    _assert_aborted(result, "[dbo].[pedidos].[nota]", "otra definicion")


def test_skips_a_step_already_in_the_target_state(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server, mssql_db, "CREATE TABLE dbo.productos (codigo varchar(40) NULL);"
    )
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            _modify(
                "productos",
                "codigo",
                _attrs("varchar", length=40),
                observed=_attrs("varchar", length=10),
            )
        ],
    )

    result = mssql_server.run_file(script)

    assert result.returncode == 0, result.stdout
    assert "ya aplicado; se omite" in result.stdout
    assert "modificada con exito" not in result.stdout


def _change(table: str, column: str, target, observed, **options):
    return ColumnResolution(
        schema_name="dbo",
        table_name=table,
        column_name=column,
        target_attributes=target,
        profiles_to_update=(_PROFILE,),
        is_missing_column=False,
        observed_by_profile=((_PROFILE, observed),),
        **options,
    )


def test_aborts_with_the_count_when_nulls_have_no_fill_value(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.clientes (pais varchar(20) NULL);"
        " INSERT dbo.clientes VALUES ('ES'), (NULL), (NULL);",
    )
    script = _script(
        tmp_path,
        mssql_db,
        table_resolutions=[_new_table("auditoria")],
        columns=[
            _change(
                "clientes",
                "pais",
                _attrs("varchar", length=20, nullable=False),
                _attrs("varchar", length=20),
            )
        ],
    )

    result = mssql_server.run_file(script)

    _assert_aborted(result, "[dbo].[clientes].[pais]", "2 fila(s) con NULL")
    assert _tables(mssql_server, mssql_db) == {"clientes"}
    assert mssql_server.query(
        "SELECT COUNT(*) FROM dbo.clientes WHERE pais IS NULL", database=mssql_db
    ) == [("2",)]


def test_aborts_when_the_fill_value_does_not_fit_the_type(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.stock (cantidad int NULL); INSERT dbo.stock VALUES (NULL);",
    )
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            _change(
                "stock",
                "cantidad",
                _attrs("int", nullable=False),
                _attrs("int"),
                backfill_value="mucho",
            )
        ],
    )

    result = mssql_server.run_file(script)

    _assert_aborted(result, "[dbo].[stock].[cantidad]", "valor de relleno")


def test_aborts_adding_a_not_null_column_without_fill_to_a_table_with_rows(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.pedidos (id int NOT NULL); INSERT dbo.pedidos VALUES (1);"
        " CREATE TABLE dbo.vacia (id int NOT NULL);",
    )

    def add(table: str) -> ColumnResolution:
        return ColumnResolution(
            schema_name="dbo",
            table_name=table,
            column_name="estado",
            target_attributes=_attrs("int", nullable=False),
            profiles_to_update=(_PROFILE,),
            is_missing_column=True,
        )

    failing = mssql_server.run_file(
        _script(tmp_path / "con-filas", mssql_db, columns=[add("pedidos")])
    )
    _apply(mssql_server, _script(tmp_path / "vacia", mssql_db, columns=[add("vacia")]))

    _assert_aborted(failing, "[dbo].[pedidos].[estado]", "1 fila(s)")
    assert "estado" not in _columns(mssql_server, mssql_db, "pedidos")
    assert _columns(mssql_server, mssql_db, "vacia")["estado"] == ("int", "", "NO")


@pytest.mark.parametrize(
    ("setup", "observed", "target"),
    [
        (
            "CREATE TABLE dbo.t (c varchar(20) NULL); INSERT dbo.t VALUES ('abcdefgh');",
            _attrs("varchar", length=20),
            _attrs("varchar", length=5),
        ),
        (
            "CREATE TABLE dbo.t (c nvarchar(10) NULL); INSERT dbo.t VALUES (N'日本');",
            _attrs("nvarchar", length=10),
            _attrs("varchar", length=10),
        ),
        (
            "CREATE TABLE dbo.t (c decimal(10,4) NULL); INSERT dbo.t VALUES (1.2345);",
            _attrs("decimal", precision=10, scale=4),
            _attrs("decimal", precision=10, scale=2),
        ),
        (
            "CREATE TABLE dbo.t (c varchar(20) NULL); INSERT dbo.t VALUES ('x1');",
            _attrs("varchar", length=20),
            _attrs("int"),
        ),
    ],
    ids=["truncate", "unicode-to-codepage", "round-scale", "not-convertible"],
)
def test_aborts_with_the_count_when_a_change_would_lose_data(
    mssql_server, mssql_db, tmp_path, setup, observed, target
) -> None:
    _setup(mssql_server, mssql_db, setup)
    before = mssql_server.query(
        "SELECT CAST(c AS nvarchar(50)) FROM dbo.t", database=mssql_db
    )
    script = _script(tmp_path, mssql_db, columns=[_change("t", "c", target, observed)])

    result = mssql_server.run_file(script)

    _assert_aborted(result, "[dbo].[t].[c]", "1 fila(s) perderian datos")
    assert (
        mssql_server.query(
            "SELECT CAST(c AS nvarchar(50)) FROM dbo.t", database=mssql_db
        )
        == before
    )


def test_applies_an_accepted_data_loss_and_says_so_in_the_script(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.t (c nvarchar(10) NULL); INSERT dbo.t VALUES (N'日本');",
    )
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            _change(
                "t",
                "c",
                _attrs("varchar", length=10),
                _attrs("nvarchar", length=10),
                accept_data_loss=True,
            )
        ],
    )

    result = mssql_server.run_file(script)

    assert result.returncode == 0, result.stdout
    assert "perdida de datos aceptada" in script.read_text(encoding="utf-8-sig")
    assert _columns(mssql_server, mssql_db, "t") == {"c": ("varchar", "10", "YES")}


def test_a_not_null_change_on_a_missing_column_reports_the_step(
    mssql_server, mssql_db, tmp_path
) -> None:
    # A query naming a missing column breaks the compilation of the whole
    # batch; the checks must still report which step and object failed.
    _setup(mssql_server, mssql_db, "CREATE TABLE dbo.clientes (id int NOT NULL);")
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            _change(
                "clientes",
                "email",
                _attrs("varchar", length=50, nullable=False),
                _attrs("varchar", length=50),
            )
        ],
    )

    result = mssql_server.run_file(script)

    _assert_aborted(result, "[dbo].[clientes].[email]", "no existe")


def _dependents(server, database: str, table: str) -> set[str]:
    """Names of the indexes, statistics and constraints of `dbo.<table>`."""
    rows = server.query(
        "SELECT N'index:' + name FROM sys.indexes"
        f" WHERE object_id = OBJECT_ID(N'dbo.{table}') AND name IS NOT NULL"
        " UNION ALL SELECT N'stats:' + name FROM sys.stats"
        f" WHERE object_id = OBJECT_ID(N'dbo.{table}') AND user_created = 1"
        " UNION ALL SELECT N'constraint:' + name FROM sys.objects"
        f" WHERE parent_object_id = OBJECT_ID(N'dbo.{table}') AND type IN ('D', 'C', 'F', 'PK', 'UQ')",
        database=database,
    )
    return {row[0] for row in rows}


def test_changes_a_column_type_keeping_every_dependent_object(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.articulos (id int NOT NULL, nombre varchar(30) NULL,"
        " codigo varchar(10) NOT NULL CONSTRAINT DF_articulos_codigo DEFAULT 'x'"
        " CONSTRAINT CK_articulos_codigo CHECK (codigo <> 'z')"
        " CONSTRAINT UQ_articulos_codigo UNIQUE);"
        " CREATE INDEX IX_articulos_codigo ON dbo.articulos (codigo DESC, id)"
        " INCLUDE (nombre) WHERE codigo > 'a';"
        " CREATE INDEX IX_articulos_id ON dbo.articulos (id) INCLUDE (codigo);"
        " CREATE STATISTICS ST_articulos_codigo ON dbo.articulos (codigo);"
        " INSERT dbo.articulos VALUES (1, 'pera', 'b1');",
    )
    before = _dependents(mssql_server, mssql_db, "articulos")
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            _change(
                "articulos",
                "codigo",
                _attrs("nvarchar", length=20, nullable=False),
                _attrs("varchar", length=10, nullable=False),
            )
        ],
    )

    _apply(mssql_server, script)

    assert _columns(mssql_server, mssql_db, "articulos")["codigo"] == (
        "nvarchar",
        "20",
        "NO",
    )
    assert _dependents(mssql_server, mssql_db, "articulos") == before
    assert mssql_server.query(
        "SELECT i.filter_definition, c.name, ic.is_descending_key, ic.is_included_column"
        " FROM sys.indexes i JOIN sys.index_columns ic"
        " ON ic.object_id = i.object_id AND ic.index_id = i.index_id"
        " JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id"
        " WHERE i.name = N'IX_articulos_codigo' ORDER BY ic.index_column_id",
        database=mssql_db,
    ) == [
        ("([codigo]>'a')", "codigo", "1", "0"),
        ("([codigo]>'a')", "id", "0", "0"),
        ("([codigo]>'a')", "nombre", "0", "1"),
    ]


def test_changes_a_referenced_primary_key_and_its_foreign_key_together(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.paises (id int NOT NULL CONSTRAINT PK_paises PRIMARY KEY);"
        " CREATE TABLE dbo.ciudades (id int NOT NULL, pais_id int NOT NULL"
        " CONSTRAINT FK_ciudades_paises REFERENCES dbo.paises (id) ON DELETE CASCADE);"
        " CREATE INDEX IX_ciudades_pais ON dbo.ciudades (pais_id);"
        " INSERT dbo.paises VALUES (34); INSERT dbo.ciudades VALUES (1, 34);",
    )
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            _change(
                "paises",
                "id",
                _attrs("bigint", nullable=False),
                _attrs("int", nullable=False),
            ),
            _change(
                "ciudades",
                "pais_id",
                _attrs("bigint", nullable=False),
                _attrs("int", nullable=False),
            ),
        ],
    )

    result = mssql_server.run_file(script)

    assert result.returncode == 0, result.stdout
    assert "reconstruye la tabla" in result.stdout
    assert _columns(mssql_server, mssql_db, "paises")["id"][0] == "bigint"
    assert _columns(mssql_server, mssql_db, "ciudades")["pais_id"][0] == "bigint"
    assert mssql_server.query(
        "SELECT name, delete_referential_action_desc, is_not_trusted"
        " FROM sys.foreign_keys",
        database=mssql_db,
    ) == [("FK_ciudades_paises", "CASCADE", "0")]
    assert "index:PK_paises" in _dependents(mssql_server, mssql_db, "paises")
    assert "index:IX_ciudades_pais" in _dependents(mssql_server, mssql_db, "ciudades")


def test_shrinks_an_indexed_column_whose_data_fits(
    mssql_server, mssql_db, tmp_path
) -> None:
    _setup(
        mssql_server,
        mssql_db,
        "CREATE TABLE dbo.t (c varchar(20) NULL); CREATE INDEX IX_t_c ON dbo.t (c);"
        " INSERT dbo.t VALUES ('corto');",
    )
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            _change(
                "t", "c", _attrs("varchar", length=10), _attrs("varchar", length=20)
            )
        ],
    )

    _apply(mssql_server, script)

    assert _columns(mssql_server, mssql_db, "t") == {"c": ("varchar", "10", "YES")}
    assert "index:IX_t_c" in _dependents(mssql_server, mssql_db, "t")


@pytest.mark.parametrize(
    ("setup", "named"),
    [
        (
            "CREATE TABLE dbo.t (c varchar(10) NULL, total AS (c + '!'));",
            "columna calculada [total]",
        ),
        (
            "CREATE TABLE dbo.t (c varchar(10) NULL);\nGO\n"
            "CREATE VIEW dbo.v_t WITH SCHEMABINDING AS SELECT c FROM dbo.t;",
            "[dbo].[v_t]",
        ),
    ],
    ids=["computed-column", "schemabound-view"],
)
def test_aborts_naming_dependents_it_cannot_recreate(
    mssql_server, mssql_db, tmp_path, setup, named
) -> None:
    _setup(mssql_server, mssql_db, setup)
    script = _script(
        tmp_path,
        mssql_db,
        columns=[
            _change(
                "t", "c", _attrs("nvarchar", length=10), _attrs("varchar", length=10)
            )
        ],
    )

    result = mssql_server.run_file(script)

    _assert_aborted(result, "[dbo].[t].[c]", "no recrea", named)
    assert _columns(mssql_server, mssql_db, "t")["c"] == ("varchar", "10", "YES")
