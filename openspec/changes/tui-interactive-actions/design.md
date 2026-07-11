Design: TUI Run & Report Actions

Change: `tui-interactive-actions`
Status: design (phase artifact)
Scope: three new interactive actions on top of the existing read-only
`SchemaComparatorApp` (in-memory exclude editing, re-run comparison,
on-demand report generation), plus the narrowly-scoped conditional
report-generation change in `cli.py`/`report/write.py`.

This design realizes the three new requirements
(REQ-interactive-tui-011/012/013) in
`openspec/changes/tui-interactive-actions/specs/interactive-tui/spec.md`,
the modified requirements in
`openspec/changes/tui-interactive-actions/specs/reporting-and-output/spec.md`,
and the five decisions in
`openspec/changes/tui-interactive-actions/proposal.md`. It builds on the
existing module layout from the archived `interactive-tui` change
(`src/schema_comparator/tui/{app,widgets,formatting}.py`).

---

## 1. Module / file layout

```text
src/schema_comparator/tui/
  app.py          # + new bindings (e, r, g), worker methods, status log wiring
  widgets.py      # + StatusLog (RichLog subclass), ExcludeEditor (Input wrapper)
  actions.py       # NEW: pure/thin orchestration -- run_comparison(), no Textual imports
  formatting.py    # unchanged

src/schema_comparator/report/
  write.py        # write_reports gains `generate_reports: bool = True`;
                   # HTML/PDF/Excel try/except blocks extracted into
                   # `generate_reports(result, *, out=...) -> None`

src/schema_comparator/cli.py
                   # _resolve_summary_renderer's tui-active branch also
                   # decides `generate_reports=False`; profiles + initial
                   # exclude patterns passed into SchemaComparatorApp
```

`actions.py` holds the one new piece of business logic this change
introduces (`run_comparison`) as a plain, Textual-independent function —
consistent with the existing `formatting.py` convention of keeping
pure/testable logic out of `app.py` and `widgets.py`.

## 2. `actions.run_comparison` — pure re-extraction/re-compare

```python
# tui/actions.py
from schema_comparator.compare.engine import compare_snapshots
from schema_comparator.compare.models import ComparisonResult
from schema_comparator.config.models import ConnectionProfile
from schema_comparator.discovery.filters import filter_excluded_tables
from schema_comparator.discovery.service import extract_schema


def run_comparison(
    profiles: list[ConnectionProfile], exclude_patterns: list[str]
) -> ComparisonResult:
    """Re-extract schemas for `profiles` and re-compare, applying
    `exclude_patterns` exactly as `cli.py`'s startup path already does.
    Raises on extraction/connection failure -- callers (the Textual
    worker in `app.py`) are responsible for catching and reporting it."""
    snapshots = [extract_schema(p) for p in profiles]
    if exclude_patterns:
        snapshots = [filter_excluded_tables(s, exclude_patterns) for s in snapshots]
    return compare_snapshots(snapshots)
```

- This mirrors `cli.py`'s existing startup sequence
  (`extract_schema` → `filter_excluded_tables` → `compare_snapshots`)
  exactly, so "run comparison from the TUI" cannot silently diverge from
  "run comparison from the CLI" — there is exactly one place
  (`run_comparison`) both now call into for this sequence; `cli.py`'s
  `main()` is updated to call it too, removing the duplicated three-line
  sequence (no behavior change to `main()`, pure de-duplication).
- No exception handling here: `run_comparison` is intentionally allowed to
  raise straight through (a connection/extraction error), matching
  `formatting.py`'s existing pure-function style (do one thing, let the
  caller decide how to react) — REQ-interactive-tui-012's "failure MUST
  NOT clear the previous result" behavior is a UI/state-management concern
  that belongs in `app.py`'s worker wrapper (§4), not in this function.

## 3. New widgets (`tui/widgets.py`)

