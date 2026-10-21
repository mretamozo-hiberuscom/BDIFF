# Architecture Decision Records

Decisiones estructurales de BDIFF. Una ADR aceptada no se reescribe: se
amplía o sustituye con otra. Las divergencias entre una ADR y el código
están en `docs/architecture/component-map.yaml`.

| Id | Decisión | Estado |
|---|---|---|
| [0001](0001-hexagonal-architecture-and-dependency-rules.md) | Arquitectura hexagonal ligera y regla de dependencias | accepted |
| [0002](0002-internal-provider-registry.md) | Registro interno de proveedores con carga diferida | accepted |
| [0003](0003-canonical-type-system-and-comparison-modes.md) | Sistema de tipos canónico y modos `native-strict` / `semantic` | accepted |
| [0004](0004-configuration-v2-and-backwards-compatibility.md) | Configuración v2 (`profiles:`) y retrocompatibilidad | accepted |
| [0005](0005-decoupled-write-only-script-generation.md) | Generación de scripts sin ejecución automática | accepted, ampliada por 0006 |
| [0006](0006-mantenimiento-de-metadatos-con-confirmacion.md) | Mantenimiento de metadatos con confirmación explícita | accepted |

Las decisiones tecnológicas (drivers, librerías) viven en el registro
tecnológico de `docs/architecture/technical-baseline.md`; las decisiones de
desarrollo de un cambio, en `idd/<cambio>/change.md`.

## Plantilla para nuevas ADR

`NNNN-<titulo-kebab>.md`, numeradas en orden:

```markdown
# NNNN. <Título>

- Status: proposed | accepted | superseded by NNNN
- Date: YYYY-MM-DD
- Evidence: path:line

## Context and drivers
## Options considered
## Decision
## Consequences
## Fitness function
## Review trigger
```
