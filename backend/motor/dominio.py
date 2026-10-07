"""Entidades del dominio de conciliación bancaria.

El motor es Python puro (sin Django): recibe datos ya parseados y devuelve resultados.
Todos los montos son enteros en pesos chilenos (CLP no tiene decimales).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from motor.texto import fmt_clp


class TipoPartida(StrEnum):
    INGRESO = "INGRESO"
    EGRESO = "EGRESO"


class Origen(StrEnum):
    PERIODO = "periodo"  # registrado/movido en el período que se concilia
    ARRASTRE = "arrastre"  # pendiente heredado de conciliaciones anteriores
    # diferencia entre lo registrado y lo cobrado de un cheque cruzado por número; queda
    # pendiente (y se arrastra) hasta que se resuelva
    DIFERENCIA = "diferencia"


@dataclass(frozen=True)
class Periodo:
    anio: int
    mes: int

    def __post_init__(self) -> None:
        if not 1 <= self.mes <= 12:
            raise ValueError(f"Mes inválido: {self.mes}")

    @classmethod
    def parse(cls, texto: str) -> Periodo:
        """Acepta 'YYYY-MM'."""
        anio, mes = texto.strip().split("-")
        return cls(int(anio), int(mes))

    def anterior(self) -> Periodo:
        return Periodo(self.anio - 1, 12) if self.mes == 1 else Periodo(self.anio, self.mes - 1)

    def siguiente(self) -> Periodo:
        return Periodo(self.anio + 1, 1) if self.mes == 12 else Periodo(self.anio, self.mes + 1)

    def __str__(self) -> str:
        return f"{self.anio:04d}-{self.mes:02d}"


@dataclass
class PartidaLibro:
    """Un ingreso o egreso registrado en las planillas del cliente (el "libro")."""

    tipo: TipoPartida
    comprobante: int | None
    fecha: date | None
    monto: int
    glosa: str = ""
    depto: str = ""
    cheque: str = ""  # nº de cheque, o texto como "PAC"/"TRANSF" si no es cheque
    origen: Origen = Origen.PERIODO

    @property
    def numero_cheque(self) -> str | None:
        """Nº de cheque normalizado si es numérico, si no None."""
        valor = self.cheque.strip()
        return valor if valor.isdigit() else None

    @property
    def clave(self) -> str:
        return f"{self.tipo.value}-{self.comprobante}"


@dataclass
class MovimientoBancario:
    """Una línea de la cartola. `monto` siempre positivo; `es_cargo` indica el sentido."""

    fecha: date
    descripcion: str
    monto: int
    es_cargo: bool
    documento: str = ""
    sucursal: str = ""
    origen: Origen = Origen.PERIODO

    @property
    def monto_con_signo(self) -> int:
        """Efecto sobre el saldo del banco: abonos positivos, cargos negativos."""
        return -self.monto if self.es_cargo else self.monto


@dataclass
class Cartola:
    banco: str
    cuenta: str
    numero: str
    desde: date
    hasta: date
    saldo_inicial: int
    saldo_final: int
    movimientos: list[MovimientoBancario] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)

    def validar(self) -> list[str]:
        """Comprueba que saldo inicial + movimientos = saldo final."""
        neto = sum(m.monto_con_signo for m in self.movimientos)
        esperado = self.saldo_inicial + neto
        if esperado != self.saldo_final:
            return [
                f"La cartola no cuadra: saldo inicial {fmt_clp(self.saldo_inicial)} + "
                f"movimientos {fmt_clp(neto)} = {fmt_clp(esperado)}, pero el saldo final "
                f"informado es {fmt_clp(self.saldo_final)}."
            ]
        return []


@dataclass
class EstadoApertura:
    """Lo que hereda una conciliación del mes anterior."""

    saldo_registro: int  # "saldo según registro" del mes anterior
    saldo_banco: int | None = None  # saldo final de la cartola anterior, para validar continuidad
    cheques_pendientes: list[PartidaLibro] = field(default_factory=list)
    depositos_pendientes: list[PartidaLibro] = field(default_factory=list)
    movimientos_no_contabilizados: list[MovimientoBancario] = field(default_factory=list)
    # movimientos de la cartola anterior: para descartar los repetidos si las cartolas se traslapan
    movimientos_cartola_anterior: list[MovimientoBancario] = field(default_factory=list)


class TipoCruce(StrEnum):
    CHEQUE = "cheque"  # nº de cheque idéntico al nº de documento del banco
    MONTO_FECHA = "monto_fecha"  # mismo monto y fecha cercana, sin ambigüedad
    SUGERIDO = "sugerido"  # mismo monto pero con ambigüedad o fecha lejana: revisar


@dataclass
class Cruce:
    partida: PartidaLibro
    movimiento: MovimientoBancario
    tipo: TipoCruce
    nota: str = ""

    @property
    def requiere_revision(self) -> bool:
        return self.tipo == TipoCruce.SUGERIDO or bool(self.nota)


@dataclass
class ResultadoConciliacion:
    periodo: Periodo
    saldo_anterior: int
    total_ingresos: int
    total_egresos: int
    redondeo: int
    cheques_pendientes: list[PartidaLibro]
    depositos_pendientes: list[PartidaLibro]
    movimientos_no_contabilizados: list[MovimientoBancario]
    saldo_banco: int
    cruces: list[Cruce]
    advertencias: list[str] = field(default_factory=list)
    movimientos_cartola: list[MovimientoBancario] = field(default_factory=list)
    movimientos_descartados: list[MovimientoBancario] = field(default_factory=list)

    @property
    def saldo_registro(self) -> int:
        return self.saldo_anterior + self.total_ingresos - self.total_egresos + self.redondeo

    @property
    def total_cheques_pendientes(self) -> int:
        return sum(p.monto for p in self.cheques_pendientes)

    @property
    def total_depositos_pendientes(self) -> int:
        return sum(p.monto for p in self.depositos_pendientes)

    @property
    def total_no_contabilizados(self) -> int:
        return sum(m.monto_con_signo for m in self.movimientos_no_contabilizados)

    @property
    def saldo_conciliacion(self) -> int:
        return (
            self.saldo_registro
            + self.total_cheques_pendientes
            - self.total_depositos_pendientes
            + self.total_no_contabilizados
        )

    @property
    def diferencia(self) -> int:
        return self.saldo_banco - self.saldo_conciliacion

    @property
    def cuadra(self) -> bool:
        return self.diferencia == 0

    def estado_cierre(self) -> EstadoApertura:
        """Estado de apertura para el mes siguiente."""
        return EstadoApertura(
            saldo_registro=self.saldo_registro,
            saldo_banco=self.saldo_banco,
            cheques_pendientes=list(self.cheques_pendientes),
            depositos_pendientes=list(self.depositos_pendientes),
            movimientos_no_contabilizados=list(self.movimientos_no_contabilizados),
            movimientos_cartola_anterior=list(self.movimientos_cartola),
        )
