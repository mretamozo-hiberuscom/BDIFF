# Tasks: Connection Profile Config

## Review workload forecast

```text
Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low
```

Estimated changed lines: ~450-550 total across 8 new/changed files, but
delivery is by design.md decision `size:exception` (proposal.md footer:
"Delivery: exception-ok ... direct-to-main commits pre-approved for this
change"). No single file exceeds ~150 lines; breakdown:

- `pyproject.toml` (dependency add): ~2 lines
- `src/schema_comparator/config/errors.py`: ~40-60 lines
- `src/schema_comparator/config/models.py`: ~25-35 lines
- `src/schema_comparator/config/loader.py`: ~90-130 lines
- `src/schema_comparator/config/__init__.py`: ~15-20 lines
- `config.example.yaml`: ~15 lines
- `tests/unit/config/test_models.py`: ~40-60 lines
- `tests/unit/config/test_loader.py`: ~180-250 lines (largest file; covers
  ~17 spec scenarios plus the parametrized secret-leakage guardrail)
- `.gitignore` check (likely no-op, entry already present at line 4)

Delivery strategy: single change, single PR (or direct-to-main per the
proposal's pre-approved `size:exception`), applied in the phase order below
in one session. No stacking/chaining needed — this is a small, self-contained
module (models/errors/loader + one example file + two test files), well
under typical review-workload-guard split thresholds even before accounting
for the exception approval already on record.

Suggested split (only relevant if a reviewer later asks for smaller diffs):
1. `errors.py` + `models.py` + their unit tests (pure logic, no I/O)
2. `loader.py` + `test_loader.py` + `pyproject.toml` dependency bump
3. `config.example.yaml` + `__init__.py` public API + `.gitignore` check

Work units: 6 phases, ~14 discrete tasks, each completable within one
session (module is small and has no external service dependencies).

---

## Notes on TDD ordering

`strict_tdd` is `false` in `openspec/config.yaml` (no test runner was
detected at `sdd-init` time) and `rules.apply.tdd: false`. However, pytest
is now configured and verified working (`scaffold-project` change,
state: done/PASS). This task list therefore orders work RED -> GREEN per
phase (write the failing unit test first, then the minimal implementation
that makes it pass) as a quality practice, even though the `strict_tdd` flag
itself is not being flipped by this change. No gate blocks proceeding
without tests passing; it is simply the recommended, and followed, order.

---

## Phase 0 — Dependency setup

- [x] 0.1 Add `PyYAML>=6.0` to `[project].dependencies` in `pyproject.toml`
      (currently `[]`). Reinstall editable package (`pip install -e .`) so
      `import yaml` resolves in the dev environment.
- [x] 0.2 Create empty test package scaffolding: `tests/unit/config/`
      directory with `__init__.py` (or confirm pytest rootdir config allows
      no `__init__.py`, matching existing `tests/unit/` convention).

## Phase 1 — Errors (`errors.py`)

RED before GREEN: write the exception-hierarchy tests first; they will fail
on import since `errors.py` does not exist yet.

- [x] 1.1 (RED) Write `tests/unit/config/test_errors.py`:
      - assert `ConfigFileNotFoundError`, `ConfigParseError`,
        `ProfileValidationError` are all subclasses of `ConfigError`, which
        is a subclass of `Exception`.
      - assert `ProfileValidationError.empty_name()`,
        `.duplicate_name(name)`, `.empty_connection_string(name)` return
        `ProfileValidationError` instances with actionable, non-empty
        messages, and that `.duplicate_name("X")` /
        `.empty_connection_string("X")` messages contain the given name
        `"X"`.
- [x] 1.2 (GREEN) Implement `src/schema_comparator/config/errors.py`: the
      `ConfigError` base and three subclasses with the factory classmethods
      per design.md §5, with pre-composed, secret-safe messages only (no
      connection-string interpolation anywhere in this file).
- [x] 1.3 Run `pytest tests/unit/config/test_errors.py` and confirm all pass.

## Phase 2 — Data model (`models.py`)

- [ ] 2.1 (RED) Write `tests/unit/config/test_models.py`:
      - `ConnectionProfile(name=..., connection_string=...)` exposes exactly
        `name` and `connection_string` (assert via `dataclasses.fields`);
        no extra attributes settable (via `slots=True` -> `AttributeError`
        on arbitrary attribute assignment).
      - instance is immutable: assigning to `.name` after construction
        raises (`dataclasses.FrozenInstanceError` or `AttributeError`).
      - a `Trusted_Connection=yes;` string (no `UID=`/`PWD=`) is accepted
        and stored unchanged (Windows-auth scenario).
      - `repr(profile)` renders `<redacted>` in place of the connection
        string and never contains the raw string value, for both a
        SQL-auth and a Windows-auth example.
- [ ] 2.2 (GREEN) Implement `src/schema_comparator/config/models.py`: the
      `ConnectionProfile` frozen, slotted dataclass with the custom
      redacting `__repr__`, per design.md §2.
- [ ] 2.3 Run `pytest tests/unit/config/test_models.py` and confirm all pass.

## Phase 3 — Loader: happy path + explicit-path contract

- [ ] 3.1 (RED) Write the happy-path section of
      `tests/unit/config/test_loader.py` (file will grow across phases 3-6):
      - loading a 2-entry `databases:` YAML file (written to `tmp_path`)
        returns exactly 2 `ConnectionProfile` objects with names and
        connection strings intact (SQL-auth + Windows-auth pair).
      - a parametrized test over N in `{1, 3, 20}` entries returns exactly N
        profiles (arbitrary-count scenario).
      - `load_profiles()` called with zero arguments raises `TypeError`
        (explicit-path contract; no cwd/repo-root default).
      - loading from an arbitrarily-named file at an arbitrary `tmp_path`
        location (not `config.local.yaml`, not repo root) succeeds.
- [ ] 3.2 (GREEN) Implement the happy-path skeleton of
      `src/schema_comparator/config/loader.py`: `load_profiles(config_path)`
      signature (required positional, no default), file existence check
      deferred to Phase 4, `yaml.safe_load` parse, iteration over
      `databases:` mapping building `ConnectionProfile` list (no trim/dup
      validation yet — added in Phase 5).
- [ ] 3.3 Run the Phase 3 subset of `test_loader.py` and confirm all pass.

## Phase 4 — Loader: missing-file and malformed-YAML fail-fast

- [ ] 4.1 (RED) Extend `test_loader.py`:
      - non-existent path raises `ConfigFileNotFoundError`; message
        references `config.example.yaml`; no raw `FileNotFoundError`
        traceback surfaces as the exception type.
      - a file containing syntactically invalid YAML raises
        `ConfigParseError`; message does not embed `str(yaml.YAMLError)` or
        any parser-internal text/line-snippet.
      - a file whose top level is not a mapping, or lacks a `databases:`
        key, or whose `databases:` value is not a mapping, raises
        `ConfigParseError` with shape guidance.
- [ ] 4.2 (GREEN) Implement the fail-fast gates in `loader.py`: path-exists
      check -> `ConfigFileNotFoundError`; `yaml.safe_load` wrapped in
      `try/except yaml.YAMLError` -> `ConfigParseError` (using `raise ...
      from exc` for debugger chaining only, never embedding `str(exc)` in
      the user-facing message); top-level/`databases:` shape check ->
      `ConfigParseError`.
- [ ] 4.3 Run the Phase 4 subset of `test_loader.py` and confirm all pass.

## Phase 5 — Loader: trim, duplicate-key, and validation pipeline

- [ ] 5.1 (RED) Extend `test_loader.py`:
      - an entry with `"  poliza-service  "` name and
        `"  Driver=...;PWD=y;  "` connection string loads with both
        leading/trailing whitespace trimmed, internal whitespace untouched.
      - an exact re-declared identical YAML key raises
        `ProfileValidationError` (duplicate).
      - two distinct keys differing only in case (`Poliza-Service` /
        `poliza-service`) raise `ProfileValidationError` (case-insensitive
        duplicate), after trim+casefold.
      - a blank/whitespace-only name raises `ProfileValidationError`
        (`empty_name`); message contains no connection-string content.
      - a blank/whitespace-only connection string raises
        `ProfileValidationError` (`empty_connection_string`) naming the
        profile, without echoing the empty value.
- [ ] 5.2 (GREEN) Implement in `loader.py`:
      - the `_DuplicateKeyLoader` / `_no_duplicate_keys` `SafeLoader`
        subclass (design.md §4) wired into the `yaml.safe_load` call so
        exact-duplicate keys raise before dict collapse.
      - the per-entry validation pipeline in order: trim name +
        connection_string -> blank-name check -> case-insensitive
        seen-name check (casefold) -> blank-connection-string check ->
        append `ConnectionProfile`.
- [ ] 5.3 Run the Phase 5 subset of `test_loader.py` and confirm all pass.

## Phase 6 — Cross-cutting guardrails, example template, public API, docs

- [ ] 6.1 (RED) Add the secret-leakage guardrail test in
      `test_loader.py`: a reusable parametrized helper drives every failure
      mode (missing file, malformed YAML, empty name, duplicate name, empty
      connection string) against a config containing sentinel secrets
      (`UID=SECRET_USER;PWD=SECRET_PASS;Trusted_Connection=yes;`) and
      asserts `str(exc)`/`repr(exc)` and `caplog` output never contain the
      sentinel substrings.
- [ ] 6.2 (RED) Add a source-inspection test: read
      `src/schema_comparator/config/loader.py` (and `models.py`,
      `errors.py`) source text and assert no `UID=`, `PWD=`, or hardcoded
      `Driver=` literal appears outside of docstrings/comments explaining
      the guardrail (no fallback credentials).
- [ ] 6.3 (RED) Add a test asserting `.gitignore` contains an entry matching
      `config.local.yaml` (already present at line 4 — this test should
      pass immediately with no production-code change; only add the entry
      if the test fails).
- [ ] 6.4 (RED) Write `tests/unit/config/test_example_config.py`:
      - `config.example.yaml` parses as valid YAML with a `databases:`
        mapping.
      - every value contains an obvious placeholder marker (e.g.
        `your-server`, `your-user`, `your-password`) and no value passes a
        "looks like a real host/credential" heuristic.
      - at least one entry contains `UID=...;PWD=` and at least one other
        entry contains `Trusted_Connection=yes;` (both auth modes present).
- [ ] 6.5 (GREEN) Write `config.example.yaml` at the repo root per
      design.md §7 (both auth-mode placeholder entries, comment header
      pointing to `config.local.yaml`).
- [ ] 6.6 (GREEN) Confirm 6.1-6.4 tests pass against the Phase 1-5
      implementation; fix any leakage found by 6.1/6.2 in `loader.py` /
      `errors.py` messages before proceeding.
- [ ] 6.7 (GREEN) Implement `src/schema_comparator/config/__init__.py`
      re-exporting `ConnectionProfile`, `load_profiles`, `ConfigError`,
      `ConfigFileNotFoundError`, `ConfigParseError`, `ProfileValidationError`
      per design.md §1 public API, with `__all__` set explicitly.
- [ ] 6.8 (GREEN) Add a "no network / no pyodbc" test: with a valid
      `tmp_path` config, load profiles and assert `pyodbc` is not present in
      `sys.modules` after the call, and that no socket-level call occurs
      (e.g. via monkeypatching `socket.socket` to raise if invoked).

## Phase 7 — Full-suite verification

- [ ] 7.1 Run the full suite: `pytest tests/unit/config/ -v` — all tests
      green.
- [ ] 7.2 Run `pytest` (whole repo) to confirm no regression in the
      existing `tests/unit/test_import_smoke.py` /
      `tests/integration/test_structure_smoke.py` smoke tests.
- [ ] 7.3 Spot-check coverage against design.md §8's per-scenario matrix:
      confirm every spec.md scenario (6 requirements, 17 scenarios total)
      has at least one corresponding test written above; note any gap
      before calling this change apply-ready.
- [ ] 7.4 Confirm `pyproject.toml` dependency change is the only
      `dependencies` edit (no accidental `pyodbc`/`textual` addition).
