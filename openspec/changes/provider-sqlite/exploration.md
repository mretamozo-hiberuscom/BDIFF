# Exploration — `provider-sqlite`

## Context & Objectives

SQLite es una base de datos embebida ampliamente utilizada que difiere significativamente de los servidores RDBMS tradicionales (como SQL Server y PostgreSQL):

1. **Sin servidor cliente-servidor**: Se conecta directamente a archivos locales de disco o a bases de datos en memoria (`:memory:`).
2. **Biblioteca Estándar de Python**: El módulo `sqlite3` está incluido en Python, por lo que no requiere instalar drivers de terceros (`pip install`).
3. **Estructura de Esquemas**: Trabaja con `main` como esquema primario, `temp` para objetos temporales y esquemas nombrados para bases adjuntas (`ATTACH DATABASE`).
4. **Sistema de Tipos y *Type Affinity***: SQLite utiliza afinidad de tipos dinámica (`INTEGER`, `REAL`, `TEXT`, `BLOB`, `NUMERIC`). Mantiene el tipo declarado por el usuario en las columnas pero agrupa la afinidad en 5 familias.
5. **Limitaciones DDL**: SQLite no soporta `ALTER COLUMN TYPE` ni `ALTER COLUMN SET/DROP NOT NULL`. Algunas versiones de SQLite tampoco soportan `DROP COLUMN`. Para aplicar alteraciones estructurales complejas a columnas existentes, la estrategia estándar de SQLite es **`table rebuild`** (creación de tabla temporal -> migración de datos -> reemplazo de tabla original).

## Exploration Findings & Architectural Decisions

- **Conexión & Perfiles**: `SqliteProvider` debe validar que `connection_string` sea una ruta a archivo válida o el identificador especial `:memory:`.
- **Introspección**:
  - `sqlite_schema` (o `sqlite_master`) para listar tablas de tipo `BASE TABLE`.
  - `PRAGMA table_xinfo("table_name")` (o `PRAGMA table_info`) para extraer metadatos de columnas: `cid`, `name`, `type`, `notnull`, `dflt_value`, `pk`, `hidden` (columnas generadas).
- **Capacidades**:
  - `supports_schemas = False` (los nombres de objeto son cualificados como `main.table` o simplemente `table`).
  - `supports_transactional_ddl = True` (SQLite soporta DDL en transacciones `BEGIN TRANSACTION` / `COMMIT`).
  - `supports_alter_column = False` (requiere `requires_table_rebuild_for_alter = True`).
- **Estrategia Table Rebuild**:
  - Para adición de columnas simples: `ALTER TABLE "table" ADD COLUMN "col" TYPE NULL/NOT NULL`.
  - Para modificaciones de columnas discrepantes:
    ```sql
    PRAGMA foreign_keys = OFF;
    BEGIN TRANSACTION;
    CREATE TABLE "table_dg_tmp" AS SELECT * FROM "table";
    DROP TABLE "table";
    ALTER TABLE "table_dg_tmp" RENAME TO "table";
    COMMIT;
    PRAGMA foreign_keys = ON;
    ```
