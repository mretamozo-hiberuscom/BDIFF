"""Unit tests for the schema consolidation and SQL generator logic."""

import datetime
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from schema_comparator.compare.consolidation import (
    ColumnResolution,
    ConsolidationDatabaseUnknownError,
    ColumnDeletionResolution,
    TableDeletionResolution,
    TableResolution,
    generate_impact_report,
    write_sql_scripts,
)
from schema_comparator.infrastructure.providers.sqlserver.ddl_renderer import (
    format_sql_column_definition,
    generate_ddl_for_profile,
)
from schema_comparator.compare.models import ColumnAttributes, NamedColumnAttributes
from schema_comparator.config.models import ConnectionProfile


def test_format_sql_column_definition_character_length() -> None:
    attrs = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=100,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    assert format_sql_column_definition(attrs) == "varchar(100) NOT NULL"


def test_format_sql_column_definition_character_max_length() -> None:
    attrs = ColumnAttributes(
        data_type="nvarchar",
        character_maximum_length=-1,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    assert format_sql_column_definition(attrs) == "nvarchar(MAX) NULL"


def test_format_sql_column_definition_numeric_precision_and_scale() -> None:
    attrs = ColumnAttributes(
        data_type="decimal",
        character_maximum_length=None,
        numeric_precision=18,
        numeric_scale=4,
        is_nullable=False,
    )
    assert format_sql_column_definition(attrs) == "decimal(18, 4) NOT NULL"


def test_format_sql_column_definition_numeric_precision_only() -> None:
    attrs = ColumnAttributes(
        data_type="numeric",
        character_maximum_length=None,
        numeric_precision=10,
        numeric_scale=None,
        is_nullable=True,
    )
    assert format_sql_column_definition(attrs) == "numeric(10) NULL"


def test_format_sql_column_definition_simple_type() -> None:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    assert format_sql_column_definition(attrs) == "int NOT NULL"


def test_format_sql_column_definition_integer_with_numeric_precision_and_scale() -> (
    None
):
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=10,
        numeric_scale=0,
        is_nullable=False,
    )
    assert format_sql_column_definition(attrs) == "int NOT NULL"


def test_format_sql_column_definition_integer_with_embedded_precision_string() -> None:
    attrs = ColumnAttributes(
        data_type="int(10, 0)",
        character_maximum_length=None,
        numeric_precision=10,
        numeric_scale=0,
        is_nullable=True,
    )
    assert format_sql_column_definition(attrs) == "int NULL"


