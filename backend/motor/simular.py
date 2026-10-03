"""Simula varios meses seguidos y los compara con las conciliaciones hechas a mano.

Parte de la conciliación del cliente del mes anterior al primero y luego encadena los meses
usando SOLO el resultado del programa (no las hojas del cliente), como ocurrirá en producción.
Lo único que se toma de la hoja de cada mes es el "Redondeo", porque es un ajuste manual.

    uv run python -m motor.simular --datos ../../ingresos_egresos_cartolas \
        --planilla "CONCILIACIÓN  MENSUAL CINEMA.xlsm" \
        --ingresos "listado ingresos CINEMA2.xlsx" --egresos "emitir egresos CINEMA.xlsm" \
        --desde 2026-01 --hasta 2026-05 \
        --cartola 2026-01=cartolas_estandar/cartola_enero_2026.xlsx \
        --cartola 2026-02=cartola_febrero_2026.pdf ...
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import openpyxl

from motor.conciliacion import conciliar
from motor.dominio import Periodo, ResultadoConciliacion, TipoPartida
from motor.parsers.cartolas import leer_cartola
from motor.parsers.conciliacion_cliente import ConciliacionCliente, leer_conciliacion_cliente
from motor.parsers.libros import leer_libro
from motor.texto import extraer_mes_anio, fmt_clp


@dataclass
class Comparacion:
    periodo: Periodo
    resultado: ResultadoConciliacion
    cliente: ConciliacionCliente | None
    diferencias: list[str] = field(default_factory=list)

    @property
    def coincide(self) -> bool:
        return self.cliente is not None and not self.diferencias


def hoja_del_periodo(ruta: Path, periodo: Periodo) -> str | None:
    """Busca la hoja cuyo nombre es el mes (ej. "ENERO'26", "ABRIL´26"); ignora copias "(2)"."""
    wb = openpyxl.load_workbook(ruta, read_only=True)
    try:
        nombres = wb.sheetnames
    finally:
        wb.close()
    candidatas = [n for n in nombres if extraer_mes_anio(n) == (periodo.anio, periodo.mes)]
    candidatas.sort(key=lambda n: ("(" in n, n))
    return candidatas[0] if candidatas else None


def _comparar(r: ResultadoConciliacion, c: ConciliacionCliente) -> list[str]:
    difs: list[str] = []

    def comparar_monto(nombre: str, nuestro: int, suyo: int | None, tolerancia: int = 1) -> None:
        if suyo is not None and abs(nuestro - suyo) > tolerancia:
            difs.append(f"{nombre}: programa {fmt_clp(nuestro)} vs cliente {fmt_clp(suyo)}")

    comparar_monto("Ingresos", r.total_ingresos, c.total_ingresos)
    comparar_monto("Egresos", r.total_egresos, c.total_egresos)
    comparar_monto("Saldo según registro", r.saldo_registro, c.saldo_registro)
    comparar_monto("Saldo banco", r.saldo_banco, c.saldo_banco, 0)
    for nombre, nuestros, suyos in (
        ("Cheques no cobrados", r.cheques_pendientes, c.cheques_pendientes),
        ("Depósitos no registrados", r.depositos_pendientes, c.depositos_pendientes),
    ):
        a = {p.comprobante for p in nuestros}
        b = {p.comprobante for p in suyos}
        if a != b:
            solo_programa = ", ".join(str(x) for x in sorted(a - b, key=str)) or "—"
            solo_cliente = ", ".join(str(x) for x in sorted(b - a, key=str)) or "—"
            difs.append(
                f"{nombre}: solo en programa [{solo_programa}]; solo en cliente [{solo_cliente}]"
            )
    nuestro_nc = sorted(m.monto_con_signo for m in r.movimientos_no_contabilizados)
    suyo_nc = sorted(m.monto_con_signo for m in c.movimientos_no_contabilizados)
    if nuestro_nc != suyo_nc:
        difs.append(
            "Movimientos no contabilizados: programa "
            f"[{', '.join(fmt_clp(x) for x in nuestro_nc) or '—'}] vs cliente "
            f"[{', '.join(fmt_clp(x) for x in suyo_nc) or '—'}]"
        )
    return difs


def simular(
    planilla: Path,
    ingresos: Path,
    egresos: Path,
    cartolas: dict[Periodo, Path],
    desde: Periodo,
    hasta: Periodo,
) -> list[Comparacion]:
    libro_ingresos = leer_libro(ingresos, TipoPartida.INGRESO)
    libro_egresos = leer_libro(egresos, TipoPartida.EGRESO)
    hoja_apertura = hoja_del_periodo(planilla, desde.anterior())
    if hoja_apertura is None:
        raise ValueError(f"No hay hoja de {desde.anterior()} en {planilla.name} para partir.")
    apertura = leer_conciliacion_cliente(planilla, hoja_apertura).como_apertura()

    resultados: list[Comparacion] = []
    periodo = desde
    while (periodo.anio, periodo.mes) <= (hasta.anio, hasta.mes):
        if periodo not in cartolas:
            raise ValueError(f"Falta la cartola de {periodo}.")
        hoja = hoja_del_periodo(planilla, periodo)
        cliente = leer_conciliacion_cliente(planilla, hoja) if hoja else None
        # el redondeo es un ajuste manual: se usa el que ingresó el cliente ese mes
        r = conciliar(
            periodo,
            apertura,
            libro_ingresos.partidas(periodo),
            libro_egresos.partidas(periodo),
            leer_cartola(cartolas[periodo]),
            redondeo=cliente.redondeo if cliente else 0,
        )
        difs = _comparar(r, cliente) if cliente else ["No hay hoja del cliente para comparar."]
        resultados.append(Comparacion(periodo, r, cliente, difs))
        apertura = r.estado_cierre()
        periodo = periodo.siguiente()
    return resultados


def imprimir(resultados: list[Comparacion]) -> None:
    columnas = ("Mes", "Redondeo", "Registro", "Cheques", "Depósitos", "No contab.", "Banco",
                "Dif.", "Revisar", "vs cliente")  # fmt: skip
    anchos = (8, 9, 13, 12, 12, 11, 13, 6, 8, 11)
    print()
    print(" ".join(f"{t:>{a}}" for t, a in zip(columnas, anchos, strict=True)))
    for c in resultados:
        r = c.resultado
        valores = (
            str(c.periodo), fmt_clp(r.redondeo), fmt_clp(r.saldo_registro),
            fmt_clp(r.total_cheques_pendientes), fmt_clp(r.total_depositos_pendientes),
            fmt_clp(r.total_no_contabilizados), fmt_clp(r.saldo_banco), fmt_clp(r.diferencia),
            str(sum(x.requiere_revision for x in r.cruces)),
            "IGUAL" if c.coincide else "DISTINTO",
        )  # fmt: skip
        print(" ".join(f"{v:>{a}}" for v, a in zip(valores, anchos, strict=True)))
    for c in resultados:
        if c.diferencias or c.resultado.advertencias:
            print(f"\n{c.periodo}:")
            for d in c.diferencias:
                print(f"   ≠ {d}")
            for a in c.resultado.advertencias:
                print(f"   ! {a}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Simula meses seguidos y compara con el cliente.")
    ap.add_argument("--datos", type=Path, default=Path("."), help="Carpeta base de los archivos")
    ap.add_argument("--planilla", required=True, help="Planilla CONCILIACIÓN MENSUAL del cliente")
    ap.add_argument("--ingresos", required=True)
    ap.add_argument("--egresos", required=True)
    ap.add_argument("--desde", required=True, help="AAAA-MM")
    ap.add_argument("--hasta", required=True, help="AAAA-MM")
    ap.add_argument("--cartola", action="append", default=[], help="AAAA-MM=ruta (repetible)")
    args = ap.parse_args(argv)

    cartolas = {}
    for item in args.cartola:
        periodo, _, ruta = item.partition("=")
        cartolas[Periodo.parse(periodo)] = args.datos / ruta
    resultados = simular(
        args.datos / args.planilla,
        args.datos / args.ingresos,
        args.datos / args.egresos,
        cartolas,
        Periodo.parse(args.desde),
        Periodo.parse(args.hasta),
    )
    imprimir(resultados)
    return 0 if all(c.coincide and c.resultado.cuadra for c in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
