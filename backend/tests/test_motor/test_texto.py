import pytest

from motor.texto import a_pesos, extraer_mes_anio, fmt_clp, normalizar, parse_monto_cl


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("CIERRE  MES MAYO  2026", (2026, 5)),
        ("CIERRE MES DE MAYO´26", (2026, 5)),
        ("CIERRE  MES AGOSTO2026", (2026, 8)),
        ("CIERRE MES DE SEPTIEMBRE'25", (2025, 9)),
        ("cierre mes diciembre 2024", (2024, 12)),
        ("CIERRE", None),
    ],
)
def test_extraer_mes_anio(texto, esperado):
    assert extraer_mes_anio(texto) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("1.379.448", 1379448),
        ("398.153", 398153),
        ("3 9 8 . 153", 398153),
        ("390.087,00", 390087),
        ("4.414", 4414),
        ("0", 0),
        ("1.000-", -1000),
    ],
)
def test_parse_monto_cl(texto, esperado):
    assert parse_monto_cl(texto) == esperado


def test_a_pesos_redondea_y_avisa_decimales():
    assert a_pesos(125660.78488) == (125661, True)
    assert a_pesos(422524.5) == (422525, True)
    assert a_pesos(80000) == (80000, False)


def test_normalizar():
    assert normalizar("  Depósitos  contabilizados ") == "DEPOSITOS CONTABILIZADOS"


def test_fmt_clp():
    assert fmt_clp(1379448) == "$1.379.448"
    assert fmt_clp(-66010) == "-$66.010"
