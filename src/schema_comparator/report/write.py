"""Orchestrate HTML/PDF/console report generation with per-format failure
isolation (REQ-reporting-and-output-007) and shared-timestamp naming
(REQ-reporting-and-output-002)."""

import sys
from datetime import datetime
from typing import Callable

from schema_comparator.compare.models import ComparisonResult
from schema_comparator.report.console import render_console
from schema_comparator.report.errors import PdfExportError
from schema_comparator.report.html import render_html
from schema_comparator.report.pdf import export_pdf


def _default_console_summary(result: ComparisonResult, *, out=sys.stdout) -> None:
    print(render_console(result), file=out)


def write_reports(
    result: ComparisonResult,
    *,
    out=sys.stdout,
    render_summary: Callable[[ComparisonResult], None] | None = None,
) -> None:
    """Always attempt all three outputs; one failing MUST NOT block the
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
        html_path = f"schema-diff-report-{timestamp}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_str)
        print(f"HTML report written: {html_path}", file=out)
    except Exception as exc:
        print(f"[ERROR] HTML report generation failed: {exc}", file=out)

    try:
        if html_str is None:
            raise PdfExportError("skipped: HTML rendering did not complete")
        pdf_bytes = export_pdf(html_str)
        pdf_path = f"schema-diff-report-{timestamp}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"PDF report written: {pdf_path}", file=out)
    except Exception as exc:
        print(f"[ERROR] PDF report generation failed: {exc}", file=out)

    try:
        effective_render_summary(result)
    except Exception as exc:
        print(f"[ERROR] Console summary generation failed: {exc}", file=out)
