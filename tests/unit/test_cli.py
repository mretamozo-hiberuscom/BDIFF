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
    m_write.assert_called_once_with(fake_result, generate_reports=True)


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

    m_write.assert_called_once_with(
        fake_result, render_summary=run_tui, generate_reports=False
    )


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

    m_write.assert_called_once_with(fake_result, generate_reports=True)
    captured = capsys.readouterr()
    assert "--tui requiere una terminal interactiva" in captured.err


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


def test_exclude_tables_flag_defaults_to_none() -> None:
    args = build_arg_parser().parse_args(["--config", "config.local.yaml"])

    assert args.exclude_tables is None


def test_exclude_tables_filters_snapshots_before_comparing() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.extract_schema", side_effect=lambda p: p),
        patch(
            "schema_comparator.cli.filter_excluded_tables",
            side_effect=lambda snapshot, patterns: snapshot,
        ) as m_filter,
        patch("schema_comparator.cli.compare_snapshots", return_value=fake_result),
        patch("schema_comparator.cli.write_reports"),
    ):
        main(
            [
                "--config",
                "config.local.yaml",
                "--exclude-tables",
                "LOG",
                "QRTZ",
            ]
        )

    assert m_filter.call_count == 2
    for call in m_filter.call_args_list:
        assert call.args[1] == ["LOG", "QRTZ"]


def test_no_exclude_tables_flag_skips_filtering() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.extract_schema", side_effect=lambda p: p),
        patch("schema_comparator.cli.filter_excluded_tables") as m_filter,
        patch("schema_comparator.cli.compare_snapshots", return_value=fake_result),
        patch("schema_comparator.cli.write_reports"),
    ):
        main(["--config", "config.local.yaml"])

    m_filter.assert_not_called()


def test_tui_on_tty_calls_write_reports_with_generate_reports_false() -> None:
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

    assert m_write.call_args.kwargs["generate_reports"] is False


def test_tui_on_non_tty_calls_write_reports_with_generate_reports_true() -> None:
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

    assert m_write.call_args.kwargs["generate_reports"] is True


def test_no_tui_calls_write_reports_with_generate_reports_true() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.extract_schema", side_effect=lambda p: p),
        patch("schema_comparator.cli.compare_snapshots", return_value=fake_result),
        patch("schema_comparator.cli.write_reports") as m_write,
    ):
        main(["--config", "config.local.yaml"])

    assert m_write.call_args.kwargs["generate_reports"] is True

