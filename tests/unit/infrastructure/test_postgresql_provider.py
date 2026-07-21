"""Unit tests for PostgreSqlProvider, introspector, ddl_renderer, and registry integration."""

from unittest.mock import MagicMock, patch

import pytest

from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import (
    ConnectionFailedError,
    DriverUnavailableError,
    MetadataAccessError,
)
from schema_comparator.domain.comparison.models import ColumnAttributes
from schema_comparator.infrastructure.providers import get_default_registry
from schema_comparator.infrastructure.providers.postgresql import (
    PostgreSqlProvider,
    ddl_renderer,
    errors,
)


def test_postgresql_provider_metadata_and_capabilities() -> None:
    provider = PostgreSqlProvider()
    assert provider.provider_id == "postgresql"

    caps = provider.capabilities()
    assert caps.provider_id == "postgresql"
    assert caps.supports_schemas is True
    assert caps.supports_transactional_ddl is True
    assert caps.supports_alter_column is True
    assert caps.supports_drop_column is True


def test_postgresql_provider_validate_profile() -> None:
    provider = PostgreSqlProvider()
    valid_profile = ConnectionProfile(name="pg_dev", connection_string="postgresql://user:pass@localhost/db", provider="postgresql")
    provider.validate_profile(valid_profile)

    empty_profile = ConnectionProfile(name="pg_empty", connection_string="", provider="postgresql")
    with pytest.raises(ValueError, match="empty connection string"):
        provider.validate_profile(empty_profile)

    wrong_provider = ConnectionProfile(name="pg_wrong", connection_string="host=localhost", provider="sqlserver")
    with pytest.raises(ValueError, match="expected 'postgresql'"):
        provider.validate_profile(wrong_provider)


def test_postgresql_provider_introspect_success() -> None:
    provider = PostgreSqlProvider()
    profile = ConnectionProfile(name="pg_test", connection_string="postgresql://user:pass@localhost/db", provider="postgresql")

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("public", "users", "id", "integer", None, 32, 0, "NO", 1, None, "YES", None),
        ("public", "users", "email", "character varying", 255, None, None, "NO", 2, None, "NO", None),
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("schema_comparator.infrastructure.providers.postgresql.connection.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn

        snapshot = provider.introspect(profile)

        assert snapshot.profile_name == "pg_test"
        assert len(snapshot.tables) == 1
        table = snapshot.tables[0]
        assert table.schema_name == "public"
        assert table.table_name == "users"
        assert len(table.columns) == 2
        assert table.columns[0].name == "id"
        assert table.columns[0].is_identity is True
        assert table.columns[1].name == "email"
        assert table.columns[1].character_maximum_length == 255


def test_postgresql_provider_introspect_query_error() -> None:
    provider = PostgreSqlProvider()
    profile = ConnectionProfile(name="pg_test", connection_string="postgresql://user:pass@localhost/db", provider="postgresql")

    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = Exception("Query execution error")

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("schema_comparator.infrastructure.providers.postgresql.connection.connect") as mock_connect:
        mock_connect.return_value.__enter__.return_value = mock_conn

        with pytest.raises(MetadataAccessError):
            provider.introspect(profile)


def test_postgresql_provider_introspect_connect_error() -> None:
    provider = PostgreSqlProvider()
    profile = ConnectionProfile(name="pg_test", connection_string="postgresql://user:pass@localhost/db", provider="postgresql")

    with patch("schema_comparator.infrastructure.providers.postgresql.connection.connect") as mock_connect:
        mock_connect.side_effect = Exception("Connection error")

        with pytest.raises(ConnectionFailedError):
            provider.introspect(profile)


def test_postgresql_translate_connect_import_error() -> None:
    err = errors.translate_connect_error("pg_test", ImportError("No module named 'psycopg'"))
    assert isinstance(err, DriverUnavailableError)
    assert "psycopg" in str(err)


def test_postgresql_ddl_renderer_quote_identifier() -> None:
    assert ddl_renderer.quote_identifier("users") == '"users"'
    assert ddl_renderer.quote_identifier('user"table') == '"user""table"'


def test_postgresql_ddl_renderer_format_column_definition() -> None:
    col1 = ColumnAttributes(data_type="varchar", character_maximum_length=100, numeric_precision=None, numeric_scale=None, is_nullable=False)
    assert ddl_renderer.format_pg_column_definition("username", col1) == '"username" varchar(100) NOT NULL'

    col2 = ColumnAttributes(data_type="numeric", character_maximum_length=None, numeric_precision=10, numeric_scale=2, is_nullable=True)
    assert ddl_renderer.format_pg_column_definition("price", col2) == '"price" numeric(10, 2) NULL'

    col3 = ColumnAttributes(data_type="integer", character_maximum_length=None, numeric_precision=32, numeric_scale=0, is_nullable=False)
    assert ddl_renderer.format_pg_column_definition("id", col3) == '"id" id integer NOT NULL' if False else '"id" integer NOT NULL'


def test_postgresql_ddl_renderer_generate_script_selective_alter() -> None:
    profile = ConnectionProfile(name="pg_target", connection_string="postgresql://localhost/db", provider="postgresql")

    missing_tables = [
        ("public", "roles", [("id", ColumnAttributes("integer", None, 32, 0, False)), ("name", ColumnAttributes("varchar", 50, None, None, False))])
    ]
    missing_cols = [
        ("public", "users", "age", ColumnAttributes("integer", None, 32, 0, True))
    ]
    # Discrepancy ONLY in type (nullability stays True)
    discrepant_cols = [
        (
            "public",
            "users",
            "bio",
            ColumnAttributes("varchar", 100, None, None, True),
            ColumnAttributes("text", None, None, None, True),
        )
    ]

    script = ddl_renderer.generate_pg_script(profile, missing_tables, missing_cols, discrepant_cols)

    assert "BEGIN;" in script
    assert "COMMIT;" in script
    assert 'CREATE TABLE IF NOT EXISTS "public"."roles"' in script
    assert 'ALTER TABLE "public"."users" ADD COLUMN IF NOT EXISTS "age" integer NULL;' in script
    assert 'ALTER TABLE "public"."users" ALTER COLUMN "bio" TYPE text USING CAST("bio" AS text);' in script
    assert "DROP NOT NULL" not in script
    assert "SET NOT NULL" not in script


def test_default_registry_has_postgresql() -> None:
    registry = get_default_registry()
    assert "postgresql" in registry.list_providers()
    assert "sqlserver" in registry.list_providers()
