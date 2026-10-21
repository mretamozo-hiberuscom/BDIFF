# 0006. Mantenimiento de metadatos con confirmación explícita

- Status: accepted
- Date: 2026-10-21
- Evidence: src/schema_comparator/cli.py:179, src/schema_comparator/infrastructure/providers/sqlserver/sp_validator.py:313, src/schema_comparator/infrastructure/providers/sqlserver/sp_validator.py:360

## Context and drivers

La ADR 0005 fija que BDIFF genera artefactos DDL pero nunca ejecuta
alteraciones de esquema, y el brief original declaraba que la herramienta
"no escribe en ninguna base de datos". Desde la v1.2.0 existe, sin embargo,
una operación que sí escribe: la recompilación de metadatos de rutinas
(`sp_refreshsqlmodule`) desde el CLI (`--refresh-modules` / `--verify-sps`
con `--yes`) y desde la pantalla de rutinas de la TUI (con modal de
confirmación). El usuario decidió el 2026-10-21 mantenerla y documentarla.

Drivers: `constraint:no-ddl-execution` (nunca alterar estructura de las
bases comparadas), `scenario:mutation-requires-confirmation` (ninguna
escritura sin confirmación explícita del usuario).

## Options considered
1. Eliminar la recompilación: BDIFF queda estrictamente de solo lectura;
   cuesta perder una reparación que los usuarios ya usan para detectar y
   corregir módulos con metadatos obsoletos.
2. Permitir solo mantenimiento de metadatos con confirmación explícita:
   conserva la capacidad, acota la escritura a una operación que no cambia
   la estructura de tablas ni datos, y exige confirmación por ejecución.
3. Permitir ejecutar también los scripts DDL generados: máxima comodidad,
   pero contradice la ADR 0005 y expone a pérdida de datos.

## Decision
Se elige la opción 2. BDIFF solo puede escribir en una base comparada para
operaciones de mantenimiento de metadatos que no alteran estructura ni
datos (hoy: recompilación de módulos de SQL Server). Cada ejecución exige
una confirmación explícita del usuario (bandera de confirmación en el CLI,
diálogo modal en la TUI), validada antes de abrir cualquier conexión. La
ejecución de DDL generado sigue prohibida, como fija la ADR 0005, que esta
decisión amplía sin sustituir.

## Consequences
- Más fácil: reparar dependencias rotas de rutinas sin salir de BDIFF.
- Más difícil: la herramienta deja de ser de solo lectura; los mensajes de
  error, la ayuda y la documentación deben distinguir validación (lectura)
  de recompilación (escritura).
- Prohibido: cualquier otra escritura (DDL, DML, cambios de permisos) y
  cualquier mutación sin confirmación previa.

## Fitness function
- Toda llamada a `commit()` sobre una conexión de base comparada vive en
  `sqlserver/sp_validator.py` y solo es alcanzable desde rutas con
  confirmación (bandera del CLI o modal de la TUI).
- Un test del CLI comprueba que la bandera mutante sin confirmación termina
  con error antes de abrir ninguna conexión.

## Review trigger
Una petición de ejecutar otra operación de escritura (DDL generado,
migraciones, permisos) o de soportar mantenimiento de metadatos en otro
motor.
