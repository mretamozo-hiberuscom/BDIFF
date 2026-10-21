# Product Brief — BDIFF (schema-comparator)

> Baseline brownfield revisado el 2026-10-21 contra el código v1.2.5. El
> brief original (2026-07, solo SQL Server) queda resumido al final en
> "Cambios respecto al brief original".

## Decisión

BDIFF es una herramienta local en Python, **pensada sobre todo para
Windows**, que extrae el esquema de N bases de datos (2 o más), las compara
todas contra la unión de sus objetos y responde rápido a "¿qué base difiere
del resto y dónde?". Produce reportes legibles (consola, HTML, PDF, Excel)
y, para SQL Server, scripts T-SQL de consolidación y de reparación de
rutinas que una persona revisa y ejecuta por su cuenta.

## Problema

Varios microservicios del dominio seguros tienen cada uno su base de datos
y deberían compartir estructura (tablas y columnas que representan los
mismos conceptos). Como cada base evoluciona por separado, la deriva se
acumula sin que nadie la vea:

- Una columna o tabla existe en una base y falta en otra.
- La misma columna tiene distinto tipo, tamaño, precisión o nulabilidad.
- Procedimientos almacenados difieren o tienen dependencias rotas.

Hoy se descubre tarde, cuando algo falla en integración o en una migración.

## Usuarios

| Usuario | Uso |
|---|---|
| Autor y responsable (desarrollador del equipo) | Ejecuta BDIFF en su máquina Windows contra bases locales o de desarrollo, mantiene y versiona la herramienta. |
| Otros desarrolladores del equipo | Leen los reportes generados para ver dónde diverge el esquema de su servicio. |

Es una herramienta interna de desarrollo, no un producto para el negocio
de seguros ni un sistema productivo.

## Resultado esperado

El desarrollador ejecuta `python run.py --config config.local.yaml` (o con
`--tui`) y obtiene, por tabla y columna:

- En qué bases existe cada objeto y en cuáles falta.
- Discrepancias de tipo, tamaño/precisión/escala, nulabilidad, default,
  identity y collation para columnas presentes en más de una base.
- Diferencias de procedimientos almacenados (SQL Server).
- Una forma rápida de ver qué base es la atípica.

## Objetivos

| Id | Objetivo |
|---|---|
| G1 | Detectar la deriva estructural entre bases del mismo motor sin falsos positivos. |
| G2 | Funcionar sin fricción en Windows: instalación con un Python del sistema, drivers ODBC 17/18, salida legible en consola. |
| G3 | Nunca alterar la estructura ni los datos de una base comparada (ver ADR 0005 y 0006). |
| G4 | Soportar varios motores (SQL Server, PostgreSQL, MySQL, MariaDB, Oracle, SQLite) instalando solo el driver que se usa. |

Medidas de éxito: no hay medidas numéricas acordadas; se registran como
`unknown` en `docs/architecture/knowledge-map.yaml`.

## No objetivos

- No es una herramienta de migración: no ejecuta DDL contra ninguna base
  (ADR 0005). La única escritura permitida es el mantenimiento de metadatos
  con confirmación explícita (ADR 0006).
- No es un servicio continuo: ejecución local bajo demanda.
- Sin interfaz web ni componente servidor.
- Sin reconciliación automática: las personas deciden qué hacer con la
  deriva y ejecutan los scripts.
- Sin comparación de datos (filas, contenido): solo estructura.
- La gestión de conexiones (alta, edición, borrado) no está en la TUI: los
  perfiles se editan en el YAML local.

## Restricciones

| Restricción | Valor | Fuente |
|---|---|---|
| Plataforma principal | Windows (Linux soportado para desarrollo y CI) | Usuario, 2026-10-21 |
| Ejecución | Local, bajo demanda, CLI con TUI opcional | Usuario (brief original) |
| Credenciales | Solo en config local ignorada por git; nunca en código, logs ni reportes | Usuario (brief original) |
| Motores | SQL Server (principal) + PostgreSQL, MySQL, MariaDB, Oracle, SQLite | Código: `infrastructure/providers/registry.py:100` |
| Escritura en BD | Solo mantenimiento de metadatos confirmado | ADR 0006 |
| Número de bases | Supuesto 3-20 por ejecución, sin validar | Brief original (supuesto) |

## Cambios respecto al brief original (2026-07)

| El brief original decía | Hoy |
|---|---|
| Solo SQL Server | 6 motores registrados; SQL Server sigue siendo el principal y el único con rutinas y scripts. |
| La TUI es la entrada y gestiona conexiones | La entrada es el CLI; `--tui` abre un navegador de hallazgos con consolidación y rutinas. Las conexiones viven en el YAML. |
| "No escribe en ninguna base" | Escribe solo para recompilar metadatos de rutinas, con confirmación (ADR 0006). |
| Detección de renombres (Should v1) | No implementada; queda en el roadmap. |
| Excel en v2 | Implementado. CSV no. |
