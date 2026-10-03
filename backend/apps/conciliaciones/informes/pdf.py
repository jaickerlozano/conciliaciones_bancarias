"""Informe de conciliación en PDF (ReportLab: Python puro, funciona igual en Windows y Docker)."""

from __future__ import annotations

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from apps.conciliaciones.informes.datos import FilaMovimiento, FilaPartida, InformeConciliacion
from motor.texto import fmt_clp

# Paleta (la misma del panel)
MARCA = colors.HexColor("#1d5f59")
MARCA_CLARO = colors.HexColor("#effaf8")
TINTA = colors.HexColor("#0f172a")
TEXTO = colors.HexColor("#334155")
SUAVE = colors.HexColor("#64748b")
LINEA = colors.HexColor("#e2e8f0")
FONDO = colors.HexColor("#f8fafc")
VERDE, VERDE_CLARO = colors.HexColor("#047857"), colors.HexColor("#ecfdf5")
ROJO, ROJO_CLARO = colors.HexColor("#be123c"), colors.HexColor("#fff1f2")
VIOLETA = colors.HexColor("#6d28d9")

MARGEN = 16 * mm
ANCHO = A4[0] - 2 * MARGEN


def _estilo(nombre: str, **kw) -> ParagraphStyle:
    base = {"fontName": "Helvetica", "fontSize": 8.5, "leading": 11, "textColor": TEXTO}
    return ParagraphStyle(nombre, **(base | kw))


E_ETIQUETA = _estilo("etiqueta", fontName="Helvetica-Bold", fontSize=7.5, textColor=MARCA)
E_TITULO = _estilo("titulo", fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=TINTA)
E_SUBTITULO = _estilo("subtitulo", fontSize=10, leading=13)
E_SECCION = _estilo(
    "seccion", fontName="Helvetica-Bold", fontSize=10.5, leading=14, textColor=TINTA
)
E_CELDA = _estilo("celda", fontSize=8, leading=10)
E_CELDA_SUAVE = _estilo("celda_suave", fontSize=7.5, leading=9.5, textColor=SUAVE)
E_DERECHA = _estilo("derecha", fontSize=8, leading=10, alignment=TA_RIGHT)
E_NOTA = _estilo("nota", fontSize=8, leading=10.5, textColor=SUAVE)


def _fecha(valor) -> str:
    return valor.strftime("%d/%m/%Y") if valor else "—"


