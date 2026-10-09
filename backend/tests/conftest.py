"""Fixtures compartidas.

Los archivos reales del cliente NO se versionan (datos personales). Los tests marcados
`datos_reales` los buscan en $CONCILIACION_DATOS_DIR o, por defecto, en
../cinema (hermana del repo), y se omiten si no están.
Las cartolas BCI de la Comunidad Edificio Bustos se buscan en $CONCILIACION_BUSTOS_DIR o, por
defecto, en ../bustos; los de Ñuñoa Centro, en $CONCILIACION_NUNOA_DIR o ../nunoa_centro; los de
Lago Ranco, en $CONCILIACION_LAGO_RANCO_DIR o ../lago_ranco, y los de General Córdova, en
$CONCILIACION_GENERAL_CORDOVA_DIR o ../general_cordova. La cartola Banco de Chile de Monseñor
Eyzaguirre se busca en $CONCILIACION_MONSENOR_DIR o ../monsenor_eyzaguirre.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
DATOS_DIR = Path(os.environ.get("CONCILIACION_DATOS_DIR", RAIZ_REPO.parent / "cinema"))
BUSTOS_DIR = Path(os.environ.get("CONCILIACION_BUSTOS_DIR", RAIZ_REPO.parent / "bustos"))
NUNOA_DIR = Path(os.environ.get("CONCILIACION_NUNOA_DIR", RAIZ_REPO.parent / "nunoa_centro"))
LAGO_RANCO_DIR = Path(
    os.environ.get("CONCILIACION_LAGO_RANCO_DIR", RAIZ_REPO.parent / "lago_ranco")
)
GENERAL_CORDOVA_DIR = Path(
    os.environ.get("CONCILIACION_GENERAL_CORDOVA_DIR", RAIZ_REPO.parent / "general_cordova")
)
MONSENOR_DIR = Path(
    os.environ.get("CONCILIACION_MONSENOR_DIR", RAIZ_REPO.parent / "monsenor_eyzaguirre")
)
ESPACIO_LYON_DIR = Path(
    os.environ.get("CONCILIACION_ESPACIO_LYON_DIR", RAIZ_REPO.parent / "espacio_lyon")
)


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


@pytest.fixture(scope="session")
def datos_lago_ranco() -> Path:
    if not LAGO_RANCO_DIR.is_dir():
        pytest.skip(f"No están los archivos de Lago Ranco en {LAGO_RANCO_DIR}")
    return LAGO_RANCO_DIR


@pytest.fixture(scope="session")
def datos_general_cordova() -> Path:
    if not GENERAL_CORDOVA_DIR.is_dir():
        pytest.skip(f"No están los archivos de General Córdova en {GENERAL_CORDOVA_DIR}")
    return GENERAL_CORDOVA_DIR


@pytest.fixture(scope="session")
def datos_monsenor() -> Path:
    if not MONSENOR_DIR.is_dir():
        pytest.skip(f"No está la cartola Banco de Chile de Monseñor Eyzaguirre en {MONSENOR_DIR}")
    return MONSENOR_DIR


@pytest.fixture(scope="session")
def datos_espacio_lyon() -> Path:
    if not ESPACIO_LYON_DIR.is_dir():
        pytest.skip(f"No está la cartola Scotiabank de Espacio Lyon en {ESPACIO_LYON_DIR}")
    return ESPACIO_LYON_DIR
