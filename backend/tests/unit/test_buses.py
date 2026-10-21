import pandas as pd

from sinsim.adapters.sources_to_pandapower import buses

DECLARED = {"GUATAPE": (115.0, 230.0), "AGUACHICA": (115.0,)}


def test_level_for_classifies_stn_str_sdl():
    assert buses.level_for(500) == "STN"
    assert buses.level_for(230) == "STN"
    assert buses.level_for(115) == "STR"
    assert buses.level_for(57.5) == "STR"
    assert buses.level_for(44) == "SDL"


def test_class_kv_unifies_equivalent_nominals():
    assert buses.class_kv(110.0) == 115.0 and buses.class_kv(115.0) == 115.0
    assert buses.class_kv(112.0) == 115.0 and buses.class_kv(121.4) == 115.0
    assert buses.class_kv(220.0) == 230.0 and buses.class_kv(238.2) == 230.0
    assert buses.class_kv(13.2) == 13.8 and buses.class_kv(500.0) == 500.0
    assert buses.class_kv(34.5) == 34.5 and buses.class_kv(44.0) == 44.0
    assert buses.class_kv(80.0) == 80.0  # sin nominal estándar dentro del 10 %


def test_nominal_kv_keeps_declared_standard():
    assert buses.nominal_kv(110.0) == 110.0 and buses.nominal_kv(112.0) == 110.0
    assert buses.nominal_kv(230.0) == 230.0 and buses.nominal_kv(238.2) == 230.0
    assert buses.nominal_kv(80.0) == 80.0


def test_canonical_kv_and_bus_id():
    assert buses.canonical_kv("GUATAPE", 113.0, DECLARED) == 115.0
    assert buses.canonical_kv("GUATAPE", 220.0, DECLARED) == 230.0
    assert buses.canonical_kv("DESCONOCIDA", 34.5, DECLARED) == 34.5
    assert buses.bus_id("AGUACHICA", 115.0) == "AGUACHICA|115"
    assert buses.bus_id("CAÑO LIMON", 34.5) == "CAÑO LIMON|34.5"
    assert buses.canonical_bus_id("GUATAPE", 221.0, DECLARED) == "GUATAPE|230"


def test_parse_connection_point_variants():
    assert buses.parse_connection_point("GUATAPE 220") == ("GUATAPE", 220.0)
    assert buses.parse_connection_point("SAN ANTONIO (BOYACA) 115") == (
        "SAN ANTONIO (BOYACA)",
        115.0,
    )
    assert buses.parse_connection_point("CAÑO LIMON 34.5") == ("CAÑO LIMON", 34.5)
    assert buses.parse_connection_point("EL PASO 110 kV") == ("EL PASO", 110.0)
    assert buses.parse_connection_point("-") is None
    assert buses.parse_connection_point(None) is None
    assert buses.parse_connection_point("SIN TENSION") is None


def test_parse_substations_groups_classes_and_keeps_declared_nominal():
    data = [
        {"elementName": "AGUABLANCA", "voltageLevel": [115, 110]},
        {"elementName": "ENVIGADO", "voltageLevel": [230, 220, 115, 110, 46]},
        {"elementName": "", "voltageLevel": [220]},
        {"elementName": "VACIA", "voltageLevel": None},
    ]
    declared = buses.parse_substations(data)
    assert declared == {"AGUABLANCA": (115.0,), "ENVIGADO": (44.0, 115.0, 230.0), "VACIA": ()}
    nominals = buses.parse_nominal_levels(data)
    assert nominals["AGUABLANCA"] == {115.0: 110.0}
    assert nominals["ENVIGADO"] == {230.0: 220.0, 115.0: 110.0, 44.0: 44.0}


def test_build_table_includes_used_sdl_buses_and_nominal():
    declared = {"AGUABLANCA": (115.0,), "VACIA": ()}
    nominals = {"AGUABLANCA": {115.0: 110.0}}
    table = buses.build_buses_table(declared, ["AGUABLANCA|13.8", "AGUABLANCA|115", "X|"], nominals)
    assert table.bus_id.tolist() == ["AGUABLANCA|115", "AGUABLANCA|13.8"]
    assert table.set_index("bus_id").level.to_dict() == {
        "AGUABLANCA|115": "STR",
        "AGUABLANCA|13.8": "SDL",
    }
    assert table.set_index("bus_id").nominal_kv.to_dict() == {
        "AGUABLANCA|115": 110.0,
        "AGUABLANCA|13.8": 13.8,
    }
    assert (~table.imputed).all()


def test_parse_subareas_strips_prefix_and_never_infers():
    data = [
        {"elementName": "AGUABLANCA", "subAreaName": "SubArea Valle"},
        {"elementName": "ENVIGADO", "subAreaName": "SubArea Antioquia"},
        {"elementName": "SIN AREA", "subAreaName": None},
        {"elementName": "VACIA", "subAreaName": "   "},
        {"elementName": "", "subAreaName": "SubArea Meta"},
    ]
    assert buses.parse_subareas(data) == {"AGUABLANCA": "Valle", "ENVIGADO": "Antioquia"}


def test_build_table_carries_subarea_to_every_level_of_the_substation():
    table = buses.build_buses_table(
        {"AGUABLANCA": (115.0,), "OTRA": (230.0,)},
        ["AGUABLANCA|13.8"],
        None,
        {"AGUABLANCA": "Valle"},
    )
    by_id = table.set_index("bus_id").subarea.to_dict()
    assert by_id["AGUABLANCA|115"] == "Valle" and by_id["AGUABLANCA|13.8"] == "Valle"
    assert by_id["OTRA|230"] is None


def test_parse_substation_coords_keeps_valid_colombian_points_only():
    data = [
        {"elementName": "AGUABLANCA", "latitude": 3.4098, "longitude": -76.48537},
        {"elementName": "SIN COORDENADAS", "latitude": None, "longitude": None},
        {"elementName": "FUERA", "latitude": 40.4, "longitude": -3.7},
        {"elementName": "TEXTO", "latitude": "6,25", "longitude": "-75,56"},
    ]
    assert buses.parse_substation_coords(data) == {
        "AGUABLANCA": (3.4098, -76.48537),
        "TEXTO": (6.25, -75.56),
    }
    table = buses.build_buses_table(
        {"AGUABLANCA": (115.0,), "FUERA": (230.0,)},
        [],
        None,
        None,
        buses.parse_substation_coords(data),
    )
    row = table.set_index("bus_id")
    assert (
        row.at["AGUABLANCA|115", "lat"] == 3.4098 and row.at["AGUABLANCA|115", "lon"] == -76.48537
    )
    assert pd.isna(row.at["FUERA|230", "lat"]) and pd.isna(row.at["FUERA|230", "lon"])
