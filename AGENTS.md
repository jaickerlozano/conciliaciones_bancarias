# AGENTS.md — Conciliaciones Bancarias (Gaudi Administraciones)

Reglas del proyecto para cualquier agente de IA (Claude Code, Codex, Cursor…) y para humanos.
`CLAUDE.md` solo importa este archivo: **editar aquí**.

## 1. Qué es

App web para que Gaudi Administraciones (administra comunidades/edificios en Chile) genere la
**conciliación bancaria mensual** de cada comunidad a partir de:

1. Planilla de **ingresos** (Excel, acumulada, un bloque por mes).
2. Planilla de **egresos** (Excel, acumulada, un bloque por mes).
3. **Cartola** bancaria del mes (PDF oficial o Excel/CSV del banco).

Salida: conciliación en pantalla + descarga en **PDF** y en **Excel** (botones separados).
Usuarios: ~3 internos de Gaudi. Muchas comunidades, cada una con su banco (Santander, BCI,
Banco de Chile, …). Piloto: **Comunidad Edificio CINEMA** (Santander, cta 0-000-03-81745-8).

Por ahora las planillas Excel del cliente siguen siendo la fuente de datos. Más adelante
ingresos/egresos se registrarán directamente en el sistema.

## 2. Fases

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Motor puro Python: parsers + cruce + cálculo. Criterio: reproducir mayo 2026 con diferencia 0 | ✅ Hecho |
| 2 | Backend Django + DRF + PostgreSQL: modelos, carga de archivos, API, login | Pendiente |
| 3 | Frontend React: carga mensual, mesa de trabajo de cruces, vista de conciliación | Pendiente |
| 4 | Salidas: PDF (WeasyPrint) y Excel (openpyxl) | Pendiente |
| 5 | Más bancos y comunidades (pruebas antes de producción) | Pendiente |

## 3. Stack

| Capa | Tecnología |
|---|---|
| Motor | Python 3.12, openpyxl (modo `read_only`), pdfplumber. **Sin Django.** |
| Backend | Django 5 + Django REST Framework, auth por sesión (cookie + CSRF), sin JWT |
| BD | PostgreSQL 16 (Docker) |
| Frontend | React + TypeScript + Vite, Tailwind CSS, TanStack Query, pnpm |
| PDF salida | WeasyPrint (plantilla HTML/CSS) — requiere GTK/Pango: usar Docker en Windows |
| Excel salida | openpyxl |
| Tests | pytest (+ pytest-django en fase 2), Vitest en frontend |
| Lint | ruff (Python, línea 100), ESLint + `tsc` (frontend) |
| Paquetes | `uv` (Python), `pnpm` (JS) |
| Infra | Docker Compose: `db`, `backend`, `frontend` |

No usar: camelot (requiere Ghostscript), pandas en el motor (innecesario), Celery (los archivos
son pequeños; procesamiento síncrono).

## 4. Estructura

```
conciliaciones_bancarias/
├── AGENTS.md / CLAUDE.md / README.md
├── .claude/skills/        # skills de Claude Code (ej. agregar-banco)
├── backend/
│   ├── pyproject.toml     # uv; Python 3.12
│   ├── motor/             # FASE 1 — lógica pura, sin Django, sin I/O de red
│   │   ├── dominio.py         # dataclasses: PartidaLibro, MovimientoBancario, Cartola, ...
│   │   ├── texto.py           # normalización, montos CLP, meses
│   │   ├── cruce.py           # algoritmo de cruce libro <-> banco
│   │   ├── conciliacion.py    # cálculo de la conciliación
│   │   ├── cli.py             # `python -m motor.cli` para probar sin servidor
│   │   └── parsers/
│   │       ├── libros.py               # planillas de ingresos/egresos
│   │       ├── conciliacion_cliente.py # hoja de conciliación manual (estado inicial)
│   │       └── cartolas/               # un módulo por banco/formato + base.py (registro)
│   ├── config/            # FASE 2 — proyecto Django (settings, urls)
│   ├── apps/              # FASE 2 — apps Django (comunidades, conciliaciones, ...)
│   └── tests/
│       ├── test_motor/        # tests del motor
│       └── conftest.py        # fixture `datos` (archivos reales, se omite si no están)
└── frontend/              # FASE 3
```

