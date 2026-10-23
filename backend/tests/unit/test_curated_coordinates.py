from dataclasses import dataclass

import pandas as pd

from sinsim.services.build_case import _apply_curated_coordinates


@dataclass(frozen=True)
class Coord:
    lat: float
    lon: float
    note: str


def buses() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "bus_id": ["PIMAMPIRO|230", "PIMAMPIRO|138", "JAMONDINO|230"],
            "substation": ["PIMAMPIRO", "PIMAMPIRO", "JAMONDINO"],
            "lat": [None, None, 1.17],
            "lon": [None, None, -77.31],
        }
    )


def test_fills_only_buses_without_paratec_coordinates():
    out, applied = _apply_curated_coordinates(
        buses(),
        {
            "PIMAMPIRO": Coord(0.4077455, -77.9471597, "Google Maps"),
            "JAMONDINO": Coord(9.0, 9.0, "no debe usarse"),
        },
    )
    pim = out.set_index("bus_id")
    assert pim.loc["PIMAMPIRO|230", "lat"] == 0.4077455
    assert pim.loc["PIMAMPIRO|138", "lon"] == -77.9471597
    # Una coordenada de PARATEC nunca se reemplaza.
    assert pim.loc["JAMONDINO|230", "lat"] == 1.17
    assert applied == [
        {
            "subestacion": "PIMAMPIRO",
            "lat": 0.4077455,
            "lon": -77.9471597,
            "barras": ["PIMAMPIRO|138", "PIMAMPIRO|230"],
            "fuente": "Google Maps",
        }
    ]


def test_without_table_nothing_changes():
    original = buses()
    out, applied = _apply_curated_coordinates(original, {})
    assert applied == []
    assert out is original


def test_adds_coordinate_columns_to_old_snapshots():
    old = buses().drop(columns=["lat", "lon"])
    out, applied = _apply_curated_coordinates(old, {"PIMAMPIRO": Coord(0.4, -77.9, "fuente")})
    assert {"lat", "lon"} <= set(out.columns)
    assert len(applied) == 1
