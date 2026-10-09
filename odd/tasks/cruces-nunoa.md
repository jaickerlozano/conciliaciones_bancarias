# Feature: cruces-nunoa — diferencias de cheque, cruces agrupados y torres (Ñuñoa Centro)

## Objetivo
Que la conciliación de Ñuñoa Centro (BCI cta 11264837, edificio con torres 45 y 61) cuadre y
quede igual a la del cliente sin trucos de "redondeo".

## Problema (evidencia 2026-10-07, simulación junio 2026 desde MAYO'26 del cliente)
- Planillas: se leen bien (torres incluidas); ingresos/egresos ene–ago 2026 = hojas del cliente.
- Cheque 179840 (egreso #5310, sueldo) registrado por $654.852, el banco pagó $645.852. El cliente
  lo tapó con "Redondeo: 9.000 — ERROR PAGO BANCO…". El sistema cruza por nº de cheque con nota
  "monto distinto" pero la diferencia de $9.000 queda sin explicar y el redondeo admite ±$100.
- Depósito BCI 03/06 por $285.796 = ingresos #34917 ($168.465) + #34918 ($117.331) de mayo: el
  cruce es solo 1:1, así que quedan como depósitos pendientes + no contabilizado (se compensan).
- La torre no se guarda: "703" existe en las torres 45 y 61.

## Alcance autorizado (usuario: "sí" a los tres)
T1 diferencia de cobro de cheque como pendiente; T2 cruce agrupado N:1 (automático + manual);
T3 panel para cruce agrupado; T4 torre-depto.

## Diseño
- T1: al cruzar un cheque por número con monto distinto, la diferencia queda como pendiente:
  banco cobró menos → partida de egreso pendiente por la diferencia (se suma a cheques no
  cobrados); banco cobró más → movimiento no contabilizado (cargo) por la diferencia. Origen
  nuevo `diferencia`. Se arrastra mes a mes hasta que se resuelva.
- T2: tras las capas 1:1, combinaciones de 2–4 partidas libres del mismo tipo cuya suma = un
  movimiento libre, fechas dentro de 15 días; siempre SUGERIDO. Modelo: `Cruce.movimiento` pasa a
  FK (varias partidas → un movimiento) + campo `grupo`; confirmar/deshacer actúa sobre el grupo.
- T3: modal "Cruzar…" desde un movimiento permite elegir varias partidas (suma en vivo; habilita
  cuando la suma = monto). API `POST cruces/ {partidas: [ids], movimiento}`.
- T4: alias de columna TORRE en planillas → depto "45-703".

## Restricciones
Datos del cliente fuera del repo; artefactos en español; montos int; commits solo con aprobación.

## Checklist
- [x] T1 Diferencia de cobro de cheque → pendiente (motor + origen `diferencia` + migración + tests). Ruta: delegada (motor + modelos + tests).
  - Decisión aceptada: diferencias ≤ $100 no se separan (umbral = redondeo; Cinema ene-26 tiene
    un cheque con $1 de diferencia que el cliente absorbió con redondeo +1).
  - `deshacer_cruce` borra también la fila de diferencia asociada (si no, se contaría dos veces).
  - Evidencia: RED → GREEN; suite 83 passed; Ñuñoa jun-26 sin redondeo → dif $0 y pendiente $9.000;
    spot check del padre: test Ñuñoa + regresiones Cinema 3 passed.
- [x] T2 Cruce agrupado N:1 en motor, modelo, servicios, API, informes + tests. Ruta: delegada.
  - Motor: capa 4 `_Grupos` en `cruce.py` (búsqueda con poda, ≤40 candidatas por movimiento,
    2–4 partidas, ventana 15 días, menor suma de días; empate → nota). Egresos con nº de cheque
    no se agrupan. `TipoCruce.AGRUPADO` + `Cruce.grupo` ("G1"…; manual "M<id movimiento>").
  - Django: `Cruce.movimiento` FK `related_name="cruces"` + `grupo` (migración 0005);
    confirmar/deshacer actúan sobre el grupo; `cruzar_manual` acepta lista de partidas;
    API `{partidas: [ids], movimiento}` (sigue aceptando `{partida, movimiento}`).
  - Evidencia: RED (3 motor + 11 API fallando) → GREEN; suite backend 93 passed; ruff OK;
    sin migraciones pendientes. Ñuñoa jun-26 sin redondeo: único grupo G1 = #34917 + #34918
    ($285.796), diferencia $0. Test permanente de la diferencia de cheque (T1) en la API.
- [x] T3 Panel: cruce agrupado manual y visualización de grupos. Ruta: delegada (frontend).
  - "Cruzar…" desde un movimiento: partidas compatibles de monto ≤ (exactas primero con
    "Monto exacto" y cruce de un clic; luego por cercanía de fecha), checkboxes, pie con
    "Seleccionado $X de $Y" + Faltan/Sobran/Cuadra; "Cruzar" solo si la suma = monto. Desde una
    partida sigue 1:1. API `{partidas: [ids], movimiento}`.
  - Por revisar: una tarjeta por grupo (partidas + total ↔ movimiento); "Confirmar todos (n)" y
    la pestaña cuentan grupos. Todos los cruces: filas del grupo juntas con insignia "Grupo G1";
    "Deshacer" actúa sobre el grupo. Insignia de tipo "Agrupado" (cielo).
  - Evidencia: RED (6 tests fallando) → GREEN; `pnpm run typecheck` OK, `pnpm run lint` 0
    avisos, `pnpm test` 17 passed (5 archivos), `pnpm run build` OK.
- [x] T4 Torre-depto en planillas. Ruta: delegada junto con T1 (mismo escritor).
  - Alias TORRE en libros.py → depto "61-703"; test con planilla sintética (test_libros.py).

## Criterios de aceptación
- Simulación junio Ñuñoa sin redondeo: diferencia $0; cheque 179840 deja $9.000 pendiente.
- El depósito de $285.796 se cruza (sugerido) con #34917 + #34918.
- Cinema ene–may y Bustos jun–jul siguen iguales al cliente. Suites backend/frontend en verde.

## Entrega
- Stacked PRs (estrategia elegida por el usuario), base `fix/limite-partidas` (PR #5).
  Una sola pasada de corte; ~1.620 líneas en total.

```
fix/limite-partidas (PR #5)
 └─ feat/torre-depto             A  6f1b914  torre-depto                         ~75
     └─ feat/diferencia-cobro-cheque  B  109ee72  diferencia de cheque pendiente  ~304
         └─ feat/cruce-agrupado       C  367e677  cruce agrupado (backend)         ~599 ⚠️ size:exception
             └─ feat/panel-cruce-agrupado D        panel cruce agrupado            ~650 ⚠️ size:exception
```

- C: motor + modelo + API + informes del agrupado son un solo cambio (no funciona por partes).
- D: pantalla + sus tests + este documento.
- Cada unidad verificada con BD de tests recreada (`--create-db`): A 76, B 83, C 93 tests;
  D frontend 17 tests + build. El último árbol es idéntico al estado de trabajo final.
- Espejo Engram `odd/cruces-nunoa/tasks`: PENDIENTE (Engram no disponible en la sesión).

## Próximo paso
Revisión e integración de las PRs A→D (base PR #5).
