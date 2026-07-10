# Exploration: Interactive TUI (`--tui` flag)

## Current State

Milestone 1 is complete and archived. The current console output is a static,
one-shot plain-text summary: `render_console(result) -> str`
([src/schema_comparator/report/console.py](../../../src/schema_comparator/report/console.py))
groups `ComparisonResult.entries` by category (counts per
`MissingTable`/`MissingColumn`/`ColumnMismatch`) and then per-table via
`itertools.groupby` on `entry.qualified_name`, printing one indented line per
finding. It is a pure function of `ComparisonResult` — no I/O, no interactivity.

`write_reports(result, *, out=sys.stdout)`
([src/schema_comparator/report/write.py](../../../src/schema_comparator/report/write.py))
always attempts HTML, then PDF, then the console summary, each isolated in its
own `try/except` so one failing format never blocks the others (this
per-format isolation is a normative requirement from `reporting-and-output`,
REQ-reporting-and-output-007, and must not regress).

`cli.py` ([src/schema_comparator/cli.py](../../../src/schema_comparator/cli.py))
is a synchronous, linear pipeline: `load_profiles` → `extract_schema` (one call
per profile) → `compare_snapshots` → `write_reports(result)`. It currently only
defines `--config` and `--profiles`; there is no `--format`/`--tui` flag yet,
and the docstring explicitly says v1 "always generates all three report
outputs."

`src/schema_comparator/tui/__init__.py` exists but is empty — a docstring
placeholder ("Textual App and screens (connections list, add/edit connection,
run/report)") describing a broader future TUI than this change's scope; this
change only needs the read-only findings browser described below, not a
connection-management UI.

`pyproject.toml` dependencies are `PyYAML`, `pyodbc`, `Jinja2`, `xhtml2pdf`
(+ dev: `pytest`, `pytest-cov`). `textual` is not present in either group.

The domain model consumed by the TUI is fixed and already stable:
`ComparisonResult` (`compared_profiles: tuple[str, ...]`,
`entries: tuple[DiffEntry, ...]`) where `DiffEntry = MissingTable |
MissingColumn | ColumnMismatch`
([src/schema_comparator/compare/models.py](../../../src/schema_comparator/compare/models.py)).
All three entry types expose `.qualified_name -> (schema_name, table_name)`.
`ColumnMismatch.values_by_profile` is a pre-sorted tuple of
`(profile_name, ColumnAttributes)` pairs.

## Affected Areas

- `src/schema_comparator/tui/` — new `App` (and likely one or two supporting
  widget/screen modules), consuming `ComparisonResult` directly (same input as
  `render_console`), read-only (no DB/report I/O inside the TUI itself).
- `src/schema_comparator/cli.py` — add an opt-in `--tui` boolean flag; branch
  after `compare_snapshots` so HTML/PDF generation runs unconditionally, and
  the TUI *replaces only* the plain-text console summary when `--tui` is
  passed and the terminal is interactive.
- `src/schema_comparator/report/write.py` — needs a way to skip/replace only
  the console-summary step when the caller opts into the TUI, without
  disturbing the HTML/PDF try/except isolation. Likely a new parameter (e.g.
  `render_console_summary: bool = True` or an injected console-renderer
  callable) rather than duplicating the HTML/PDF logic in `cli.py`.
- `pyproject.toml` — add `textual` as a new core (non-dev) dependency, since
  `--tui` is a documented CLI feature, not a dev-only tool.
- `tests/unit/tui/` (new) — Textual's `Pilot`/testing harness-based tests
  (see Design Question 3) plus fixtures reusing the existing hand-built
  `ComparisonResult` fixtures pattern from `tests/unit/report/` and
  `tests/unit/compare/`.
- `tests/unit/test_cli.py` — extend for the new `--tui` flag parsing and the
  non-interactive-terminal fallback branch.
- `openspec/specs/reporting-and-output/spec.md` — likely needs a new
  requirement (or an amended one) documenting that `--tui` replaces only the
  console summary and HTML/PDF generation is unaffected; exact spec-file
  ownership (extend `reporting-and-output` vs. a new `interactive-tui` spec)
  is a proposal-phase decision, not resolved here.

## Key Design Questions

### 1. Is `textual` a reasonable dependency to add?

`textual` is an actively maintained, widely-used Python TUI framework (by the
makers of Rich, which is already a transitive dependency of several packages
in this ecosystem). It is a reasonable, appropriately-scoped choice for this
project:

- **Terminal compatibility**: `textual` targets modern ANSI-capable terminals
  (Windows Terminal, most Linux/macOS terminals, VS Code's integrated
  terminal). Legacy `cmd.exe` support is degraded but functional for basic
  cases. Since this is a developer-facing CLI tool (not an end-user product),
  this is an acceptable constraint, but it reinforces the need for a
  non-interactive/dumb-terminal fallback (Design Question 4).