def test_generate_ddl_for_profile_missing_column() -> None:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    res = ColumnResolution(
        schema_name="dbo",
        table_name="users",
        column_name="age",
        target_attributes=attrs,
        profiles_to_update=("profileA", "profileB"),
        is_missing_column=True,
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_a = ConnectionProfile(
        name="profileA", connection_string="Database=real_db_a;"
    )
    ddl_a = generate_ddl_for_profile([res], profile_a, timestamp=ts)

    assert "USE [real_db_a];" in ddl_a
    assert "BEGIN TRANSACTION;" in ddl_a
    assert (
        "IF EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'users' AND COLUMN_NAME = N'age')"
        in ddl_a
    )
    assert "ALTER TABLE [dbo].[users] ADD [age] int NULL;" in ddl_a
    assert "COMMIT TRANSACTION;" in ddl_a
    assert "-- Generado por BDIFF el 2026-07-14 12:00:00" in ddl_a

    profile_c = ConnectionProfile(
        name="profileC", connection_string="Database=real_db_c;"
    )
    ddl_c = generate_ddl_for_profile([res], profile_c, timestamp=ts)
    assert "No se requieren cambios para este perfil." in ddl_c


def test_generate_ddl_for_profile_column_mismatch() -> None:
    attrs = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=255,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    res = ColumnResolution(
        schema_name="dbo",
        table_name="users",
        column_name="email",
        target_attributes=attrs,
        profiles_to_update=("profileB",),
        is_missing_column=False,
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_b = ConnectionProfile(
        name="profileB", connection_string="Initial Catalog=real_db_b;"
    )
    ddl_b = generate_ddl_for_profile([res], profile_b, timestamp=ts)

    assert "USE [real_db_b];" in ddl_b
    assert "ELSE IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS" in ddl_b
    assert (
        "ALTER TABLE [dbo].[users] ALTER COLUMN [email] varchar(255) NOT NULL;" in ddl_b
    )


def test_write_sql_scripts_creates_files() -> None:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    res1 = ColumnResolution(
        schema_name="dbo",
        table_name="users",
        column_name="age",
        target_attributes=attrs,
        profiles_to_update=("profileA",),
        is_missing_column=True,
    )
    res2 = ColumnResolution(
        schema_name="dbo",
        table_name="users",
        column_name="email",
        target_attributes=attrs,
        profiles_to_update=("profileB",),
        is_missing_column=False,
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_a = ConnectionProfile(
        name="profileA", connection_string="Database=real_db_a;"
    )
    profile_b = ConnectionProfile(
        name="profileB", connection_string="Database=real_db_b;"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        written_files = write_sql_scripts(
            [res1, res2], tmp_path, [profile_a, profile_b], timestamp=ts
        )

        # A script and its undo per profile, plus the impact report.
        assert len(written_files) == 5

        file_a = tmp_path / "scripts-db" / "20260714_120000" / "profileA.sql"
        file_b = tmp_path / "scripts-db" / "20260714_120000" / "profileB.sql"
        report_file = tmp_path / "scripts-db" / "20260714_120000" / "impact_report.md"

        assert file_a.exists()
        assert file_b.exists()
        assert report_file.exists()

        content_a = file_a.read_text(encoding="utf-8")
        content_b = file_b.read_text(encoding="utf-8")
        report_content = report_file.read_text(encoding="utf-8")

        assert "USE [real_db_a];" in content_a
        # NOT NULL with no default nor fill value: only an empty table can
        # take it, so the script counts the rows first.
        assert "SELECT @n = COUNT_BIG(*) FROM [dbo].[users];" in content_a
        assert "ALTER TABLE [dbo].[users] ADD [age] int NOT NULL;" in content_a
        assert "= 0 WHERE" not in content_a

        assert "USE [real_db_b];" in content_b
        assert (
            "ALTER TABLE [dbo].[users] ALTER COLUMN [email] int NOT NULL;" in content_b
        )

        assert (
            "# Reporte de Impacto en Procedimientos Almacenados y Objetos DB"
            in report_content
        )
        assert "sys.sql_expression_dependencies" in report_content


def test_generate_ddl_for_profile_missing_table() -> None:
    id_attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    name_attrs = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=150,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    tres = TableResolution(
        schema_name="dbo",
        table_name="products",
        columns=(
            NamedColumnAttributes(name="id", attributes=id_attrs),
            NamedColumnAttributes(name="name", attributes=name_attrs),
        ),
        profiles_to_update=("profileB",),
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_b = ConnectionProfile(
        name="profileB", connection_string="Database=real_db_b;"
    )
    ddl_b = generate_ddl_for_profile(
        [], profile_b, timestamp=ts, table_resolutions=[tres]
    )

    assert "USE [real_db_b];" in ddl_b
    assert "IF OBJECT_ID(N'[dbo].[products]', N'U') IS NOT NULL" in ddl_b
    assert "CREATE TABLE [dbo].[products] (" in ddl_b
    assert "[id] int NOT NULL" in ddl_b
    assert "[name] varchar(150) NULL" in ddl_b
    assert "Tabla [dbo].[products] creada con exito." in ddl_b
    assert "COMMIT TRANSACTION;" in ddl_b


def test_generate_ddl_for_profile_table_deletion() -> None:
    deletion = TableDeletionResolution(
        schema_name="dbo",
        table_name="legacy_products",
        profiles_to_update=("profileB",),
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_b = ConnectionProfile(
        name="profileB", connection_string="Database=real_db_b;"
    )
    ddl_b = generate_ddl_for_profile(
        [], profile_b, timestamp=ts, table_deletions=[deletion]
    )

    assert "IF NOT (OBJECT_ID(N'[dbo].[legacy_products]', N'U') IS NOT NULL)" in ddl_b
    assert "DROP TABLE [dbo].[legacy_products];" in ddl_b
    assert "Tabla [dbo].[legacy_products] eliminada con exito." in ddl_b
    assert "COMMIT TRANSACTION;" in ddl_b


def test_generate_ddl_for_profile_column_deletion() -> None:
    deletion = ColumnDeletionResolution(
        schema_name="dbo",
        table_name="legacy_products",
        column_name="obsolete_code",
        profiles_to_update=("profileB",),
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_b = ConnectionProfile(
        name="profileB", connection_string="Database=real_db_b;"
    )
    ddl_b = generate_ddl_for_profile(
        [], profile_b, timestamp=ts, column_deletions=[deletion]
    )

    assert (
        "IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = N'dbo' AND TABLE_NAME = N'legacy_products' AND COLUMN_NAME = N'obsolete_code')"
        in ddl_b
    )

    assert (
        "INTO [bdiff_respaldo].[bdiff_bak_20260714_120000_legacy_products_obsolete_code]"
        in ddl_b
    )
    assert "DROP COLUMN [obsolete_code];" in ddl_b
    assert (
        "Columna [obsolete_code] eliminada con exito de [dbo].[legacy_products]."
        in ddl_b
    )
    assert "BEGIN TRANSACTION;" in ddl_b
    assert "COMMIT TRANSACTION;" in ddl_b


def test_write_sql_scripts_with_column_deletion_includes_affected_profile() -> None:
    deletion = ColumnDeletionResolution(
        schema_name="dbo",
        table_name="legacy_products",
        column_name="obsolete_code",
        profiles_to_update=("profileB",),
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_a = ConnectionProfile(
        name="profileA", connection_string="Database=real_db_a;"
    )
    profile_b = ConnectionProfile(
        name="profileB", connection_string="Database=real_db_b;"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        written_files = write_sql_scripts(
            [],
            tmp_path,
            [profile_a, profile_b],
            timestamp=ts,
            column_deletions=[deletion],
        )

        assert len(written_files) == 3
        file_b = tmp_path / "scripts-db" / "20260714_120000" / "profileB.sql"
        assert file_b.exists()
        assert "DROP COLUMN [obsolete_code];" in file_b.read_text(encoding="utf-8")


def test_write_sql_scripts_with_table_resolution() -> None:
    id_attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    tres = TableResolution(
        schema_name="dbo",
        table_name="products",
        columns=(NamedColumnAttributes(name="id", attributes=id_attrs),),
        profiles_to_update=("profileB",),
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_a = ConnectionProfile(
        name="profileA", connection_string="Database=real_db_a;"
    )
    profile_b = ConnectionProfile(
        name="profileB", connection_string="Database=real_db_b;"
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        written_files = write_sql_scripts(
            [], tmp_path, [profile_a, profile_b], timestamp=ts, table_resolutions=[tres]
        )

        assert len(written_files) == 3
        file_b = tmp_path / "scripts-db" / "20260714_120000" / "profileB.sql"
        assert file_b.exists()
        content_b = file_b.read_text(encoding="utf-8")
        assert "CREATE TABLE [dbo].[products] (" in content_b


def _envelope_script(database_part: str = "Database=real_db;") -> str:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    return generate_ddl_for_profile(
        [
            ColumnResolution(
                schema_name="dbo",
                table_name="users",
                column_name="age",
                target_attributes=attrs,
                profiles_to_update=("p",),
                is_missing_column=True,
            )
        ],
        ConnectionProfile(name="p", connection_string=f"Server=s;{database_part}"),
        timestamp=datetime.datetime(2026, 10, 21, 12, 0, 0),
    )


def test_script_runs_nothing_unless_the_active_database_is_the_target() -> None:
    script = _envelope_script()

    guard = script.index("IF DB_NAME() <> N'real_db'")
    assert script.index("USE [real_db];") < guard < script.index("BEGIN TRANSACTION;")
    assert "SET NOEXEC ON;" in script[guard:]
    assert script.rstrip().endswith("SET NOEXEC OFF;\nGO")


def test_script_aborts_whole_on_any_error_and_rethrows_the_original() -> None:
    script = _envelope_script()

    assert "SET XACT_ABORT ON;" in script
    assert "SET LOCK_TIMEOUT 30000;" in script
    assert "    THROW;" in script
    assert "RAISERROR(@ErrorMessage" not in script


def test_script_header_says_how_to_run_it() -> None:
    header = _envelope_script().split("USE [", 1)[0]

    assert "sqlcmd" in header and "-b" in header
    assert "SSMS" in header


def test_write_sql_scripts_refuses_a_profile_without_database(tmp_path) -> None:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    resolution = ColumnResolution(
        schema_name="dbo",
        table_name="users",
        column_name="age",
        target_attributes=attrs,
        profiles_to_update=("con_base", "sin_base"),
        is_missing_column=True,
    )
    profiles = [
        ConnectionProfile(name="con_base", connection_string="Server=s;Database=a;"),
        ConnectionProfile(
            name="sin_base", connection_string="Server=s;Password=secreto;"
        ),
    ]

    with pytest.raises(ConsolidationDatabaseUnknownError) as excinfo:
        write_sql_scripts([resolution], tmp_path, profiles)

    assert "sin_base" in str(excinfo.value)
    assert "con_base" not in str(excinfo.value)
    assert "secreto" not in str(excinfo.value)
    assert not (tmp_path / "scripts-db").exists()


def test_write_sql_scripts_writes_utf8_with_bom(tmp_path) -> None:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    written = write_sql_scripts(
        [
            ColumnResolution(
                schema_name="dbo",
                table_name="Año",
                column_name="número",
                target_attributes=attrs,
                profiles_to_update=("p",),
                is_missing_column=True,
            )
        ],
        tmp_path,
        [ConnectionProfile(name="p", connection_string="Database=a;")],
    )

    script = next(Path(f) for f in written if f.endswith(".sql"))
    raw = script.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "[Año]" in raw.decode("utf-8-sig")


def test_script_verifies_every_step_before_committing() -> None:
    script = _envelope_script()

    check = script.index("-- 1. Comprobaciones previas")
    change = script.index("ALTER TABLE [dbo].[users] ADD [age] int NULL;")
    verify = script.index("-- 3. Verificacion final")
    commit = script.index("COMMIT TRANSACTION;")
    assert check < change < verify < commit
    assert (
        "THROW 50002, N'Paso 1/1: agregar la columna [dbo].[users].[age]: "
        "no quedo aplicado; se deshace todo.', 1;" in script[verify:commit]
    )


def test_scripts_use_nothing_newer_than_sql_server_2016() -> None:
    attrs = ColumnAttributes(
        data_type="nvarchar",
        character_maximum_length=20,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    script = generate_ddl_for_profile(
        [
            ColumnResolution(
                schema_name="dbo",
                table_name="t",
                column_name="c",
                target_attributes=attrs,
                profiles_to_update=("p",),
                is_missing_column=False,
                observed_by_profile=(("p", replace(attrs, data_type="varchar")),),
            )
        ],
        ConnectionProfile(name="p", connection_string="Database=a;"),
    ).upper()

    for newer in (
        "STRING_AGG",
        "TRIM(",
        "CONCAT_WS",
        "TRANSLATE(",
        "GREATEST(",
        "LEAST(",
    ):
        assert newer not in script


def test_impact_report_warns_that_a_clustered_rebuild_is_slow() -> None:
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    report = generate_impact_report(
        [
            ColumnResolution(
                schema_name="dbo",
                table_name="t",
                column_name="c",
                target_attributes=attrs,
                profiles_to_update=("p",),
                is_missing_column=False,
            )
        ],
        ["p"],
        timestamp=datetime.datetime(2026, 10, 21, 12, 0, 0),
    )

    assert "reconstruye la tabla completa" in report


def test_impact_report_lists_the_backups_and_how_to_clean_them() -> None:
    report = generate_impact_report(
        [],
        ["p"],
        timestamp=datetime.datetime(2026, 10, 21, 12, 0, 0),
        table_deletions=[
            TableDeletionResolution(
                schema_name="dbo", table_name="viejas", profiles_to_update=("p",)
            )
        ],
        column_deletions=[
            ColumnDeletionResolution(
                schema_name="dbo",
                table_name="stock",
                column_name="cantidad",
                profiles_to_update=("p",),
            )
        ],
    )

    assert "[bdiff_respaldo].[bdiff_bak_20261021_120000_viejas]" in report
    assert "[bdiff_respaldo].[bdiff_bak_20261021_120000_stock_cantidad]" in report
    assert "[bdiff_respaldo].[bdiff_diario_20261021_120000]" in report
    assert "DROP TABLE" in report


def test_undo_refuses_steps_it_has_no_previous_definition_for() -> None:
    from schema_comparator.infrastructure.providers.sqlserver.ddl_renderer import (
        generate_undo_for_profile,
    )

    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    undo = generate_undo_for_profile(
        [
            ColumnResolution(
                schema_name="dbo",
                table_name="t",
                column_name="c",
                target_attributes=attrs,
                profiles_to_update=("p",),
                is_missing_column=False,
            )
        ],
        ConnectionProfile(name="p", connection_string="Database=a;"),
        timestamp=datetime.datetime(2026, 10, 21, 12, 0, 0),
        table_deletions=[
            TableDeletionResolution(
                schema_name="dbo", table_name="vieja", profiles_to_update=("p",)
            )
        ],
    )

    assert (
        "Paso 1/2: modificar la columna [dbo].[t].[c]: no se conoce su definicion anterior"
        in undo
    )
    assert (
        "Paso 2/2: recrear la tabla [dbo].[vieja]: no se conoce su definicion" in undo
    )
    assert "-- Script para DESHACER" in undo
