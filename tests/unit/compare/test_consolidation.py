"""Unit tests for the schema consolidation and SQL generator logic."""

import datetime
import tempfile
from pathlib import Path

from schema_comparator.compare.consolidation import (
    ColumnResolution,
    ColumnDeletionResolution,
    TableDeletionResolution,
    TableResolution,
    format_sql_column_definition,
    generate_ddl_for_profile,
    write_sql_scripts,
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


def test_format_sql_column_definition_integer_with_numeric_precision_and_scale() -> None:
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
    profile_a = ConnectionProfile(name="profileA", connection_string="Database=real_db_a;")
    ddl_a = generate_ddl_for_profile([res], profile_a, timestamp=ts)
    
    assert "USE [real_db_a];" in ddl_a
    assert "BEGIN TRANSACTION;" in ddl_a
    assert "IF NOT EXISTS (" in ddl_a
    assert "ALTER TABLE [dbo].[users] ADD [age] int NULL;" in ddl_a
    assert "COMMIT TRANSACTION;" in ddl_a
    assert "-- Generado por BDIFF el 2026-07-14 12:00:00" in ddl_a

    profile_c = ConnectionProfile(name="profileC", connection_string="Database=real_db_c;")
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
    profile_b = ConnectionProfile(name="profileB", connection_string="Initial Catalog=real_db_b;")
    ddl_b = generate_ddl_for_profile([res], profile_b, timestamp=ts)
    
    assert "USE [real_db_b];" in ddl_b
    assert "IF EXISTS (" in ddl_b
    assert "ALTER TABLE [dbo].[users] ALTER COLUMN [email] varchar(255) NOT NULL;" in ddl_b


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
    profile_a = ConnectionProfile(name="profileA", connection_string="Database=real_db_a;")
    profile_b = ConnectionProfile(name="profileB", connection_string="Database=real_db_b;")
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        written_files = write_sql_scripts([res1, res2], tmp_path, [profile_a, profile_b], timestamp=ts)
        
        assert len(written_files) == 2
        
        file_a = tmp_path / "scripts-db" / "profileA.sql"
        file_b = tmp_path / "scripts-db" / "profileB.sql"
        
        assert file_a.exists()
        assert file_b.exists()
        
        content_a = file_a.read_text(encoding="utf-8")
        content_b = file_b.read_text(encoding="utf-8")
        
        assert "USE [real_db_a];" in content_a
        assert "ALTER TABLE [dbo].[users] ADD [age] int NOT NULL;" in content_a
        
        assert "USE [real_db_b];" in content_b
        assert "ALTER TABLE [dbo].[users] ALTER COLUMN [email] int NOT NULL;" in content_b


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
    profile_b = ConnectionProfile(name="profileB", connection_string="Database=real_db_b;")
    ddl_b = generate_ddl_for_profile([], profile_b, timestamp=ts, table_resolutions=[tres])

    assert "USE [real_db_b];" in ddl_b
    assert "IF NOT EXISTS (" in ddl_b
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
    profile_b = ConnectionProfile(name="profileB", connection_string="Database=real_db_b;")
    ddl_b = generate_ddl_for_profile(
        [], profile_b, timestamp=ts, table_deletions=[deletion]
    )

    assert "IF EXISTS (" in ddl_b
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
    profile_b = ConnectionProfile(name="profileB", connection_string="Database=real_db_b;")
    ddl_b = generate_ddl_for_profile(
        [], profile_b, timestamp=ts, column_deletions=[deletion]
    )

    assert "FROM sys.columns c" in ddl_b
    assert "JOIN sys.objects o ON c.object_id = o.object_id" in ddl_b
    assert "JOIN sys.schemas s ON o.schema_id = s.schema_id" in ddl_b
    assert "DROP COLUMN [obsolete_code];" in ddl_b
    assert "Columna [obsolete_code] eliminada con exito de [dbo].[legacy_products]." in ddl_b
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
    profile_a = ConnectionProfile(name="profileA", connection_string="Database=real_db_a;")
    profile_b = ConnectionProfile(name="profileB", connection_string="Database=real_db_b;")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        written_files = write_sql_scripts(
            [], tmp_path, [profile_a, profile_b], timestamp=ts,
            column_deletions=[deletion],
        )

        assert len(written_files) == 1
        file_b = tmp_path / "scripts-db" / "profileB.sql"
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
        columns=(
            NamedColumnAttributes(name="id", attributes=id_attrs),
        ),
        profiles_to_update=("profileB",),
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_a = ConnectionProfile(name="profileA", connection_string="Database=real_db_a;")
    profile_b = ConnectionProfile(name="profileB", connection_string="Database=real_db_b;")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        written_files = write_sql_scripts([], tmp_path, [profile_a, profile_b], timestamp=ts, table_resolutions=[tres])

        assert len(written_files) == 1
        file_b = tmp_path / "scripts-db" / "profileB.sql"
        assert file_b.exists()
        content_b = file_b.read_text(encoding="utf-8")
        assert "CREATE TABLE [dbo].[products] (" in content_b

