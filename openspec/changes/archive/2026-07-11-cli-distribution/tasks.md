# Tasks: Zero-Venv CLI Launcher (`run.py`)

## Spec/Design Reconciliation

| Requirement / Scenario | Priority | Design Allocation | Status | Notes |
|---|---|---|---|---|
| REQ-cli-distribution-001 First run provisions & runs | MUST | `run.py` §3 `main`/`_provision` | covered-by-design | Also covers `py`/`python`/`python3` invocability (stdlib-only script) |
| REQ-cli-distribution-002 Idempotent skip on re-run | MUST | `is_venv_ready` §2, `main` §3 | covered-by-design | Marker-file check, no re-install |
| REQ-cli-distribution-003 Self-heal missing/removed venv | MUST | `is_venv_ready` + `_provision` §2-3 | covered-by-design | Same code path as first run |
| REQ-cli-distribution-004 Forward args & exit code | MUST | `build_relaunch_argv`, `main`'s `sys.exit` §2-3 | covered-by-design | No re-parsing of `cli_args` |
| REQ-cli-distribution-005 Fail loudly, no partial ready state | MUST | `_run_checked`, marker write ordering §3 | covered-by-design | Marker only reached after zero-exit install |

### Reconciliation Verdict

- MUST coverage: complete
- SHOULD/MAY gaps: none (spec has no SHOULD/MAY-level requirements)
- Ambiguities to track: none outstanding; `venv.create` raising directly
  (uncaught) rather than going through `_run_checked` is a deliberate
  design choice (§3), not an open question.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~350–500 (5 files: `run.py`, `__main__.py`, 2 new test files, README section) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | (not yet fixed for this change — decide before `sdd-apply`) |
| Chain strategy | none needed |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: none needed
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | `run.py` pure functions + unit tests (mocked subprocess/venv) | PR 1 | Phases 1–3 |
| 2 | `__main__.py` + orchestration wiring + integration tests + docs | PR 1 (same PR, small enough) | Phases 4–6 |

### Checklist Status Legend

- `[ ]` Not implemented yet
- `[~]` Implemented but not yet verified locally
- `[x]` Implemented and verified locally

## Phase 1: Pure Path/Readiness Helpers (`run.py`)

- [x] 1.1 (RED) Create `tests/unit/test_run_launcher.py`; write
      `test_resolve_venv_dir_is_repo_root_slash_venv`,
      `test_resolve_venv_python_windows_path`,
      `test_resolve_venv_python_posix_path` (parametrized/monkeypatched
      `os.name`) against a not-yet-created `run` module (REQ-cli-distribution-001)
- [x] 1.2 (GREEN) Create `run.py` at the repo root with
      `resolve_venv_dir`, `resolve_venv_python` per design §2
- [x] 1.3 (RED) Write `test_is_venv_ready_false_when_interpreter_missing`,
      `test_is_venv_ready_false_when_marker_missing`,
      `test_is_venv_ready_true_when_both_present`, using `tmp_path` to
      fabricate the interpreter file and marker (REQ-cli-distribution-002,
      REQ-cli-distribution-003)
- [x] 1.4 (GREEN) Implement `is_venv_ready` per design §2
- [x] 1.5 Run `pytest tests/unit/test_run_launcher.py` and confirm Phase 1
      tests pass

## Phase 2: Argv-Building Helpers (`run.py`)

- [x] 2.1 (RED) Write `test_build_pip_install_argv_shape` and
      `test_build_relaunch_argv_forwards_cli_args_unmodified` (including a
      case with `--tui`/`--exclude-tables` style multi-value args) against
      not-yet-implemented functions (REQ-cli-distribution-004)
- [x] 2.2 (GREEN) Implement `build_pip_install_argv`, `build_relaunch_argv`
      per design §2
- [x] 2.3 Run `pytest tests/unit/test_run_launcher.py` and confirm Phase 2
      tests pass

## Phase 3: Orchestration (`main`, `_provision`, `_run_checked`)

