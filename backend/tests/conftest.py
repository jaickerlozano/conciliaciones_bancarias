"""Fixtures compartidas.

Los archivos reales del cliente NO se versionan (datos personales). Los tests marcados
`datos_reales` los buscan en $CONCILIACION_DATOS_DIR o, por defecto, en
../ingresos_egresos_cartolas (hermana del repo), y se omiten si no están.
Las cartolas BCI de la Comunidad Edificio Bustos se buscan en $CONCILIACION_BUSTOS_DIR o, por
defecto, en ../bustos; los de Ñuñoa Centro, en $CONCILIACION_NUNOA_DIR o ../nunoa_centro.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
DATOS_DIR = Path(
    os.environ.get("CONCILIACION_DATOS_DIR", RAIZ_REPO.parent / "ingresos_egresos_cartolas")
)
BUSTOS_DIR = Path(os.environ.get("CONCILIACION_BUSTOS_DIR", RAIZ_REPO.parent / "bustos"))
NUNOA_DIR = Path(os.environ.get("CONCILIACION_NUNOA_DIR", RAIZ_REPO.parent / "nunoa_centro"))


@pytest.fixture(scope="session")
def datos() -> Path:
    if not DATOS_DIR.is_dir():
        pytest.skip(f"No están los archivos reales del cliente en {DATOS_DIR}")
    return DATOS_DIR


@pytest.fixture(scope="session")
def datos_bustos() -> Path:
    if not BUSTOS_DIR.is_dir():
        pytest.skip(f"No están las cartolas BCI del cliente en {BUSTOS_DIR}")
    return BUSTOS_DIR


@pytest.fixture(scope="session")
def datos_nunoa() -> Path:
    if not NUNOA_DIR.is_dir():
        pytest.skip(f"No están los archivos de Ñuñoa Centro en {NUNOA_DIR}")
    return NUNOA_DIR