Las apps Django **usan** el motor; el motor **nunca** importa Django.

## 5. Reglas de negocio de la conciliación (fuente de verdad)

```
Saldo según registro     = saldo según registro del mes anterior + ingresos del mes − egresos del mes (+ redondeo)
Saldo según conciliación = registro
                         + cheques girados no cobrados            (egresos del libro sin cargo en el banco)
                         − depósitos contabilizados no en banco    (ingresos del libro sin abono en el banco)
                         + movimientos no contabilizados          (del banco sin partida en el libro; abono +, cargo −)
Diferencia               = saldo final de la cartola − saldo según conciliación   → debe ser 0
```

- **El período de una partida lo define su bloque** en la planilla (filas `CIERRE MES <MES> <AÑO>`),
  **no su fecha**. Hay ingresos fechados en junio dentro del bloque de mayo. Las filas después del
  último cierre son el período abierto (siguiente al último cierre).
- **Arrastre:** los pendientes (cheques, depósitos y movimientos no contabilizados) pasan al mes
  siguiente y se vuelven a cruzar contra la nueva cartola. Ej.: el ingreso 1210 de mayo liquidó
  un abono no contabilizado de enero.
- **Cruce, en capas:**
  1. Egreso con nº de cheque ↔ cargo cuyo `N° DCTO` es ese cheque (exacto). Si el monto difiere, se cruza con nota.
  2. Egresos sin cheque (PAC, transferencias) ↔ cargos restantes, por monto y fecha.
  3. Ingresos ↔ abonos, por monto y fecha.
  En 2 y 3, por cada monto se maximiza el nº de pares y luego se minimiza la suma de días
  (ventana 60 días). Es `SUGERIDO` (requiere confirmación del usuario) si sobran partidas o movimientos de ese monto
  o si la diferencia supera 7 días; si no, es automático.
- **Continuidad:** el saldo inicial de la cartola debe coincidir con el saldo final de la anterior.
  Si no, advertir (falta una cartola o se traslapan; ver febrero 2026). En fase 2: deduplicar
  movimientos repetidos entre cartolas traslapadas.
- **Validación de cartola:** saldo inicial + Σ movimientos = saldo final; si no, advertir.
- Comprobantes con monto 0 ("NULO") se ignoran. Concepto `INGRESO`/`INGRESOS`, `EGRESO`/`EGRESOS`.
- Una conciliación aprobada queda **cerrada** (inmutable, con usuario y fecha); su estado de cierre
  es la apertura del mes siguiente.
- Al incorporar una comunidad, el estado inicial se importa desde la última hoja de su planilla
  "CONCILIACIÓN MENSUAL" (`parsers/conciliacion_cliente.py`).

## 6. Convenciones de código

- **Montos: `int` en pesos chilenos.** Nunca `float`. Los montos con decimales (cuotas en UF) se
  redondean al importar (ROUND_HALF_UP) y se genera una advertencia. Mostrar con `fmt_clp()` → `$1.379.448`.
- **Idioma:** términos del dominio en español (`cartola`, `egreso`, `conciliar`, `PartidaLibro`);
  términos técnicos genéricos pueden ir en inglés (`parser`, `base`). Comentarios, docstrings,
  mensajes al usuario y commits en **español**.
- Los mensajes de error/advertencia del motor se muestran **tal cual al usuario final**: deben ser
  claros, en español y decir qué hacer.
- Los parsers **no fallan en silencio**: si algo no se puede leer, `ErrorCartola` /
  `ErrorFormatoPlanilla` con mensaje claro, o una advertencia. Nunca devolver `None` crudo.
- Excel del cliente: siempre `openpyxl.load_workbook(..., read_only=True, data_only=True)` y
  `iter_rows(max_col=...)` (hay hojas con 16.000+ columnas vacías).
- Columnas de planillas: ubicarlas por **encabezado** (con alias), no por posición fija.
- Cartolas PDF: ubicar columnas por **posición x de los encabezados**, no por regex sobre texto plano.
- Cada banco/formato de cartola = una subclase de `ParserCartola` registrada con `@registrar`
  (ver skill `agregar-banco`).
- Tipado completo; `from __future__ import annotations`; dataclasses para el dominio.
- **Finales de línea LF y UTF-8** en todo el repo (`.gitattributes` + `.editorconfig`). Al escribir
  archivos desde Python usar `newline="
"` (en Windows `write_text` convierte a CRLF).

