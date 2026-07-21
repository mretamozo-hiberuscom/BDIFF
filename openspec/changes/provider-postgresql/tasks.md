# Tasks — `provider-postgresql`

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

## Phase 1 — Package & Infrastructure Setup
- [x] 1.1 Crear paquete `src/schema_comparator/infrastructure/providers/postgresql/` y su `__init__.py`.
- [x] 1.2 Crear `errors.py` con traducción de excepciones de `psycopg` a excepciones neutras de dominio/infraestructura.
- [x] 1.3 Crear `profile_parser.py` para parseo y validación de perfiles y opciones de conexión PostgreSQL.
- [x] 1.4 Crear `connection.py` para gestión de conexiones PostgreSQL con `psycopg`.

## Phase 2 — Introspector & DDL Renderer
- [x] 2.1 Crear `introspector.py` con consultas a `information_schema` y `pg_catalog` (tablas, columnas, tipos canónicos, serial, identity, defaults).
- [x] 2.2 Crear `ddl_renderer.py` con renderizado de DDL PostgreSQL (quoting `"name"`, `CREATE TABLE`, `ADD COLUMN`, `ALTER COLUMN TYPE ... USING`, `DROP COLUMN`).
- [x] 2.3 Crear `provider.py` con la clase `PostgreSqlProvider` e implementación de `ProviderCapabilities`.

## Phase 3 — Provider Registry & Optional Dependencies
- [x] 3.1 Registrar `PostgreSqlProvider` mediante fábrica diferida (`register_factory`) en `src/schema_comparator/infrastructure/providers/registry.py`.
- [x] 3.2 Verificar / actualizar la sección `[project.optional-dependencies]` en `pyproject.toml`.

## Phase 4 — Testing & Golden Fixtures
- [x] 4.1 Crear golden file DDL en `tests/fixtures/golden/postgresql/postgresql_golden.sql`.
- [x] 4.2 Crear suite de pruebas unitarias y de contrato en `tests/unit/infrastructure/test_postgresql_provider.py`.
- [x] 4.3 Ejecutar suite completa de pytest y verificar 0 fallos.
