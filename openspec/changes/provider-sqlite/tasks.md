# Tasks — `provider-sqlite`

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Phase 1 — Package & Infrastructure Setup
- [x] 1.1 Crear paquete `src/schema_comparator/infrastructure/providers/sqlite/` y su `__init__.py`.
- [x] 1.2 Crear `errors.py` con traducción de excepciones de `sqlite3` a excepciones de dominio.
- [x] 1.3 Crear `profile_parser.py` para parseo y validación de rutas y cadenas de conexión SQLite (soporte de rutas y `:memory:`).
- [x] 1.4 Crear `connection.py` para gestión de conexiones SQLite con `sqlite3`.

## Phase 2 — Introspector & DDL Renderer
- [x] 2.1 Crear `introspector.py` con introspección mediante `sqlite_master` y `PRAGMA table_xinfo` (tablas, columnas, afinidad de tipos, defaults, nulos y PKs).
- [x] 2.2 Crear `ddl_renderer.py` con renderizado DDL SQLite (`CREATE TABLE`, `ADD COLUMN`) y estrategia de reconstrucción de tabla (`table rebuild`).
- [x] 2.3 Crear `provider.py` con la clase `SqliteProvider` e implementación de `ProviderCapabilities`.

## Phase 3 — Provider Registry Integration
- [x] 3.1 Registrar `SqliteProvider` mediante fábrica diferida (`register_factory`) en `src/schema_comparator/infrastructure/providers/registry.py`.

## Phase 4 — Testing & Golden Fixtures
- [x] 4.1 Crear golden file DDL en `tests/fixtures/golden/sqlite/sqlite_golden.sql`.
- [x] 4.2 Crear suite de pruebas unitarias y de contrato en `tests/unit/infrastructure/test_sqlite_provider.py`.
- [x] 4.3 Ejecutar suite completa de pytest y verificar 0 fallos.
