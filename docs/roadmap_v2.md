# Roadmap OpenSpec — Estabilización de Providers de BDIFF

## Objetivo

Convertir la implementación multi-provider actual de BDIFF en un sistema realmente operativo, verificable y seguro, conectando los providers al flujo principal, formalizando sus contratos y endureciendo la introspección y generación DDL de cada motor.

Los changes ya archivados permanecen como historial. Este roadmap se implementará mediante nuevos changes correctivos y evolutivos; no se reabrirán ni se reescribirán los changes anteriores.

---

# Horizonte 0 — Corregir el núcleo y activar realmente los providers

## Change 01 — `fix-advanced-object-comparison-semantics`

**Modo:** Standard SDD
**Prioridad:** P0 — Correctness blocker
**Dependencias:** Ninguna

### Objetivo

Corregir la comparación de Primary Keys, Foreign Keys e índices para comparar exclusivamente sus valores estructurales, no las tuplas que contienen el nombre del perfil.

### Alcance

* Corregir la igualdad de PK, FK e índices.
* Añadir pruebas donde dos perfiles tengan objetos idénticos.
* Añadir escenarios de objeto faltante, objeto diferente y orden determinista.
* Definir si los nombres de constraints e índices forman parte de la igualdad estructural.
* Verificar que no aparecen falsos positivos.

### Criterio de salida

Dos snapshots estructuralmente iguales producen cero discrepancias avanzadas.

### Clasificación

Aunque la modificación de código será pequeña, no es Lite: afecta la corrección del motor central.

---

## Change 02 — `wire-provider-runtime-dispatch`

**Modo:** Standard SDD
**Prioridad:** P0 — Architecture blocker
**Dependencias:** Change 01

### Objetivo

Hacer que CLI, TUI y `CompareProfilesUseCase` resuelvan cada perfil mediante `ProviderRegistry`, utilizando `profile.provider`.

### Alcance

* Introducir un servicio de extracción provider-aware.
* Resolver el provider mediante `ProviderRegistry.require()`.
* Ejecutar `validate_profile()` e `introspect()` del provider correspondiente.
* Eliminar la inyección predeterminada del extractor SQL Server legado.
* Mantener compatibilidad con perfiles legacy, cuyo provider predeterminado es `sqlserver`.
* Unificar errores de provider inexistente, driver ausente, conexión y metadatos.
* Añadir pruebas con perfiles mezclados y providers simulados.

### Criterio de salida

Un perfil `oracle`, `postgresql`, `sqlite`, `mysql` o `mariadb` utiliza realmente su implementación durante una ejecución normal de CLI o TUI.

---

## Change 03 — `enforce-provider-aware-comparison-policy`

**Modo:** Standard SDD
**Prioridad:** P0
**Dependencias:** Change 02

### Objetivo

Impedir comparaciones nativas accidentalmente inválidas entre motores diferentes.

### Alcance

* Incorporar `provider_id` y, cuando esté disponible, versión del motor al snapshot.
* Aplicar `native-strict` como política predeterminada.
* Rechazar snapshots de motores distintos en `native-strict`.
* Reservar `semantic-equivalent` para el futuro change de comparación semántica.
* Mostrar un error accionable cuando los providers no sean compatibles.

### Criterio de salida

BDIFF nunca compara silenciosamente `VARCHAR2`, `varchar`, `nvarchar` o afinidades SQLite como si fueran contratos nativos equivalentes.

---

## Change 04 — `introduce-provider-migration-planning-port`

**Modo:** Standard SDD
**Prioridad:** P0
**Dependencias:** Changes 02 y 03

### Objetivo

Eliminar la dependencia directa del pipeline de consolidación respecto al renderer T-SQL.

### Alcance

* Introducir operaciones neutrales de migración:

  * `CreateTable`
  * `AddColumn`
  * `AlterColumn`
  * `DropColumn`
  * `DropTable`
  * operaciones de constraints e índices.
