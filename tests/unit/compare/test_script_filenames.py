"""Per-profile script file names: valid on Windows, unique regardless of
case, and cited exactly as written by the impact report."""

import datetime
from pathlib import Path

import pytest

from schema_comparator.compare.consolidation import (
    ColumnResolution,
    assign_script_filenames,
    generate_impact_report,
    sanitize_profile_filename,
    write_sql_scripts,
)
from schema_comparator.compare.models import ColumnAttributes
from schema_comparator.config.models import ConnectionProfile

_TS = datetime.datetime(2026, 10, 21, 12, 0, 0)


@pytest.mark.parametrize(
    ("profile_name", "expected"),
    [
        ("prod/db", "prod_db"),
        ("qa\\db", "qa_db"),
        ("con", "con_"),
        ("NUL", "NUL_"),
        ("com1", "com1_"),
        ("LPT9", "LPT9_"),
        ("polizas. ", "polizas"),
        ("a:b*c", "a_b_c"),
        ("...", "profile"),
    ],
)
def test_sanitize_profile_filename_is_valid_on_windows(
    profile_name: str, expected: str
) -> None:
    assert sanitize_profile_filename(profile_name) == expected


def test_assign_script_filenames_is_unique_ignoring_case() -> None:
    names = assign_script_filenames(["Dev", "dev", "prod/db", "prod_db"])

    assert names == {
        "Dev": "Dev",
        "dev": "dev_1",
        "prod/db": "prod_db",
        "prod_db": "prod_db_1",
    }


def _resolution(profiles: list[str]) -> ColumnResolution:
    return ColumnResolution(
        schema_name="dbo",
        table_name="Poliza",
        column_name="Prima",
        target_attributes=ColumnAttributes(
            data_type="decimal",
            character_maximum_length=None,
            numeric_precision=10,
            numeric_scale=2,
            is_nullable=False,
        ),
        profiles_to_update=tuple(profiles),
        is_missing_column=True,
    )


def test_impact_report_cites_the_written_file_names(tmp_path) -> None:
    profiles = [
        ConnectionProfile(name="Dev", connection_string="Database=A;"),
        ConnectionProfile(name="dev", connection_string="Database=B;"),
    ]

    written = write_sql_scripts(
        [_resolution(["Dev", "dev"])], tmp_path, profiles, timestamp=_TS
    )

    sql_names = sorted(Path(p).name for p in written if p.endswith(".sql"))
    assert sql_names == [
        "Dev.deshacer.sql",
        "Dev.sql",
        "dev_1.deshacer.sql",
        "dev_1.sql",
    ]
    report = (
        tmp_path / "scripts-db" / "20261021_120000" / "impact_report.md"
    ).read_text(encoding="utf-8")
    assert "`Dev.sql`" in report
    assert "`dev_1.sql`" in report


def test_impact_report_defaults_to_assigned_names() -> None:
    report = generate_impact_report([_resolution(["a/b"])], ["a/b"], timestamp=_TS)

    assert "`a_b.sql`" in report
