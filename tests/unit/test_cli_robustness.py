"""CLI guard rails: confirmation and profile selection are checked before
any connection, known errors print a clean message, and the routine
exclusions reach the TUI."""

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest

from schema_comparator.application.use_cases.compare_profiles import (
    CompareProfilesUseCase,
)
from schema_comparator.cli import main
from schema_comparator.compare.errors import InsufficientSnapshotsError
from schema_comparator.config.errors import ConfigFileNotFoundError
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.errors import ConnectionFailedError


def _profiles(*names: str) -> list[ConnectionProfile]:
    return [ConnectionProfile(name=n, connection_string=f"DSN={n}") for n in names]


def test_refresh_without_yes_fails_before_loading_profiles(capsys) -> None:
    with patch("schema_comparator.cli.load_profiles") as m_load:
        code = main(["--config", "c.yaml", "--refresh-modules"])

    assert code == 2
    m_load.assert_not_called()
    assert "--yes" in capsys.readouterr().err


def test_unknown_profile_names_stop_before_comparing(capsys) -> None:
    with (
        patch(
            "schema_comparator.cli.load_profiles", return_value=_profiles("dev", "qa")
        ),
        patch("schema_comparator.cli.run_comparison") as m_run,
    ):
        code = main(["--config", "c.yaml", "--profiles", "dev", "prod"])

    assert code == 2
    m_run.assert_not_called()
    err = capsys.readouterr().err
    assert "prod" in err
    assert "dev, qa" in err


def test_profile_names_match_ignoring_case() -> None:
    fake_result = MagicMock(entries=())
    with (
        patch(
            "schema_comparator.cli.load_profiles",
            return_value=_profiles("dev", "qa", "prod"),
        ),
        patch(
            "schema_comparator.cli.run_comparison", return_value=fake_result
        ) as m_run,
        patch("schema_comparator.cli.write_reports"),
    ):
        code = main(["--config", "c.yaml", "--profiles", "DEV", "Qa"])

    assert code == 0
    assert [p.name for p in m_run.call_args.args[0]] == ["dev", "qa"]


@pytest.mark.parametrize(
    "error",
    [
        ConfigFileNotFoundError.at_path("c.yaml"),
        ConnectionFailedError.for_profile("dev"),
        InsufficientSnapshotsError.for_count(1),
    ],
)
def test_known_errors_print_a_clean_message(error, capsys) -> None:
    with patch("schema_comparator.cli.load_profiles", side_effect=error):
        code = main(["--config", "c.yaml"])

    assert code == 2
    err = capsys.readouterr().err
    assert err.startswith("[ERROR] ")
    assert "INESPERADO" not in err


def test_use_case_rejects_fewer_than_two_profiles_before_extracting() -> None:
    extractor = MagicMock()
    use_case = CompareProfilesUseCase(extractor=extractor)

    with pytest.raises(InsufficientSnapshotsError):
        use_case.execute(_profiles("dev"))

    extractor.assert_not_called()


def test_python_dash_m_package_propagates_exit_code(tmp_path) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "schema_comparator", "--config", "missing.yaml"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )

    assert completed.returncode == 2


def test_tui_receives_table_and_routine_exclusions() -> None:
    fake_result = MagicMock(entries=())
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles("a", "b")),
        patch("schema_comparator.cli.run_comparison", return_value=fake_result),
        patch("schema_comparator.cli.write_reports") as m_write,
        patch("sys.stdout.isatty", return_value=True),
        patch("sys.stdin.isatty", return_value=True),
    ):
        main(
            [
                "--config",
                "c.yaml",
                "--tui",
                "--exclude-tables",
                "LOG",
                "--exclude-routines",
                "tmp",
            ]
        )

    render_summary = m_write.call_args.kwargs["render_summary"]
    assert render_summary.keywords["exclude_patterns"] == ["LOG"]
    assert render_summary.keywords["exclude_routines"] == ["tmp"]
