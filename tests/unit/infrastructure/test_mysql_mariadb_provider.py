"""Unit tests for MySQL and MariaDB providers."""

import pytest

from schema_comparator.config.errors import ProfileValidationError
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.domain.comparison.models import ColumnAttributes
from schema_comparator.infrastructure.providers.mariadb import MariaDbProvider
from schema_comparator.infrastructure.providers.mysql import MySqlProvider
from schema_comparator.infrastructure.providers.mysql_family.ddl_renderer import (
    format_mysql_data_type,
    generate_mysql_script,
    quote_identifier,
)
from schema_comparator.infrastructure.providers.mysql_family.introspector import (
    build_snapshot,
)
from schema_comparator.infrastructure.providers.mysql_family.profile_parser import (
    parse_mysql_family_options,
    validate_mysql_family_profile,
)
from schema_comparator.infrastructure.providers.registry import get_default_registry


def test_mysql_and_mariadb_registration():
    registry = get_default_registry()
    assert "mysql" in registry.list_providers()
    assert "mariadb" in registry.list_providers()

    mysql_p = registry.require("mysql")
    assert isinstance(mysql_p, MySqlProvider)
    assert mysql_p.provider_id == "mysql"

    mariadb_p = registry.require("mariadb")
    assert isinstance(mariadb_p, MariaDbProvider)
    assert mariadb_p.provider_id == "mariadb"


def test_mysql_capabilities():
    p = MySqlProvider()
    caps = p.capabilities()
    assert caps.provider_id == "mysql"
    assert caps.supports_drop_column is True
    assert caps.supports_alter_column is True


def test_quote_identifier():
    assert quote_identifier("users") == "`users`"
    assert quote_identifier("user`name") == "`user``name`"


def test_profile_validation_and_parsing():
    valid_profile = ConnectionProfile(
        name="my_db",
        connection_string="Server=localhost;Port=3306;Database=app;Uid=root;Pwd=secret;",
    )
    validate_mysql_family_profile(valid_profile, "mysql")
    opts = parse_mysql_family_options(valid_profile)
    assert opts["host"] == "localhost"
    assert opts["port"] == 3306
    assert opts["database"] == "app"
    assert opts["user"] == "root"
    assert opts["password"] == "secret"

    invalid_port_profile = ConnectionProfile(
        name="bad_port", connection_string="Server=localhost;Port=invalid;"
    )
    with pytest.raises(ProfileValidationError):
        parse_mysql_family_options(invalid_port_profile)


def test_introspector_build_snapshot():
    rows = [
        (
            "app_db",
            "users",
            "id",
            "int",
            None,
            10,
            0,
            "NO",
            1,
            None,
            "auto_increment",
            None,
        ),
        (
            "app_db",
            "users",
            "email",
            "varchar",
            255,
            None,
            None,
            "YES",
            2,
            None,
            "",
            "utf8mb4_unicode_ci",
        ),
    ]
    snapshot = build_snapshot("mysql_profile", rows)
    assert snapshot.profile_name == "mysql_profile"
    assert len(snapshot.tables) == 1
    t = snapshot.tables[0]
    assert t.table_name == "users"
    assert len(t.columns) == 2
    assert t.columns[0].name == "id"
    assert t.columns[0].is_identity is True
    assert t.columns[1].name == "email"
    assert t.columns[1].is_nullable is True


def test_enum_and_datetime_data_type_formatting():
    enum_attrs = ColumnAttributes(
        data_type="ENUM('active','inactive')",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    assert format_mysql_data_type(enum_attrs) == "ENUM('active','inactive')"

    dt_attrs = ColumnAttributes(
        data_type="DATETIME(6)",
        character_maximum_length=None,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=True,
    )
    assert format_mysql_data_type(dt_attrs) == "DATETIME(6)"


def test_generate_mysql_script():
    profile = ConnectionProfile(
        name="dev_mysql", connection_string="Server=localhost;", provider="mysql"
    )
    col_attrs = ColumnAttributes(
        data_type="varchar",
        character_maximum_length=100,
        numeric_precision=None,
        numeric_scale=None,
        is_nullable=False,
    )
    missing_tables = [
        (
            "app_db",
            "orders",
            [
                (
                    "id",
                    ColumnAttributes(
                        data_type="int",
                        character_maximum_length=None,
                        numeric_precision=10,
                        numeric_scale=0,
                        is_nullable=False,
                    ),
                )
            ],
        ),
    ]
    missing_cols = [
        (
            "app_db",
            "users",
            "age",
            ColumnAttributes(
                data_type="int",
                character_maximum_length=None,
                numeric_precision=10,
                numeric_scale=0,
                is_nullable=True,
            ),
        )
    ]
    discrepant_cols = [
        (
            "app_db",
            "users",
            "email",
            ColumnAttributes(
                data_type="varchar",
                character_maximum_length=50,
                numeric_precision=None,
                numeric_scale=None,
                is_nullable=True,
            ),
            col_attrs,
        )
    ]

    script = generate_mysql_script(
        profile, missing_tables, missing_cols, discrepant_cols
    )
    assert "CREATE TABLE IF NOT EXISTS `app_db`.`orders`" in script
    assert "ALTER TABLE `app_db`.`users` ADD COLUMN `age` int NULL;" in script
    assert (
        "ALTER TABLE `app_db`.`users` MODIFY COLUMN `email` varchar(100) NOT NULL;"
        in script
    )
    assert "SET FOREIGN_KEY_CHECKS = 0;" in script


def _mysql_row(schema, table):
    return (schema, table, "id", "int", None, 10, 0, "NO", 1, None, "", None)


def test_single_database_snapshot_declares_it_as_default_schema():
    snapshot = build_snapshot("p", [_mysql_row("app_dev", "poliza")])

    assert snapshot.default_schema == "app_dev"


def test_multi_database_snapshot_has_no_default_schema():
    snapshot = build_snapshot(
        "p", [_mysql_row("app_dev", "poliza"), _mysql_row("audit", "log")]
    )

    assert snapshot.default_schema is None
