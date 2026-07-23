# Changelog

Todas las modificaciones destacables de este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/), y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [1.1.0] - 2026-07-23

### Añadido
- Organización automática de scripts DDL generados dentro de subcarpetas con marcas temporales en `scripts-db/<YYYYMMDD_HHMMSS>/`.
- Organización automática de reportes generados (HTML, PDF, Excel) dentro de subcarpetas con marcas temporales en `reportes/<YYYYMMDD_HHMMSS>/`.
- Generación automática del reporte de impacto `impact_report.md` en `scripts-db/<YYYYMMDD_HHMMSS>/`, detallando cambios por perfil, evaluación de riesgos en procedimientos almacenados, consultas T-SQL sobre `sys.sql_expression_dependencies` y recomendaciones `sp_recompile`.
- Sanitización de nombres de archivo de perfiles y desduplicación de nombres para evitar colisiones en el sistema de archivos.

## [1.0.0] - 2026-07-23

### Añadido
- Modo de comparación semántica opt-in (`ComparisonMode.SEMANTIC_EQUIVALENT`) para comparación heterogénea entre distintos motores de bases de datos (SQL Server, PostgreSQL, SQLite, MySQL, MariaDB, Oracle).
- Matriz de equivalencia semántica de tipos en `src/schema_comparator/domain/comparison/type_equivalences.py` (`STRING`, `INTEGER`, `BOOLEAN`, `FLOAT`, `DECIMAL`, `DATETIME`, `BINARY`, `UUID`, `JSON`).
- Preservación estricta de diferencias de longitud, precisión, escala y nullability durante la normalización semántica.
- Pruebas unitarias completas de comparación heterogénea en `tests/unit/compare/test_cross_provider_semantic.py`.
- Estabilización de la arquitectura multibase de datos y API pública v1.0.0.

## [0.10.0] - 2026-07-21

### Añadido
- Modelos de dominio para restricciones de clave primaria (`PrimaryKeySnapshot`), clave foránea (`ForeignKeySnapshot` con `referenced_schema`) e índices (`IndexSnapshot`) en `src/schema_comparator/domain/schema/models.py`.
- Modelos de discrepancia (`PrimaryKeyMismatch`, `ForeignKeyMismatch`, `IndexMismatch`) en `src/schema_comparator/domain/comparison/models.py`.
- Extensión del motor de comparación N-way (`compare/engine.py`) para evaluar derivas en claves primarias, foráneas e índices entre perfiles de base de datos.
- Pruebas unitarias de inmutabilidad y detección de derivas en `tests/unit/domain/test_advanced_schema_objects.py`.

## [0.9.0] - 2026-07-21

### Añadido
- Adaptador del proveedor Oracle Database (`OracleProvider`) en `src/schema_comparator/infrastructure/providers/oracle/`.
- Introspección de catálogos sobre `ALL_TAB_COLS` y `ALL_TABLES` mapeando `OWNER` a esquema y detectando identidades `GENERATED AS IDENTITY`.
- Generador de scripts DDL para Oracle (`ddl_renderer.py`) con quoting de comillas dobles (`"..."`), sentencias `ADD (...)` y `MODIFY (...)`.
- Carga diferida (*lazy loading*) de `oracle` en `ProviderRegistry` y extra opcional `oracle = ["oracledb>=2.0"]` en `pyproject.toml`.
- Suite de pruebas unitarias para el proveedor Oracle en `tests/unit/infrastructure/test_oracle_provider.py`.

## [0.8.0] - 2026-07-21

### Añadido
- Proveedores de infraestructura MySQL (`MySqlProvider`) y MariaDB (`MariaDbProvider`) bajo el paquete reutilizable `mysql_family`.
- Introspección de catálogos mediante `information_schema.columns` e `information_schema.tables` con soporte para atributos nativos (`UNSIGNED`, `AUTO_INCREMENT`, `ENUM`, `SET`, `TINYINT(1)` / `BOOLEAN`).
- Renderizado de scripts DDL para MySQL y MariaDB (`ddl_renderer.py`) con quoting de backticks (`` `...` ``), `ALTER TABLE ... ADD COLUMN`, `ALTER TABLE ... MODIFY COLUMN` y desactivación temporal de foreign keys (`SET FOREIGN_KEY_CHECKS = 0`).
- Carga diferida (*lazy loading*) de `mysql` y `mariadb` en `ProviderRegistry` y extras opcionales `mysql` y `mariadb` (`pymysql>=1.1`) en `pyproject.toml`.
- Suite de pruebas unitarias para proveedores MySQL/MariaDB en `tests/unit/infrastructure/test_mysql_mariadb_provider.py`.

## [0.7.0] - 2026-07-21

