"""Orchestrate HTML/PDF/Excel/console report generation with per-format
failure isolation (REQ-reporting-and-output-007) and shared-timestamp
naming (REQ-reporting-and-output-002)."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

from schema_comparator.compare.models import ComparisonResult
from schema_comparator.report.console import render_console
from schema_comparator.report.errors import PdfExportError
from schema_comparator.report.excel import export_excel
from schema_comparator.report.html import render_html
from schema_comparator.report.pdf import export_pdf

_REPORTS_DIR = "reportes"


def _report_path(filename: str) -> str:
    """Ensure `_REPORTS_DIR` exists (relative to the current invocation
    cwd) and return the joined path for `filename` inside it."""
    Path(_REPORTS_DIR).mkdir(parents=True, exist_ok=True)
    return str(Path(_REPORTS_DIR) / filename)


def _default_console_summary(result: ComparisonResult, *, out=sys.stdout) -> None:
    print(render_console(result), file=out)


def write_reports(
    result: ComparisonResult,
    *,
    out=sys.stdout,
    render_summary: Callable[[ComparisonResult], None] | None = None,
) -> None:
    """Always attempt all four outputs; one failing MUST NOT block the
    others. Failures are printed to `out` as clearly labeled messages,
    never raised past this function.

    `render_summary`, when omitted, defaults to the plain console summary
    written to this call's `out` (not necessarily `sys.stdout`) — bound
    at call time rather than as a plain parameter default, so a caller
    overriding `out` without overriding `render_summary` still sees the
    console summary land in `out`."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    html_str: str | None = None
    effective_render_summary = (
        render_summary
        if render_summary is not None
        else (lambda result: _default_console_summary(result, out=out))
    )

    try:
        html_str = render_html(result)
        html_path = _report_path(f"schema-diff-report-{timestamp}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_str)
        print(f"Reporte HTML generado: {html_path}", file=out)
    except Exception as exc:
        print(f"[ERROR] Falló la generación del reporte HTML: {exc}", file=out)

    try:
        if html_str is None:
            raise PdfExportError("omitido: la generación de HTML no se completó")
        pdf_bytes = export_pdf(html_str)
        pdf_path = _report_path(f"schema-diff-report-{timestamp}.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"Reporte PDF generado: {pdf_path}", file=out)
    except Exception as exc:
        print(f"[ERROR] Falló la generación del reporte PDF: {exc}", file=out)

    try:
        xlsx_bytes = export_excel(result)
        xlsx_path = _report_path(f"schema-diff-report-{timestamp}.xlsx")
        with open(xlsx_path, "wb") as f:
            f.write(xlsx_bytes)
        print(f"Reporte Excel generado: {xlsx_path}", file=out)
    except Exception as exc:
        print(f"[ERROR] Falló la generación del reporte Excel: {exc}", file=out)

    try:
        effective_render_summary(result)
    except Exception as exc:
        print(f"[ERROR] Falló la generación del resumen de consola: {exc}", file=out)
