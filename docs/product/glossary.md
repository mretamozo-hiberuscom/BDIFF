# Glosario — BDIFF

| Término | Significado en este proyecto |
|---|---|
| Perfil de conexión | Entrada con nombre de `config.local.yaml`: `provider`, `connection_string` y `options`. El nombre del perfil es lo que aparece en reportes; la cadena nunca. |
| Proveedor (provider) | Adaptador de un motor (`sqlserver`, `postgresql`, `mysql`, `mariadb`, `oracle`, `sqlite`) registrado en `ProviderRegistry`. |
| Snapshot de esquema | Metadatos extraídos de una base en un momento: tablas, columnas, procedimientos y, cuando se extraigan, PK, FK e índices. |
| Deriva de esquema (drift) | Cualquier diferencia estructural entre bases que deberían compartir estructura. |
| Línea base (baseline) de comparación | No es una base fija: es la unión de todos los objetos vistos en las bases comparadas. Lo que falta respecto a esa unión se reporta. |
| Identidad de objeto | Clave con la que se emparejan tablas y columnas entre bases. Se normaliza: insensible a mayúsculas, sin esquema en MySQL/MariaDB y con el owner por defecto normalizado en Oracle (decisión 2026-10-21). |
| Tabla o columna faltante | Objeto presente en al menos una base y ausente en otra. |
| Discrepancia (mismatch) | Objeto presente en varias bases con atributos distintos (tipo, tamaño, nulabilidad, default, identity, collation, PK, FK, índice o definición de rutina). |
| Modo `native-strict` | Comparación por tipo nativo exacto; pensada para perfiles del mismo motor (ADR 0003). |
| Modo `semantic` | Comparación por familia de tipo entre motores distintos; opt-in (ADR 0003). |
| Consolidación | Pantalla de la TUI donde se decide, por hallazgo, qué estado debe quedar y en qué bases; produce scripts T-SQL que nadie ejecuta automáticamente. |
| Mantenimiento de metadatos | Escritura acotada y confirmada sobre una base comparada que no cambia estructura ni datos; hoy `sp_refreshsqlmodule` (ADR 0006). |
| Validación de rutinas | Comprobación de solo lectura de las dependencias de procedimientos y vistas en SQL Server. |
| Reporte de deriva | Salidas de una ejecución: resumen de consola, HTML, PDF y Excel. |
| Likely rename | Heurística (no implementada) para emparejar columnas con distinto nombre que representan el mismo campo. |
