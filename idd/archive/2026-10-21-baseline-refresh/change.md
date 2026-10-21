# baseline-refresh

## Intent and acceptance

Baseline brownfield estilo foundation: la documentación describe un producto antiguo (solo SQL Server, sin escritura en BD, TUI de gestión de conexiones) y hay 4 roadmaps contradictorios

Acceptance: brief, alcance, glosario y baseline técnico reflejan el producto real (6 motores, Windows como plataforma principal, CLI+TUI, scripts T-SQL); existen knowledge-map.yaml y component-map.yaml válidos con divergencias citadas; ADR 0006 documenta la mutación de metadatos con confirmación; un único docs/roadmap.md con backlog priorizado sustituye a los roadmaps antiguos; README, decisions/README y openspec/config.yaml son coherentes

## Plan

1. Reescribir brief, alcance funcional y glosario con el producto real
   (v1.2.5), conservando un resumen de lo que cambió respecto a 2026-07.
2. Reestructurar el baseline técnico con el esqueleto de foundation y un
   historial de las decisiones originales.
3. Crear `knowledge-map.yaml` (perfil internal-tool, sin rondas abiertas) y
   `component-map.yaml` (9 componentes, 15 divergencias con evidencia).
4. ADR 0006 (amplía la 0005) e índice de ADR.
5. Roadmap único con estado verificado, la tanda de endurecimiento y el
   backlog; borrar los cuatro documentos antiguos.
6. README orientado a Windows y multi-motor; `openspec/config.yaml`
   coherente (y YAML válido: el bloque `rules.apply` no parseaba).

## Decisions

### Decision: Mapas en JSON

Kind: dc

`knowledge-map.yaml` y `component-map.yaml` se escriben como JSON (YAML 1.2
válido) porque el motor de `ospec foundation` solo lee JSON.

### Decision: Specs openspec sin reescribir

Kind: dc

Por decisión del usuario, `openspec/specs/` no se reescribe en esta tanda:
cada desfase queda como divergencia `spec-*` en el component-map y como
tarea P1 del roadmap.

### Decision: README y config de ejemplo como contrato público

Kind: dc

El detector de `ospec` marcó `public-contract` por un falso positivo (un
nombre de tabla temporal T-SQL entre comillas invertidas leído como
selector CSS) y una señal del diff no se puede retirar. Con aprobación del
usuario, `idd/config.yaml` declara `README.md` y `config.example.yaml` como
documentos de contrato, y `tests/unit/test_readme_cli_contract.py` comprueba
que la tabla de opciones del README coincide con `build_arg_parser()`.

## Evidence

<!-- ospec:evidence:start -->
- ev-1: check-run for checks-pass (2026-10-21T10:26:02.656Z)
- ev-2: adr-impact-declaration for adr-impact-declaration (2026-10-21T10:26:02.656Z)
- ev-3: check-run for checks-pass (2026-10-21T10:26:55.510Z)
- ev-4: check-run for checks-pass (2026-10-21T10:29:40.754Z)
- ev-5: contract-spec-and-test for contract-spec-and-test (2026-10-21T10:29:40.754Z)
- ev-6: living-doc-current for living-doc (2026-10-21T10:29:45.348Z)
<!-- ospec:evidence:end -->
