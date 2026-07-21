"""Unit tests for Foreign Key and constraint dependency cleanup in SQL Server DDL rendering."""

from schema_comparator.compare.consolidation import (
    ColumnAttributes,
    ColumnDeletionResolution,
    ColumnResolution,
    NamedColumnAttributes,
    TableDeletionResolution,
    TableResolution,
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
    assert extract_database_name("Database = \" Production \";") == "Production"


def test_generate_ddl_table_deletion_cleans_foreign_keys() -> None:
    profile = ConnectionProfile(name="dev_db", connection_string="Database=TestDB;")
    table_deletions = [
        TableDeletionResolution(schema_name="dbo", table_name="Orders", profiles_to_update=("dev_db",)),
    ]

    ddl = generate_ddl_for_profile(
        resolutions=[],
        profile=profile,
        table_deletions=table_deletions,
    )

    assert "sys.foreign_keys" in ddl
    assert "DROP TABLE [dbo].[Orders];" in ddl
    assert "@fk_sql_t_0" in ddl
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
    assert "@col_fk_sql_c_0" in ddl
    assert "@idx_sql_c_0" in ddl
    assert "@chk_sql_c_0" in ddl
    assert "@def_sql_c_0" in ddl


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

    assert "PRINT 'Tabla [d''bo].[Order''s] creada con exito.';" in ddl
    assert "PRINT 'Columna [Age''s] agregada con exito a [d''bo].[User''s].';" in ddl


def test_generate_ddl_not_null_column_backfills_nulls() -> None:
    profile = ConnectionProfile(name="dev_db", connection_string="Database=TestDB;")
    not_null_attrs = ColumnAttributes(
        data_type="int",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    mod_res = [
        ColumnResolution(
            schema_name="dbo",
            table_name="Polizas",
            column_name="IdTomador",
            target_attributes=not_null_attrs,
            profiles_to_update=("dev_db",),
            is_missing_column=False,
        )
    ]
    add_res = [
        ColumnResolution(
            schema_name="dbo",
            table_name="Polizas",
            column_name="IdCobrador",
            target_attributes=not_null_attrs,
            profiles_to_update=("dev_db",),
            is_missing_column=True,
        )
    ]

    ddl_mod = generate_ddl_for_profile(resolutions=mod_res, profile=profile)
    assert "UPDATE [dbo].[Polizas]" in ddl_mod
    assert "SET [IdTomador] = 0" in ddl_mod
    assert "WHERE [IdTomador] IS NULL;" in ddl_mod
    assert "ALTER TABLE [dbo].[Polizas] ALTER COLUMN [IdTomador] int NOT NULL;" in ddl_mod

    ddl_add = generate_ddl_for_profile(resolutions=add_res, profile=profile)
    assert "ALTER TABLE [dbo].[Polizas] ADD [IdCobrador] int NOT NULL;" in ddl_add