* Introducir un `MigrationPlan`.
* Clasificar operaciones como:

  * seguras;
  * potencialmente destructivas;
  * requieren backfill;
  * requieren rebuild;
  * requieren intervención manual.
* Incorporar un puerto de planificación/renderizado por provider.
* Resolver el renderer según el provider del perfil destino.
* Prohibir la generación de SQL cuando el provider no pueda representar una operación de forma segura.

### Criterio de salida

No existe ninguna importación directa del renderer SQL Server desde el flujo neutral de consolidación.

---

## Change 05 — `formalize-provider-capabilities-contract`

**Modo:** Standard SDD
**Prioridad:** P0
**Dependencias:** Change 04

### Objetivo

Convertir `ProviderCapabilities` en un contrato útil para planificación, comparación y generación DDL.

### Alcance

* Añadir `capabilities()` al `DatabaseProvider` Protocol.
* Ampliar las capacidades para representar:

  * soporte de schemas y catálogos;
  * DDL transaccional;
  * alteración directa o mediante rebuild;
  * identidad y columnas generadas;
  * defaults, collations y comments;
  * PK, FK, unique, check e índices;
  * operaciones destructivas;
  * diferencias por versión del motor.
* Añadir capacidades al provider SQL Server.
* Validar que cada provider declarado satisface el Protocol.
* Añadir una suite común de tests de contrato.

### Criterio de salida

El planificador nunca presupone una operación únicamente porque otro motor la soporte.

---

# Horizonte 1 — Endurecimiento de providers por riesgo

## Change 06 — `harden-oracle-provider`

**Modo:** Standard SDD
**Prioridad:** P0 — Alto riesgo
**Dependencias:** Changes 02–05

### Objetivo

Hacer que Oracle tenga introspección fiel, conexión robusta y DDL conservador.

### Alcance

* Sustituir la blacklist global de owners por configuración explícita de alcance.
* Definir comportamiento para schemas visibles mediante `ALL_*`.
* Modelar o excluir explícitamente columnas ocultas, invisibles y virtuales.
* Preservar semántica de longitud `BYTE` frente a `CHAR`.
* Mejorar defaults, identidad, collations y tipos temporales.
* Soportar DSN completo, Easy Connect y descriptores de conexión sin reinterpretarlos como simples hosts.
* Clasificar `MODIFY` por seguridad:

  * ampliación compatible;
  * conversión con riesgo;
  * cambio no ejecutable automáticamente;
  * cambio a `NOT NULL` que requiere prevalidación o backfill.
* Prohibir `MODIFY` directo cuando no se pueda demostrar su seguridad.
* Añadir pruebas de integración contra Oracle real o un entorno CI controlado.
* Añadir golden files de DDL.

### Criterio de salida

El provider Oracle no genera automáticamente una modificación que pueda fallar o causar pérdida de datos sin advertencia explícita.

---

## Change 07 — `implement-sqlite-lossless-table-rebuild`

**Modo:** Standard SDD
**Prioridad:** P0 — Riesgo de pérdida de esquema
**Dependencias:** Changes 04 y 05

### Objetivo

Reemplazar el rebuild actual por una reconstrucción real y sin pérdida de definición.

### Alcance

* Obtener la definición original completa de la tabla.
* Crear una tabla temporal con el esquema objetivo, no mediante `CREATE TABLE AS SELECT`.
* Copiar datos usando una proyección explícita.
* Aplicar cast o backfill únicamente cuando haya una decisión registrada.
* Recrear PK, FK, unique, check, índices y triggers.
* Ejecutar `foreign_key_check`.
* Restaurar el estado original de `PRAGMA foreign_keys`.
* No inventar defaults como `0` o cadena vacía.
* Añadir pruebas con constraints, índices, triggers y rollback.

### Criterio de salida

Una reconstrucción conserva datos y objetos dependientes, o se bloquea antes de generar el script.

---

## Change 08 — `harden-postgresql-native-types-and-ddl`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Changes 04 y 05