def _texto(valor: str) -> str:
    return (valor or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class _CanvasNumerado(Canvas):
    """Canvas en dos pasadas para poder escribir "Página X de Y"."""

    def __init__(self, *args, informe: InformeConciliacion, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas: list[dict] = []
        self._informe = informe

    def showPage(self):  # noqa: N802 (API de ReportLab)
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._decorar(total)
            super().showPage()
        super().save()

    def _decorar(self, total: int) -> None:
        inf = self._informe
        ancho, alto = A4
        # barra superior de marca
        self.setFillColor(MARCA)
        self.rect(0, alto - 5, ancho, 5, stroke=0, fill=1)
        # pie
        self.setStrokeColor(LINEA)
        self.line(MARGEN, 14 * mm, ancho - MARGEN, 14 * mm)
        self.setFont("Helvetica", 7)
        self.setFillColor(SUAVE)
        self.drawString(MARGEN, 10 * mm, f"Gaudi Administraciones · {inf.comunidad} · {inf.titulo}")
        generado = f"Generado el {inf.generado_en:%d/%m/%Y %H:%M}"
        if inf.generado_por:
            generado += f" por {inf.generado_por}"
        self.drawString(MARGEN, 7 * mm, generado)
        self.drawRightString(ancho - MARGEN, 10 * mm, f"Página {self._pageNumber} de {total}")
        if not inf.cerrada:
            self.saveState()
            self.setFillColor(colors.Color(0.75, 0.08, 0.24, alpha=0.07))
            self.setFont("Helvetica-Bold", 90)
            self.translate(ancho / 2, alto / 2)
            self.rotate(35)
            self.drawCentredString(0, -30, "BORRADOR")
            self.restoreState()


def _encabezado(inf: InformeConciliacion) -> list:
    izquierda = [
        Paragraph(
            "CONCILIACIÓN BANCARIA" if not inf.es_saldo_inicial else "SALDO INICIAL", E_ETIQUETA
        ),
        Spacer(0, 3),
        Paragraph(_texto(inf.periodo_texto), E_TITULO),
        Spacer(0, 2),
        Paragraph(f"<b>{_texto(inf.comunidad)}</b>", E_SUBTITULO),
        Paragraph(
            _texto(
                " · ".join(
                    x
                    for x in (
                        inf.comunidad_rut and f"RUT {inf.comunidad_rut}",
                        inf.comunidad_direccion,
                    )
                    if x
                )
            ),
            E_NOTA,
        ),
    ]
    cartola = "—"
    if inf.cartola_desde and inf.cartola_hasta:
        cartola = f"{_fecha(inf.cartola_desde)} al {_fecha(inf.cartola_hasta)}"
        if inf.cartola_numero:
            cartola = f"Nº {inf.cartola_numero} · {cartola}"
    if inf.cerrada and inf.cerrada_en:
        estado = f"{inf.estado_texto} el {inf.cerrada_en:%d/%m/%Y}"
        if inf.cerrada_por:
            estado += f" por {inf.cerrada_por}"
    else:
        estado = inf.estado_texto if inf.cerrada else f"{inf.estado_texto} (no cerrada)"
    datos = [
        ("Banco", inf.banco),
        ("Cuenta corriente", inf.cuenta),
        ("Cartola", cartola),
        ("Estado", estado),
    ]
    derecha = Table(
        [
            [Paragraph(k, E_CELDA_SUAVE), Paragraph(f"<b>{_texto(v)}</b>", E_CELDA)]
            for k, v in datos
        ],
        colWidths=[28 * mm, 58 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), FONDO),
                ("BOX", (0, 0), (-1, -1), 0.6, LINEA),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ]
        ),
    )
    return [
        Table(
            [[izquierda, derecha]],
            colWidths=[ANCHO - 88 * mm, 88 * mm],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
                ]
            ),
        ),
        Spacer(0, 8 * mm),
    ]


def _resumen(inf: InformeConciliacion) -> list:
    r = inf.resumen
    filas: list[tuple[str, str, int | None, bool]] = []  # signo, etiqueta, monto, fuerte
    if inf.es_saldo_inicial:
        filas.append(("", "Saldo según registro", r.saldo_registro, True))
    else:
        filas += [
            ("", f"Saldo conciliado {inf.periodo_anterior_texto}", r.saldo_anterior, False),
            ("+", f"Ingresos de {inf.periodo_texto}", r.total_ingresos, False),
            ("−", f"Egresos de {inf.periodo_texto}", r.total_egresos, False),
        ]
        if r.redondeo:
            filas.append(("+", "Redondeo", r.redondeo, False))
        filas.append(("", "Saldo según registro", r.saldo_registro, True))
    inicio_conciliacion = len(filas)
    filas += [
        ("+", "Cheques girados no cobrados", r.total_cheques_pendientes, False),
        (
            "−",
            "Depósitos contabilizados no registrados en banco",
            r.total_depositos_pendientes,
            False,
        ),
        ("+", "Movimientos no contabilizados", r.total_no_contabilizados, False),
        ("", "Saldo según conciliación", r.saldo_conciliacion, True),
        ("", "Saldo según banco", r.saldo_banco, True),
    ]
    datos = [
        [
            s,
            Paragraph(f"<b>{e}</b>" if f else e, E_CELDA),
            Paragraph(f"<b>{fmt_clp(m or 0)}</b>" if f else fmt_clp(m or 0), E_DERECHA),
        ]
        for s, e, m, f in filas
    ]
    cuadra = r.diferencia == 0
    estilo = [
        ("FONTSIZE", (0, 0), (0, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), SUAVE),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, LINEA),
        ("LINEABOVE", (0, inicio_conciliacion), (-1, inicio_conciliacion), 1.2, TINTA),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    tabla = Table(
        datos, colWidths=[6 * mm, ANCHO - 6 * mm - 70 * mm - 30 * mm, 30 * mm], style=estilo
    )

    color, fondo = (VERDE, VERDE_CLARO) if cuadra else (ROJO, ROJO_CLARO)
    hexa = color.hexval()
    veredicto = "CUADRA" if cuadra else "HAY DIFERENCIA"
    caja = Table(
        [
            [
                Paragraph(
                    f"<font color='{hexa}'><b>{veredicto}</b></font>",
                    E_ETIQUETA,
                )
            ],
            [
                Paragraph(
                    f"<font size='22' color='{hexa}'><b>{fmt_clp(r.diferencia or 0)}</b></font>",
                    _estilo("dif", leading=26),
                )
            ],
            [Paragraph("Diferencia = saldo banco − saldo según conciliación", E_NOTA)],
        ],
        colWidths=[64 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fondo),
                ("BOX", (0, 0), (-1, -1), 0.8, color),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (0, 0), 10),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
            ]
        ),
    )
    return [
        Paragraph("Cálculo de la conciliación", E_SECCION),
        Spacer(0, 2 * mm),
        Table(
            [[tabla, caja]],
            colWidths=[ANCHO - 70 * mm, 70 * mm],
            style=TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (0, 0), 0),
                    ("RIGHTPADDING", (-1, 0), (-1, 0), 0),
                    ("LEFTPADDING", (1, 0), (1, 0), 6 * mm),
                ]
            ),
        ),
        Spacer(0, 7 * mm),
    ]


