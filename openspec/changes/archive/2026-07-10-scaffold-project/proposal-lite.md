# Proposal Lite: Scaffold Project

## Change Class

small

## Intent

The repository is greenfield — no code exists yet. Before any Milestone 1
capability (connection config, discovery, comparison, reporting) can be
built, the project needs a minimal, runnable Python skeleton: package
metadata, the `src/schema_comparator/` layout already decided in
`docs/architecture/technical-baseline.md`, and a working pytest setup.
This unblocks all subsequent SDD changes without introducing any business
logic itself.

## Boundaries

- In scope:
  - `pyproject.toml` (PEP 621) declaring project metadata, Python 3.11+
    requirement, and `pytest` as a dev dependency; installable via
    `pip install -e .`.
  - `src/schema_comparator/` package skeleton with empty (docstring-only)
    subpackages matching the planned architecture: `config/`,
    `connectors/`, `discovery/`, `compare/`, `report/`, `tui/`, plus a
    minimal `cli.py` entry point that only proves the package imports and
    runs (e.g. prints a placeholder message) — no Textual app, no DB
    logic yet.
  - `tests/unit/` and `tests/integration/` directories with a placeholder
    smoke test so `pytest` has something to collect and pass.
  - `.gitignore` entries for `.venv/`, `__pycache__/`, `config.local.yaml`.
- Out of scope (forces escalation to full SDD if attempted here):
  - Any connection/config-loading logic, DB connectivity (`pyodbc`),
    schema discovery, comparison engine, or report rendering.
  - The actual Textual TUI screens/widgets.
  - Dependency additions beyond `pytest` (e.g. `pyodbc`, `textual`,
    `xhtml2pdf`) — those ship with their owning capability's change.

## Affected Areas

| Area | Impact | Notes |
|------|--------|-------|
| `pyproject.toml` | New | Project metadata, Python version pin, `pytest` dev dependency, `pip install -e .` support |
| `src/schema_comparator/__init__.py` | New | Package marker |
| `src/schema_comparator/{config,connectors,discovery,compare,report,tui}/__init__.py` | New | Empty subpackages per planned layout (technical-baseline.md) |
| `src/schema_comparator/cli.py` | New | Minimal entry point placeholder, no business logic |
| `tests/unit/`, `tests/integration/` | New | Empty layout + one smoke test each so `pytest` passes |
| `.gitignore` | New | Ignore `.venv/`, `__pycache__/`, `config.local.yaml` |

## Acceptance Checks

- [ ] `python -m venv .venv && pip install -e .` succeeds from a clean clone
- [ ] `pytest` runs and passes (collects the placeholder smoke tests, zero failures)
- [ ] `python -m schema_comparator.cli` (or equivalent) runs without error and exits cleanly
- [ ] No business logic (DB connection, discovery, comparison, reporting) present in any file

## Risks and Rollback

- Risk: Low — purely additive scaffolding, no runtime behavior to break, nothing else depends on it yet.
- Rollback: `git revert` the single commit/PR introducing the scaffold; no data or external state involved.

---

**Branch advisory:** Before `sdd-apply` begins, a feature branch SHOULD be created following the `<tipo>/<descripción>` convention defined in the `branch-pr` skill (e.g. `git checkout -b feat/scaffold-project main`). This note is SHOULD, not MUST.