### Objetivo

Preservar correctamente tipos y semántica PostgreSQL.

### Alcance

* Usar `pg_catalog` donde `information_schema` pierda información.
* Diferenciar tipos base, domains, enums, arrays y tipos definidos por usuario.
* Diferenciar `serial` basado en secuencia de `IDENTITY`.
* Preservar defaults, columnas generadas y collations.
* Reemplazar el `CAST` universal por una estrategia de conversión explícita.
* Prevalidar cambios a `NOT NULL`.
* Añadir pruebas de integración por versiones soportadas.

### Criterio de salida

La introspección y renderización permiten un round-trip estructural sin degradar tipos nativos.

---

## Change 09 — `harden-mysql-mariadb-column-roundtrip`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Changes 04 y 05

### Objetivo

Evitar que `MODIFY COLUMN` elimine atributos no representados.

### Alcance

* Introspectar `COLUMN_TYPE`, no solamente `DATA_TYPE`.
* Preservar `UNSIGNED`, `ZEROFILL`, `ENUM`, `SET` y precisión temporal.
* Preservar charset, collation, comments, generated expressions y `ON UPDATE`.
* Separar reglas MySQL y MariaDB cuando diverjan.
* Detectar versión del servidor.
* Evitar la desactivación global de FKs salvo cuando sea imprescindible y esté justificada.
* Modelar ejecución parcial, ya que no puede suponerse rollback transaccional completo.

### Criterio de salida

Toda sentencia `MODIFY COLUMN` reproduce la definición completa conocida de la columna.

---

## Change 10 — `align-sqlserver-provider-with-provider-contract`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Change 05

### Objetivo

Llevar el provider SQL Server al mismo contrato que los providers nuevos.

### Alcance

* Implementar capabilities.
* Eliminar importaciones ansiosas de `pyodbc`.
* Mover cualquier extracción legacy restante al provider.
* Introspectar defaults, identities y collations.
* Añadir pruebas de contrato compartidas.
* Mantener golden files del comportamiento T-SQL existente.

### Criterio de salida

SQL Server deja de ser una excepción arquitectónica y funciona mediante el mismo pipeline que los demás motores.

---

# Horizonte 2 — Objetos de esquema avanzados reales

## Change 11 — `complete-advanced-schema-object-contract`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Changes 01 y 05

### Objetivo

Completar el contrato de dominio de objetos avanzados.

### Alcance

* Formalizar PK, FK e índices.
* Añadir Unique Constraints y Check Constraints, actualmente no representados de forma independiente.
* Representar orden de columnas, filtros, expresiones e índices incluidos cuando proceda.
* Definir igualdad nativa y semántica.
* Definir reglas de normalización por provider.
* Extender modelos de discrepancia y reportes.

### Criterio de salida

El dominio puede representar todos los objetos que BDIFF declara comparar, sin campos específicos de un único motor.

---

## Change 12 — `introspect-advanced-objects-sqlserver`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Change 11

Implementar introspección real de PK, FK, unique, check e índices para SQL Server.

---

## Change 13 — `introspect-advanced-objects-postgresql`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Change 11

Implementar introspección mediante `pg_constraint`, `pg_index` y catálogos asociados.

---

## Change 14 — `introspect-advanced-objects-mysql-mariadb`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Change 11

Implementar introspección separando las diferencias reales entre MySQL y MariaDB.

---

## Change 15 — `introspect-advanced-objects-oracle`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Changes 06 y 11

Implementar introspección de constraints e índices Oracle respetando owner, orden de columnas y acciones referenciales soportadas.

---

## Change 16 — `introspect-advanced-objects-sqlite`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Changes 07 y 11

Combinar PRAGMAs y SQL original para recuperar PK, FK, índices, unique y check constraints.

---

# Horizonte 3 — Validación, instalación y cierre

## Change 17 — `add-provider-contract-integration-matrix`

