# Feature: banco-bci — segunda comunidad (Edificio Bustos 2166, BCI)

## Objetivo
Incorporar la cartola oficial PDF de BCI y validar el sistema con la comunidad Edificio
Bustos 2166 (cuenta BCI 29845203), igual que se hizo con Cinema/Santander.

## Problema / por qué
Fase 5 del plan: más bancos y comunidades antes de producción. Varias comunidades del cliente
reciben esta misma cartola BCI, así que un parser cubre a todas.

## Evidencia de exploración (2026-10-06)
- Archivos en `../bustos/` (fuera del repo, confidenciales): ingresos, egresos, conciliación
  (hojas hasta JULIO'26) y cartolas BCI junio, julio y agosto 2026.
- Planillas: los parsers actuales (`libros.py`, `conciliacion_cliente.py`) las leen sin cambios;
  totales de ingresos/egresos may–jul 2026 = los de la conciliación del cliente.
- Cartola BCI: PDF con texto, 2 páginas, columnas FECHA (dd-mm-aaaa) · SUCURSAL · DESCRIPCIÓN ·
  Nº DOCUMENTO · monto · SALDO DIARIO (en cada fila). Resumen "Saldo Anterior − Cargos + Abonos
  = Saldo Final". Las tres cartolas encadenan sin traslape.

## Alcance autorizado
Parser BCI + tests, simulación jun–jul contra el cliente (agosto sin hoja del cliente),
correcciones que la simulación revele, carga de Bustos en el sistema, documentación.

## Restricciones
- Datos del cliente nunca entran al repo. Artefactos en español (proyecto en español).
- Montos `int`; columnas por posición x de encabezados; sentido del monto verificable con el
  saldo diario.
- Commits solo con aprobación del usuario (AGENTS.md §9).

## Checklist
- [x] T1 Parser `BciPDFOficial` + tests con jun/jul/ago (saldos, conteos, sentidos). Ruta: delegada (2 archivos no triviales: parser + tests).
  - Evidencia: RED (ModuleNotFoundError) → GREEN; `tests/test_motor/test_bci.py` 5 passed; ruff OK.
  - Hallazgo: el cliente reemplazó marzo/abril de Cinema por cartolas oficiales Santander (Nº 304/305);
    se leen sin advertencias y calzan con las plantillas transcritas → test actualizado (solo enero
    queda ilegible) + test de comparación oficial vs plantilla.
  - Bloqueado: tests de API (22 errores) porque el puerto 5432 lo ocupa el Postgres de otro
    proyecto (`codigo-secreto`); el contenedor `db` de este proyecto no está arriba.
  - Resuelto (usuario aprobó): Postgres del proyecto pasa al puerto 5433 (.env, .env.example,
    settings, docker-compose, AGENTS/README). Suite completa: 72 passed; ruff OK.
- [x] T1b (pedido del usuario) Puertos propios para convivir con codigo_secreto: Django 8010
  (`apps/desarrollo` sobreescribe el puerto por defecto de runserver), Vite 5180 con strictPort,
  CSRF_TRUSTED_ORIGINS=5180, docker-compose y Dockerfile. Ruta: inline (config mecánica).
  - Evidencia: smoke test Django :8010 → 204, Vite :5180 → 200, proxy → 204; backend 72 passed,
    frontend 10 passed, build OK.
- [x] T2 Simulación jun–jul vs hojas del cliente (apertura MAYO´26) + agosto; corregir lo que aparezca. Ruta: inline (comandos y análisis).
  - Evidencia: `motor.simular` jun y jul IGUAL al cliente, diferencia $0 (3 y 5 cruces por revisar);
    agosto (sin hoja del cliente) diferencia $0, 1 por revisar, no contabilizado −$381.668.
  - Hallazgo para el cliente: PAC ENEL agosto registrado como egreso #2444 por $397.314, el banco
    cobró $381.668 (P.A.C. CHILECTRA 20/08) → diferencia $15.646 a revisar en su planilla.
  - Sin cambios de código necesarios.
- [x] T3 Cargar Bustos en el sistema (comando de demo generalizado) y probar flujo/informes. Ruta: inline (1 archivo nuevo + ajuste puntual).
  - `demo_cinema` → `cargar_piloto cinema|bustos`; Cinema usa ahora las cartolas oficiales de mar/abr
    (simulación ene–may sigue IGUAL al cliente).
  - Hallazgo: planilla de conciliación de Bustos pesa 21,6 MB → límite por tipo: 50 MB saldo inicial,
    10 MB mensuales (+ test).
  - Evidencia: `cargar_piloto bustos` → jun/jul $0 cerrados, ago $0 abierto (1 por revisar);
    PDF/Excel de agosto generados (cabecera BCI · Cartola Nº 8).
- [x] T4 AGENTS.md (formatos BCI, pilotos, puertos, comandos, hallazgo ENEL) y README. Ruta: inline.
  - Evidencia final: backend 73 passed, ruff OK; frontend 10 passed + build OK (tras cambio de puertos).

## Criterios de aceptación
- Las 3 cartolas BCI se leen sin advertencias (saldo inicial + movimientos = saldo final).
- Junio y julio 2026 iguales a las hojas del cliente y con diferencia $0 (o diferencia explicada).
- Suite completa en verde (`uv run pytest`, ruff).

## Verificaciones
`uv run pytest`, `uv run ruff check .`, `uv run python -m motor.simular ...` (Bustos).

## Progreso
- Rama `feat/banco-bci` creada desde `8e8044e`.
- Espejo Engram `odd/banco-bci/tasks`: PENDIENTE (Engram no disponible en esta sesión; resincronizar).

## Entrega
- Estrategia: `ask-on-risk` → el usuario eligió **Stacked PRs a `main`** (2026-10-06).
- El commit único original (958 líneas) se rehízo como 3 unidades de trabajo apiladas:

```
main
 └─ chore/puertos-dev     PR 1  02d1165  chore(dev): puertos propios          ~76 líneas
     └─ feat/cartola-bci  PR 2  6fadab7  feat(cartolas): lector BCI           467 líneas ⚠️ size:exception
         └─ feat/pilotos-bustos PR 3     feat(pilotos): cargar_piloto + Bustos ~418 líneas ⚠️ size:exception
```

- PR 2 excede por ~67 líneas: lector (313) + sus tests (97) + cambio de test por los datos nuevos;
  no hay corte cohesivo menor (el lector sin sus tests no es revisable).
- PR 3 excede por ~18 líneas: incluye la eliminación de `demo_cinema` (109) y este documento (74).
- Revisión RDD: cambio de `.gitignore` aprobado (lineage review-3e8b325b700ae2c2).
- Sin remoto configurado: las ramas quedan listas; las PRs se abren cuando exista el repositorio remoto.

## Próximo paso
Crear el remoto y abrir las 3 PRs en orden (1 → 2 → 3), cada una apuntando a la rama anterior.