```python
# tui/widgets.py (additions)
from textual.widgets import RichLog


class StatusLog(RichLog):
    """Append-only status/progress panel for run-comparison and
    generate-reports outcomes. Never receives raw stdout; only the
    explicit messages app.py's worker methods write to it."""

    def info(self, message: str) -> None:
        self.write(message)

    def error(self, message: str) -> None:
        self.write(f"[red]{message}[/red]")
```

```python
# tui/widgets.py (additions, continued)
from textual.widgets import Input


class ExcludeEditor(Input):
    """Input pre-seeded with the current exclude-pattern list, space-
    separated, matching --exclude-tables's existing CLI syntax."""

    def __init__(self, initial_patterns: list[str], **kwargs) -> None:
        super().__init__(value=" ".join(initial_patterns), **kwargs)
```

`ExcludeEditor` reuses `Input`'s existing `Input.Submitted` event
(fired on `Enter`) rather than introducing a new event type; `app.py`
listens for it the same way it already listens for the filter `Input`'s
`Input.Changed` (§4).

## 4. `app.py` — bindings, workers, wiring

```python
# tui/app.py (additions)
from textual.worker import Worker, WorkerState

from schema_comparator.tui.actions import run_comparison
from schema_comparator.report.write import generate_reports
import io


class SchemaComparatorApp(App):
    BINDINGS = [
        # ...existing q / escape / slash bindings...
        Binding("e", "focus_exclude_editor", "Excludes"),
        Binding("r", "run_comparison", "Run"),
        Binding("g", "generate_reports", "Reports"),
    ]

    def __init__(
        self,
        result: ComparisonResult,
        *,
        profiles: list[ConnectionProfile] | None = None,
        exclude_patterns: list[str] | None = None,
    ) -> None:
        super().__init__()
        self._result = result
        self._tree_data = build_tree_data(result)
        self._profiles = profiles or []
        self._exclude_patterns = list(exclude_patterns or [])

    def compose(self) -> ComposeResult:
        # ...existing header / filter-input / tree / detail-panel...
        yield ExcludeEditor(self._exclude_patterns, id="exclude-editor")
        yield StatusLog(id="status-log")
        yield Footer()

    def action_focus_exclude_editor(self) -> None:
        self.query_one(ExcludeEditor).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "exclude-editor":
            self._exclude_patterns = event.value.split()
            self.action_run_comparison()

    def action_run_comparison(self) -> None:
        if not self._profiles:
            self.query_one(StatusLog).error(
                "No hay perfiles cargados; no se puede ejecutar la comparación."
            )
            return
        self.query_one(StatusLog).info("Ejecutando comparación…")
        self.run_worker(self._do_run_comparison, exclusive=True, thread=True)

    def _do_run_comparison(self) -> None:
        try:
            new_result = run_comparison(self._profiles, self._exclude_patterns)
        except Exception as exc:
            self.call_from_thread(
                self.query_one(StatusLog).error,
                f"Falló la comparación: {exc}",
            )
            return
        self.call_from_thread(self._apply_new_result, new_result)

    def _apply_new_result(self, new_result: ComparisonResult) -> None:
        self._result = new_result
        self._tree_data = build_tree_data(new_result)
        self.query_one(FindingsTree).populate(self._tree_data)
        self.query_one(SummaryHeader).update(header_text(new_result))
        self.query_one(StatusLog).info("Comparación actualizada.")

    def action_generate_reports(self) -> None:
        self.query_one(StatusLog).info("Generando reportes…")
        self.run_worker(self._do_generate_reports, exclusive=True, thread=True)

    def _do_generate_reports(self) -> None:
        buffer = io.StringIO()
        try:
            generate_reports(self._result, out=buffer)
        finally:
            self.call_from_thread(
                self.query_one(StatusLog).info, buffer.getvalue()
            )
```

