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
Usuarios: ~3 internos de Gaudi.

**Interfaz:** el personal usa **solo el panel React** (fase 3): CRUD y filtro de comunidades,
cuentas y todo el flujo mensual, en español y guiado paso a paso. El **admin de Django es solo
para el superusuario** (desarrollador): gestión de usuarios y soporte. El personal se crea como
usuario normal (`is_staff=False`), sin acceso a `/admin`. Muchas comunidades, cada una con su banco (Santander, BCI,
Banco de Chile, …). Piloto: **Comunidad Edificio CINEMA** (Santander, cta 0-000-03-81745-8).

Por ahora las planillas Excel del cliente siguen siendo la fuente de datos. Más adelante
ingresos/egresos se registrarán directamente en el sistema.

## 2. Fases

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Motor puro Python: parsers + cruce + cálculo. Criterio: reproducir mayo 2026 con diferencia 0 | ✅ Hecho |
| 2 | Backend Django + DRF + PostgreSQL: modelos, carga de archivos, API, login | ✅ Hecho |
| 2b | Simulación ene→may 2026 vs. conciliaciones del cliente: los 5 meses iguales, dif. $0 | ✅ Hecho |
| 3 | Frontend React: carga mensual, mesa de trabajo de cruces, vista de conciliación | ✅ Hecho |
| 4 | Salidas: PDF (ReportLab) y Excel (openpyxl, con fórmulas) | ✅ Hecho |
| 5 | Más bancos y comunidades (pruebas antes de producción) | Pendiente |

## 3. Stack

| Capa | Tecnología |
|---|---|
| Motor | Python 3.12, openpyxl (modo `read_only`), pdfplumber. **Sin Django.** |
| Backend | Django 5 + Django REST Framework, auth por sesión (cookie + CSRF), sin JWT |
| BD | PostgreSQL 16 (Docker) |
| Frontend | React 19 + TypeScript + Vite, Tailwind CSS 4, TanStack Query, React Router, lucide-react, sonner, pnpm |
| PDF salida | ReportLab (Python puro: funciona igual en Windows y Docker, sin GTK) |
| Excel salida | openpyxl (fórmulas vivas en la hoja principal) |
| Tests | pytest + pytest-django (BD de tests en el Postgres de Docker), Vitest en frontend |
| Lint | ruff (Python, línea 100), oxlint + `tsc` estricto (frontend) |
| Paquetes | `uv` (Python), `pnpm` (JS) |
| Infra | Docker Compose: `db`, `backend`, `frontend` |

