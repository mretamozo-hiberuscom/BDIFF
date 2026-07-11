"""Unit tests for report.write: write_reports failure isolation and
timestamped naming (mocked render_html/export_pdf/render_console)."""

import io
import re

from report.conftest import comparison_result_with_findings

from schema_comparator.report.write import write_reports


def test_write_reports_html_failure_still_attempts_pdf_and_console(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "schema_comparator.report.write.render_html",
        lambda result: (_ for _ in ()).throw(RuntimeError("html boom")),
    )
    out = io.StringIO()

    write_reports(comparison_result_with_findings(), out=out)

    output = out.getvalue()
    assert "[ERROR] Falló la generación del reporte HTML" in output
    assert "Reporte de Diferencias de Esquema - Resumen de Consola" in output


def test_write_reports_pdf_failure_still_leaves_html_written_and_console_printed(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    from schema_comparator.report.errors import PdfExportError

    monkeypatch.setattr(
        "schema_comparator.report.write.export_pdf",
        lambda html: (_ for _ in ()).throw(PdfExportError("pdf boom")),
    )
    out = io.StringIO()

    write_reports(comparison_result_with_findings(), out=out)

    output = out.getvalue()
    assert "[ERROR] Falló la generación del reporte PDF" in output
    html_files = list(tmp_path.glob("schema-diff-report-*.html"))
    assert len(html_files) == 1
    assert "Reporte de Diferencias de Esquema - Resumen de Consola" in output


def test_write_reports_console_failure_still_leaves_html_and_pdf_written(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "schema_comparator.report.write.render_console",
        lambda result: (_ for _ in ()).throw(RuntimeError("console boom")),
    )
    out = io.StringIO()

    write_reports(comparison_result_with_findings(), out=out)

    output = out.getvalue()
    assert "[ERROR] Falló la generación del resumen de consola" in output
    assert list(tmp_path.glob("schema-diff-report-*.html"))
    assert list(tmp_path.glob("schema-diff-report-*.pdf"))


def test_write_reports_never_raises_past_the_function_boundary(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "schema_comparator.report.write.render_html",
        lambda result: (_ for _ in ()).throw(RuntimeError("html boom")),
    )
    monkeypatch.setattr(
        "schema_comparator.report.write.render_console",
        lambda result: (_ for _ in ()).throw(RuntimeError("console boom")),
    )
    out = io.StringIO()

    write_reports(comparison_result_with_findings(), out=out)  # must not raise


def test_write_reports_html_and_pdf_filenames_share_the_same_timestamp(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()

    write_reports(comparison_result_with_findings(), out=out)

    html_file = next(tmp_path.glob("schema-diff-report-*.html"))
    pdf_file = next(tmp_path.glob("schema-diff-report-*.pdf"))
    html_ts = re.search(r"schema-diff-report-(.+)\.html", html_file.name).group(1)
    pdf_ts = re.search(r"schema-diff-report-(.+)\.pdf", pdf_file.name).group(1)
    assert html_ts == pdf_ts


def test_write_reports_writes_to_the_current_working_directory(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()

    write_reports(comparison_result_with_findings(), out=out)

    assert list(tmp_path.glob("schema-diff-report-*.html"))
    assert list(tmp_path.glob("schema-diff-report-*.pdf"))


def test_write_reports_default_render_summary_matches_prior_console_output(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()

    write_reports(comparison_result_with_findings(), out=out)

    assert "Reporte de Diferencias de Esquema - Resumen de Consola" in out.getvalue()


def test_write_reports_calls_custom_render_summary_when_provided(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()
    received = []

    write_reports(
        comparison_result_with_findings(),
        out=out,
        render_summary=received.append,
    )

    assert len(received) == 1
    assert received[0] == comparison_result_with_findings()
    assert "Schema Drift Report - Console Summary" not in out.getvalue()


def test_write_reports_isolates_render_summary_failure_from_html_pdf(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()

    def _boom(result):
        raise RuntimeError("summary boom")

    write_reports(
        comparison_result_with_findings(), out=out, render_summary=_boom
    )

    output = out.getvalue()
    assert "[ERROR] Fall\u00f3 la generaci\u00f3n del resumen de consola" in output
    assert list(tmp_path.glob("schema-diff-report-*.html"))
    assert list(tmp_path.glob("schema-diff-report-*.pdf"))
