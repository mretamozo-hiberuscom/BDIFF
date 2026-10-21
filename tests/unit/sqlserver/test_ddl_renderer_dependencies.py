"""Unit tests for Foreign Key and constraint dependency cleanup in SQL Server DDL rendering."""

from schema_comparator.compare.consolidation import (
    ColumnDeletionResolution,
    ColumnResolution,
    TableDeletionResolution,
    TableResolution,
)
from schema_comparator.domain.comparison.models import (
    ColumnAttributes,
    NamedColumnAttributes,
)
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.infrastructure.providers.sqlserver.ddl_renderer import (
    extract_database_name,
    generate_ddl_for_profile,
)


def test_extract_database_name_variations() -> None:
    assert extract_database_name("Database=TestDB;User=sa;") == "TestDB"
    assert extract_database_name("Initial Catalog='My DB';User=sa;") == "My DB"
    assert extract_database_name("db=[Sales_DB];User=sa;") == "Sales_DB"
    assert extract_database_name('Database = " Production ";') == "Production"


def test_generate_ddl_table_deletion_cleans_foreign_keys() -> None:
    profile = ConnectionProfile(name="dev_db", connection_string="Database=TestDB;")
    table_deletions = [
        TableDeletionResolution(
            schema_name="dbo", table_name="Orders", profiles_to_update=("dev_db",)
        ),
    ]

    ddl = generate_ddl_for_profile(
        resolutions=[],
        profile=profile,
        table_deletions=table_deletions,
    )

    assert "sys.foreign_keys" in ddl
    assert "DROP TABLE [dbo].[Orders];" in ddl
    assert "@fk_sql_1" in ddl
    assert "referenced_object_id = OBJECT_ID(N'[dbo].[Orders]')" in ddl


def test_generate_ddl_column_deletion_cleans_fks_and_default_constraints() -> None:
    profile = ConnectionProfile(name="dev_db", connection_string="Database=TestDB;")
    column_deletions = [
        ColumnDeletionResolution(
            schema_name="dbo",
            table_name="Customers",
            column_name="StatusId",
            profiles_to_update=("dev_db",),
        ),
    ]

    ddl = generate_ddl_for_profile(
        resolutions=[],
        profile=profile,
        column_deletions=column_deletions,
    )

    assert "sys.foreign_key_columns" in ddl
    assert "sys.default_constraints" in ddl
    assert "sys.indexes" in ddl
    assert "sys.check_constraints" in ddl
    assert "sys.sql_expression_dependencies" in ddl
    assert "ALTER TABLE [dbo].[Customers] DROP COLUMN [StatusId];" in ddl
    # Every dependent is collected with its drop and recreate statements,
    # journaled for undo, and dropped before the column.
    assert "DECLARE @deps_1 TABLE" in ddl
    assert "INSERT [bdiff_respaldo].[bdiff_diario_" in ddl
    assert "DECLARE bdiff_dep_drop_1 CURSOR" in ddl


def test_generate_ddl_escapes_single_quotes_in_print_statements() -> None:
    profile = ConnectionProfile(name="dev_db", connection_string="Database=TestDB;")
    attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    table_res = [
        TableResolution(
            schema_name="d'bo",
            table_name="Order's",
            columns=(NamedColumnAttributes(name="col'1", attributes=attrs),),
            profiles_to_update=("dev_db",),
        )
    ]
    column_res = [
        ColumnResolution(
            schema_name="d'bo",
            table_name="User's",
            column_name="Age's",
            target_attributes=attrs,
            profiles_to_update=("dev_db",),
            is_missing_column=True,
        )
    ]

    ddl = generate_ddl_for_profile(
        resolutions=column_res,
        profile=profile,
        table_resolutions=table_res,
    )

    assert "PRINT N'Tabla [d''bo].[Order''s] creada con exito.';" in ddl
    assert "PRINT N'Columna [Age''s] agregada con exito a [d''bo].[User''s].';" in ddl


def test_generate_ddl_not_null_column_never_invents_a_fill_value() -> None:
    profile = ConnectionProfile(name="dev_db", connection_string="Database=TestDB;")
    not_null_attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )

    def resolution(column: str, missing: bool, fill: str | None) -> ColumnResolution:
        return ColumnResolution(
            schema_name="dbo",
            table_name="Orders",
            column_name=column,
            target_attributes=not_null_attrs,
            profiles_to_update=("dev_db",),
            is_missing_column=missing,
            backfill_value=fill,
        )

    ddl_mod = generate_ddl_for_profile(
        resolutions=[resolution("CustomerId", False, None)], profile=profile
    )
    assert "FROM [dbo].[Orders] WHERE [CustomerId] IS NULL;" in ddl_mod
    assert "fila(s) con NULL" in ddl_mod
    assert "SET [CustomerId] = 0" not in ddl_mod

    ddl_filled = generate_ddl_for_profile(
        resolutions=[resolution("CustomerId", False, "7")], profile=profile
    )
    assert (
        "UPDATE [dbo].[Orders] SET [CustomerId] = CONVERT(int, N''7'')"
        " WHERE [CustomerId] IS NULL;" in ddl_filled
    )
    assert "IF TRY_CONVERT(int, N'7') IS NULL" in ddl_filled

    ddl_add = generate_ddl_for_profile(
        resolutions=[resolution("WarehouseId", True, "1")], profile=profile
    )
    for statement in (
        "ALTER TABLE [dbo].[Orders] ADD [WarehouseId] int NULL;",
        "UPDATE [dbo].[Orders] SET [WarehouseId] = CONVERT(int, N''1'') WHERE [WarehouseId] IS NULL;",
        "ALTER TABLE [dbo].[Orders] ALTER COLUMN [WarehouseId] int NOT NULL;",
    ):
        assert f"EXEC sys.sp_executesql N'{statement}';" in ddl_add