No usar: WeasyPrint (en Windows exige GTK/Pango; se reemplazó por ReportLab), camelot (requiere Ghostscript), pandas en el motor (innecesario), Celery (los archivos
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
│   │   ├── simular.py         # `python -m motor.simular`: encadena meses y compara con el cliente
│   │   └── parsers/
│   │       ├── libros.py               # planillas de ingresos/egresos
│   │       ├── conciliacion_cliente.py # hoja de conciliación manual (estado inicial)
│   │       └── cartolas/               # un módulo por banco/formato + base.py (registro)
│   │           └── plantilla.py            # plantilla estándar Excel (respaldo universal)
│   ├── config/            # proyecto Django: settings (vía .env), urls, excepciones -> 400
│   ├── apps/
│   │   ├── autenticacion/     # login/logout/yo/csrf por sesión
│   │   ├── comunidades/       # Comunidad, CuentaBancaria (+ importar apertura)
│   │   └── conciliaciones/
│   │       ├── models.py      # Conciliacion, Partida, Movimiento, Cruce, ArchivoCargado, Evento
│   │       ├── servicios.py   # TODA la lógica de negocio (casos de uso)
│   │       ├── views.py       # solo HTTP: valida entrada y llama a servicios
│   │       ├── informes/      # datos.py (estructura común) → pdf.py y excel.py
│   │       └── management/commands/demo_cinema.py
│   ├── Dockerfile
│   └── tests/
│       ├── test_motor/        # tests del motor (sin BD)
│       ├── test_api/          # tests de la API (requieren Postgres)
│       └── conftest.py        # fixture `datos` (archivos reales, se omite si no están)
├── docker-compose.yml     # db (Postgres 16) + backend
├── .env.example           # copiar a .env
└── frontend/
    ├── vite.config.ts     # proxy /api y /admin -> Django (mismo origen: cookie + CSRF sin CORS)
    └── src/
        ├── api/           # cliente.ts (fetch + CSRF + errores), tipos.ts, consultas.ts (hooks)
        ├── sesion/        # login por sesión, RequiereSesion
        ├── lib/formato.ts # $1.379.448, dd/mm/aaaa, "Mayo 2026"
        ├── componentes/   # Marco (barra, migas) y ui/ (Boton, Campos, Modal, Insignia, ...)
        └── paginas/       # Ingresar, Comunidades, Comunidad, SaldoInicial,
                           # conciliacion/ (Pasos, Archivos, Resumen, Revision, CruceManual)
```

### Pantallas (panel del personal)

1. **Comunidades:** buscador + filtro activas/inactivas/todas (en la URL), alta/edición.
2. **Comunidad:** cuentas; por cuenta, tabla de meses (estado, saldo banco, diferencia) y botón
   "Iniciar <mes siguiente>" (deshabilitado con motivo visible si el anterior no está cerrado).
   Sin meses: "Configurar saldo inicial" (manual con cuadre en vivo, o importar hoja de planilla).
3. **Conciliación:** pasos Archivos → Revisión → Cierre; carga por arrastre; resumen con la
   estructura de la planilla del cliente y la diferencia destacada; pestañas Por revisar
   (confirmar / "No corresponde" / confirmar todos), cheques, depósitos, no contabilizados
   (con "Cruzar…" solo si hay contraparte del mismo monto), todos los cruces, advertencias e
   historial. Acciones: cerrar (solo con diferencia $0 y nada por revisar), reabrir con motivo,
   eliminar.

### Informes (PDF y Excel)

- Ambos salen de `informes/datos.py::armar_informe` (una sola fuente: nunca difieren).
- Contenido: cabecera (comunidad, banco, cuenta, cartola y período, estado), cálculo con la
  estructura de la planilla del cliente y la diferencia destacada, cheques no cobrados, depósitos
  no registrados, movimientos no contabilizados (con totales), firmas Preparado/Revisado por.
- PDF: anexo con todos los cruces, pie "Página X de Y", marca de agua BORRADOR si no está cerrada.
- Excel: hoja Conciliación con **fórmulas vivas** (saldo según registro, totales =SUM, conciliación
  y diferencia con formato condicional verde/rojo) + hojas Cruces y Cartola (estado de cada
  movimiento) con filtros. Configurado para imprimir en A4.
- Nombre de archivo: `Conciliacion_<Comunidad>_<AAAA-MM>.pdf|xlsx`.

Convenciones de UI: textos en español de Chile, montos con `pesos()` y clase `monto`
(tabular-nums), colores de estado fijos (ver `index.css`), toda acción con resultado visible
(toast abajo a la derecha) y confirmación en las destructivas.

Las apps Django **usan** el motor; el motor **nunca** importa Django.
Las vistas **no** contienen reglas de negocio: todo pasa por `apps/conciliaciones/servicios.py`
(lanza `ErrorConciliacion`, que `config/excepciones.py` convierte en 400 `{"detail": "..."}`).

### Modelo de datos

- `Conciliacion` (una por cuenta y mes; estados `importada` → `borrador` → `procesada` → `cerrada`).
  Guarda saldo anterior, totales del mes, saldo banco y advertencias.
- `Partida` (libro) y `Movimiento` (banco) se guardan **todos**; lo que no tiene `Cruce` es pendiente.
  `origen`: `periodo` / `arrastre` (pendiente de meses anteriores) / `repetido` (movimiento ya
  incluido en la cartola anterior, descartado).
- La apertura de un mes = pendientes de la conciliación anterior (`servicios.apertura_desde`).
  El primer mes de una cuenta se importa desde la planilla del cliente (estado `importada`).
- `ArchivoCargado`: archivo original + sha256 (auditoría). `Evento`: bitácora de quién hizo qué.
- Resumen (saldos, diferencia, cruces por revisar) se calcula con `servicios.calcular_resumen`.

### API (`/api/…`, sesión + CSRF; todo requiere login salvo `auth/csrf` y `auth/login`)

| Método | Ruta | Uso |
|---|---|---|
| GET | `auth/csrf/` | Setea cookie `csrftoken` (enviarla en `X-CSRFToken`) |
| POST | `auth/login/` `{usuario, clave}` · `auth/logout/` · GET `auth/yo/` | Sesión |
| CRUD | `comunidades/?q=texto&activa=true`, `cuentas/?comunidad=ID` | Maestros (con búsqueda) |
| POST | `cuentas/hojas/` (multipart `archivo`) | Lista hojas de una planilla de conciliación |
| POST | `cuentas/ID/apertura/` (multipart `archivo, hoja, periodo`) | Importa saldo inicial |
| POST | `cuentas/ID/apertura-manual/` `{periodo, saldo_registro, saldo_banco, cheques_pendientes[], depositos_pendientes[], movimientos_no_contabilizados[]}` | Saldo inicial manual (movimientos: abono +, cargo −) |
| GET/POST | `conciliaciones/?cuenta=ID` · `{cuenta, periodo:"AAAA-MM"}` | Listar / crear |
| GET/DELETE | `conciliaciones/ID/` | Detalle completo / eliminar |
| POST | `conciliaciones/ID/archivos/` (multipart `tipo, archivo`) | `ingresos`, `egresos`, `cartola` |
| POST | `conciliaciones/ID/procesar/` | Corre el motor y guarda resultados |
| POST | `conciliaciones/ID/cruces/` `{partida, movimiento}` | Cruce manual |
| POST/DELETE | `conciliaciones/ID/cruces/CID/confirmar/` · `conciliaciones/ID/cruces/CID/` | Confirmar / deshacer |
| POST | `conciliaciones/ID/redondeo/` `{monto}` | Ajuste por redondeo (±$100) |
| POST | `conciliaciones/ID/cerrar/` · `conciliaciones/ID/reabrir/` `{motivo}` | Cierre |
| GET | `conciliaciones/ID/pdf/` · `conciliaciones/ID/excel/` | Informe descargable (no disponible en borrador) |
| GET | `bancos/` · `plantilla-cartola/` | Lista de bancos · plantilla estándar vacía |

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
     Si la cartola trunca el nº (ej. `87109` por `1587109`), se acepta la terminación de ≥ 5 dígitos solo con monto idéntico.
  2. Egresos sin cheque (PAC, transferencias) ↔ cargos restantes, por monto y fecha.
  3. Ingresos ↔ abonos, por monto y fecha.
  En 2 y 3, por cada monto se maximiza el nº de pares y luego se minimiza la suma de días
  (ventana 60 días). Es `SUGERIDO` (requiere confirmación del usuario) si sobran partidas o movimientos de ese monto
  o si la diferencia supera 7 días; si no, es automático.
- **Continuidad:** el saldo inicial de la cartola debe coincidir con el saldo final de la anterior.
- **Cartolas traslapadas** (febrero 2026 empieza el 30/01 y repite movimientos de enero): solo si
  la cartola NO continúa desde el saldo anterior, se descartan los movimientos que ya venían en la
  cartola anterior. Mismo movimiento = mismo monto y sentido, mismo nº de documento si ambos lo
  traen, y fecha a ±5 días (los formatos difieren en descripción y en fecha operación/contable).
  Si aun así no calza el saldo, se advierte.
- **Redondeo:** ajuste manual de hasta ±$100 para absorber decimales (cuotas en UF). El cliente lo
  usa (ej. +$1 en enero 2026). Queda en la bitácora.
- **Validación de cartola:** saldo inicial + Σ movimientos = saldo final; si no, advertir.
- Comprobantes con monto 0 ("NULO") se ignoran. Concepto `INGRESO`/`INGRESOS`, `EGRESO`/`EGRESOS`.
- Una conciliación aprobada queda **cerrada** (inmutable, con usuario y fecha); su estado de cierre
  es la apertura del mes siguiente.
- **Solo se cierra** si la diferencia es 0 y no quedan cruces por revisar (sugeridos sin confirmar).
- Para crear el mes N, el mes N−1 debe estar cerrado (o importado). Para reabrir o eliminar un
  mes, no debe existir el mes siguiente. Reabrir exige motivo (queda en la bitácora).
- Cruce manual: egreso ↔ cargo o ingreso ↔ abono, mismo monto, ambos libres.
- Si se sube un archivo nuevo a una conciliación procesada, sus resultados se borran (hay que
  volver a procesar).
- La cartola debe ser del banco y nº de cuenta de la `CuentaBancaria` que se concilia.
- **Saldo inicial** de una cuenta (una sola vez, antes del primer mes): (a) **manual** —
  saldo según registro, saldo banco y la lista de pendientes; debe cuadrar exacto o no se guarda
  (opción recomendada para cuentas nuevas), o (b) **importado** desde la última hoja de la planilla
  "CONCILIACIÓN MENSUAL" del cliente (`parsers/conciliacion_cliente.py`).

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
| mar 2026 | "Cartola Histórica" del portal (PDF sin saldos ni signo) | ❌ no soportado → plantilla estándar |
| abr 2026 | "Cartola Histórica" con fuente sin mapa de caracteres (texto `(cid:..)`) | ❌ → plantilla estándar |
| ene 2026 | "Consulta de movimientos" impresa como trazos vectoriales (sin texto) | ❌ → plantilla estándar |
| cualquiera | **Plantilla estándar Excel** (`CARTOLA ESTÁNDAR`) | ✅ `PlantillaEstandar` |

Enero, marzo y abril se convirtieron una vez a plantilla estándar (verificadas fila a fila contra
los saldos del banco) y están en `../ingresos_egresos_cartolas/cartolas_estandar/`.
Se pidió al cliente usar siempre **Excel/CSV del portal** o la **cartola oficial PDF**. Para
bancos/formatos no soportados, la **plantilla estándar** es el respaldo (el usuario copia ahí los
movimientos); `escribir_plantilla()` genera la plantilla vacía para descargar.
En las transferencias, la descripción trae el RUT del pagador (ej. `0106472769`): servirá para
asociar RUT ↔ depto y automatizar el cruce de ingresos.

## 8. Comandos

```bash
# Backend / motor (desde backend/)
uv sync                                   # instalar dependencias
uv run pytest                             # todos los tests (test_api requiere Postgres arriba)
uv run pytest tests/test_motor            # solo el motor (sin BD)
uv run pytest -m "not datos_reales"       # sin archivos del cliente
uv run ruff check . && uv run ruff format --check .
uv run python -m motor.cli --periodo 2026-05 \
  --ingresos "../../ingresos_egresos_cartolas/listado ingresos CINEMA2.xlsx" \
  --egresos "../../ingresos_egresos_cartolas/emitir egresos CINEMA.xlsm" \
  --cartola ../../ingresos_egresos_cartolas/cartola_mayo_2026.pdf \
  --apertura "../../ingresos_egresos_cartolas/CONCILIACIÓN  MENSUAL CINEMA.xlsm" \
  --hoja-apertura "ABRIL´26"

# Simulación enero→mayo 2026 contra las conciliaciones del cliente (desde backend/)
uv run python -m motor.simular --datos ../../ingresos_egresos_cartolas \
  --planilla "CONCILIACIÓN  MENSUAL CINEMA.xlsm" --ingresos "listado ingresos CINEMA2.xlsx" \
  --egresos "emitir egresos CINEMA.xlsm" --desde 2026-01 --hasta 2026-05 \
  --cartola 2026-01=cartolas_estandar/cartola_enero_2026.xlsx --cartola 2026-02=cartola_febrero_2026.pdf \
  --cartola 2026-03=cartolas_estandar/cartola_marzo_2026.xlsx \
  --cartola 2026-04=cartolas_estandar/cartola_abril_2026.xlsx --cartola 2026-05=cartola_mayo_2026.pdf

# Base de datos (desde la raíz; requiere Docker Desktop corriendo)
cp .env.example .env                      # primera vez
docker compose up -d db                   # Postgres en localhost:5432
docker compose up --build                 # alternativa: db + backend en contenedores (:8000)

# Django (desde backend/)
uv run python manage.py migrate
uv run python manage.py createsuperuser   # crear los usuarios (o desde /admin)
uv run python manage.py demo_cinema --reiniciar  # piloto: dic-25 importado, ene–abr cerrados, may abierto
uv run python manage.py runserver         # http://localhost:8000/admin y /api/
uv run python manage.py makemigrations    # tras cambiar modelos

# Frontend (desde frontend/; requiere el backend en :8000)
pnpm install
pnpm dev                                  # http://localhost:5173
pnpm run lint && pnpm run build           # build = prueba de fuego del tipado
pnpm test                                 # Vitest + Testing Library
```

En Windows la consola necesita `PYTHONIOENCODING=utf-8` para imprimir tildes desde el CLI.

## 9. Guardrails

- **Cartola ilegible** (escaneada, fuente codificada): el parser aborta con `ErrorCartola` y un
  mensaje que pide el formato correcto. Nunca devolver movimientos vacíos como si fuera válida.
- **Archivos grandes:** rechazar planillas de más de 10.000 partidas en un request síncrono.
- **Uploads:** validar extensión y tamaño (máx. 10 MB); guardar el archivo original asociado a la
  conciliación para auditoría.
- **Conciliación cerrada = inmutable.** Reabrir requiere acción explícita y queda registrada.
- **El admin de Django es de solo lectura para conciliaciones**: todo cambio pasa por servicios.
- **Login protegido con CSRF** (DRF por defecto no lo exige a usuarios anónimos).
- **Antes de dar por terminado un cambio en el motor:** `uv run pytest` en verde, incluido
  `test_reproduce_conciliacion_mayo_2026` si los datos están disponibles.
- **Frontend:** si `pnpm run build` no compila, el cambio no está terminado.
- No hacer commits ni push sin que el usuario lo pida.

## 10. Decisiones abiertas

- Permisos por usuario/comunidad (hoy los usuarios del panel ven y editan todo).
- Pedir al cliente una columna "Nº operación" en la planilla de ingresos → cruce exacto de ingresos.
- Tabla RUT ↔ depto por comunidad (aprendida de cruces confirmados).
- Aviso de cheques caducados (> 60 días sin cobrar).
- Errores detectados en planillas del cliente para informarle: cierre 2021-02 y 2024-04 de
  ingresos y 2025-02 de egresos no cuadran con la suma de sus partidas; comprobante 1261 con
  fecha 18/08/2226; comprobantes 23–26 de ingresos y 1217 de egresos duplicados.