def _estilo_tabla(n_filas: int, con_total: bool) -> TableStyle:
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), MARCA_CLARO),
        ("TEXTCOLOR", (0, 0), (-1, 0), MARCA),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, MARCA),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINEA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
    ]
    for i in range(2, n_filas, 2):
        estilo.append(("BACKGROUND", (0, i), (-1, i), FONDO))
    if con_total:
        estilo += [
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, TINTA),
            ("BACKGROUND", (0, -1), (-1, -1), colors.white),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
    return TableStyle(estilo)


def _marca_anterior(fila) -> str:
    return " <font color='#6d28d9' size='6.5'>(mes anterior)</font>" if fila.mes_anterior else ""


def _seccion_partidas(
    titulo: str, filas: list[FilaPartida], columna_ref: str, vacio: str, es_egreso: bool
) -> list:
    total = sum(f.monto for f in filas)
    cabecera = Paragraph(
        f"{titulo} <font color='#64748b' size='9'>· {fmt_clp(total)}</font>", E_SECCION
    )
    if not filas:
        return [
            KeepTogether([cabecera, Spacer(0, 1.5 * mm), Paragraph(vacio, E_NOTA)]),
            Spacer(0, 6 * mm),
        ]
    datos = [["Fecha", "Nº", columna_ref, "Detalle", "Monto"]]
    for f in filas:
        detalle = _texto(f.detalle) or ("—" if es_egreso else "Gasto común")
        datos.append(
            [
                _fecha(f.fecha),
                str(f.comprobante or "—"),
                Paragraph(_texto(f.referencia) or "—", E_CELDA),
                Paragraph(detalle + _marca_anterior(f), E_CELDA),
                fmt_clp(f.monto),
            ]
        )
    datos.append(["", "", "", Paragraph("<b>Total</b>", E_DERECHA), fmt_clp(total)])
    anchos = [18 * mm, 13 * mm, 25 * mm, ANCHO - 18 * mm - 13 * mm - 25 * mm - 26 * mm, 26 * mm]
    tabla = Table(datos, colWidths=anchos, repeatRows=1, style=_estilo_tabla(len(datos), True))
    tabla.setStyle([("FONTSIZE", (0, 1), (-1, -1), 8)])
    return [cabecera, Spacer(0, 1.5 * mm), tabla, Spacer(0, 6 * mm)]


def _seccion_movimientos(filas: list[FilaMovimiento]) -> list:
    total = sum(f.monto_con_signo for f in filas)
    cabecera = Paragraph(
        f"Movimientos no contabilizados <font color='#64748b' size='9'>· {fmt_clp(total)}</font>",
        E_SECCION,
    )
    if not filas:
        nota = "Todos los movimientos de la cartola están registrados en las planillas."
        return [
            KeepTogether([cabecera, Spacer(0, 1.5 * mm), Paragraph(nota, E_NOTA)]),
            Spacer(0, 6 * mm),
        ]
    datos = [["Fecha", "Descripción", "Documento", "Monto"]]
    for f in filas:
        datos.append(
            [
                _fecha(f.fecha),
                Paragraph(_texto(f.descripcion) + _marca_anterior(f), E_CELDA),
                f.documento or "—",
                fmt_clp(f.monto_con_signo),
            ]
        )
    datos.append(
        ["", Paragraph("<b>Total</b> (abonos +, cargos −)", E_DERECHA), "", fmt_clp(total)]
    )
    anchos = [18 * mm, ANCHO - 18 * mm - 26 * mm - 26 * mm, 26 * mm, 26 * mm]
    tabla = Table(datos, colWidths=anchos, repeatRows=1, style=_estilo_tabla(len(datos), True))
    tabla.setStyle([("FONTSIZE", (0, 1), (-1, -1), 8)])
    return [cabecera, Spacer(0, 1.5 * mm), tabla, Spacer(0, 6 * mm)]


