# Tasks: Scaffold Project

Source: `openspec/changes/scaffold-project/proposal-lite.md` (route: lite — no spec.md/design.md exist for this change).
`strict_tdd: false` — no test runner exists yet; this change is the one that installs pytest, so tasks are ordered
scaffold-first, smoke-test-second rather than RED-GREEN-REFACTOR.

## Review Workload Forecast

```text
Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low
```

- Estimated changed lines: ~120-180 (all new files: `pyproject.toml`, ~7 `__init__.py` package markers,
  `cli.py`, 2 placeholder smoke tests, `.gitignore`). No existing files modified, no deletions.
- Delivery strategy: single PR / single commit. Purely additive scaffolding with no business logic and no
  interdependent review surface — splitting would add coordination overhead without reducing reviewer risk.
- Suggested split: none. If reviewers prefer smaller diffs, the natural (optional) seam is
  "1. packaging + package skeleton" vs "2. tests + gitignore", but this is not recommended given the low
  line count and tight coupling (tests need the package to exist to smoke-import it).
- Work units: 3 (Phase 1 packaging, Phase 2 package skeleton + CLI stub, Phase 3 tests + tooling hygiene),
  all completable in one focused session.

## 1. Packaging (`pyproject.toml`)

- [x] 1.1 Create `pyproject.toml` (PEP 621): project name `schema-comparator`, `requires-python = ">=3.11"`,
      `pytest` declared as a dev/optional dependency group (e.g. `[project.optional-dependencies].dev` or
      `[dependency-groups]`), package discovery pointing at `src/schema_comparator/` (`src` layout via
      `[tool.setuptools.packages.find]` or `[build-system]` equivalent).
- [x] 1.2 Verify `python -m venv .venv && pip install -e .` succeeds from a clean checkout
      (acceptance check #1 in proposal-lite.md).

## 2. Package Skeleton (`src/schema_comparator/`)

- [x] 2.1 Create `src/schema_comparator/__init__.py` (package marker, docstring only).
- [x] 2.2 Create empty subpackages with docstring-only `__init__.py`, matching the planned layout in
      `docs/architecture/technical-baseline.md`:
  - [x] 2.2.1 `src/schema_comparator/config/__init__.py`
  - [x] 2.2.2 `src/schema_comparator/connectors/__init__.py`
  - [x] 2.2.3 `src/schema_comparator/discovery/__init__.py`
  - [x] 2.2.4 `src/schema_comparator/compare/__init__.py`
  - [x] 2.2.5 `src/schema_comparator/report/__init__.py`
  - [x] 2.2.6 `src/schema_comparator/tui/__init__.py`
- [x] 2.3 Create `src/schema_comparator/cli.py` with a minimal entry point that only proves the package
      imports and runs (e.g. prints a placeholder message) — no Textual app, no DB logic, no argument
      parsing beyond what's needed to run.
- [x] 2.4 Confirm no file under `src/schema_comparator/` contains connection/config-loading logic, DB
      connectivity, schema discovery, comparison, or report rendering (acceptance check #4).

## 3. Tests, Entry Point Verification, and Repo Hygiene

- [x] 3.1 Create `tests/unit/` directory with one placeholder smoke test (e.g. asserts
      `import schema_comparator` succeeds).
- [x] 3.2 Create `tests/integration/` directory with one placeholder smoke test (structure-only; no real DB
      connection — out of scope per proposal-lite.md boundaries).
- [x] 3.3 Run `pytest` and confirm it collects and passes both smoke tests with zero failures
      (acceptance check #2).
- [x] 3.4 Run `python -m schema_comparator.cli` (or the equivalent declared entry point) and confirm it
      exits cleanly (acceptance check #3).
- [x] 3.5 Create/update `.gitignore` with entries for `.venv/`, `__pycache__/`, `config.local.yaml`.

## 4. Wrap-up

- [x] 4.1 Re-check all four acceptance checks from `proposal-lite.md` end-to-end on a clean clone/venv.
- [x] 4.2 (Advisory, per proposal-lite.md branch note) confirm work happened on a feature branch
      (`feat/scaffold-project` or similar) before merge, per the `branch-pr` skill convention.
- [x] 4.3 Note in the PR description that `openspec/config.yaml` `testing.strict_tdd_mode` should be
      revisited (flip to enabled) now that pytest exists, per `docs/architecture/technical-baseline.md`
      Testing Bar section — flagged as a follow-up, not part of this change's scope.
