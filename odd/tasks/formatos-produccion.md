# Feature: formatos-produccion — bancos y planillas de las comunidades de partida

## Objetivo
Que las primeras cargas en producción no fallen: leer las cartolas de Scotiabank y Banco de
Chile, y las planillas de ingresos/egresos de Lago Ranco y General Córdova sin errores ni
partidas perdidas.

## Problema (evidencia 2026-10-09, archivos en `../general_cordova`, `../lago_ranco`,
`../monsenor_eyzaguirre`)
- Cartola General Córdova (Scotiabank, "ESTADO DE CUENTA N° 12", cta 000992892528,
  01-09-2026 a 30-09-2026): no la reconoce ningún parser. Montos con "$" y signo
  ("$ -6.867"), columnas Fecha | Descripción | N° Doc. | Cargos | Abonos | Saldo, saldo por fila;
  resumen Saldo Anterior / Depositos-Abonos / Cargos-Giros / Saldo Actual. Logo es imagen.
- Cartola Banco de Chile (Monseñor Eyzaguirre, muestra 2023, 5 páginas, cta 50579801,
  CARTOLA N° 10): no la reconoce. Columnas FECHA DIA/MES | DETALLE DE TRANSACCION | SUCURSAL |
  N° DOCTO | MONTO CHEQUES O CARGOS | MONTO DEPOSITOS O ABONOS | SALDO; primera fila
  "SALDO INICIAL".
- Egresos Lago Ranco: `_fila_cierre` toma como cierre cualquier celda con "CIERRE"; glosas de
  proveedores que la contienen cortan el bloque y se pierden partidas.
- Ingresos General Córdova: falla "no se encontró la fila de encabezados" (encabezado
  "COMP." sin alias) y el monto del ingreso viene en HABER (DEBE vacío).

## Alcance autorizado (usuario 2026-10-09: "necesito dejar listo este mvp…", "ok, continua")
T1 planillas robustas; T2 parser Scotiabank; T3 parser Banco de Chile; T4 documentación;
T5 segundo formato Scotiabank (Espacio Lyon).
Los bancos `scotiabank` y `chile` ya existen en `Banco` (sin migración).

## Restricciones
Datos del cliente fuera del repo (tests con fixtures sintéticas o `datos_reales` que se omiten
si faltan los archivos); montos int; artefactos en español; LF; commits solo con aprobación.

## Checklist
- [x] T1 libros.py: cierre estricto, alias "COMP.", monto desde DEBE o HABER según cuál tenga
  valor; tests sintéticos RED→GREEN + `datos_reales` de las 4 planillas. Ruta: delegada (writer).
  - Decisión: cierre = alguna celda empieza por "CIERRE" y la fila no es partida (concepto
    INGRESO/EGRESO + comprobante numérico). La regla "concepto ≠ EGRESO" rompía Cinema (fila de
    cierre con concepto EGRESO y la etiqueta en COMPROB).
  - Evidencia: sintéticos 3 RED → GREEN; reales 3 RED → 4 GREEN. Lago Ranco egresos recupera 32
    partidas; General Córdova ingresos 68 partidas (antes fallaba). Cinema/Bustos/Ñuñoa: mismos
    períodos, cantidades y totales (solo 2 advertencias nuevas DEBE+HABER en Ñuñoa).
- Suite completa con Postgres (`pytest --create-db`): 117 passed.
- [x] T2 Parser `ScotiabankPDF` + tests con la cartola real de General Córdova. Ruta: delegada.
  Evidencia: RED "No se reconoce el formato" + ImportError; GREEN `test_scotiabank.py` (26 movs,
  cargos $2.774.084, abonos $3.161.251 = resumen, sin advertencias, no reclama Santander/BCI/
  Banco de Chile). Sin cambios en servicios (la cuenta se compara sin ceros a la izquierda).
- [x] T3 Parser `BancoChilePDF` + tests con la cartola de Monseñor Eyzaguirre. Ruta: delegada.
  Evidencia: GREEN `test_banco_chile.py` (162 movs, cargos $14.295.270, abonos $23.107.319 =
  totales de la última página, saldo diario verificado, año DIA/MES con cruce dic→ene).
  Sin cambios en cruce.py (`_normalizar_doc` ya quita ceros a la izquierda).
- [x] T4 AGENTS.md (§2, §7 formatos y carpetas, §10 hallazgos Lago Ranco), conftest
  (`datos_monsenor`) y ruta Cinema `../ingresos_egresos_cartolas` → `../cinema` en conftest,
  settings, simular, cargar_piloto, .env.example, docker-compose, README y AGENTS. Alias
  "FBRERO" NO agregado: rompería la aserción de T1 (`test_planillas_nuevas.py`, 1 cierre
  ilegible) y obliga a tocar `NOMBRE_MES`; queda documentado como error del cliente.
  Checks: `pytest tests/test_motor` 89 passed, 0 skipped; ruff check/format OK; git diff --check
  OK. Suite completa (test_api) pendiente: Docker/Postgres no estaba corriendo.
- [x] T5 Segundo formato Scotiabank "ESTADO DE CUENTA CORRIENTE" (Espacio Lyon,
  `../espacio_lyon`): nuevo `ScotiabankPDFCuentaCorriente` en `scotiabank_cc_pdf.py` (formato
  `pdf-cuenta-corriente`), fixture `datos_espacio_lyon`, tests en `test_scotiabank.py`, AGENTS §7.
  Ruta: delegada (writer). Columnas por x de encabezados (DOCTO, CARGO, ABONO, DIARIO), fecha
  "07 / SEP" con año del período (reusa `fecha_dia_mes`), SALDO DIARIO verificado (acumula si
  falta), corta en "Resumen de Comisiones".
  Evidencia: RED `leer_cartola` → "No se reconoce el formato"; GREEN 120 movs, cargos
  $17.261.789 y abonos $21.472.777 = resumen, saldos $21.770.181 → $25.981.169, sin
  advertencias; los dos formatos Scotiabank no se reclaman entre sí ni a Santander/BCI/Banco de
  Chile. Cuenta "0-0099-28968-17": en la `CuentaBancaria` sirve "0099-28968-17" o "992896817".
  Checks: `pytest tests/test_motor` 101 passed, 0 skipped; suite completa 129 passed; ruff
  check/format OK; git diff --check OK.

## Criterios de aceptación
- Las 4 planillas se leen sin perder partidas; totales por período coherentes con sus cierres.
- Ambas cartolas: saldo inicial + Σ movimientos = saldo final, sin advertencias.
- Suite backend completa en verde; ruff limpio; Cinema/Bustos/Ñuñoa sin cambios.

## Entrega
Estrategia `ask-on-risk`; previsión ~600–800 líneas → probable cadena de PRs (T1 | T2+T3+T4).

## Progreso
- Rama `feat/formatos-produccion` desde `main` 2b98278 (incluye PR #11 que recuperó #7–#9).
- Espejo Engram `odd/formatos-produccion/tasks`: PENDIENTE (Engram no registra la sesión).

## Próximo paso
T1 (parent) y suite completa con Postgres; luego commits por unidad de trabajo.