- **Worker isolation (Decision 3, REQ-interactive-tui-012):**
  `run_worker(..., thread=True)` runs `_do_run_comparison` /
  `_do_generate_reports` off the Textual event-loop thread. Both worker
  methods call back into the UI only via `self.call_from_thread(...)`
  (Textual's documented cross-thread-safe UI update mechanism) — this is
  what keeps the app responsive and avoids any direct widget mutation
  from the worker thread.
- **Failure isolation, previous result preserved (REQ-interactive-tui-012's
  third scenario):** `_do_run_comparison`'s `except` branch reports the
  error and `return`s **before** calling `_apply_new_result` — `self._result`
  and `self._tree_data` are simply never reassigned on failure, so the
  displayed tree is untouched by construction, not by an explicit
  "restore previous state" step.
- **Output capture (Decision 4, REQ-interactive-tui-013's third
  scenario):** `_do_generate_reports` passes an `io.StringIO()` as
  `generate_reports`'s `out`, never touching `sys.stdout`; the buffered
  text is written into `StatusLog` in one `call_from_thread` call once
  generation finishes (the `finally` ensures partial output is still
  surfaced even if `generate_reports` itself raised — though per §5,
  `generate_reports` is not expected to raise past itself, mirroring
  `write_reports`'s existing per-format try/except isolation).

## 5. `report/write.py` — extracting `generate_reports`

```python
# report/write.py
def generate_reports(result: ComparisonResult, *, out=sys.stdout) -> None:
    """The HTML/PDF/Excel generation steps, extracted verbatim from
    write_reports's existing per-format try/except blocks (REQ-reporting-
    and-output-004's isolation contract is unchanged -- this is a pure
    extraction, not a behavior change)."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    html_str: str | None = None

    try:
        html_str = render_html(result)
        html_path = f"schema-diff-report-{timestamp}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_str)
        print(f"Reporte HTML generado: {html_path}", file=out)
    except Exception as exc:
        print(f"[ERROR] Falló la generación del reporte HTML: {exc}", file=out)

    try:
        if html_str is None:
            raise PdfExportError("omitido: la generación de HTML no se completó")
        pdf_bytes = export_pdf(html_str)
        pdf_path = f"schema-diff-report-{timestamp}.pdf"
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"Reporte PDF generado: {pdf_path}", file=out)
    except Exception as exc:
        print(f"[ERROR] Falló la generación del reporte PDF: {exc}", file=out)

    try:
        xlsx_bytes = export_excel(result)
        xlsx_path = f"schema-diff-report-{timestamp}.xlsx"
        with open(xlsx_path, "wb") as f:
            f.write(xlsx_bytes)
        print(f"Reporte Excel generado: {xlsx_path}", file=out)
    except Exception as exc:
        print(f"[ERROR] Falló la generación del reporte Excel: {exc}", file=out)


def write_reports(
    result: ComparisonResult,
    *,
    out=sys.stdout,
    render_summary: Callable[[ComparisonResult], None] | None = None,
    generate_reports: bool = True,
) -> None:
    effective_render_summary = (
        render_summary
        if render_summary is not None
        else (lambda result: _default_console_summary(result, out=out))
    )

    if generate_reports:
        _generate_reports_impl(result, out=out)  # the extracted function above

    try:
        effective_render_summary(result)
    except Exception as exc:
        print(f"[ERROR] Falló la generación del resumen de consola: {exc}", file=out)
```

- The parameter name collision between the module-level function
  `generate_reports` and `write_reports`'s new `generate_reports: bool`
  parameter is resolved by importing the function under its own name and
  calling it as `_generate_reports_impl` internally within `write.py` (or
  equivalently, naming the module-level function `generate_all_reports`
  from the start) — this is an implementation-time naming detail, not a
  behavior question; the tasks phase picks one concrete name before
  writing tests against it.
- `write_reports`'s existing signature, defaults, and per-format
  try/except isolation are otherwise unchanged — this is additive
  (Decision 1's rationale: no existing non-TUI behavior changes).

## 6. `cli.py` — wiring `generate_reports=False` and profile/exclude passthrough

```python
# cli.py
def _resolve_summary_renderer_and_generate_reports(use_tui: bool):
    """Returns (render_summary_or_None, generate_reports: bool)."""
    if not use_tui:
        return None, True
    if sys.stdout.isatty() and sys.stdin.isatty():
        return run_tui, False  # TUI launches: skip automatic generation
    print(
        "[AVISO] --tui requiere una terminal interactiva; "
        "se usará el resumen de consola simple",
        file=sys.stderr,
    )
    return None, True  # fallback: unchanged behavior


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    profiles = load_profiles(args.config)
    if args.profiles:
        profiles = [p for p in profiles if p.name in args.profiles]

    exclude_patterns = list(args.exclude_tables or [])
    result = run_comparison(profiles, exclude_patterns)  # de-duplicated (§2)

    render_summary, do_generate = _resolve_summary_renderer_and_generate_reports(args.tui)
    write_reports(result, render_summary=render_summary, generate_reports=do_generate)
```

- `run_tui` (in `tui/app.py`) is updated to accept and forward `profiles`
  and `exclude_patterns` into `SchemaComparatorApp.__init__` so the app has
  what it needs for REQ-interactive-tui-011/012 without re-reading
  `args` or any config file itself — `cli.py` remains the only place that
  ever calls `load_profiles`.

## 7. Testing strategy

### 7.1 Pure-function tests (`tests/unit/tui/test_actions.py`)

Direct tests of `run_comparison`, monkeypatching `extract_schema`,
`filter_excluded_tables`, and `compare_snapshots` to assert call order and
argument passthrough (including the "no exclude patterns" no-op path),
plus a test that an exception raised by `extract_schema` propagates
unmodified (no wrapping) — the caller-handles-it contract §2 documents.

### 7.2 Widget tests (`tests/unit/tui/test_widgets.py`)

`StatusLog.info`/`.error` write expected content (assert via
`RichLog`'s line buffer); `ExcludeEditor.__init__` seeds `value` from a
given pattern list (space-joined) and round-trips via `.split()`.

### 7.3 `Pilot`-driven interaction tests (`tests/unit/tui/test_app.py`, additions)

`@pytest.mark.asyncio` tests using `app.run_test()`/`Pilot`, mocking
`tui.actions.run_comparison` and `report.write.generate_reports` at the
`app.py` import site:
- pressing `e` focuses the exclude editor; typing and submitting updates
  `app._exclude_patterns` and triggers a (mocked) re-run
  (REQ-interactive-tui-011).
- pressing `r` triggers a (mocked) re-run without changing
  `_exclude_patterns` (REQ-interactive-tui-012).
- a re-run whose mocked `run_comparison` raises leaves `app._result`
  unchanged and writes an error line to `StatusLog`
  (REQ-interactive-tui-012's failure scenario).
- pressing `g` calls the mocked `generate_reports` with an `io.StringIO`
  `out` and appends its captured content to `StatusLog`
  (REQ-interactive-tui-013).
- a mocked `generate_reports` that writes an `[ERROR]`-prefixed line for
  one format still results in that line appearing in `StatusLog`, without
  the app crashing (REQ-interactive-tui-013's isolation scenario).

### 7.4 `report/write.py` tests (`tests/unit/report/test_write.py`, additions)

- `generate_reports(result, out=buffer)` produces the same three
  print-line outcomes `write_reports` previously produced inline
  (regression-style, comparing against the pre-refactor behavior).
- `write_reports(result, generate_reports=False)` does not call
  `render_html`/`export_pdf`/`export_excel` at all (mocked, asserting
  zero calls), and still calls `render_summary`.
- `write_reports(result, generate_reports=True)` (the default) is
  unchanged from today's behavior (existing tests continue to pass
  unmodified).

### 7.5 `cli.py` tests (`tests/unit/test_cli.py`, additions)

- `--tui` on a mocked-TTY terminal calls `write_reports` with
  `generate_reports=False` (REQ-reporting-and-output-002's new scenario).
- `--tui` on a mocked-non-TTY terminal calls `write_reports` with
  `generate_reports=True` (fallback unchanged).
- no `--tui` calls `write_reports` with `generate_reports=True`
  (unchanged, regression-style assertion).
