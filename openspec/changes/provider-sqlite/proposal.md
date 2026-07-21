# Proposal — `provider-sqlite`

## Intent

Incorporar el soporte nativo para SQLite como el tercer proveedor de bases de datos en BDIFF, permitiendo la introspección de esquemas y tablas mediante el módulo estándar `sqlite3` de Python (sin dependencias de drivers de terceros), la comparación N-way homogénea entre bases SQLite (`main`, `temp` y bases adjuntas), la generación de DDL específico para SQLite (`CREATE TABLE`, `ALTER TABLE ... ADD COLUMN`) y la estrategia de reconstrucción de tablas (`table rebuild`) para operaciones DDL no soportadas por la sintaxis nativa de SQLite.

## Scope

1. **`src/schema_comparator/infrastructure/providers/sqlite/`**:
   - `__init__.py`: Exportar `SqliteProvider`.
   - `connection.py`: Conector `sqlite3` para archivos locales y bases en memoria (`:memory:`).
   - `introspector.py`: Consultas a `sqlite_schema` y `PRAGMA table_xinfo` para construir `SchemaSnapshot` con `QualifiedName`, `SqlType` (*type affinity*), nullability, defaults y columnas generadas.
   - `profile_parser.py`: Validación de rutas de base de datos SQLite y URI options.
   - `ddl_renderer.py`: Renderizador DDL SQLite con quoting de identificadores y planificador de reconstrucción de tabla (`table rebuild`).
   - `errors.py`: Mapeo de excepciones `sqlite3.Error` a excepciones de dominio.
   - `provider.py`: Clase `SqliteProvider` que implementa `DatabaseProvider` y expone `ProviderCapabilities` (`supports_schemas=False`, `supports_transactional_ddl=True`, `requires_table_rebuild_for_alter=True`).

2. **Registro & Empaquetado**:
   - Registrar `sqlite` en `ProviderRegistry` mediante `register_factory` en `get_default_registry()`.

3. **Pruebas**:
   - Tests unitarios y de contrato para `SqliteProvider` con bases `:memory:`.
   - Golden file DDL para SQLite en `tests/fixtures/golden/sqlite/sqlite_golden.sql`.

## Rollback Plan

Eliminar el directorio `src/schema_comparator/infrastructure/providers/sqlite/` y desregistrar `sqlite` de `ProviderRegistry`.