def _firmas() -> list:
    linea = Table(
        [["", "", ""], [Paragraph("Preparado por", E_NOTA), "", Paragraph("Revisado por", E_NOTA)]],
        colWidths=[70 * mm, ANCHO - 140 * mm, 70 * mm],
        style=TableStyle(
            [
                ("LINEBELOW", (0, 0), (0, 0), 0.6, TEXTO),
                ("LINEBELOW", (2, 0), (2, 0), 0.6, TEXTO),
                ("TOPPADDING", (0, 0), (-1, 0), 14 * mm),
            ]
        ),
    )
    return [KeepTogether([Spacer(0, 4 * mm), linea])]


def _anexo_cruces(inf: InformeConciliacion) -> list:
    if not inf.cruces:
        return []
    datos = [["Libro", "Banco", "Monto", "Cruce"]]
    for x in inf.cruces:
        libro = (
            f"<b>{x.partida_tipo} #{x.comprobante or '—'}</b> · {_fecha(x.fecha_libro)}"
            f"<br/><font color='#64748b'>{_texto(x.detalle_libro)[:90]}</font>"
        )
        banco = (
            f"{_fecha(x.fecha_banco)}"
            f"<br/><font color='#64748b'>{_texto(x.detalle_banco)[:70]}</font>"
        )
        cruce = x.tipo + (
            f"<br/><font color='#64748b'>Confirmó {_texto(x.confirmado_por)}</font>"
            if x.confirmado_por
            else ""
        )
        datos.append(
            [
                Paragraph(libro, E_CELDA),
                Paragraph(banco, E_CELDA),
                fmt_clp(x.monto),
                Paragraph(cruce, E_CELDA),
            ]
        )
    anchos = [ANCHO * 0.40, ANCHO * 0.32, 24 * mm, ANCHO * 0.28 - 24 * mm]
    tabla = Table(datos, colWidths=anchos, repeatRows=1, style=_estilo_tabla(len(datos), False))
    tabla.setStyle(
        [
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),
            ("ALIGN", (-1, 0), (-1, -1), "LEFT"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
        ]
    )
    return [
        PageBreak(),
        Paragraph("ANEXO", E_ETIQUETA),
        Paragraph(f"Cruces realizados ({len(inf.cruces)})", E_SECCION),
        Paragraph(
            "Partidas de las planillas que se cruzaron con movimientos de la cartola "
            "(por nº de cheque, por monto y fecha, o manualmente).",
            E_NOTA,
        ),
        Spacer(0, 3 * mm),
        tabla,
    ]


def generar_pdf(inf: InformeConciliacion) -> bytes:
    salida = BytesIO()
    doc = SimpleDocTemplate(
        salida,
        pagesize=A4,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=14 * mm,
        bottomMargin=20 * mm,
        title=f"{inf.titulo} — {inf.comunidad}",
        author="Gaudi Administraciones",
        subject=f"{inf.banco} {inf.cuenta}",
    )
    historia = _encabezado(inf) + _resumen(inf)
    historia += _seccion_partidas(
        "Cheques girados no cobrados",
        inf.cheques,
        "Nº cheque",
        "Todos los cheques girados fueron cobrados.",
        es_egreso=True,
    )
    historia += _seccion_partidas(
        "Depósitos contabilizados no registrados en banco",
        inf.depositos,
        "Depto",
        "Todos los ingresos registrados aparecen en la cartola.",
        es_egreso=False,
    )
    historia += _seccion_movimientos(inf.no_contabilizados)
    historia += _firmas()
    historia += _anexo_cruces(inf)
    doc.build(historia, canvasmaker=lambda *a, **k: _CanvasNumerado(*a, informe=inf, **k))
    return salida.getvalue()
