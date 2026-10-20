from sinsim.adapters.sources_to_pandapower import generators

DECLARED = {"GUATAPE": (220.0, 110.0), "SAN ANTONIO (BOYACA)": (115.0,)}


def unit(name, plant, cp, p, qmin, qmax):
    return {
        "elementName": name,
        "hydraulicPlant": plant,
        "thermalPlant": plant,
        "connectionPoint": cp,
        "ratedNetMaxP": p,
        "minQ": qmin,
        "maxQ": qmax,
        "elementStateName": "Operación",
        "operationMode": "Despachada Centralmente",
    }


def test_units_map_connection_point_and_q_limits_sign_convention():
    df = generators.parse_generators(
        [unit("GUATAPE 1", "GUATAPE", "GUATAPE 220", 70.2, 32.0, 32.0)],
        [unit("ARGOS 1", "ARGOS", "SAN ANTONIO (BOYACA) 115", 15, 11.25, 11.25)],
        [],
        [],
        DECLARED,
    )
    g = df.set_index("unit_id")
    assert g.loc["hidráulica:GUATAPE 1", "bus"] == "GUATAPE|230"  # clase 220/230 → 230
    assert g.loc["hidráulica:GUATAPE 1", "plant"] == "GUATAPE"
    assert g.loc["térmica:ARGOS 1", "bus"] == "SAN ANTONIO (BOYACA)|115"
    assert g.loc["hidráulica:GUATAPE 1", "q_absorb_mvar"] == 32.0  # magnitud positiva
    assert df.missing_params.map(len).sum() == 0


def test_missing_q_limits_are_optional_but_recorded():
    df = generators.parse_generators(
        [unit("U1", "P", "GUATAPE 220", 10, None, 1.05)], [], [], [], DECLARED
    )
    assert df.iloc[0].missing_params == ["q_limits"]
    assert df.iloc[0].bus == "GUATAPE|230"


def test_unparseable_or_unknown_connection_point_is_missing_bus():
    df = generators.parse_generators(
        [unit("U1", "P", "-", 10, 1, 1), unit("U2", "P", "NOEXISTE 220", 0, 1, 1)],
        [],
        [],
        [],
        DECLARED,
    )
    assert df.iloc[0].missing_params == ["bus"]
    assert set(df.iloc[1].missing_params) == {"bus", "p_max_mw"}


def test_renewable_plants_become_one_unit_per_plant():
    solar = [
        {
            "elementName": "ALMA II",
            "connectionPoint": "GUATAPE 110",
            "netEffectiveCapacity": 9.8,
            "absorptionCapacity": 3.43,
            "generationCapacity": 3.43,
            "elementStateName": "Operación",
            "operationMode": "No Despachada Centralmente",
        }
    ]
    wind = [
        {
            "elementName": "CARRETO",
            "connectionPoint": "GUATAPE 110",
            "netEffectiveCapacity": 9.1,
            "absorptionCapacityMaxPower": 3.0,
            "generationCapacityMaxPower": 3.0,
            "elementStateName": "Pruebas",
            "operationMode": "No Despachada Centralmente",
        }
    ]
    df = generators.parse_generators([], [], solar, wind, DECLARED)
    assert df.tech.tolist() == ["solar", "eólica"]
    assert df.unit.tolist() == df.plant.tolist() == ["ALMA II", "CARRETO"]
    assert df.p_max_mw.tolist() == [9.8, 9.1]
    assert df.q_gen_mvar.tolist() == [3.43, 3.0]
