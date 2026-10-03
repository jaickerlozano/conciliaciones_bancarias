"""CLI para correr una conciliación sin levantar el servidor.

Ejemplo:
    uv run python -m motor.cli --periodo 2026-05 \
        --ingresos "listado ingresos CINEMA2.xlsx" --egresos "emitir egresos CINEMA.xlsm" \
        --cartola cartola_mayo_2026.pdf \
        --apertura "CONCILIACIÓN  MENSUAL CINEMA.xlsm" --hoja-apertura "ABRIL´26"
"""

from __future__ import annotations

import argparse
import sys

from motor.conciliacion import conciliar
from motor.dominio import Periodo, ResultadoConciliacion, TipoPartida
from motor.parsers.cartolas import leer_cartola
from motor.parsers.conciliacion_cliente import leer_conciliacion_cliente
from motor.parsers.libros import leer_libro
from motor.texto import fmt_clp


def imprimir(r: ResultadoConciliacion) -> None:
    print(f"\nCONCILIACIÓN {r.periodo}")
    print(f"  Saldo conciliado mes anterior   {fmt_clp(r.saldo_anterior):>16}")
    print(f"  + Ingresos del mes              {fmt_clp(r.total_ingresos):>16}")
    print(f"  - Egresos del mes               {fmt_clp(r.total_egresos):>16}")
    print(f"  = Saldo según registro          {fmt_clp(r.saldo_registro):>16}")

    print(f"\n  Cheques girados no cobrados     {fmt_clp(r.total_cheques_pendientes):>16}")
    for p in r.cheques_pendientes:
        print(
            f"     {p.fecha or '':%d/%m/%Y}  #{p.comprobante:<5} ch {p.cheque:<8} "
            f"{fmt_clp(p.monto):>12}  {p.glosa[:55]}"
        )
    print(f"  Depósitos no registrados banco  {fmt_clp(r.total_depositos_pendientes):>16}")
    for p in r.depositos_pendientes:
        print(
            f"     {p.fecha or '':%d/%m/%Y}  #{p.comprobante:<5} depto {p.depto:<6} "
            f"{fmt_clp(p.monto):>12}"
        )
    print(f"  Movimientos no contabilizados   {fmt_clp(r.total_no_contabilizados):>16}")
    for m in r.movimientos_no_contabilizados:
        print(f"     {m.fecha:%d/%m/%Y}  {fmt_clp(m.monto_con_signo):>12}  {m.descripcion[:60]}")

    print(f"\n  Saldo según conciliación        {fmt_clp(r.saldo_conciliacion):>16}")
    print(f"  Saldo según banco               {fmt_clp(r.saldo_banco):>16}")
    print(
        f"  DIFERENCIA                      {fmt_clp(r.diferencia):>16}  "
        f"{'OK' if r.cuadra else '<-- NO CUADRA'}"
    )

    revisar = [c for c in r.cruces if c.requiere_revision]
    if revisar:
        print(f"\n  Cruces a revisar ({len(revisar)}):")
        for c in revisar:
            print(
                f"     #{c.partida.comprobante} {fmt_clp(c.partida.monto)} <-> "
                f"{c.movimiento.fecha:%d/%m} {c.movimiento.descripcion[:35]}: {c.nota}"
            )
    if r.advertencias:
        print("\n  Advertencias:")
        for a in r.advertencias:
            print(f"     - {a}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Concilia un mes con los archivos del cliente.")
    ap.add_argument("--periodo", required=True, help="YYYY-MM")
    ap.add_argument("--ingresos", required=True)
    ap.add_argument("--egresos", required=True)
    ap.add_argument("--cartola", required=True)
    ap.add_argument("--apertura", required=True, help="Planilla de conciliación del cliente")
    ap.add_argument("--hoja-apertura", required=True, help="Hoja del mes anterior")
    ap.add_argument(
        "--advertencias-libros",
        action="store_true",
        help="Mostrar también las advertencias de las planillas completas",
    )
    args = ap.parse_args(argv)

    periodo = Periodo.parse(args.periodo)
    ingresos = leer_libro(args.ingresos, TipoPartida.INGRESO)
    egresos = leer_libro(args.egresos, TipoPartida.EGRESO)
    apertura = leer_conciliacion_cliente(args.apertura, args.hoja_apertura).como_apertura()
    cartola = leer_cartola(args.cartola)

    resultado = conciliar(
        periodo, apertura, ingresos.partidas(periodo), egresos.partidas(periodo), cartola
    )
    imprimir(resultado)
    if args.advertencias_libros:
        print("\n  Advertencias de planillas:")
        for a in ingresos.advertencias + egresos.advertencias:
            print(f"     - {a}")
    return 0 if resultado.cuadra else 1


if __name__ == "__main__":
    sys.exit(main())
