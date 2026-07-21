# Proposal — `provider-postgresql`

## Intent

Incorporar el soporte completo para PostgreSQL como el segundo proveedor de bases de datos en BDIFF, permitiendo la introspección de catálogos y esquemas (`information_schema` y `pg_catalog`), la comparación N-way homogénea entre esquemas PostgreSQL, la generación de DDL específico para PostgreSQL (`CREATE TABLE`, `ALTER TABLE ... ADD COLUMN`, `ALTER COLUMN TYPE ... USING`, `DROP COLUMN`) con quoting de identificadores por comillas dobles (`"name"`), e integrando `PostgreSqlProvider` mediante carga diferida (*lazy loading*) con el extra opcional `psycopg[binary]`.

## Scope

1. **`src/schema_comparator/infrastructure/providers/postgresql/`**:
   - `__init__.py`: Exportar `PostgreSqlProvider`.
   - `connection.py`: Gestión de conexión `psycopg` (v3).
   - `introspector.py`: Consultas SQL a `information_schema` y `pg_catalog` para construir `SchemaSnapshot` con `QualifiedName`, `SqlType` y atributos de columna.
   - `profile_parser.py`: Validación de DSN/cadenas de conexión y opciones específicas de PostgreSQL.
   - `ddl_renderer.py`: Renderizador DDL PostgreSQL con quoting de comillas dobles `"..."`.
   - `errors.py`: Mapeo de excepciones de `psycopg` a excepciones neutras de dominio.
   - `provider.py`: Clase `PostgreSqlProvider` que implementa `DatabaseProvider` y expone `ProviderCapabilities` específicas de PostgreSQL.

2. **Registro & Empaquetado**:
   - Registrar `postgresql` en `ProviderRegistry` mediante `register_factory`.
   - Asegurar el extra opcional `postgresql = ["psycopg[binary]"]` en `pyproject.toml`.

3. **Pruebas**:
   - Tests unitarios y de contrato para `PostgreSqlProvider` con mocks/fixtures.
   - Golden file DDL para PostgreSQL en `tests/fixtures/golden/postgresql/postgresql_golden.sql`.

## Rollback Plan

Eliminar el directorio `src/schema_comparator/infrastructure/providers/postgresql/` y desregistrar `postgresql` de `ProviderRegistry`.
