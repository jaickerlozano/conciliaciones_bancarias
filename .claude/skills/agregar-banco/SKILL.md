---
name: agregar-banco
description: Agrega soporte para un nuevo banco o formato de cartola (PDF o Excel/CSV) al motor de conciliación. Usar cuando el usuario entregue una cartola de un banco o formato que el sistema aún no lee (BCI, Banco de Chile, Santander portal, etc.).
---

# Agregar un banco / formato de cartola

Necesitas al menos **una cartola real** del formato (idealmente dos: una de 1 página y otra de
varias). Los archivos reales NO se copian al repo (ver AGENTS.md §7).

## 1. Inspeccionar el archivo

- PDF: con pdfplumber, revisar `extract_text()` de la página 1.
  - Sin texto → escaneado: **no soportar**; pedir al cliente otro formato.
  - Texto `(cid:NN)` → fuente codificada: **no soportar**; pedir otro formato.
  - Texto OK → volcar `extract_words()` con `x0/x1/top` para ubicar columnas
    (ver cómo lo hace `motor/parsers/cartolas/santander_pdf.py`).
- Excel/CSV: ubicar la fila de encabezados y los nombres de columnas (fecha, descripción,
  nº documento, cargo/abono o monto con signo, saldo).
- Identificar: nº de cuenta, período desde/hasta, saldo inicial y saldo final, y cómo se
  distinguen cargos de abonos.

## 2. Implementar

Crear `backend/motor/parsers/cartolas/<banco>_<formato>.py`:

```python
@registrar
class BciExcelPortal(ParserCartola):
    banco = "BCI"
    formato = "excel-portal"
    extensiones = (".xlsx",)

    @classmethod
    def puede_leer(cls, ruta: Path) -> bool: ...   # detección barata y específica

    def leer(self, ruta: Path) -> Cartola: ...      # lanza ErrorCartola si algo falla
```

Reglas:
- Montos `int` en pesos, siempre positivos en `MovimientoBancario.monto`; el sentido va en `es_cargo`.
- `documento` = nº de cheque cuando el movimiento es un cheque (lo usa la capa 1 del cruce).
- Columnas por encabezado/posición de encabezado, nunca índices fijos.
- `puede_leer` no debe aceptar archivos de otros bancos: incluir el nombre del banco en la detección.
- Importar el módulo en `motor/parsers/cartolas/__init__.py` para que se registre.

## 3. Verificar

- Test en `backend/tests/test_motor/test_datos_reales.py` (marcado `datos_reales`) que compruebe
  saldos inicial/final, cantidad de movimientos y un cargo y un abono concretos.
- `cartola.validar()` debe devolver `[]` (saldo inicial + movimientos = saldo final).
- `uv run pytest` y `uv run ruff check .` en verde.
- Si existe la conciliación manual del cliente para ese mes, correr `python -m motor.cli` y
  comparar que la diferencia sea 0.
- Actualizar la tabla de formatos en AGENTS.md §7.
