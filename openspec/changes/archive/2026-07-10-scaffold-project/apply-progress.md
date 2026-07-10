# Apply Progress: Scaffold Project

**Mode**: Standard (strict_tdd: false — no test runner existed pre-scaffold; scaffold-first per tasks.md)
**Route**: lite (proposal-lite.md is the behavior contract; no spec.md/design.md)
**Branch**: `feat/scaffold-project`

## Batch 1 — Full scaffold (Phases 1-4)

All tasks completed and locally verified in a single batch (no prior apply-progress existed).

### Completed Tasks

- [x] 1.1 `pyproject.toml` created (PEP 621, `schema-comparator`, `requires-python = ">=3.11"`,
      `pytest>=8.0` under `[project.optional-dependencies].dev`, src-layout via
      `[tool.setuptools.packages.find]`).
- [x] 1.2 Verified `python -m venv .venv` + `pip install -e ".[dev]"` succeeds (fresh `.venv`, not
      previously present in the repo).
- [x] 2.1 `src/schema_comparator/__init__.py` (docstring-only marker).
- [x] 2.2 / 2.2.1-2.2.6 Empty subpackages created, matching
      `docs/architecture/technical-baseline.md` planned layout: `config/`, `connectors/`, `discovery/`,
      `compare/`, `report/`, `tui/` — each with a docstring-only `__init__.py`.
- [x] 2.3 `src/schema_comparator/cli.py` — minimal `main()` that prints a placeholder message and exits;
      no Textual app, no DB logic, no argument parsing.
- [x] 2.4 Confirmed by inspection: every file under `src/schema_comparator/` is either an empty
      docstring-only `__init__.py` or the placeholder `cli.py` — no connection/config-loading, DB
      connectivity, discovery, comparison, or report logic present.
- [x] 3.1 `tests/unit/test_import_smoke.py` — asserts `import schema_comparator` succeeds.
- [x] 3.2 `tests/integration/test_structure_smoke.py` — structure-only smoke test (`assert True`), no real
      DB connection, per proposal-lite.md boundaries.
- [x] 3.3 Ran `pytest -q` in the fresh venv: `2 passed in 0.02s`.
- [x] 3.4 Ran `python -m schema_comparator.cli`: printed placeholder message, exit code `0`.
- [x] 3.5 `.gitignore` created with `.venv/`, `__pycache__/`, `*.pyc`, `config.local.yaml`,
      `*.egg-info/`, `build/`, `dist/`, `.pytest_cache/`.
- [x] 4.1 Re-ran all four acceptance checks end-to-end against the fresh `.venv`:
  1. `python -m venv .venv && pip install -e ".[dev]"` — succeeded.
  2. `pytest` — 2 passed, 0 failures.
  3. `python -m schema_comparator.cli` — exit 0, clean output.
  4. No business logic present under `src/schema_comparator/` — confirmed by file inspection (all
     `__init__.py` are docstring-only; `cli.py` only prints and exits).
- [x] 4.2 Confirmed current branch is `feat/scaffold-project` (advisory check, already satisfied — work
      was not done on `main`).
- [x] 4.3 Follow-up flagged for the PR description (not actioned in this change, out of scope per
      proposal-lite.md): `openspec/config.yaml` → `testing.strict_tdd_mode` should be revisited (flip to
      `enabled`) now that pytest exists, per `docs/architecture/technical-baseline.md` Testing Bar section.

### Files Changed

| File | Action | What Was Done |
|------|--------|----------------|
| `pyproject.toml` | Created | PEP 621 metadata, `schema-comparator`, Python `>=3.11`, `pytest` dev extra, src-layout package discovery |
| `src/schema_comparator/__init__.py` | Created | Package marker (docstring only) |
| `src/schema_comparator/config/__init__.py` | Created | Empty subpackage marker |
| `src/schema_comparator/connectors/__init__.py` | Created | Empty subpackage marker |
| `src/schema_comparator/discovery/__init__.py` | Created | Empty subpackage marker |
| `src/schema_comparator/compare/__init__.py` | Created | Empty subpackage marker |
| `src/schema_comparator/report/__init__.py` | Created | Empty subpackage marker |
| `src/schema_comparator/tui/__init__.py` | Created | Empty subpackage marker |
| `src/schema_comparator/cli.py` | Created | Minimal placeholder entry point (`main()` prints + exits, no business logic) |
| `tests/unit/test_import_smoke.py` | Created | Smoke test: package imports |
| `tests/integration/test_structure_smoke.py` | Created | Structure-only smoke test |
| `.gitignore` | Created | `.venv/`, `__pycache__/`, `*.pyc`, `config.local.yaml`, `*.egg-info/`, `build/`, `dist/`, `.pytest_cache/` |

### Deviations from Design (proposal-lite.md)

- **`readme` field omitted from `pyproject.toml`**: proposal-lite.md and tasks.md do not mention a
  `README.md`, and none exists in the repo yet. Setting `readme = "README.md"` in `[project]` would break
  `pip install -e .` (setuptools errors on a referenced-but-missing readme file). Omitting the field is a
  cosmetic/internal packaging-metadata detail with no observable-behavior impact (no public contract is
  affected — it doesn't change installability, the CLI, or test behavior) — recorded as an assumption
  below rather than a blocking question, per the Assumption Materiality Rule.
- **Fixed a real defect found during verification**: the first draft of `cli.py` used an em dash
  (`—`) in the placeholder print string, which produced a `UnicodeEncodeError`-adjacent mangled character
  (`�`) under the default Windows console codepage (cp1252) during the `python -m schema_comparator.cli`
  verification run (task 3.4). Replaced with a plain ASCII hyphen (`-`) to keep the entry point portable
  across default console encodings. Re-verified after the fix: exit code 0, clean output.

### Issues Found

None beyond the encoding fix above (already resolved and re-verified).

### Remaining Tasks

None — all tasks in `tasks.md` (Phases 1-4) are complete and locally verified (`[x]`).

### Workload / PR Boundary

- Mode: single PR (no chaining needed — forecast was `400-line budget risk: Low`, `Decision needed before
  apply: No`)
- Current work unit: N/A (single unit, fully completed)
- Boundary: entire scaffold change, start to finish, in one batch
- Estimated review budget impact: ~12 new files, well under the 400-line budget (mostly single-line
  docstring `__init__.py` files, one short `cli.py`, one `pyproject.toml`, two short test files, one
  `.gitignore`)

### Status

15/15 tasks (including nested 2.2.x) complete. Ready for verify.

### Local Verification Evidence

```text
$ python -m venv .venv
$ .venv\Scripts\python.exe -m pip install --upgrade pip -q
$ .venv\Scripts\python.exe -m pip install -e ".[dev]" -q
(succeeded, no errors)

$ .venv\Scripts\python.exe -m pytest -q
..                                                                       [100%]
2 passed in 0.02s

$ .venv\Scripts\python.exe -m schema_comparator.cli
schema_comparator: scaffold placeholder - no TUI wired up yet.
$ echo EXIT:$LASTEXITCODE
EXIT:0
```
