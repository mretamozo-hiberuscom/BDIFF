"""Unit tests for cli.main: argparse wiring and write_reports dispatch."""

from unittest.mock import MagicMock, patch

from schema_comparator.cli import build_arg_parser, main
from schema_comparator.config.models import ConnectionProfile


def _profiles():
    return [
        ConnectionProfile(name="a", connection_string="DSN=a"),
        ConnectionProfile(name="b", connection_string="DSN=b"),
    ]


def test_cli_main_invokes_write_reports_after_run_comparison() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()) as m_load,
        patch(
            "schema_comparator.cli.run_comparison", return_value=fake_result
        ) as m_run_comparison,
        patch("schema_comparator.cli.write_reports") as m_write,
    ):
        main(["--config", "config.local.yaml"])

    m_load.assert_called_once_with("config.local.yaml")
    m_run_comparison.assert_called_once_with(_profiles(), [])
    m_write.assert_called_once_with(fake_result, generate_reports=True)


def test_cli_main_filters_profiles_when_profiles_flag_given() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch(
            "schema_comparator.cli.run_comparison", return_value=fake_result
        ) as m_run_comparison,
        patch("schema_comparator.cli.write_reports"),
    ):
        main(["--config", "config.local.yaml", "--profiles", "a"])

    called_profiles = m_run_comparison.call_args[0][0]
    assert [p.name for p in called_profiles] == ["a"]


def test_main_deduplicates_extract_filter_compare_via_run_comparison() -> None:
    """main() delegates the extract/filter/compare sequence to
    tui.actions.run_comparison instead of inlining it, so the CLI and the
    TUI's re-run action can never diverge (design §2)."""
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch(
            "schema_comparator.cli.run_comparison", return_value=fake_result
        ) as m_run_comparison,
        patch("schema_comparator.cli.write_reports"),
    ):
        main(["--config", "config.local.yaml"])

    m_run_comparison.assert_called_once()


def test_tui_flag_defaults_to_false() -> None:
    args = build_arg_parser().parse_args(["--config", "config.local.yaml"])

    assert args.tui is False


def test_tui_flag_on_tty_passes_run_tui_as_render_summary() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.run_comparison", return_value=fake_result),
        patch("schema_comparator.cli.write_reports") as m_write,
        patch("schema_comparator.cli.run_tui") as m_run_tui,
        patch("sys.stdout.isatty", return_value=True),
        patch("sys.stdin.isatty", return_value=True),
    ):
        main(["--config", "config.local.yaml", "--tui"])

    assert m_write.call_args.kwargs["generate_reports"] is False
    render_summary = m_write.call_args.kwargs["render_summary"]
    # `render_summary` must be `run_tui` bound with this run's `profiles`
    # and `exclude_patterns` (a bare `run_tui` reference would call it
    # with empty defaults, leaving the TUI's "run"/"generate reports"
    # actions with no profiles to work with).
    render_summary(fake_result)
    m_run_tui.assert_called_once_with(
        fake_result, profiles=_profiles(), exclude_patterns=[]
    )


def test_tui_flag_on_non_tty_prints_warning_and_uses_default_renderer(capsys) -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.run_comparison", return_value=fake_result),
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
        patch("schema_comparator.cli.run_comparison", return_value=fake_result),
        patch("schema_comparator.cli.write_reports"),
        patch("sys.stdout.isatty", return_value=False),
        patch("sys.stdin.isatty", return_value=False),
    ):
        main(["--config", "config.local.yaml", "--tui"])  # must not raise


def test_exclude_tables_flag_defaults_to_none() -> None:
    args = build_arg_parser().parse_args(["--config", "config.local.yaml"])

    assert args.exclude_tables is None


def test_exclude_tables_flag_passes_patterns_to_run_comparison() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch(
            "schema_comparator.cli.run_comparison", return_value=fake_result
        ) as m_run_comparison,
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

    assert m_run_comparison.call_args[0][1] == ["LOG", "QRTZ"]


def test_no_exclude_tables_flag_passes_empty_list_to_run_comparison() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch(
            "schema_comparator.cli.run_comparison", return_value=fake_result
        ) as m_run_comparison,
        patch("schema_comparator.cli.write_reports"),
    ):
        main(["--config", "config.local.yaml"])

    assert m_run_comparison.call_args[0][1] == []


def test_tui_on_tty_calls_write_reports_with_generate_reports_false() -> None:
    fake_result = MagicMock(name="ComparisonResult")
    with (
        patch("schema_comparator.cli.load_profiles", return_value=_profiles()),
        patch("schema_comparator.cli.run_comparison", return_value=fake_result),
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
        patch("schema_comparator.cli.run_comparison", return_value=fake_result),
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
        patch("schema_comparator.cli.run_comparison", return_value=fake_result),
        patch("schema_comparator.cli.write_reports") as m_write,
    ):
        main(["--config", "config.local.yaml"])

    assert m_write.call_args.kwargs["generate_reports"] is True

