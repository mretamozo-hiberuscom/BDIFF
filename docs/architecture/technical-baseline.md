# Technical Baseline — SQL Server Schema Comparator

This document resolves the technical questions marked blocking in
`openspec/config.yaml` (`rules.foundation`), plus the additional stack
questions raised for this project. Where the user had no strong
preference, a reasonable default was chosen and is recorded here as a
**decision**, not as an open question. Rationale is included so it can be
revisited later without re-litigating from scratch.

## Decisions

| # | Question | Decision | Rationale |
|---|---|---|---|
| 1 | Python driver for SQL Server | **pyodbc**, used directly (no SQLAlchemy layer) | This tool only needs schema introspection (read-only catalog queries), not an ORM or query builder. pyodbc gives direct control over the connection string, driver version, and catalog queries against `INFORMATION_SCHEMA`/`sys.*` with the least indirection. Requires the Microsoft ODBC Driver for SQL Server (17 or 18) installed locally. |
| 2 | Auth method | **Direct connection string per profile**, not separate server/user/password fields. Each microservice DB entry in the local config supplies its full ODBC connection string as-is (e.g. `Driver={ODBC Driver 18 for SQL Server};Server=...;Database=...;UID=...;PWD=...;` or `...;Trusted_Connection=yes;`), passed straight to `pyodbc.connect()`. The tool does not parse/reconstruct auth mode — whatever the connection string expresses (SQL auth, Windows auth, `Encrypt=`, `TrustServerCertificate=`, etc.) is honored as-is. | User explicitly requested direct connection-string access instead of a field-by-field auth model. This is also simpler and matches how developers already copy connection strings from their microservices' own `appsettings.json`/`.env` for local debugging — no need to decompose them into separate fields just to reassemble later. Still git-ignored, still never hardcoded (see Secrets below). |
| 3 | Schema discovery method | **Live database connection** is the v1 (primary) discovery method, querying `INFORMATION_SCHEMA.TABLES`, `INFORMATION_SCHEMA.COLUMNS`, and `sys.*` catalog views (`sys.tables`, `sys.columns`, `sys.key_constraints`, `sys.foreign_keys`, `sys.indexes` for the best-effort PK/FK/index extension). Exported-DDL-file discovery is deferred as a later/optional input source, not built in v1. | Live connection is simpler to keep accurate over time (no manual export step per run) and the user has direct network access to the databases as a developer. DDL-export mode is a reasonable future extension for cases where direct connectivity isn't available, but adding it now would split effort without a confirmed need. |
| 4 | Report format(s) | **HTML** as the primary/source-of-truth report (self-contained file, grouped by table, color-coded by diff type: missing table/column, type/size/nullability mismatch, likely rename) **+ in-TUI/console summary** (quick overview after each run). **PDF export** of the same HTML report ships in v1 too, via **`xhtml2pdf`** (pure-Python HTML→PDF, no external system binary/browser download required — keeps the "simple to install on any teammate's machine" constraint). **Excel/CSV export** is pushed to **v2**, deferred further than originally planned, per explicit user decision to prioritize HTML+PDF first. | HTML satisfies "reports legibles para detectar rápido qué base difiere del resto" without needing a server, and is the natural source to also "print" to PDF for sharing/archiving with people who just want a static file. `xhtml2pdf` was chosen over `weasyprint` (historically friction-prone system deps on Windows) and `playwright`/`wkhtmltopdf` (require downloading a full browser/binary) to keep setup to `pip install` only. Excel/CSV is genuinely useful for spreadsheet-style filtering but is additive, not core to "see where it differs," so it moved to v2. |
| 5 | Approx. number of microservices/databases to compare | **Unknown / not provided.** Design assumption: small-to-medium count (roughly 3-20 databases) for a single local run. Documented as an assumption to validate, not a hard blocking decision — it does not change the v1 architecture, only informs whether sequential vs. parallel extraction matters later. | The user did not state an exact count. Since the comparator design (union-of-objects N-way diff) scales the same way regardless of exact N in this range, this was treated as a non-blocking assumption rather than a question that halts foundation. Revisit if the real count is much larger (50+), where parallel extraction and incremental/caching strategies would matter more. |
| 6 | Python dependency manager | **pip + venv** (stdlib `venv`, `requirements.txt` / `pyproject.toml` with `pip`) | This is an internal, local-only developer tool intended to be simple to set up on any team member's machine without requiring an additional package manager installation (no `uv`/`poetry` prerequisite). Lowest-friction default for a small internal tool; can be revisited to `uv` later if dependency speed/lockfile reproducibility becomes a pain point. |
| 7 | UI mode | **TUI (terminal UI)**, not a plain CLI. Built with **Textual**. The app opens into an interactive screen listing saved connections (by profile name and, once resolvable, the actual database name), with a checkbox per row to mark which databases are included in the run, plus screens/actions to add, edit, and delete saved connections. | User explicitly requested an interactive TUI: persist connection strings, show database names, and let the user mark which ones to compare — this is an interaction model (persistent list + selection), not a one-shot argument-driven CLI invocation. Textual was chosen over `questionary`/`prompt_toolkit` (too limited for a persistent list+checkbox+multi-screen app) and over raw `curses` (too low-level, no built-in widgets) for its widget set (data tables, checkboxes, screens) and active maintenance. |
| 9 | HTML report styling | **Pico.css**, vendored/embedded inline in the generated HTML (not loaded from a CDN), as the base stylesheet, with a small custom CSS overlay on top just for diff-specific highlighting (row coloring by diff type: missing table/column, type/size/nullability mismatch, likely rename). No JS UI framework, no Bootstrap/Tailwind. | Pico.css is classless — it styles semantic HTML (tables, headings, layout) with no per-element classes needed, giving a polished look with minimal authoring effort. At ~10KB it stays lightweight and keeps the report a single self-contained, offline-usable file (embedding avoids a network dependency to view a locally generated report). The diff-specific coloring still needs a small custom CSS layer regardless of base framework, so Pico removes the generic styling work without adding real weight or a build step. |
| 10 | Saved-connection persistence | **Local YAML file** (`config.local.yaml`, git-ignored), read/written by the TUI itself — not a one-time-authored file the user hand-edits before running (though manual editing remains possible). Same file format as decision #2's connection-string-per-profile design. | Keeps the storage format simple, human-inspectable, and consistent with the already-decided "one named profile = one raw connection string" model; the TUI becomes the primary way to manage it, but nothing prevents a developer from editing the YAML directly if they prefer. SQLite was considered and rejected for v1 — no query/scale need justifies trading away plain-text inspectability for a small, single-user list of connections. |

