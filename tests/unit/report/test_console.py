"""Unit tests for report.console: render_console (pure text, no I/O)."""

from report.conftest import comparison_result_empty, comparison_result_with_findings

from schema_comparator.report.console import render_console


def test_render_console_reports_counts_by_diff_category() -> None:
    output = render_console(comparison_result_with_findings())

    assert "Tablas faltantes: 1" in output
    assert "Columnas faltantes: 1" in output
    assert "Discrepancias de columnas: 1" in output


def test_render_console_lists_compared_profiles_and_per_table_breakdown() -> None:
    output = render_console(comparison_result_with_findings())

    assert "a, b, c" in output
    assert "sales.Invoice" in output
    assert "sales.Payment" in output


def test_render_console_no_drift_message_on_empty_entries_without_zero_counts() -> None:
    output = render_console(comparison_result_empty())

    assert "No se detectaron diferencias entre los perfiles comparados." in output
    assert "0" not in output


def test_render_console_is_independent_of_html_and_pdf_modules() -> None:
    import schema_comparator.report.console as console_module

    with open(console_module.__file__, encoding="utf-8") as f:
        source = f.read()

    assert "jinja2" not in source.lower()
    assert "xhtml2pdf" not in source.lower()
