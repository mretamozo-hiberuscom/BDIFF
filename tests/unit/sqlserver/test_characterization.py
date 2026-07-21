"""Characterization tests for SQL Server DDL generation and snapshot formatting.

These tests freeze the current SQL Server output behavior to ensure that
future refactorings (such as extracting the SQL Server provider or moving to
canonical models) do not alter the generated T-SQL output silently.
"""

import datetime
from pathlib import Path

from schema_comparator.compare.consolidation import (
    ColumnAttributes,
    ColumnResolution,
    NamedColumnAttributes,
    TableResolution,
    generate_ddl_for_profile,
)
from schema_comparator.config.models import ConnectionProfile

GOLDEN_DIR = Path(__file__).parents[2] / "fixtures" / "golden" / "sqlserver"


def test_characterization_add_column_ddl() -> None:
    """Verify generated ADD COLUMN T-SQL matches golden snapshot."""
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
        profiles_to_update=("profileA",),
        is_missing_column=True,
    )

    ts = datetime.datetime(2026, 7, 14, 12, 0, 0)
    profile_a = ConnectionProfile(name="profileA", connection_string="Database=real_db_a;")
    ddl = generate_ddl_for_profile([res], profile_a, timestamp=ts)

    golden_file = GOLDEN_DIR / "expected_add_column.sql"
    expected = golden_file.read_text(encoding="utf-8").strip()
    assert ddl.strip() == expected


def test_characterization_create_table_ddl() -> None:
    """Verify generated CREATE TABLE T-SQL matches golden snapshot."""
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
    ddl = generate_ddl_for_profile([], profile_b, timestamp=ts, table_resolutions=[tres])

    golden_file = GOLDEN_DIR / "expected_create_table.sql"
    expected = golden_file.read_text(encoding="utf-8").strip()
    assert ddl.strip() == expected