- **Async event loop**: `textual.App.run()` internally drives an `asyncio`
  event loop, but it is a fully synchronous call from the caller's
  perspective — `App().run()` blocks until the user quits, then returns
  control normally. This means `cli.py`'s existing synchronous, linear
  pipeline (`load_profiles` → `extract_schema` → `compare_snapshots` →
  `write_reports`) does **not** need to become async; the TUI can be invoked
  as `App(result).run()` as a drop-in replacement for the
  `render_console`/`print` step, with no ripple effect on the rest of the
  pipeline being synchronous. This is the single most important feasibility
  finding: no async rewrite of the CLI is required.
- **Packaging weight**: `textual` pulls in `rich` (usually a shared
  transitive anyway) and pure-Python dependencies; no native/compiled
  extensions, so it does not complicate the existing `pyodbc`/`xhtml2pdf`
  dependency profile.

Conclusion: adding `textual` as a core dependency is reasonable and low-risk.

### 2. Concrete interaction design (v1-scoped, not over-engineered)

Given the fixed scope (navigate findings, filter by table/type, collapse/expand,
quit with a key) and the existing `render_console` grouping (by category, then
per-table), a v1 layout that mirrors that grouping without inventing new
information:

- **Main view**: a `Tree` widget (Textual's built-in `Tree`/`DataTable`
  primitives cover this without custom widget code) with one root node per
  table (`schema.table`, matching `entry.qualified_name`), each expandable to
  its findings as leaf nodes labeled the same way `render_console` already
  formats each line (missing table / missing column / mismatch + profiles).
  Collapse/expand is a `Tree` built-in behavior — no custom implementation
  needed.
- **Filter/search**: a single `Input` widget bound to a live filter over
  either the diff-type label (`MissingTable`/`MissingColumn`/`ColumnMismatch`)
  or a substring of `schema.table`/column name — one filter box, not separate
  per-field controls, to keep v1 scope small. Filtering hides non-matching
  tree nodes rather than re-querying data.
- **Detail panel**: a secondary panel (e.g. `Static`/`RichLog` region) showing
  the full detail of the currently-selected leaf node — for `ColumnMismatch`,
  this is where the full `values_by_profile` breakdown (all profiles' full
  `ColumnAttributes`) is shown, since the tree leaf label itself should stay
  short (this is strictly *more* detail than `render_console` currently
  prints inline, so it is a genuine improvement, not a regression).
- **Header/footer**: a summary header showing `compared_profiles` and total
  counts by category (same data `render_console` prints first), and a footer
  with key bindings (Textual's `Footer` widget auto-derives this from
  declared `BINDINGS`), e.g. `q`/`Escape` to quit, `/` to focus the filter
  input, arrow keys/`j`/`k` to navigate (Tree defaults), `Enter`/`Space` to
  toggle expand.

This is intentionally a single-screen app (no connection-management screens,
no run/re-extract action) — strictly the *findings browser* the roadmap item
describes, leaving the broader TUI docstring in `tui/__init__.py` as an
aspirational placeholder for a possible future change, not this one's scope.

### 3. Testability — is meaningful automated TDD feasible?

Yes, with caveats. Textual ships a first-class testing harness:
`App.run_test()` returns an async context manager yielding a `Pilot` object
that can simulate key presses/clicks (`pilot.press("down")`,
`pilot.click(...)`) and await screen settling, while the test asserts against
the live `App`/widget state (e.g. `app.query_one(Tree)`, node counts, focused
widget, `Input.value`). This runs headless — no real terminal/TTY needed —
so it is CI-safe and does not require the non-interactive-terminal detection
in Design Question 4 to be worked around in tests.

Caveats to carry into the design/task-planning phase:

- Tests are `async def` and use `pytest-asyncio` (or `pytest.mark.asyncio`),
  which is a **new test-infrastructure dependency** not currently in
  `pyproject.toml`'s `dev` extras — must be added alongside `textual` itself
  (as a dev dependency, since it's test-only, unlike `textual` which is a
  runtime dependency of the CLI).
  \[Note: `textual-dev`/`textual`'s own test utilities may bundle a
  compatible `pytest` plugin; confirm exact package name during
  design/implementation rather than assuming here.]
- Snapshot/pixel-level assertions are possible via Textual's snapshot testing
  but are heavier-weight and more brittle than state-based assertions;
  recommend state-based assertions only for v1 (assert on tree node count,
  selected node identity, filter narrowing the visible set, key binding
  triggering quit) rather than adopting snapshot testing.
