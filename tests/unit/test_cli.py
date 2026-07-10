"""Unit tests for cli.main: argparse wiring and write_reports dispatch."""

from unittest.mock import MagicMock, patch

from schema_comparator.cli import build_arg_parser, main
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.tui import run_tui


def _profiles():
    return [
        ConnectionProfile(name="a", connection_string="DSN=a"),
        ConnectionProfile(name="b", connection_string="DSN=b"),
    ]


def test_cli_main_invokes_write_reports_after_compare_snapshots() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()) as m_load,
        patch("schema_comparator.cli.extract_schema", side_effect=lambda p: p) as m_extract,
        patch(
            "schema_comparator.cli.compare_snapshots", return_value=fake_result
        ) as m_compare,
        patch("schema_comparator.cli.write_reports") as m_write,
    ):
        main(["--config", "config.local.yaml"])

    m_load.assert_called_once_with("config.local.yaml")
    assert m_extract.call_count == 2
    m_compare.assert_called_once()
    m_write.assert_called_once_with(fake_result)


def test_cli_main_filters_profiles_when_profiles_flag_given() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.extract_schema", side_effect=lambda p: p) as m_extract,
        patch("schema_comparator.cli.compare_snapshots", return_value=fake_result),
        patch("schema_comparator.cli.write_reports"),
    ):
        main(["--config", "config.local.yaml", "--profiles", "a"])

    assert m_extract.call_count == 1
    assert m_extract.call_args[0][0].name == "a"


def test_tui_flag_defaults_to_false() -> None:
    args = build_arg_parser().parse_args(["--config", "config.local.yaml"])

    assert args.tui is False


def test_tui_flag_on_tty_passes_run_tui_as_render_summary() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.extract_schema", side_effect=lambda p: p),
        patch("schema_comparator.cli.compare_snapshots", return_value=fake_result),
        patch("schema_comparator.cli.write_reports") as m_write,
        patch("sys.stdout.isatty", return_value=True),
        patch("sys.stdin.isatty", return_value=True),
    ):
        main(["--config", "config.local.yaml", "--tui"])

    m_write.assert_called_once_with(fake_result, render_summary=run_tui)


def test_tui_flag_on_non_tty_prints_warning_and_uses_default_renderer(capsys) -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.extract_schema", side_effect=lambda p: p),
        patch("schema_comparator.cli.compare_snapshots", return_value=fake_result),
        patch("schema_comparator.cli.write_reports") as m_write,
        patch("sys.stdout.isatty", return_value=False),
        patch("sys.stdin.isatty", return_value=True),
    ):
        main(["--config", "config.local.yaml", "--tui"])

    m_write.assert_called_once_with(fake_result)
    captured = capsys.readouterr()
    assert "--tui requires an interactive terminal" in captured.err


def test_tui_flag_on_non_tty_exit_code_is_zero() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.extract_schema", side_effect=lambda p: p),
        patch("schema_comparator.cli.compare_snapshots", return_value=fake_result),
        patch("schema_comparator.cli.write_reports"),
        patch("sys.stdout.isatty", return_value=False),
        patch("sys.stdin.isatty", return_value=False),
    ):
        main(["--config", "config.local.yaml", "--tui"])  # must not raise