### Añadido
- Adaptador del proveedor SQLite (`SqliteProvider`) en `src/schema_comparator/infrastructure/providers/sqlite/`.
- Introspección nativa con la biblioteca estándar `sqlite3` usando `sqlite_master` y `PRAGMA table_xinfo` (tablas, columnas, afinidad de tipos, defaults, nulos y autoincrement ROWID identity).
- Renderizado de scripts DDL para SQLite (`ddl_renderer.py`) con quoting de comillas dobles (`"..."`), adición segura de columnas `ALTER TABLE ... ADD COLUMN` con valores por defecto y estrategia de reconstrucción de tabla (`table rebuild`) para modificaciones complejas.
- Registro en `ProviderRegistry` (`get_default_registry()`).
- Fixture golden file DDL en `tests/fixtures/golden/sqlite/sqlite_golden.sql` y suite de pruebas unitarias/contrato en `tests/unit/infrastructure/test_sqlite_provider.py`.

## [0.6.0] - 2026-07-21

### Añadido
- Adaptador del proveedor PostgreSQL (`PostgreSqlProvider`) en `src/schema_comparator/infrastructure/providers/postgresql/`.
- Introspección completa de catálogos y esquemas PostgreSQL (`information_schema` y `pg_catalog`) soportando familias de tipos, nullability, ordinal position, expresiones por defecto y secuencias/identidades.
- Generador de scripts DDL para PostgreSQL (`ddl_renderer.py`) con quoting de comillas dobles (`"..."`), sentencias de alteración selectivas (`TYPE ... USING CAST(...)`, `SET/DROP NOT NULL`) y transacciones `BEGIN; ... COMMIT;`.
- Carga diferida (*lazy loading*) de `postgresql` en `ProviderRegistry` (`get_default_registry()`) y extra opcional `postgresql = ["psycopg[binary]>=3.1"]` en `pyproject.toml`.
- Fixture golden file en `tests/fixtures/golden/postgresql/postgresql_golden.sql` y suite de pruebas unitarias/contrato en `tests/unit/infrastructure/test_postgresql_provider.py`.

## [0.5.0] - 2026-07-21

### Añadido
- Estrategia dinámica de relleno de valores nulos (Null-Backfill Strategy) previa a la conversión de columnas a `NOT NULL` en scripts DDL T-SQL (`_get_default_backfill_literal`), evitando errores de restricción 515.
- Selección por defecto del valor 'No hacer nada' / 'Ignorar' (`(None, ())`) en la pantalla interactiva de decisiones (`DecisionScreen`) del TUI de consolidación.

## [0.4.0] - 2026-07-21

### Añadido
- Manejo seguro y dinámico de Foreign Keys, restricciones Únicas/Primarias (`sys.key_constraints`), restricciones `CHECK` (`sys.check_constraints`), restricciones por Defecto (`sys.default_constraints`) e Índices (`sys.indexes`) en la generación de scripts DDL de consolidación (`DROP TABLE` y `DROP COLUMN`).
- Captura de restricciones `CHECK` a nivel de tabla mediante `sys.sql_expression_dependencies`.
- Quoting seguro T-SQL (`QUOTENAME()`) para identificadores dinámicos y desduplicación `DISTINCT` para evitar sentencias repetidas.
- Escape de comillas simples (`_escape_literal`) en mensajes `PRINT` de todos los bloques DDL.
- Limpieza de comillas y corchetes en `extract_database_name`.
- Pruebas unitarias dedicadas en `tests/unit/sqlserver/test_ddl_renderer_dependencies.py`.

## [0.3.0] - 2026-07-21

### Añadido
- Arquitectura desacoplada basada en Hexagonal (Puertos y Adaptadores).
- Hoja de ruta arquitectónica para soporte multitarget (PostgreSQL, Oracle, MySQL, SQLite, SQL Server) y ADRs 0001 a 0005 en `docs/architecture/`.
- Registro interno de proveedores de base de datos (`ProviderRegistry`) con carga diferida (*lazy loading*).
- Formato de configuración v2 (`ConnectionProfile`) compatible con especificación de proveedor y opciones por perfil.
- Modelos de dominio canónicos: `QualifiedName`, `SqlType`, `TypeFamily`, `ProviderCapabilities` y política `native-strict`.
- Adaptador extraído de SQL Server (`SqlServerProvider`) en `infrastructure/providers/sqlserver/`.
- Escapado de seguridad T-SQL (`]` -> `]]`, `'` -> `''`) en el generador de scripts DDL para prevenir inyección SQL.

### Cambiado
- Re-exportación transparente en conectores, discovery y consolidación para garantizar 100% de compatibilidad hacia atrás.

## [0.2.0] - 2026-07-20

### Añadido
- Agrupamiento de entradas de `MissingColumn` en un único bloque de decisión (`MergedMissingColumn`) dentro de `DecisionScreen` en la consolidación del TUI.
- Selección por defecto de todos los perfiles ausentes al agregar columnas faltantes en múltiples perfiles.
- Filtrado automático al seleccionar eliminación (`DROP COLUMN`), mostrando únicamente los perfiles donde la columna sí existe.
- Requisito `REQ-interactive-tui-014` y escenarios en la especificación OpenSpec de `interactive-tui`.
- Pruebas unitarias para validar `MergedMissingColumn` en `tests/unit/tui/test_decision_screen.py`.