**Modo:** Standard SDD
**Prioridad:** P1
**Dependencias:** Changes 06–16

### Objetivo

Ejecutar una misma suite de comportamiento contra todos los providers.

### Alcance

* Fixtures canónicas compartidas.
* Introspect → snapshot → compare → plan → render.
* Pruebas de round-trip.
* Matriz de versiones soportadas.
* Tests unitarios, integración y golden files.
* Evidencia separada por provider.
* CI con drivers y servicios opcionales.

### Criterio de salida

Un provider no puede declararse estable solamente porque sus mocks devuelvan las filas esperadas.

---

## Change 18 — `make-database-drivers-truly-optional`

**Modo:** Standard SDD
**Prioridad:** P2
**Dependencias:** Changes 02 y 10

### Objetivo

Permitir instalar el core sin drivers de motores no utilizados.

### Alcance

* Retirar `pyodbc` de dependencias core.
* Mantener extras por provider.
* Revisar `run.py` para instalar el extra necesario.
* Añadir diagnóstico de drivers.
* Verificar instalación core más SQLite sin dependencias externas.
* Normalizar mensajes de instalación.

### Criterio de salida

Importar y ejecutar funcionalidades core no requiere `pyodbc`, `psycopg`, `pymysql` ni `oracledb`.

---

## Change 19 — `reconcile-provider-documentation-and-project-metadata`

**Modo:** SDD Lite, condicionado
**Prioridad:** P2
**Dependencias:** Todos los anteriores

### Objetivo

Sincronizar README, descripción del paquete, `openspec/config.yaml`, ejemplos y roadmap con el comportamiento real ya verificado.

### Condición para usar Lite

Puede ejecutarse como Lite únicamente si:

* no modifica comportamiento;
* no introduce decisiones arquitectónicas;
* no cambia compatibilidad;
* se limita a sincronización mecánica de documentación y metadatos.

Si durante la actualización aparecen decisiones sobre soporte, versiones o contratos públicos, deberá escalar a Standard SDD.

---

# Orden de ejecución

```text
01
└── 02
    ├── 03
    └── 04
        └── 05
            ├── 06 Oracle
            ├── 07 SQLite
            ├── 08 PostgreSQL
            ├── 09 MySQL/MariaDB
            └── 10 SQL Server

01 + 05
└── 11 Advanced Object Contract
    ├── 12 SQL Server
    ├── 13 PostgreSQL
    ├── 14 MySQL/MariaDB
    ├── 15 Oracle
    └── 16 SQLite

06–16
└── 17 Integration Matrix
    └── 18 Optional Drivers
        └── 19 Documentation Lite
```

# Política de ejecución OpenSpec

## Changes estándar

Cada change deberá generar:

```text
openspec/changes/{change-name}/
├── proposal.md
├── specs/{capability}/spec.md
├── design.md
├── tasks.md
└── state.yaml
```

Durante ejecución y cierre:

```text
├── apply-progress.md
├── verify-report.md
└── archive-report.md
```

Cuando el alcance esté suficientemente definido, se utilizará `/sdd-ff` para compactar exclusivamente la planificación:

```text
proposal -> specs -> design -> tasks
```

La implementación y verificación no se omiten.

## Changes Lite

```text
openspec/changes/{change-name}/
├── proposal-lite.md
├── tasks.md
└── state.yaml
```

Su contrato deberá incluir:

* Change Class.
* Intent.
* Boundaries.
* Affected Areas.
* Acceptance Checks.
* Risks and Rollback.

# Decisión de clasificación

* **Oracle:** Standard, alto riesgo.
* **SQLite rebuild:** Standard, crítico.
* **Runtime dispatch:** Standard, arquitectónico.
* **Capabilities y DDL planning:** Standard, arquitectónico.
* **Correcciones del motor de comparación:** Standard, aunque tengan pocas líneas.
* **Providers restantes:** Standard.
* **Documentación y ajustes puramente mecánicos:** posibles candidatos a Lite.