## 7. Datos del cliente (confidencial)

- Los archivos reales viven **fuera del repo**, en `../ingresos_egresos_cartolas/` (o
  `$CONCILIACION_DATOS_DIR`). Contienen nombres, RUTs y montos reales: **nunca** copiarlos al
  repo, a fixtures versionadas, a issues ni a servicios externos. `.gitignore` bloquea `*.xlsx`,
  `*.xlsm`, `*.pdf`.
- Fixtures sintéticas para tests: construirlas en código (ver `tests/test_motor/test_cruce.py`).

### Formatos de cartola conocidos (Santander)

| Archivo | Formato | Estado |
|---|---|---|
| feb, may 2026 | Cartola oficial PDF (texto) | ✅ `SantanderPDFOficial` |
| mar 2026 | Listado "movimientos" del portal (PDF) | ❌ no soportado aún |
| abr 2026 | PDF con fuente codificada (texto ilegible `(cid:..)`) | ❌ no procesable |
| ene 2026 | PDF escaneado (imagen) | ❌ no procesable (requeriría OCR) |

Se pidió al cliente usar siempre **Excel/CSV del portal** o la **cartola oficial PDF**.
En las transferencias, la descripción trae el RUT del pagador (ej. `0106472769`): servirá para
asociar RUT ↔ depto y automatizar el cruce de ingresos.

## 8. Comandos

```bash
# Backend / motor (desde backend/)
uv sync                                   # instalar dependencias
uv run pytest                             # todos los tests
uv run pytest -m "not datos_reales"       # solo tests sin archivos del cliente
uv run ruff check . && uv run ruff format --check .
uv run python -m motor.cli --periodo 2026-05 \
  --ingresos "../../ingresos_egresos_cartolas/listado ingresos CINEMA2.xlsx" \
  --egresos "../../ingresos_egresos_cartolas/emitir egresos CINEMA.xlsm" \
  --cartola ../../ingresos_egresos_cartolas/cartola_mayo_2026.pdf \
  --apertura "../../ingresos_egresos_cartolas/CONCILIACIÓN  MENSUAL CINEMA.xlsm" \
  --hoja-apertura "ABRIL´26"

# Fase 2+ (Django)
uv run python manage.py makemigrations && uv run python manage.py migrate
uv run pytest -k "upload"

# Fase 3+ (frontend, desde frontend/)
pnpm install
pnpm run lint && pnpm run build           # build = prueba de fuego del tipado
pnpm test
```

En Windows la consola necesita `PYTHONIOENCODING=utf-8` para imprimir tildes desde el CLI.

## 9. Guardrails

- **Cartola ilegible** (escaneada, fuente codificada): el parser aborta con `ErrorCartola` y un
  mensaje que pide el formato correcto. Nunca devolver movimientos vacíos como si fuera válida.
- **Archivos grandes:** rechazar planillas de más de 10.000 filas útiles en un request síncrono.
- **Uploads:** validar extensión y tamaño (máx. 10 MB); guardar el archivo original asociado a la
  conciliación para auditoría.
- **Conciliación cerrada = inmutable.** Reabrir requiere acción explícita y queda registrada.
- **Antes de dar por terminado un cambio en el motor:** `uv run pytest` en verde, incluido
  `test_reproduce_conciliacion_mayo_2026` si los datos están disponibles.
- **Frontend:** si `pnpm run build` no compila, el cambio no está terminado.
- No hacer commits ni push sin que el usuario lo pida.

## 10. Decisiones abiertas

- Deduplicación de movimientos entre cartolas traslapadas (fase 2, por fecha + doc + monto + descripción).
- Pedir al cliente una columna "Nº operación" en la planilla de ingresos → cruce exacto de ingresos.
- Tabla RUT ↔ depto por comunidad (aprendida de cruces confirmados).
- Aviso de cheques caducados (> 60 días sin cobrar).
- Errores detectados en planillas del cliente para informarle: cierre 2021-02 y 2024-04 de
  ingresos y 2025-02 de egresos no cuadran con la suma de sus partidas; comprobante 1261 con
  fecha 18/08/2226; comprobantes 23–26 de ingresos y 1217 de egresos duplicados.
