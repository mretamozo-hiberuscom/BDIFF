"""Unit tests for SqliteProvider, introspector, ddl_renderer, and registry integration."""

import sqlite3
import pytest

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ColumnAttributes
from schema_comparator.infrastructure.providers import get_default_registry
from schema_comparator.infrastructure.providers.sqlite import (
    SqliteProvider,
    ddl_renderer,
)


def test_sqlite_provider_metadata_and_capabilities() -> None:
    provider = SqliteProvider()
    assert provider.provider_id == "sqlite"

    caps = provider.capabilities()
    assert caps.provider_id == "sqlite"
    assert caps.supports_schemas is False
    assert caps.supports_transactional_ddl is True
    assert caps.supports_drop_column is True
    assert caps.supports_alter_column is False


def test_sqlite_provider_validate_profile() -> None:
    provider = SqliteProvider()
    valid_profile = ConnectionProfile(name="sqlite_dev", connection_string=":memory:", provider="sqlite")
    provider.validate_profile(valid_profile)

    empty_profile = ConnectionProfile(name="sqlite_empty", connection_string="", provider="sqlite")
    with pytest.raises(ValueError, match="empty connection string"):
        provider.validate_profile(empty_profile)

    wrong_provider = ConnectionProfile(name="sqlite_wrong", connection_string=":memory:", provider="postgres")
    with pytest.raises(ValueError, match="expected 'sqlite'"):
        provider.validate_profile(wrong_provider)


def test_sqlite_provider_introspect_in_memory() -> None:
    provider = SqliteProvider()
    profile = ConnectionProfile(name="sqlite_test", connection_string=":memory:", provider="sqlite")

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL, email VARCHAR(255) NULL)")
    cursor.close()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("schema_comparator.infrastructure.providers.sqlite.connection.connect", lambda prof, **kw: conn)
        snapshot = provider.introspect(profile)

    assert snapshot.profile_name == "sqlite_test"
    assert len(snapshot.tables) == 1
    table = snapshot.tables[0]
    assert table.schema_name == "main"
    assert table.table_name == "users"
    assert len(table.columns) == 3
    assert table.columns[0].name == "id"
    assert table.columns[0].is_identity is True
    assert table.columns[1].name == "username"
    assert table.columns[1].is_nullable is False
    assert table.columns[2].name == "email"
    assert table.columns[2].character_maximum_length == 255


def test_sqlite_ddl_renderer_quote_identifier() -> None:
    assert ddl_renderer.quote_identifier("users") == '"users"'
    assert ddl_renderer.quote_identifier('user"table') == '"user""table"'


def test_sqlite_ddl_renderer_format_column_definition() -> None:
    col1 = ColumnAttributes(data_type="VARCHAR", character_maximum_length=100, numeric_precision=None, numeric_scale=None, is_nullable=False)
    assert ddl_renderer.format_sqlite_column_definition("username", col1) == '"username" VARCHAR(100) NOT NULL'

    col2 = ColumnAttributes(data_type="NUMERIC", character_maximum_length=None, numeric_precision=10, numeric_scale=2, is_nullable=True)
    assert ddl_renderer.format_sqlite_column_definition("price", col2) == '"price" NUMERIC(10, 2) NULL'

    col3 = ColumnAttributes(data_type="INTEGER", character_maximum_length=None, numeric_precision=32, numeric_scale=0, is_nullable=False)
    assert ddl_renderer.format_sqlite_column_definition("id", col3) == '"id" INTEGER NOT NULL'


def test_sqlite_ddl_renderer_generate_script() -> None:
    profile = ConnectionProfile(name="sqlite_target", connection_string=":memory:", provider="sqlite")

    missing_tables = [
        ("main", "roles", [("id", ColumnAttributes("INTEGER", None, 32, 0, False)), ("name", ColumnAttributes("TEXT", 50, None, None, False))])
    ]
    missing_cols = [
        ("main", "users", "age", ColumnAttributes("INTEGER", None, 32, 0, True))
    ]
    discrepant_cols = [
        (
            "main",
            "users",
            "bio",
            ColumnAttributes("TEXT", 100, None, None, True),
            ColumnAttributes("TEXT", None, None, None, True),
        )
    ]

    script = ddl_renderer.generate_sqlite_script(profile, missing_tables, missing_cols, discrepant_cols)

    assert "BEGIN TRANSACTION;" in script
    assert "COMMIT;" in script
    assert 'CREATE TABLE IF NOT EXISTS "roles"' in script
    assert 'ALTER TABLE "users" ADD COLUMN "age" INTEGER NULL;' in script
    assert 'CREATE TABLE "users_dg_tmp" AS SELECT * FROM "users";' in script
    assert 'DROP TABLE "users";' in script
    assert 'ALTER TABLE "users_dg_tmp" RENAME TO "users";' in script


def test_default_registry_has_sqlite() -> None:
    registry = get_default_registry()
    assert "sqlite" in registry.list_providers()
    assert "postgresql" in registry.list_providers()
    assert "sqlserver" in registry.list_providers()