- Given the existing project's `strict_tdd_mode: disabled` project setting
  (per `openspec/config.yaml`) but this being a fresh, well-testable surface,
  TDD is a reasonable posture for the *filtering logic* and *tree
  construction from `ComparisonResult`* in particular — those can be tested
  as plain synchronous unit tests **without** the `Pilot` harness at all, by
  extracting the pure "which entries match this filter" / "what tree
  structure does this ComparisonResult produce" logic into ordinary
  functions the `App` calls, keeping the `Pilot`-based tests focused on a
  smaller number of true interaction scenarios (navigate, filter, quit).
  This mirrors the project's existing preference for pure-function testable
  cores (`render_console`, `compare_snapshots`) with thin I/O/UI shells.

Conclusion: meaningful automated tests are feasible and should be a first-class
part of this change (both pure-logic unit tests and a small number of
`Pilot`-driven interaction tests), not downgraded to manual-smoke-test-only.

### 4. Non-interactive terminal fallback

`textual` cannot run in a non-TTY context (piped output, CI, redirected
stdout) — attempting to do so fails ungracefully at the terminal-driver
level. Two options:

1. **Detect and fall back to the plain console summary with a warning.**
   Check `sys.stdout.isatty()` (and ideally `sys.stdin.isatty()`, since
   Textual also needs interactive input) before invoking the TUI; if not a
   TTY, print a one-line warning (e.g. `[WARN] --tui requires an interactive
   terminal; falling back to plain console summary`) to stderr and call
   `render_console` instead.
2. **Error out clearly** if `--tui` is requested but the terminal is
   non-interactive.

Recommendation: **(1), detect and fall back**, for two reasons specific to
this project: (a) HTML/PDF generation must always succeed regardless of
`--tui` per the fixed scope constraint, so the *tool's* overall exit
behavior/exit code should not be held hostage by an interactive-only
convenience flag; a CI pipeline that always passes `--tui` for local-dev
convenience via a shared script must not start failing when run headless.
(b) It mirrors the existing per-format failure-isolation philosophy in
`write_reports` (never let one output's inability to run block the others or
error the whole run) — falling back is more consistent with the codebase's
established error-handling posture than introducing the first hard-error path
in the reporting pipeline. The warning must go to stderr (or the same `out`
sink already used for `[ERROR]` lines in `write_reports`) so it's visible but
doesn't corrupt piped stdout consumers.

### 5. Risks and open questions for spec/design phase

- **Where does the `--tui`/non-TTY detection belong?** — `cli.py` (before
  calling `write_reports`) vs. inside `write_reports` itself (as a parameter).
  Putting it in `write_reports` keeps `cli.py` thin and keeps the "always
  attempt HTML/PDF, isolate failures" contract in one place, but couples
  `write_reports` to `sys.stdin`/`sys.stdout` TTY checks it doesn't currently
  need. Putting it in `cli.py` keeps `write_reports`'s existing signature
  smaller but means the interactive/TUI decision and the file-write
  orchestration are split across two modules. Needs a decision in
  design/proposal, not here.
- **New dev-dependency for async tests** (`pytest-asyncio` or equivalent) —
  confirm the exact package/plugin Textual's own test suite recommends before
  locking the `pyproject.toml` diff, and which pytest-asyncio mode
  (`auto`/`strict`) to configure to avoid surprising the rest of the
  (currently fully synchronous) test suite.
- **Exit code semantics when falling back**: does a non-TTY fallback still
  exit 0 (treating it as graceful degradation), matching how `write_reports`
  never raises past itself today? Recommend yes, for consistency, but should
  be confirmed as an explicit requirement in the spec.
- **Spec ownership**: extend the existing `reporting-and-output` spec (since
  this is another *output mode* of the same reporting stage) vs. a new
  `interactive-tui` spec. Given the roadmap explicitly lists this as its own
  Milestone 2 item (unlike Milestone 1's console summary, which was folded
  into `reporting-and-output`), a **new dedicated spec** is likely more
  consistent with how milestone items have been tracked so far, but this is a
  proposal-phase call, not resolved here.
- **Scope creep risk**: `tui/__init__.py`'s existing docstring describes a
  much larger TUI ("connections list, add/edit connection, run/report") than
  this change's fixed scope (read-only findings browser). The proposal/design
  phase should explicitly narrow this docstring (or leave it and just not
  implement beyond the findings browser) so future readers don't assume more
  was built than actually was.
- **Large result sets**: no current signal on typical finding counts at
  scale; `Tree`/`DataTable` performance with hundreds/thousands of nodes is
  generally fine for Textual, but worth a smoke check during design/testing
  rather than assuming.
