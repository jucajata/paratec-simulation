from datetime import date
from pathlib import Path

import pytest

from sinsim.adapters.storage.equivalences import CsvEquivalenceRepository
from sinsim.domain.errors import DomainError

RES_HEADER = "resource,kind,paratec_ids,connection_bus,valid_from,valid_to,note\n"
NODE_HEADER = "node,ucp,vn_kv,substation,paratec_vn_kv,valid_from,valid_to,note\n"


def write(tmp_path: Path, resources: str, nodes: str) -> CsvEquivalenceRepository:
    (tmp_path / "recursos_despacho.csv").write_text(RES_HEADER + resources, encoding="utf-8")
    (tmp_path / "nodos_demanda.csv").write_text(NODE_HEADER + nodes, encoding="utf-8")
    return CsvEquivalenceRepository(tmp_path)


def test_fixture_tables_resolve_known_rows(equivalences_repo):
    on = date(2026, 10, 20)
    guavio = equivalences_repo.resolve_resource("GUAVIO", on)
    assert guavio is not None and guavio.kind == "plant" and guavio.paratec_ids == ["GUAVIO"]
    link = equivalences_repo.resolve_resource("ECUADOR230_1", on)
    assert link is not None and link.kind == "intl_link" and link.connection_bus == "JAMONDINO|230"
    assert equivalences_repo.resolve_resource("PLANTA_FANTASMA", on) is None
    node = equivalences_repo.resolve_node("ANCONSU1", 110.0, on)
    assert node is not None and node.substation == "ANCON SUR (EPM)" and node.paratec_vn_kv == 110.0
    assert equivalences_repo.resolve_node("ANCONSU1", 220.0, on) is None
    assert len(equivalences_repo.sha256) == 64
    assert len(equivalences_repo.resources) > 10 and len(equivalences_repo.nodes) > 10


def test_validity_window_is_respected(tmp_path: Path):
    repo = write(
        tmp_path,
        "X,plant,X_OLD,,2020-01-01,2024-12-31,\nX,plant,X_NEW,,2025-01-01,,\n",
        "N,U,110,S,110,2025-06-01,2025-12-31,\n",
    )
    assert repo.resolve_resource("X", date(2024, 6, 1)).paratec_ids == ["X_OLD"]
    assert repo.resolve_resource("X", date(2025, 6, 1)).paratec_ids == ["X_NEW"]
    assert repo.resolve_resource("X", date(2019, 1, 1)) is None
    assert repo.resolve_node("N", 110, date(2025, 7, 1)) is not None
    assert repo.resolve_node("N", 110, date(2026, 1, 1)) is None


def test_overlapping_validity_is_rejected(tmp_path: Path):
    with pytest.raises(DomainError) as exc:
        write(tmp_path, "X,plant,A,,2020-01-01,,\nX,plant,B,,2024-01-01,,\n", "")
    assert exc.value.code == "EQUIVALENCE_OVERLAP" and "X" in exc.value.detail
    with pytest.raises(DomainError):
        write(tmp_path, "", "N,U,110,S,110,2020-01-01,,\nN,U,110,S2,110,2021-01-01,,\n")


def test_invalid_kind_or_missing_valid_from(tmp_path: Path):
    with pytest.raises(DomainError):
        write(tmp_path, "X,otro,A,,2020-01-01,,\n", "")
    with pytest.raises(DomainError):
        write(tmp_path, "X,plant,A,,,,\n", "")
    with pytest.raises(DomainError):
        write(tmp_path, "", "N,U,110,S,110,,,\n")


def test_missing_files_give_empty_tables(tmp_path: Path):
    repo = CsvEquivalenceRepository(tmp_path)
    assert repo.resources == [] and repo.nodes == []
    assert repo.resolve_resource("X", date(2026, 1, 1)) is None


def test_sha256_changes_with_content(tmp_path: Path):
    a = write(tmp_path, "X,plant,A,,2020-01-01,,\n", "").sha256
    b = write(tmp_path, "X,plant,B,,2020-01-01,,\n", "").sha256
    assert a != b


COORD_HEADER = "substation,lat,lon,valid_from,valid_to,note\n"


def test_curated_coordinates_are_read_with_validity_and_source(tmp_path: Path):
    (tmp_path / "coordenadas_subestaciones.csv").write_text(
        COORD_HEADER + "PIMAMPIRO,0.4077455,-77.9471597,2020-01-01,,Google Maps (CELEC EP)\n",
        encoding="utf-8",
    )
    repo = write(tmp_path, "", "")
    coords = repo.substation_coords(date(2026, 10, 20))
    assert set(coords) == {"PIMAMPIRO"}
    assert coords["PIMAMPIRO"].lat == pytest.approx(0.4077455)
    assert coords["PIMAMPIRO"].lon == pytest.approx(-77.9471597)
    assert "Google Maps" in coords["PIMAMPIRO"].note
    assert repo.substation_coords(date(2019, 1, 1)) == {}


def test_curated_coordinates_change_the_tables_checksum(tmp_path: Path):
    before = write(tmp_path, "", "").sha256
    (tmp_path / "coordenadas_subestaciones.csv").write_text(
        COORD_HEADER + "PIMAMPIRO,0.4,-77.9,2020-01-01,,fuente\n", encoding="utf-8"
    )
    assert CsvEquivalenceRepository(tmp_path).sha256 != before


@pytest.mark.parametrize(
    "row",
    [
        "PIMAMPIRO,95,-77.9,2020-01-01,,fuente\n",  # latitud fuera de rango
        "PIMAMPIRO,abc,-77.9,2020-01-01,,fuente\n",  # no numérica
        "PIMAMPIRO,0.4,-77.9,2020-01-01,,\n",  # sin fuente
        "PIMAMPIRO,0.4,-77.9,2020-01-01,,a\nPIMAMPIRO,0.5,-77.9,2024-01-01,,b\n",  # solapada
    ],
)
def test_invalid_curated_coordinates_are_rejected(tmp_path: Path, row: str):
    (tmp_path / "coordenadas_subestaciones.csv").write_text(COORD_HEADER + row, encoding="utf-8")
    with pytest.raises(DomainError):
        write(tmp_path, "", "")