## Stack Summary

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| UI | **Textual** TUI: connections screen (list + add/edit/delete + checkbox selection) and run/report screens |
| DB driver | `pyodbc` (direct), requiring Microsoft ODBC Driver 17/18 for SQL Server installed on the machine |
| Dependency management | `pip` + stdlib `venv`, dependencies declared in `pyproject.toml` (PEP 621) or `requirements.txt` |
| Config format | Local YAML connection profiles file (name → raw connection string), git-ignored, read/written by the TUI, never committed with real credentials |
| Report output | HTML (primary/source-of-truth) + PDF export via `xhtml2pdf` (v1) + in-TUI/console text summary; CSV/Excel export planned as v2 |
| Execution | Single local TUI entry point, on-demand, no background service |
| Testing | pytest, per `stack-python-testing` project standard: unit/integration/e2e layout under `tests/`, 80%+ coverage target, mock DB connections in unit tests, real (or containerized) SQL Server only in integration tests |

## Planned Project Structure (documented intent — not scaffolded by this phase)

```text
tools/
  src/
    schema_comparator/
      config/          # load & persist connection profiles (YAML), never logs secrets
      connectors/       # pyodbc connection management per profile
      discovery/        # INFORMATION_SCHEMA / sys.* extraction -> schema snapshot model
      compare/           # N-way diff engine over schema snapshots (union-of-objects baseline)
      report/            # HTML renderer, PDF export (xhtml2pdf), console summary, (v2) CSV/Excel export
      tui/               # Textual App, screens (connections list, add/edit connection, run/report)
      cli.py             # entry point, launches the Textual app
  tests/
    unit/
    integration/
  pyproject.toml
  requirements.txt (or generated from pyproject)
  README.md
```