- [x] 3.1 (RED) Write `test_main_skips_provisioning_when_venv_ready`
      (monkeypatch `is_venv_ready` to `True`, monkeypatch `subprocess.run`
      to a fake success, assert `venv.create` is never called and the pip
      install argv is never invoked) (REQ-cli-distribution-002)
- [x] 3.2 (GREEN) Implement `main()`'s ready-skip branch per design §3
- [x] 3.3 (RED) Write `test_main_provisions_when_venv_not_ready` (monkeypatch
      `is_venv_ready` to `False`, monkeypatch `venv.create` and
      `subprocess.run` to fake successes, assert provisioning steps ran in
      order and the marker file was written before relaunch)
      (REQ-cli-distribution-001, REQ-cli-distribution-003)
- [x] 3.4 (GREEN) Implement `_provision` per design §3
- [x] 3.5 (RED) Write `test_main_exits_with_child_returncode` (monkeypatch
      relaunch `subprocess.run` to return a non-zero code, assert
      `sys.exit` is called with that exact code) (REQ-cli-distribution-004)
- [x] 3.6 (GREEN) Confirm/adjust `main()`'s final `sys.exit(completed.returncode)`
- [x] 3.7 (RED) Write `test_provision_failure_reports_error_and_skips_marker`
      (monkeypatch the install-step `subprocess.run` to return non-zero,
      assert an error is printed to `stderr`, `sys.exit` is called with a
      non-zero code, and no marker file is written) (REQ-cli-distribution-005)
- [x] 3.8 (GREEN) Implement `_run_checked` per design §3; wire it into
      `_provision` before the marker-write line
- [x] 3.9 Run `pytest tests/unit/test_run_launcher.py` in full and confirm
      all Phase 1–3 tests pass together

## Phase 4: `src/schema_comparator/__main__.py`

- [x] 4.1 (RED) Add `test_module_invocation_runs_main` to
      `tests/unit/test_cli.py` (or a new `tests/unit/test_main_module.py`),
      asserting `python -m schema_comparator.cli` style invocation reaches
      `cli.main` (subprocess-based smoke test, or a direct import + call
      assertion if a subprocess round-trip is judged unnecessarily slow
      for this specific check)
- [x] 4.2 (GREEN) Create `src/schema_comparator/__main__.py` per design §4
- [x] 4.3 Run the relevant test file and confirm it passes

## Phase 5: Real-Venv Integration Tests

- [x] 5.1 Create `tests/integration/test_run_launcher_bootstrap.py`; write
      `test_first_run_creates_working_venv_with_marker` invoking `run.py`
      as a subprocess against a `tmp_path` copy of the repo (or a minimal
      fixture project referencing this repo's `pyproject.toml`), asserting
      `.venv`'s interpreter and marker file exist afterward
      (REQ-cli-distribution-001)
- [x] 5.2 Write `test_second_run_does_not_reprovision` asserting a second
      invocation does not recreate `.venv` (e.g. via an `mtime` check on
      the marker file or interpreter) (REQ-cli-distribution-002)
- [x] 5.3 Write `test_deleting_venv_triggers_reprovisioning` deleting
      `.venv` between two invocations and asserting it is recreated with a
      fresh marker (REQ-cli-distribution-003)
- [x] 5.4 Run `pytest tests/integration/test_run_launcher_bootstrap.py`
      and confirm all three pass (accept the longer runtime of real venv
      creation for this small, isolated test file)

## Phase 6: Documentation

- [x] 6.1 Add or update the top-level README with a "Quick start" section
      documenting `python run.py --config ... --tui` (and the `py`/`python3`
      variants) as the recommended zero-setup entry point, with a short
      note on `uv run`/`pipx run` as a documented alternative (not the
      primary mechanism), per proposal Out-of-Scope
- [x] 6.2 Run the full suite with `pytest --cov`; confirm the new
      `run.py`/`__main__.py` modules meet the project's 80%+ coverage
      target and no pre-existing test regresses