This structure is a foundation-phase **decision**, not yet created on disk.
Actual scaffolding happens in the first `sdd-new` change (e.g.
`scaffold-project`), per the Hard Rule: no application code before
scaffold/project setup is approved.

## Architecture Style

**Modular monolith CLI**, single process, single local execution per run.
No frontend/backend split, no serverless, no microservice architecture for
the tool itself (ironic given its purpose, but intentional: this is a
small internal tool, not the system it inspects). Internally organized
into clear layers (config -> connectors -> discovery -> compare -> report)
so the diff engine stays decoupled from SQL Server I/O — worth evaluating
`hexagonal-architecture`-style ports/adapters at `sdd-design` time for the
connectors/discovery boundary if it earns its complexity.

## Connectivity & Secrets

- Each microservice DB is configured as a **named profile holding one raw
  ODBC connection string**, e.g.:

  ```yaml
  databases:
    poliza-service: "Driver={ODBC Driver 18 for SQL Server};Server=...;Database=PolizaDB;UID=...;PWD=...;TrustServerCertificate=yes;"
    siniestro-service: "Driver={ODBC Driver 18 for SQL Server};Server=...;Database=SiniestroDB;Trusted_Connection=yes;"
  ```

  The profile name is the human-readable label used throughout the diff
  reports (so the report says "missing in `siniestro-service`", not a raw
  server/DB string).
- Connection strings live in a local config file (e.g. `config.local.yaml`)
  that is **git-ignored** by convention; a `config.example.yaml` with
  placeholder connection strings is committed instead.
- The tool passes the connection string straight to `pyodbc.connect()`
  without parsing or validating its internal fields — whatever auth mode,
  encryption, or driver options it encodes are honored as-is. No secret is
  ever logged, echoed, or included in generated reports (reports reference
  the profile name only, never the connection string).
- Connections MUST use short-lived, narrow-scope reads only (schema
  catalog views); the tool never writes to the target databases.

## Discovery Query Approach

- Prefer set-based catalog queries over cursors/loops.
- Use `INFORMATION_SCHEMA.TABLES` / `INFORMATION_SCHEMA.COLUMNS` for the
  v1 must-have (tables/columns: name, type, size/precision/scale,
  nullable, ordinal position).
- Use `sys.key_constraints`, `sys.foreign_keys`, `sys.indexes` for the
  should/could-have PK/FK/index extraction.
- Reads should default to READ COMMITTED (RCSI-friendly) rather than
  `NOLOCK`, to avoid dirty reads skewing a diff — schema catalog reads are
  cheap and infrequent, so avoiding `NOLOCK` has negligible cost here.

## Testing Bar

- pytest, layout `tests/unit`, `tests/integration` (per `stack-python-testing`).
- Unit tests mock DB connections (`unittest.mock`, `autospec=True`); never
  hit a real network/DB in unit tests.
- Integration tests may run against a real or local SQL Server instance
  (e.g. developer's own dev DB, or a local SQL Server container) to
  validate catalog-query extraction.
- Target 80%+ coverage overall, with the compare/diff engine (core logic,
  no I/O) as a critical path aiming for close to 100%.
- `strict_tdd` stays `false` for now (see `openspec/config.yaml`); no test
  runner exists yet since no code exists yet. Recommended to flip
  `testing.strict_tdd_mode` to enabled once `pyproject.toml`/pytest are
  scaffolded in the first SDD change.

## Delivery Target

- Local only. No container, no CI/CD, no cloud deployment in v1 — this is
  an internal dev tool run from a developer's machine.
- No target environments beyond "wherever a developer has Python + the
  ODBC driver + network access to the SQL Server instances being compared."

## Open Questions

None blocking. See table above for defaults taken and their rationale;
revisit item #5 (approx. database count) if the assumed range (3-20)
turns out to be significantly wrong once real connection profiles are
configured.
